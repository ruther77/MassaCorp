#!/usr/bin/env python3
"""
ETL TAIYAT - Extraction des factures PDF
=========================================
Parser pour les factures TAI YAT DISTRIBUTION.

Format ligne article TAIYAT:
    Colis | Designation | Cal | Cat | Provenance | P.U. HT | Pieces | Uv | P.U. TTC | MT TTC | T

Colonnes:
- Colis: Quantite de colis commandee
- Designation: Nom du produit
- Cal: Calibre (optionnel)
- Cat: Categorie (optionnel, souvent 1)
- Provenance: Pays d'origine
- P.U. HT: Prix unitaire HT
- Pieces: Nombre de pieces
- Uv: Unite de vente (c = colis)
- P.U. TTC: Prix unitaire TTC
- MT TTC: Montant total TTC
- T: Code TVA (1 = 5.5%, 2 = 20%)

Changelog:
- v1.0 (2026-01-07): Version initiale
"""

import re
import uuid
import json
import logging
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Codes TVA TAIYAT
TVA_CODES = {
    '1': 5.5,   # TVA reduite (alimentaire)
    '2': 20.0,  # TVA normale
}

# Pays connus (pour validation)
PAYS_CONNUS = {
    'FRANCE', 'BELGIQUE', 'PAYS-BAS', 'ALLEMAGNE', 'POLOGNE', 'ROYAUME-UNI',
    'ESPAGNE', 'ITALIE', 'MAROC', 'SENEGAL', 'MALI', 'COTE-D IVOIRE',
    'CAMEROUN', 'GHANA', 'NIGERIA', 'THAILANDE', 'CHINE', 'VIETNAM',
    'INDE', 'PAKISTAN', 'BRESIL', 'COLOMBIE', 'COSTA-RICA', 'CHILI',
    'PEROU', 'NORVEGE', 'ISLANDE', 'HOLLANDE', 'OUGANDA', 'KENYA'
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LigneTaiyat:
    """Ligne de facture TAIYAT extraite."""
    batch_id: str
    source_file: str
    numero_facture: Optional[str] = None
    date_facture: Optional[str] = None
    fournisseur_nom: str = "TAI YAT DISTRIBUTION"
    fournisseur_siret: str = "443695598"
    client_nom: Optional[str] = None
    client_code: Optional[str] = None
    ligne_numero: int = 0
    designation: Optional[str] = None
    provenance: Optional[str] = None
    calibre: Optional[str] = None
    colis: Optional[int] = None
    pieces: Optional[int] = None
    unite: str = "c"
    prix_unitaire_ht: Optional[float] = None
    prix_unitaire_ttc: Optional[float] = None
    montant_ttc: Optional[float] = None
    code_tva: Optional[str] = None
    taux_tva: Optional[float] = None
    est_remise: bool = False
    raw_line: Optional[str] = None
    parse_confidence: float = 0.0


@dataclass
class FactureTaiyat:
    """Facture TAIYAT complete."""
    batch_id: str
    source_file: str
    numero_facture: Optional[str] = None
    date_facture: Optional[str] = None
    echeance: Optional[str] = None
    fournisseur_nom: str = "TAI YAT DISTRIBUTION"
    fournisseur_siret: str = "443695598"
    client_nom: Optional[str] = None
    client_code: Optional[str] = None
    client_adresse: Optional[str] = None
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None
    lignes: List[LigneTaiyat] = field(default_factory=list)
    # Stats
    lignes_parsees: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0
    extraction_quality: float = 0.0


@dataclass
class ExtractionStats:
    """Statistiques globales d'extraction."""
    fichiers_traites: int = 0
    fichiers_succes: int = 0
    fichiers_echec: int = 0
    lignes_total: int = 0
    lignes_produits: int = 0
    lignes_remises: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0
    factures_sans_lignes: int = 0
    erreurs: List[str] = field(default_factory=list)


# =============================================================================
# PARSER ENGINE
# =============================================================================

class TaiyatParser:
    """
    Parser pour les factures TAI YAT DISTRIBUTION.
    """

    def __init__(self, batch_id: str = None, debug: bool = False):
        self.batch_id = batch_id or str(uuid.uuid4())
        self.debug = debug
        self.stats = ExtractionStats()
        self._current_facture_rejections = 0
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile les patterns regex."""

        # Numero de facture
        self.RE_FACTURE = re.compile(r'FACTURE\s*N[°o]?\s*(\d+)', re.IGNORECASE)

        # Date facture (format DD/MM/YYYY)
        self.RE_DATE = re.compile(r':\s*(\d{2}/\d{2}/\d{4})')

        # Code client
        self.RE_CODE_CLIENT = re.compile(r'Code\s*Client\s*:\s*(\d+)', re.IGNORECASE)

        # Echeance
        self.RE_ECHEANCE = re.compile(r'[EÉ]ch[ée]ance\s*:\s*(\d{2}/\d{2}/\d{4})', re.IGNORECASE)

        # Total TTC - NET A PAYER
        self.RE_TOTAL_TTC = re.compile(r'(\d[\d\s]*[,.]?\d*)\s*EUR', re.IGNORECASE)

        # Ligne article TAIYAT - pattern principal
        # Format: COLIS DESIGNATION [CAL] [CAT] [PROVENANCE] P.U.HT PIECES UV P.U.TTC MT_TTC T
        self.RE_LIGNE = re.compile(
            r'^(\d+(?:[,.]\d+)?)\s+'           # Colis (peut etre decimal)
            r'(.+?)\s+'                         # Designation
            r'(\d+[,.]\d+)\s+'                  # P.U. HT
            r'(\d+)\s+'                         # Pieces
            r'([a-z])\s+'                       # UV (unite)
            r'(\d+[,.]\d+(?:-\d+[,.]\d+%)?)\s+' # P.U. TTC (peut avoir remise -XX.X%)
            r'(\d+[,.]\d+)\s+'                  # MT TTC
            r'([12])\s*$'                       # Code TVA
        )

        # Pattern alternatif plus souple
        self.RE_LIGNE_ALT = re.compile(
            r'^(\d+(?:[,.]\d+)?)\s+'           # Colis
            r'(.+?)\s+'                         # Designation
            r'(\d+[,.]\d+)\s+'                  # Un prix
            r'(\d+)\s+'                         # Pieces
            r'([a-z])\s+'                       # UV
            r'(.+?)\s+'                         # P.U. TTC
            r'(\d+[,.]\d+)\s+'                  # MT TTC
            r'([12])\s*$'                       # Code TVA
        )

        # Pattern pour detecter les pays d'origine
        self.RE_PAYS = re.compile(
            r'\b(' + '|'.join(re.escape(p) for p in PAYS_CONNUS) + r')\b',
            re.IGNORECASE
        )

    def parse_number(self, s: str) -> Optional[float]:
        """Parse un nombre."""
        if not s:
            return None
        try:
            # Nettoyer
            cleaned = s.replace(' ', '').replace(',', '.')
            # Gerer les remises (-XX.X%)
            if '-' in cleaned and '%' in cleaned:
                cleaned = re.sub(r'-[\d.]+%', '', cleaned)
            value = float(cleaned)
            if value < 0 or value > 100000:
                return None
            return value
        except (ValueError, TypeError):
            return None

    def parse_integer(self, s: str) -> Optional[int]:
        """Parse un entier."""
        if not s:
            return None
        try:
            cleaned = s.replace(' ', '').replace(',', '.')
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None

    def extract_provenance(self, text: str) -> Optional[str]:
        """Extrait le pays d'origine."""
        match = self.RE_PAYS.search(text)
        if match:
            pays = match.group(1).upper()
            # Normaliser
            if 'HOLLANDE' in pays:
                return 'PAYS-BAS'
            return pays
        return None

    def parse_line_article(self, line: str) -> Optional[LigneTaiyat]:
        """Parse une ligne article."""
        line = line.strip()
        if not line or not line[0].isdigit():
            return None

        # Ignorer les lignes de totaux
        if any(x in line.upper() for x in ['BASE', 'TOTAL', 'COLIS', 'NET A', 'TAXES', 'TVA']):
            return None

        # Ignorer les headers de BL
        if 'BL n' in line or 'Du ' in line:
            return None

        # Essayer le pattern principal
        match = self.RE_LIGNE.match(line)
        confidence = 0.9

        if not match:
            # Essayer pattern alternatif
            match = self.RE_LIGNE_ALT.match(line)
            confidence = 0.7

        if not match:
            return None

        try:
            colis = self.parse_number(match.group(1))
            designation = match.group(2).strip()
            prix_ht = self.parse_number(match.group(3))
            pieces = self.parse_integer(match.group(4))
            unite = match.group(5)
            prix_ttc_raw = match.group(6)
            montant_ttc = self.parse_number(match.group(7))
            code_tva = match.group(8)

            # Detecter les remises
            est_remise = '-' in prix_ttc_raw and '%' in prix_ttc_raw
            prix_ttc = self.parse_number(prix_ttc_raw)

            # Extraire provenance de la designation
            provenance = self.extract_provenance(designation)

            # Nettoyer designation (enlever provenance si presente)
            if provenance:
                designation = re.sub(
                    r'\s*\d*\s*' + re.escape(provenance) + r'\s*',
                    ' ',
                    designation,
                    flags=re.IGNORECASE
                ).strip()

            ligne = LigneTaiyat(
                batch_id=self.batch_id,
                source_file="",
                designation=designation,
                provenance=provenance,
                colis=int(colis) if colis else None,
                pieces=pieces,
                unite=unite,
                prix_unitaire_ht=prix_ht,
                prix_unitaire_ttc=prix_ttc,
                montant_ttc=montant_ttc,
                code_tva=code_tva,
                taux_tva=TVA_CODES.get(code_tva, 5.5),
                est_remise=est_remise,
                raw_line=line,
                parse_confidence=confidence
            )

            # Validation stricte: montant ET prix requis
            if ligne.montant_ttc is not None and ligne.prix_unitaire_ht is not None:
                return ligne
            else:
                self._current_facture_rejections += 1
                if self.debug:
                    logger.warning(f"REJECTED (missing data): {designation[:50]}")
                return None

        except Exception as e:
            if self.debug:
                logger.warning(f"Parse error: {e} - Line: {line[:50]}")
            return None

    def extract_header(self, facture: FactureTaiyat, text: str):
        """Extrait les infos d'en-tete."""

        # Numero facture
        m = self.RE_FACTURE.search(text)
        if m:
            facture.numero_facture = m.group(1)

        # Date
        m = self.RE_DATE.search(text)
        if m:
            date_str = m.group(1)
            try:
                dt = datetime.strptime(date_str, '%d/%m/%Y')
                facture.date_facture = dt.strftime('%Y-%m-%d')
            except:
                facture.date_facture = date_str

        # Code client
        m = self.RE_CODE_CLIENT.search(text)
        if m:
            facture.client_code = m.group(1)

        # Client depuis nom fichier
        filename = facture.source_file.upper()
        if 'NOUTAM' in filename:
            facture.client_nom = 'NOUTAM'
        elif 'INCONTOURNABLE' in filename:
            facture.client_nom = 'INCONTOURNABLE'

        # Echeance
        m = self.RE_ECHEANCE.search(text)
        if m:
            facture.echeance = m.group(1)

    def extract_totals(self, facture: FactureTaiyat, text: str):
        """Extrait les totaux."""
        lines = text.split('\n')

        for line in lines:
            line_upper = line.upper()

            # NET A PAYER TTC
            if 'PAYER' in line_upper or 'NET A' in line_upper:
                m = self.RE_TOTAL_TTC.search(line)
                if m:
                    facture.total_ttc = self.parse_number(m.group(1))

            # Total HT
            if 'HT' in line_upper and 'BASE' not in line_upper:
                numbers = re.findall(r'(\d[\d\s]*[,.]?\d*)', line)
                if numbers:
                    for num in numbers:
                        val = self.parse_number(num)
                        if val and val > 10:
                            facture.total_ht = val
                            break

    def extract_lines(self, facture: FactureTaiyat, text: str):
        """Extrait les lignes articles."""
        lines = text.split('\n')
        ligne_num = 0
        self._current_facture_rejections = 0

        for line in lines:
            ligne = self.parse_line_article(line)
            if ligne:
                ligne_num += 1
                ligne.ligne_numero = ligne_num
                ligne.source_file = facture.source_file
                ligne.numero_facture = facture.numero_facture
                ligne.date_facture = facture.date_facture
                ligne.client_nom = facture.client_nom
                ligne.client_code = facture.client_code

                facture.lignes.append(ligne)
                facture.lignes_parsees += 1

                if ligne.est_remise:
                    self.stats.lignes_remises += 1

        facture.lignes_rejetees = self._current_facture_rejections

    def validate_and_calculate_quality(self, facture: FactureTaiyat):
        """Calcule le score de qualite."""
        score = 0.0
        checks = 0

        if facture.numero_facture:
            score += 1
            checks += 1
        if facture.date_facture:
            score += 1
            checks += 1
        if facture.client_nom:
            score += 1
            checks += 1
        if facture.total_ttc:
            score += 1
            checks += 1
        if facture.lignes:
            score += 2
            checks += 2

            # Coherence montants
            total_calc = sum(l.montant_ttc or 0 for l in facture.lignes)
            if facture.total_ttc and total_calc > 0:
                ecart = abs(facture.total_ttc - total_calc) / facture.total_ttc
                if ecart < 0.05:
                    score += 2
                elif ecart < 0.15:
                    score += 1
                checks += 2
        else:
            checks += 4

        facture.extraction_quality = (score / checks * 100) if checks > 0 else 0

    def extract_file(self, pdf_path: Path) -> Optional[FactureTaiyat]:
        """Extrait une facture PDF."""
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber non installe")
            return None

        self.stats.fichiers_traites += 1

        try:
            with pdfplumber.open(pdf_path) as pdf:
                facture = FactureTaiyat(
                    batch_id=self.batch_id,
                    source_file=pdf_path.name
                )

                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    all_text += text + "\n"

                if not all_text.strip():
                    logger.warning(f"PDF vide: {pdf_path.name}")
                    self.stats.fichiers_echec += 1
                    return None

                self.extract_header(facture, all_text)
                self.extract_lines(facture, all_text)
                self.extract_totals(facture, all_text)
                self.validate_and_calculate_quality(facture)

                # Stats
                self.stats.fichiers_succes += 1
                self.stats.lignes_total += len(facture.lignes)
                self.stats.lignes_produits += len(facture.lignes)
                self.stats.lignes_rejetees += facture.lignes_rejetees

                if not facture.lignes:
                    self.stats.factures_sans_lignes += 1
                    logger.warning(
                        f"Facture sans lignes: {pdf_path.name} "
                        f"(numero={facture.numero_facture}, rejetees={facture.lignes_rejetees})"
                    )

                if self.debug:
                    logger.info(
                        f"Extrait {pdf_path.name}: {len(facture.lignes)} lignes, "
                        f"rejetees={facture.lignes_rejetees}, qualite={facture.extraction_quality:.0f}%"
                    )

                return facture

        except Exception as e:
            logger.error(f"Erreur extraction {pdf_path.name}: {e}")
            self.stats.fichiers_echec += 1
            self.stats.erreurs.append(f"{pdf_path.name}: {str(e)}")
            return None

    def extract_directory(self, directory: Path) -> List[FactureTaiyat]:
        """Extrait toutes les factures d'un repertoire."""
        factures = []
        pdf_files = sorted(directory.rglob('*.pdf'))

        logger.info(f"Extraction de {len(pdf_files)} PDFs depuis {directory}")

        for i, pdf in enumerate(pdf_files, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(pdf_files)}")

            facture = self.extract_file(pdf)
            if facture and facture.numero_facture:
                factures.append(facture)

        # Rapport
        logger.info("=" * 60)
        logger.info("RAPPORT D'EXTRACTION TAIYAT")
        logger.info("=" * 60)
        logger.info(f"Fichiers traites:     {self.stats.fichiers_traites}")
        logger.info(f"Fichiers succes:      {self.stats.fichiers_succes}")
        logger.info(f"Fichiers echec:       {self.stats.fichiers_echec}")
        logger.info(f"Factures valides:     {len(factures)}")
        logger.info(f"Factures sans lignes: {self.stats.factures_sans_lignes}")
        logger.info("-" * 60)
        logger.info(f"Lignes total:         {self.stats.lignes_total}")
        logger.info(f"Lignes produits:      {self.stats.lignes_produits}")
        logger.info(f"Lignes remises:       {self.stats.lignes_remises}")
        logger.info(f"Lignes REJETEES:      {self.stats.lignes_rejetees}")

        if self.stats.lignes_total > 0:
            success_rate = self.stats.lignes_produits / (self.stats.lignes_total + self.stats.lignes_rejetees) * 100
            logger.info(f"Taux de succes:       {success_rate:.1f}%")

        return factures


# =============================================================================
# CLI
# =============================================================================

def test_extraction(pdf_path: str, debug: bool = False):
    """Test d'extraction sur un fichier."""
    parser = TaiyatParser(debug=debug)
    facture = parser.extract_file(Path(pdf_path))

    if not facture:
        print("ECHEC extraction")
        return None

    print("=" * 80)
    print("EXTRACTION TAIYAT REUSSIE")
    print("=" * 80)
    print(f"Fichier:    {facture.source_file}")
    print(f"Facture:    N°{facture.numero_facture}")
    print(f"Date:       {facture.date_facture}")
    print(f"Client:     {facture.client_nom} (code: {facture.client_code})")
    print(f"Total TTC:  {facture.total_ttc} EUR")
    print(f"Nb lignes:  {len(facture.lignes)} (rejetees: {facture.lignes_rejetees})")
    print(f"Qualite:    {facture.extraction_quality:.0f}%")

    print("\n" + "=" * 80)
    print("LIGNES EXTRAITES")
    print("=" * 80)

    total_calc = 0
    for l in facture.lignes:
        remise = " [REMISE]" if l.est_remise else ""
        print(f"\n{l.ligne_numero:3d}. {l.designation or 'N/A'}")
        print(f"     Provenance: {l.provenance or 'N/A'}")
        print(f"     Colis: {l.colis} | Pieces: {l.pieces} | Prix HT: {l.prix_unitaire_ht}")
        print(f"     Montant TTC: {l.montant_ttc} | TVA: {l.taux_tva}%{remise}")

        if l.montant_ttc:
            total_calc += l.montant_ttc

    print("\n" + "=" * 80)
    ecart = abs(total_calc - (facture.total_ttc or 0))
    print(f"TOTAL CALCULE: {total_calc:.2f} EUR")
    print(f"TOTAL FACTURE: {facture.total_ttc} EUR")
    print(f"ECART:         {ecart:.2f} EUR")
    print("=" * 80)

    return facture


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description='ETL TAIYAT - Extraction PDF')
    arg_parser.add_argument('pdf', nargs='?', help='Chemin vers le fichier PDF')
    arg_parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    arg_parser.add_argument('--dir', help='Repertoire de PDFs')

    args = arg_parser.parse_args()

    if args.dir:
        parser = TaiyatParser(debug=args.debug)
        factures = parser.extract_directory(Path(args.dir))
        print(f"\n{len(factures)} factures extraites")
    elif args.pdf:
        test_extraction(args.pdf, debug=args.debug)
    else:
        print("Usage: python extract_taiyat_pdf.py [--debug] <fichier.pdf>")
        print("       python extract_taiyat_pdf.py --dir <repertoire>")
