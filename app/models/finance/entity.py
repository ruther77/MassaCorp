"""
FinanceEntity - Entite financiere (societe, etablissement).
Support multi-entites pour groupes avec plusieurs structures.
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.finance.account import FinanceAccount
    from app.models.finance.category import FinanceCategory


class FinanceEntity(Base, TimestampMixin, TenantMixin):
    """
    Entite financiere - represente une societe ou un etablissement.
    Permet de gerer plusieurs entites juridiques au sein d'un meme tenant.
    """
    __tablename__ = "finance_entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, default="EUR", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Informations legales optionnelles
    siret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    members: Mapped[List["FinanceEntityMember"]] = relationship(
        "FinanceEntityMember",
        back_populates="entity",
        lazy="selectin"
    )
    accounts: Mapped[List["FinanceAccount"]] = relationship(
        "FinanceAccount",
        back_populates="entity",
        lazy="selectin"
    )
    categories: Mapped[List["FinanceCategory"]] = relationship(
        "FinanceCategory",
        back_populates="entity",
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_finance_entities_tenant_name", "tenant_id", "name"),
        Index("ix_finance_entities_tenant_code", "tenant_id", "code", unique=True),
        Index("ix_finance_entities_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<FinanceEntity(id={self.id}, code={self.code}, name={self.name})>"

    @property
    def display_name(self) -> str:
        """Nom d'affichage avec code."""
        return f"{self.code} - {self.name}"


class FinanceEntityMember(Base, TimestampMixin):
    """
    Membre d'une entite financiere.
    Lie un utilisateur a une entite avec un role specifique.
    """
    __tablename__ = "finance_entity_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(Text, default="viewer", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relations
    entity: Mapped["FinanceEntity"] = relationship(
        "FinanceEntity",
        back_populates="members"
    )
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index(
            "ix_finance_entity_members_entity_user",
            "entity_id", "user_id",
            unique=True
        ),
    )

    def __repr__(self) -> str:
        return f"<FinanceEntityMember(entity_id={self.entity_id}, user_id={self.user_id})>"
