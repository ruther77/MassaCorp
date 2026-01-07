#!/usr/bin/env python3
"""
Script de rapprochement V2 - Gere les cas speciaux avec synonymes.
"""
import os
import sys
import re
from decimal import Decimal
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://massacorp:massacorp_secret@localhost:5432/massacorp_db")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Synonymes et termes de recherche alternatifs
SEARCH_ALIASES = {
    "33 EXPORT 6D 33CL VP": ["33 EXPORT", "EXPORT 33"],
    "Attieke": ["ATTIÉKÉ", "ATIEKE", "MANIOC SEMOULE"],
    "BEAUFORT BIERE 33CL VP": ["BEAUFORT", "BEAUFORT BIERE"],
    "BOOSTER ENERGY DRINK": ["BOOSTER", "ENERGY DRINK"],
    "Brochettes": ["BROCHETTE", "PIQUE BOIS"],
    "CASTEL BIERE 33CL VP": ["CASTEL", "CASTEL BIERE"],
    "Champignons africains": ["CHAMPIGNON", "CHAMPIGNONS"],
    "Château D'arsin": ["ARSIN", "CHATEAU ARSIN"],
    "Château de Giscours": ["GISCOURS", "CHATEAU GISCOURS"],
    "Château des Vignes": ["VIGNES", "CHATEAU VIGNES"],
    "Darkatine": ["DAKATINE", "BEURRE ARACHIDE", "PATE ARACHIDE"],
    "Djansan (njansang)": ["NJANSANG", "DJANSAN", "DJANSANG"],
    "Ecrevisses sechees": ["ECREVISSE", "CREVISSE SECHE"],
    "Feuilles Eru": ["ERU", "FEUILLE ERU", "OKOK"],
    "Feuilles Ndole": ["NDOLE", "FEUILLE NDOLE"],
    "Foufou": ["FUFU", "FOU FOU", "FARINE MANIOC"],
    "Gambas décortiquées": ["GAMBAS", "CREVETTE GEANTE", "GAMBA"],
    "ISENBECK BIERE 33CL VP": ["ISENBECK"],
    "KADJI BEER 33CL VP": ["KADJI"],
    "Maquero": ["MAQUEREAU", "MAQUEREAUX"],
    "MUTZIG BIERE 33CL VP": ["MUTZIG"],
    "Piments antillais": ["PIMENT ANTILL", "PIMENT FORT"],
    "Pistache": ["PISTACHE", "ARACHIDE"],
    "Pistache pilee": ["PISTACHE PILE", "PATE PISTACHE", "ARACHIDE PILE"],
    "PRUNE": ["PRUNE", "PRUNEAUX"],
    "Riz": ["RIZ LONG", "RIZ PARFUME", "RIZ THAI"],
    "Rosé Anjou": ["ROSE ANJOU", "ANJOU ROSE", "VIN ROSE ANJOU"],
    "Sel gemme": ["SEL", "GROS SEL"],
    "Sirène de Giscours": ["SIRENE", "GISCOURS"],
    "Sole": ["SOLE", "POISSON SOLE", "FILET SOLE"],
    "Soya": ["SOJA", "LAIT SOJA", "SOYA"],
    "Waterleaf/Epinards": ["EPINARD", "WATERLEAF", "SPINACH"],
    "WH GLENFIDDICH 15A 40D 70CL": ["GLENFIDDICH", "GLEN FIDDICH"],
    "WH J.DANIEL S 100CL 40D": ["JACK DANIEL", "J DANIEL", "J.DANIEL"],
    "WH J.DANIEL'S 70CL 40D": ["JACK DANIEL", "J DANIEL", "J.DANIEL"],
    "WH JWALKER BLACK 12A 40D 70CL": ["JOHNNIE WALKER", "JWALKER", "J WALKER", "JOHNNY WALKER"],
}


