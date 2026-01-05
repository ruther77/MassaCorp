#!/usr/bin/env python3
"""
ETL METRO - Extraction des factures PDF (Version 3 - Par tableaux)
===================================================================
Parser qui respecte les colonnes du PDF en utilisant les coordonnées.

Colonnes détectées dans les PDFs METRO:
- EAN (x: 25-85)
- N° Article (x: 89-120)
- Désignation (x: 123-250)
- Régie (x: 255-275)
- Vol% (x: 276-305)
- VAP (x: 306-340)
- Volume (x: 340-390)
- Prix unitaire (x: 395-450)
- Colisage (x: 438-465)
- Qté (x: 467-485)
- Montant (x: 489-520)
- TVA (x: 523-540)
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import uuid

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False
    logger.warning("pdfplumber non installé: pip install pdfplumber")


@dataclass
class LigneFacture:
    """Ligne de facture extraite."""
    ean: str
    article_numero: Optional[str] = None
    designation: Optional[str] = None
    regie: Optional[str] = None
    vol_alcool: Optional[float] = None
    vap: Optional[float] = None
    volume: Optional[float] = None
    prix_unitaire: Optional[float] = None
    colisage: int = 1
    quantite: int = 1
    montant: Optional[float] = None
    code_tva: Optional[str] = None
    taux_tva: float = 20.0
    ligne_numero: int = 0
    raw_data: Optional[Dict] = None


@dataclass
class Facture:
    """Facture extraite."""
    source_file: str
    numero: Optional[str] = None
    date_facture: Optional[str] = None
    magasin: Optional[str] = None
    client: Optional[str] = None
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None
    lignes: List[LigneFacture] = field(default_factory=list)


class MetroParserV3:
    """
    Parser METRO V3 - Extraction par coordonnées de colonnes.

    Utilise les positions X des mots pour extraire chaque colonne
    correctement, évitant le mélange de lignes.
    """

    # Définition des colonnes (plages X approximatives)
    COLUMNS = {
        'ean': (20, 88),
        'article': (89, 122),
        'designation': (123, 254),
        'regie': (255, 275),
        'vol': (276, 308),
        'vap': (306, 345),
        'volume': (340, 394),
        'prix': (395, 450),
        'colisage': (438, 466),
        'qte': (467, 488),
        'montant': (489, 522),
        'tva': (523, 545),
    }

    # Tolérance pour le groupement par ligne (en points)
    LINE_TOLERANCE = 5

    # TVA codes
    TVA_MAP = {'A': 0.0, 'B': 5.5, 'C': 10.0, 'D': 20.0}

    # Patterns
    RE_EAN = re.compile(r'^[0-9]{8,14}$')
    RE_ARTICLE = re.compile(r'^[0-9]{6,7}$')
    RE_NUMBER = re.compile(r'^[0-9]+[,.]?[0-9]*$')
    RE_DATE = re.compile(r'(\d{2})-(\d{2})-(\d{4})')
    RE_FACTURE_NUM = re.compile(r'(\d/\d\(\d+\)\d+/\d+)')
    RE_TOTAL_HT = re.compile(r'Total\s*H\.?T\.?\s*:?\s*([\d\s]+[,.]?\d*)', re.IGNORECASE)

    def __init__(self):
        self.stats = {'fichiers': 0, 'lignes': 0, 'erreurs': 0}

    def parse_number(self, s: str) -> Optional[float]:
        """Parse un nombre français (virgule décimale, espaces)."""
        if not s:
            return None
        try:
            cleaned = s.replace(' ', '').replace(',', '.')
            return float(cleaned)
        except:
            return None

    def parse_int(self, s: str) -> Optional[int]:
        """Parse un entier."""
        if not s:
            return None
        try:
            return int(s.replace(' ', ''))
        except:
            return None

    def group_words_by_line(self, words: List[Dict]) -> Dict[float, List[Dict]]:
        """
        Groupe les mots par ligne en utilisant leur coordonnée Y.

        Les mots avec des Y proches (< LINE_TOLERANCE) sont sur la même ligne.
        """
        if not words:
            return {}

        # Trier par Y puis X
        sorted_words = sorted(words, key=lambda w: (w['top'], w['x0']))

        lines = {}
        current_y = None

        for word in sorted_words:
            y = word['top']

            # Trouver une ligne existante proche
            found_line = None
            for line_y in lines.keys():
                if abs(y - line_y) < self.LINE_TOLERANCE:
                    found_line = line_y
                    break

            if found_line is not None:
                lines[found_line].append(word)
            else:
                lines[y] = [word]

        return lines

    def extract_column(self, words: List[Dict], col_name: str) -> str:
        """
        Extrait le texte d'une colonne spécifique.

        Args:
            words: Liste des mots de la ligne
            col_name: Nom de la colonne

        Returns:
            Texte concaténé de la colonne
        """
        if col_name not in self.COLUMNS:
            return ""

        x_min, x_max = self.COLUMNS[col_name]

        # Filtrer les mots dans la plage X
        col_words = []
        for w in words:
            word_center = (w['x0'] + w['x1']) / 2
            # Un mot est dans la colonne si son centre ou son début est dans la plage
            if x_min <= w['x0'] <= x_max or x_min <= word_center <= x_max:
                col_words.append(w)

        # Trier par X et concaténer
        col_words.sort(key=lambda w: w['x0'])
        return ' '.join(w['text'] for w in col_words).strip()

    def is_article_line(self, words: List[Dict]) -> bool:
        """
        Détermine si une ligne contient un article (commence par un EAN).
        """
        if not words:
            return False

        # Chercher un EAN dans la zone EAN
        ean_text = self.extract_column(words, 'ean')

        # Nettoyer et vérifier
        ean_clean = ean_text.replace(' ', '')
        return bool(self.RE_EAN.match(ean_clean))

    def parse_article_line(self, words: List[Dict], ligne_num: int) -> Optional[LigneFacture]:
        """
        Parse une ligne article.
        """
        try:
            # Extraire chaque colonne
            ean = self.extract_column(words, 'ean').replace(' ', '')
            article = self.extract_column(words, 'article').replace(' ', '')
            designation = self.extract_column(words, 'designation')
            regie = self.extract_column(words, 'regie').strip()
            vol = self.extract_column(words, 'vol')
            vap = self.extract_column(words, 'vap')
            volume = self.extract_column(words, 'volume')
            prix = self.extract_column(words, 'prix')
            colisage = self.extract_column(words, 'colisage')
            qte = self.extract_column(words, 'qte')
            montant = self.extract_column(words, 'montant')
            tva = self.extract_column(words, 'tva').strip()

            # Valider EAN
            if not self.RE_EAN.match(ean):
                return None

            # Créer la ligne
            ligne = LigneFacture(
                ean=ean,
                article_numero=article if self.RE_ARTICLE.match(article) else None,
                designation=designation if designation else None,
                regie=regie if regie in ['S', 'T', 'B', 'M', 'A'] else None,
                vol_alcool=self.parse_number(vol),
                vap=self.parse_number(vap),
                volume=self.parse_number(volume),
                prix_unitaire=self.parse_number(prix),
                colisage=self.parse_int(colisage) or 1,
                quantite=self.parse_int(qte) or 1,
                montant=self.parse_number(montant),
                code_tva=tva if tva in ['A', 'B', 'C', 'D'] else 'D',
                ligne_numero=ligne_num,
            )

            ligne.taux_tva = self.TVA_MAP.get(ligne.code_tva, 20.0)

            # Debug: stocker les données brutes
            ligne.raw_data = {
                'ean': ean, 'article': article, 'designation': designation,
                'regie': regie, 'vol': vol, 'vap': vap, 'volume': volume,
                'prix': prix, 'colisage': colisage, 'qte': qte,
                'montant': montant, 'tva': tva
            }

            return ligne

        except Exception as e:
            logger.debug(f"Erreur parsing ligne: {e}")
            return None

    def extract_header(self, text: str, facture: Facture):
        """Extrait les informations d'en-tête."""
        # Numéro facture
        m = self.RE_FACTURE_NUM.search(text)
        if m:
            facture.numero = m.group(1)

        # Date
        m = self.RE_DATE.search(text)
        if m:
            facture.date_facture = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        # Magasin
        if 'METRO' in text:
            # Chercher le nom du magasin après METRO
            m = re.search(r'METRO\s+([A-Z][A-Z\s]+?)(?:\s*\*|\s*PAGE|\n)', text)
            if m:
                facture.magasin = f"METRO {m.group(1).strip()}"

        # Client
        for client in ['NOUTAM', "L'INCONTOURNABLE", 'INCONTOURNABLE']:
            if client in text.upper():
                facture.client = client
                break

        # Total HT
        m = self.RE_TOTAL_HT.search(text)
        if m:
            facture.total_ht = self.parse_number(m.group(1))

    def extract_file(self, pdf_path: Path) -> Optional[Facture]:
        """
        Extrait une facture PDF METRO.

        Args:
            pdf_path: Chemin vers le fichier PDF

        Returns:
            Facture extraite ou None si erreur
        """
        if not HAS_PDFPLUMBER:
            logger.error("pdfplumber requis")
            return None

        try:
            facture = Facture(source_file=pdf_path.name)
            all_text = ""
            ligne_num = 0

            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extraire le texte pour l'en-tête
                    text = page.extract_text() or ""
                    all_text += text + "\n"

                    # Extraire les mots avec coordonnées
                    words = page.extract_words()

                    # Grouper par ligne
                    lines = self.group_words_by_line(words)

                    # Parser chaque ligne
                    for y in sorted(lines.keys()):
                        line_words = lines[y]

                        if self.is_article_line(line_words):
                            ligne_num += 1
                            ligne = self.parse_article_line(line_words, ligne_num)
                            if ligne:
                                facture.lignes.append(ligne)

            # Extraire en-tête
            self.extract_header(all_text, facture)

            self.stats['fichiers'] += 1
            self.stats['lignes'] += len(facture.lignes)

            return facture

        except Exception as e:
            logger.error(f"Erreur extraction {pdf_path}: {e}")
            self.stats['erreurs'] += 1
            return None

    def extract_directory(self, directory: Path) -> List[Facture]:
        """Extrait toutes les factures d'un répertoire."""
        factures = []
        pdf_files = list(directory.rglob('*.pdf'))
        logger.info(f"Trouvé {len(pdf_files)} PDFs dans {directory}")

        for pdf in pdf_files:
            facture = self.extract_file(pdf)
            if facture and facture.lignes:
                factures.append(facture)

        logger.info(f"Extraction terminée: {self.stats}")
        return factures

    def to_json(self, factures: List[Facture]) -> dict:
        """Convertit les factures en format JSON pour import."""
        return {
            'extraction_date': datetime.now().isoformat(),
            'stats': self.stats,
            'factures': [
                {
                    'numero': f.numero,
                    'date': f.date_facture,
                    'magasin': f.magasin or 'METRO',
                    'total_ht': f.total_ht or sum(l.montant or 0 for l in f.lignes),
                    'lignes': [
                        {
                            'ean': l.ean,
                            'article_numero': l.article_numero,
                            'designation': l.designation,
                            'quantite': l.quantite,
                            'colisage': l.colisage,
                            'prix_unitaire': l.prix_unitaire,
                            'montant': l.montant,
                            'taux_tva': l.taux_tva,
                            'code_tva': l.code_tva,
                            'regie': l.regie,
                            'vol_alcool': l.vol_alcool,
                        }
                        for l in f.lignes
                    ]
                }
                for f in factures
            ]
        }


