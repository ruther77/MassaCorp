#!/usr/bin/env python3
"""
ETL METRO - Extraction des factures PDF (Version 3 - Senior Engineer Refactor)
================================================================================
Parser robuste pour les factures METRO avec gestion avancee des erreurs,
multiples patterns de fallback, et reporting detaille.

Format ligne article METRO (plusieurs variantes):
- Alcool:     EAN ARTICLE DESIGNATION REGIE VOL% VAP VOLUME PRIX COLISAGE QTE MONTANT TVA [P]
- Vin:        EAN ARTICLE DESIGNATION T VOLUME PRIX COLISAGE QTE MONTANT TVA [P]
- Standard:   EAN ARTICLE DESIGNATION PRIX COLISAGE QTE MONTANT TVA [P]
- Simplifie:  EAN ARTICLE DESIGNATION QTE MONTANT TVA

Changelog:
- v3.0 (2026-01-07): Refactoring complet - patterns multiples, fallbacks, logging
- v2.1 (2026-01-06): Integration module normalisation (N1-N8)
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
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class LineType(Enum):
    """Types de lignes detectees dans les factures."""
    PRODUCT_ALCOHOL = "alcohol"
    PRODUCT_WINE = "wine"
    PRODUCT_STANDARD = "standard"
    PRODUCT_SIMPLE = "simple"
    PRODUCT_FALLBACK = "fallback"
    FEE_TRANSPORT = "fee_transport"
    FEE_TAX = "fee_tax"
    FEE_OTHER = "fee_other"
    UNKNOWN = "unknown"


# Lignes a exclure completement (bruit)
EXCLUDE_PATTERNS = [
    r'RUM\s*:',
    r'CARTE\s+METRO',
    r'CMR\s+paiement',
    r'FIN\s+DE\s+LA\s+FACTURE',
    r'ENTREPOT',
    r'PAGE\s+\d+',
    r'^\s*\*+\s*$',
    r'Sous-total',
    r'N[°o]\s*Client',
]

# Lignes de frais/taxes (a conserver mais marquer)
FEE_PATTERNS = {
    'transport': [r'Frais\s+Transport', r'FRAIS\s+LIVRAISON', r'Port\s+forfait'],
    'tax': [r'ICS\s*:', r'COTIS.*SECURITE', r'Cotisation', r'Eco-participation'],
    'other': [r'Consigne', r'Emballage', r'Location'],
}

# Mapping TVA
TVA_CODES = {'A': 0.0, 'B': 5.5, 'C': 10.0, 'D': 20.0}

# Mapping Regie -> Categorie
REGIE_CATEGORIES = {
    'S': 'SPIRITUEUX',
    'T': 'VINS',
    'B': 'BRASSERIE',
    'M': 'CHAMPAGNE',
    'A': 'APERITIFS',
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LigneFacture:
    """Ligne de facture extraite avec metadata."""
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
    unite: str = "U"
    prix_unitaire: Optional[float] = None
    colisage: Optional[int] = None
    quantite: Optional[int] = None
    montant_ligne: Optional[float] = None
    code_tva: Optional[str] = None
    taux_tva: Optional[float] = None
    est_promo: bool = False
    est_frais: bool = False
    type_frais: Optional[str] = None
    line_type: str = "unknown"
    raw_line: Optional[str] = None
    parse_confidence: float = 0.0


@dataclass
class FactureEntete:
    """En-tete de facture avec statistiques d'extraction."""
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
    # Stats d'extraction
    lignes_parsees: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0  # Lignes parsées mais rejetées (sans prix/montant)
    lignes_frais: int = 0
    extraction_quality: float = 0.0


@dataclass
class ExtractionStats:
    """Statistiques globales d'extraction."""
    fichiers_traites: int = 0
    fichiers_succes: int = 0
    fichiers_echec: int = 0
    lignes_total: int = 0
    lignes_produits: int = 0
    lignes_frais: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0  # Lignes parsées mais sans prix/montant
    factures_sans_lignes: int = 0
    erreurs: List[str] = field(default_factory=list)


