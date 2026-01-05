"""
Model Tenant pour l'isolation multi-tenant
Chaque tenant represente une organisation/entreprise
"""
from typing import TYPE_CHECKING, List, Optional, Any

from sqlalchemy import BigInteger, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.rbac import Role


class Tenant(Base, TimestampMixin):
    """
    Represente un tenant (organisation/entreprise).

    Chaque tenant a ses propres utilisateurs, roles, etc.
    L'isolation est assuree par tenant_id sur toutes les tables.
    """

    __tablename__ = "tenants"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Nom affichable du tenant
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Slug unique pour URLs et identification
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)

    # Etat du tenant
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Configuration JSON flexible
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)

    # Relations
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="tenant",
        lazy="dynamic"
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        back_populates="tenant",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"

    def to_dict(self) -> dict:
        """Serialise le tenant en dictionnaire"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "is_active": self.is_active,
            "settings": self.settings or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def user_count(self) -> int:
        """Nombre d'utilisateurs actifs dans ce tenant"""
        return self.users.filter_by(is_active=True).count()

    def deactivate(self) -> None:
        """Desactive le tenant et tous ses utilisateurs"""
        self.is_active = False

    def activate(self) -> None:
        """Reactive le tenant"""
        self.is_active = True
