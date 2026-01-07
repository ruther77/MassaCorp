"""
Repository pour FinanceTransaction et FinanceTransactionLine.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import desc, and_

from app.models.finance.transaction import (
    FinanceTransaction,
    FinanceTransactionLine,
    FinanceTransactionDirection,
    FinanceTransactionStatus,
)
from app.repositories.base import TenantAwareBaseRepository, BaseRepository, PaginatedResult


class FinanceTransactionRepository(TenantAwareBaseRepository[FinanceTransaction]):
    """
    Repository pour les transactions financieres.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceTransaction

    def get_by_entity(
        self,
        entity_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceTransaction]:
        """Recupere les transactions d'une entite avec pagination."""
        query = (
            self._tenant_query()
            .filter(FinanceTransaction.entity_id == entity_id)
            .order_by(desc(FinanceTransaction.date_operation))
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_account(
        self,
        account_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceTransaction]:
        """Recupere les transactions d'un compte avec pagination."""
        query = (
            self._tenant_query()
            .filter(FinanceTransaction.account_id == account_id)
            .order_by(desc(FinanceTransaction.date_operation))
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_period(
        self,
        entity_id: int,
        start_date: date,
        end_date: date
    ) -> List[FinanceTransaction]:
        """Recupere les transactions sur une periode."""
        return (
            self._tenant_query()
            .filter(
                FinanceTransaction.entity_id == entity_id,
                FinanceTransaction.date_operation >= start_date,
                FinanceTransaction.date_operation <= end_date
            )
            .order_by(desc(FinanceTransaction.date_operation))
            .all()
        )

    def get_uncategorized(self, entity_id: int) -> List[FinanceTransaction]:
        """Recupere les transactions non categorisees."""
        return (
            self._tenant_query()
            .filter(
                FinanceTransaction.entity_id == entity_id,
                ~FinanceTransaction.lines.any()
            )
            .order_by(desc(FinanceTransaction.date_operation))
            .all()
        )

    def get_by_status(
        self,
        entity_id: int,
        status: FinanceTransactionStatus
    ) -> List[FinanceTransaction]:
        """Recupere les transactions par statut."""
        return (
            self._tenant_query()
            .filter(
                FinanceTransaction.entity_id == entity_id,
                FinanceTransaction.status == status
            )
            .order_by(desc(FinanceTransaction.date_operation))
            .all()
        )

    def search(
        self,
        entity_id: int,
        label: Optional[str] = None,
        direction: Optional[FinanceTransactionDirection] = None,
        min_amount: Optional[int] = None,
        max_amount: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceTransaction]:
        """Recherche avancee de transactions."""
        query = (
            self._tenant_query()
            .filter(FinanceTransaction.entity_id == entity_id)
        )

        if label:
            query = query.filter(FinanceTransaction.label.ilike(f"%{label}%"))
        if direction:
            query = query.filter(FinanceTransaction.direction == direction)
        if min_amount is not None:
            query = query.filter(FinanceTransaction.amount >= min_amount)
        if max_amount is not None:
            query = query.filter(FinanceTransaction.amount <= max_amount)
        if start_date:
            query = query.filter(FinanceTransaction.date_operation >= start_date)
        if end_date:
            query = query.filter(FinanceTransaction.date_operation <= end_date)

        query = query.order_by(desc(FinanceTransaction.date_operation))
        return self.paginate(page=page, page_size=page_size, query=query)


class FinanceTransactionLineRepository(BaseRepository[FinanceTransactionLine]):
    """
    Repository pour les lignes de transactions.
    Pas de TenantMixin car lie a une transaction qui a deja l'isolation.
    """
    model = FinanceTransactionLine

    def get_by_transaction(
        self,
        transaction_id: int
    ) -> List[FinanceTransactionLine]:
        """Recupere toutes les lignes d'une transaction."""
        return (
            self.session.query(FinanceTransactionLine)
            .filter(FinanceTransactionLine.transaction_id == transaction_id)
            .all()
        )

    def get_by_category(
        self,
        category_id: int,
        limit: int = 100
    ) -> List[FinanceTransactionLine]:
        """Recupere les lignes par categorie."""
        return (
            self.session.query(FinanceTransactionLine)
            .filter(FinanceTransactionLine.category_id == category_id)
            .limit(limit)
            .all()
        )

    def get_by_cost_center(
        self,
        cost_center_id: int,
        limit: int = 100
    ) -> List[FinanceTransactionLine]:
        """Recupere les lignes par centre de couts."""
        return (
            self.session.query(FinanceTransactionLine)
            .filter(FinanceTransactionLine.cost_center_id == cost_center_id)
            .limit(limit)
            .all()
        )

    def delete_by_transaction(self, transaction_id: int) -> int:
        """Supprime toutes les lignes d'une transaction."""
        count = (
            self.session.query(FinanceTransactionLine)
            .filter(FinanceTransactionLine.transaction_id == transaction_id)
            .delete()
        )
        self.session.flush()
        return count
