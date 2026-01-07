#!/usr/bin/env python3
"""
Export des factures METRO vers JSON pour import dans l'API.
Genere un fichier metro_data.json compatible avec POST /metro/import
"""

import sys
import json
import logging
from pathlib import Path
from dataclasses import asdict
from datetime import datetime

# Setup path - direct import
sys.path.insert(0, str(Path(__file__).parent))

from extract_metro_pdf import MetroParserV2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def export_metro_to_json(input_dir: Path, output_file: Path, with_normalization: bool = True):
    """
    Exporte toutes les factures METRO vers un fichier JSON.

    Args:
        input_dir: Dossier contenant les PDFs METRO
        output_file: Fichier JSON de sortie
        with_normalization: Appliquer la normalisation
    """
    parser = MetroParserV2()

    logger.info(f"Extraction depuis: {input_dir}")

    # Extraire toutes les factures
    factures = parser.extract_directory(input_dir, normalize=with_normalization)

    logger.info(f"Factures extraites: {len(factures)}")

    # Convertir au format JSON attendu par l'API
    export_data = {
        "metadata": {
            "source": "ETL METRO PDF Parser v2.1",
            "extracted_at": datetime.now().isoformat(),
            "input_dir": str(input_dir),
            "nb_factures": len(factures),
            "nb_lignes_total": sum(len(f.lignes) for f in factures),
        },
        "factures": []
    }

    for facture in factures:
        if not facture.numero_facture:
            continue

        facture_json = {
            "numero": facture.numero_facture,
            "numero_interne": facture.numero_interne,
            "date": facture.date_facture or datetime.now().strftime("%Y-%m-%d"),
            "magasin": facture.magasin_nom or "METRO",
            "client_nom": facture.client_nom,
            "client_numero": facture.client_numero,
            "total_ht": facture.total_ht or 0,
            "total_tva": facture.total_tva or 0,
            "total_ttc": facture.total_ttc or 0,
            "fichier_source": facture.source_file,
            "lignes": []
        }

        for ligne in facture.lignes:
            ligne_json = {
                "ean": ligne.ean,
                "article_numero": ligne.article_numero,
                "designation": ligne.designation,
                "colisage": ligne.colisage or 1,
                "quantite": ligne.quantite or 0,
                "prix_unitaire": ligne.prix_unitaire or 0,
                "montant": ligne.montant_ligne or 0,
                "volume_unitaire": ligne.poids_volume,
                "unite": ligne.unite or "U",
                "taux_tva": ligne.taux_tva or 20,
                "code_tva": ligne.code_tva,
                "regie": ligne.regie,
                "vol_alcool": ligne.vol_alcool,
                "categorie_source": ligne.categorie_source,
                "est_promo": ligne.est_promo,
            }
            facture_json["lignes"].append(ligne_json)

        export_data["factures"].append(facture_json)

    # Calculer stats par produit unique (EAN)
    produits_uniques = {}
    for facture in export_data["factures"]:
        for ligne in facture["lignes"]:
            ean = ligne.get("ean")
            if not ean:
                continue
            if ean not in produits_uniques:
                produits_uniques[ean] = {
                    "ean": ean,
                    "designation": ligne["designation"],
                    "nb_achats": 0,
                    "quantite_totale": 0,
                    "montant_total": 0,
                }
            produits_uniques[ean]["nb_achats"] += 1
            produits_uniques[ean]["quantite_totale"] += ligne.get("quantite", 0) or 0
            produits_uniques[ean]["montant_total"] += ligne.get("montant", 0) or 0

    export_data["metadata"]["nb_produits_uniques"] = len(produits_uniques)

    # Sauvegarder
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Export termine: {output_file}")
    logger.info(f"  - Factures: {len(export_data['factures'])}")
    logger.info(f"  - Lignes: {export_data['metadata']['nb_lignes_total']}")
    logger.info(f"  - Produits uniques: {len(produits_uniques)}")

    return export_data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export METRO PDFs vers JSON")
    parser.add_argument("--input", "-i", default="docs/METRO", help="Dossier des PDFs")
    parser.add_argument("--output", "-o", default="metro_data.json", help="Fichier JSON de sortie")
    parser.add_argument("--raw", action="store_true", help="Sans normalisation")

    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_absolute():
        input_dir = Path(__file__).parent.parent.parent / args.input

    output_file = Path(args.output)
    if not output_file.is_absolute():
        output_file = Path(__file__).parent.parent.parent / args.output

    export_metro_to_json(input_dir, output_file, with_normalization=not args.raw)
