#!/usr/bin/env python3
"""
ETL EUROCIEL - Extraction du catalogue produits PDF
====================================================
Parser pour le catalogue produits EUROCIEL (références disponibles).

Formats extraits:
- REF: Code référence produit (ex: 10 126, 12 110)
- Désignation: Nom du produit
- Taille/Calibre: Format du produit (ex: 500/800, 1000+)
- Conditionnement: Poids ou quantité (ex: 10KG, 12X1KG)
- Origine: Pays d'origine si spécifié

Categories METRO (référentiel commun):
- Poisson (pages 4-8, 10): poissons, darnes, fumés, crevettes
- Volaille (page 9): volailles et viandes
- Legumes (pages 11-12): légumes et riz
- Epicerie (page 13): nourriture préparée

Changelog:
- v1.0 (2026-01-07): Version initiale
"""

import re
import json
import logging
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List, Dict, Set
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Mapping vers catégories METRO (référentiel commun)
CATEGORIES_PAR_PAGE = {
    4: 'Poisson',      # POISSONS ENTIERS & GV
    5: 'Poisson',      # POISSONS ENTIERS & GV
    6: 'Poisson',      # POISSONS ENTIERS & GV
    7: 'Poisson',      # DARNES DE POISSON
    8: 'Poisson',      # FUMÉS
    9: 'Volaille',     # VOLAILLES / VIANDES
    10: 'Poisson',     # CREVETTES / CRUSTACES
    11: 'Legumes',     # LÉGUMES
    12: 'Legumes',     # LÉGUMES / RIZ
    13: 'Epicerie',    # NOURRITURE PREPAREE
}

