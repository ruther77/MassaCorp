"""
Model User pour l'authentification et la gestion des utilisateurs
Multi-tenant avec support MFA et SSO
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class User(Base, TimestampMixin):
    """
    Represente un utilisateur du systeme.

    Attributs:
        id: Identifiant unique
        tenant_id: FK vers le tenant
        email: Email unique par tenant
        password_hash: Hash bcrypt du mot de passe (NULL si SSO-only)
        is_active: Compte actif ou desactive
        is_verified: Email verifie
        is_superuser: Droits administrateur
        first_name: Prenom (optionnel)
        last_name: Nom (optionnel)
        phone: Telephone (optionnel)
        last_login_at: Derniere connexion
        password_changed_at: Dernier changement de mot de passe
    """

    __tablename__ = "users"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # FK vers tenant
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Authentification
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Etat du compte
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Force MFA apres compromission suspecte
    # Si True, l'utilisateur doit activer le MFA avant de pouvoir continuer
    mfa_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Profil
    first_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps supplementaires
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relations
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users"
    )

    # Index unique sur (tenant_id, email) defini en DB
    __table_args__ = (
        # L'unicite est deja definie dans la migration SQL
        # On garde juste une reference pour la documentation
        {"comment": "Utilisateurs du systeme avec isolation multi-tenant"},
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', tenant_id={self.tenant_id})>"

    @property
    def full_name(self) -> str:
        """Retourne le nom complet ou l'email si non renseigne"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email.split("@")[0]

    @property
    def has_password(self) -> bool:
        """Verifie si l'utilisateur a un mot de passe (vs SSO-only)"""
        return self.password_hash is not None

    @property
    def can_login(self) -> bool:
        """Verifie si l'utilisateur peut se connecter"""
        return self.is_active and self.is_verified

    def update_last_login(self) -> None:
        """Met a jour la date de derniere connexion"""
        self.last_login_at = datetime.now(timezone.utc)

    def update_password_timestamp(self) -> None:
        """Met a jour la date de changement de mot de passe"""
        self.password_changed_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        """Desactive le compte utilisateur"""
        self.is_active = False

    def activate(self) -> None:
        """Active le compte utilisateur"""
        self.is_active = True

    def verify_email(self) -> None:
        """Marque l'email comme verifie"""
        self.is_verified = True

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Serialise l'utilisateur en dictionnaire.

        Args:
            include_sensitive: Inclure les champs sensibles (admin only)
        """
        data = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "email": self.email,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

        if include_sensitive:
            data.update({
                "is_superuser": self.is_superuser,
                "phone": self.phone,
                "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
                "password_changed_at": self.password_changed_at.isoformat() if self.password_changed_at else None,
                "has_password": self.has_password,
                "mfa_required": self.mfa_required,
            })

        return data
