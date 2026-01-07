"""
FinanceAccount - Comptes bancaires et de tresorerie.
Historique des soldes pour suivi de tresorerie.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
import enum

from sqlalchemy import BigInteger, Text, Boolean, ForeignKey, Index, Numeric, Date
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.entity import FinanceEntity
    from app.models.finance.transaction import FinanceTransaction
    from app.models.finance.bank_statement import FinanceBankStatement


class FinanceAccountType(str, enum.Enum):
    """Type de compte financier."""
    BANQUE = "BANQUE"        # Compte bancaire classique
    CAISSE = "CAISSE"        # Caisse especes
    CB = "CB"                # Carte bancaire
    PLATFORM = "PLATFORM"    # Plateforme (Stripe, PayPal...)
    AUTRE = "AUTRE"          # Autre


class FinanceAccount(Base, TimestampMixin, TenantMixin):
    """
    Compte bancaire ou de tresorerie.
    Supporte plusieurs types: banque, caisse, CB, plateforme.
    """
    __tablename__ = "finance_accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    type: Mapped[FinanceAccountType] = mapped_column(
        SQLEnum(FinanceAccountType, name="finance_account_type"),
        nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    bank_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    iban: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(Text, default="EUR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Solde initial et actuel (en centimes pour eviter les erreurs d'arrondi)
    initial_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Couleur pour l'affichage
    color: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship(
        "FinanceEntity",
        back_populates="accounts"
    )
    balances: Mapped[List["FinanceAccountBalance"]] = relationship(
        "FinanceAccountBalance",
        back_populates="account",
        lazy="selectin",
        order_by="desc(FinanceAccountBalance.date)"
    )
    transactions: Mapped[List["FinanceTransaction"]] = relationship(
        "FinanceTransaction",
        back_populates="account",
        lazy="dynamic"
    )
    bank_statements: Mapped[List["FinanceBankStatement"]] = relationship(
        "FinanceBankStatement",
        back_populates="account",
        lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_finance_accounts_entity_type", "entity_id", "type"),
        Index("ix_finance_accounts_entity_active", "entity_id", "is_active"),
        Index("ix_finance_accounts_tenant", "tenant_id"),
        Index("ix_finance_accounts_iban", "iban"),
    )

    def __repr__(self) -> str:
        return f"<FinanceAccount(id={self.id}, label={self.label}, type={self.type})>"

    @property
    def balance_decimal(self) -> Decimal:
        """Solde actuel en decimal (euros)."""
        return Decimal(self.current_balance) / 100

    @property
    def masked_iban(self) -> Optional[str]:
        """IBAN masque pour affichage securise."""
        if not self.iban:
            return None
        if len(self.iban) < 8:
            return self.iban
        return f"{self.iban[:4]}****{self.iban[-4:]}"


class FinanceAccountBalance(Base, TimestampMixin):
    """
    Historique des soldes de compte.
    Permet le suivi de tresorerie dans le temps.
    """
    __tablename__ = "finance_account_balances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False)  # En centimes
    source: Mapped[str] = mapped_column(
        Text,
        default="manual",
        nullable=False
    )  # manual, import, calculated

    # Relations
    account: Mapped["FinanceAccount"] = relationship(
        "FinanceAccount",
        back_populates="balances"
    )

    __table_args__ = (
        Index(
            "ix_finance_account_balances_account_date",
            "account_id", "date",
            unique=True
        ),
    )

    def __repr__(self) -> str:
        return f"<FinanceAccountBalance(account_id={self.account_id}, date={self.date})>"

    @property
    def balance_decimal(self) -> Decimal:
        """Solde en decimal (euros)."""
        return Decimal(self.balance) / 100
