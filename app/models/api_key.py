"""
Model pour les API Keys (authentification Machine-to-Machine).

Securite:
- Key hashee en DB (SHA-256) - jamais stockee en clair
- Expiration configurable
- Revocation possible
- Isolation par tenant
- Scopes limites (least privilege)
- Usage logging pour audit
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


# Scopes disponibles pour les API Keys
class APIKeyScopes:
    """
    Scopes disponibles pour les API Keys.

    Principe du least privilege: une key ne devrait avoir
    que les scopes strictement necessaires.
    """
    # Lecture seule
    READ_USERS = "users:read"
    READ_SESSIONS = "sessions:read"
    READ_AUDIT = "audit:read"

    # Ecriture
    WRITE_USERS = "users:write"
    WRITE_SESSIONS = "sessions:write"

    # Administration
    ADMIN_USERS = "users:admin"
    ADMIN_TENANT = "tenant:admin"

    # Scope special: tous les droits
    ADMIN_ALL = "*"

    @classmethod
    def all_scopes(cls) -> List[str]:
        """Retourne tous les scopes disponibles."""
        return [
            cls.READ_USERS, cls.READ_SESSIONS, cls.READ_AUDIT,
            cls.WRITE_USERS, cls.WRITE_SESSIONS,
            cls.ADMIN_USERS, cls.ADMIN_TENANT, cls.ADMIN_ALL
        ]

    @classmethod
    def validate_scopes(cls, scopes: List[str]) -> bool:
        """Valide que tous les scopes sont connus."""
        valid_scopes = set(cls.all_scopes())
        return all(scope in valid_scopes for scope in scopes)


class APIKey(Base):
    """
    API Key pour authentification M2M.

    Attributs:
        id: Identifiant unique
        tenant_id: FK vers le tenant
        name: Nom descriptif de la key
        key_hash: Hash SHA-256 de la key (jamais la key brute)
        key_prefix: Premiers caracteres pour identification (ex: "mc_")
        expires_at: Date d'expiration (optionnel)
        revoked_at: Timestamp de revocation (NULL si active)
        last_used_at: Derniere utilisation
        created_at: Timestamp de creation
        created_by_user_id: User qui a cree la key

    Notes:
        - La key brute n'est affichee qu'une seule fois a la creation
        - Seul le hash est stocke en base
        - Une key peut etre revoquee ou expirer
    """

    __tablename__ = "api_keys"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Reference vers le tenant
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Nom descriptif
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Hash SHA-256 de la key (pas la key brute!)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Prefix de la key pour identification visuelle (ex: "mc_abc...")
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)

    # Date d'expiration (optionnel)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # Timestamp de revocation (NULL = active)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Derniere utilisation
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Timestamp de creation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # User qui a cree la key (optionnel)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Scopes autorises pour cette key (least privilege)
    # Format: ["users:read", "sessions:read"] ou ["*"] pour admin
    scopes: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Scopes autorises - null = tous les droits (legacy)"
    )

    # Relations
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        status = "revoked" if self.revoked_at else "active"
        return f"<APIKey(id={self.id}, name='{self.name}', status='{status}')>"

    @property
    def is_valid(self) -> bool:
        """Verifie si la key est valide (non revoquee et non expiree)."""
        from datetime import datetime, timezone

        if self.revoked_at is not None:
            return False
        if self.expires_at and self.expires_at <= datetime.now(timezone.utc):
            return False
        return True

    @property
    def is_revoked(self) -> bool:
        """Verifie si la key est revoquee."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Verifie si la key a expire."""
        from datetime import datetime, timezone
        if not self.expires_at:
            return False
        return self.expires_at <= datetime.now(timezone.utc)

    def revoke(self) -> None:
        """Revoque la key."""
        from datetime import datetime, timezone
        self.revoked_at = datetime.now(timezone.utc)

    def update_last_used(self) -> None:
        """Met a jour le timestamp de derniere utilisation."""
        from datetime import datetime, timezone
        self.last_used_at = datetime.now(timezone.utc)

    def has_scope(self, required_scope: str) -> bool:
        """
        Verifie si la key a le scope requis.

        Args:
            required_scope: Scope requis (ex: "users:read")

        Returns:
            True si le scope est autorise
        """
        # Keys legacy sans scopes = tous les droits
        if self.scopes is None:
            return True

        # Scope admin = tous les droits
        if APIKeyScopes.ADMIN_ALL in self.scopes:
            return True

        # Verifier le scope exact
        if required_scope in self.scopes:
            return True

        # Verifier les scopes hierarchiques (users:admin inclut users:read)
        if ":" in required_scope:
            resource, action = required_scope.split(":", 1)
            admin_scope = f"{resource}:admin"
            if admin_scope in self.scopes:
                return True

        return False

    def has_any_scope(self, required_scopes: List[str]) -> bool:
        """Verifie si la key a au moins un des scopes requis."""
        return any(self.has_scope(scope) for scope in required_scopes)

    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """Verifie si la key a tous les scopes requis."""
        return all(self.has_scope(scope) for scope in required_scopes)

    def to_dict(self, include_hash: bool = False) -> dict:
        """Serialise la key (sans le hash par defaut)."""
        data = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_valid": self.is_valid,
        }
        if include_hash:
            data["key_hash"] = self.key_hash
        return data


class APIKeyUsage(Base):
    """
    Log d'utilisation des API Keys.

    Chaque requete authentifiee par API Key est loguee ici.
    Permet:
    - Audit des usages
    - Detection d'anomalies
    - Rate limiting par key
    - Analytics d'utilisation
    """

    __tablename__ = "api_key_usage"

    # Identifiant unique
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Reference vers l'API Key
    api_key_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Tenant pour isolation
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Timestamp de l'utilisation
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Endpoint appele
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)

    # Methode HTTP
    method: Mapped[str] = mapped_column(Text, nullable=False)

    # Adresse IP source
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User-Agent
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Code de reponse HTTP
    response_status: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Temps de reponse en ms
    response_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Relations
    api_key: Mapped["APIKey"] = relationship("APIKey", foreign_keys=[api_key_id])

    def __repr__(self) -> str:
        return f"<APIKeyUsage(key_id={self.api_key_id}, endpoint='{self.endpoint}')>"
