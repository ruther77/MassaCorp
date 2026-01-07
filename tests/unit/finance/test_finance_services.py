"""
Tests comportementaux pour les services Finance.
Verifie la logique metier, pas la structure.
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestFinanceAccountService:
    """Tests comportementaux pour FinanceAccountService."""

    @pytest.fixture
    def mock_account_repo(self):
        """Mock du repository account."""
        return MagicMock()

    @pytest.fixture
    def mock_balance_repo(self):
        """Mock du repository balance."""
        return MagicMock()

    @pytest.fixture
    def account_service(self, mock_account_repo, mock_balance_repo):
        """Service avec mocks."""
        from app.services.finance.account import FinanceAccountService
        return FinanceAccountService(mock_account_repo, mock_balance_repo)

    @pytest.mark.unit
    def test_create_account_normalizes_iban(self, account_service, mock_account_repo):
        """create_account doit normaliser l'IBAN (majuscules, sans espaces)."""
        from app.models.finance.account import FinanceAccountType

        mock_account_repo.get_by_iban.return_value = None
        mock_account_repo.create.return_value = MagicMock(id=1)

        account_service.create_account(
            entity_id=1,
            label="Test",
            account_type=FinanceAccountType.BANQUE,
            iban="fr76 3000 1007 9412 3456 7890 185",  # Minuscules + espaces
        )

        # Verifier que l'IBAN est normalise dans l'appel create
        call_args = mock_account_repo.create.call_args[0][0]
        assert call_args["iban"] == "FR7630001007941234567890185"

    @pytest.mark.unit
    def test_create_account_rejects_duplicate_iban(self, account_service, mock_account_repo):
        """create_account doit rejeter un IBAN deja utilise."""
        from app.models.finance.account import FinanceAccountType
        from app.services.finance.account import DuplicateIBANError

        # Simuler un compte existant avec cet IBAN
        mock_account_repo.get_by_iban.return_value = MagicMock(id=99)

        with pytest.raises(DuplicateIBANError):
            account_service.create_account(
                entity_id=1,
                label="Test",
                account_type=FinanceAccountType.BANQUE,
                iban="FR7630001007941234567890185",
            )

    @pytest.mark.unit
    def test_create_account_records_initial_balance(
        self, account_service, mock_account_repo, mock_balance_repo
    ):
        """create_account doit enregistrer le solde initial si non zero."""
        from app.models.finance.account import FinanceAccountType

        mock_account_repo.get_by_iban.return_value = None
        mock_account = MagicMock(id=1)
        mock_account_repo.create.return_value = mock_account

        account_service.create_account(
            entity_id=1,
            label="Test",
            account_type=FinanceAccountType.BANQUE,
            initial_balance=150000,  # 1500 EUR
        )

        # Verifier que le solde initial est enregistre
        mock_balance_repo.create.assert_called_once()
        balance_data = mock_balance_repo.create.call_args[0][0]
        assert balance_data["balance"] == 150000
        assert balance_data["source"] == "initial"

    @pytest.mark.unit
    def test_update_balance_adds_for_credit(self, account_service, mock_account_repo):
        """update_balance doit ajouter le montant pour un credit."""
        mock_account = MagicMock()
        mock_account.current_balance = 100000  # 1000 EUR
        mock_account_repo.get.return_value = mock_account

        account_service.update_balance(
            account_id=1,
            amount=50000,  # 500 EUR
            is_credit=True
        )

        assert mock_account.current_balance == 150000  # 1500 EUR

    @pytest.mark.unit
    def test_update_balance_subtracts_for_debit(self, account_service, mock_account_repo):
        """update_balance doit soustraire le montant pour un debit."""
        mock_account = MagicMock()
        mock_account.current_balance = 100000  # 1000 EUR
        mock_account_repo.get.return_value = mock_account

        account_service.update_balance(
            account_id=1,
            amount=30000,  # 300 EUR
            is_credit=False
        )

        assert mock_account.current_balance == 70000  # 700 EUR

    @pytest.mark.unit
    def test_get_account_raises_when_not_found(self, account_service, mock_account_repo):
        """get_account doit lever AccountNotFoundError si non trouve."""
        from app.services.finance.account import AccountNotFoundError

        mock_account_repo.get.return_value = None

        with pytest.raises(AccountNotFoundError) as exc_info:
            account_service.get_account(999)

        assert exc_info.value.account_id == 999

    @pytest.mark.unit
    def test_get_total_balance_sums_all_active_accounts(
        self, account_service, mock_account_repo
    ):
        """get_total_balance doit sommer les soldes des comptes actifs."""
        mock_accounts = [
            MagicMock(current_balance=100000, is_active=True),
            MagicMock(current_balance=50000, is_active=True),
            MagicMock(current_balance=25000, is_active=True),
        ]
        mock_account_repo.get_active_by_entity.return_value = mock_accounts

        result = account_service.get_total_balance(entity_id=1)

        assert result == 175000  # 1750 EUR


