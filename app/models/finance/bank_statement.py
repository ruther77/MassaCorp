"""
FinanceBankStatement - Releves bancaires et rapprochement.
Import et rapprochement des releves avec les transactions.
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
    from app.models.finance.account import FinanceAccount
    from app.models.finance.transaction import FinanceTransaction


class FinanceReconciliationStatus(str, enum.Enum):
    """Statut du rapprochement."""
    AUTO = "AUTO"        # Rapprochement automatique
    MANUAL = "MANUAL"    # Rapprochement manuel
    REJECTED = "REJECTED"  # Rapprochement rejete


class FinanceBankStatement(Base, TimestampMixin, TenantMixin):
    """
    Releve bancaire importe.
    Contient les metadata d'un import de releve.
    """
    __tablename__ = "finance_bank_statements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Periode couverte
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Source du releve
    source: Mapped[str] = mapped_column(Text, nullable=False)  # ofx, csv, manual
    file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soldes declares
    balance_start: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # En centimes
    balance_end: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Statistiques d'import
    lines_imported: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    lines_matched: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Relations
    account: Mapped["FinanceAccount"] = relationship(
        "FinanceAccount",
        back_populates="bank_statements"
    )
    lines: Mapped[List["FinanceBankStatementLine"]] = relationship(
        "FinanceBankStatementLine",
        back_populates="statement",
        lazy="selectin",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_finance_bank_statements_account_period", "account_id", "period_start", "period_end"),
        Index("ix_finance_bank_statements_tenant", "tenant_id"),
        Index("ix_finance_bank_statements_hash", "file_hash"),
    )

    def __repr__(self) -> str:
        return f"<FinanceBankStatement(id={self.id}, account_id={self.account_id}, period={self.period_start}-{self.period_end})>"

    @property
    def match_rate(self) -> float:
        """Taux de rapprochement (0-100)."""
        if self.lines_imported == 0:
            return 0.0
        return (self.lines_matched / self.lines_imported) * 100


class FinanceBankStatementLine(Base, TimestampMixin):
    """
    Ligne de releve bancaire.
    Une operation du releve a rapprocher.
    """
    __tablename__ = "finance_bank_statement_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    statement_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_bank_statements.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Dates
    date_operation: Mapped[date] = mapped_column(Date, nullable=False)
    date_valeur: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Libelle brut de la banque
    libelle_banque: Mapped[str] = mapped_column(Text, nullable=False)

    # Montant (en centimes, signe)
    montant: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # References bancaires
    ref_banque: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statut de rapprochement
    is_matched: Mapped[bool] = mapped_column(
        default=False,
        nullable=False
    )

    # Relations
    statement: Mapped["FinanceBankStatement"] = relationship(
        "FinanceBankStatement",
        back_populates="lines"
    )
    reconciliations: Mapped[List["FinanceReconciliation"]] = relationship(
        "FinanceReconciliation",
        back_populates="statement_line",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_finance_bank_statement_lines_statement", "statement_id"),
        Index("ix_finance_bank_statement_lines_date", "date_operation"),
        Index("ix_finance_bank_statement_lines_ref", "ref_banque"),
        Index("ix_finance_bank_statement_lines_checksum", "checksum"),
    )

    def __repr__(self) -> str:
        return f"<FinanceBankStatementLine(id={self.id}, date={self.date_operation}, montant={self.montant})>"

    @property
    def montant_decimal(self) -> Decimal:
        """Montant en decimal."""
        return Decimal(self.montant) / 100

    @property
    def is_credit(self) -> bool:
        """True si operation credit (entree)."""
        return self.montant > 0

    @property
    def is_debit(self) -> bool:
        """True si operation debit (sortie)."""
        return self.montant < 0


class FinanceReconciliation(Base, TimestampMixin):
    """
    Rapprochement entre ligne de releve et transaction.
    Permet de lier les operations bancaires aux transactions internes.
    """
    __tablename__ = "finance_reconciliations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    statement_line_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_bank_statement_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    transaction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Statut et methode
    status: Mapped[FinanceReconciliationStatus] = mapped_column(
        SQLEnum(FinanceReconciliationStatus, name="finance_reconciliation_status"),
        default=FinanceReconciliationStatus.MANUAL,
        nullable=False
    )

    # Score de confiance pour rapprochement auto (0-100)
    confidence: Mapped[int] = mapped_column(BigInteger, default=100, nullable=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    statement_line: Mapped["FinanceBankStatementLine"] = relationship(
        "FinanceBankStatementLine",
        back_populates="reconciliations"
    )
    transaction: Mapped["FinanceTransaction"] = relationship(
        "FinanceTransaction",
        back_populates="reconciliations"
    )

    __table_args__ = (
        Index("ix_finance_reconciliations_statement_line", "statement_line_id"),
        Index("ix_finance_reconciliations_transaction", "transaction_id"),
        Index("ix_finance_reconciliations_status", "status"),
        Index(
            "ix_finance_reconciliations_unique",
            "statement_line_id", "transaction_id",
            unique=True
        ),
    )

    def __repr__(self) -> str:
        return f"<FinanceReconciliation(id={self.id}, status={self.status}, confidence={self.confidence})>"

    @property
    def is_auto(self) -> bool:
        """True si rapprochement automatique."""
        return self.status == FinanceReconciliationStatus.AUTO

    @property
    def is_valid(self) -> bool:
        """True si rapprochement valide (non rejete)."""
        return self.status != FinanceReconciliationStatus.REJECTED
