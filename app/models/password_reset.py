"""
Model pour les tokens de reinitialisation de mot de passe.

Securite:
- Token hashe en DB (SHA-256) - jamais stocke en clair
- Expiration courte (1 heure)
- Usage unique (used_at marque l'utilisation)
- Rate limiting (max 3 demandes/heure/email)
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PasswordResetToken(Base):
    """
    Token de reinitialisation de mot de passe.

    Attributs:
        id: Identifiant unique
        user_id: FK vers l'utilisateur
        token_hash: Hash SHA-256 du token (jamais le token brut)
        expires_at: Date d'expiration (1 heure apres creation)
        used_at: Timestamp d'utilisation (NULL si pas encore utilise)
        created_at: Timestamp de creation

    Notes:
        - Le token brut est envoye par email, seul le hash est stocke
        - Un token utilise (used_at != NULL) ne peut plus servir
        - Les tokens expires peuvent etre purges periodiquement
    """

    __tablename__ = "password_reset_tokens"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Reference vers l'utilisateur
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Hash SHA-256 du token (pas le token brut!)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Date d'expiration du token
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Timestamp d'utilisation (NULL = pas encore utilise)
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Timestamp de creation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relation vers l'utilisateur
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        status = "used" if self.used_at else "active"
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, status='{status}')>"

    @property
    def is_valid(self) -> bool:
        """Verifie si le token est valide (non utilise et non expire)."""
        from datetime import datetime, timezone
        if self.used_at is not None:
            return False
        return self.expires_at > datetime.now(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Verifie si le token a expire."""
        from datetime import datetime, timezone
        return self.expires_at <= datetime.now(timezone.utc)

    @property
    def is_used(self) -> bool:
        """Verifie si le token a deja ete utilise."""
        return self.used_at is not None

    def mark_as_used(self) -> None:
        """Marque le token comme utilise."""
        from datetime import datetime, timezone
        self.used_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialise le token (sans le hash)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "is_valid": self.is_valid,
        }
