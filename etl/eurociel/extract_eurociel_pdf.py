#!/usr/bin/env python3
"""
ETL EUROCIEL - Extraction des factures PDF
==========================================
Parser pour les factures EUROCIEL (grossiste alimentaire africain/tropical).

Fournisseur:
- Nom: EUROCIEL
- SIRET: 510154313
- TVA: FR55510154313

Format ligne article EUROCIEL:
    Ref | Désignation | Qté | Poids (kg) | Px.unit | Montant HT | Code TVA

Colonnes:
- Ref: Référence article (numéro ligne)
- Désignation: Nom du produit
- Qté: Quantité commandée (colis/unités)
- Poids: Poids en kg
- Px.unit: Prix unitaire HT (au kg ou à l'unité)
- Montant HT: Montant total HT
- Code TVA: C07/C2=5.5%, C08=20%

Types de documents:
- FA: Facture
- AV: Avoir (crédit)

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

# Codes TVA EUROCIEL
TVA_CODES = {
    'C07': 5.5,   # TVA réduite (alimentaire)
    'C2': 5.5,    # TVA réduite (alimentaire) - ancien code
    'C08': 20.0,  # TVA normale (non-alimentaire)
}

# Catégories de produits EUROCIEL
CATEGORIES = {
    'POISSON': [
        'COURBINE', 'TILAPIA', 'BARRACUDA', 'OMBRINE', 'PANGASIUS',
        'POISSON CHAT', 'CREVETTE', 'CRABE', 'EMPEREUR', 'ACOUPA',
        'KANDRATIKI', 'IKAGEL', 'CAPITAINE', 'DORADE', 'MACHOIRON',
        'CARPE', 'SILURE', 'MORUE', 'STOCKFISH', 'CHINCHARD'
    ],
    'VOLAILLE': [
        'POULET', 'POULE', 'AILE', 'CUISSE', 'PILON', 'DINDE',
        'GESIER', 'PATTES', 'CROUPION', 'DOS DE POULET'
    ],
    'LEGUMES': [
        'MANIOC', 'NDOLE', 'FUMBWA', 'GOMBO', 'SAKA SAKA', 'PLACALI',
        'PLANTAIN', 'POMME DE TERRE', 'IGNAME', 'GINGEMBRE', 'PIMENT',
        'EPINARD', 'FEUILLE', 'BANANE', 'ATTIÉKÉ', 'FOUFOU'
    ],
    'BOISSONS': [
        'MALTA', 'VIMTO', 'VITAMALT', 'GUINESS', 'SCHWEPPES', 'FANTA',
        'COCA', 'SPRITE', 'JUS', 'BISSAP', 'GINGEMBRE'
    ],
    'SNACKS': [
        'CHIPS', 'NOUILLE', 'YUM YUM', 'NEMS', 'FRITE', 'BEIGNET',
        'SAMOSSA', 'ACCRA'
    ],
    'VIANDE': [
        'BOEUF', 'PORC', 'MOUTON', 'AGNEAU', 'CHÈVRE', 'QUEUE',
        'PIED', 'TRIPE', 'ROGNON', 'FOIE'
    ],
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LigneEurociel:
    """Ligne de facture EUROCIEL extraite."""
    batch_id: str
    source_file: str
    page_numero: int = 0
    numero_facture: Optional[str] = None
    date_facture: Optional[str] = None
    type_document: str = "FA"
    fournisseur_nom: str = "EUROCIEL"
    fournisseur_siret: str = "510154313"
    client_nom: Optional[str] = None
    client_code: Optional[str] = None
    ligne_numero: int = 0
    reference: Optional[str] = None
    designation: Optional[str] = None
    quantite: Optional[float] = None
    poids: Optional[float] = None
    prix_unitaire: Optional[float] = None
    montant_ht: Optional[float] = None
    code_tva: str = "C07"
    taux_tva: float = 5.5
    est_promo: bool = False
    raw_line: Optional[str] = None
    parse_confidence: float = 0.0


@dataclass
class FactureEurociel:
    """Facture EUROCIEL complète."""
    batch_id: str
    source_file: str
    numero_facture: Optional[str] = None
    type_document: str = "FA"
    date_facture: Optional[str] = None
    fournisseur_nom: str = "EUROCIEL"
    fournisseur_siret: str = "510154313"
    client_nom: Optional[str] = None
    client_code: Optional[str] = None
    client_adresse: Optional[str] = None
    client_telephone: Optional[str] = None
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: Optional[float] = None
    poids_total: Optional[float] = None
    quantite_totale: Optional[float] = None
    lignes: List[LigneEurociel] = field(default_factory=list)
    # Stats
    lignes_parsees: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0
    page_source: int = 0
    extraction_quality: float = 0.0


@dataclass
class ExtractionStats:
    """Statistiques globales d'extraction."""
    fichiers_traites: int = 0
    fichiers_succes: int = 0
    fichiers_echec: int = 0
    pages_traitees: int = 0
    factures_extraites: int = 0
    lignes_total: int = 0
    lignes_produits: int = 0
    lignes_echec: int = 0
    lignes_rejetees: int = 0
    factures_sans_lignes: int = 0
    erreurs: List[str] = field(default_factory=list)


