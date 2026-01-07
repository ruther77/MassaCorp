#!/usr/bin/env python3
"""
Script de migration des produits epicerie depuis monprojet vers MassaCorp.
Source: /monprojet/db/epicerie_backup_20251030_141910_2000-articles.sql
Target: dwh.metro_produit_agregat dans MassaCorp

Usage:
    docker exec -i massacorp_api python scripts/migrate_epicerie_from_monprojet.py
"""
import os
import sys
import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

# Add app to path for database access
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# Category mapping from monprojet (type_cat) to MassaCorp (categorie_id)
CATEGORY_MAPPING = {
    'Epicerie sucree': 91,  # AUTRE - default, will be refined
    'Epicerie salee': 91,   # AUTRE - default
    'Alcool': 13,           # ALC_SPIRIT
    'Autre': 91,            # AUTRE
    'Afrique': 73,          # MONDE_AFRIQUE
    'Boissons': 2,          # BOIS_SODA - default for non-alcoholic
    'Hygiene': 81,          # HYG_CORPS
}

# Refined category detection based on product name
def detect_category(nom: str, old_category: str) -> tuple[int, str, str]:
    """
    Detect the best MassaCorp category based on product name.
    Returns: (categorie_id, famille, categorie)
    """
    nom_lower = nom.lower()

    # Alcoholic beverages
    if any(kw in nom_lower for kw in ['whisky', 'whiskey', 'vodka', 'gin', 'rhum', 'rum', 'cognac', 'brandy', 'liqueur', 'aperol', 'martini', 'baileys']):
        return (13, 'Boissons', 'Alcools')  # Spiritueux
    if any(kw in nom_lower for kw in ['vin ', 'vin.', 'bordeaux', 'bourgogne', 'chablis', 'medoc', 'saint-emilion', 'champagne', 'chateau', 'ch.']):
        if any(kw in nom_lower for kw in ['blanc', 'blc', 'chardonnay', 'sauvignon']):
            return (11, 'Boissons', 'Alcools')  # Vins blancs
        elif any(kw in nom_lower for kw in ['rose', 'rosé']):
            return (12, 'Boissons', 'Alcools')  # Vins rosés
        return (10, 'Boissons', 'Alcools')  # Vins rouges
    if any(kw in nom_lower for kw in ['biere', 'bière', 'lager', 'stout', 'ale', 'heineken', 'kronenbourg', 'leffe', '1664']):
        return (9, 'Boissons', 'Alcools')  # Bières
    if any(kw in nom_lower for kw in ['porto', 'muscat', 'pineau', 'vermouth']):
        return (14, 'Boissons', 'Alcools')  # Apéritifs

    # Non-alcoholic beverages
    if any(kw in nom_lower for kw in ['coca', 'pepsi', 'fanta', 'sprite', '7up', 'orangina', 'oasis', 'limonade', 'schweppes']):
        return (2, 'Boissons', 'Sans Alcool')  # Sodas
    if any(kw in nom_lower for kw in ['jus', 'nectar', 'tropicana', 'minute maid']):
        return (3, 'Boissons', 'Sans Alcool')  # Jus
    if any(kw in nom_lower for kw in ['evian', 'vittel', 'volvic', 'perrier', 'badoit', 'eau ']):
        return (1, 'Boissons', 'Sans Alcool')  # Eaux
    if any(kw in nom_lower for kw in ['red bull', 'monster', 'energy', 'redbull']):
        return (5, 'Boissons', 'Sans Alcool')  # Energy drinks
    if any(kw in nom_lower for kw in ['sirop']):
        return (4, 'Boissons', 'Sans Alcool')  # Sirops
    if any(kw in nom_lower for kw in ['café', 'cafe', 'nescafe', 'expresso', 'cappuccino', 'dolce gusto']):
        return (6, 'Boissons', 'Chaudes')  # Cafés
    if any(kw in nom_lower for kw in ['thé', 'the ', 'infusion', 'tisane', 'lipton']):
        return (7, 'Boissons', 'Chaudes')  # Thés

    # Dairy products
    if any(kw in nom_lower for kw in ['lait', 'milk']):
        return (16, 'Produits Laitiers', 'Laits')
    if any(kw in nom_lower for kw in ['creme', 'crème']):
        return (17, 'Produits Laitiers', 'Crèmes')
    if any(kw in nom_lower for kw in ['beurre', 'butter']):
        return (18, 'Produits Laitiers', 'Beurres')
    if any(kw in nom_lower for kw in ['fromage', 'emmental', 'gruyere', 'camembert', 'brie', 'roquefort', 'mozzarella', 'parmesan']):
        return (19, 'Produits Laitiers', 'Fromages')
    if any(kw in nom_lower for kw in ['yaourt', 'yogourt', 'yop', 'danone', 'skyr']):
        return (20, 'Produits Laitiers', 'Yaourts')

    # Sweets
    if any(kw in nom_lower for kw in ['chocolat', 'choco', 'm&m', 'maltesers', 'kinder', 'nutella', 'mars', 'snickers', 'twix', 'bounty']):
        return (42, 'Épicerie Sucrée', 'Confiseries')
    if any(kw in nom_lower for kw in ['bonbon', 'haribo', 'carambar', 'mentos']):
        return (43, 'Épicerie Sucrée', 'Confiseries')
    if any(kw in nom_lower for kw in ['biscuit', 'cookie', 'oreo', 'prince', 'bn ', 'petit beurre', 'sable']):
        return (39, 'Épicerie Sucrée', 'Biscuits & Gâteaux')
    if any(kw in nom_lower for kw in ['gateau', 'gâteau', 'madel', 'brownie', 'muffin']):
        return (40, 'Épicerie Sucrée', 'Biscuits & Gâteaux')
    if any(kw in nom_lower for kw in ['croissant', 'pain au choc', 'brioche', 'viennois']):
        return (41, 'Épicerie Sucrée', 'Biscuits & Gâteaux')
    if any(kw in nom_lower for kw in ['sucre', 'sugar']):
        return (38, 'Épicerie Sucrée', 'Petit-déjeuner')
    if any(kw in nom_lower for kw in ['confiture', 'miel', 'marmelade', 'pate a tartiner']):
        return (37, 'Épicerie Sucrée', 'Petit-déjeuner')
    if any(kw in nom_lower for kw in ['cereale', 'muesli', 'corn flakes', 'special k']):
        return (36, 'Épicerie Sucrée', 'Petit-déjeuner')
    if any(kw in nom_lower for kw in ['farine', 'flour']):
        return (44, 'Épicerie Sucrée', 'Pâtisserie')
    if any(kw in nom_lower for kw in ['levure', 'baking']):
        return (45, 'Épicerie Sucrée', 'Pâtisserie')
    if any(kw in nom_lower for kw in ['nappage', 'decoration', 'topping']):
        return (47, 'Épicerie Sucrée', 'Pâtisserie')

    # Savory
    if any(kw in nom_lower for kw in ['pate', 'spaghetti', 'macaroni', 'tagliatelle', 'fusilli', 'penne', 'lasagne']):
        return (22, 'Épicerie Salée', 'Féculents')
    if any(kw in nom_lower for kw in ['riz', 'rice']):
        return (23, 'Épicerie Salée', 'Féculents')
    if any(kw in nom_lower for kw in ['semoule', 'couscous']):
        return (24, 'Épicerie Salée', 'Féculents')
    if any(kw in nom_lower for kw in ['lentille', 'pois', 'haricot sec', 'feve']):
        return (25, 'Épicerie Salée', 'Féculents')
    if any(kw in nom_lower for kw in ['conserve', 'legume', 'petit pois', 'mais', 'haricot vert', 'tomate pelee']):
        return (26, 'Épicerie Salée', 'Conserves')
    if any(kw in nom_lower for kw in ['thon', 'sardine', 'maquereau', 'saumon']):
        return (27, 'Épicerie Salée', 'Conserves')
    if any(kw in nom_lower for kw in ['sauce', 'ketchup', 'mayo', 'moutarde', 'vinaigrette']):
        return (32, 'Épicerie Salée', 'Condiments')
    if any(kw in nom_lower for kw in ['huile', 'oil']):
        return (30, 'Épicerie Salée', 'Condiments')
    if any(kw in nom_lower for kw in ['vinaigre', 'vinegar']):
        return (31, 'Épicerie Salée', 'Condiments')
    if any(kw in nom_lower for kw in ['epice', 'épice', 'poivre', 'curry', 'paprika', 'cumin', 'herbe', 'aromate']):
        return (33, 'Épicerie Salée', 'Condiments')
    if any(kw in nom_lower for kw in ['sel ', 'sel.']):
        return (35, 'Épicerie Salée', 'Condiments')
    if any(kw in nom_lower for kw in ['bouillon', 'fond', 'cube maggi']):
        return (34, 'Épicerie Salée', 'Condiments')

    # Snacking
    if any(kw in nom_lower for kw in ['chips', 'lay', 'pringles']):
        return (78, 'Snacking', 'Chips')
    if any(kw in nom_lower for kw in ['cacahuete', 'noix', 'amande', 'pistache', 'fruit sec']):
        return (79, 'Snacking', 'Fruits secs')
    if any(kw in nom_lower for kw in ['biscuit apero', 'cracker', 'bretzel', 'gressin', 'tuc']):
        return (80, 'Snacking', 'Biscuits apéro')

    # Hygiene
    if any(kw in nom_lower for kw in ['savon', 'gel douche', 'shampoo', 'deodorant', 'dentifrice']):
        return (81, 'Hygiène', 'Corps')
    if any(kw in nom_lower for kw in ['papier', 'sopalin', 'essuie', 'mouchoir', 'toilette']):
        return (82, 'Hygiène', 'Papier')

    # Cleaning
    if any(kw in nom_lower for kw in ['lessive', 'assouplissant', 'detergent']):
        return (83, 'Entretien', 'Lessive')
    if any(kw in nom_lower for kw in ['nettoyant', 'javel', 'desinfectant', 'ajax', 'cif']):
        return (84, 'Entretien', 'Nettoyants')
    if any(kw in nom_lower for kw in ['liquide vaisselle', 'tablette', 'lave vaisselle']):
        return (85, 'Entretien', 'Vaisselle')

    # Pro consumables
    if any(kw in nom_lower for kw in ['barq', 'barquette', 'plat alu', 'emball', 'sachet', 'sac ', 'boite']):
        return (86, 'Consommables Pro', 'Emballages')
    if any(kw in nom_lower for kw in ['paille', 'gobelet', 'gob ', 'assiette jetable', 'couvert jetable', 'serviette']):
        return (87, 'Consommables Pro', 'Jetables')
    if any(kw in nom_lower for kw in ['film', 'papier alu', 'cellophane']):
        return (88, 'Consommables Pro', 'Films')
    if any(kw in nom_lower for kw in ['gant', 'charlotte', 'tablier']):
        return (89, 'Consommables Pro', 'Protection')
    if any(kw in nom_lower for kw in ['etiquette', 'marqueur']):
        return (90, 'Consommables Pro', 'Étiquettes')

    # World products
    if any(kw in nom_lower for kw in ['afrique', 'africain', 'plantain', 'manioc', 'fufu', 'gombo', 'attiéké']):
        return (73, 'Produits du Monde', 'Afrique')
    if any(kw in nom_lower for kw in ['asie', 'asiatique', 'soja', 'noodle', 'wok', 'sriracha', 'nuoc mam']):
        return (74, 'Produits du Monde', 'Asie')
    if any(kw in nom_lower for kw in ['halal']):
        return (77, 'Produits du Monde', 'Halal')

    # Fresh products
    if any(kw in nom_lower for kw in ['boeuf', 'bœuf', 'steak', 'viande hachee', 'entrecote']):
        return (48, 'Produits Frais', 'Viandes')
    if any(kw in nom_lower for kw in ['poulet', 'dinde', 'volaille']):
        return (49, 'Produits Frais', 'Viandes')
    if any(kw in nom_lower for kw in ['porc', 'jambon', 'saucisse', 'lardon', 'bacon']):
        return (50, 'Produits Frais', 'Viandes')
    if any(kw in nom_lower for kw in ['agneau', 'veau']):
        return (51, 'Produits Frais', 'Viandes')
    if any(kw in nom_lower for kw in ['oeuf', 'œuf']):
        return (59, 'Produits Frais', 'Œufs')

    # Fruits & vegetables
    if any(kw in nom_lower for kw in ['pomme', 'banane', 'orange', 'citron', 'raisin', 'fraise', 'fruit frais']):
        return (69, 'Fruits & Légumes', 'Fruits')
    if any(kw in nom_lower for kw in ['carotte', 'tomate fraiche', 'oignon', 'courgette', 'aubergine', 'legume frais']):
        return (70, 'Fruits & Légumes', 'Légumes')
    if any(kw in nom_lower for kw in ['salade', 'laitue', 'iceberg', 'mache', 'roquette']):
        return (72, 'Fruits & Légumes', 'Salades')

    # Frozen
    if any(kw in nom_lower for kw in ['glace', 'sorbet', 'ice cream', 'magnum', 'haagen']):
        return (65, 'Surgelés', 'Glaces')
    if any(kw in nom_lower for kw in ['surgele', 'surgelé', 'frozen']):
        return (61, 'Surgelés', 'Légumes')  # Default frozen

    # Bakery
    if any(kw in nom_lower for kw in ['pain ', 'baguette', 'pain de mie']):
        return (66, 'Boulangerie', 'Pains')
    if any(kw in nom_lower for kw in ['burger', 'mini burger', 'hamburger']):
        return (66, 'Boulangerie', 'Pains')

    # Default based on old category
    default_mapping = {
        'Epicerie sucree': (91, 'Divers', 'Non classé'),
        'Epicerie salee': (91, 'Divers', 'Non classé'),
        'Alcool': (13, 'Boissons', 'Alcools'),
        'Autre': (91, 'Divers', 'Non classé'),
        'Afrique': (73, 'Produits du Monde', 'Afrique'),
        'Boissons': (2, 'Boissons', 'Sans Alcool'),
        'Hygiene': (81, 'Hygiène', 'Corps'),
    }

    return default_mapping.get(old_category, (91, 'Divers', 'Non classé'))


