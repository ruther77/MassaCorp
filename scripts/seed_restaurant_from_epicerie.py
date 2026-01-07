#!/usr/bin/env python3
"""
Script pour generer des donnees restaurant initiales basees sur les produits epicerie.
Cree des ingredients lies aux produits epicerie et des plats avec compositions.

Usage:
    docker exec -i massacorp_api python scripts/seed_restaurant_from_epicerie.py
"""
import os
import sys
from decimal import Decimal
from typing import Optional, List

sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# Sample ingredients to create, linked to epicerie products by name patterns
INGREDIENT_TEMPLATES = [
    # Viandes
    {'name': 'Boeuf haché', 'unit': 'KG', 'category': 'VIANDE', 'price_per_kg': 1200, 'keywords': ['boeuf', 'viande hach']},
    {'name': 'Poulet', 'unit': 'KG', 'category': 'VIANDE', 'price_per_kg': 800, 'keywords': ['poulet', 'volaille']},
    {'name': 'Bacon', 'unit': 'KG', 'category': 'VIANDE', 'price_per_kg': 1500, 'keywords': ['bacon', 'lardon']},
    {'name': 'Jambon', 'unit': 'KG', 'category': 'VIANDE', 'price_per_kg': 1000, 'keywords': ['jambon']},

    # Produits laitiers
    {'name': 'Crème fraîche', 'unit': 'L', 'category': 'PRODUIT_LAITIER', 'price_per_kg': 400, 'keywords': ['creme', 'crème']},
    {'name': 'Lait', 'unit': 'L', 'category': 'PRODUIT_LAITIER', 'price_per_kg': 120, 'keywords': ['lait']},
    {'name': 'Beurre', 'unit': 'KG', 'category': 'PRODUIT_LAITIER', 'price_per_kg': 1000, 'keywords': ['beurre']},
    {'name': 'Fromage râpé', 'unit': 'KG', 'category': 'PRODUIT_LAITIER', 'price_per_kg': 1200, 'keywords': ['fromage', 'emmental', 'gruyere']},
    {'name': 'Mozzarella', 'unit': 'KG', 'category': 'PRODUIT_LAITIER', 'price_per_kg': 800, 'keywords': ['mozzarella']},

    # Légumes
    {'name': 'Tomates', 'unit': 'KG', 'category': 'LEGUME', 'price_per_kg': 300, 'keywords': ['tomate']},
    {'name': 'Oignons', 'unit': 'KG', 'category': 'LEGUME', 'price_per_kg': 150, 'keywords': ['oignon']},
    {'name': 'Salade', 'unit': 'U', 'category': 'LEGUME', 'price_per_kg': 150, 'keywords': ['salade', 'laitue', 'iceberg']},
    {'name': 'Pommes de terre', 'unit': 'KG', 'category': 'LEGUME', 'price_per_kg': 100, 'keywords': ['pomme de terre', 'patate']},

    # Epicerie
    {'name': 'Pain burger', 'unit': 'U', 'category': 'EPICERIE', 'price_per_kg': 50, 'keywords': ['burger', 'pain']},
    {'name': 'Sauce tomate', 'unit': 'L', 'category': 'CONDIMENT', 'price_per_kg': 200, 'keywords': ['sauce tomate', 'tomate pelee']},
    {'name': 'Huile', 'unit': 'L', 'category': 'CONDIMENT', 'price_per_kg': 500, 'keywords': ['huile']},
    {'name': 'Sel', 'unit': 'KG', 'category': 'CONDIMENT', 'price_per_kg': 50, 'keywords': ['sel']},
    {'name': 'Poivre', 'unit': 'KG', 'category': 'CONDIMENT', 'price_per_kg': 2000, 'keywords': ['poivre']},
    {'name': 'Pâtes', 'unit': 'KG', 'category': 'EPICERIE', 'price_per_kg': 150, 'keywords': ['pate', 'spaghetti', 'penne']},
    {'name': 'Riz', 'unit': 'KG', 'category': 'EPICERIE', 'price_per_kg': 150, 'keywords': ['riz']},
    {'name': 'Frites surgelées', 'unit': 'KG', 'category': 'EPICERIE', 'price_per_kg': 200, 'keywords': ['frites', 'frite']},

    # Boissons pour préparation
    {'name': 'Vin rouge cuisine', 'unit': 'L', 'category': 'BOISSON', 'price_per_kg': 300, 'keywords': ['vin rouge']},
    {'name': 'Bière', 'unit': 'L', 'category': 'BOISSON', 'price_per_kg': 200, 'keywords': ['biere', 'bière']},
]

