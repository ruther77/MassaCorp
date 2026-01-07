"""
Tests comportementaux pour les models Finance.
Verifie le comportement des models, pas leur structure.
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock


class TestFinanceAccountModel:
    """Tests comportementaux pour FinanceAccount."""

    @pytest.mark.unit
    def test_balance_decimal_converts_centimes_to_euros(self):
        """balance_decimal doit convertir les centimes en euros."""
        from app.models.finance.account import FinanceAccount

        account = FinanceAccount(
            id=1,
            tenant_id=1,
            entity_id=1,
            type="BANQUE",
            label="Compte Test",
            currency="EUR",
            is_active=True,
            initial_balance=0,
            current_balance=150075,  # 1500.75 EUR en centimes
        )

        result = account.balance_decimal

        assert result == Decimal("1500.75")

    @pytest.mark.unit
    def test_masked_iban_hides_middle_characters(self):
        """masked_iban doit masquer les caracteres du milieu."""
        from app.models.finance.account import FinanceAccount

        account = FinanceAccount(
            id=1,
            tenant_id=1,
            entity_id=1,
            type="BANQUE",
            label="Compte Test",
            currency="EUR",
            is_active=True,
            initial_balance=0,
            current_balance=0,
            iban="FR7630001007941234567890185",
        )

        result = account.masked_iban

        assert result.startswith("FR76")
        assert result.endswith("0185")
        assert "****" in result

    @pytest.mark.unit
    def test_masked_iban_returns_none_when_no_iban(self):
        """masked_iban doit retourner None si pas d'IBAN."""
        from app.models.finance.account import FinanceAccount

        account = FinanceAccount(
            id=1,
            tenant_id=1,
            entity_id=1,
            type="CAISSE",
            label="Caisse",
            currency="EUR",
            is_active=True,
            initial_balance=0,
            current_balance=0,
            iban=None,
        )

        assert account.masked_iban is None


class TestFinanceTransactionModel:
    """Tests comportementaux pour FinanceTransaction."""

    @pytest.mark.unit
    def test_signed_amount_negative_for_out_direction(self):
        """signed_amount doit etre negatif pour direction OUT."""
        from app.models.finance.transaction import (
            FinanceTransaction,
            FinanceTransactionDirection,
            FinanceTransactionStatus,
        )

        transaction = FinanceTransaction(
            id=1,
            tenant_id=1,
            entity_id=1,
            account_id=1,
            direction=FinanceTransactionDirection.OUT,
            status=FinanceTransactionStatus.CONFIRMED,
            date_operation=date.today(),
            amount=50000,  # 500 EUR
            label="Test debit",
        )

        result = transaction.signed_amount

        assert result == -50000

    @pytest.mark.unit
    def test_signed_amount_positive_for_in_direction(self):
        """signed_amount doit etre positif pour direction IN."""
        from app.models.finance.transaction import (
            FinanceTransaction,
            FinanceTransactionDirection,
            FinanceTransactionStatus,
        )

        transaction = FinanceTransaction(
            id=1,
            tenant_id=1,
            entity_id=1,
            account_id=1,
            direction=FinanceTransactionDirection.IN,
            status=FinanceTransactionStatus.CONFIRMED,
            date_operation=date.today(),
            amount=50000,
            label="Test credit",
        )

        result = transaction.signed_amount

        assert result == 50000

    @pytest.mark.unit
    def test_is_categorized_false_when_no_lines(self):
        """is_categorized doit etre False sans lignes."""
        from app.models.finance.transaction import (
            FinanceTransaction,
            FinanceTransactionDirection,
            FinanceTransactionStatus,
        )

        transaction = FinanceTransaction(
            id=1,
            tenant_id=1,
            entity_id=1,
            account_id=1,
            direction=FinanceTransactionDirection.OUT,
            status=FinanceTransactionStatus.CONFIRMED,
            date_operation=date.today(),
            amount=50000,
            label="Test",
        )
        transaction.lines = []

        assert transaction.is_categorized is False