def parse_sql_backup(sql_file: str) -> tuple[list, list]:
    """
    Parse the SQL backup file and extract products and barcodes.
    Returns: (products, barcodes)
    """
    products = []
    barcodes = []

    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract products data
    # Format: id, nom, categorie, prix_achat, prix_vente, tva, seuil_alerte, actif, stock_actuel, created_at, updated_at
    products_match = re.search(
        r'COPY public\.produits \([^)]+\) FROM stdin;\n(.*?)\n\\.',
        content,
        re.DOTALL
    )

    if products_match:
        for line in products_match.group(1).strip().split('\n'):
            if not line or line.startswith('--'):
                continue
            parts = line.split('\t')
            if len(parts) >= 11:
                try:
                    products.append({
                        'id': int(parts[0]),
                        'nom': parts[1],
                        'categorie': parts[2] if parts[2] != '\\N' else 'Autre',
                        'prix_achat': Decimal(parts[3]) if parts[3] != '\\N' else Decimal('0'),
                        'prix_vente': Decimal(parts[4]) if parts[4] != '\\N' else Decimal('0'),
                        'tva': Decimal(parts[5]) if parts[5] != '\\N' else Decimal('20'),
                        'seuil_alerte': Decimal(parts[6]) if parts[6] != '\\N' else Decimal('0'),
                        'actif': parts[7] == 't',
                        'stock_actuel': Decimal(parts[8]) if parts[8] != '\\N' else Decimal('0'),
                    })
                except (ValueError, IndexError) as e:
                    print(f"Warning: Could not parse product line: {line[:50]}... Error: {e}")

    # Extract barcodes data
    # Format: id, produit_id, code, symbologie, pays_iso2, is_principal, created_at
    barcodes_match = re.search(
        r'COPY public\.produits_barcodes \([^)]+\) FROM stdin;\n(.*?)\n\\.',
        content,
        re.DOTALL
    )

    if barcodes_match:
        for line in barcodes_match.group(1).strip().split('\n'):
            if not line or line.startswith('--'):
                continue
            parts = line.split('\t')
            if len(parts) >= 6:
                try:
                    barcodes.append({
                        'id': int(parts[0]),
                        'produit_id': int(parts[1]),
                        'code': parts[2],
                        'symbologie': parts[3] if parts[3] != '\\N' else None,
                        'pays_iso2': parts[4] if parts[4] != '\\N' else None,
                        'is_principal': parts[5] == 't',
                    })
                except (ValueError, IndexError) as e:
                    print(f"Warning: Could not parse barcode line: {line[:50]}... Error: {e}")

    return products, barcodes


