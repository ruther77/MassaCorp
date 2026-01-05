#!/usr/bin/env python3
"""
ETL METRO - Extraction des factures PDF (Version 2 - Optimisée)
================================================================
Parser amélioré pour le format spécifique des factures METRO.

Format ligne article METRO:
EAN ARTICLE DESIGNATION REGIE VOL% VAP VOLUME PRIX COLISAGE QTE MONTANT TVA

Exemple:
5010327325125 0799775 WH GLENFIDDICH 15A 40D 70CL S 40,0 0,280 0,700 32,940 1 20 658,80 D
"""

import re
import uuid
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


@dataclass
class LigneFacture:
    """Ligne de facture extraite."""
    batch_id: str
    source_file: str
    numero_facture: Optional[str] = None
    numero_interne: Optional[str] = None
    date_facture: Optional[str] = None
    fournisseur_nom: str = "METRO France"
    fournisseur_siret: str = "399315613"
    magasin_nom: Optional[str] = None
    client_nom: Optional[str] = None
    client_numero: Optional[str] = None
    ligne_numero: int = 0
    ean: Optional[str] = None
    article_numero: Optional[str] = None
    designation: Optional[str] = None
    categorie_source: Optional[str] = None
    regie: Optional[str] = None
    vol_alcool: Optional[float] = None
    vap: Optional[float] = None
    poids_volume: Optional[float] = None
    unite: str = "L"
    prix_unitaire: Optional[float] = None
    colisage: Optional[int] = None
    quantite: Optional[int] = None
    montant_ligne: Optional[float] = None
    code_tva: Optional[str] = None
    taux_tva: Optional[float] = None
    est_promo: bool = False
    cotis_secu: Optional[float] = None
    raw_line: Optional[str] = None


@dataclass
class FactureEntete:
    """En-tête de facture."""
    batch_id: str
    source_file: str
    numero_facture: Optional[str] = None
    numero_interne: Optional[str] = None
    date_facture: Optional[str] = None
    fournisseur_nom: str = "METRO France"
    fournisseur_siret: str = "399315613"
    magasin_nom: Optional[str] = None
    client_nom: Optional[str] = None
    client_numero: Optional[str] = None
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None
    lignes: List[LigneFacture] = field(default_factory=list)


