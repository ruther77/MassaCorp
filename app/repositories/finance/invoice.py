"""
Repository pour FinanceInvoice, FinanceInvoiceLine et FinancePayment.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import desc

from app.models.finance.invoice import (
    FinanceInvoice,
    FinanceInvoiceLine,
    FinancePayment,
    FinanceInvoiceStatus,
)
from app.repositories.base import TenantAwareBaseRepository, BaseRepository, PaginatedResult


class FinanceInvoiceRepository(TenantAwareBaseRepository[FinanceInvoice]):
    """
    Repository pour les factures fournisseurs.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceInvoice

    def get_by_entity(
        self,
        entity_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceInvoice]:
        """Recupere les factures d'une entite avec pagination."""
        query = (
            self._tenant_query()
            .filter(FinanceInvoice.entity_id == entity_id)
            .order_by(desc(FinanceInvoice.date_invoice))
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_vendor(
        self,
        vendor_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceInvoice]:
        """Recupere les factures d'un fournisseur avec pagination."""
        query = (
            self._tenant_query()
            .filter(FinanceInvoice.vendor_id == vendor_id)
            .order_by(desc(FinanceInvoice.date_invoice))
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_status(
        self,
        entity_id: int,
        status: FinanceInvoiceStatus
    ) -> List[FinanceInvoice]:
        """Recupere les factures par statut."""
        return (
            self._tenant_query()
            .filter(
                FinanceInvoice.entity_id == entity_id,
                FinanceInvoice.status == status
            )
            .order_by(desc(FinanceInvoice.date_invoice))
            .all()
        )

    def get_pending(self, entity_id: int) -> List[FinanceInvoice]:
        """Recupere les factures en attente de paiement."""
        return self.get_by_status(entity_id, FinanceInvoiceStatus.EN_ATTENTE)

    def get_overdue(self, entity_id: int) -> List[FinanceInvoice]:
        """Recupere les factures en retard."""
        today = date.today()
        return (
            self._tenant_query()
            .filter(
                FinanceInvoice.entity_id == entity_id,
                FinanceInvoice.status.in_([
                    FinanceInvoiceStatus.EN_ATTENTE,
                    FinanceInvoiceStatus.PARTIELLE
                ]),
                FinanceInvoice.date_due < today
            )
            .order_by(FinanceInvoice.date_due)
            .all()
        )

    def get_by_number(
        self,
        entity_id: int,
        vendor_id: int,
        invoice_number: str
    ) -> Optional[FinanceInvoice]:
        """Recupere une facture par numero."""
        return (
            self._tenant_query()
            .filter(
                FinanceInvoice.entity_id == entity_id,
                FinanceInvoice.vendor_id == vendor_id,
                FinanceInvoice.invoice_number == invoice_number
            )
            .first()
        )

    def check_duplicate(
        self,
        entity_id: int,
        vendor_id: int,
        invoice_number: str
    ) -> bool:
        """Verifie si une facture existe deja."""
        return self.get_by_number(entity_id, vendor_id, invoice_number) is not None

    def update_status(self, invoice_id: int, status: FinanceInvoiceStatus) -> bool:
        """Met a jour le statut d'une facture."""
        invoice = self.get(invoice_id)
        if invoice:
            invoice.status = status
            self.session.flush()
            return True
        return False


class FinanceInvoiceLineRepository(BaseRepository[FinanceInvoiceLine]):
    """
    Repository pour les lignes de factures.
    Pas de TenantMixin car lie a une facture qui a deja l'isolation.
    """
    model = FinanceInvoiceLine

    def get_by_invoice(self, invoice_id: int) -> List[FinanceInvoiceLine]:
        """Recupere toutes les lignes d'une facture."""
        return (
            self.session.query(FinanceInvoiceLine)
            .filter(FinanceInvoiceLine.invoice_id == invoice_id)
            .all()
        )

    def get_by_category(
        self,
        category_id: int,
        limit: int = 100
    ) -> List[FinanceInvoiceLine]:
        """Recupere les lignes par categorie."""
        return (
            self.session.query(FinanceInvoiceLine)
            .filter(FinanceInvoiceLine.category_id == category_id)
            .limit(limit)
            .all()
        )

    def delete_by_invoice(self, invoice_id: int) -> int:
        """Supprime toutes les lignes d'une facture."""
        count = (
            self.session.query(FinanceInvoiceLine)
            .filter(FinanceInvoiceLine.invoice_id == invoice_id)
            .delete()
        )
        self.session.flush()
        return count


class FinancePaymentRepository(BaseRepository[FinancePayment]):
    """
    Repository pour les paiements.
    Pas de TenantMixin car lie a une facture qui a deja l'isolation.
    """
    model = FinancePayment

    def get_by_invoice(self, invoice_id: int) -> List[FinancePayment]:
        """Recupere tous les paiements d'une facture."""
        return (
            self.session.query(FinancePayment)
            .filter(FinancePayment.invoice_id == invoice_id)
            .order_by(FinancePayment.date_payment)
            .all()
        )

    def get_by_transaction(self, transaction_id: int) -> Optional[FinancePayment]:
        """Recupere le paiement lie a une transaction."""
        return (
            self.session.query(FinancePayment)
            .filter(FinancePayment.transaction_id == transaction_id)
            .first()
        )

    def get_total_by_invoice(self, invoice_id: int) -> int:
        """Calcule le total des paiements d'une facture."""
        from sqlalchemy import func
        result = (
            self.session.query(func.sum(FinancePayment.amount))
            .filter(FinancePayment.invoice_id == invoice_id)
            .scalar()
        )
        return result or 0
