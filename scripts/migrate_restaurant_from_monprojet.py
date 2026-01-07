#!/usr/bin/env python3
"""
Script de migration des donnees restaurant depuis monprojet vers MassaCorp.
Importe les ingredients, plats et compositions depuis les CSV exportes.

Usage:
    docker exec -i massacorp_api python scripts/migrate_restaurant_from_monprojet.py
"""
import os
import sys
import csv
from decimal import Decimal

sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text

# Category mappings from monprojet string to MassaCorp enum
INGREDIENT_CATEGORY_MAP = {
    'viandes / poisson / charcut': 'VIANDE',
    'viandes': 'VIANDE',
    'poisson': 'POISSON',
    'fruits de mer': 'POISSON',
    'épicerie sucrée': 'EPICERIE',
    'épices & bouillons': 'CONDIMENT',
    'épices': 'CONDIMENT',
    'condiments': 'CONDIMENT',
    'laits / crèmes': 'PRODUIT_LAITIER',
    'laits': 'PRODUIT_LAITIER',
    'crèmes': 'PRODUIT_LAITIER',
    'pâtes / riz / semoule / farine': 'EPICERIE',
    'bières': 'BOISSON',
    'vins': 'BOISSON',
    'vins blancs': 'BOISSON',
    'vins rouges': 'BOISSON',
    'spiritueux': 'BOISSON',
    'boissons': 'BOISSON',
    'légumes': 'LEGUME',
    'fruits': 'FRUIT',
    '': 'AUTRE',
}

PLAT_CATEGORY_MAP = {
    'whisky': 'BOISSON',
    'spiritueux': 'BOISSON',
    'vins': 'BOISSON',
    'champagne': 'BOISSON',
    'bières': 'BOISSON',
    'apéritifs': 'BOISSON',
    'boissons chaudes': 'BOISSON',
    'viandes': 'PLAT',
    'grillades': 'PLAT',
    'bouillons': 'PLAT',
    'entrées': 'ENTREE',
    'desserts': 'DESSERT',
    'accompagnements': 'ACCOMPAGNEMENT',
    'plats': 'PLAT',
    '': 'AUTRE',
}

UNIT_MAP = {
    'kg': 'KG',
    'l': 'L',
    'unit': 'U',
    'unité': 'U',
    'g': 'G',
    'cl': 'CL',
    'ml': 'ML',
    'pack': 'U',
    '': 'U',
}


def clear_sample_data(engine, tenant_id: int = 1):
    """Remove sample data we created earlier."""
    with engine.connect() as conn:
        # Delete in correct order for foreign keys
        conn.execute(text("DELETE FROM restaurant_plat_ingredients WHERE plat_id IN (SELECT id FROM restaurant_plats WHERE tenant_id = :tid)"), {'tid': tenant_id})
        conn.execute(text("DELETE FROM restaurant_epicerie_links WHERE tenant_id = :tid"), {'tid': tenant_id})
        conn.execute(text("DELETE FROM restaurant_consumptions WHERE tenant_id = :tid"), {'tid': tenant_id})
        conn.execute(text("DELETE FROM restaurant_plats WHERE tenant_id = :tid"), {'tid': tenant_id})
        # Stock movements reference stock, so delete movements first
        conn.execute(text("DELETE FROM restaurant_stock_movements WHERE stock_id IN (SELECT id FROM restaurant_stock WHERE tenant_id = :tid)"), {'tid': tenant_id})
        conn.execute(text("DELETE FROM restaurant_stock WHERE tenant_id = :tid"), {'tid': tenant_id})
        conn.execute(text("DELETE FROM restaurant_ingredients WHERE tenant_id = :tid"), {'tid': tenant_id})
        conn.commit()
    print("Cleared existing sample data")


def migrate_ingredients(engine, csv_file: str, tenant_id: int = 1) -> dict:
    """
    Import ingredients from CSV.
    Returns: old_id -> new_id mapping
    """
    id_mapping = {}

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        ingredients = list(reader)

    with engine.connect() as conn:
        for row in ingredients:
            old_id = int(row['id'])
            nom = row['nom']
            unite = row.get('unite_base', 'kg')
            cout = float(row.get('cout_unitaire', 0) or 0)
            categorie = row.get('categorie', '') or ''
            stock_min = float(row.get('stock_min', 0) or 0)

            # Map category and unit
            mc_category = INGREDIENT_CATEGORY_MAP.get(categorie.lower().strip(), 'AUTRE')
            mc_unit = UNIT_MAP.get(unite.lower().strip(), 'U')

            # Convert cout to centimes
            prix_centimes = int(cout * 100)

            result = conn.execute(text("""
                INSERT INTO restaurant_ingredients (tenant_id, name, unit, category, prix_unitaire, seuil_alerte, is_active)
                VALUES (:tid, :name, :unit, :cat, :prix, :seuil, true)
                RETURNING id
            """), {
                'tid': tenant_id,
                'name': nom[:255],
                'unit': mc_unit,
                'cat': mc_category,
                'prix': prix_centimes,
                'seuil': stock_min if stock_min > 0 else None,
            })
            new_id = result.fetchone()[0]
            id_mapping[old_id] = new_id

        conn.commit()

    return id_mapping