ORIGINES_CONNUES = {
    'SÉNÉGAL', 'SENEGAL', 'CHINE', 'VIÊTNAM', 'VIETNAM', 'ARGENTINE',
    'MAROC', 'SURINAME', 'URUGUAY', 'URUGUY', 'INDONÉSIE', 'INDONESIE',
    'PORTUGAL', 'CHILI', 'NZ', 'YÉMEN', 'YEMEN', 'CAMEROUN', 'INDE',
    'INDO', 'MADAGASCAR'
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ProduitCatalogue:
    """Produit du catalogue EUROCIEL."""
    reference: str
    designation: str
    categorie: str
    taille: Optional[str] = None
    conditionnement: Optional[str] = None
    poids_kg: Optional[float] = None
    origine: Optional[str] = None
    page_source: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionStats:
    """Statistiques d'extraction."""
    pages_traitees: int = 0
    produits_extraits: int = 0
    produits_par_categorie: Dict[str, int] = field(default_factory=dict)
    references_uniques: Set[str] = field(default_factory=set)
    erreurs: List[str] = field(default_factory=list)


# =============================================================================
# PARSER
# =============================================================================

class EurocielCatalogParser:
    """Parser pour catalogue EUROCIEL PDF."""

    def __init__(self):
        self.stats = ExtractionStats()
        self.produits: List[ProduitCatalogue] = []

        # Patterns pour extraction
        # Format: REF TAILLE KG [ORIGINE]
        # Ex: 10 126 200/400 4 SÉNÉGAL
        self.RE_LIGNE_STANDARD = re.compile(
            r'^(\d{2}\s?\d{3})\s+'           # REF: 10 126 ou 10126
            r'([\d/+\.]+(?:\s*[gG])?)\s+'    # TAILLE: 200/400, 1000+, 2/3
            r'(\d+(?:[,.]?\d*)?)\s*'          # KG: 4, 10, 23
            r'([A-ZÉÊÈÀÙÂÎÔ]+)?$',            # ORIGINE optionnelle
            re.IGNORECASE
        )

        # Format avec QTY: 10 302 20X500G VIETNAM
        self.RE_LIGNE_QTY = re.compile(
            r'^(\d{2}\s?\d{3})\s+'            # REF
            r'(\d+[xX]\d+(?:[gG][rR]?)?)\s*'  # QTY: 20X500G
            r'([A-ZÉÊÈÀÙÂÎÔ]+)?$',            # ORIGINE optionnelle
            re.IGNORECASE
        )

        # Format REF : xxx QTE/QTY : xxx
        self.RE_REF_QTE = re.compile(
            r'REF\s*:\s*(\d{2}\s?\d{3})',
            re.IGNORECASE
        )
        self.RE_QTE = re.compile(
            r'QT[EY]\s*:\s*(\d+[xX]?\d*[gGkK][gGrR]?)',
            re.IGNORECASE
        )

        # Format inline: 10 145 DUC 10KG
        self.RE_INLINE = re.compile(
            r'^(\d{2}\s?\d{3})\s+'            # REF
            r'([A-Z]+)\s+'                    # Marque/Type
            r'(\d+[xX]?\d*[gGkK][gGrR]?)$',   # Conditionnement
            re.IGNORECASE
        )

        # Format volailles: 12 230 10X1100GR
        self.RE_VOLAILLE = re.compile(
            r'^(\d{2}\s?\d{3})\s+'            # REF
            r'(\d+[xX]\d+[gGkK][gGrR]?)$',    # Conditionnement
            re.IGNORECASE
        )

    def _normalize_ref(self, ref: str) -> str:
        """Normalise une référence produit."""
        # Supprimer espaces et mettre en format XX XXX
        clean = ref.replace(' ', '')
        if len(clean) == 5:
            return f"{clean[:2]} {clean[2:]}"
        return ref.strip()

    def _parse_conditionnement(self, cond: str) -> tuple:
        """Parse conditionnement pour extraire poids."""
        if not cond:
            return None, None

        cond = cond.upper().strip()

        # Format: 10KG, 4KG
        match = re.match(r'^(\d+)\s*KG$', cond, re.IGNORECASE)
        if match:
            return cond, float(match.group(1))

        # Format: 12X1KG, 10X800GR
        match = re.match(r'^(\d+)[xX](\d+)(KG|GR?)$', cond, re.IGNORECASE)
        if match:
            qty = int(match.group(1))
            poids = int(match.group(2))
            unit = match.group(3).upper()
            if unit == 'KG':
                return cond, qty * poids
            else:  # GR
                return cond, qty * poids / 1000

        # Format: ±24
        match = re.match(r'^[±~]?(\d+)$', cond)
        if match:
            return f"{match.group(1)}KG", float(match.group(1))

        return cond, None

    def _detect_origine(self, text: str) -> Optional[str]:
        """Détecte l'origine dans un texte."""
        text_upper = text.upper()
        for origine in ORIGINES_CONNUES:
            if origine in text_upper:
                # Normaliser
                if origine in ('SÉNÉGAL', 'SENEGAL'):
                    return 'SÉNÉGAL'
                if origine in ('VIÊTNAM', 'VIETNAM'):
                    return 'VIETNAM'
                if origine in ('INDONÉSIE', 'INDONESIE', 'INDO'):
                    return 'INDONÉSIE'
                if origine == 'URUGUY':
                    return 'URUGUAY'
                if origine in ('YÉMEN', 'YEMEN'):
                    return 'YÉMEN'
                return origine
        return None

    def _extract_page_standard(self, text: str, page_num: int, categorie: str) -> List[ProduitCatalogue]:
        """Extrait les produits format standard (pages 4-6, poissons)."""
        produits = []
        lines = text.split('\n')

        current_product = None
        current_origine = None

        # Headers à ignorer
        HEADERS = {'REF', 'TAILLE', 'KG', 'ORIGINE', 'QTY', 'QTE', 'REF TAILLE KG',
                   'REF TAILLE KG ORIGINE', 'REF QTY', 'REF QTY ORIGINE'}

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Ignorer headers
            if line.upper() in HEADERS:
                continue

            # Ignorer le titre de catégorie
            if line == categorie:
                continue

            # Détecter nom de produit (en majuscules, pas de chiffres au début, au moins 3 chars)
            if (re.match(r'^[A-ZÉÊÈÀÙÂÎÔ][A-ZÉÊÈÀÙÂÎÔ\s\'/\-]+$', line)
                and not re.match(r'^\d', line)
                and len(line) >= 3):

                # Détecter origine dans le nom (ex: COURBINE SENEGAL)
                origine = self._detect_origine(line)
                if origine:
                    # Nettoyer le nom
                    for o in ORIGINES_CONNUES:
                        line = re.sub(rf"'{o}'|\b{o}\b", '', line, flags=re.IGNORECASE)
                    line = re.sub(r'\s+', ' ', line).strip()

                if line and len(line) >= 3:  # S'assurer qu'il reste un nom valide
                    current_product = line
                    current_origine = origine
                continue

            # Détecter origine seule (ex: 'YÉMEN')
            if re.match(r"^'[A-ZÉÊÈÀÙÂÎÔ]+'\s*$", line):
                current_origine = self._detect_origine(line)
                continue

            # Essayer les patterns de ligne
            if current_product:
                # Format standard: 10 126 200/400 4 [ORIGINE]
                match = self.RE_LIGNE_STANDARD.match(line)
                if match:
                    ref = self._normalize_ref(match.group(1))
                    taille = match.group(2)
                    kg = match.group(3)
                    origine = match.group(4) or current_origine

                    cond, poids = self._parse_conditionnement(kg + 'KG')

                    produit = ProduitCatalogue(
                        reference=ref,
                        designation=current_product,
                        categorie=categorie,
                        taille=taille,
                        conditionnement=cond,
                        poids_kg=poids,
                        origine=self._detect_origine(origine) if origine else current_origine,
                        page_source=page_num
                    )
                    produits.append(produit)
                    continue

                # Format QTY: 10 302 20X500G VIETNAM
                match = self.RE_LIGNE_QTY.match(line)
                if match:
                    ref = self._normalize_ref(match.group(1))
                    qty = match.group(2)
                    origine = match.group(3) or current_origine

                    cond, poids = self._parse_conditionnement(qty)

                    produit = ProduitCatalogue(
                        reference=ref,
                        designation=current_product,
                        categorie=categorie,
                        conditionnement=cond,
                        poids_kg=poids,
                        origine=self._detect_origine(origine) if origine else current_origine,
                        page_source=page_num
                    )
                    produits.append(produit)
                    continue

        return produits

    def _extract_page_ref_qte(self, text: str, page_num: int, categorie: str) -> List[ProduitCatalogue]:
        """Extrait les produits format REF:/QTE: (pages 7-8, 10-13)."""
        produits = []
        lines = text.split('\n')

        # Trouver paires REF/QTE
        refs = self.RE_REF_QTE.findall(text)
        qtes = self.RE_QTE.findall(text)

        # Extraire noms de produits (lignes en majuscules avant REF)
        product_names = []
        for i, line in enumerate(lines):
            line = line.strip()
            if re.match(r'^[A-ZÉÊÈÀÙÂÎÔ][A-ZÉÊÈÀÙÂÎÔ\s\'/\-]+$', line):
                if line not in ('REF', 'QTE', 'QTY', categorie) and 'REF' not in line:
                    product_names.append(line)

        # Matcher refs avec noms
        for i, ref in enumerate(refs):
            ref_norm = self._normalize_ref(ref)

            # Trouver le nom de produit correspondant
            designation = product_names[i] if i < len(product_names) else f"PRODUIT {ref_norm}"

            # Trouver conditionnement
            cond = qtes[i] if i < len(qtes) else None
            cond_str, poids = self._parse_conditionnement(cond) if cond else (None, None)

            produit = ProduitCatalogue(
                reference=ref_norm,
                designation=designation,
                categorie=categorie,
                conditionnement=cond_str,
                poids_kg=poids,
                page_source=page_num
            )
            produits.append(produit)

        return produits

    def _extract_page_volailles(self, text: str, page_num: int, categorie: str) -> List[ProduitCatalogue]:
        """Extrait les produits format volailles (page 9)."""
        produits = []
        lines = text.split('\n')

        current_product = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Nom de produit
            if re.match(r'^[A-ZÉÊÈÀÙÂÎÔ][A-ZÉÊÈÀÙÂÎÔ\s\'/\-]+$', line) and not any(c.isdigit() for c in line):
                if line not in ('REF', 'QTE', 'QTY', categorie):
                    current_product = line
                continue

            # Format: 12 230 10X1100GR
            match = self.RE_VOLAILLE.match(line)
            if match and current_product:
                ref = self._normalize_ref(match.group(1))
                cond = match.group(2)
                cond_str, poids = self._parse_conditionnement(cond)

                produit = ProduitCatalogue(
                    reference=ref,
                    designation=current_product,
                    categorie=categorie,
                    conditionnement=cond_str,
                    poids_kg=poids,
                    page_source=page_num
                )
                produits.append(produit)
                continue

            # Format inline: 10 145 DUC 10KG
            match = self.RE_INLINE.match(line)
            if match and current_product:
                ref = self._normalize_ref(match.group(1))
                marque = match.group(2)
                cond = match.group(3)
                cond_str, poids = self._parse_conditionnement(cond)

                produit = ProduitCatalogue(
                    reference=ref,
                    designation=f"{current_product} {marque}",
                    categorie=categorie,
                    conditionnement=cond_str,
                    poids_kg=poids,
                    page_source=page_num
                )
                produits.append(produit)

        return produits

    def extract_file(self, pdf_path: Path) -> List[ProduitCatalogue]:
        """Extrait tous les produits du catalogue."""
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber non installé: pip install pdfplumber")
            return []

        logger.info(f"Extraction catalogue: {pdf_path.name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    if page_num < 4 or page_num > 13:
                        continue  # Pages intro/fin

                    text = page.extract_text() or ''
                    categorie = CATEGORIES_PAR_PAGE.get(page_num, 'AUTRE')

                    # Choisir la méthode d'extraction selon la page
                    if page_num in (4, 5, 6):
                        # Poissons - format standard
                        prods = self._extract_page_standard(text, page_num, categorie)
                    elif page_num in (7, 8, 10, 11, 12, 13):
                        # Darnes, Fumés, Crevettes, Légumes, Préparés - format REF/QTE
                        prods = self._extract_page_ref_qte(text, page_num, categorie)
                        # Ajouter extraction standard aussi
                        prods.extend(self._extract_page_standard(text, page_num, categorie))
                    elif page_num == 9:
                        # Volailles - format mixte
                        prods = self._extract_page_volailles(text, page_num, categorie)
                        prods.extend(self._extract_page_ref_qte(text, page_num, categorie))
                    else:
                        prods = []

                    # Dédupliquer par référence
                    seen_refs = set()
                    for p in prods:
                        if p.reference not in seen_refs:
                            self.produits.append(p)
                            seen_refs.add(p.reference)
                            self.stats.references_uniques.add(p.reference)

                            # Stats par catégorie
                            if p.categorie not in self.stats.produits_par_categorie:
                                self.stats.produits_par_categorie[p.categorie] = 0
                            self.stats.produits_par_categorie[p.categorie] += 1

                    self.stats.pages_traitees += 1
                    logger.info(f"  Page {page_num} ({categorie}): {len(prods)} produits")

            self.stats.produits_extraits = len(self.produits)
            return self.produits

        except Exception as e:
            logger.error(f"Erreur extraction: {e}")
            self.stats.erreurs.append(str(e))
            return []

    def export_json(self, output_path: Path):
        """Exporte les produits en JSON."""
        data = {
            'extraction_date': datetime.now().isoformat(),
            'source': 'catalogue-2022-website-1-1.pdf',
            'fournisseur': 'EUROCIEL',
            'stats': {
                'pages_traitees': self.stats.pages_traitees,
                'produits_extraits': self.stats.produits_extraits,
                'references_uniques': len(self.stats.references_uniques),
                'par_categorie': self.stats.produits_par_categorie,
            },
            'produits': [p.to_dict() for p in self.produits]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Export JSON: {output_path}")

    def print_report(self):
        """Affiche le rapport d'extraction."""
        print("\n" + "=" * 60)
        print("RAPPORT EXTRACTION CATALOGUE EUROCIEL")
        print("=" * 60)
        print(f"Pages traitées:      {self.stats.pages_traitees}")
        print(f"Produits extraits:   {self.stats.produits_extraits}")
        print(f"Références uniques:  {len(self.stats.references_uniques)}")
        print("-" * 60)
        print("PAR CATÉGORIE:")
        for cat, count in sorted(self.stats.produits_par_categorie.items()):
            print(f"  {cat}: {count}")
        print("-" * 60)
        if self.stats.erreurs:
            print("ERREURS:")
            for err in self.stats.erreurs:
                print(f"  - {err}")
        print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Extraction catalogue EUROCIEL')
    parser.add_argument('pdf', nargs='?',
                        default='docs/EUROCIEL/catalogue-2022-website-1-1.pdf',
                        help='Chemin vers le PDF catalogue')
    parser.add_argument('--output', '-o', default='output/eurociel_catalogue.json',
                        help='Fichier JSON de sortie')
    parser.add_argument('--debug', action='store_true', help='Mode debug')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Erreur: fichier non trouvé: {pdf_path}")
        return 1

    # Extraction
    extractor = EurocielCatalogParser()
    produits = extractor.extract_file(pdf_path)

    # Export
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    extractor.export_json(output_path)

    # Rapport
    extractor.print_report()

    # Afficher quelques exemples
    print("\nEXEMPLES DE PRODUITS:")
    for p in produits[:10]:
        print(f"  [{p.reference}] {p.designation} - {p.conditionnement or 'N/A'} ({p.origine or 'N/A'})")

    return 0


if __name__ == '__main__':
    exit(main())
