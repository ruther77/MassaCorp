"""
FinanceInvoice - Factures fournisseurs.
Gestion des factures avec lignes et paiements.
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
    from app.models.finance.vendor import FinanceVendor
    from app.models.finance.category import FinanceCategory
    from app.models.finance.transaction import FinanceTransaction


class FinanceInvoiceStatus(str, enum.Enum):
    """Statut de la facture."""
    EN_ATTENTE = "EN_ATTENTE"  # En attente de paiement
    PARTIELLE = "PARTIELLE"    # Partiellement payee
    PAYEE = "PAYEE"            # Entierement payee
    ANNULEE = "ANNULEE"        # Annulee


class FinanceInvoice(Base, TimestampMixin, TenantMixin):
    """
    Facture fournisseur.
    Suivi des factures avec statut de paiement.
    """
    __tablename__ = "finance_invoices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    vendor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_vendors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Informations facture
    invoice_number: Mapped[str] = mapped_column(Text, nullable=False)
    date_invoice: Mapped[date] = mapped_column(Date, nullable=False)
    date_due: Mapped[date] = mapped_column(Date, nullable=False)
    date_received: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Montants (en centimes)
    montant_ht: Mapped[int] = mapped_column(BigInteger, nullable=False)
    montant_tva: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    montant_ttc: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Statut
    status: Mapped[FinanceInvoiceStatus] = mapped_column(
        SQLEnum(FinanceInvoiceStatus, name="finance_invoice_status"),
        default=FinanceInvoiceStatus.EN_ATTENTE,
        nullable=False
    )

    # Document source
    file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship("FinanceEntity")
    vendor: Mapped["FinanceVendor"] = relationship(
        "FinanceVendor",
        back_populates="invoices"
    )
    lines: Mapped[List["FinanceInvoiceLine"]] = relationship(
        "FinanceInvoiceLine",
        back_populates="invoice",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    payments: Mapped[List["FinancePayment"]] = relationship(
        "FinancePayment",
        back_populates="invoice",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_finance_invoices_entity_status", "entity_id", "status"),
        Index("ix_finance_invoices_vendor", "vendor_id"),
        Index("ix_finance_invoices_due", "date_due"),
        Index("ix_finance_invoices_tenant_date", "tenant_id", "date_invoice"),
        Index(
            "ix_finance_invoices_entity_number",
            "entity_id", "vendor_id", "invoice_number",
            unique=True
        ),
    )

    def __repr__(self) -> str:
        return f"<FinanceInvoice(id={self.id}, number={self.invoice_number}, status={self.status})>"

    @property
    def montant_ht_decimal(self) -> Decimal:
        """Montant HT en decimal."""
        return Decimal(self.montant_ht) / 100

    @property
    def montant_ttc_decimal(self) -> Decimal:
        """Montant TTC en decimal."""
        return Decimal(self.montant_ttc) / 100

    @property
    def amount_paid(self) -> int:
        """Montant deja paye en centimes."""
        return sum(p.amount for p in self.payments)

    @property
    def amount_remaining(self) -> int:
        """Montant restant a payer en centimes."""
        return self.montant_ttc - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        """True si facture en retard."""
        if self.status in (FinanceInvoiceStatus.PAYEE, FinanceInvoiceStatus.ANNULEE):
            return False
        return date.today() > self.date_due

    @property
    def days_overdue(self) -> int:
        """Nombre de jours de retard."""
        if not self.is_overdue:
            return 0
        return (date.today() - self.date_due).days


class FinanceInvoiceLine(Base, TimestampMixin):
    """
    Ligne de facture.
    Detail d'une facture avec affectation comptable.
    """
    __tablename__ = "finance_invoice_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Quantite et prix unitaire
    quantite: Mapped[int] = mapped_column(BigInteger, default=100, nullable=False)  # En centiemes
    prix_unitaire: Mapped[int] = mapped_column(BigInteger, nullable=False)  # En centimes

    # Montants calcules (en centimes)
    montant_ht: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tva_pct: Mapped[int] = mapped_column(BigInteger, default=2000, nullable=False)  # 2000 = 20%
    montant_ttc: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relations
    invoice: Mapped["FinanceInvoice"] = relationship(
        "FinanceInvoice",
        back_populates="lines"
    )
    category: Mapped[Optional["FinanceCategory"]] = relationship("FinanceCategory")

    __table_args__ = (
        Index("ix_finance_invoice_lines_invoice", "invoice_id"),
        Index("ix_finance_invoice_lines_category", "category_id"),
    )

    def __repr__(self) -> str:
        return f"<FinanceInvoiceLine(id={self.id}, description={self.description[:30]}...)>"


class FinancePayment(Base, TimestampMixin):
    """
    Paiement d'une facture.
    Lie une facture a une transaction bancaire.
    """
    __tablename__ = "finance_payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    transaction_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Montant et date
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # En centimes
    date_payment: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(Text, default="virement", nullable=False)

    # Reference
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    invoice: Mapped["FinanceInvoice"] = relationship(
        "FinanceInvoice",
        back_populates="payments"
    )
    transaction: Mapped[Optional["FinanceTransaction"]] = relationship("FinanceTransaction")

    __table_args__ = (
        Index("ix_finance_payments_invoice", "invoice_id"),
        Index("ix_finance_payments_transaction", "transaction_id"),
    )

    def __repr__(self) -> str:
        return f"<FinancePayment(id={self.id}, amount={self.amount}, date={self.date_payment})>"

    @property
    def amount_decimal(self) -> Decimal:
        """Montant en decimal."""
        return Decimal(self.amount) / 100