class TestFinanceTransactionService:
    """Tests comportementaux pour FinanceTransactionService."""

    @pytest.fixture
    def mock_tx_repo(self):
        """Mock du repository transaction."""
        return MagicMock()

    @pytest.fixture
    def mock_line_repo(self):
        """Mock du repository ligne."""
        return MagicMock()

    @pytest.fixture
    def mock_account_repo(self):
        """Mock du repository account."""
        return MagicMock()

    @pytest.fixture
    def transaction_service(self, mock_tx_repo, mock_line_repo, mock_account_repo):
        """Service avec mocks."""
        from app.services.finance.transaction import FinanceTransactionService
        return FinanceTransactionService(mock_tx_repo, mock_line_repo, mock_account_repo)

    @pytest.mark.unit
    def test_create_transaction_rejects_zero_amount(self, transaction_service):
        """create_transaction doit rejeter un montant de 0."""
        from app.models.finance.transaction import FinanceTransactionDirection
        from app.services.finance.transaction import InvalidTransactionError

        with pytest.raises(InvalidTransactionError):
            transaction_service.create_transaction(
                entity_id=1,
                account_id=1,
                direction=FinanceTransactionDirection.IN,
                amount=0,  # Montant invalide
                label="Test",
                date_operation=date.today(),
            )

    @pytest.mark.unit
    def test_create_transaction_rejects_negative_amount(self, transaction_service):
        """create_transaction doit rejeter un montant negatif."""
        from app.models.finance.transaction import FinanceTransactionDirection
        from app.services.finance.transaction import InvalidTransactionError

        with pytest.raises(InvalidTransactionError):
            transaction_service.create_transaction(
                entity_id=1,
                account_id=1,
                direction=FinanceTransactionDirection.IN,
                amount=-5000,  # Montant negatif
                label="Test",
                date_operation=date.today(),
            )

    @pytest.mark.unit
    def test_create_transaction_updates_account_balance_for_credit(
        self, transaction_service, mock_tx_repo, mock_account_repo
    ):
        """create_transaction doit mettre a jour le solde pour un credit."""
        from app.models.finance.transaction import FinanceTransactionDirection

        mock_tx_repo.create.return_value = MagicMock(id=1)
        mock_account = MagicMock(current_balance=100000)
        mock_account_repo.get.return_value = mock_account

        transaction_service.create_transaction(
            entity_id=1,
            account_id=1,
            direction=FinanceTransactionDirection.IN,
            amount=50000,
            label="Credit test",
            date_operation=date.today(),
        )

        assert mock_account.current_balance == 150000

    @pytest.mark.unit
    def test_create_transaction_updates_account_balance_for_debit(
        self, transaction_service, mock_tx_repo, mock_account_repo
    ):
        """create_transaction doit mettre a jour le solde pour un debit."""
        from app.models.finance.transaction import FinanceTransactionDirection

        mock_tx_repo.create.return_value = MagicMock(id=1)
        mock_account = MagicMock(current_balance=100000)
        mock_account_repo.get.return_value = mock_account

        transaction_service.create_transaction(
            entity_id=1,
            account_id=1,
            direction=FinanceTransactionDirection.OUT,
            amount=30000,
            label="Debit test",
            date_operation=date.today(),
        )

        assert mock_account.current_balance == 70000

    @pytest.mark.unit
    def test_cancel_transaction_reverts_balance(
        self, transaction_service, mock_tx_repo, mock_account_repo
    ):
        """cancel_transaction doit reverter le solde du compte."""
        from app.models.finance.transaction import (
            FinanceTransactionDirection,
            FinanceTransactionStatus,
        )

        mock_tx = MagicMock()
        mock_tx.direction = FinanceTransactionDirection.OUT
        mock_tx.status = FinanceTransactionStatus.CONFIRMED
        mock_tx.amount = 50000
        mock_tx.account_id = 1
        mock_tx_repo.get.return_value = mock_tx

        mock_account = MagicMock(current_balance=50000)
        mock_account_repo.get.return_value = mock_account

        transaction_service.cancel_transaction(1)

        # Le solde doit etre restitue (+50000 pour annuler un OUT)
        assert mock_account.current_balance == 100000
        assert mock_tx.status == FinanceTransactionStatus.CANCELLED

    @pytest.mark.unit
    def test_categorize_transaction_deletes_existing_lines(
        self, transaction_service, mock_tx_repo, mock_line_repo
    ):
        """categorize_transaction doit supprimer les lignes existantes."""
        mock_tx = MagicMock(id=1, amount=10000)
        mock_tx_repo.get.return_value = mock_tx

        transaction_service.categorize_transaction(
            transaction_id=1,
            lines=[
                {"category_id": 1, "montant_ht": 8333, "tva_pct": 2000, "montant_ttc": 10000}
            ]
        )

        mock_line_repo.delete_by_transaction.assert_called_once_with(1)


