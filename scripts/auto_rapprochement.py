#!/usr/bin/env python3
"""
Script de rapprochement automatique ingredients restaurant <-> produits fournisseurs.
Lie les ingredients aux produits METRO, TAIYAT, EUROCIEL correspondants.
"""
import os
import sys
import json
import re
from decimal import Decimal
from difflib import SequenceMatcher

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://massacorp:massacorp_secret@localhost:5432/massacorp_db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def normalize_name(name: str) -> str:
    """Normalise un nom pour comparaison."""
    name = name.upper().strip()
    # Remove common packaging info
    name = re.sub(r'\d+X\d+[A-Z]*', '', name)
    name = re.sub(r'\d+[KGML]+', '', name)
    name = re.sub(r'\d+CL', '', name)
    name = re.sub(r'\d+D', '', name)  # Degree alcohol
    name = re.sub(r'VP|BT|PET', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def similarity(a: str, b: str) -> float:
    """Calcule la similarite entre deux chaines."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def extract_unit_quantity(designation: str) -> tuple:
    """Extrait la quantite et unite d'une designation produit."""
    # Patterns: 24X500G, 10X1KG, 33CL, 75CL, 1L, 5KG, etc.
    designation = designation.upper()

    # Colisage type 24X500G
    match = re.search(r'(\d+)X(\d+(?:\.\d+)?)(KG|G|L|ML|CL)', designation)
    if match:
        count = int(match.group(1))
        qty = float(match.group(2))
        unit = match.group(3)
        # Convert to kg or L
        if unit == 'G':
            return count * qty / 1000, 'KG'
        elif unit == 'ML':
            return count * qty / 1000, 'L'
        elif unit == 'CL':
            return count * qty / 100, 'L'
        else:
            return count * qty, unit

    # Simple unit: 75CL, 1L, 5KG
    match = re.search(r'(\d+(?:\.\d+)?)(KG|G|L|ML|CL)', designation)
    if match:
        qty = float(match.group(1))
        unit = match.group(2)
        if unit == 'G':
            return qty / 1000, 'KG'
        elif unit == 'ML':
            return qty / 1000, 'L'
        elif unit == 'CL':
            return qty / 100, 'L'
        else:
            return qty, unit

    return 1, 'U'


def calculate_ratio(ingredient_unit: str, produit_designation: str) -> float:
    """Calcule le ratio de conversion."""
    qty, prod_unit = extract_unit_quantity(produit_designation)

    # Si ingredient en KG et produit en KG
    if ingredient_unit == 'KG' and prod_unit == 'KG':
        return qty  # ratio = quantite totale en kg

    # Si ingredient en L et produit en L
    if ingredient_unit == 'L' and prod_unit == 'L':
        return qty

    # Si ingredient en U (unite)
    if ingredient_unit == 'U':
        return 1.0  # 1 produit = 1 unite

    # Default
    return 1.0


def get_ingredients(session) -> list:
    """Recupere tous les ingredients restaurant."""
    result = session.execute(text("""
        SELECT id, name, unit, category, prix_unitaire
        FROM restaurant_ingredients
        WHERE tenant_id = 1 AND is_active = true
        ORDER BY name
    """))
    return [dict(row._mapping) for row in result]


def get_existing_links(session) -> set:
    """Recupere les liens existants."""
    result = session.execute(text("""
        SELECT ingredient_id, produit_id, fournisseur
        FROM restaurant_epicerie_links
        WHERE tenant_id = 1
    """))
    return {(row.ingredient_id, row.produit_id, row.fournisseur) for row in result}


def search_metro_products(session, search_term: str) -> list:
    """Recherche produits METRO."""
    result = session.execute(text("""
        SELECT id, designation, prix_unitaire_moyen as prix,
               categorie, famille, unite
        FROM dwh.metro_produit_agregat
        WHERE tenant_id = 1
          AND UPPER(designation) LIKE :search
        ORDER BY designation
        LIMIT 50
    """), {"search": f"%{search_term.upper()}%"})
    return [dict(row._mapping) for row in result]


def search_taiyat_products(session, search_term: str) -> list:
    """Recherche produits TAIYAT."""
    result = session.execute(text("""
        SELECT id, designation_brute as designation, prix_moyen_ht as prix,
               famille, categorie
        FROM dwh.taiyat_produit_agregat
        WHERE tenant_id = 1
          AND UPPER(designation_brute) LIKE :search
        ORDER BY designation_brute
        LIMIT 50
    """), {"search": f"%{search_term.upper()}%"})
    return [dict(row._mapping) for row in result]


def search_eurociel_products(session, search_term: str) -> list:
    """Recherche produits EUROCIEL."""
    result = session.execute(text("""
        SELECT id, designation_brute as designation, prix_moyen as prix,
               famille, categorie
        FROM dwh.eurociel_produit_agregat
        WHERE tenant_id = 1
          AND UPPER(designation_brute) LIKE :search
        ORDER BY designation_brute
        LIMIT 50
    """), {"search": f"%{search_term.upper()}%"})
    return [dict(row._mapping) for row in result]


def create_link(session, ingredient_id: int, produit_id: int, fournisseur: str,
                ratio: float, is_primary: bool = False) -> bool:
    """Cree un lien ingredient-produit."""
    try:
        session.execute(text("""
            INSERT INTO restaurant_epicerie_links
            (tenant_id, ingredient_id, produit_id, fournisseur, ratio, is_primary)
            VALUES (1, :ing_id, :prod_id, :fournisseur, :ratio, :is_primary)
        """), {
            "ing_id": ingredient_id,
            "prod_id": produit_id,
            "fournisseur": fournisseur,
            "ratio": ratio,
            "is_primary": is_primary
        })
        return True
    except Exception as e:
        print(f"  Erreur creation lien: {e}")
        return False


def find_best_matches(ingredient: dict, metro_products: list, taiyat_products: list,
                      eurociel_products: list, threshold: float = 0.5) -> list:
    """Trouve les meilleurs matches pour un ingredient."""
    matches = []
    ing_name = ingredient['name']

    # Recherche METRO
    for prod in metro_products:
        score = similarity(ing_name, prod['designation'])
        if score >= threshold:
            matches.append({
                'fournisseur': 'METRO',
                'produit_id': prod['id'],
                'designation': prod['designation'],
                'prix': prod['prix'],
                'score': score,
                'ratio': calculate_ratio(ingredient['unit'], prod['designation'])
            })

    # Recherche TAIYAT
    for prod in taiyat_products:
        score = similarity(ing_name, prod['designation'])
        if score >= threshold:
            matches.append({
                'fournisseur': 'TAIYAT',
                'produit_id': prod['id'],
                'designation': prod['designation'],
                'prix': prod['prix'],
                'score': score,
                'ratio': calculate_ratio(ingredient['unit'], prod['designation'])
            })

    # Recherche EUROCIEL
    for prod in eurociel_products:
        score = similarity(ing_name, prod['designation'])
        if score >= threshold:
            matches.append({
                'fournisseur': 'EUROCIEL',
                'produit_id': prod['id'],
                'designation': prod['designation'],
                'prix': prod['prix'],
                'score': score,
                'ratio': calculate_ratio(ingredient['unit'], prod['designation'])
            })

    # Trier par score
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def main():
    session = Session()

    try:
        print("=" * 60)
        print("RAPPROCHEMENT AUTOMATIQUE INGREDIENTS <-> PRODUITS")
        print("=" * 60)

        # Recuperer donnees
        ingredients = get_ingredients(session)
        existing_links = get_existing_links(session)

        print(f"\nIngredients: {len(ingredients)}")
        print(f"Liens existants: {len(existing_links)}")

        # Stats
        created = 0
        skipped = 0
        no_match = 0

        for ing in ingredients:
            ing_id = ing['id']
            ing_name = ing['name']
            ing_unit = ing['unit']

            print(f"\n[{ing_id}] {ing_name} ({ing_unit})")

            # Extraire termes de recherche
            # Pour les boissons, rechercher le nom complet
            # Pour les autres, utiliser les premiers mots
            search_terms = []
            words = ing_name.split()

            # Terme principal
            if len(words) >= 2:
                search_terms.append(' '.join(words[:2]))
            search_terms.append(words[0])

            # Rechercher dans chaque fournisseur
            all_matches = []

            for term in search_terms:
                if len(term) < 3:
                    continue

                metro = search_metro_products(session, term)
                taiyat = search_taiyat_products(session, term)
                eurociel = search_eurociel_products(session, term)

                matches = find_best_matches(ing, metro, taiyat, eurociel, threshold=0.4)
                all_matches.extend(matches)

            # Dedupliquer par (fournisseur, produit_id)
            seen = set()
            unique_matches = []
            for m in all_matches:
                key = (m['fournisseur'], m['produit_id'])
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)

            # Trier par score
            unique_matches.sort(key=lambda x: x['score'], reverse=True)

            if not unique_matches:
                print(f"  -> Aucun match trouve")
                no_match += 1
                continue

            # Creer les liens (max 5 par ingredient)
            links_created = 0
            for i, match in enumerate(unique_matches[:5]):
                key = (ing_id, match['produit_id'], match['fournisseur'])

                if key in existing_links:
                    print(f"  -> Deja lie: {match['fournisseur']} #{match['produit_id']}")
                    skipped += 1
                    continue

                is_primary = (i == 0) and links_created == 0
                ratio = match['ratio']

                if create_link(session, ing_id, match['produit_id'],
                              match['fournisseur'], ratio, is_primary):
                    print(f"  + {match['fournisseur']}: {match['designation'][:50]} "
                          f"(score={match['score']:.2f}, ratio={ratio})")
                    created += 1
                    links_created += 1
                    existing_links.add(key)

        session.commit()

        print("\n" + "=" * 60)
        print(f"RESULTAT:")
        print(f"  - Liens crees: {created}")
        print(f"  - Deja lies: {skipped}")
        print(f"  - Sans match: {no_match}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
