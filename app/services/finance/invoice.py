"""
Service pour la gestion des factures fournisseurs.
"""
import logging
from datetime import date
from typing import List, Optional, Dict, Any

from app.models.finance.invoice import (
    FinanceInvoice,
    FinanceInvoiceLine,
    FinancePayment,
    FinanceInvoiceStatus,
)
from app.repositories.finance.invoice import (
    FinanceInvoiceRepository,
    FinanceInvoiceLineRepository,
    FinancePaymentRepository,
)
from app.repositories.base import PaginatedResult
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class InvoiceNotFoundError(AppException):
    """Facture non trouvee."""
    status_code = 404
    error_code = "INVOICE_NOT_FOUND"

    def __init__(self, invoice_id: int):
        super().__init__(message=f"Facture {invoice_id} non trouvee")
        self.invoice_id = invoice_id


class DuplicateInvoiceError(AppException):
    """Facture deja existante."""
    status_code = 409
    error_code = "DUPLICATE_INVOICE"

    def __init__(self, invoice_number: str, vendor_name: str):
        super().__init__(
            message=f"La facture {invoice_number} existe deja pour {vendor_name}"
        )


class InvalidPaymentError(AppException):
    """Paiement invalide."""
    status_code = 400
    error_code = "INVALID_PAYMENT"


class FinanceInvoiceService:
    """
    Service de gestion des factures fournisseurs.
    """

    def __init__(
        self,
        invoice_repository: FinanceInvoiceRepository,
        line_repository: FinanceInvoiceLineRepository,
        payment_repository: FinancePaymentRepository,
    ):
        self.invoice_repository = invoice_repository
        self.line_repository = line_repository
        self.payment_repository = payment_repository

    def create_invoice(
        self,
        entity_id: int,
        vendor_id: int,
        invoice_number: str,
        date_invoice: date,
        date_due: date,
        montant_ht: int,
        montant_tva: int,
        montant_ttc: int,
        date_received: Optional[date] = None,
        file_name: Optional[str] = None,
        file_hash: Optional[str] = None,
        notes: Optional[str] = None,
        lines: Optional[List[Dict[str, Any]]] = None,
    ) -> FinanceInvoice:
        """
        Cree une nouvelle facture.

        Raises:
            DuplicateInvoiceError: Si la facture existe deja
        """
        # Verifier doublon
        if self.invoice_repository.check_duplicate(entity_id, vendor_id, invoice_number):
            raise DuplicateInvoiceError(invoice_number, str(vendor_id))

        invoice = self.invoice_repository.create({
            "entity_id": entity_id,
            "vendor_id": vendor_id,
            "invoice_number": invoice_number,
            "date_invoice": date_invoice,
            "date_due": date_due,
            "date_received": date_received,
            "montant_ht": montant_ht,
            "montant_tva": montant_tva,
            "montant_ttc": montant_ttc,
            "status": FinanceInvoiceStatus.EN_ATTENTE,
            "file_name": file_name,
            "file_hash": file_hash,
            "notes": notes,
        })

        # Creer les lignes
        if lines:
            for line_data in lines:
                self.line_repository.create({
                    "invoice_id": invoice.id,
                    **line_data
                })

        logger.info(f"Facture creee: {invoice.id} - {invoice_number}")
        return invoice

    def get_invoice(self, invoice_id: int) -> FinanceInvoice:
        """
        Recupere une facture par ID.

        Raises:
            InvoiceNotFoundError: Si la facture n'existe pas
        """
        invoice = self.invoice_repository.get(invoice_id)
        if not invoice:
            raise InvoiceNotFoundError(invoice_id)
        return invoice

    def get_invoices_by_entity(
        self,
        entity_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceInvoice]:
        """Recupere les factures d'une entite avec pagination."""
        return self.invoice_repository.get_by_entity(entity_id, page, page_size)

    def get_invoices_by_vendor(
        self,
        vendor_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceInvoice]:
        """Recupere les factures d'un fournisseur avec pagination."""
        return self.invoice_repository.get_by_vendor(vendor_id, page, page_size)

    def get_pending_invoices(self, entity_id: int) -> List[FinanceInvoice]:
        """Recupere les factures en attente."""
        return self.invoice_repository.get_pending(entity_id)

    def get_overdue_invoices(self, entity_id: int) -> List[FinanceInvoice]:
        """Recupere les factures en retard."""
        return self.invoice_repository.get_overdue(entity_id)

    def record_payment(
        self,
        invoice_id: int,
        amount: int,
        date_payment: date,
        mode: str = "virement",
        reference: Optional[str] = None,
        transaction_id: Optional[int] = None,
    ) -> FinancePayment:
        """
        Enregistre un paiement sur une facture.

        Args:
            invoice_id: ID de la facture
            amount: Montant en centimes
            date_payment: Date du paiement
            mode: Mode de paiement
            reference: Reference optionnelle
            transaction_id: ID de la transaction liee

        Returns:
            Le paiement cree
        """
        invoice = self.get_invoice(invoice_id)

        if invoice.status == FinanceInvoiceStatus.ANNULEE:
            raise InvalidPaymentError("Impossible de payer une facture annulee")

        if invoice.status == FinanceInvoiceStatus.PAYEE:
            raise InvalidPaymentError("Facture deja entierement payee")

        remaining = invoice.amount_remaining
        if amount > remaining:
            raise InvalidPaymentError(
                f"Montant ({amount/100:.2f}) superieur au reste a payer ({remaining/100:.2f})"
            )

        payment = self.payment_repository.create({
            "invoice_id": invoice_id,
            "amount": amount,
            "date_payment": date_payment,
            "mode": mode,
            "reference": reference,
            "transaction_id": transaction_id,
        })

        # Mettre a jour le statut
        self._update_invoice_status(invoice)

        logger.info(f"Paiement enregistre: {payment.id} - {amount/100:.2f}EUR sur facture {invoice_id}")
        return payment

    def _update_invoice_status(self, invoice: FinanceInvoice) -> None:
        """Met a jour le statut de la facture selon les paiements."""
        total_paid = self.payment_repository.get_total_by_invoice(invoice.id)

        if total_paid >= invoice.montant_ttc:
            invoice.status = FinanceInvoiceStatus.PAYEE
        elif total_paid > 0:
            invoice.status = FinanceInvoiceStatus.PARTIELLE
        else:
            invoice.status = FinanceInvoiceStatus.EN_ATTENTE

        self.invoice_repository.session.flush()

    def cancel_invoice(self, invoice_id: int) -> FinanceInvoice:
        """Annule une facture."""
        invoice = self.get_invoice(invoice_id)

        if invoice.amount_paid > 0:
            raise InvalidPaymentError("Impossible d'annuler une facture avec des paiements")

        invoice.status = FinanceInvoiceStatus.ANNULEE
        self.invoice_repository.session.flush()

        logger.info(f"Facture annulee: {invoice_id}")
        return invoice

    def get_total_pending(self, entity_id: int) -> int:
        """Calcule le total des factures en attente."""
        invoices = self.get_pending_invoices(entity_id)
        return sum(i.amount_remaining for i in invoices)

    def get_total_overdue(self, entity_id: int) -> int:
        """Calcule le total des factures en retard."""
        invoices = self.get_overdue_invoices(entity_id)
        return sum(i.amount_remaining for i in invoices)