# Sample plats with their compositions
PLAT_TEMPLATES = [
    {
        'name': 'Burger Maison',
        'category': 'PLAT',
        'prix_vente': 1200,  # 12€
        'ingredients': [
            ('Pain burger', 0.1, 'U'),
            ('Boeuf haché', 0.15, 'KG'),
            ('Fromage râpé', 0.03, 'KG'),
            ('Salade', 0.05, 'U'),
            ('Tomates', 0.05, 'KG'),
            ('Oignons', 0.02, 'KG'),
        ]
    },
    {
        'name': 'Pâtes Carbonara',
        'category': 'PLAT',
        'prix_vente': 1100,  # 11€
        'ingredients': [
            ('Pâtes', 0.15, 'KG'),
            ('Bacon', 0.08, 'KG'),
            ('Crème fraîche', 0.1, 'L'),
            ('Fromage râpé', 0.05, 'KG'),
            ('Poivre', 0.002, 'KG'),
        ]
    },
    {
        'name': 'Salade César',
        'category': 'ENTREE',
        'prix_vente': 900,  # 9€
        'ingredients': [
            ('Salade', 0.2, 'U'),
            ('Poulet', 0.1, 'KG'),
            ('Fromage râpé', 0.03, 'KG'),
            ('Huile', 0.02, 'L'),
        ]
    },
    {
        'name': 'Pizza Margherita',
        'category': 'PLAT',
        'prix_vente': 1000,  # 10€
        'ingredients': [
            ('Sauce tomate', 0.08, 'L'),
            ('Mozzarella', 0.15, 'KG'),
            ('Huile', 0.02, 'L'),
            ('Sel', 0.005, 'KG'),
        ]
    },
    {
        'name': 'Steak Frites',
        'category': 'PLAT',
        'prix_vente': 1500,  # 15€
        'ingredients': [
            ('Boeuf haché', 0.2, 'KG'),
            ('Frites surgelées', 0.2, 'KG'),
            ('Huile', 0.05, 'L'),
            ('Sel', 0.003, 'KG'),
            ('Poivre', 0.001, 'KG'),
        ]
    },
    {
        'name': 'Poulet rôti',
        'category': 'PLAT',
        'prix_vente': 1300,  # 13€
        'ingredients': [
            ('Poulet', 0.25, 'KG'),
            ('Pommes de terre', 0.2, 'KG'),
            ('Huile', 0.03, 'L'),
            ('Sel', 0.005, 'KG'),
        ]
    },
    {
        'name': 'Risotto aux champignons',
        'category': 'PLAT',
        'prix_vente': 1200,  # 12€
        'ingredients': [
            ('Riz', 0.12, 'KG'),
            ('Crème fraîche', 0.1, 'L'),
            ('Beurre', 0.03, 'KG'),
            ('Vin rouge cuisine', 0.05, 'L'),
            ('Fromage râpé', 0.04, 'KG'),
        ]
    },
    {
        'name': 'Club Sandwich',
        'category': 'PLAT',
        'prix_vente': 1000,  # 10€
        'ingredients': [
            ('Pain burger', 0.15, 'U'),
            ('Jambon', 0.08, 'KG'),
            ('Fromage râpé', 0.04, 'KG'),
            ('Salade', 0.1, 'U'),
            ('Tomates', 0.05, 'KG'),
        ]
    },
]


def seed_ingredients(engine, tenant_id: int = 1) -> dict:
    """
    Create restaurant ingredients and return a mapping name -> id.
    """
    ingredient_ids = {}

    with engine.connect() as conn:
        # Check existing ingredients
        existing = conn.execute(text(
            "SELECT name FROM restaurant_ingredients WHERE tenant_id = :tid"
        ), {'tid': tenant_id})
        existing_names = {row[0].lower() for row in existing}

        for template in INGREDIENT_TEMPLATES:
            if template['name'].lower() in existing_names:
                # Get existing ID
                result = conn.execute(text(
                    "SELECT id FROM restaurant_ingredients WHERE tenant_id = :tid AND LOWER(name) = LOWER(:name)"
                ), {'tid': tenant_id, 'name': template['name']})
                row = result.fetchone()
                if row:
                    ingredient_ids[template['name']] = row[0]
                continue

            # Insert new ingredient
            result = conn.execute(text("""
                INSERT INTO restaurant_ingredients (tenant_id, name, unit, category, prix_unitaire, is_active)
                VALUES (:tid, :name, :unit, :category, :price, true)
                RETURNING id
            """), {
                'tid': tenant_id,
                'name': template['name'],
                'unit': template['unit'],
                'category': template['category'],
                'price': template['price_per_kg'],
            })
            ingredient_ids[template['name']] = result.fetchone()[0]

        conn.commit()

    return ingredient_ids


