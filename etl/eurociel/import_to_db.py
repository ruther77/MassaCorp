#!/usr/bin/env python3
"""
Script d'import des factures EUROCIEL vers PostgreSQL

Usage:
    python import_to_db.py --dir <repertoire_pdfs>
    python import_to_db.py --all  # Importe depuis docs/EUROCIEL
    python import_to_db.py --json <output.json>  # Export JSON uniquement
"""

import sys
import json
import logging
from pathlib import Path
from dataclasses import asdict

# Ajouter le chemin racine pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extract_eurociel_pdf import EurocielParser, FactureEurociel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def facture_to_dict(facture: FactureEurociel) -> dict:
    """Convertit une facture en dictionnaire pour l'API."""
    return {
        "numero_facture": facture.numero_facture,
        "type_document": facture.type_document,
        "date_facture": facture.date_facture,
        "client_nom": facture.client_nom,
        "client_code": facture.client_code,
        "client_adresse": facture.client_adresse,
        "client_telephone": facture.client_telephone,
        "total_ht": sum(l.montant_ht or 0 for l in facture.lignes),
        "total_ttc": facture.total_ttc,
        "poids_total": facture.poids_total,
        "quantite_totale": facture.quantite_totale,
        "source_file": facture.source_file,
        "page_source": facture.page_source,
        "lignes": [
            {
                "reference": l.reference,
                "designation": l.designation,
                "quantite": l.quantite,
                "poids": l.poids,
                "prix_unitaire": l.prix_unitaire,
                "montant_ht": l.montant_ht,
                "code_tva": l.code_tva,
                "taux_tva": l.taux_tva,
                "est_promo": l.est_promo,
            }
            for l in facture.lignes
        ]
    }


def export_to_json(factures: list, output_path: Path):
    """Exporte les factures en JSON."""
    data = [facture_to_dict(f) for f in factures]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Exporté {len(data)} factures vers {output_path}")


def import_via_api(factures: list, api_url: str, token: str, tenant_id: int = 1):
    """Importe les factures via l'API."""
    import requests

    data = [facture_to_dict(f) for f in factures]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Tenant-ID": str(tenant_id),
    }

    # Importer par lots de 50
    batch_size = 50
    total_imported = 0
    total_lignes = 0

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        response = requests.post(
            f"{api_url}/api/v1/eurociel/import",
            json=batch,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            total_imported += result.get("factures_importees", 0)
            total_lignes += result.get("lignes_importees", 0)
            logger.info(f"Lot {i // batch_size + 1}: {result}")
        else:
            logger.error(f"Erreur: {response.status_code} - {response.text}")

    logger.info(f"Total importé: {total_imported} factures, {total_lignes} lignes")
    return total_imported


def print_summary(factures: list):
    """Affiche un résumé des factures extraites."""
    print("\n" + "=" * 60)
    print("RÉSUMÉ EXTRACTION EUROCIEL")
    print("=" * 60)

    total_factures = len(factures)
    total_lignes = sum(len(f.lignes) for f in factures)
    total_ht = sum(sum(l.montant_ht or 0 for l in f.lignes) for f in factures)
    total_poids = sum(f.poids_total or 0 for f in factures)

    # Par type
    factures_fa = [f for f in factures if f.type_document == 'FA']
    factures_av = [f for f in factures if f.type_document == 'AV']

    print(f"Factures extraites:   {total_factures}")
    print(f"  - Factures (FA):    {len(factures_fa)}")
    print(f"  - Avoirs (AV):      {len(factures_av)}")
    print(f"Lignes total:         {total_lignes}")
    print(f"Montant HT total:     {total_ht:,.2f} EUR")
    print(f"Poids total:          {total_poids:,.2f} kg")

    # Par client
    print("\n" + "-" * 60)
    print("PAR CLIENT:")
    clients = {}
    for f in factures:
        client = f.client_nom or 'INCONNU'
        if client not in clients:
            clients[client] = {'count': 0, 'lignes': 0, 'montant': 0}
        clients[client]['count'] += 1
        clients[client]['lignes'] += len(f.lignes)
        clients[client]['montant'] += sum(l.montant_ht or 0 for l in f.lignes)

    for client, stats in sorted(clients.items()):
        print(f"  {client}:")
        print(f"    Factures: {stats['count']}")
        print(f"    Lignes:   {stats['lignes']}")
        print(f"    HT:       {stats['montant']:,.2f} EUR")

    # Période
    print("\n" + "-" * 60)
    dates = [f.date_facture for f in factures if f.date_facture]
    if dates:
        print(f"Période: {min(dates)} à {max(dates)}")

    print("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import EUROCIEL vers DB')
    parser.add_argument('--dir', help='Répertoire des PDFs')
    parser.add_argument('--all', action='store_true', help='Importer tout depuis docs/EUROCIEL')
    parser.add_argument('--json', help='Exporter en JSON au lieu d\'importer')
    parser.add_argument('--api-url', default='http://localhost:8000', help='URL de l\'API')
    parser.add_argument('--token', help='Token JWT pour l\'API')
    parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    parser.add_argument('--summary', '-s', action='store_true', help='Afficher résumé')

    args = parser.parse_args()

    # Déterminer le répertoire source
    if args.all:
        base_dir = Path(__file__).parent.parent.parent
        pdf_dir = base_dir / "docs" / "EUROCIEL"
    elif args.dir:
        pdf_dir = Path(args.dir)
    else:
        print("Usage: python import_to_db.py --all")
        print("       python import_to_db.py --dir <répertoire>")
        print("       python import_to_db.py --all --json eurociel_data.json")
        print("       python import_to_db.py --all --token <JWT_TOKEN>")
        sys.exit(1)

    if not pdf_dir.exists():
        logger.error(f"Répertoire non trouvé: {pdf_dir}")
        sys.exit(1)

    # Extraction
    eurociel_parser = EurocielParser(debug=args.debug)
    factures = eurociel_parser.extract_directory(pdf_dir)

    if not factures:
        logger.error("Aucune facture extraite")
        sys.exit(1)

    # Résumé
    if args.summary:
        print_summary(factures)

    # Export JSON ou import API
    if args.json:
        export_to_json(factures, Path(args.json))
    elif args.token:
        import_via_api(factures, args.api_url, args.token)
    else:
        # Export JSON par défaut
        output_path = Path(__file__).parent / "eurociel_data.json"
        export_to_json(factures, output_path)
        print_summary(factures)
        print(f"\nDonnées exportées vers: {output_path}")
        print(f"\nPour importer via API:")
        print(f"  python import_to_db.py --all --token <JWT_TOKEN>")


if __name__ == '__main__':
    main()