def test_extraction(pdf_path: str):
    """Test d'extraction sur un fichier."""
    parser = MetroParserV3()
    facture = parser.extract_file(Path(pdf_path))

    if not facture:
        print("ÉCHEC extraction")
        return

    print("=" * 80)
    print("EXTRACTION V3 RÉUSSIE")
    print("=" * 80)
    print(f"Fichier: {facture.source_file}")
    print(f"Numéro: {facture.numero}")
    print(f"Date: {facture.date_facture}")
    print(f"Magasin: {facture.magasin}")
    print(f"Client: {facture.client}")
    print(f"Total HT: {facture.total_ht}")
    print(f"Nb lignes: {len(facture.lignes)}")

    print("\n" + "=" * 80)
    print("LIGNES EXTRAITES")
    print("=" * 80)

    total_calc = 0
    for l in facture.lignes[:15]:  # Afficher les 15 premières
        print(f"\n[{l.ligne_numero}] EAN: {l.ean}")
        print(f"    Art: {l.article_numero}")
        print(f"    Désig: {l.designation}")
        print(f"    Régie: {l.regie} | Vol: {l.vol_alcool}%")
        print(f"    Prix: {l.prix_unitaire}€ x Col:{l.colisage} x Qté:{l.quantite}")
        print(f"    Montant: {l.montant}€ | TVA: {l.code_tva}")

        if l.montant:
            total_calc += l.montant

    if len(facture.lignes) > 15:
        print(f"\n... et {len(facture.lignes) - 15} autres lignes")
        for l in facture.lignes[15:]:
            if l.montant:
                total_calc += l.montant

    print("\n" + "=" * 80)
    print(f"TOTAL CALCULÉ: {total_calc:.2f}€")
    print(f"TOTAL FACTURE: {facture.total_ht}€" if facture.total_ht else "TOTAL FACTURE: N/A")
    if facture.total_ht:
        print(f"ÉCART: {abs(total_calc - facture.total_ht):.2f}€")
    print("=" * 80)

    return facture


