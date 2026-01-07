"""
Service pour la gestion des transactions financieres.
"""
import logging
from datetime import date
from typing import List, Optional, Dict, Any

from app.models.finance.transaction import (
    FinanceTransaction,
    FinanceTransactionLine,
    FinanceTransactionDirection,
    FinanceTransactionStatus,
)
from app.repositories.finance.transaction import (
    FinanceTransactionRepository,
    FinanceTransactionLineRepository,
)
from app.repositories.finance.account import FinanceAccountRepository
from app.repositories.base import PaginatedResult
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class TransactionNotFoundError(AppException):
    """Transaction non trouvee."""
    status_code = 404
    error_code = "TRANSACTION_NOT_FOUND"

    def __init__(self, transaction_id: int):
        super().__init__(message=f"Transaction {transaction_id} non trouvee")
        self.transaction_id = transaction_id


class InvalidTransactionError(AppException):
    """Transaction invalide."""
    status_code = 400
    error_code = "INVALID_TRANSACTION"


class FinanceTransactionService:
    """
    Service de gestion des transactions financieres.
    """

    def __init__(
        self,
        transaction_repository: FinanceTransactionRepository,
        line_repository: FinanceTransactionLineRepository,
        account_repository: FinanceAccountRepository,
    ):
        self.transaction_repository = transaction_repository
        self.line_repository = line_repository
        self.account_repository = account_repository

    def create_transaction(
        self,
        entity_id: int,
        account_id: int,
        direction: FinanceTransactionDirection,
        amount: int,
        label: str,
        date_operation: date,
        date_valeur: Optional[date] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        source: str = "manual",
        lines: Optional[List[Dict[str, Any]]] = None,
        update_balance: bool = True,
    ) -> FinanceTransaction:
        """
        Cree une nouvelle transaction.

        Args:
            entity_id: ID de l'entite
            account_id: ID du compte
            direction: Direction (IN/OUT/TRANSFER)
            amount: Montant en centimes (positif)
            label: Libelle
            date_operation: Date d'operation
            date_valeur: Date de valeur
            reference: Reference optionnelle
            notes: Notes optionnelles
            source: Source (manual, import, api)
            lines: Lignes de ventilation optionnelles
            update_balance: Mettre a jour le solde du compte

        Returns:
            La transaction creee
        """
        if amount <= 0:
            raise InvalidTransactionError("Le montant doit etre positif")

        transaction = self.transaction_repository.create({
            "entity_id": entity_id,
            "account_id": account_id,
            "direction": direction,
            "status": FinanceTransactionStatus.CONFIRMED,
            "date_operation": date_operation,
            "date_valeur": date_valeur,
            "amount": amount,
            "label": label,
            "reference": reference,
            "notes": notes,
            "source": source,
        })

        # Creer les lignes de ventilation
        if lines:
            for line_data in lines:
                self.line_repository.create({
                    "transaction_id": transaction.id,
                    **line_data
                })

        # Mettre a jour le solde du compte
        if update_balance:
            account = self.account_repository.get(account_id)
            if account:
                if direction == FinanceTransactionDirection.IN:
                    account.current_balance += amount
                elif direction == FinanceTransactionDirection.OUT:
                    account.current_balance -= amount
                self.account_repository.session.flush()

        logger.info(f"Transaction creee: {transaction.id} - {amount/100:.2f}EUR {direction}")
        return transaction

    def get_transaction(self, transaction_id: int) -> FinanceTransaction:
        """
        Recupere une transaction par ID.

        Raises:
            TransactionNotFoundError: Si la transaction n'existe pas
        """
        transaction = self.transaction_repository.get(transaction_id)
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        return transaction

    def get_transactions_by_entity(
        self,
        entity_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceTransaction]:
        """Recupere les transactions d'une entite avec pagination."""
        return self.transaction_repository.get_by_entity(entity_id, page, page_size)

    def get_transactions_by_account(
        self,
        account_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[FinanceTransaction]:
        """Recupere les transactions d'un compte avec pagination."""
        return self.transaction_repository.get_by_account(account_id, page, page_size)

    def get_transactions_by_period(
        self,
        entity_id: int,
        start_date: date,
        end_date: date
    ) -> List[FinanceTransaction]:
        """Recupere les transactions sur une periode."""
        return self.transaction_repository.get_by_period(entity_id, start_date, end_date)

    def search_transactions(
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
        return self.transaction_repository.search(
            entity_id=entity_id,
            label=label,
            direction=direction,
            min_amount=min_amount,
            max_amount=max_amount,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )

    def categorize_transaction(
        self,
        transaction_id: int,
        lines: List[Dict[str, Any]]
    ) -> FinanceTransaction:
        """
        Categorise une transaction avec des lignes de ventilation.

        Args:
            transaction_id: ID de la transaction
            lines: Liste des lignes avec category_id, cost_center_id, montant_ttc, etc.
        """
        transaction = self.get_transaction(transaction_id)

        # Supprimer les lignes existantes
        self.line_repository.delete_by_transaction(transaction_id)

        # Creer les nouvelles lignes
        total = 0
        for line_data in lines:
            line = self.line_repository.create({
                "transaction_id": transaction_id,
                **line_data
            })
            total += line.montant_ttc

        # Verifier que le total correspond au montant de la transaction
        if total != transaction.amount:
            logger.warning(
                f"Transaction {transaction_id}: total lignes ({total}) != montant ({transaction.amount})"
            )

        logger.info(f"Transaction categorisee: {transaction_id} ({len(lines)} lignes)")
        return self.get_transaction(transaction_id)

    def get_uncategorized_transactions(
        self,
        entity_id: int
    ) -> List[FinanceTransaction]:
        """Recupere les transactions non categorisees."""
        return self.transaction_repository.get_uncategorized(entity_id)

    def cancel_transaction(self, transaction_id: int) -> FinanceTransaction:
        """
        Annule une transaction.
        Revert le solde du compte.
        """
        transaction = self.get_transaction(transaction_id)

        if transaction.status == FinanceTransactionStatus.CANCELLED:
            return transaction

        # Reverter le solde
        account = self.account_repository.get(transaction.account_id)
        if account:
            if transaction.direction == FinanceTransactionDirection.IN:
                account.current_balance -= transaction.amount
            elif transaction.direction == FinanceTransactionDirection.OUT:
                account.current_balance += transaction.amount
            self.account_repository.session.flush()

        transaction.status = FinanceTransactionStatus.CANCELLED
        self.transaction_repository.session.flush()

        logger.info(f"Transaction annulee: {transaction_id}")
        return transaction
