#!/usr/bin/env python3
"""
Script d'import des factures TAIYAT vers PostgreSQL

Usage:
    python import_to_db.py --dir <repertoire_pdfs>
    python import_to_db.py --all  # Importe depuis docs/TAIYAT/factures_individuelles
"""

import sys
import json
import logging
from pathlib import Path
from dataclasses import asdict

# Ajouter le chemin racine pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extract_taiyat_pdf import TaiyatParser, FactureTaiyat

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def facture_to_dict(facture: FactureTaiyat) -> dict:
    """Convertit une facture en dictionnaire pour l'API."""
    return {
        "numero_facture": facture.numero_facture,
        "date_facture": facture.date_facture,
        "client_nom": facture.client_nom,
        "client_code": facture.client_code,
        "total_ttc": sum(l.montant_ttc or 0 for l in facture.lignes),
        "source_file": facture.source_file,
        "lignes": [
            {
                "designation": l.designation,
                "provenance": l.provenance,
                "colis": l.colis,
                "pieces": l.pieces,
                "unite": l.unite,
                "prix_unitaire_ht": l.prix_unitaire_ht,
                "prix_unitaire_ttc": l.prix_unitaire_ttc,
                "montant_ttc": l.montant_ttc,
                "code_tva": l.code_tva,
                "taux_tva": l.taux_tva,
                "est_remise": l.est_remise,
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

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        response = requests.post(
            f"{api_url}/api/v1/taiyat/import",
            json=batch,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            total_imported += result.get("factures_importees", 0)
            logger.info(f"Lot {i // batch_size + 1}: {result}")
        else:
            logger.error(f"Erreur: {response.status_code} - {response.text}")

    logger.info(f"Total importé: {total_imported} factures")
    return total_imported


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import TAIYAT vers DB')
    parser.add_argument('--dir', help='Répertoire des PDFs')
    parser.add_argument('--all', action='store_true', help='Importer tout')
    parser.add_argument('--json', help='Exporter en JSON au lieu d\'importer')
    parser.add_argument('--api-url', default='http://localhost:8000', help='URL de l\'API')
    parser.add_argument('--token', help='Token JWT pour l\'API')

    args = parser.parse_args()

    # Déterminer le répertoire source
    if args.all:
        base_dir = Path(__file__).parent.parent.parent
        pdf_dir = base_dir / "docs" / "TAIYAT" / "factures_individuelles"
    elif args.dir:
        pdf_dir = Path(args.dir)
    else:
        print("Usage: python import_to_db.py --all")
        print("       python import_to_db.py --dir <repertoire>")
        sys.exit(1)

    if not pdf_dir.exists():
        logger.error(f"Répertoire non trouvé: {pdf_dir}")
        sys.exit(1)

    # Extraction
    taiyat_parser = TaiyatParser()
    factures = taiyat_parser.extract_directory(pdf_dir)

    if not factures:
        logger.error("Aucune facture extraite")
        sys.exit(1)

    # Export JSON ou import API
    if args.json:
        export_to_json(factures, Path(args.json))
    elif args.token:
        import_via_api(factures, args.api_url, args.token)
    else:
        # Export JSON par défaut
        output_path = Path(__file__).parent / "taiyat_data.json"
        export_to_json(factures, output_path)
        print(f"\nPour importer via API:")
        print(f"  python import_to_db.py --all --token <JWT_TOKEN>")


if __name__ == '__main__':
    main()
