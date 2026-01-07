"""
FinanceCostCenter - Centres de couts.
Permet l'affectation analytique des transactions.
"""
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.entity import FinanceEntity


class FinanceCostCenter(Base, TimestampMixin, TenantMixin):
    """
    Centre de couts pour l'affectation analytique.
    Permet de suivre les depenses par departement, projet, etc.
    """
    __tablename__ = "finance_cost_centers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Budget optionnel
    budget_annual: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship("FinanceEntity")

    __table_args__ = (
        Index("ix_finance_cost_centers_entity_active", "entity_id", "is_active"),
        Index(
            "ix_finance_cost_centers_entity_code",
            "entity_id", "code",
            unique=True
        ),
        Index("ix_finance_cost_centers_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<FinanceCostCenter(id={self.id}, code={self.code}, name={self.name})>"

    @property
    def display_name(self) -> str:
        """Nom d'affichage avec code."""
        return f"{self.code} - {self.name}"