def normalize_name(name: str) -> str:
    """Normalise un nom pour comparaison."""
    name = name.upper().strip()
    name = re.sub(r'\d+X\d+[A-Z]*', '', name)
    name = re.sub(r'\d+[KGML]+', '', name)
    name = re.sub(r'\d+CL', '', name)
    name = re.sub(r'\d+D', '', name)
    name = re.sub(r'VP|BT|PET', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def similarity(a: str, b: str) -> float:
    """Calcule la similarite entre deux chaines."""
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def extract_unit_quantity(designation: str) -> tuple:
    """Extrait la quantite et unite d'une designation produit."""
    designation = designation.upper()

    match = re.search(r'(\d+)X(\d+(?:\.\d+)?)(KG|G|L|ML|CL)', designation)
    if match:
        count = int(match.group(1))
        qty = float(match.group(2))
        unit = match.group(3)
        if unit == 'G':
            return count * qty / 1000, 'KG'
        elif unit == 'ML':
            return count * qty / 1000, 'L'
        elif unit == 'CL':
            return count * qty / 100, 'L'
        else:
            return count * qty, unit

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
    qty, prod_unit = extract_unit_quantity(produit_designation)
    if ingredient_unit == 'KG' and prod_unit == 'KG':
        return qty
    if ingredient_unit == 'L' and prod_unit == 'L':
        return qty
    if ingredient_unit == 'U':
        return 1.0
    return 1.0


def search_all_products(session, search_term: str) -> list:
    """Recherche dans tous les fournisseurs."""
    products = []

    # METRO
    try:
        result = session.execute(text("""
            SELECT id, designation, prix_unitaire_moyen as prix, 'METRO' as fournisseur
            FROM dwh.metro_produit_agregat
            WHERE tenant_id = 1 AND UPPER(designation) LIKE :search
            ORDER BY designation LIMIT 20
        """), {"search": f"%{search_term.upper()}%"})
        products.extend([dict(row._mapping) for row in result])
    except:
        pass

    # TAIYAT
    try:
        result = session.execute(text("""
            SELECT id, designation_brute as designation, prix_moyen_ht as prix, 'TAIYAT' as fournisseur
            FROM dwh.taiyat_produit_agregat
            WHERE tenant_id = 1 AND UPPER(designation_brute) LIKE :search
            ORDER BY designation_brute LIMIT 20
        """), {"search": f"%{search_term.upper()}%"})
        products.extend([dict(row._mapping) for row in result])
    except:
        pass

    # EUROCIEL
    try:
        result = session.execute(text("""
            SELECT id, designation_brute as designation, prix_moyen as prix, 'EUROCIEL' as fournisseur
            FROM dwh.eurociel_produit_agregat
            WHERE tenant_id = 1 AND UPPER(designation_brute) LIKE :search
            ORDER BY designation_brute LIMIT 20
        """), {"search": f"%{search_term.upper()}%"})
        products.extend([dict(row._mapping) for row in result])
    except:
        pass

    return products


def get_unlinked_ingredients(session) -> list:
    """Recupere les ingredients sans liens."""
    result = session.execute(text("""
        SELECT i.id, i.name, i.unit, i.category
        FROM restaurant_ingredients i
        WHERE i.tenant_id = 1 AND i.is_active = true
        AND i.id NOT IN (SELECT DISTINCT ingredient_id FROM restaurant_epicerie_links WHERE tenant_id = 1)
        ORDER BY i.name
    """))
    return [dict(row._mapping) for row in result]


def get_existing_links(session) -> set:
    result = session.execute(text("""
        SELECT ingredient_id, produit_id, fournisseur
        FROM restaurant_epicerie_links WHERE tenant_id = 1
    """))
    return {(row.ingredient_id, row.produit_id, row.fournisseur) for row in result}


def create_link(session, ingredient_id: int, produit_id: int, fournisseur: str,
                ratio: float, is_primary: bool = False) -> bool:
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
        print(f"  Erreur: {e}")
        return False


def main():
    session = Session()

    try:
        print("=" * 60)
        print("RAPPROCHEMENT V2 - CAS SPECIAUX")
        print("=" * 60)

        ingredients = get_unlinked_ingredients(session)
        existing_links = get_existing_links(session)

        print(f"\nIngredients sans liens: {len(ingredients)}")

        created = 0

        for ing in ingredients:
            ing_id = ing['id']
            ing_name = ing['name']
            ing_unit = ing['unit']

            print(f"\n[{ing_id}] {ing_name} ({ing_unit})")

            # Termes de recherche: aliases ou mots du nom
            search_terms = SEARCH_ALIASES.get(ing_name, [])
            if not search_terms:
                words = ing_name.split()
                for w in words:
                    if len(w) >= 3 and w.upper() not in ['THE', 'AND', 'FOR', 'LES', 'DES', 'UNE', 'AVEC']:
                        search_terms.append(w)

            all_matches = []

            for term in search_terms:
                if len(term) < 3:
                    continue

                products = search_all_products(session, term)

                for prod in products:
                    score = similarity(ing_name, prod['designation'])
                    if score >= 0.35:  # Seuil plus bas
                        all_matches.append({
                            'fournisseur': prod['fournisseur'],
                            'produit_id': prod['id'],
                            'designation': prod['designation'],
                            'prix': prod['prix'],
                            'score': score,
                            'ratio': calculate_ratio(ing_unit, prod['designation'])
                        })

            # Dedupliquer
            seen = set()
            unique_matches = []
            for m in all_matches:
                key = (m['fournisseur'], m['produit_id'])
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)

            unique_matches.sort(key=lambda x: x['score'], reverse=True)

            if not unique_matches:
                print(f"  -> Aucun match")
                continue

            links_created = 0
            for i, match in enumerate(unique_matches[:5]):
                key = (ing_id, match['produit_id'], match['fournisseur'])

                if key in existing_links:
                    continue

                is_primary = (i == 0) and links_created == 0

                if create_link(session, ing_id, match['produit_id'],
                              match['fournisseur'], match['ratio'], is_primary):
                    print(f"  + {match['fournisseur']}: {match['designation'][:50]} "
                          f"(score={match['score']:.2f})")
                    created += 1
                    links_created += 1
                    existing_links.add(key)

        session.commit()

        print("\n" + "=" * 60)
        print(f"LIENS CREES: {created}")
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
