#!/usr/bin/env python3
"""
Script pour scinder les PDFs multi-factures TAIYAT en factures individuelles.

Usage:
    python split_taiyat_pdf.py <input_pdf> <output_dir>
    python split_taiyat_pdf.py --all  # Traite tous les PDFs TAIYAT
"""

import re
import sys
import logging
from pathlib import Path
from typing import List, Dict, Tuple

try:
    import pdfplumber
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("Installation des dependances...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber", "pypdf"])
    import pdfplumber
    from pypdf import PdfReader, PdfWriter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def detect_invoices(pdf_path: Path) -> List[Dict]:
    """
    Detecte toutes les factures dans un PDF multi-pages.

    Returns:
        Liste de dicts avec: facture_num, date, client, start_page, end_page
    """
    invoices = []

    # Detecter le client depuis le nom de fichier
    filename = pdf_path.name.upper()
    if 'NOUTAM' in filename:
        client = 'NOUTAM'
    elif 'INCONTOURNABLE' in filename:
        client = 'INCONTOURNABLE'
    else:
        client = 'INCONNU'

    logger.info(f"Analyse de {pdf_path.name} (client: {client})")

    with pdfplumber.open(pdf_path) as pdf:
        current_invoice = None

        for page_idx, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            # Chercher numero de facture
            facture_match = re.search(r'FACTURE\s*N[°o]?\s*(\d+)', text, re.IGNORECASE)
            page_match = re.search(r'Page\s*(\d+)\s*/\s*(\d+)', text)
            date_match = re.search(r':\s*(\d{2}/\d{2}/\d{4})', text)

            if facture_match and page_match:
                facture_num = facture_match.group(1)
                page_num = int(page_match.group(1))
                total_pages = int(page_match.group(2))

                if page_num == 1:
                    # Nouvelle facture
                    if current_invoice:
                        invoices.append(current_invoice)

                    current_invoice = {
                        'facture_num': facture_num,
                        'date': date_match.group(1) if date_match else None,
                        'client': client,
                        'start_page': page_idx,
                        'end_page': page_idx + total_pages - 1,
                        'total_pages': total_pages
                    }

        # Ajouter la derniere facture
        if current_invoice:
            invoices.append(current_invoice)

    logger.info(f"  -> {len(invoices)} factures detectees")
    return invoices


def split_pdf(pdf_path: Path, invoices: List[Dict], output_dir: Path) -> List[Path]:
    """
    Scinde un PDF en factures individuelles.

    Returns:
        Liste des chemins des PDFs generes
    """
    reader = PdfReader(pdf_path)
    output_files = []

    for inv in invoices:
        writer = PdfWriter()

        # Extraire les pages de cette facture
        for page_idx in range(inv['start_page'], inv['end_page'] + 1):
            if page_idx < len(reader.pages):
                writer.add_page(reader.pages[page_idx])

        # Generer nom de fichier
        date_str = inv['date'].replace('/', '') if inv['date'] else 'nodate'
        filename = f"TAIYAT_{inv['client']}_{inv['facture_num']}_{date_str}.pdf"
        output_path = output_dir / filename

        with open(output_path, 'wb') as f:
            writer.write(f)

        output_files.append(output_path)
        logger.debug(f"  Cree: {filename}")

    return output_files


def process_pdf(pdf_path: Path, output_dir: Path) -> Tuple[int, int]:
    """
    Traite un PDF complet.

    Returns:
        Tuple (nb_factures, nb_pages)
    """
    invoices = detect_invoices(pdf_path)
    if not invoices:
        logger.warning(f"Aucune facture trouvee dans {pdf_path.name}")
        return 0, 0

    output_files = split_pdf(pdf_path, invoices, output_dir)
    total_pages = sum(inv['total_pages'] for inv in invoices)

    logger.info(f"  -> {len(output_files)} fichiers PDF crees ({total_pages} pages)")
    return len(output_files), total_pages


def process_all_taiyat():
    """Traite tous les PDFs TAIYAT."""
    base_dir = Path(__file__).parent.parent.parent
    input_dir = base_dir / "docs" / "TAIYAT"
    output_dir = input_dir / "factures_individuelles"
    output_dir.mkdir(exist_ok=True)

    # Trouver les PDFs de factures (pas la liste des tarifs)
    pdf_files = [
        f for f in input_dir.glob("*.pdf")
        if 'factures' in f.name.lower() and f.is_file()
    ]

    if not pdf_files:
        logger.error("Aucun PDF de factures trouve")
        return

    total_invoices = 0
    total_pages = 0

    for pdf_path in pdf_files:
        nb_inv, nb_pages = process_pdf(pdf_path, output_dir)
        total_invoices += nb_inv
        total_pages += nb_pages

    logger.info("=" * 60)
    logger.info("RAPPORT DE DECOUPAGE")
    logger.info("=" * 60)
    logger.info(f"PDFs traites:        {len(pdf_files)}")
    logger.info(f"Factures extraites:  {total_invoices}")
    logger.info(f"Pages totales:       {total_pages}")
    logger.info(f"Dossier sortie:      {output_dir}")


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--all':
        process_all_taiyat()
    elif len(sys.argv) == 3:
        pdf_path = Path(sys.argv[1])
        output_dir = Path(sys.argv[2])
        output_dir.mkdir(exist_ok=True)
        process_pdf(pdf_path, output_dir)
    else:
        print(__doc__)
        sys.exit(1)