def migrate_products(engine, products: list, barcodes: list, tenant_id: int = 1):
    """
    Migrate products to MassaCorp metro_produit_agregat table.
    """
    # Build barcode lookup: produit_id -> list of barcodes
    barcode_lookup = {}
    for bc in barcodes:
        pid = bc['produit_id']
        if pid not in barcode_lookup:
            barcode_lookup[pid] = []
        barcode_lookup[pid].append(bc)

    with engine.connect() as conn:
        # Check existing products to avoid duplicates
        existing = conn.execute(text(
            "SELECT ean FROM dwh.metro_produit_agregat WHERE tenant_id = :tenant_id"
        ), {'tenant_id': tenant_id})
        existing_eans = {row[0] for row in existing}

        inserted = 0
        skipped = 0

        for product in products:
            # Get primary barcode or first barcode
            product_barcodes = barcode_lookup.get(product['id'], [])

            # Skip products that start with $ (these seem to be orphan barcodes)
            if product['nom'].startswith('$'):
                skipped += 1
                continue

            ean = None
            if product_barcodes:
                # Prefer principal barcode
                for bc in product_barcodes:
                    if bc['is_principal']:
                        ean = bc['code']
                        break
                if not ean:
                    ean = product_barcodes[0]['code']
            else:
                # Generate a synthetic EAN for products without barcodes
                ean = f"INT{product['id']:010d}"

            # Skip if already exists
            if ean in existing_eans:
                skipped += 1
                continue

            # Detect category
            cat_id, famille, categorie = detect_category(product['nom'], product['categorie'])

            # Insert into metro_produit_agregat
            try:
                conn.execute(text("""
                    INSERT INTO dwh.metro_produit_agregat (
                        tenant_id, ean, designation,
                        colisage_moyen, unite,
                        quantite_colis_totale, quantite_unitaire_totale,
                        montant_total_ht, montant_total_tva, montant_total, nb_achats,
                        prix_unitaire_moyen, prix_unitaire_min, prix_unitaire_max, prix_colis_moyen,
                        taux_tva, categorie_id, famille, categorie,
                        calcule_le
                    ) VALUES (
                        :tenant_id, :ean, :designation,
                        1, 'U',
                        :stock, :stock,
                        :montant_ht, :montant_tva, :montant_ttc, 1,
                        :prix, :prix, :prix, :prix,
                        :taux_tva, :cat_id, :famille, :categorie,
                        NOW()
                    )
                """), {
                    'tenant_id': tenant_id,
                    'ean': ean,
                    'designation': product['nom'][:255],
                    'stock': float(product['stock_actuel']),
                    'montant_ht': float(product['prix_vente'] * product['stock_actuel']),
                    'montant_tva': float(product['prix_vente'] * product['stock_actuel'] * product['tva'] / 100),
                    'montant_ttc': float(product['prix_vente'] * product['stock_actuel'] * (1 + product['tva'] / 100)),
                    'prix': float(product['prix_vente']),
                    'taux_tva': float(product['tva']),
                    'cat_id': cat_id,
                    'famille': famille,
                    'categorie': categorie,
                })
                existing_eans.add(ean)
                inserted += 1
            except Exception as e:
                print(f"Error inserting product {product['id']} ({ean}): {e}")
                skipped += 1

        conn.commit()

    return inserted, skipped


def main():
    # Database connection
    database_url = os.getenv('DATABASE_URL', 'postgresql://massa:O31xU-XOZw5ZGfyWNfn46qTI0ZdzPZNg@db:5432/MassaCorp')
    engine = create_engine(database_url)

    # SQL backup file path
    sql_file = '/home/ruuuzer/Documents/monprojet/db/epicerie_backup_20251030_141910_2000-articles.sql'

    # Check if file exists (for local testing, mount the file or copy it)
    if not os.path.exists(sql_file):
        # Try alternate path for Docker
        sql_file = '/data/epicerie_backup.sql'
        if not os.path.exists(sql_file):
            print(f"Error: SQL backup file not found at {sql_file}")
            print("Please copy the file to /data/epicerie_backup.sql or adjust the path")
            sys.exit(1)

    print(f"Parsing SQL backup: {sql_file}")
    products, barcodes = parse_sql_backup(sql_file)

    print(f"Found {len(products)} products and {len(barcodes)} barcodes")

    print("Migrating products to MassaCorp...")
    inserted, skipped = migrate_products(engine, products, barcodes, tenant_id=1)

    print(f"\nMigration complete!")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (duplicates or invalid): {skipped}")


if __name__ == '__main__':
    main()