def seed_plats(engine, ingredient_ids: dict, tenant_id: int = 1):
    """
    Create restaurant plats with their compositions.
    """
    with engine.connect() as conn:
        # Check existing plats
        existing = conn.execute(text(
            "SELECT name FROM restaurant_plats WHERE tenant_id = :tid"
        ), {'tid': tenant_id})
        existing_names = {row[0].lower() for row in existing}

        for template in PLAT_TEMPLATES:
            if template['name'].lower() in existing_names:
                print(f"  Skipping plat '{template['name']}' (already exists)")
                continue

            # Insert plat
            result = conn.execute(text("""
                INSERT INTO restaurant_plats (tenant_id, name, category, prix_vente, is_active)
                VALUES (:tid, :name, :category, :price, true)
                RETURNING id
            """), {
                'tid': tenant_id,
                'name': template['name'],
                'category': template['category'],
                'price': template['prix_vente'],
            })
            plat_id = result.fetchone()[0]
            print(f"  Created plat: {template['name']} (id={plat_id})")

            # Insert ingredients composition
            for ing_name, qty, unit in template['ingredients']:
                if ing_name not in ingredient_ids:
                    print(f"    Warning: Ingredient '{ing_name}' not found, skipping")
                    continue

                conn.execute(text("""
                    INSERT INTO restaurant_plat_ingredients (plat_id, ingredient_id, quantite)
                    VALUES (:plat_id, :ing_id, :qty)
                """), {
                    'plat_id': plat_id,
                    'ing_id': ingredient_ids[ing_name],
                    'qty': qty,
                })

        conn.commit()


def link_epicerie_products(engine, ingredient_ids: dict, tenant_id: int = 1):
    """
    Try to link restaurant ingredients to epicerie products based on keywords.
    Uses produit_id to reference metro_produit_agregat.id
    """
    with engine.connect() as conn:
        for template in INGREDIENT_TEMPLATES:
            ing_name = template['name']
            if ing_name not in ingredient_ids:
                continue

            ing_id = ingredient_ids[ing_name]
            keywords = template.get('keywords', [])

            for kw in keywords:
                # Find matching epicerie product
                result = conn.execute(text("""
                    SELECT id, ean, designation, prix_unitaire_moyen
                    FROM dwh.metro_produit_agregat
                    WHERE tenant_id = :tid
                    AND LOWER(designation) LIKE :kw
                    LIMIT 1
                """), {'tid': tenant_id, 'kw': f'%{kw.lower()}%'})

                row = result.fetchone()
                if row:
                    produit_id = row[0]
                    # Check if link already exists
                    existing = conn.execute(text("""
                        SELECT id FROM restaurant_epicerie_links
                        WHERE ingredient_id = :ing_id AND produit_id = :pid
                    """), {'ing_id': ing_id, 'pid': produit_id})

                    if not existing.fetchone():
                        conn.execute(text("""
                            INSERT INTO restaurant_epicerie_links (tenant_id, ingredient_id, produit_id, ratio)
                            VALUES (:tid, :ing_id, :pid, 1.0)
                        """), {'tid': tenant_id, 'ing_id': ing_id, 'pid': produit_id})
                        print(f"  Linked '{ing_name}' to epicerie product: {row[2][:50]}")
                    break

        conn.commit()


def main():
    database_url = os.getenv('DATABASE_URL', 'postgresql://massa:O31xU-XOZw5ZGfyWNfn46qTI0ZdzPZNg@db:5432/MassaCorp')
    engine = create_engine(database_url)

    print("=== Seeding Restaurant Data ===\n")

    print("1. Creating ingredients...")
    ingredient_ids = seed_ingredients(engine, tenant_id=1)
    print(f"   Created/found {len(ingredient_ids)} ingredients\n")

    print("2. Creating plats with compositions...")
    seed_plats(engine, ingredient_ids, tenant_id=1)
    print()

    print("3. Linking ingredients to epicerie products...")
    link_epicerie_products(engine, ingredient_ids, tenant_id=1)
    print()

    print("=== Done! ===")

    # Show summary
    with engine.connect() as conn:
        ing_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_ingredients")).fetchone()[0]
        plat_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_plats")).fetchone()[0]
        comp_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_plat_ingredients")).fetchone()[0]
        link_count = conn.execute(text("SELECT COUNT(*) FROM restaurant_epicerie_links")).fetchone()[0]

        print(f"\nSummary:")
        print(f"  - Ingredients: {ing_count}")
        print(f"  - Plats: {plat_count}")
        print(f"  - Compositions: {comp_count}")
        print(f"  - Epicerie links: {link_count}")


if __name__ == '__main__':
    main()