# =============================================================================
# PARSER ENGINE
# =============================================================================

class EurocielParser:
    """
    Parser pour les factures EUROCIEL.
    Gère les PDF multi-pages avec plusieurs factures par fichier.
    """

    def __init__(self, batch_id: str = None, debug: bool = False):
        self.batch_id = batch_id or str(uuid.uuid4())
        self.debug = debug
        self.stats = ExtractionStats()
        self._current_facture_rejections = 0
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile les patterns regex."""

        # Numéro de facture EUROCIEL (FA ou AV suivi de chiffres)
        self.RE_FACTURE = re.compile(r'\b(FA|AV)\s*(\d{6,12})\b', re.IGNORECASE)

        # Date facture (format DD/MM/YY ou DD/MM/YYYY)
        self.RE_DATE = re.compile(r'\b(\d{2}/\d{2}/(?:\d{2}|\d{4}))\b')

        # Client NOUTAM ou INCONTOURNABLE
        self.RE_CLIENT = re.compile(
            r'(NOUTAM|L[\'\s]*INCONTOURNABLE|INCONTOURNABLE)',
            re.IGNORECASE
        )

        # Code client
        self.RE_CODE_CLIENT = re.compile(r'\b([A-Z]{2}\d{4,6})\b')

        # Téléphone
        self.RE_TELEPHONE = re.compile(r'\b(0[1-9][\s.]?\d{2}[\s.]?\d{2}[\s.]?\d{2}[\s.]?\d{2})\b')

        # Total TTC / NET A PAYER
        self.RE_TOTAL_TTC = re.compile(r'NET\s+A\s+PAYER[:\s]*(\d[\d\s,]*[,.]?\d*)', re.IGNORECASE)

        # Total HT
        self.RE_TOTAL_HT = re.compile(r'TOTAL\s+H\.?T\.?[:\s]*(\d[\d\s,]*[,.]?\d*)', re.IGNORECASE)

        # Code TVA pattern - handles "C07", "C0 * 7", "C08", "C0 * 8", "C2"
        # In PDFs, TVA codes appear as "C0 * 7" with space and asterisk
        self.RE_CODE_TVA = re.compile(r'C0\s*\*?\s*([78])|C2', re.IGNORECASE)

        # Ligne article EUROCIEL - Pattern principal avec TVA "C0 * 7" format
        # Format: REF DESIGNATION QTE POIDS PX.UNIT MONTANT_HT CODE_TVA
        # Example: "1 KANDRATIKI/ACOUPA 450/900 -10Kg 2,000 20 56,8500 113,70 C0 * 7"
        self.RE_LIGNE = re.compile(
            r'^(\d{1,5})\s+'                            # Référence (numéro ligne)
            r'(.+?)\s+'                                  # Désignation
            r'(\d+[,.]?\d*)\s+'                          # Quantité (2,000)
            r'(\d+[,.]?\d*)\s+'                          # Poids (20)
            r'(\d+[,.]\d{2,4})\s+'                       # Prix unitaire (56,8500)
            r'(\d+[,.]\d{2})\s+'                         # Montant HT (113,70)
            r'(C0\s*\*?\s*[78]|C07|C08|C2)\s*$',        # Code TVA (C0 * 7 ou C07)
            re.IGNORECASE
        )

        # Pattern alternatif pour lignes avec TVA C07/C08 sans espace
        self.RE_LIGNE_ALT = re.compile(
            r'^(\d{1,5})\s+'                            # Référence
            r'(.+?)\s+'                                  # Désignation
            r'(\d+[,.]?\d*)\s+'                          # Quantité
            r'(\d+[,.]?\d*)\s+'                          # Poids
            r'(\d+[,.]\d{2,4})\s+'                       # Prix unitaire
            r'(\d+[,.]\d{2})\s*'                         # Montant HT
            r'(C07|C08|C2)?\s*$',                        # Code TVA optionnel
            re.IGNORECASE
        )

        # Pattern pour les lignes avec désignation longue (multi-mots)
        self.RE_LIGNE_LONG = re.compile(
            r'^(\d{1,5})\s+'                            # Référence
            r'(.{10,80}?)\s+'                            # Désignation longue
            r'(\d+[,.]?\d{0,3})\s+'                      # Quantité
            r'(\d+[,.]?\d{0,2})\s+'                      # Poids
            r'(\d+[,.]\d{2,4})\s+'                       # Prix unitaire
            r'(-?\d+[,.]\d{2})\s*'                       # Montant HT (peut être négatif)
            r'(C0\s*\*?\s*[78]|C07|C08|C2)?\s*$',       # Code TVA
            re.IGNORECASE
        )

    def parse_number(self, s: str) -> Optional[float]:
        """Parse un nombre (entier ou décimal)."""
        if not s:
            return None
        try:
            # Nettoyer
            cleaned = s.replace(' ', '').replace(',', '.')
            value = float(cleaned)
            # Valider (pas de montants absurdes)
            if abs(value) > 1000000:
                return None
            return value
        except (ValueError, TypeError):
            return None

    def parse_date(self, date_str: str) -> Optional[str]:
        """Parse une date au format DD/MM/YY ou DD/MM/YYYY vers YYYY-MM-DD."""
        if not date_str:
            return None
        try:
            # Format DD/MM/YY
            if len(date_str) == 8:
                dt = datetime.strptime(date_str, '%d/%m/%y')
            else:
                dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return None

    def _normalize_tva_code(self, code_tva: str) -> str:
        """
        Normalise le code TVA.
        Les PDFs EUROCIEL encodent le code TVA comme "C0 * 7" au lieu de "C07".
        """
        if not code_tva:
            return 'C07'

        # Nettoyer les espaces et astérisques
        clean = code_tva.upper().replace(' ', '').replace('*', '')

        # Mapper les variantes
        if clean in ('C07', 'C7'):
            return 'C07'
        elif clean in ('C08', 'C8'):
            return 'C08'
        elif clean == 'C2':
            return 'C2'

        return 'C07'  # Default

    def categoriser_produit(self, designation: str) -> tuple:
        """Catégorise un produit basé sur sa désignation."""
        designation_upper = designation.upper()

        for categorie, mots_cles in CATEGORIES.items():
            for mot in mots_cles:
                if mot in designation_upper:
                    return ('EPICERIE', categorie.capitalize(), None)

        return ('EPICERIE', 'Divers', None)

    def parse_line_article(self, line: str, page_num: int = 1) -> Optional[LigneEurociel]:
        """Parse une ligne article."""
        line = line.strip()
        if not line or not line[0].isdigit():
            return None

        # Ignorer les lignes de totaux et headers
        line_upper = line.upper()
        if any(x in line_upper for x in [
            'TOTAL', 'NET A', 'BASE', 'MONTANT', 'REFERENCE',
            'DESIGNATION', 'QUANTITE', 'POIDS', 'PRIX', 'TVA',
            'FACTURE', 'CLIENT', 'DATE', 'PAGE', 'AVOIR'
        ]):
            return None

        # Essayer les différents patterns
        match = None
        confidence = 0.0
        has_poids = True

        # Pattern avec poids
        match = self.RE_LIGNE.match(line)
        if match:
            confidence = 0.95
            has_poids = True
        else:
            # Pattern long
            match = self.RE_LIGNE_LONG.match(line)
            if match:
                confidence = 0.85
                has_poids = True
            else:
                # Pattern sans poids
                match = self.RE_LIGNE_ALT.match(line)
                if match:
                    confidence = 0.75
                    has_poids = False

        if not match:
            return None

        try:
            groups = match.groups()

            if has_poids and len(groups) >= 7:
                reference = groups[0]
                designation = groups[1].strip()
                quantite = self.parse_number(groups[2])
                poids = self.parse_number(groups[3])
                prix_unitaire = self.parse_number(groups[4])
                montant_ht = self.parse_number(groups[5])
                code_tva = groups[6] if len(groups) > 6 and groups[6] else 'C07'
            else:
                # Sans poids
                reference = groups[0]
                designation = groups[1].strip()
                quantite = self.parse_number(groups[2])
                poids = None
                prix_unitaire = self.parse_number(groups[3])
                montant_ht = self.parse_number(groups[4])
                code_tva = groups[5] if len(groups) > 5 and groups[5] else 'C07'

            # Normaliser code TVA (C0 * 7 -> C07, C0 * 8 -> C08)
            code_tva = self._normalize_tva_code(code_tva)
            taux_tva = TVA_CODES.get(code_tva, 5.5)

            # Détecter les promos (prix inhabituellement bas)
            est_promo = False

            ligne = LigneEurociel(
                batch_id=self.batch_id,
                source_file="",
                page_numero=page_num,
                reference=reference,
                designation=designation,
                quantite=quantite,
                poids=poids,
                prix_unitaire=prix_unitaire,
                montant_ht=montant_ht,
                code_tva=code_tva,
                taux_tva=taux_tva,
                est_promo=est_promo,
                raw_line=line,
                parse_confidence=confidence
            )

            # Validation: montant ET prix requis
            if ligne.montant_ht is not None and ligne.prix_unitaire is not None:
                return ligne
            else:
                self._current_facture_rejections += 1
                if self.debug:
                    logger.warning(f"REJECTED (missing data): {designation[:50]}")
                return None

        except Exception as e:
            if self.debug:
                logger.warning(f"Parse error: {e} - Line: {line[:60]}")
            return None

    def extract_header(self, facture: FactureEurociel, text: str):
        """Extrait les infos d'en-tête."""

        # Numéro facture (FA ou AV)
        m = self.RE_FACTURE.search(text)
        if m:
            type_doc = m.group(1).upper()
            numero = m.group(2)
            facture.numero_facture = f"{type_doc}{numero}"
            facture.type_document = type_doc

        # Date
        m = self.RE_DATE.search(text)
        if m:
            facture.date_facture = self.parse_date(m.group(1))

        # Client
        m = self.RE_CLIENT.search(text)
        if m:
            client = m.group(1).upper()
            if 'INCONTOURNABLE' in client:
                facture.client_nom = "L'INCONTOURNABLE"
            else:
                facture.client_nom = 'NOUTAM'

        # Aussi détecter depuis le nom de fichier
        if not facture.client_nom:
            filename = facture.source_file.upper()
            if 'NOUTAM' in filename:
                facture.client_nom = 'NOUTAM'
            elif 'INCONTOURNABLE' in filename or 'INCONTOUR' in filename:
                facture.client_nom = "L'INCONTOURNABLE"

        # Code client
        m = self.RE_CODE_CLIENT.search(text)
        if m:
            facture.client_code = m.group(1)

        # Téléphone
        m = self.RE_TELEPHONE.search(text)
        if m:
            facture.client_telephone = m.group(1).replace(' ', '.').replace('..', '.')

    def extract_totals(self, facture: FactureEurociel, text: str):
        """Extrait les totaux."""

        # NET A PAYER (TTC)
        m = self.RE_TOTAL_TTC.search(text)
        if m:
            facture.total_ttc = self.parse_number(m.group(1))

        # TOTAL HT
        m = self.RE_TOTAL_HT.search(text)
        if m:
            facture.total_ht = self.parse_number(m.group(1))

        # Calculer TVA si on a HT et TTC
        if facture.total_ht and facture.total_ttc:
            facture.total_tva = facture.total_ttc - facture.total_ht

    def extract_lines(self, facture: FactureEurociel, text: str, page_num: int = 1):
        """Extrait les lignes articles."""
        lines = text.split('\n')
        self._current_facture_rejections = 0

        for line in lines:
            ligne = self.parse_line_article(line, page_num)
            if ligne:
                facture.lignes_parsees += 1
                ligne.source_file = facture.source_file
                ligne.numero_facture = facture.numero_facture
                ligne.date_facture = facture.date_facture
                ligne.type_document = facture.type_document
                ligne.client_nom = facture.client_nom
                ligne.client_code = facture.client_code
                ligne.ligne_numero = facture.lignes_parsees

                facture.lignes.append(ligne)

        facture.lignes_rejetees = self._current_facture_rejections

    def validate_and_calculate_quality(self, facture: FactureEurociel):
        """Calcule le score de qualité."""
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
        if facture.total_ht or facture.total_ttc:
            score += 1
            checks += 1
        if facture.lignes:
            score += 2
            checks += 2

            # Cohérence montants
            total_calc = sum(l.montant_ht or 0 for l in facture.lignes)
            if facture.total_ht and total_calc > 0:
                ecart = abs(facture.total_ht - total_calc) / facture.total_ht
                if ecart < 0.05:
                    score += 2
                elif ecart < 0.15:
                    score += 1
                checks += 2
        else:
            checks += 4

        facture.extraction_quality = (score / checks * 100) if checks > 0 else 0

        # Calculer poids total et quantité totale
        facture.poids_total = sum(l.poids or 0 for l in facture.lignes)
        facture.quantite_totale = sum(l.quantite or 0 for l in facture.lignes)

    def extract_page(self, text: str, page_num: int, source_file: str) -> Optional[FactureEurociel]:
        """Extrait une facture depuis une page de texte."""
        facture = FactureEurociel(
            batch_id=self.batch_id,
            source_file=source_file,
            page_source=page_num
        )

        self.extract_header(facture, text)
        self.extract_lines(facture, text, page_num)
        self.extract_totals(facture, text)
        self.validate_and_calculate_quality(facture)

        return facture if facture.numero_facture else None

    def extract_file(self, pdf_path: Path) -> List[FactureEurociel]:
        """
        Extrait les factures d'un fichier PDF.
        Un PDF peut contenir plusieurs factures (une par page ou plusieurs pages par facture).
        """
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber non installé")
            return []

        self.stats.fichiers_traites += 1
        factures = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                current_facture = None
                current_facture_num = None

                for page_num, page in enumerate(pdf.pages, 1):
                    self.stats.pages_traitees += 1
                    text = page.extract_text() or ""

                    if not text.strip():
                        continue

                    # Chercher un numéro de facture dans la page
                    m = self.RE_FACTURE.search(text)
                    if m:
                        page_facture_num = f"{m.group(1).upper()}{m.group(2)}"

                        # Nouvelle facture détectée
                        if page_facture_num != current_facture_num:
                            # Sauvegarder la facture précédente
                            if current_facture and current_facture.lignes:
                                self.validate_and_calculate_quality(current_facture)
                                factures.append(current_facture)
                                self.stats.factures_extraites += 1

                            # Créer une nouvelle facture
                            current_facture = FactureEurociel(
                                batch_id=self.batch_id,
                                source_file=pdf_path.name,
                                page_source=page_num
                            )
                            current_facture_num = page_facture_num
                            self.extract_header(current_facture, text)

                    # Extraire les lignes de cette page
                    if current_facture:
                        self.extract_lines(current_facture, text, page_num)
                        self.extract_totals(current_facture, text)

                # Sauvegarder la dernière facture
                if current_facture and current_facture.lignes:
                    self.validate_and_calculate_quality(current_facture)
                    factures.append(current_facture)
                    self.stats.factures_extraites += 1

                self.stats.fichiers_succes += 1

                # Stats lignes
                for f in factures:
                    self.stats.lignes_total += len(f.lignes)
                    self.stats.lignes_produits += len(f.lignes)
                    self.stats.lignes_rejetees += f.lignes_rejetees

                if not factures:
                    self.stats.factures_sans_lignes += 1
                    logger.warning(f"PDF sans factures valides: {pdf_path.name}")

                if self.debug:
                    logger.info(
                        f"Extrait {pdf_path.name}: {len(factures)} factures, "
                        f"{sum(len(f.lignes) for f in factures)} lignes"
                    )

                return factures

        except Exception as e:
            logger.error(f"Erreur extraction {pdf_path.name}: {e}")
            self.stats.fichiers_echec += 1
            self.stats.erreurs.append(f"{pdf_path.name}: {str(e)}")
            return []

    def extract_directory(self, directory: Path) -> List[FactureEurociel]:
        """Extrait toutes les factures d'un répertoire."""
        all_factures = []
        pdf_files = sorted(directory.rglob('*.pdf'))

        logger.info(f"Extraction de {len(pdf_files)} PDFs depuis {directory}")

        for i, pdf in enumerate(pdf_files, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(pdf_files)}")

            factures = self.extract_file(pdf)
            all_factures.extend(factures)

        # Rapport
        self._print_report(all_factures)

        return all_factures

    def _print_report(self, factures: List[FactureEurociel]):
        """Affiche le rapport d'extraction."""
        logger.info("=" * 60)
        logger.info("RAPPORT D'EXTRACTION EUROCIEL")
        logger.info("=" * 60)
        logger.info(f"Fichiers traités:     {self.stats.fichiers_traites}")
        logger.info(f"Fichiers succès:      {self.stats.fichiers_succes}")
        logger.info(f"Fichiers échec:       {self.stats.fichiers_echec}")
        logger.info(f"Pages traitées:       {self.stats.pages_traitees}")
        logger.info(f"Factures extraites:   {len(factures)}")
        logger.info(f"Factures sans lignes: {self.stats.factures_sans_lignes}")
        logger.info("-" * 60)
        logger.info(f"Lignes total:         {self.stats.lignes_total}")
        logger.info(f"Lignes produits:      {self.stats.lignes_produits}")
        logger.info(f"Lignes REJETÉES:      {self.stats.lignes_rejetees}")

        if self.stats.lignes_total > 0:
            success_rate = self.stats.lignes_produits / (
                self.stats.lignes_total + self.stats.lignes_rejetees
            ) * 100
            logger.info(f"Taux de succès:       {success_rate:.1f}%")

        # Stats par type de document
        factures_fa = [f for f in factures if f.type_document == 'FA']
        factures_av = [f for f in factures if f.type_document == 'AV']
        logger.info("-" * 60)
        logger.info(f"Factures (FA):        {len(factures_fa)}")
        logger.info(f"Avoirs (AV):          {len(factures_av)}")

        # Stats par client
        clients = {}
        for f in factures:
            client = f.client_nom or 'INCONNU'
            if client not in clients:
                clients[client] = {'count': 0, 'lignes': 0, 'montant': 0}
            clients[client]['count'] += 1
            clients[client]['lignes'] += len(f.lignes)
            clients[client]['montant'] += f.total_ht or 0

        logger.info("-" * 60)
        logger.info("PAR CLIENT:")
        for client, stats in sorted(clients.items()):
            logger.info(
                f"  {client}: {stats['count']} factures, "
                f"{stats['lignes']} lignes, {stats['montant']:.2f} EUR HT"
            )