def compare_ean_consistency(pdf_path: str):
    """Compare les EAN extraits pour vérifier la cohérence."""
    parser = MetroParserV3()
    facture = parser.extract_file(Path(pdf_path))

    if not facture:
        return

    print("\n=== VÉRIFICATION COHÉRENCE EAN/DÉSIGNATION ===\n")

    ean_desig = {}
    for l in facture.lignes:
        if l.ean not in ean_desig:
            ean_desig[l.ean] = set()
        if l.designation:
            ean_desig[l.ean].add(l.designation)

    # Afficher les EAN avec plusieurs désignations
    multi = {ean: desigs for ean, desigs in ean_desig.items() if len(desigs) > 1}

    if multi:
        print(f"ATTENTION: {len(multi)} EAN avec désignations multiples:\n")
        for ean, desigs in list(multi.items())[:10]:
            print(f"  EAN {ean}:")
            for d in desigs:
                print(f"    - {d}")
    else:
        print("OK: Chaque EAN a une seule désignation")

    print(f"\nTotal: {len(ean_desig)} EAN uniques, {len(facture.lignes)} lignes")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]

        if sys.argv[-1] == '--check':
            compare_ean_consistency(pdf_path)
        else:
            test_extraction(pdf_path)
    else:
        print("Usage: python extract_metro_pdf_v3.py <chemin_pdf> [--check]")