def migrate_plats(engine, csv_file: str, tenant_id: int = 1) -> dict:
    """
    Import plats from CSV.
    Returns: old_id -> new_id mapping
    """
    id_mapping = {}

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        plats = list(reader)

    with engine.connect() as conn:
        for row in plats:
            old_id = int(row['id'])
            nom = row['nom']
            categorie = row.get('categorie', '') or ''
            prix_ttc = float(row.get('prix_vente_ttc', 0) or 0)
            actif = row.get('actif', 't') == 't'
            plat_type = row.get('type', 'cuisine')  # 'bar' ou 'cuisine'

            # Map category
            mc_category = PLAT_CATEGORY_MAP.get(categorie.lower().strip(), 'AUTRE')

            # Convert prix to centimes
            prix_centimes = int(prix_ttc * 100)

            # Determine if this is a "menu" (bar items are typically drinks, not menus)
            is_menu = False

            result = conn.execute(text("""
                INSERT INTO restaurant_plats (tenant_id, name, category, prix_vente, is_active, is_menu, notes)
                VALUES (:tid, :name, :cat, :prix, :actif, :is_menu, :notes)
                RETURNING id
            """), {
                'tid': tenant_id,
                'name': nom[:255],
                'cat': mc_category,
                'prix': prix_centimes,
                'actif': actif,
                'is_menu': is_menu,
                'notes': f"Type: {plat_type}, Catégorie originale: {categorie}" if categorie else f"Type: {plat_type}",
            })
            new_id = result.fetchone()[0]
            id_mapping[old_id] = new_id

        conn.commit()

    return id_mapping


def migrate_compositions(engine, csv_file: str, ingredient_map: dict, plat_map: dict):
    """Import plat-ingredient compositions from CSV."""
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        compositions = list(reader)

    inserted = 0
    skipped = 0

    with engine.connect() as conn:
        for row in compositions:
            old_plat_id = int(row['plat_id'])
            old_ing_id = int(row['ingredient_id'])
            quantite = float(row.get('quantite', 0) or 0)

            # Get mapped IDs
            new_plat_id = plat_map.get(old_plat_id)
            new_ing_id = ingredient_map.get(old_ing_id)

            if not new_plat_id or not new_ing_id:
                skipped += 1
                continue

            try:
                conn.execute(text("""
                    INSERT INTO restaurant_plat_ingredients (plat_id, ingredient_id, quantite)
                    VALUES (:plat_id, :ing_id, :qty)
                """), {
                    'plat_id': new_plat_id,
                    'ing_id': new_ing_id,
                    'qty': quantite,
                })
                inserted += 1
            except Exception as e:
                print(f"Warning: Could not insert composition plat={old_plat_id} ing={old_ing_id}: {e}")
                skipped += 1

        conn.commit()

    return inserted, skipped


def main():
    database_url = os.getenv('DATABASE_URL', 'postgresql://massa:O31xU-XOZw5ZGfyWNfn46qTI0ZdzPZNg@db:5432/MassaCorp')
    engine = create_engine(database_url)

    # CSV files
    ingredients_csv = '/data/restaurant_ingredients.csv'
    plats_csv = '/data/restaurant_plats.csv'
    compositions_csv = '/data/restaurant_plat_ingredients.csv'

    # Check files exist
    for f in [ingredients_csv, plats_csv, compositions_csv]:
        if not os.path.exists(f):
            print(f"Error: File not found: {f}")
            print("Please copy the CSV files to /data/")
            sys.exit(1)

    print("=== Migration Restaurant depuis monprojet ===\n")

    print("1. Suppression des donnees d'exemple...")
    clear_sample_data(engine, tenant_id=1)

    print("\n2. Import des ingredients...")
    ingredient_map = migrate_ingredients(engine, ingredients_csv, tenant_id=1)
    print(f"   Importes: {len(ingredient_map)} ingredients")

    print("\n3. Import des plats...")
    plat_map = migrate_plats(engine, plats_csv, tenant_id=1)
    print(f"   Importes: {len(plat_map)} plats")

    print("\n4. Import des compositions...")
    inserted, skipped = migrate_compositions(engine, compositions_csv, ingredient_map, plat_map)
    print(f"   Importees: {inserted} compositions")
    print(f"   Ignorees: {skipped} (IDs manquants)")

    print("\n=== Migration terminee! ===")

    # Summary
    with engine.connect() as conn:
        ing_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_ingredients")).fetchone()[0]
        plat_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_plats")).fetchone()[0]
        comp_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_plat_ingredients")).fetchone()[0]

        print(f"\nResume:")
        print(f"  - Ingredients: {ing_count}")
        print(f"  - Plats: {plat_count}")
        print(f"  - Compositions: {comp_count}")


if __name__ == '__main__':
    main()