class TestFinanceInvoiceService:
    """Tests comportementaux pour FinanceInvoiceService."""

    @pytest.fixture
    def mock_invoice_repo(self):
        """Mock du repository invoice."""
        return MagicMock()

    @pytest.fixture
    def mock_line_repo(self):
        """Mock du repository ligne."""
        return MagicMock()

    @pytest.fixture
    def mock_payment_repo(self):
        """Mock du repository payment."""
        return MagicMock()

    @pytest.fixture
    def invoice_service(self, mock_invoice_repo, mock_line_repo, mock_payment_repo):
        """Service avec mocks."""
        from app.services.finance.invoice import FinanceInvoiceService
        return FinanceInvoiceService(mock_invoice_repo, mock_line_repo, mock_payment_repo)

    @pytest.mark.unit
    def test_create_invoice_rejects_duplicate(self, invoice_service, mock_invoice_repo):
        """create_invoice doit rejeter une facture doublon."""
        from app.services.finance.invoice import DuplicateInvoiceError

        mock_invoice_repo.check_duplicate.return_value = True

        with pytest.raises(DuplicateInvoiceError):
            invoice_service.create_invoice(
                entity_id=1,
                vendor_id=1,
                invoice_number="FAC-001",
                date_invoice=date.today(),
                date_due=date.today(),
                montant_ht=10000,
                montant_tva=2000,
                montant_ttc=12000,
            )

    @pytest.mark.unit
    def test_record_payment_rejects_cancelled_invoice(
        self, invoice_service, mock_invoice_repo
    ):
        """record_payment doit rejeter un paiement sur facture annulee."""
        from app.models.finance.invoice import FinanceInvoiceStatus
        from app.services.finance.invoice import InvalidPaymentError

        mock_invoice = MagicMock()
        mock_invoice.status = FinanceInvoiceStatus.ANNULEE
        mock_invoice_repo.get.return_value = mock_invoice

        with pytest.raises(InvalidPaymentError) as exc_info:
            invoice_service.record_payment(
                invoice_id=1,
                amount=5000,
                date_payment=date.today(),
            )

        assert "annulee" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_record_payment_rejects_overpayment(
        self, invoice_service, mock_invoice_repo
    ):
        """record_payment doit rejeter un paiement superieur au reste du."""
        from app.models.finance.invoice import FinanceInvoiceStatus
        from app.services.finance.invoice import InvalidPaymentError

        mock_invoice = MagicMock()
        mock_invoice.status = FinanceInvoiceStatus.EN_ATTENTE
        mock_invoice.montant_ttc = 10000
        mock_invoice.amount_remaining = 5000  # Reste 50 EUR
        mock_invoice_repo.get.return_value = mock_invoice

        with pytest.raises(InvalidPaymentError) as exc_info:
            invoice_service.record_payment(
                invoice_id=1,
                amount=8000,  # Superieur au reste
                date_payment=date.today(),
            )

        assert "superieur" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_record_payment_updates_status_to_paid(
        self, invoice_service, mock_invoice_repo, mock_payment_repo
    ):
        """record_payment doit mettre a jour le statut a PAYEE si solde complet."""
        from app.models.finance.invoice import FinanceInvoiceStatus

        mock_invoice = MagicMock()
        mock_invoice.status = FinanceInvoiceStatus.EN_ATTENTE
        mock_invoice.montant_ttc = 10000
        mock_invoice.amount_remaining = 10000
        mock_invoice_repo.get.return_value = mock_invoice

        mock_payment_repo.create.return_value = MagicMock(id=1)
        mock_payment_repo.get_total_by_invoice.return_value = 10000  # Paiement complet

        invoice_service.record_payment(
            invoice_id=1,
            amount=10000,
            date_payment=date.today(),
        )

        assert mock_invoice.status == FinanceInvoiceStatus.PAYEE

    @pytest.mark.unit
    def test_record_payment_updates_status_to_partial(
        self, invoice_service, mock_invoice_repo, mock_payment_repo
    ):
        """record_payment doit mettre a jour le statut a PARTIELLE si paiement partiel."""
        from app.models.finance.invoice import FinanceInvoiceStatus

        mock_invoice = MagicMock()
        mock_invoice.status = FinanceInvoiceStatus.EN_ATTENTE
        mock_invoice.montant_ttc = 10000
        mock_invoice.amount_remaining = 10000
        mock_invoice_repo.get.return_value = mock_invoice

        mock_payment_repo.create.return_value = MagicMock(id=1)
        mock_payment_repo.get_total_by_invoice.return_value = 5000  # Paiement partiel

        invoice_service.record_payment(
            invoice_id=1,
            amount=5000,
            date_payment=date.today(),
        )

        assert mock_invoice.status == FinanceInvoiceStatus.PARTIELLE

    @pytest.mark.unit
    def test_cancel_invoice_rejects_if_payments_exist(
        self, invoice_service, mock_invoice_repo
    ):
        """cancel_invoice doit rejeter si des paiements existent."""
        from app.services.finance.invoice import InvalidPaymentError

        mock_invoice = MagicMock()
        mock_invoice.amount_paid = 5000  # Paiements existent
        mock_invoice_repo.get.return_value = mock_invoice

        with pytest.raises(InvalidPaymentError) as exc_info:
            invoice_service.cancel_invoice(1)

        assert "paiements" in str(exc_info.value).lower()
