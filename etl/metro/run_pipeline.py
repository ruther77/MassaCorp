#!/usr/bin/env python3
"""
ETL METRO - Orchestrateur de Pipeline
======================================
Script principal d'orchestration du pipeline ETL complet.
Conforme à l'architecture SID CIF (Corporate Information Factory).

Pipeline:
    1. EXTRACTION   : PDF → staging.stg_facture_ligne
    2. NETTOYAGE    : Validation + enrichissement
    3. TRANSFORMATION : Staging → ODS (calculs métier)
    4. HISTORISATION : ODS → DWH (SCD Type 2)
    5. NETTOYAGE    : Purge staging

Usage:
    python run_pipeline.py --input /docs/METRO --db postgresql://...
    python run_pipeline.py --input /docs/METRO --dry-run
    python run_pipeline.py --batch-id abc123 --skip-extraction
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'etl_metro_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger('ETL-METRO')

# Import extraction (même répertoire)
try:
    from extract_metro_pdf import MetroPDFExtractor, export_to_json
except ImportError:
    # Fallback si exécuté depuis un autre répertoire
    sys.path.insert(0, str(Path(__file__).parent))
    from extract_metro_pdf import MetroPDFExtractor, export_to_json

# Import psycopg2 optionnel
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_DB = True
except ImportError:
    HAS_DB = False
    logger.warning("psycopg2 non installé - mode DB désactivé")


class PipelineStep:
    """Décorateur pour les étapes du pipeline."""

    def __init__(self, step_number: int, name: str):
        self.step_number = step_number
        self.name = name

    def __call__(self, func):
        def wrapper(pipeline, *args, **kwargs):
            pipeline.log_step_start(self.step_number, self.name)
            try:
                result = func(pipeline, *args, **kwargs)
                pipeline.log_step_end(self.step_number, self.name, 'SUCCESS', result)
                return result
            except Exception as e:
                pipeline.log_step_end(self.step_number, self.name, 'ERROR', error=str(e))
                raise
        return wrapper


class MetroETLPipeline:
    """
    Pipeline ETL complet pour les factures METRO.

    Étapes:
        1. Extraction PDF → Staging
        2. Nettoyage & Validation
        3. Enrichissement colonnes manquantes
        4. Transformation → ODS
        5. Chargement → DWH
        6. Nettoyage staging
    """

    def __init__(
        self,
        db_connection: str = None,
        batch_id: str = None,
        dry_run: bool = False
    ):
        self.db_connection = db_connection
        self.batch_id = batch_id or str(uuid.uuid4())
        self.dry_run = dry_run
        self.conn = None
        self.execution_id = None
        self.stats = {
            'fichiers_traites': 0,
            'lignes_extraites': 0,
            'lignes_validees': 0,
            'lignes_erreur': 0,
            'lignes_ods': 0,
            'lignes_dwh': 0,
            'montant_ht': 0,
            'nb_factures': 0,
        }

        logger.info(f"Pipeline initialisé - Batch: {self.batch_id}")

    def connect(self):
        """Connexion à la base de données."""
        if not HAS_DB:
            logger.warning("Mode sans DB - utilisation export JSON uniquement")
            return False

        if not self.db_connection:
            logger.warning("Pas de connection string - mode sans DB")
            return False

        try:
            self.conn = psycopg2.connect(self.db_connection)
            logger.info("Connexion DB établie")
            return True
        except Exception as e:
            logger.error(f"Erreur connexion DB: {e}")
            return False

    def disconnect(self):
        """Déconnexion de la base de données."""
        if self.conn:
            self.conn.close()
            logger.info("Connexion DB fermée")

    def log_step_start(self, step_number: int, name: str):
        """Log le début d'une étape."""
        logger.info(f"[{step_number}] {name} - DÉBUT")

    def log_step_end(self, step_number: int, name: str, status: str, result: Any = None, error: str = None):
        """Log la fin d'une étape."""
        if status == 'SUCCESS':
            logger.info(f"[{step_number}] {name} - {status} ({result})")
        else:
            logger.error(f"[{step_number}] {name} - {status}: {error}")

        # Log en DB si connecté
        if self.conn and self.execution_id:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT etl.log_step(%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.execution_id,
                        step_number,
                        name,
                        status,
                        result.get('rows', 0) if isinstance(result, dict) else 0,
                        error,
                        json.dumps(result) if result else None
                    ))
                self.conn.commit()
            except Exception as e:
                logger.warning(f"Erreur log step DB: {e}")

    def execute_sql(self, sql: str, params: tuple = None) -> Optional[list]:
        """Exécute une requête SQL."""
        if not self.conn:
            logger.warning("Pas de connexion DB - SQL ignoré")
            return None

        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                if cur.description:
                    return cur.fetchall()
                return []
        except Exception as e:
            logger.error(f"Erreur SQL: {e}")
            raise

    def call_function(self, func_name: str, params: tuple = None) -> Any:
        """Appelle une fonction SQL."""
        if not self.conn:
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {func_name}(%s)", params or (self.batch_id,))
                if cur.description:
                    return cur.fetchall()
                return None
        except Exception as e:
            logger.error(f"Erreur appel {func_name}: {e}")
            raise

    # =========================================================================
    # ÉTAPES DU PIPELINE
    # =========================================================================

    @PipelineStep(1, "EXTRACTION")
    def step_extraction(self, input_path: Path) -> Dict:
        """Étape 1: Extraction des PDFs METRO."""
        extractor = MetroPDFExtractor(batch_id=self.batch_id)
        factures = extractor.extract_directory(input_path)

        self.stats['fichiers_traites'] = extractor.stats['fichiers_traites']
        self.stats['lignes_extraites'] = extractor.stats['lignes_extraites']
        self.stats['nb_factures'] = len(factures)

        # Export JSON (backup)
        output_json = Path(f"staging_metro_{self.batch_id[:8]}.json")
        export_to_json(factures, output_json)
        logger.info(f"Export JSON: {output_json}")

        # Insert en DB si connecté
        if self.conn:
            self._insert_staging(factures)

        return {
            'fichiers': extractor.stats['fichiers_traites'],
            'factures': len(factures),
            'lignes': extractor.stats['lignes_extraites'],
            'rows': extractor.stats['lignes_extraites']
        }

    def _insert_staging(self, factures):
        """Insère les factures extraites dans staging."""
        with self.conn.cursor() as cur:
            for facture in factures:
                for ligne in facture.lignes:
                    cur.execute("""
                        INSERT INTO staging.stg_facture_ligne (
                            batch_id, source_file, numero_facture, numero_interne,
                            date_facture, fournisseur_nom, fournisseur_siret,
                            magasin_nom, client_nom, client_numero,
                            ligne_numero, ean, article_numero, designation,
                            categorie_source, regie, vol_alcool, poids_volume,
                            unite, prix_unitaire, quantite, montant_ligne,
                            code_tva, taux_tva, est_promo, raw_line
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        ligne.batch_id, ligne.source_file, ligne.numero_facture,
                        ligne.numero_interne, ligne.date_facture, ligne.fournisseur_nom,
                        ligne.fournisseur_siret, ligne.magasin_nom, ligne.client_nom,
                        ligne.client_numero, ligne.ligne_numero, ligne.ean,
                        ligne.article_numero, ligne.designation, ligne.categorie_source,
                        ligne.regie, ligne.vol_alcool, ligne.poids_volume,
                        ligne.unite, ligne.prix_unitaire, ligne.quantite,
                        ligne.montant_ligne, ligne.code_tva, ligne.taux_tva,
                        ligne.est_promo, ligne.raw_line
                    ))
            self.conn.commit()
            logger.info(f"Staging: {self.stats['lignes_extraites']} lignes insérées")

    @PipelineStep(2, "NETTOYAGE")
    def step_nettoyage(self) -> Dict:
        """Étape 2: Nettoyage des données staging."""
        if not self.conn:
            return {'rows': 0, 'message': 'Pas de connexion DB'}

        # Appel fonction nettoyage
        results = self.call_function('staging.nettoyer_facture_lignes', (self.batch_id,))
        logger.info(f"Nettoyage: {results}")

        return {'rows': len(results) if results else 0, 'details': results}

    @PipelineStep(3, "VALIDATION")
    def step_validation(self) -> Dict:
        """Étape 3: Validation des données staging."""
        if not self.conn:
            return {'rows': 0, 'valides': 0, 'erreurs': 0}

        # Appel fonction validation
        results = self.call_function('staging.valider_facture_lignes', (self.batch_id,))

        # Comptage
        valides = sum(1 for r in results if r[1] == 'VALIDE') if results else 0
        erreurs = sum(1 for r in results if r[1] == 'ERREUR') if results else 0

        self.stats['lignes_validees'] = valides
        self.stats['lignes_erreur'] = erreurs

        return {
            'rows': len(results) if results else 0,
            'valides': valides,
            'erreurs': erreurs,
            'taux': f"{100*valides/(valides+erreurs):.1f}%" if (valides+erreurs) > 0 else "N/A"
        }

    @PipelineStep(4, "ENRICHISSEMENT")
    def step_enrichissement(self) -> Dict:
        """Étape 4: Enrichissement des colonnes manquantes."""
        if not self.conn:
            return {'rows': 0}

        results = self.call_function('staging.enrichir_colonnes_manquantes', (self.batch_id,))
        logger.info(f"Enrichissement: {results}")

        return {'rows': sum(r[1] for r in results) if results else 0, 'details': results}

    @PipelineStep(5, "TRANSFORMATION_ODS")
    def step_transformation_ods(self) -> Dict:
        """Étape 5: Transformation Staging → ODS."""
        if not self.conn:
            return {'rows': 0}

        results = self.call_function('staging.transformer_vers_ods', (self.batch_id,))

        if results and len(results) > 0:
            nb_entetes = results[0][0]
            nb_lignes = results[0][1]
            montant = results[0][2]

            self.stats['lignes_ods'] = nb_lignes
            self.stats['montant_ht'] = float(montant) if montant else 0

            return {
                'rows': nb_lignes,
                'entetes': nb_entetes,
                'lignes': nb_lignes,
                'montant_ht': float(montant) if montant else 0
            }

        return {'rows': 0}

    @PipelineStep(6, "CHARGEMENT_DWH")
    def step_chargement_dwh(self) -> Dict:
        """Étape 6: Chargement ODS → DWH."""
        if not self.conn:
            return {'rows': 0}

        # Appel procédure
        with self.conn.cursor() as cur:
            cur.execute("CALL dwh.charger_faits_achats()")
            self.conn.commit()

        # Récupérer stats
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM dwh.fait_achats WHERE source_batch_id = %s
            """, (self.batch_id,))
            count = cur.fetchone()[0]

        self.stats['lignes_dwh'] = count

        return {'rows': count}

    @PipelineStep(7, "GENERATION_ENTETES")
    def step_generation_entetes(self) -> Dict:
        """Étape 7: Génération des en-têtes de factures."""
        if not self.conn:
            return {'rows': 0}

        with self.conn.cursor() as cur:
            cur.execute("SELECT staging.generer_entetes_factures(%s)", (self.batch_id,))
            count = cur.fetchone()[0]
            self.conn.commit()

        return {'rows': count}

    @PipelineStep(8, "CREATION_PRODUITS")
    def step_creation_produits(self) -> Dict:
        """Étape 8: Création des nouveaux produits dans DWH."""
        if not self.conn:
            return {'rows': 0}

        with self.conn.cursor() as cur:
            cur.execute("SELECT dwh.creer_produit_depuis_ods(%s)", (self.batch_id,))
            count = cur.fetchone()[0]
            self.conn.commit()

        return {'rows': count, 'nouveaux_produits': count}

    # =========================================================================
    # EXÉCUTION PRINCIPALE
    # =========================================================================

    def run(
        self,
        input_path: Path,
        skip_extraction: bool = False,
        skip_dwh: bool = False
    ) -> Dict:
        """
        Exécute le pipeline ETL complet.

        Args:
            input_path: Répertoire des PDFs METRO
            skip_extraction: Ignorer l'extraction (utiliser données existantes)
            skip_dwh: Ignorer le chargement DWH

        Returns:
            Statistiques d'exécution
        """
        logger.info("=" * 60)
        logger.info(f"PIPELINE ETL METRO - Batch {self.batch_id}")
        logger.info(f"Input: {input_path}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Connexion DB
        has_db = self.connect()

        # Enregistrer début pipeline
        if has_db:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT etl.start_pipeline(%s, %s, %s, %s)
                    """, (
                        'METRO_FACTURES',
                        self.batch_id,
                        str(input_path),
                        json.dumps({'dry_run': self.dry_run})
                    ))
                    self.execution_id = cur.fetchone()[0]
                    self.conn.commit()
            except Exception as e:
                logger.warning(f"Erreur enregistrement pipeline: {e}")

        try:
            # Étape 1: Extraction
            if not skip_extraction:
                self.step_extraction(input_path)

            if has_db:
                # Étape 2: Nettoyage
                self.step_nettoyage()

                # Étape 3: Validation
                self.step_validation()

                # Étape 4: Enrichissement
                self.step_enrichissement()

                # Étape 5: Transformation ODS
                self.step_transformation_ods()

                # Étape 6: Génération en-têtes
                self.step_generation_entetes()

                if not skip_dwh and not self.dry_run:
                    # Étape 7: Chargement DWH
                    self.step_chargement_dwh()

                    # Étape 8: Création produits
                    self.step_creation_produits()

            # Finaliser pipeline
            if has_db and self.execution_id:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT etl.finish_pipeline(%s, %s)", (self.execution_id, 'SUCCESS'))
                    self.conn.commit()

            status = 'SUCCESS'

        except Exception as e:
            logger.error(f"Erreur pipeline: {e}")
            status = 'ERROR'

            if has_db and self.execution_id:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT etl.finish_pipeline(%s, %s, %s)", (
                        self.execution_id, 'ERROR', str(e)
                    ))
                    self.conn.commit()

            raise

        finally:
            self.disconnect()

        # Résumé
        duration = (datetime.now() - start_time).total_seconds()
        self.stats['duration_seconds'] = duration
        self.stats['status'] = status

        logger.info("=" * 60)
        logger.info("RÉSUMÉ PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Statut: {status}")
        logger.info(f"Durée: {duration:.1f}s")
        logger.info(f"Fichiers traités: {self.stats['fichiers_traites']}")
        logger.info(f"Factures: {self.stats['nb_factures']}")
        logger.info(f"Lignes extraites: {self.stats['lignes_extraites']}")
        logger.info(f"Lignes validées: {self.stats['lignes_validees']}")
        logger.info(f"Lignes en erreur: {self.stats['lignes_erreur']}")
        logger.info(f"Lignes ODS: {self.stats['lignes_ods']}")
        logger.info(f"Lignes DWH: {self.stats['lignes_dwh']}")
        logger.info(f"Montant HT: {self.stats['montant_ht']:.2f}€")
        logger.info("=" * 60)

        return self.stats


def main():
    parser = argparse.ArgumentParser(
        description='Pipeline ETL METRO - Extraction → Staging → ODS → DWH',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python run_pipeline.py --input /docs/METRO
  python run_pipeline.py --input /docs/METRO --db postgresql://user:pass@localhost/db
  python run_pipeline.py --input /docs/METRO --dry-run
  python run_pipeline.py --batch-id abc123 --skip-extraction --db postgresql://...
        """
    )

    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Répertoire contenant les PDFs METRO'
    )
    parser.add_argument(
        '--db',
        help='Connection string PostgreSQL (ex: postgresql://user:pass@localhost/db)'
    )
    parser.add_argument(
        '--batch-id',
        help='ID de batch (généré si non fourni)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Exécution sans modification (pas de chargement DWH)'
    )
    parser.add_argument(
        '--skip-extraction',
        action='store_true',
        help='Ignorer l\'extraction (utiliser données staging existantes)'
    )
    parser.add_argument(
        '--skip-dwh',
        action='store_true',
        help='Ignorer le chargement DWH'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mode verbeux'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Répertoire non trouvé: {input_path}")
        return 1

    # Créer et exécuter le pipeline
    pipeline = MetroETLPipeline(
        db_connection=args.db,
        batch_id=args.batch_id,
        dry_run=args.dry_run
    )

    try:
        stats = pipeline.run(
            input_path=input_path,
            skip_extraction=args.skip_extraction,
            skip_dwh=args.skip_dwh
        )

        # Export stats JSON
        with open(f"etl_stats_{pipeline.batch_id[:8]}.json", 'w') as f:
            json.dump(stats, f, indent=2, default=str)

        return 0 if stats['status'] == 'SUCCESS' else 1

    except Exception as e:
        logger.exception(f"Erreur fatale: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
