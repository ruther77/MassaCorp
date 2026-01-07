"""
FinanceVendor - Fournisseurs.
Gestion des fournisseurs avec informations de contact et paiement.
"""
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.entity import FinanceEntity
    from app.models.finance.invoice import FinanceInvoice


class FinanceVendor(Base, TimestampMixin, TenantMixin):
    """
    Fournisseur.
    Stocke les informations de contact et de paiement.
    """
    __tablename__ = "finance_vendors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Informations legales
    siret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tva_intra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Contact
    contact_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Adresse
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(Text, default="FR", nullable=False)

    # Informations bancaires
    iban: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Conditions de paiement
    payment_terms_days: Mapped[int] = mapped_column(BigInteger, default=30, nullable=False)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship("FinanceEntity")
    invoices: Mapped[List["FinanceInvoice"]] = relationship(
        "FinanceInvoice",
        back_populates="vendor",
        lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_finance_vendors_entity_name", "entity_id", "name"),
        Index("ix_finance_vendors_entity_active", "entity_id", "is_active"),
        Index("ix_finance_vendors_tenant", "tenant_id"),
        Index("ix_finance_vendors_siret", "siret"),
    )

    def __repr__(self) -> str:
        return f"<FinanceVendor(id={self.id}, name={self.name})>"

    @property
    def display_name(self) -> str:
        """Nom d'affichage avec code si disponible."""
        if self.code:
            return f"{self.code} - {self.name}"
        return self.name

    @property
    def full_address(self) -> Optional[str]:
        """Adresse complete formatee."""
        parts = []
        if self.address:
            parts.append(self.address)
        if self.postal_code or self.city:
            parts.append(f"{self.postal_code or ''} {self.city or ''}".strip())
        if self.country and self.country != "FR":
            parts.append(self.country)
        return "\n".join(parts) if parts else None