# =============================================================================
# PARSER ENGINE
# =============================================================================

class MetroParserV3:
    """
    Parser robuste pour les factures METRO.

    Caracteristiques:
    - Multiples patterns regex avec fallback intelligent
    - Detection et categorisation des frais/taxes
    - Logging detaille pour debug
    - Statistiques de qualite d'extraction
    - Validation des donnees extraites
    """

    def __init__(self, batch_id: str = None, debug: bool = False):
        self.batch_id = batch_id or str(uuid.uuid4())
        self.debug = debug
        self.stats = ExtractionStats()
        self._current_facture_rejections = 0  # Compteur temporaire par facture
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile tous les patterns regex pour performance."""

        # Pattern EAN - plus flexible
        # Accepte: 13 chiffres, 8 chiffres, avec ou sans 0 initial
        self.RE_EAN = re.compile(r'^0?(\d{13}|\d{12}|\d{8})\s')

        # Pattern numero article METRO (7 chiffres)
        self.RE_ARTICLE = re.compile(r'\s(\d{7})\s')

        # Patterns pour les differents formats de ligne
        # Format 1: Alcool complet avec regie
        # EAN ART DESIGNATION REGIE VOL VAP VOLUME PRIX COLIS QTE MONTANT TVA
        self.RE_ALCOHOL = re.compile(
            r'\s([STBMA])\s+'           # Regie
            r'(\d+[,.]?\d*)\s+'         # Vol alcool
            r'(\d+[,.]?\d*)\s+'         # VAP
            r'[a-z]?\s*'                # Lettre optionnelle
            r'(\d+[,.]?\d*)\s+'         # Volume
            r'(\d+[,.]?\d*)\s+'         # Prix unitaire
            r'(\d+)\s+'                 # Colisage
            r'(\d+)\s+'                 # Quantite
            r'(\d[\d\s]*[,.]?\d*)\s+'   # Montant (peut avoir espace)
            r'([ABCD])'                 # Code TVA
            r'(?:\s*P)?'                # Promo optionnel
        )

        # Format 2: Vin (sans degre alcool)
        # EAN ART DESIGNATION T VOLUME PRIX COLIS QTE MONTANT TVA
        self.RE_WINE = re.compile(
            r'\s(T)\s+'                 # Regie T (vins)
            r'(\d+[,.]?\d*)\s+'         # Volume
            r'(\d+[,.]?\d*)\s+'         # Prix unitaire
            r'(\d+)\s+'                 # Colisage
            r'(\d+)\s+'                 # Quantite
            r'(\d[\d\s]*[,.]?\d*)\s+'   # Montant
            r'([ABCD])'                 # Code TVA
        )

        # Format 3: Produit standard (fin de ligne)
        # ... PRIX COLIS QTE MONTANT TVA [P]
        self.RE_STANDARD = re.compile(
            r'(\d+[,.]?\d+)\s+'         # Prix unitaire (avec decimales)
            r'(\d+)\s+'                 # Colisage
            r'(\d+)\s+'                 # Quantite
            r'(\d[\d\s]*[,.]?\d*)\s+'   # Montant
            r'([ABCD])'                 # Code TVA
            r'(?:\s*P)?\s*$'            # Promo + fin de ligne
        )

        # Format 4: Simplifie (sans prix unitaire)
        # ... QTE MONTANT TVA
        self.RE_SIMPLE = re.compile(
            r'(\d+)\s+'                 # Quantite
            r'(\d[\d\s]*[,.]?\d*)\s+'   # Montant
            r'([ABCD])\s*$'             # Code TVA + fin
        )

        # Format 5: Ultra-simplifie (juste montant et TVA)
        self.RE_MINIMAL = re.compile(
            r'(\d[\d\s]*[,.]?\d*)\s+'   # Montant
            r'([ABCD])\s*$'             # Code TVA
        )

        # Patterns en-tete
        self.RE_NUMERO_FACTURE = re.compile(r'(\d/\d\(\d+\)\d+/\d+)')
        self.RE_NUMERO_INTERNE = re.compile(r'\((\d{3}-\d{6})\)')
        self.RE_DATE = re.compile(r'Date\s*facture\s*\*?\s*:?\s*(\d{2})[-/](\d{2})[-/](\d{4})')
        self.RE_DATE_ALT = re.compile(r'(\d{2})[-/](\d{2})[-/](\d{4})')
        self.RE_MAGASIN = re.compile(r'METRO\s+([A-Z][A-Z\s]+?)(?:\s*\*|\s+PAGE|\s+Date)', re.IGNORECASE)
        self.RE_CLIENT_NUMERO = re.compile(r'N[°o]\s*Client\s*:?\s*(\d{3}\s*\d{8})')

        # Patterns totaux
        self.RE_TOTAL_HT = re.compile(r'Total\s*H\.?T\.?\s*:?\s*(\d[\d\s]*[,.]?\d*)', re.IGNORECASE)
        self.RE_TOTAL_TTC = re.compile(r'Total\s*[àa]\s*payer\s*:?\s*(\d[\d\s]*[,.]?\d*)', re.IGNORECASE)
        self.RE_TOTAL_TVA = re.compile(r'Total\s*TVA\s*:?\s*(\d[\d\s]*[,.]?\d*)', re.IGNORECASE)

        # Pattern sections
        self.RE_SECTION = re.compile(
            r'\*{2,3}\s*(SPIRITUEUX|CAVE|BRASSERIE|CHAMPAGNE|EPICERIE|SURGELES|DROGUERIE|FOURNITURES)',
            re.IGNORECASE
        )

        # Compile exclusion patterns
        self.RE_EXCLUDE = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

        # Compile fee patterns
        self.FEE_PATTERNS_COMPILED = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in FEE_PATTERNS.items()
        }

    def parse_number(self, s: str) -> Optional[float]:
        """Parse un nombre avec gestion robuste des formats."""
        if not s:
            return None
        try:
            # Nettoyer: espaces, virgule -> point
            cleaned = s.replace(' ', '').replace(',', '.')
            # Gerer les doubles points (erreur OCR)
            cleaned = re.sub(r'\.+', '.', cleaned)
            value = float(cleaned)
            # Validation: montants raisonnables
            if value < 0 or value > 100000:
                return None
            return value
        except (ValueError, TypeError):
            return None

    def parse_integer(self, s: str) -> Optional[int]:
        """Parse un entier avec validation."""
        if not s:
            return None
        try:
            cleaned = s.replace(' ', '')
            value = int(cleaned)
            if value < 0 or value > 10000:
                return None
            return value
        except (ValueError, TypeError):
            return None

    def detect_fee_type(self, line: str) -> Optional[str]:
        """Detecte si une ligne est un frais/taxe."""
        for fee_type, patterns in self.FEE_PATTERNS_COMPILED.items():
            for pattern in patterns:
                if pattern.search(line):
                    return fee_type
        return None

    def should_exclude(self, line: str) -> bool:
        """Verifie si une ligne doit etre exclue."""
        return bool(self.RE_EXCLUDE.search(line))

    def extract_ean(self, line: str) -> Tuple[Optional[str], int]:
        """
        Extrait l'EAN et retourne sa position de fin.

        Returns:
            Tuple (ean, end_position) ou (None, 0)
        """
        match = self.RE_EAN.match(line.strip())
        if match:
            ean = match.group(1)
            # Normaliser EAN-13 (ajouter 0 si 12 chiffres)
            if len(ean) == 12:
                ean = '0' + ean
            return ean, match.end()
        return None, 0

    def extract_article_number(self, line: str, start_pos: int) -> Tuple[Optional[str], int]:
        """Extrait le numero article METRO."""
        match = self.RE_ARTICLE.search(line[start_pos:])
        if match:
            return match.group(1), start_pos + match.end()
        return None, start_pos

    def parse_line_alcohol(self, line: str, ean: str, art_num: Optional[str],
                           designation_start: int) -> Optional[LigneFacture]:
        """Parse une ligne de produit alcool."""
        match = self.RE_ALCOHOL.search(line)
        if not match:
            return None

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            article_numero=art_num,
            regie=match.group(1),
            vol_alcool=self.parse_number(match.group(2)),
            vap=self.parse_number(match.group(3)),
            poids_volume=self.parse_number(match.group(4)),
            prix_unitaire=self.parse_number(match.group(5)),
            colisage=self.parse_integer(match.group(6)),
            quantite=self.parse_integer(match.group(7)),
            montant_ligne=self.parse_number(match.group(8)),
            code_tva=match.group(9),
            taux_tva=TVA_CODES.get(match.group(9), 20.0),
            line_type=LineType.PRODUCT_ALCOHOL.value,
            parse_confidence=0.95,
            raw_line=line
        )

        # Extraction designation
        end_pos = match.start()
        ligne.designation = line[designation_start:end_pos].strip()

        # Detection promo
        if 'P' in line[match.end():] or 'PROMO' in line.upper():
            ligne.est_promo = True

        return ligne

    def parse_line_wine(self, line: str, ean: str, art_num: Optional[str],
                        designation_start: int) -> Optional[LigneFacture]:
        """Parse une ligne de produit vin."""
        match = self.RE_WINE.search(line)
        if not match:
            return None

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            article_numero=art_num,
            regie='T',
            poids_volume=self.parse_number(match.group(2)),
            prix_unitaire=self.parse_number(match.group(3)),
            colisage=self.parse_integer(match.group(4)),
            quantite=self.parse_integer(match.group(5)),
            montant_ligne=self.parse_number(match.group(6)),
            code_tva=match.group(7),
            taux_tva=TVA_CODES.get(match.group(7), 20.0),
            line_type=LineType.PRODUCT_WINE.value,
            parse_confidence=0.90,
            raw_line=line
        )

        ligne.designation = line[designation_start:match.start()].strip()
        return ligne

    def parse_line_standard(self, line: str, ean: str, art_num: Optional[str],
                            designation_start: int) -> Optional[LigneFacture]:
        """Parse une ligne de produit standard."""
        match = self.RE_STANDARD.search(line)
        if not match:
            return None

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            article_numero=art_num,
            prix_unitaire=self.parse_number(match.group(1)),
            colisage=self.parse_integer(match.group(2)),
            quantite=self.parse_integer(match.group(3)),
            montant_ligne=self.parse_number(match.group(4)),
            code_tva=match.group(5),
            taux_tva=TVA_CODES.get(match.group(5), 20.0),
            line_type=LineType.PRODUCT_STANDARD.value,
            parse_confidence=0.85,
            raw_line=line
        )

        ligne.designation = line[designation_start:match.start()].strip()

        # Detecter si c'est un promo
        if line.rstrip().endswith('P'):
            ligne.est_promo = True

        return ligne

    def parse_line_simple(self, line: str, ean: str, art_num: Optional[str],
                          designation_start: int) -> Optional[LigneFacture]:
        """Parse une ligne simplifiee (sans prix unitaire)."""
        match = self.RE_SIMPLE.search(line)
        if not match:
            return None

        quantite = self.parse_integer(match.group(1))
        montant = self.parse_number(match.group(2))

        # Calculer prix unitaire si possible
        prix_unitaire = None
        if quantite and montant and quantite > 0:
            prix_unitaire = round(montant / quantite, 4)

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            article_numero=art_num,
            prix_unitaire=prix_unitaire,
            colisage=1,
            quantite=quantite,
            montant_ligne=montant,
            code_tva=match.group(3),
            taux_tva=TVA_CODES.get(match.group(3), 20.0),
            line_type=LineType.PRODUCT_SIMPLE.value,
            parse_confidence=0.70,
            raw_line=line
        )

        ligne.designation = line[designation_start:match.start()].strip()
        return ligne

    def parse_line_fallback(self, line: str, ean: str, art_num: Optional[str],
                            designation_start: int) -> Optional[LigneFacture]:
        """Fallback: extraction minimale."""
        match = self.RE_MINIMAL.search(line)
        if not match:
            return None

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            article_numero=art_num,
            montant_ligne=self.parse_number(match.group(1)),
            code_tva=match.group(2),
            taux_tva=TVA_CODES.get(match.group(2), 20.0),
            line_type=LineType.PRODUCT_FALLBACK.value,
            parse_confidence=0.50,
            raw_line=line
        )

        ligne.designation = line[designation_start:match.start()].strip()
        return ligne

    def parse_fee_line(self, line: str, ean: str, fee_type: str) -> Optional[LigneFacture]:
        """Parse une ligne de frais/taxe."""
        # Chercher un montant et code TVA
        match = self.RE_MINIMAL.search(line)
        if not match:
            # Essayer de trouver juste un montant
            montant_match = re.search(r'(\d+[,.]?\d*)\s*$', line)
            if montant_match:
                montant = self.parse_number(montant_match.group(1))
            else:
                montant = None
            code_tva = 'D'  # Par defaut 20%
        else:
            montant = self.parse_number(match.group(1))
            code_tva = match.group(2)

        ligne = LigneFacture(
            batch_id=self.batch_id,
            source_file="",
            ean=ean,
            montant_ligne=montant,
            code_tva=code_tva,
            taux_tva=TVA_CODES.get(code_tva, 20.0),
            est_frais=True,
            type_frais=fee_type,
            line_type=f"fee_{fee_type}",
            parse_confidence=0.60,
            raw_line=line
        )

        # Designation = toute la ligne nettoyee
        ligne.designation = re.sub(r'\s+', ' ', line).strip()

        return ligne

    def parse_line_article(self, line: str, current_categorie: Optional[str]) -> Optional[LigneFacture]:
        """
        Parse une ligne article avec strategie de fallback.

        Ordre de tentative:
        1. Format alcool complet
        2. Format vin
        3. Format standard
        4. Format simple
        5. Fallback minimal
        """
        line = line.strip()

        # Exclure lignes de bruit
        if self.should_exclude(line):
            return None

        # Detecter frais/taxes
        fee_type = self.detect_fee_type(line)

        # Extraire EAN
        ean, ean_end = self.extract_ean(line)
        if not ean:
            return None

        # Si c'est un frais, traiter separement
        if fee_type:
            ligne = self.parse_fee_line(line, ean, fee_type)
            if ligne:
                ligne.categorie_source = current_categorie
            return ligne

        # Extraire numero article
        art_num, designation_start = self.extract_article_number(line, ean_end)
        if not art_num:
            designation_start = ean_end

        # Strategie de fallback ordonnee
        parsers = [
            self.parse_line_alcohol,
            self.parse_line_wine,
            self.parse_line_standard,
            self.parse_line_simple,
            self.parse_line_fallback,
        ]

        for parser in parsers:
            ligne = parser(line, ean, art_num, designation_start)
            if ligne:
                ligne.categorie_source = current_categorie

                # VALIDATION STRICTE: ligne DOIT avoir montant ET prix
                # Exception: les lignes de frais (transport, taxes) n'ont pas de prix unitaire
                if ligne.est_frais:
                    # Frais: seulement montant requis
                    if ligne.montant_ligne is not None:
                        if self.debug:
                            logger.debug(f"Parsed [FRAIS-{ligne.type_frais}]: {ligne.designation[:40] if ligne.designation else 'N/A'}")
                        return ligne
                else:
                    # Produit: montant ET prix obligatoires
                    if ligne.montant_ligne is not None and ligne.prix_unitaire is not None:
                        if self.debug:
                            logger.debug(f"Parsed [{ligne.line_type}]: {ligne.designation[:40] if ligne.designation else 'N/A'}")
                        return ligne
                    else:
                        # Ligne rejetee - pas de prix ou montant
                        self._current_facture_rejections += 1
                        missing = []
                        if ligne.montant_ligne is None:
                            missing.append("montant")
                        if ligne.prix_unitaire is None:
                            missing.append("prix")
                        if self.debug:
                            logger.warning(f"REJECTED (missing {', '.join(missing)}): {ligne.designation[:50] if ligne.designation else line[:50]}")

        # Echec total - logger pour analyse
        if self.debug:
            logger.warning(f"Failed to parse: {line[:80]}")

        return None

    def extract_header(self, facture: FactureEntete, text: str):
        """Extrait les informations d'en-tete de facture."""

        # Numero facture
        m = self.RE_NUMERO_FACTURE.search(text)
        if m:
            facture.numero_facture = m.group(1)

        # Numero interne
        m = self.RE_NUMERO_INTERNE.search(text)
        if m:
            facture.numero_interne = m.group(1)

        # Date - essayer format principal puis alternatif
        m = self.RE_DATE.search(text)
        if m:
            facture.date_facture = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        elif not facture.date_facture:
            # Chercher dans les premieres lignes
            for line in text.split('\n')[:20]:
                m = self.RE_DATE_ALT.search(line)
                if m:
                    facture.date_facture = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
                    break

        # Magasin
        m = self.RE_MAGASIN.search(text)
        if m:
            magasin = m.group(1).strip()
            # Nettoyer les caracteres parasites
            magasin = re.sub(r'\s+', ' ', magasin)
            facture.magasin_nom = f"METRO {magasin}"

        # Client - detection robuste
        text_upper = text.upper()
        if 'NOUTAM' in text_upper:
            facture.client_nom = 'NOUTAM'
        elif 'INCONTOURNABLE' in text_upper or 'SAS INCON' in text_upper:
            facture.client_nom = 'INCONTOURNABLE'

        # Numero client
        m = self.RE_CLIENT_NUMERO.search(text)
        if m:
            facture.client_numero = m.group(1).replace(' ', '')

    def extract_totals(self, facture: FactureEntete, text: str):
        """Extrait les totaux de la facture."""

        # Total HT
        m = self.RE_TOTAL_HT.search(text)
        if m:
            facture.total_ht = self.parse_number(m.group(1))

        # Total TTC
        m = self.RE_TOTAL_TTC.search(text)
        if m:
            facture.total_ttc = self.parse_number(m.group(1))

        # Total TVA
        m = self.RE_TOTAL_TVA.search(text)
        if m:
            facture.total_tva = self.parse_number(m.group(1))

        # Calculer TVA si manquante
        if not facture.total_tva and facture.total_ht and facture.total_ttc:
            facture.total_tva = round(facture.total_ttc - facture.total_ht, 2)

    def extract_lines(self, facture: FactureEntete, text: str):
        """Extrait toutes les lignes articles."""
        lines = text.split('\n')
        current_categorie = None
        ligne_num = 0

        # Reset compteur de rejets pour cette facture
        self._current_facture_rejections = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detecter section/categorie
            section_match = self.RE_SECTION.search(line)
            if section_match:
                current_categorie = section_match.group(1).upper()
                continue

            # Detecter headers de categorie simples
            for cat in ['SPIRITUEUX', 'CAVE', 'BRASSERIE', 'CHAMPAGNE', 'EPICERIE', 'SURGELES', 'DROGUERIE']:
                if line.upper().startswith(cat) and 'Total' not in line:
                    current_categorie = cat
                    break

            # Parser ligne article si commence par chiffre (potentiel EAN)
            if line and line[0].isdigit():
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

                    # Assigner categorie depuis regie si disponible
                    if ligne.regie and not ligne.categorie_source:
                        ligne.categorie_source = REGIE_CATEGORIES.get(ligne.regie)

                    facture.lignes.append(ligne)
                    facture.lignes_parsees += 1

                    if ligne.est_frais:
                        facture.lignes_frais += 1
                else:
                    facture.lignes_echec += 1

        # Reporter les lignes rejetees (parsees mais sans prix/montant)
        facture.lignes_rejetees = self._current_facture_rejections

    def validate_and_calculate_quality(self, facture: FactureEntete):
        """Valide les donnees et calcule le score de qualite."""

        # Calculer montant total depuis lignes
        total_lignes = sum(
            l.montant_ligne or 0
            for l in facture.lignes
            if not l.est_frais
        )

        # Score de qualite base sur:
        # - Presence de toutes les infos header
        # - Coherence total HT vs somme lignes
        # - Ratio lignes parsees / echec

        score = 0.0
        checks = 0

        # Header complet
        if facture.numero_facture:
            score += 1
            checks += 1
        if facture.date_facture:
            score += 1
            checks += 1
        if facture.magasin_nom:
            score += 1
            checks += 1
        if facture.client_nom:
            score += 1
            checks += 1
        if facture.total_ht:
            score += 1
            checks += 1

        # Lignes extraites
        if facture.lignes:
            score += 2
            checks += 2

            # Coherence montants (tolerance 5%)
            if facture.total_ht and total_lignes > 0:
                ecart = abs(facture.total_ht - total_lignes) / facture.total_ht
                if ecart < 0.05:
                    score += 2
                elif ecart < 0.15:
                    score += 1
                checks += 2
        else:
            checks += 4  # Penalite pas de lignes

        facture.extraction_quality = (score / checks * 100) if checks > 0 else 0

    def extract_file(self, pdf_path: Path) -> Optional[FactureEntete]:
        """
        Extrait une facture PDF METRO.

        Args:
            pdf_path: Chemin vers le fichier PDF

        Returns:
            FactureEntete extraite ou None si echec
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber non installe")
            return None

        self.stats.fichiers_traites += 1

        try:
            with pdfplumber.open(pdf_path) as pdf:
                facture = FactureEntete(
                    batch_id=self.batch_id,
                    source_file=pdf_path.name
                )

                # Extraire texte de toutes les pages
                all_text = ""
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    all_text += text + "\n"

                if not all_text.strip():
                    logger.warning(f"PDF vide ou illisible: {pdf_path.name}")
                    self.stats.fichiers_echec += 1
                    return None

                # Extraction
                self.extract_header(facture, all_text)
                self.extract_lines(facture, all_text)
                self.extract_totals(facture, all_text)

                # Validation et qualite
                self.validate_and_calculate_quality(facture)

                # Stats
                self.stats.fichiers_succes += 1
                self.stats.lignes_total += len(facture.lignes)
                self.stats.lignes_produits += sum(1 for l in facture.lignes if not l.est_frais)
                self.stats.lignes_frais += facture.lignes_frais
                self.stats.lignes_echec += facture.lignes_echec
                self.stats.lignes_rejetees += facture.lignes_rejetees

                if not facture.lignes:
                    self.stats.factures_sans_lignes += 1
                    logger.warning(
                        f"Facture sans lignes: {pdf_path.name} "
                        f"(numero={facture.numero_facture}, total_ht={facture.total_ht}, "
                        f"rejetees={facture.lignes_rejetees})"
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

    def extract_directory(self, directory: Path, normalize: bool = True) -> List[FactureEntete]:
        """
        Extrait toutes les factures d'un repertoire.

        Args:
            directory: Chemin du repertoire
            normalize: Appliquer la normalisation (non impl. v3)

        Returns:
            Liste des factures extraites
        """
        factures = []
        pdf_files = sorted(directory.rglob('*.pdf'))

        logger.info(f"Extraction de {len(pdf_files)} PDFs depuis {directory}")

        for i, pdf in enumerate(pdf_files, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(pdf_files)}")

            facture = self.extract_file(pdf)
            if facture and facture.numero_facture:
                factures.append(facture)

        # Rapport final
        logger.info("=" * 60)
        logger.info("RAPPORT D'EXTRACTION")
        logger.info("=" * 60)
        logger.info(f"Fichiers traites:     {self.stats.fichiers_traites}")
        logger.info(f"Fichiers succes:      {self.stats.fichiers_succes}")
        logger.info(f"Fichiers echec:       {self.stats.fichiers_echec}")
        logger.info(f"Factures valides:     {len(factures)}")
        logger.info(f"Factures sans lignes: {self.stats.factures_sans_lignes}")
        logger.info("-" * 60)
        logger.info(f"Lignes total:         {self.stats.lignes_total}")
        logger.info(f"Lignes produits:      {self.stats.lignes_produits}")
        logger.info(f"Lignes frais:         {self.stats.lignes_frais}")
        logger.info(f"Lignes echec parse:   {self.stats.lignes_echec}")
        logger.info(f"Lignes REJETEES:      {self.stats.lignes_rejetees} (sans prix/montant)")

        if self.stats.lignes_total > 0:
            success_rate = (self.stats.lignes_produits + self.stats.lignes_frais) / self.stats.lignes_total * 100
            logger.info(f"Taux de succes:       {success_rate:.1f}%")

        if self.stats.lignes_rejetees > 0:
            logger.warning(f"ATTENTION: {self.stats.lignes_rejetees} lignes rejetees car prix ou montant manquant")

        if self.stats.erreurs:
            logger.warning(f"Erreurs: {len(self.stats.erreurs)}")
            for err in self.stats.erreurs[:5]:
                logger.warning(f"  - {err}")

        return factures


# =============================================================================
# COMPATIBILITY ALIAS
# =============================================================================

# Alias pour compatibilite avec code existant
MetroParserV2 = MetroParserV3


# =============================================================================
# CLI
# =============================================================================

def test_extraction(pdf_path: str, debug: bool = False):
    """Test d'extraction sur un fichier."""
    parser = MetroParserV3(debug=debug)
    facture = parser.extract_file(Path(pdf_path))

    if not facture:
        print("ECHEC extraction")
        return None

    print("=" * 80)
    print("EXTRACTION REUSSIE")
    print("=" * 80)
    print(f"Fichier:    {facture.source_file}")
    print(f"Numero:     {facture.numero_facture} ({facture.numero_interne})")
    print(f"Date:       {facture.date_facture}")
    print(f"Magasin:    {facture.magasin_nom}")
    print(f"Client:     {facture.client_nom} ({facture.client_numero})")
    print(f"Total HT:   {facture.total_ht}")
    print(f"Total TTC:  {facture.total_ttc}")
    print(f"Nb lignes:  {len(facture.lignes)} (frais: {facture.lignes_frais}, rejetees: {facture.lignes_rejetees})")
    print(f"Qualite:    {facture.extraction_quality:.0f}%")
    if facture.lignes_rejetees > 0:
        print(f"\n⚠️  {facture.lignes_rejetees} lignes rejetees (sans prix ou montant)")

    print("\n" + "=" * 80)
    print("LIGNES EXTRAITES")
    print("=" * 80)

    total_calc = 0
    for l in facture.lignes:
        type_label = f"[{l.line_type}]" if l.line_type else ""
        frais_label = "[FRAIS]" if l.est_frais else ""
        print(f"\n{l.ligne_numero:3d}. {l.designation or 'N/A'}")
        print(f"     EAN: {l.ean} | Art: {l.article_numero} {type_label} {frais_label}")
        print(f"     Prix: {l.prix_unitaire} x Qte: {l.quantite} = {l.montant_ligne}")
        print(f"     TVA: {l.code_tva} ({l.taux_tva}%) | Confidence: {l.parse_confidence:.0%}")

        if l.montant_ligne and not l.est_frais:
            total_calc += l.montant_ligne

    print("\n" + "=" * 80)
    ecart = abs(total_calc - (facture.total_ht or 0))
    print(f"TOTAL CALCULE: {total_calc:.2f} EUR")
    print(f"TOTAL FACTURE: {facture.total_ht} EUR")
    print(f"ECART:         {ecart:.2f} EUR ({ecart/(facture.total_ht or 1)*100:.1f}%)")
    print("=" * 80)

    return facture


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description='ETL METRO v3 - Extraction PDF')
    arg_parser.add_argument('pdf', nargs='?', help='Chemin vers le fichier PDF')
    arg_parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    arg_parser.add_argument('--dir', help='Repertoire de PDFs a traiter')

    args = arg_parser.parse_args()

    if args.dir:
        parser = MetroParserV3(debug=args.debug)
        factures = parser.extract_directory(Path(args.dir))
        print(f"\n{len(factures)} factures extraites")
    elif args.pdf:
        test_extraction(args.pdf, debug=args.debug)
    else:
        print("Usage: python extract_metro_pdf.py [--debug] <fichier.pdf>")
        print("       python extract_metro_pdf.py --dir <repertoire>")