class MetroParserV2:
    """
    Parser optimisé pour les factures METRO.

    Format de ligne article détecté:
    EAN(13) ARTICLE(7) DESIGNATION REGIE VOL% VAP VOLUME PRIX COLISAGE QTE MONTANT TVA [P]
    """

    # Regex compilés
    RE_EAN = re.compile(r'^0?(\d{8}|\d{13})')  # Gère EAN 8 ou 13 chiffres
    RE_ARTICLE = re.compile(r'\s+(\d{7})\s+')
    # Format alcool: REGIE VOL% VAP [a] VOLUME PRIX COLISAGE QTE MONTANT TVA
    # Note: montant peut avoir espace "1 542,40"
    RE_REGIE = re.compile(r'\s([STBMA])\s+(\d+[,.]?\d*)\s+(\d+[,.]?\d*)\s+[a-z]?\s*(\d+[,.]?\d*)\s+(\d+[,.]?\d*)\s+(\d+)\s+(\d+)\s+(\d[\d\s]*[,.]?\d*)\s+([ABCD])')
    # Format vin sans degré: T VOLUME PRIX COLISAGE QTE MONTANT TVA
    RE_VIN = re.compile(r'\s([T])\s+(\d+[,.]?\d*)\s+(\d+[,.]?\d*)\s+(\d+)\s+(\d+)\s+(\d[\d\s]*[,.]?\d*)\s+([ABCD])')
    # Format non-alcool avec montant pouvant avoir espace
    RE_NON_ALCOOL = re.compile(r'\s(\d+[,.]?\d*)\s+(\d+)\s+(\d+)\s+(\d[\d\s]*[,.]?\d*)\s+([ABCD])\s*(?:P)?$')
    RE_TOTAL_SECTION = re.compile(r'\*{2,3}\s*(SPIRITUEUX|CAVE|BRASSERIE|CHAMPAGNE|EPICERIE\s*SECHE|SURGELES|DROGUERIE|FOURNITURES|Articles\s*divers)\s*Total\s*:\s*(\d+[,.]?\d*)', re.IGNORECASE)
    RE_NUMERO_FACTURE = re.compile(r'(\d/\d\(\d+\)\d+/\d+)')
    RE_NUMERO_INTERNE = re.compile(r'\((\d{3}-\d{6})\)')
    RE_DATE = re.compile(r'Date\s*facture\s*\*?\s*:\s*(\d{2})-(\d{2})-(\d{4})')
    RE_CLIENT_NUMERO = re.compile(r'N[º°]\s*Client\s*:\s*(\d{3}\s+\d{8})')
    RE_MAGASIN = re.compile(r'METRO\s+([A-Z\s]+?)\s*\*?\s*PAGE')
    RE_TOTAL_HT = re.compile(r'Total\s*H\.?T\.?\s*:?\s*(\d[\d\s]*[,.]?\d*)', re.IGNORECASE)
    RE_TOTAL_TTC = re.compile(r'Total\s*à\s*payer\s*(\d[\d\s]*[,.]?\d*)', re.IGNORECASE)
    RE_COTIS = re.compile(r'COTIS\.?\s*SECURITE\s*SOCIALE\s*(\d+[,.]?\d*)')
    RE_PROMO = re.compile(r'\sP\s*$|PROMO|-\d+%')
    # Lignes à exclure (bas de page, transactions)
    RE_EXCLUDE = re.compile(r'RUM\s*:|CARTE\s+METRO|CMR\s+paiement|FIN\s+DE\s+LA\s+FACTURE|ENTREPOT', re.IGNORECASE)

    REGIE_MAP = {
        'SPIRITUEUX': 'S',
        'CAVE': 'T',
        'BRASSERIE': 'B',
        'CHAMPAGNE': 'M',
    }

    TVA_MAP = {'A': 0.0, 'B': 5.5, 'C': 10.0, 'D': 20.0}

    def __init__(self, batch_id: str = None):
        self.batch_id = batch_id or str(uuid.uuid4())
        self.stats = {'fichiers': 0, 'lignes': 0, 'erreurs': 0}

    def parse_number(self, s: str) -> Optional[float]:
        """Parse un nombre avec virgule, point et espaces."""
        if not s:
            return None
        try:
            # Nettoyer: supprimer espaces, remplacer virgule par point
            cleaned = s.replace(' ', '').replace(',', '.')
            return float(cleaned)
        except:
            return None

    def parse_line_article(self, line: str, current_categorie: str) -> Optional[LigneFacture]:
        """Parse une ligne article METRO."""

        # Exclure les lignes de fin de facture
        if self.RE_EXCLUDE.search(line):
            return None

        # Vérifier si c'est une ligne article (commence par EAN)
        ean_match = self.RE_EAN.match(line.strip())
        if not ean_match:
            return None

        ean = ean_match.group(1)

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            categorie_source=current_categorie,
            raw_line=line
        )

        # Extraire numéro article
        art_match = self.RE_ARTICLE.search(line)
        if art_match:
            ligne.article_numero = art_match.group(1)

        # Promo
        if self.RE_PROMO.search(line):
            ligne.est_promo = True

        # 1. Format alcool complet: REGIE VOL VAP VOLUME PRIX COLISAGE QTE MONTANT TVA
        regie_match = self.RE_REGIE.search(line)
        if regie_match:
            ligne.regie = regie_match.group(1)
            ligne.vol_alcool = self.parse_number(regie_match.group(2))
            ligne.vap = self.parse_number(regie_match.group(3))
            ligne.poids_volume = self.parse_number(regie_match.group(4))
            ligne.prix_unitaire = self.parse_number(regie_match.group(5))
            ligne.colisage = int(regie_match.group(6))
            ligne.quantite = int(regie_match.group(7))
            ligne.montant_ligne = self.parse_number(regie_match.group(8))
            ligne.code_tva = regie_match.group(9)
            ligne.taux_tva = self.TVA_MAP.get(ligne.code_tva, 20.0)

            # Désignation: entre article et régie
            start = art_match.end() if art_match else len(ean) + 1
            end = regie_match.start()
            ligne.designation = line[start:end].strip()

        else:
            # 2. Format vin (sans degré): T VOLUME PRIX COLISAGE QTE MONTANT TVA
            vin_match = self.RE_VIN.search(line)
            if vin_match:
                ligne.regie = vin_match.group(1)  # T
                ligne.poids_volume = self.parse_number(vin_match.group(2))
                ligne.prix_unitaire = self.parse_number(vin_match.group(3))
                ligne.colisage = int(vin_match.group(4))
                ligne.quantite = int(vin_match.group(5))
                ligne.montant_ligne = self.parse_number(vin_match.group(6))
                ligne.code_tva = vin_match.group(7)
                ligne.taux_tva = self.TVA_MAP.get(ligne.code_tva, 20.0)

                # Désignation
                start = art_match.end() if art_match else len(ean) + 1
                end = vin_match.start()
                ligne.designation = line[start:end].strip()
            else:
                # 3. Format non-alcool: POIDS PRIX COLISAGE QTE MONTANT TVA
                non_alc_match = self.RE_NON_ALCOOL.search(line)
                if non_alc_match:
                    ligne.prix_unitaire = self.parse_number(non_alc_match.group(1))
                    ligne.colisage = int(non_alc_match.group(2))
                    ligne.quantite = int(non_alc_match.group(3))
                    ligne.montant_ligne = self.parse_number(non_alc_match.group(4))
                    ligne.code_tva = non_alc_match.group(5)
                    ligne.taux_tva = self.TVA_MAP.get(ligne.code_tva, 20.0)

                    # Désignation
                    start = art_match.end() if art_match else len(ean) + 1
                    end = non_alc_match.start()
                    ligne.designation = line[start:end].strip()
                else:
                    # 4. Fallback: extraire ce qu'on peut
                    parts = line.split()
                    if len(parts) >= 3:
                        start_idx = 2 if art_match else 1
                        ligne.designation = ' '.join(parts[start_idx:-4]) if len(parts) > 6 else ' '.join(parts[start_idx:])

                        try:
                            if len(parts) >= 4:
                                ligne.montant_ligne = self.parse_number(parts[-2])
                                ligne.code_tva = parts[-1] if parts[-1] in 'ABCD' else 'D'
                                ligne.taux_tva = self.TVA_MAP.get(ligne.code_tva, 20.0)
                        except:
                            pass

        # Valider la ligne (montant doit être raisonnable)
        if ligne.montant_ligne and ligne.montant_ligne > 50000:
            return None  # Probablement un faux positif

        return ligne

    def extract_file(self, pdf_path: Path) -> Optional[FactureEntete]:
        """Extrait une facture PDF METRO."""
        if not HAS_PDFPLUMBER:
            logger.error("pdfplumber non installé")
            return None

        try:
            with pdfplumber.open(pdf_path) as pdf:
                facture = FactureEntete(
                    batch_id=self.batch_id,
                    source_file=pdf_path.name
                )

                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    all_text += text + "\n"

                # Extraire en-tête
                self._extract_header(facture, all_text)

                # Extraire lignes
                self._extract_lines(facture, all_text)

                # Extraire totaux
                self._extract_totals(facture, all_text)

                self.stats['fichiers'] += 1
                self.stats['lignes'] += len(facture.lignes)

                return facture

        except Exception as e:
            logger.error(f"Erreur {pdf_path}: {e}")
            self.stats['erreurs'] += 1
            return None

    def _extract_header(self, facture: FactureEntete, text: str):
        """Extrait l'en-tête."""
        # Numéro facture
        m = self.RE_NUMERO_FACTURE.search(text)
        if m:
            facture.numero_facture = m.group(1)

        # Numéro interne
        m = self.RE_NUMERO_INTERNE.search(text)
        if m:
            facture.numero_interne = m.group(1)

        # Date
        m = self.RE_DATE.search(text)
        if m:
            facture.date_facture = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        # Magasin
        m = self.RE_MAGASIN.search(text)
        if m:
            facture.magasin_nom = f"METRO {m.group(1).strip()}"

        # Client
        if 'NOUTAM' in text:
            facture.client_nom = 'NOUTAM'
        elif "L'INCONTOURNABLE" in text.upper():
            facture.client_nom = "L'INCONTOURNABLE"

        m = self.RE_CLIENT_NUMERO.search(text)
        if m:
            facture.client_numero = m.group(1)

    def _extract_lines(self, facture: FactureEntete, text: str):
        """Extrait les lignes articles."""
        lines = text.split('\n')
        current_categorie = None
        ligne_num = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Détecter section/catégorie
            total_match = self.RE_TOTAL_SECTION.search(line)
            if total_match:
                current_categorie = total_match.group(1).upper().strip()
                continue

            # Détecter nouvelle catégorie (avant Total)
            for cat in ['SPIRITUEUX', 'CAVE', 'BRASSERIE', 'CHAMPAGNE', 'EPICERIE', 'SURGELES', 'DROGUERIE']:
                if line.strip().upper().startswith(cat) and 'Total' not in line:
                    current_categorie = cat
                    break

            # Parser ligne article
            if self.RE_EAN.match(line):
                ligne = self.parse_line_article(line, current_categorie)
                if ligne:
                    ligne_num += 1
                    ligne.ligne_numero = ligne_num
                    ligne.source_file = facture.source_file
                    ligne.numero_facture = facture.numero_facture
                    ligne.numero_interne = facture.numero_interne
                    ligne.date_facture = facture.date_facture
                    ligne.magasin_nom = facture.magasin_nom
                    ligne.client_nom = facture.client_nom
                    ligne.client_numero = facture.client_numero

                    # Assigner régie depuis catégorie si non détectée
                    if not ligne.regie and current_categorie:
                        ligne.regie = self.REGIE_MAP.get(current_categorie)

                    facture.lignes.append(ligne)

    def _extract_totals(self, facture: FactureEntete, text: str):
        """Extrait les totaux."""
        m = self.RE_TOTAL_HT.search(text)
        if m:
            facture.total_ht = self.parse_number(m.group(1))

        m = self.RE_TOTAL_TTC.search(text)
        if m:
            facture.total_ttc = self.parse_number(m.group(1))

    def extract_directory(self, directory: Path) -> List[FactureEntete]:
        """Extrait toutes les factures d'un répertoire."""
        factures = []
        pdf_files = list(directory.rglob('*.pdf'))
        logger.info(f"Trouvé {len(pdf_files)} PDFs")

        for pdf in pdf_files:
            facture = self.extract_file(pdf)
            if facture:
                factures.append(facture)

        logger.info(f"Extraction: {self.stats}")
        return factures


