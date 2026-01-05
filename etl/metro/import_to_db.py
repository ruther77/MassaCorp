#!/usr/bin/env python3
"""
Import METRO JSON to PostgreSQL
================================
Script pour importer les données METRO depuis JSON vers PostgreSQL
avec calcul automatique du colisage et des prix unitaires réels.

Usage:
    python import_to_db.py --json metro_data.json --db postgresql://... --tenant 1
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import execute_values
    HAS_DB = True
except ImportError:
    HAS_DB = False
    logger.error("psycopg2 non installé: pip install psycopg2-binary")


# =============================================================================
# Parsing de la désignation pour extraire le colisage
# =============================================================================

# Patterns pour détecter le colisage dans la désignation
COLISAGE_PATTERNS = [
    # "12X33CL" -> 12 unités de 33cl
    r'(\d+)\s*[xX]\s*(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|G|KG)',
    # "6X75CL" -> 6 unités
    r'(\d+)\s*[xX]\s*(\d+(?:[,\.]\d+)?)\s*$',
    # "BTE 12" ou "CTN 24"
    r'(?:BTE|CTN|PCK|PAK|LOT)\s*(\d+)',
    # "x12" à la fin
    r'[xX](\d+)\s*$',
]

# Patterns pour extraire le volume
VOLUME_PATTERNS = [
    # "70CL" -> 0.70 L
    r'(\d+(?:[,\.]\d+)?)\s*(CL)',
    # "75CL" -> 0.75 L
    r'(\d+(?:[,\.]\d+)?)\s*(ML)',
    # "1L" ou "1,5L"
    r'(\d+(?:[,\.]\d+)?)\s*(L)\b',
]


def parse_designation(designation: str) -> Dict:
    """
    Parse la désignation pour extraire colisage et volume.

    Returns:
        Dict avec colisage, volume_unitaire (en L), unite
    """
    result = {
        'colisage': 1,
        'volume_unitaire': None,
        'unite': 'U',
    }

    if not designation:
        return result

    designation_upper = designation.upper()

    # Chercher le colisage
    for pattern in COLISAGE_PATTERNS:
        match = re.search(pattern, designation_upper)
        if match:
            try:
                result['colisage'] = int(match.group(1))
                break
            except (ValueError, IndexError):
                pass

    # Chercher le volume
    for pattern in VOLUME_PATTERNS:
        match = re.search(pattern, designation_upper)
        if match:
            try:
                value = float(match.group(1).replace(',', '.'))
                unit = match.group(2)

                if unit == 'CL':
                    result['volume_unitaire'] = value / 100  # -> L
                    result['unite'] = 'L'
                elif unit == 'ML':
                    result['volume_unitaire'] = value / 1000  # -> L
                    result['unite'] = 'L'
                elif unit == 'L':
                    result['volume_unitaire'] = value
                    result['unite'] = 'L'
                break
            except (ValueError, IndexError):
                pass

    return result


def calculer_colisage_depuis_montant(
    quantite: int,
    prix_unitaire: float,
    montant: float
) -> int:
    """
    Calcule le colisage à partir du montant.

    Si montant != quantite * prix_unitaire, alors:
    colisage = montant / (quantite * prix_unitaire)
    """
    if quantite <= 0 or prix_unitaire <= 0:
        return 1

    montant_attendu = quantite * prix_unitaire

    # Si les montants correspondent, pas de colisage
    if abs(montant - montant_attendu) < 0.01:
        return 1

    # Sinon, calculer le colisage
    try:
        colisage = round(montant / montant_attendu)
        return max(1, colisage)
    except:
        return 1


def get_categorie_id(regie: str, designation: str, db_cursor) -> Tuple[Optional[int], str, str, Optional[str]]:
    """
    Trouve la catégorie unifiée pour un produit METRO.

    Returns:
        Tuple (categorie_id, famille, categorie, sous_categorie)
    """
    # Mapping régie METRO -> famille/catégorie
    REGIE_MAP = {
        'S': ('BOISSONS', 'Spiritueux', 'Whisky'),  # TODO: détecter sous-cat
        'B': ('BOISSONS', 'Bières', None),
        'T': ('BOISSONS', 'Vins', None),
        'M': ('BOISSONS', 'Alcools', None),
    }

    if regie and regie in REGIE_MAP:
        famille, categorie, sous_cat = REGIE_MAP[regie]
    else:
        # Détecter à partir de la désignation
        designation_upper = designation.upper() if designation else ''

        if any(k in designation_upper for k in ['WHISKY', 'WHISKEY', 'WH ']):
            famille, categorie, sous_cat = 'BOISSONS', 'Spiritueux', 'Whisky'
        elif any(k in designation_upper for k in ['VODKA', 'GIN', 'RHUM', 'RUM']):
            famille, categorie, sous_cat = 'BOISSONS', 'Spiritueux', 'Autres spiritueux'
        elif any(k in designation_upper for k in ['BIERE', 'BEER', 'HEINEKEN', 'LEFFE', 'CORONA']):
            famille, categorie, sous_cat = 'BOISSONS', 'Bières', None
        elif any(k in designation_upper for k in ['VIN', 'WINE', 'CHATEAU']):
            famille, categorie, sous_cat = 'BOISSONS', 'Vins', None
        elif any(k in designation_upper for k in ['CHAMPAGNE', 'PROSECCO']):
            famille, categorie, sous_cat = 'BOISSONS', 'Champagnes', None
        elif any(k in designation_upper for k in ['COCA', 'PEPSI', 'ORANGINA', 'PERRIER', 'EVIAN']):
            famille, categorie, sous_cat = 'BOISSONS', 'Soft drinks', None
        elif any(k in designation_upper for k in ['JUS', 'JUICE']):
            famille, categorie, sous_cat = 'BOISSONS', 'Jus de fruits', None
        else:
            famille, categorie, sous_cat = 'EPICERIE', 'Epicerie', None

    # Chercher l'ID dans dim_categorie_produit
    categorie_id = None
    if db_cursor:
        try:
            db_cursor.execute("""
                SELECT categorie_id FROM dwh.dim_categorie_produit
                WHERE famille = %s AND categorie = %s
                LIMIT 1
            """, (famille, categorie))
            row = db_cursor.fetchone()
            if row:
                categorie_id = row[0]
        except:
            pass

    return categorie_id, famille, categorie, sous_cat


# =============================================================================
# Import principal
# =============================================================================

def safe_decimal(value, default=Decimal(0)) -> Decimal:
    """Convertit une valeur en Decimal de manière sécurisée."""
    if value is None:
        return default
    try:
        # Gère les strings avec virgule
        if isinstance(value, str):
            value = value.replace(',', '.').strip()
            if not value or value in ('null', 'None', 'NaN', ''):
                return default
        return Decimal(str(value))
    except:
        return default


def safe_float(value, default=0.0) -> float:
    """Convertit une valeur en float de manière sécurisée."""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(',', '.').strip()
            if not value or value in ('null', 'None', 'NaN', ''):
                return default
        return float(value)
    except:
        return default


def safe_int(value, default=0) -> int:
    """Convertit une valeur en int de manière sécurisée."""
    if value is None:
        return default
    try:
        return int(float(value))
    except:
        return default


def import_metro_data(
    json_path: str,
    db_url: str,
    tenant_id: int,
    dry_run: bool = False
) -> Dict:
    """
    Importe les données METRO depuis JSON vers PostgreSQL.

    Args:
        json_path: Chemin vers metro_data.json
        db_url: URL PostgreSQL
        tenant_id: ID du tenant
        dry_run: Si True, ne pas insérer

    Returns:
        Statistiques d'import
    """
    start_time = time.time()
    stats = {
        'factures_importees': 0,
        'lignes_importees': 0,
        'produits_agreges': 0,
        'erreurs': [],
    }

    # Charger le JSON
    logger.info(f"Chargement de {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    factures = data.get('factures', [])
    logger.info(f"Trouvé {len(factures)} factures")

    if dry_run:
        logger.info("Mode dry-run, pas d'insertion")
        return stats

    # Connexion DB
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        # Créer les tables si nécessaire
        sql_path = Path(__file__).parent / 'sql' / 'create_tables.sql'
        if sql_path.exists():
            logger.info("Création des tables...")
            with open(sql_path, 'r') as f:
                cursor.execute(f.read())
            conn.commit()

        # Import des factures
        for facture_data in factures:
            try:
                numero = facture_data.get('numero', '')
                if not numero:
                    continue

                # Parser la date
                date_str = facture_data.get('date', '')
                try:
                    date_facture = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    date_facture = datetime.now().date()

                # Calculer les totaux TVA avec conversion sécurisée
                lignes = facture_data.get('lignes', [])
                total_ht = safe_decimal(facture_data.get('total_ht'), Decimal(0))
                total_tva = Decimal(0)

                for ligne in lignes:
                    montant = safe_decimal(ligne.get('montant'), Decimal(0))
                    taux = safe_decimal(ligne.get('taux_tva'), Decimal(20))
                    total_tva += montant * taux / Decimal(100)

                total_tva = total_tva.quantize(Decimal('0.01'), ROUND_HALF_UP)
                total_ttc = total_ht + total_tva

                # Magasin avec valeur par défaut
                magasin = facture_data.get('magasin') or 'METRO'

                # Vérifier si existe déjà
                cursor.execute("""
                    SELECT id FROM dwh.metro_facture
                    WHERE tenant_id = %s AND numero = %s
                """, (tenant_id, numero))

                existing = cursor.fetchone()
                if existing:
                    facture_id = existing[0]
                    logger.debug(f"Facture {numero} existe déjà (id={facture_id})")
                else:
                    # Insérer la facture
                    cursor.execute("""
                        INSERT INTO dwh.metro_facture (
                            tenant_id, numero, date_facture, magasin,
                            total_ht, total_tva, total_ttc,
                            fichier_source
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        tenant_id, numero, date_facture,
                        magasin,
                        float(total_ht), float(total_tva), float(total_ttc),
                        facture_data.get('fichier'),
                    ))
                    facture_id = cursor.fetchone()[0]
                    stats['factures_importees'] += 1
                    conn.commit()  # Commit après chaque facture pour éviter les rollbacks en cascade

                # Insérer les lignes
                for ligne in lignes:
                    ean = ligne.get('ean', '')
                    if not ean:
                        continue

                    designation = ligne.get('designation', '') or ''

                    # Gestion des valeurs nulles avec conversion sécurisée
                    quantite = safe_int(ligne.get('quantite'), 0)
                    prix_unitaire = safe_float(ligne.get('prix_unitaire'), 0.0)
                    montant = safe_float(ligne.get('montant'), 0.0)
                    taux_tva = safe_float(ligne.get('taux_tva'), 20.0)

                    # Calculer le colisage
                    colisage = calculer_colisage_depuis_montant(quantite, prix_unitaire, montant)

                    # Parser la désignation pour le volume
                    parsed = parse_designation(designation)
                    if parsed['colisage'] > 1 and colisage == 1:
                        colisage = parsed['colisage']

                    # Calculer les vraies quantités et prix
                    # IMPORTANT: dans le JSON METRO, prix_unitaire est DÉJÀ le prix par unité (bouteille)
                    # Le montant = quantite_colis * colisage * prix_unitaire
                    quantite_colis = quantite
                    quantite_unitaire = quantite * colisage
                    prix_unitaire_reel = prix_unitaire  # Déjà le prix unitaire !
                    prix_colis = prix_unitaire * colisage  # Prix du colis = prix_unit × colisage

                    # TVA
                    montant_ht = safe_decimal(montant, Decimal(0))
                    taux = safe_decimal(taux_tva, Decimal(20))
                    montant_tva = (montant_ht * taux / Decimal(100)).quantize(Decimal('0.01'))

                    # Catégorie
                    regie = ligne.get('regie')
                    cat_id, famille, categorie, sous_cat = get_categorie_id(regie, designation, cursor)

                    cursor.execute("""
                        INSERT INTO dwh.metro_ligne (
                            tenant_id, facture_id,
                            ean, article_numero, designation,
                            colisage, quantite_colis, quantite_unitaire,
                            prix_colis, prix_unitaire, montant_ht,
                            volume_unitaire, unite,
                            taux_tva, code_tva, montant_tva,
                            regie, vol_alcool,
                            categorie_id
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        tenant_id, facture_id,
                        ean, ligne.get('article_numero'), designation,
                        colisage, quantite_colis, quantite_unitaire,
                        prix_colis, prix_unitaire_reel, float(montant_ht),
                        parsed['volume_unitaire'], parsed['unite'],
                        taux_tva, ligne.get('code_tva'), float(montant_tva),
                        regie, safe_float(ligne.get('vol_alcool')),
                        cat_id,
                    ))
                    stats['lignes_importees'] += 1

                # Commit après les lignes de chaque facture
                conn.commit()

            except Exception as e:
                conn.rollback()  # Rollback uniquement cette facture
                stats['erreurs'].append(f"Facture {facture_data.get('numero', '?')}: {str(e)}")
                logger.error(f"Erreur facture: {e}")

        conn.commit()
        logger.info(f"Importé {stats['factures_importees']} factures, {stats['lignes_importees']} lignes")

        # Recalculer les agrégats
        logger.info("Recalcul des agrégats...")
        cursor.execute("SELECT dwh.recalculer_metro_agregats(%s)", (tenant_id,))
        stats['produits_agreges'] = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Agrégé {stats['produits_agreges']} produits")

    except Exception as e:
        conn.rollback()
        stats['erreurs'].append(f"Erreur globale: {str(e)}")
        logger.error(f"Erreur: {e}")
        raise

    finally:
        cursor.close()
        conn.close()

    stats['duree_ms'] = int((time.time() - start_time) * 1000)
    return stats


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Import METRO JSON to PostgreSQL')
    parser.add_argument('--json', required=True, help='Chemin vers metro_data.json')
    parser.add_argument('--db', required=True, help='URL PostgreSQL')
    parser.add_argument('--tenant', type=int, default=1, help='Tenant ID')
    parser.add_argument('--dry-run', action='store_true', help='Ne pas insérer')
    args = parser.parse_args()

    if not HAS_DB:
        logger.error("psycopg2 requis: pip install psycopg2-binary")
        sys.exit(1)

    stats = import_metro_data(
        json_path=args.json,
        db_url=args.db,
        tenant_id=args.tenant,
        dry_run=args.dry_run,
    )

    print(f"\n=== Résultat import ===")
    print(f"Factures: {stats['factures_importees']}")
    print(f"Lignes: {stats['lignes_importees']}")
    print(f"Produits agrégés: {stats['produits_agreges']}")
    print(f"Durée: {stats['duree_ms']}ms")

    if stats['erreurs']:
        print(f"\nErreurs ({len(stats['erreurs'])}):")
        for err in stats['erreurs'][:10]:
            print(f"  - {err}")


if __name__ == '__main__':
    main()
