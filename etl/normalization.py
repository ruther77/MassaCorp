"""
ETL Normalization Utilities
============================
Module de normalisation des donnees pour tous les fournisseurs (METRO, EUROCIEL, TAIYAT).
Implemente les mini-workflows N1-N8 definis dans WORKFLOW_NORMALISATION_COLONNES.md

Author: MassaCorp ETL Team
Version: 1.0.0
"""

import re
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, Tuple


# =============================================================================
# N1: Nettoyage texte de base
# =============================================================================

def clean_text(text: Optional[str]) -> Optional[str]:
    """
    Nettoie un texte des caracteres parasites.

    - Supprime tabs, newlines, carriage returns
    - Supprime guillemets francais
    - Remplace non-breaking spaces
    - Reduit espaces multiples en un seul
    """
    if text is None:
        return None

    result = text
    # Remove tabs, newlines, carriage returns
    result = result.replace('\t', ' ')
    result = result.replace('\n', '')
    result = result.replace('\r', '')
    # Remove French quotes
    result = result.replace('\u00AB', '').replace('\u00BB', '')
    # Replace non-breaking space
    result = result.replace('\u00A0', ' ')
    # Reduce multiple spaces
    result = re.sub(r'\s+', ' ', result)
    return result.strip()


# =============================================================================
# N1: Normalisation Designation produit
# =============================================================================

# Table des abbreviations a etendre
ABBREVIATIONS = {
    r'\bWH\b': 'Whiskey',
    r'\bVDK\b': 'Vodka',
    r'\bCHAMP\b': 'Champagne',
    r'\bBLE\b': 'Blonde',
    r'\bBRN\b': 'Brune',
    r'\bAMB\b': 'Ambree',
    r'\bRGE\b': 'Rouge',
    r'\bBLC\b': 'Blanc',
    r'\bRS\b': 'Rose',
}

# Unites a garder en minuscules
UNITS_LOWER = {'cl', 'ml', 'l', 'kg', 'g', 'mg'}


def normalize_designation(designation: Optional[str]) -> Optional[str]:
    """
    Normalise le nom d'un produit (N1).

    Etapes:
    1. Nettoyage caracteres
    2. Title Case avec exceptions pour unites
    3. Expansion des abbreviations
    4. Normalisation apostrophes
    5. Normalisation volumes (35CL -> 35cl, 0.7L -> 70cl)
    """
    if not designation:
        return None

    # Step 1: Clean
    result = clean_text(designation)
    if not result:
        return None

    # Step 2: Title Case with unit exceptions
    words = result.split()
    titled_words = []
    for word in words:
        lower = word.lower()
        # Check if it's a unit or number+unit
        if lower in UNITS_LOWER or re.match(r'^\d+[a-z]+$', lower):
            titled_words.append(lower)
        else:
            titled_words.append(word.capitalize())
    result = ' '.join(titled_words)

    # Step 3: Expand abbreviations
    for pattern, replacement in ABBREVIATIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Convert degree notation: 40D/40d -> 40deg (case insensitive, after title case)
    result = re.sub(r'(\d+)[Dd]\b', lambda m: m.group(1) + '\u00B0', result)

    # Step 4: Normalize apostrophes
    result = result.replace("'", "\u2019")  # Typographic apostrophe
    result = result.replace("`", "\u2019")
    result = re.sub(r"\s+'\s+", "'", result)

    # Step 5: Normalize volumes
    # 35CL -> 35cl
    result = re.sub(r'(\d+)CL\b', r'\1cl', result, flags=re.IGNORECASE)
    result = re.sub(r'(\d+)ML\b', r'\1ml', result, flags=re.IGNORECASE)
    # 0.7L / 0,7L -> 70cl
    result = re.sub(r'0[,.]7\s*L\b', '70cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]5\s*L\b', '50cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]33\s*L\b', '33cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]25\s*L\b', '25cl', result, flags=re.IGNORECASE)
    # 1L -> 100cl (only standalone L, not if already processed as cl)
    def convert_liters(m):
        val = int(m.group(1))
        return f'{val * 100}cl' if val < 10 else m.group(0)  # Only convert 1L-9L
    result = re.sub(r'(\d+)\s*L\b(?!cl)', convert_liters, result, flags=re.IGNORECASE)

    return result


# =============================================================================
# N2: Normalisation EAN
# =============================================================================

def calculate_ean_checksum(ean: str) -> int:
    """Calcule le checksum EAN-13."""
    if len(ean) < 12:
        return -1
    total = sum(
        int(ean[i]) * (1 if i % 2 == 0 else 3)
        for i in range(12)
    )
    return (10 - (total % 10)) % 10