class TestFinanceInvoiceModel:
    """Tests comportementaux pour FinanceInvoice."""

    @pytest.mark.unit
    def test_is_overdue_true_when_past_due_date(self):
        """is_overdue doit etre True si date echeance depassee."""
        from app.models.finance.invoice import FinanceInvoice, FinanceInvoiceStatus
        from datetime import timedelta

        invoice = FinanceInvoice(
            id=1,
            tenant_id=1,
            entity_id=1,
            vendor_id=1,
            invoice_number="FAC-001",
            date_invoice=date.today() - timedelta(days=60),
            date_due=date.today() - timedelta(days=30),  # 30 jours en retard
            montant_ht=10000,
            montant_tva=2000,
            montant_ttc=12000,
            status=FinanceInvoiceStatus.EN_ATTENTE,
        )

        assert invoice.is_overdue is True

    @pytest.mark.unit
    def test_is_overdue_false_when_paid(self):
        """is_overdue doit etre False si facture payee."""
        from app.models.finance.invoice import FinanceInvoice, FinanceInvoiceStatus
        from datetime import timedelta

        invoice = FinanceInvoice(
            id=1,
            tenant_id=1,
            entity_id=1,
            vendor_id=1,
            invoice_number="FAC-001",
            date_invoice=date.today() - timedelta(days=60),
            date_due=date.today() - timedelta(days=30),  # Passee mais payee
            montant_ht=10000,
            montant_tva=2000,
            montant_ttc=12000,
            status=FinanceInvoiceStatus.PAYEE,
        )

        assert invoice.is_overdue is False

    @pytest.mark.unit
    def test_days_overdue_returns_correct_count(self):
        """days_overdue doit retourner le nombre correct de jours."""
        from app.models.finance.invoice import FinanceInvoice, FinanceInvoiceStatus
        from datetime import timedelta

        days_late = 15
        invoice = FinanceInvoice(
            id=1,
            tenant_id=1,
            entity_id=1,
            vendor_id=1,
            invoice_number="FAC-001",
            date_invoice=date.today() - timedelta(days=45),
            date_due=date.today() - timedelta(days=days_late),
            montant_ht=10000,
            montant_tva=2000,
            montant_ttc=12000,
            status=FinanceInvoiceStatus.EN_ATTENTE,
        )

        assert invoice.days_overdue == days_late

    @pytest.mark.unit
    def test_amount_remaining_calculated_correctly(self):
        """amount_remaining doit calculer le reste a payer."""
        from app.models.finance.invoice import FinanceInvoice, FinanceInvoiceStatus, FinancePayment

        invoice = FinanceInvoice(
            id=1,
            tenant_id=1,
            entity_id=1,
            vendor_id=1,
            invoice_number="FAC-001",
            date_invoice=date.today(),
            date_due=date.today(),
            montant_ht=10000,
            montant_tva=2000,
            montant_ttc=12000,
            status=FinanceInvoiceStatus.PARTIELLE,
        )

        # Simuler des paiements
        payment1 = MagicMock()
        payment1.amount = 5000
        payment2 = MagicMock()
        payment2.amount = 3000
        invoice.payments = [payment1, payment2]

        # Reste a payer = 12000 - 5000 - 3000 = 4000
        assert invoice.amount_remaining == 4000


class TestFinanceCategoryModel:
    """Tests comportementaux pour FinanceCategory."""

    @pytest.mark.unit
    def test_full_path_includes_parent_name(self):
        """full_path doit inclure le nom du parent."""
        from app.models.finance.category import FinanceCategory, FinanceCategoryType

        parent = FinanceCategory(
            id=1,
            tenant_id=1,
            entity_id=1,
            name="Charges",
            type=FinanceCategoryType.EXPENSE,
        )
        parent.parent = None
        parent.children = []

        child = FinanceCategory(
            id=2,
            tenant_id=1,
            entity_id=1,
            name="Fournitures",
            type=FinanceCategoryType.EXPENSE,
        )
        child.parent = parent
        child.children = []

        assert child.full_path == "Charges > Fournitures"

    @pytest.mark.unit
    def test_level_returns_depth_in_hierarchy(self):
        """level doit retourner la profondeur dans la hierarchie."""
        from app.models.finance.category import FinanceCategory, FinanceCategoryType

        root = FinanceCategory(
            id=1,
            tenant_id=1,
            entity_id=1,
            name="Root",
            type=FinanceCategoryType.EXPENSE,
        )
        root.parent = None
        root.children = []

        level1 = FinanceCategory(
            id=2,
            tenant_id=1,
            entity_id=1,
            name="Level1",
            type=FinanceCategoryType.EXPENSE,
        )
        level1.parent = root
        level1.children = []

        level2 = FinanceCategory(
            id=3,
            tenant_id=1,
            entity_id=1,
            name="Level2",
            type=FinanceCategoryType.EXPENSE,
        )
        level2.parent = level1
        level2.children = []

        assert root.level == 0
        assert level1.level == 1
        assert level2.level == 2

    @pytest.mark.unit
    def test_is_leaf_true_when_no_children(self):
        """is_leaf doit etre True sans enfants."""
        from app.models.finance.category import FinanceCategory, FinanceCategoryType

        category = FinanceCategory(
            id=1,
            tenant_id=1,
            entity_id=1,
            name="Leaf",
            type=FinanceCategoryType.EXPENSE,
        )
        category.parent = None
        category.children = []

        assert category.is_leaf is True
