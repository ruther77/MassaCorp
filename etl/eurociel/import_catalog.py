#!/usr/bin/env python3
"""
Import catalogue EUROCIEL dans la base de données
"""
import json
import sys
from pathlib import Path
from decimal import Decimal

# Ajouter le répertoire parent au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os


def get_db_url():
    """Récupère l'URL de la base de données."""
    return os.getenv(
        'DATABASE_URL',
        'postgresql://massacorp_user:massacorp_secret@localhost:5432/massacorp_db'
    )


def import_catalog(json_path: str, tenant_id: int = 1):
    """Importe le catalogue depuis le fichier JSON."""
    # Charger le JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    produits = data['produits']
    print(f"Chargement de {len(produits)} produits du catalogue...")

    # Connexion DB
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Vider la table existante pour ce tenant
        session.execute(text(f"DELETE FROM dwh.eurociel_catalogue_produit WHERE tenant_id = {tenant_id}"))
        print(f"Table vidée pour tenant_id={tenant_id}")

        # Insérer les produits (avec upsert pour gérer les doublons)
        inserted = 0
        for p in produits:
            session.execute(text("""
                INSERT INTO dwh.eurociel_catalogue_produit (
                    tenant_id, reference, designation, designation_clean,
                    categorie, sous_categorie, taille, conditionnement,
                    poids_kg, origine, page_source, actif
                ) VALUES (
                    :tenant_id, :reference, :designation, :designation_clean,
                    :categorie, :sous_categorie, :taille, :conditionnement,
                    :poids_kg, :origine, :page_source, true
                )
                ON CONFLICT (tenant_id, reference) DO UPDATE SET
                    designation = EXCLUDED.designation,
                    designation_clean = EXCLUDED.designation_clean,
                    categorie = EXCLUDED.categorie,
                    taille = EXCLUDED.taille,
                    conditionnement = EXCLUDED.conditionnement,
                    poids_kg = EXCLUDED.poids_kg,
                    origine = EXCLUDED.origine,
                    updated_at = now()
            """), {
                'tenant_id': tenant_id,
                'reference': p['reference'],
                'designation': p['designation'],
                'designation_clean': p['designation'].upper().strip(),
                'categorie': p['categorie'],
                'sous_categorie': p.get('sous_categorie'),
                'taille': p.get('taille'),
                'conditionnement': p.get('conditionnement'),
                'poids_kg': Decimal(str(p['poids_kg'])) if p.get('poids_kg') else None,
                'origine': p.get('origine'),
                'page_source': p.get('page_source'),
            })
            inserted += 1

        session.commit()
        print(f"\n{inserted} produits importés avec succès!")

        # Stats par catégorie
        result = session.execute(text("""
            SELECT categorie, COUNT(*) as nb
            FROM dwh.eurociel_catalogue_produit
            WHERE tenant_id = :tenant_id
            GROUP BY categorie
            ORDER BY nb DESC
        """), {'tenant_id': tenant_id})

        print("\nPar catégorie:")
        for row in result:
            print(f"  {row[0]}: {row[1]} produits")

        # Total
        result = session.execute(text("""
            SELECT COUNT(*) FROM dwh.eurociel_catalogue_produit WHERE tenant_id = :tenant_id
        """), {'tenant_id': tenant_id})
        total = result.scalar()
        print(f"\nTotal catalogue: {total} références")

    except Exception as e:
        session.rollback()
        print(f"Erreur: {e}")
        raise
    finally:
        session.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import catalogue EUROCIEL')
    parser.add_argument('json', nargs='?', default='output/eurociel_catalogue.json',
                        help='Fichier JSON à importer')
    parser.add_argument('--tenant', '-t', type=int, default=1,
                        help='Tenant ID')

    args = parser.parse_args()

    json_path = Path(args.json)
    if not json_path.exists():
        print(f"Erreur: fichier non trouvé: {json_path}")
        return 1

    import_catalog(str(json_path), args.tenant)
    return 0


if __name__ == '__main__':
    exit(main())