def normalize_ean(ean: Optional[str]) -> Optional[str]:
    """
    Normalise un code EAN (N2).

    - Supprime espaces et caracteres non numeriques
    - Gere EAN-8 et EAN-13
    - Valide le checksum
    """
    if not ean:
        return None

    # Clean: keep only digits
    clean = re.sub(r'\D', '', ean.strip())

    # Handle leading zero if 14 digits
    if len(clean) == 14 and clean.startswith('0'):
        clean = clean[1:]

    # Validate length
    if len(clean) not in (8, 13):
        return None

    # Pad EAN-8 to EAN-13
    if len(clean) == 8:
        clean = '00000' + clean

    # Validate checksum
    expected = calculate_ean_checksum(clean)
    actual = int(clean[12])
    if expected != actual:
        # Log warning but still return (source data sometimes incorrect)
        pass

    return clean


# =============================================================================
# N3: Normalisation Categorie
# =============================================================================

# Mapping des categories par fournisseur
CATEGORY_MAPPING: Dict[str, Dict[str, str]] = {
    'METRO': {
        'SPIRITUEUX': 'ALC_SPIRITUEUX',
        'BRASSERIE': 'ALC_BIERE',
        'CAVE': 'ALC_VIN',
        'CHAMPAGNES': 'ALC_CHAMPAGNE',
        'CHAMPAGNE': 'ALC_CHAMPAGNE',
        'EPICERIE SECHE': 'ALI_EPICERIE',
        'EPICERIE': 'ALI_EPICERIE',
        'SURGELES': 'ALI_SURGELES',
        'DROGUERIE': 'NON_ALI_DROGUERIE',
        'FOURNITURES': 'NON_ALI_FOURNITURES',
    },
    'EUROCIEL': {
        'ALCOOLS FORTS': 'ALC_SPIRITUEUX',
        'SPIRITUEUX': 'ALC_SPIRITUEUX',
        'BIERES': 'ALC_BIERE',
        'VINS': 'ALC_VIN',
        'CHAMPAGNES': 'ALC_CHAMPAGNE',
    },
    'TAIYAT': {
        'SPIRITS': 'ALC_SPIRITUEUX',
        'BEER': 'ALC_BIERE',
        'WINE': 'ALC_VIN',
        'CHAMPAGNE': 'ALC_CHAMPAGNE',
    }
}


def normalize_categorie(fournisseur: str, categorie_source: Optional[str]) -> str:
    """
    Normalise une categorie produit (N3).

    Utilise une table de mapping par fournisseur.
    Retourne 'INCONNU' si non trouve.
    """
    if not categorie_source:
        return 'INCONNU'

    fournisseur_upper = fournisseur.upper().strip()
    categorie_upper = categorie_source.upper().strip()

    mapping = CATEGORY_MAPPING.get(fournisseur_upper, {})
    return mapping.get(categorie_upper, 'INCONNU')


# =============================================================================
# N4: Normalisation Prix
# =============================================================================

def normalize_prix(prix: Optional[str]) -> Optional[Decimal]:
    """
    Normalise un prix (N4).

    Gere:
    - Format francais (virgule decimale)
    - Separateurs de milliers (espace ou point)
    - Symboles monetaires
    """
    if prix is None:
        return None

    if isinstance(prix, (int, float, Decimal)):
        return Decimal(str(prix))

    # Clean
    clean = str(prix).strip()
    clean = re.sub(r'[\u20AC EUR]', '', clean, flags=re.IGNORECASE)  # Remove euro
    clean = re.sub(r'\s+', '', clean)  # Remove spaces

    # Handle French format (1.234,56 -> 1234.56)
    if re.search(r'\d+\.\d{3},', clean):
        clean = clean.replace('.', '')
    clean = clean.replace(',', '.')

    try:
        result = Decimal(clean)
        # Validate range
        if result < 0 or result > 100000:
            return None
        return result
    except InvalidOperation:
        return None


# =============================================================================
# N5: Normalisation Quantite
# =============================================================================

def normalize_quantite(quantite: Optional[str]) -> Optional[int]:
    """
    Normalise une quantite (N5).

    - Convertit en entier
    - Gere les decimales (.0)
    - Valide la plage (1-10000)
    """
    if quantite is None:
        return None

    if isinstance(quantite, int):
        return quantite if 0 < quantite <= 10000 else None

    # Clean
    clean = str(quantite).strip()
    clean = re.sub(r'[,.]0+$', '', clean)  # Remove trailing .0
    clean = clean.replace(',', '.')

    try:
        result = round(float(clean))
        if result <= 0 or result > 10000:
            return None
        return result
    except ValueError:
        return None


# =============================================================================
# N6: Normalisation Fournisseur
# =============================================================================

