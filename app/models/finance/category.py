"""
FinanceCategory - Categories de transactions financieres.
Hierarchie de categories avec support parent/enfant.
"""
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.entity import FinanceEntity

import enum


class FinanceCategoryType(str, enum.Enum):
    """Type de categorie financiere."""
    INCOME = "INCOME"      # Revenus
    EXPENSE = "EXPENSE"    # Depenses
    TRANSFER = "TRANSFER"  # Transferts internes


class FinanceCategory(Base, TimestampMixin, TenantMixin):
    """
    Categorie de transaction financiere.
    Support hierarchique avec categories parent/enfant.
    """
    __tablename__ = "finance_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[FinanceCategoryType] = mapped_column(
        SQLEnum(FinanceCategoryType, name="finance_category_type"),
        nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship(
        "FinanceEntity",
        back_populates="categories"
    )
    parent: Mapped[Optional["FinanceCategory"]] = relationship(
        "FinanceCategory",
        remote_side="FinanceCategory.id",
        back_populates="children"
    )
    children: Mapped[List["FinanceCategory"]] = relationship(
        "FinanceCategory",
        back_populates="parent",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_finance_categories_entity_type", "entity_id", "type"),
        Index("ix_finance_categories_tenant_entity", "tenant_id", "entity_id"),
        Index("ix_finance_categories_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"<FinanceCategory(id={self.id}, name={self.name}, type={self.type})>"

    @property
    def full_path(self) -> str:
        """Chemin complet de la categorie (parent > enfant)."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    @property
    def level(self) -> int:
        """Niveau dans la hierarchie (0 = racine)."""
        if self.parent:
            return self.parent.level + 1
        return 0

    @property
    def is_leaf(self) -> bool:
        """True si categorie sans enfants."""
        return len(self.children) == 0
