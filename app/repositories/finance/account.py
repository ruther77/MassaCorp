"""
Repository pour FinanceAccount et FinanceAccountBalance.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import desc

from app.models.finance.account import (
    FinanceAccount,
    FinanceAccountBalance,
    FinanceAccountType,
)
from app.repositories.base import TenantAwareBaseRepository, BaseRepository


class FinanceAccountRepository(TenantAwareBaseRepository[FinanceAccount]):
    """
    Repository pour les comptes bancaires.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceAccount

    def get_by_entity(self, entity_id: int) -> List[FinanceAccount]:
        """Recupere tous les comptes d'une entite."""
        return (
            self._tenant_query()
            .filter(FinanceAccount.entity_id == entity_id)
            .order_by(FinanceAccount.label)
            .all()
        )

    def get_active_by_entity(self, entity_id: int) -> List[FinanceAccount]:
        """Recupere les comptes actifs d'une entite."""
        return (
            self._tenant_query()
            .filter(
                FinanceAccount.entity_id == entity_id,
                FinanceAccount.is_active == True
            )
            .order_by(FinanceAccount.label)
            .all()
        )

    def get_by_type(
        self,
        entity_id: int,
        account_type: FinanceAccountType
    ) -> List[FinanceAccount]:
        """Recupere les comptes par type."""
        return (
            self._tenant_query()
            .filter(
                FinanceAccount.entity_id == entity_id,
                FinanceAccount.type == account_type
            )
            .order_by(FinanceAccount.label)
            .all()
        )

    def get_by_iban(self, iban: str) -> Optional[FinanceAccount]:
        """Recupere un compte par IBAN."""
        return (
            self._tenant_query()
            .filter(FinanceAccount.iban == iban)
            .first()
        )

    def get_with_balances(self, account_id: int) -> Optional[FinanceAccount]:
        """Recupere un compte avec son historique de soldes."""
        return self.get(account_id)  # Relations chargees en selectin

    def update_balance(self, account_id: int, new_balance: int) -> bool:
        """Met a jour le solde courant d'un compte."""
        account = self.get(account_id)
        if account:
            account.current_balance = new_balance
            self.session.flush()
            return True
        return False


class FinanceAccountBalanceRepository(BaseRepository[FinanceAccountBalance]):
    """
    Repository pour l'historique des soldes.
    Pas de TenantMixin car lie a un compte qui a deja l'isolation.
    """
    model = FinanceAccountBalance

    def get_by_account(
        self,
        account_id: int,
        limit: int = 30
    ) -> List[FinanceAccountBalance]:
        """Recupere l'historique des soldes d'un compte."""
        return (
            self.session.query(FinanceAccountBalance)
            .filter(FinanceAccountBalance.account_id == account_id)
            .order_by(desc(FinanceAccountBalance.date))
            .limit(limit)
            .all()
        )

    def get_by_date(
        self,
        account_id: int,
        target_date: date
    ) -> Optional[FinanceAccountBalance]:
        """Recupere le solde a une date donnee."""
        return (
            self.session.query(FinanceAccountBalance)
            .filter(
                FinanceAccountBalance.account_id == account_id,
                FinanceAccountBalance.date == target_date
            )
            .first()
        )

    def get_latest(self, account_id: int) -> Optional[FinanceAccountBalance]:
        """Recupere le dernier solde enregistre."""
        return (
            self.session.query(FinanceAccountBalance)
            .filter(FinanceAccountBalance.account_id == account_id)
            .order_by(desc(FinanceAccountBalance.date))
            .first()
        )

    def upsert(
        self,
        account_id: int,
        target_date: date,
        balance: int,
        source: str = "manual"
    ) -> FinanceAccountBalance:
        """Insere ou met a jour un solde."""
        existing = self.get_by_date(account_id, target_date)
        if existing:
            existing.balance = balance
            existing.source = source
            self.session.flush()
            return existing
        else:
            return self.create({
                "account_id": account_id,
                "date": target_date,
                "balance": balance,
                "source": source,
            })
