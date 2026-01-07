"""
Service pour la gestion des comptes financiers.
"""
import logging
from datetime import date
from typing import List, Optional, Dict, Any
from decimal import Decimal

from app.models.finance.account import (
    FinanceAccount,
    FinanceAccountBalance,
    FinanceAccountType,
)
from app.repositories.finance.account import (
    FinanceAccountRepository,
    FinanceAccountBalanceRepository,
)
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class AccountNotFoundError(AppException):
    """Compte non trouve."""
    status_code = 404
    error_code = "ACCOUNT_NOT_FOUND"

    def __init__(self, account_id: int):
        super().__init__(message=f"Compte {account_id} non trouve")
        self.account_id = account_id


class DuplicateIBANError(AppException):
    """IBAN deja utilise."""
    status_code = 409
    error_code = "DUPLICATE_IBAN"

    def __init__(self, iban: str):
        super().__init__(message=f"L'IBAN {iban} existe deja")
        self.iban = iban


class FinanceAccountService:
    """
    Service de gestion des comptes bancaires et de tresorerie.
    """

    def __init__(
        self,
        account_repository: FinanceAccountRepository,
        balance_repository: FinanceAccountBalanceRepository,
    ):
        self.account_repository = account_repository
        self.balance_repository = balance_repository

    def create_account(
        self,
        entity_id: int,
        label: str,
        account_type: FinanceAccountType,
        currency: str = "EUR",
        bank_name: Optional[str] = None,
        iban: Optional[str] = None,
        bic: Optional[str] = None,
        initial_balance: int = 0,
        color: Optional[str] = None,
    ) -> FinanceAccount:
        """
        Cree un nouveau compte.

        Args:
            entity_id: ID de l'entite
            label: Libelle du compte
            account_type: Type de compte
            currency: Devise
            bank_name: Nom de la banque
            iban: IBAN
            bic: BIC
            initial_balance: Solde initial en centimes
            color: Couleur pour l'affichage

        Returns:
            Le compte cree

        Raises:
            DuplicateIBANError: Si l'IBAN existe deja
        """
        # Verifier unicite IBAN si fourni
        if iban:
            iban = iban.replace(" ", "").upper()
            existing = self.account_repository.get_by_iban(iban)
            if existing:
                raise DuplicateIBANError(iban)

        account = self.account_repository.create({
            "entity_id": entity_id,
            "label": label,
            "type": account_type,
            "currency": currency,
            "bank_name": bank_name,
            "iban": iban,
            "bic": bic,
            "initial_balance": initial_balance,
            "current_balance": initial_balance,
            "color": color,
            "is_active": True,
        })

        # Enregistrer le solde initial
        if initial_balance != 0:
            self.balance_repository.create({
                "account_id": account.id,
                "date": date.today(),
                "balance": initial_balance,
                "source": "initial",
            })

        logger.info(f"Compte cree: {account.id} - {account.label}")
        return account

    def get_account(self, account_id: int) -> FinanceAccount:
        """
        Recupere un compte par ID.

        Raises:
            AccountNotFoundError: Si le compte n'existe pas
        """
        account = self.account_repository.get(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return account

    def get_accounts_by_entity(self, entity_id: int) -> List[FinanceAccount]:
        """Recupere tous les comptes d'une entite."""
        return self.account_repository.get_by_entity(entity_id)

    def get_active_accounts(self, entity_id: int) -> List[FinanceAccount]:
        """Recupere les comptes actifs d'une entite."""
        return self.account_repository.get_active_by_entity(entity_id)

    def get_accounts_by_type(
        self,
        entity_id: int,
        account_type: FinanceAccountType
    ) -> List[FinanceAccount]:
        """Recupere les comptes par type."""
        return self.account_repository.get_by_type(entity_id, account_type)

    def update_account(
        self,
        account_id: int,
        data: Dict[str, Any]
    ) -> FinanceAccount:
        """
        Met a jour un compte.

        Raises:
            AccountNotFoundError: Si le compte n'existe pas
            DuplicateIBANError: Si le nouvel IBAN existe deja
        """
        account = self.get_account(account_id)

        # Verifier unicite IBAN si modifie
        if "iban" in data and data["iban"]:
            new_iban = data["iban"].replace(" ", "").upper()
            if new_iban != account.iban:
                existing = self.account_repository.get_by_iban(new_iban)
                if existing:
                    raise DuplicateIBANError(new_iban)
                data["iban"] = new_iban

        updated = self.account_repository.update(account_id, data)
        logger.info(f"Compte mis a jour: {account_id}")
        return updated

    def deactivate_account(self, account_id: int) -> FinanceAccount:
        """Desactive un compte."""
        account = self.get_account(account_id)
        account.is_active = False
        self.account_repository.session.flush()
        logger.info(f"Compte desactive: {account_id}")
        return account

    def update_balance(
        self,
        account_id: int,
        amount: int,
        is_credit: bool = True
    ) -> FinanceAccount:
        """
        Met a jour le solde d'un compte.

        Args:
            account_id: ID du compte
            amount: Montant en centimes (positif)
            is_credit: True pour credit, False pour debit
        """
        account = self.get_account(account_id)

        if is_credit:
            account.current_balance += amount
        else:
            account.current_balance -= amount

        self.account_repository.session.flush()
        return account

    def record_balance(
        self,
        account_id: int,
        balance_date: date,
        balance: int,
        source: str = "manual"
    ) -> FinanceAccountBalance:
        """
        Enregistre un solde a une date donnee.
        Met a jour si existe deja.
        """
        self.get_account(account_id)  # Verifier existence
        return self.balance_repository.upsert(
            account_id=account_id,
            target_date=balance_date,
            balance=balance,
            source=source
        )

    def get_balance_history(
        self,
        account_id: int,
        limit: int = 30
    ) -> List[FinanceAccountBalance]:
        """Recupere l'historique des soldes."""
        return self.balance_repository.get_by_account(account_id, limit)

    def get_total_balance(self, entity_id: int) -> int:
        """Calcule le solde total de tous les comptes actifs."""
        accounts = self.get_active_accounts(entity_id)
        return sum(a.current_balance for a in accounts)

    def get_balance_by_type(
        self,
        entity_id: int,
        account_type: FinanceAccountType
    ) -> int:
        """Calcule le solde total par type de compte."""
        accounts = self.get_accounts_by_type(entity_id, account_type)
        return sum(a.current_balance for a in accounts if a.is_active)