def test_extraction(pdf_path: str):
    """Test d'extraction sur un fichier."""
    parser = MetroParserV2()
    facture = parser.extract_file(Path(pdf_path))

    if not facture:
        print("ÉCHEC extraction")
        return

    print("=" * 80)
    print("EXTRACTION RÉUSSIE")
    print("=" * 80)
    print(f"Fichier: {facture.source_file}")
    print(f"Numéro: {facture.numero_facture} ({facture.numero_interne})")
    print(f"Date: {facture.date_facture}")
    print(f"Magasin: {facture.magasin_nom}")
    print(f"Client: {facture.client_nom} ({facture.client_numero})")
    print(f"Total HT: {facture.total_ht}")
    print(f"Total TTC: {facture.total_ttc}")
    print(f"Nb lignes: {len(facture.lignes)}")

    print("\n" + "=" * 80)
    print("LIGNES EXTRAITES")
    print("=" * 80)

    total_calc = 0
    for i, l in enumerate(facture.lignes):
        print(f"\n[{i+1}] {l.designation or 'N/A'}")
        print(f"    EAN: {l.ean} | Art: {l.article_numero}")
        print(f"    Cat: {l.categorie_source} | Régie: {l.regie}")
        print(f"    Vol: {l.vol_alcool}% | Volume: {l.poids_volume}L")
        print(f"    Prix: {l.prix_unitaire}€ × Qté: {l.quantite} = {l.montant_ligne}€")
        print(f"    TVA: {l.code_tva} ({l.taux_tva}%) | Promo: {l.est_promo}")

        if l.montant_ligne:
            total_calc += l.montant_ligne

    print("\n" + "=" * 80)
    print(f"TOTAL CALCULÉ: {total_calc:.2f}€")
    print(f"TOTAL FACTURE: {facture.total_ht}€")
    print(f"ÉCART: {abs(total_calc - (facture.total_ht or 0)):.2f}€")
    print("=" * 80)

    return facture


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        test_extraction(sys.argv[1])
    else:
        print("Usage: python extract_metro_pdf_v2.py <chemin_pdf>")