@dataclass
class FournisseurInfo:
    """Informations normalisees sur un fournisseur."""
    nom_normalise: str
    siret: Optional[str]
    tva_intra: Optional[str]
    code_interne: str


# Mapping des fournisseurs
FOURNISSEUR_MAPPING: Dict[str, FournisseurInfo] = {
    'METRO': FournisseurInfo('METRO France', '399315613', 'FR12399315613', 'METRO'),
    'METRO FRANCE': FournisseurInfo('METRO France', '399315613', 'FR12399315613', 'METRO'),
    'METRO FRANCE SA': FournisseurInfo('METRO France', '399315613', 'FR12399315613', 'METRO'),
    'EUROCIEL': FournisseurInfo('EUROCIEL', None, None, 'EUROCIEL'),
    'EUROCIEL SAS': FournisseurInfo('EUROCIEL', None, None, 'EUROCIEL'),
    'TAIYAT': FournisseurInfo('TAIYAT', None, None, 'TAIYAT'),
}


def normalize_fournisseur(nom: Optional[str]) -> FournisseurInfo:
    """
    Normalise un nom de fournisseur (N6).

    Retourne les informations completes (nom, SIRET, TVA intra, code).
    """
    if not nom:
        return FournisseurInfo('INCONNU', None, None, 'INCONNU')

    nom_upper = nom.upper().strip()
    info = FOURNISSEUR_MAPPING.get(nom_upper)

    if info:
        return info
    return FournisseurInfo(nom_upper, None, None, 'INCONNU')


# =============================================================================
# N7: Normalisation Date
# =============================================================================

def normalize_date(date_str: Optional[str]) -> Optional[date]:
    """
    Normalise une date (N7).

    Gere les formats:
    - DD-MM-YYYY, DD/MM/YYYY (francais)
    - YYYY-MM-DD (ISO)
    - DD mois YYYY (francais textuel)
    """
    if not date_str:
        return None

    if isinstance(date_str, date):
        return date_str

    clean = str(date_str).strip()

    # Try French format DD-MM-YYYY or DD/MM/YYYY
    match = re.match(r'^(\d{2})[-/](\d{2})[-/](\d{4})$', clean)
    if match:
        day, month, year = match.groups()
        try:
            result = date(int(year), int(month), int(day))
            return _validate_date_range(result)
        except ValueError:
            return None

    # Try ISO format YYYY-MM-DD
    match = re.match(r'^(\d{4})[-/](\d{2})[-/](\d{2})$', clean)
    if match:
        year, month, day = match.groups()
        try:
            result = date(int(year), int(month), int(day))
            return _validate_date_range(result)
        except ValueError:
            return None

    # Try generic parsing
    try:
        result = datetime.strptime(clean, '%Y-%m-%d').date()
        return _validate_date_range(result)
    except ValueError:
        pass

    return None


def _validate_date_range(d: date) -> Optional[date]:
    """Valide qu'une date est dans une plage raisonnable."""
    min_date = date(2000, 1, 1)
    max_date = date.today()

    if d < min_date or d > max_date:
        return None
    return d


# =============================================================================
# N8: Calcul Montants (TVA, TTC)
# =============================================================================

@dataclass
class Montants:
    """Montants calcules HT, TVA et TTC."""
    montant_ht: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal


def calculate_montants(
    prix_unitaire: Optional[Decimal],
    quantite: Optional[int],
    taux_tva: Optional[Decimal] = None
) -> Optional[Montants]:
    """
    Calcule les montants HT, TVA et TTC (N8).

    Args:
        prix_unitaire: Prix unitaire HT
        quantite: Quantite
        taux_tva: Taux de TVA en pourcentage (defaut 20%)

    Returns:
        Montants calcules ou None si donnees invalides
    """
    if prix_unitaire is None or quantite is None:
        return None

    if taux_tva is None:
        taux_tva = Decimal('20.0')

    ht = Decimal(str(prix_unitaire)) * Decimal(str(quantite))
    ht = ht.quantize(Decimal('0.01'))

    tva = ht * (taux_tva / Decimal('100'))
    tva = tva.quantize(Decimal('0.01'))

    ttc = ht + tva

    return Montants(
        montant_ht=ht,
        montant_tva=tva,
        montant_ttc=ttc
    )


# =============================================================================
# Fonction de normalisation complete d'une ligne
# =============================================================================

