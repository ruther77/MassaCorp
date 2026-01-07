"""
Repository pour FinanceBankStatement, FinanceBankStatementLine et FinanceReconciliation.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import desc

from app.models.finance.bank_statement import (
    FinanceBankStatement,
    FinanceBankStatementLine,
    FinanceReconciliation,
    FinanceReconciliationStatus,
)
from app.repositories.base import TenantAwareBaseRepository, BaseRepository, PaginatedResult


class FinanceBankStatementRepository(TenantAwareBaseRepository[FinanceBankStatement]):
    """
    Repository pour les releves bancaires.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceBankStatement

    def get_by_account(
        self,
        account_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceBankStatement]:
        """Recupere les releves d'un compte avec pagination."""
        query = (
            self._tenant_query()
            .filter(FinanceBankStatement.account_id == account_id)
            .order_by(desc(FinanceBankStatement.period_start))
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_period(
        self,
        account_id: int,
        start_date: date,
        end_date: date
    ) -> List[FinanceBankStatement]:
        """Recupere les releves sur une periode."""
        return (
            self._tenant_query()
            .filter(
                FinanceBankStatement.account_id == account_id,
                FinanceBankStatement.period_start >= start_date,
                FinanceBankStatement.period_end <= end_date
            )
            .order_by(desc(FinanceBankStatement.period_start))
            .all()
        )

    def check_duplicate(self, file_hash: str) -> bool:
        """Verifie si un releve existe deja (par hash)."""
        return (
            self._tenant_query()
            .filter(FinanceBankStatement.file_hash == file_hash)
            .first()
        ) is not None

    def get_by_hash(self, file_hash: str) -> Optional[FinanceBankStatement]:
        """Recupere un releve par hash."""
        return (
            self._tenant_query()
            .filter(FinanceBankStatement.file_hash == file_hash)
            .first()
        )

    def update_stats(
        self,
        statement_id: int,
        lines_imported: int,
        lines_matched: int
    ) -> bool:
        """Met a jour les statistiques d'un releve."""
        statement = self.get(statement_id)
        if statement:
            statement.lines_imported = lines_imported
            statement.lines_matched = lines_matched
            self.session.flush()
            return True
        return False


class FinanceBankStatementLineRepository(BaseRepository[FinanceBankStatementLine]):
    """
    Repository pour les lignes de releves.
    Pas de TenantMixin car lie a un releve qui a deja l'isolation.
    """
    model = FinanceBankStatementLine

    def get_by_statement(
        self,
        statement_id: int
    ) -> List[FinanceBankStatementLine]:
        """Recupere toutes les lignes d'un releve."""
        return (
            self.session.query(FinanceBankStatementLine)
            .filter(FinanceBankStatementLine.statement_id == statement_id)
            .order_by(FinanceBankStatementLine.date_operation)
            .all()
        )

    def get_unmatched(self, statement_id: int) -> List[FinanceBankStatementLine]:
        """Recupere les lignes non rapprochees."""
        return (
            self.session.query(FinanceBankStatementLine)
            .filter(
                FinanceBankStatementLine.statement_id == statement_id,
                FinanceBankStatementLine.is_matched == False
            )
            .order_by(FinanceBankStatementLine.date_operation)
            .all()
        )

    def get_by_checksum(self, checksum: str) -> Optional[FinanceBankStatementLine]:
        """Recupere une ligne par checksum."""
        return (
            self.session.query(FinanceBankStatementLine)
            .filter(FinanceBankStatementLine.checksum == checksum)
            .first()
        )

    def check_duplicate(self, checksum: str) -> bool:
        """Verifie si une ligne existe deja (par checksum)."""
        return self.get_by_checksum(checksum) is not None

    def mark_matched(self, line_id: int) -> bool:
        """Marque une ligne comme rapprochee."""
        line = self.get(line_id)
        if line:
            line.is_matched = True
            self.session.flush()
            return True
        return False


class FinanceReconciliationRepository(BaseRepository[FinanceReconciliation]):
    """
    Repository pour les rapprochements.
    Pas de TenantMixin car lie a des entites qui ont deja l'isolation.
    """
    model = FinanceReconciliation

    def get_by_statement_line(
        self,
        statement_line_id: int
    ) -> List[FinanceReconciliation]:
        """Recupere les rapprochements d'une ligne de releve."""
        return (
            self.session.query(FinanceReconciliation)
            .filter(FinanceReconciliation.statement_line_id == statement_line_id)
            .all()
        )

    def get_by_transaction(
        self,
        transaction_id: int
    ) -> List[FinanceReconciliation]:
        """Recupere les rapprochements d'une transaction."""
        return (
            self.session.query(FinanceReconciliation)
            .filter(FinanceReconciliation.transaction_id == transaction_id)
            .all()
        )

    def get_valid_by_statement_line(
        self,
        statement_line_id: int
    ) -> Optional[FinanceReconciliation]:
        """Recupere le rapprochement valide d'une ligne."""
        return (
            self.session.query(FinanceReconciliation)
            .filter(
                FinanceReconciliation.statement_line_id == statement_line_id,
                FinanceReconciliation.status != FinanceReconciliationStatus.REJECTED
            )
            .first()
        )

    def check_exists(
        self,
        statement_line_id: int,
        transaction_id: int
    ) -> bool:
        """Verifie si un rapprochement existe deja."""
        return (
            self.session.query(FinanceReconciliation)
            .filter(
                FinanceReconciliation.statement_line_id == statement_line_id,
                FinanceReconciliation.transaction_id == transaction_id
            )
            .first()
        ) is not None

    def create_match(
        self,
        statement_line_id: int,
        transaction_id: int,
        status: FinanceReconciliationStatus = FinanceReconciliationStatus.MANUAL,
        confidence: int = 100,
        notes: Optional[str] = None
    ) -> FinanceReconciliation:
        """Cree un nouveau rapprochement."""
        return self.create({
            "statement_line_id": statement_line_id,
            "transaction_id": transaction_id,
            "status": status,
            "confidence": confidence,
            "notes": notes,
        })

    def reject(self, reconciliation_id: int) -> bool:
        """Rejette un rapprochement."""
        reconciliation = self.get(reconciliation_id)
        if reconciliation:
            reconciliation.status = FinanceReconciliationStatus.REJECTED
            self.session.flush()
            return True
        return False

    def get_auto_matches(
        self,
        min_confidence: int = 80
    ) -> List[FinanceReconciliation]:
        """Recupere les rapprochements automatiques avec confiance elevee."""
        return (
            self.session.query(FinanceReconciliation)
            .filter(
                FinanceReconciliation.status == FinanceReconciliationStatus.AUTO,
                FinanceReconciliation.confidence >= min_confidence
            )
            .all()
        )
