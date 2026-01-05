"""
Models pour l'authentification multi-facteur (MFA/2FA).

Ce module contient les modeles SQLAlchemy pour:
- MFASecret: Secret TOTP pour la generation de codes a usage unique
- MFARecoveryCode: Codes de recuperation a usage unique

Architecture MFA:
1. L'utilisateur configure MFA via /mfa/setup (genere un secret TOTP)
2. Le secret est stocke dans MFASecret (chiffre en production)
3. L'utilisateur scanne le QR code avec une app (Google Authenticator, etc.)
4. A chaque login, l'utilisateur fournit le code TOTP genere par l'app
5. Des codes de recuperation sont fournis en cas de perte de l'app

Securite:
- Le secret TOTP doit etre chiffre en base (AES-256-GCM recommande)
- Les codes de recuperation sont hashes (bcrypt)
- Chaque code de recuperation ne peut etre utilise qu'une fois
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Any, Dict

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Tenant


class MFASecret(Base):
    """
    Stocke le secret TOTP pour l'authentification a deux facteurs.

    Chaque utilisateur ne peut avoir qu'un seul secret MFA (user_id = PK).
    Le secret est utilise pour generer et verifier les codes TOTP.

    Attributs:
        user_id: Cle primaire, FK vers l'utilisateur
        tenant_id: FK vers le tenant pour isolation multi-tenant
        secret: Secret TOTP en base32 (doit etre chiffre en production!)
        enabled: True si MFA est active pour cet utilisateur
        created_at: Timestamp de creation du secret
        last_used_at: Derniere verification TOTP reussie

    Notes:
        - Le secret est en base32 pour compatibilite avec les apps TOTP
        - enabled=False signifie que le secret est configure mais pas active
        - last_used_at permet de detecter les comptes inactifs
    """

    __tablename__ = "mfa_secrets"

    # user_id est la cle primaire (un seul secret par utilisateur)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Reference vers le tenant pour isolation multi-tenant
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Secret TOTP en base32
    # ATTENTION: Doit etre chiffre en production (AES-256-GCM)
    secret: Mapped[str] = mapped_column(Text, nullable=False)

    # Indique si MFA est active pour cet utilisateur
    # False = secret configure mais pas encore valide (setup en cours)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # Timestamp de creation du secret
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Derniere utilisation du MFA (verification reussie)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Dernier window TOTP utilise (anti-replay)
    # TOTP change toutes les 30s, ce champ stocke le numero de window
    # pour empecher la reutilisation du meme code
    last_totp_window: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True
    )

    # Relations
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<MFASecret(user_id={self.user_id}, status='{status}')>"

    @property
    def is_configured(self) -> bool:
        """Retourne True si MFA est configure et active."""
        return self.enabled

    def update_last_used(self) -> None:
        """Met a jour le timestamp de derniere utilisation."""
        self.last_used_at = datetime.now(timezone.utc)

    def to_dict(self, include_secret: bool = False) -> Dict[str, Any]:
        """
        Serialise le secret MFA en dictionnaire.

        Args:
            include_secret: Si True, inclut le secret brut (DANGER!)
                           Utiliser uniquement pendant le setup initial.

        Returns:
            Dict avec les informations MFA (sans secret par defaut)
        """
        data = {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

        if include_secret:
            data["secret"] = self.secret

        return data


class MFARecoveryCode(Base):
    """
    Codes de recuperation a usage unique pour MFA.

    Ces codes permettent de se connecter si l'utilisateur perd acces
    a son app TOTP. Chaque code ne peut etre utilise qu'une fois.

    Attributs:
        id: Cle primaire auto-incrementee
        user_id: FK vers l'utilisateur proprietaire
        tenant_id: FK vers le tenant
        code_hash: Hash bcrypt du code de recuperation
        used_at: Timestamp d'utilisation (NULL si pas utilise)
        created_at: Timestamp de creation

    Notes:
        - 10 codes sont generes par defaut lors de l'activation MFA
        - Le code brut est affiche une seule fois a l'utilisateur
        - Seul le hash est stocke en base (comme un mot de passe)
        - Un code utilise ne peut plus servir (used_at != NULL)
    """

    __tablename__ = "mfa_recovery_codes"

    # Identifiant unique auto-incremente
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Reference vers l'utilisateur proprietaire du code
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Reference vers le tenant pour isolation multi-tenant
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    # Hash bcrypt du code de recuperation
    # Le code brut n'est JAMAIS stocke
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp d'utilisation du code
    # NULL = code valide, non-NULL = code deja utilise
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # Timestamp de creation du code
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relations
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        status = "used" if self.used_at else "valid"
        return f"<MFARecoveryCode(id={self.id}, user_id={self.user_id}, status='{status}')>"

    @property
    def is_used(self) -> bool:
        """Retourne True si le code a deja ete utilise."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Retourne True si le code peut encore etre utilise."""
        return self.used_at is None

    def mark_as_used(self) -> None:
        """Marque le code comme utilise (invalide pour usage futur)."""
        self.used_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise le code de recuperation en dictionnaire.

        Note: Le hash du code n'est JAMAIS expose.

        Returns:
            Dict avec les informations du code (sans le hash)
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "is_used": self.is_used,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