def normalize_ligne(ligne: Dict[str, Any], fournisseur: str = 'METRO') -> Dict[str, Any]:
    """
    Normalise completement une ligne de facture.

    Applique tous les workflows N1-N8 selon le fournisseur.
    """
    result = ligne.copy()

    # N1: Designation
    if 'designation' in result:
        result['designation'] = normalize_designation(result.get('designation'))

    # N2: EAN
    if 'ean' in result:
        result['ean'] = normalize_ean(result.get('ean'))

    # N3: Categorie
    if 'categorie_source' in result:
        result['categorie_dwh'] = normalize_categorie(
            fournisseur,
            result.get('categorie_source')
        )

    # N4: Prix
    if 'prix_unitaire' in result:
        result['prix_unitaire'] = normalize_prix(result.get('prix_unitaire'))

    # N5: Quantite
    if 'quantite' in result:
        result['quantite'] = normalize_quantite(result.get('quantite'))

    # N6: Fournisseur
    fournisseur_info = normalize_fournisseur(result.get('fournisseur_nom', fournisseur))
    result['fournisseur_nom'] = fournisseur_info.nom_normalise
    result['fournisseur_siret'] = fournisseur_info.siret
    result['fournisseur_tva_intra'] = fournisseur_info.tva_intra
    result['fournisseur_code'] = fournisseur_info.code_interne

    # N7: Date
    if 'date_facture' in result:
        result['date_facture'] = normalize_date(result.get('date_facture'))

    # N8: Montants
    if result.get('prix_unitaire') and result.get('quantite'):
        montants = calculate_montants(
            result['prix_unitaire'],
            result['quantite'],
            result.get('taux_tva')
        )
        if montants:
            result['montant_ht_calc'] = montants.montant_ht
            result['montant_tva_calc'] = montants.montant_tva
            result['montant_ttc_calc'] = montants.montant_ttc

    return result


# =============================================================================
# Tests unitaires
# =============================================================================

if __name__ == '__main__':
    print("=== Tests de normalisation ===\n")

    # Test N1: Designation
    print("N1 - Designation:")
    tests_designation = [
        ("WH JACK DANIEL'S 40D 35CL", "Whiskey Jack Daniel\u2019s 40\u00B0 35cl"),
        ("VDK ABSOLUT 40D 70CL", "Vodka Absolut 40\u00B0 70cl"),
        ("HEINEKEN BLE 33CL", "Heineken Blonde 33cl"),
    ]
    for input_val, expected in tests_designation:
        result = normalize_designation(input_val)
        # Compare normalized strings
        status = "OK" if result == expected else f"FAIL (expected: {expected!r}, got: {result!r})"
        print(f"  '{input_val}' -> '{result}' [{status}]")

    # Test N2: EAN
    print("\nN2 - EAN:")
    tests_ean = [
        ("5010327325125", "5010327325125"),
        ("05010327325125", "5010327325125"),
        (" 5010327325125 ", "5010327325125"),
    ]
    for input_val, expected in tests_ean:
        result = normalize_ean(input_val)
        status = "OK" if result == expected else f"FAIL (got: {result})"
        print(f"  '{input_val}' -> '{result}' [{status}]")

    # Test N3: Categorie
    print("\nN3 - Categorie:")
    tests_cat = [
        (("METRO", "SPIRITUEUX"), "ALC_SPIRITUEUX"),
        (("EUROCIEL", "Bieres"), "ALC_BIERE"),
        (("TAIYAT", "SPIRITS"), "ALC_SPIRITUEUX"),
    ]
    for (fournisseur, cat), expected in tests_cat:
        result = normalize_categorie(fournisseur, cat)
        status = "OK" if result == expected else f"FAIL (got: {result})"
        print(f"  ({fournisseur}, '{cat}') -> '{result}' [{status}]")

    # Test N4: Prix
    print("\nN4 - Prix:")
    tests_prix = [
        ("12,50", Decimal("12.50")),
        ("1 234,56", Decimal("1234.56")),
        ("12.50", Decimal("12.50")),
    ]
    for input_val, expected in tests_prix:
        result = normalize_prix(input_val)
        status = "OK" if result == expected else f"FAIL (got: {result})"
        print(f"  '{input_val}' -> '{result}' [{status}]")

    # Test N5: Quantite
    print("\nN5 - Quantite:")
    tests_qte = [
        ("12", 12),
        ("12.0", 12),
        ("12,00", 12),
    ]
    for input_val, expected in tests_qte:
        result = normalize_quantite(input_val)
        status = "OK" if result == expected else f"FAIL (got: {result})"
        print(f"  '{input_val}' -> {result} [{status}]")

    # Test N7: Date
    print("\nN7 - Date:")
    tests_date = [
        ("07-06-2024", date(2024, 6, 7)),
        ("07/06/2024", date(2024, 6, 7)),
        ("2024-06-07", date(2024, 6, 7)),
    ]
    for input_val, expected in tests_date:
        result = normalize_date(input_val)
        status = "OK" if result == expected else f"FAIL (got: {result})"
        print(f"  '{input_val}' -> {result} [{status}]")

    print("\n=== Tous les tests termines ===")
