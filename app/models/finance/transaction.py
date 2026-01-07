"""
FinanceTransaction - Transactions financieres.
Lignes de transactions avec ventilation par categorie et centre de couts.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum

from sqlalchemy import BigInteger, Text, ForeignKey, Index, Date, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.entity import FinanceEntity
    from app.models.finance.account import FinanceAccount
    from app.models.finance.category import FinanceCategory
    from app.models.finance.cost_center import FinanceCostCenter
    from app.models.finance.bank_statement import FinanceReconciliation


class FinanceTransactionDirection(str, enum.Enum):
    """Direction de la transaction."""
    IN = "IN"          # Entree (credit)
    OUT = "OUT"        # Sortie (debit)
    TRANSFER = "TRANSFER"  # Transfert interne


class FinanceTransactionStatus(str, enum.Enum):
    """Statut de la transaction."""
    DRAFT = "DRAFT"          # Brouillon
    CONFIRMED = "CONFIRMED"  # Confirmee
    CANCELLED = "CANCELLED"  # Annulee


class FinanceTransaction(Base, TimestampMixin, TenantMixin):
    """
    Transaction financiere.
    Represente un mouvement sur un compte avec ventilation possible.
    """
    __tablename__ = "finance_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    direction: Mapped[FinanceTransactionDirection] = mapped_column(
        SQLEnum(FinanceTransactionDirection, name="finance_tx_direction"),
        nullable=False
    )
    status: Mapped[FinanceTransactionStatus] = mapped_column(
        SQLEnum(FinanceTransactionStatus, name="finance_tx_status"),
        default=FinanceTransactionStatus.CONFIRMED,
        nullable=False
    )

    # Dates
    date_operation: Mapped[date] = mapped_column(Date, nullable=False)
    date_valeur: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Montant total (en centimes)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Libelle et reference
    label: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source de la transaction
    source: Mapped[str] = mapped_column(
        Text,
        default="manual",
        nullable=False
    )  # manual, import, api

    # Relations
    entity: Mapped["FinanceEntity"] = relationship("FinanceEntity")
    account: Mapped["FinanceAccount"] = relationship(
        "FinanceAccount",
        back_populates="transactions"
    )
    lines: Mapped[List["FinanceTransactionLine"]] = relationship(
        "FinanceTransactionLine",
        back_populates="transaction",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    reconciliations: Mapped[List["FinanceReconciliation"]] = relationship(
        "FinanceReconciliation",
        back_populates="transaction",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_finance_tx_entity_date", "entity_id", "date_operation"),
        Index("ix_finance_tx_account_date", "account_id", "date_operation"),
        Index("ix_finance_tx_tenant_date", "tenant_id", "date_operation"),
        Index("ix_finance_tx_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<FinanceTransaction(id={self.id}, amount={self.amount}, direction={self.direction})>"

    @property
    def amount_decimal(self) -> Decimal:
        """Montant en decimal (euros)."""
        return Decimal(self.amount) / 100

    @property
    def signed_amount(self) -> int:
        """Montant signe (negatif pour OUT)."""
        if self.direction == FinanceTransactionDirection.OUT:
            return -self.amount
        return self.amount

    @property
    def is_categorized(self) -> bool:
        """True si transaction entierement categorisee."""
        if not self.lines:
            return False
        categorized_amount = sum(line.montant_ttc for line in self.lines)
        return categorized_amount == self.amount

    @property
    def is_reconciled(self) -> bool:
        """True si transaction rapprochee."""
        return any(r.status != "REJECTED" for r in self.reconciliations)


class FinanceTransactionLine(Base, TimestampMixin):
    """
    Ligne de transaction avec ventilation.
    Permet d'affecter une transaction a plusieurs categories/centres de couts.
    """
    __tablename__ = "finance_transaction_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    cost_center_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_cost_centers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Montants (en centimes)
    montant_ht: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tva_pct: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # En centieme (2000 = 20%)
    montant_ttc: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Description optionnelle
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    transaction: Mapped["FinanceTransaction"] = relationship(
        "FinanceTransaction",
        back_populates="lines"
    )
    category: Mapped[Optional["FinanceCategory"]] = relationship("FinanceCategory")
    cost_center: Mapped[Optional["FinanceCostCenter"]] = relationship("FinanceCostCenter")

    __table_args__ = (
        Index("ix_finance_tx_lines_transaction", "transaction_id"),
        Index("ix_finance_tx_lines_category", "category_id"),
        Index("ix_finance_tx_lines_cost_center", "cost_center_id"),
    )

    def __repr__(self) -> str:
        return f"<FinanceTransactionLine(id={self.id}, montant_ttc={self.montant_ttc})>"

    @property
    def montant_ht_decimal(self) -> Decimal:
        """Montant HT en decimal."""
        return Decimal(self.montant_ht) / 100

    @property
    def montant_ttc_decimal(self) -> Decimal:
        """Montant TTC en decimal."""
        return Decimal(self.montant_ttc) / 100

    @property
    def tva_amount(self) -> int:
        """Montant de TVA en centimes."""
        return self.montant_ttc - self.montant_ht
