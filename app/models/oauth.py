"""
Model OAuthAccount pour l'authentification sociale
Support Google, Facebook, GitHub, etc.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class OAuthAccount(Base, TimestampMixin):
    """
    Represente un compte OAuth lie a un utilisateur.

    Permet a un utilisateur de se connecter via Google, Facebook, GitHub, etc.
    Un utilisateur peut avoir plusieurs comptes OAuth (un par provider).

    Attributs:
        id: Identifiant unique
        user_id: FK vers l'utilisateur (peut etre NULL pour inscription en cours)
        provider: Nom du provider ('google', 'facebook', 'github')
        provider_user_id: ID unique de l'utilisateur chez le provider
        email: Email du compte OAuth
        name: Nom complet du provider
        avatar_url: URL de l'avatar
        access_token: Token d'acces OAuth (chiffre)
        refresh_token: Token de refresh OAuth (chiffre)
        expires_at: Date d'expiration du token
    """

    __tablename__ = "oauth_accounts"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # FK vers user (peut etre NULL si inscription en cours)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Tenant pour isolation multi-tenant
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Provider info
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)

    # Profil du provider
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tokens OAuth (stockes chiffres en production)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relations
    user: Mapped[Optional["User"]] = relationship(
        "User",
        backref="oauth_accounts"
    )

    # Contraintes
    __table_args__ = (
        # Un seul compte par provider par tenant
        UniqueConstraint('provider', 'provider_user_id', 'tenant_id', name='uq_oauth_provider_user_tenant'),
        {"comment": "Comptes OAuth pour authentification sociale"},
    )

    def __repr__(self) -> str:
        return f"<OAuthAccount(id={self.id}, provider='{self.provider}', user_id={self.user_id})>"

    @property
    def is_linked(self) -> bool:
        """Verifie si le compte OAuth est lie a un utilisateur"""
        return self.user_id is not None

    @property
    def is_token_expired(self) -> bool:
        """Verifie si le token est expire"""
        if self.expires_at is None:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        """Serialise le compte OAuth (sans les tokens)"""
        return {
            "id": self.id,
            "provider": self.provider,
            "email": self.email,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "is_linked": self.is_linked,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