# =============================================================================
# CLI
# =============================================================================

def test_extraction(pdf_path: str, debug: bool = False):
    """Test d'extraction sur un fichier."""
    parser = EurocielParser(debug=debug)
    factures = parser.extract_file(Path(pdf_path))

    if not factures:
        print("ÉCHEC extraction - aucune facture trouvée")
        return None

    for facture in factures:
        print("=" * 80)
        print("EXTRACTION EUROCIEL RÉUSSIE")
        print("=" * 80)
        print(f"Fichier:    {facture.source_file}")
        print(f"Page:       {facture.page_source}")
        print(f"Facture:    N°{facture.numero_facture} ({facture.type_document})")
        print(f"Date:       {facture.date_facture}")
        print(f"Client:     {facture.client_nom} (code: {facture.client_code})")
        print(f"Total HT:   {facture.total_ht} EUR")
        print(f"Total TTC:  {facture.total_ttc} EUR")
        print(f"Poids:      {facture.poids_total} kg")
        print(f"Nb lignes:  {len(facture.lignes)} (rejetées: {facture.lignes_rejetees})")
        print(f"Qualité:    {facture.extraction_quality:.0f}%")

        print("\n" + "=" * 80)
        print("LIGNES EXTRAITES")
        print("=" * 80)

        total_calc = 0
        for l in facture.lignes:
            print(f"\n{l.ligne_numero:3d}. {l.designation or 'N/A'}")
            print(f"     Qté: {l.quantite} | Poids: {l.poids} kg | PU: {l.prix_unitaire}")
            print(f"     Montant HT: {l.montant_ht} | TVA: {l.code_tva} ({l.taux_tva}%)")

            if l.montant_ht:
                total_calc += l.montant_ht

        print("\n" + "=" * 80)
        ecart = abs(total_calc - (facture.total_ht or 0))
        print(f"TOTAL CALCULÉ: {total_calc:.2f} EUR")
        print(f"TOTAL FACTURE: {facture.total_ht} EUR")
        print(f"ÉCART:         {ecart:.2f} EUR")
        print("=" * 80)

    return factures


if __name__ == '__main__':
    import argparse

    arg_parser = argparse.ArgumentParser(description='ETL EUROCIEL - Extraction PDF')
    arg_parser.add_argument('pdf', nargs='?', help='Chemin vers le fichier PDF')
    arg_parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    arg_parser.add_argument('--dir', help='Répertoire de PDFs')

    args = arg_parser.parse_args()

    if args.dir:
        parser = EurocielParser(debug=args.debug)
        factures = parser.extract_directory(Path(args.dir))
        print(f"\n{len(factures)} factures extraites")
    elif args.pdf:
        test_extraction(args.pdf, debug=args.debug)
    else:
        print("Usage: python extract_eurociel_pdf.py [--debug] <fichier.pdf>")
        print("       python extract_eurociel_pdf.py --dir <répertoire>")
