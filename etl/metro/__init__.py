"""
ETL METRO - Pipeline d'extraction des factures fournisseur
==========================================================

Ce module implémente le pipeline ETL complet pour les factures METRO:
    1. Extraction PDF → Staging
    2. Validation & Nettoyage
    3. Transformation → ODS
    4. Historisation → DWH

Conforme à l'architecture SID CIF (Corporate Information Factory).

Usage:
    from etl.metro import MetroPDFExtractor, MetroETLPipeline

    # Extraction seule
    extractor = MetroPDFExtractor()
    factures = extractor.extract_directory('/path/to/pdfs')

    # Pipeline complet
    pipeline = MetroETLPipeline(db_connection='postgresql://...')
    stats = pipeline.run(input_path='/path/to/pdfs')
"""

from .extract_metro_pdf import MetroPDFExtractor, LigneFacture, FactureEntete
from .run_pipeline import MetroETLPipeline

__version__ = '1.0.0'
__all__ = [
    'MetroPDFExtractor',
    'MetroETLPipeline',
    'LigneFacture',
    'FactureEntete',
]
