"""
Classes de base et mixins pour les modeles SQLAlchemy
Multi-tenant avec timestamps automatiques
Compatible SQLAlchemy 2.0 avec Mapped types
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base pour tous les modeles SQLAlchemy"""
    pass


class TimestampMixin:
    """
    Mixin pour ajouter created_at et updated_at automatiques.
    updated_at est mis a jour automatiquement a chaque modification.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class TenantMixin:
    """
    Mixin pour l'isolation multi-tenant.
    Toutes les tables tenant-aware heritent de ce mixin.
    """
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True
    )


class SoftDeleteMixin:
    """
    Mixin pour la suppression logique.
    Les enregistrements ne sont pas supprimes mais marques.
    """
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    def soft_delete(self) -> None:
        """Marque l'enregistrement comme supprime"""
        self.is_active = False

    def restore(self) -> None:
        """Restaure un enregistrement supprime"""
        self.is_active = True


def utc_now() -> datetime:
    """Retourne l'heure actuelle en UTC (timezone-aware)"""
    return datetime.now(timezone.utc)
