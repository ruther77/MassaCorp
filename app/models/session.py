"""
Models pour la gestion des sessions et tokens d'authentification.

Ce module contient les modeles SQLAlchemy pour:
- Session: Sessions utilisateur actives avec suivi d'activite
- RefreshToken: Tokens de rafraichissement pour renouveler les access tokens
- RevokedToken: Blacklist des tokens JWT revoques (logout, compromis, etc.)

Architecture d'authentification:
1. L'utilisateur se connecte et recoit un access token (courte duree) + refresh token
2. La Session represente la connexion active de l'utilisateur
3. Le RefreshToken permet de renouveler l'access token sans re-authentification
4. Lors d'un logout ou revocation, le token est ajoute a RevokedToken

Cette architecture permet une gestion fine des sessions avec possibilite de:
- Voir toutes les sessions actives d'un utilisateur
- Revoquer des sessions specifiques ou toutes les sessions
- Detecter la reutilisation de tokens voles (rotation)
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Tenant


class Session(Base):
    """
    Represente une session utilisateur active.

    Une session est creee lors de chaque connexion reussie et contient les
    informations de contexte (IP, user-agent). Elle peut etre explicitement
    revoquee (logout) ou expirer naturellement.

    Attributs:
        id: UUID unique de la session (utilise dans les tokens JWT)
        user_id: FK vers l'utilisateur proprietaire de la session
        tenant_id: FK vers le tenant pour l'isolation multi-tenant
        created_at: Timestamp de creation de la session
        last_seen_at: Derniere activite sur cette session
        ip: Adresse IP de la connexion initiale
        user_agent: User-Agent du navigateur/client
        revoked_at: Timestamp de revocation (NULL si session active)

    Notes:
        - L'ID est un UUID pour eviter les attaques par enumeration
        - last_seen_at est mis a jour a chaque rafraichissement de token
        - Une session revoquee (revoked_at != NULL) ne peut plus etre utilisee
        - ON DELETE CASCADE: la suppression de l'utilisateur supprime ses sessions
    """

    __tablename__ = "sessions"

    # UUID unique de la session
    # Utilise comme identifiant dans les tokens JWT (claim 'sid')
    # L'UUID evite les attaques par enumeration sequentielle
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)

    # Reference vers l'utilisateur proprietaire de cette session
    # ON DELETE CASCADE: si l'utilisateur est supprime, ses sessions aussi
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Reference vers le tenant pour isolation multi-tenant
    # Permet de lister/revoquer toutes les sessions d'un tenant
    # ON DELETE CASCADE: suppression du tenant = suppression des sessions
    tenant_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Timestamp de creation de la session (moment de la connexion)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Timestamp de derniere modification
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Derniere activite detectee sur cette session
    # Mis a jour lors du rafraichissement du token ou de requetes actives
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Adresse IP lors de la creation de la session
    # Peut etre utilisee pour detecter les connexions suspectes
    ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User-Agent du client lors de la connexion
    # Aide a identifier le type d'appareil (mobile, desktop, etc.)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp de revocation de la session
    # NULL = session active, non-NULL = session revoquee (logout/force-logout)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # Date d'expiration absolue de la session (30 jours apres creation)
    # Cette date ne change JAMAIS meme avec rotation de tokens
    # Garantit qu'une session ne peut pas etre etendue indefiniment
    absolute_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,  # Nullable pour compatibilite avec sessions existantes
        index=True
    )

    # Relations
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        status = "revoked" if self.revoked_at else "active"
        return f"<Session(id={self.id}, user_id={self.user_id}, status='{status}')>"

    @property
    def is_active(self) -> bool:
        """
        Verifie si la session est toujours active.

        Une session est active si:
        - Elle n'a pas ete revoquee (revoked_at is None)
        - Elle n'a pas depasse son expiration absolue (si definie)
        """
        if self.revoked_at is not None:
            return False
        if self.absolute_expiry is not None:
            now = datetime.now(timezone.utc)
            if self.absolute_expiry <= now:
                return False
        return True

    @property
    def is_absolute_expired(self) -> bool:
        """
        Verifie si la session a depasse son expiration absolue.

        L'expiration absolue est une limite dure de 30 jours qui ne peut
        pas etre etendue par rotation de tokens.
        """
        if self.absolute_expiry is None:
            return False
        now = datetime.now(timezone.utc)
        return self.absolute_expiry <= now

    def revoke(self) -> None:
        """Revoque la session (logout)"""
        from datetime import datetime, timezone
        self.revoked_at = datetime.now(timezone.utc)

    def update_last_seen(self) -> None:
        """Met a jour le timestamp de derniere activite"""
        from datetime import datetime, timezone
        self.last_seen_at = datetime.now(timezone.utc)

    def to_dict(self, include_tokens: bool = False) -> dict:
        """
        Serialise la session en dictionnaire.

        Args:
            include_tokens: Inclure les refresh tokens associes (admin only)
        """
        data = {
            "id": str(self.id),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "is_active": self.is_active,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "absolute_expiry": self.absolute_expiry.isoformat() if self.absolute_expiry else None,
        }

        if include_tokens and self.refresh_tokens:
            data["refresh_tokens"] = [rt.to_dict() for rt in self.refresh_tokens]

        return data


class RefreshToken(Base):
    """
    Token de rafraichissement pour renouveler les access tokens JWT.

    Les refresh tokens ont une duree de vie plus longue que les access tokens
    et permettent d'obtenir de nouveaux access tokens sans re-authentification.

    Securite implementee:
    - Rotation des tokens: chaque utilisation genere un nouveau refresh token
    - Detection de reutilisation: si un token utilise est reutilise, toute la session est compromise
    - Hachage du token: seul le hash est stocke en base (comme un mot de passe)

    Attributs:
        jti: JWT ID unique (cle primaire, identifiant du token dans le JWT)
        session_id: FK vers la session associee
        token_hash: Hash bcrypt/argon2 du token (le token brut n'est jamais stocke)
        expires_at: Date d'expiration du token
        created_at: Timestamp de creation
        used_at: Timestamp d'utilisation (NULL si pas encore utilise)
        replaced_by_jti: JTI du token de remplacement apres rotation

    Notes:
        - La cle primaire est le JTI (pas d'auto-increment pour eviter l'enumeration)
        - Un token utilise (used_at != NULL) ne peut plus servir a rafraichir
        - Si replaced_by_jti est defini, le token a ete remplace lors d'une rotation
    """

    __tablename__ = "refresh_tokens"

    # JWT ID unique - identifiant du token dans le payload JWT
    # Utilise comme cle primaire pour eviter l'enumeration
    jti: Mapped[str] = mapped_column(Text, primary_key=True)

    # Reference vers la session associee (nullable pour éviter les conflits de transaction)
    # ON DELETE CASCADE: suppression de la session = suppression des tokens
    session_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Hash du token de rafraichissement
    # Le token brut est envoye au client, seul le hash est stocke
    # Protege contre les fuites de base de donnees
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Date/heure d'expiration du token
    # Apres cette date, le token ne peut plus etre utilise
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Timestamp de creation du token
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Timestamp d'utilisation du token (rotation)
    # NULL = token pas encore utilise, non-NULL = token deja consomme
    # Un token consomme ne peut plus etre utilise (one-time use)
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # JTI du token qui a remplace celui-ci lors de la rotation
    # Permet de tracer la chaine de tokens
    # Si un token est reutilise apres remplacement, c'est une attaque
    replaced_by_jti: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relation vers la session parente
    session: Mapped["Session"] = relationship(
        "Session",
        back_populates="refresh_tokens"
    )

    def __repr__(self) -> str:
        status = "used" if self.used_at else "active"
        return f"<RefreshToken(jti='{self.jti[:8]}...', status='{status}')>"

    @property
    def is_valid(self) -> bool:
        """
        Verifie si le token est valide (non utilise et non expire).
        Note: Ne verifie pas la revocation de la session associee.
        """
        from datetime import datetime, timezone
        if self.used_at is not None:
            return False
        return self.expires_at > datetime.now(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Verifie si le token a expire"""
        from datetime import datetime, timezone
        return self.expires_at <= datetime.now(timezone.utc)

    def mark_as_used(self, replaced_by: Optional[str] = None) -> None:
        """
        Marque le token comme utilise lors d'une rotation.

        Args:
            replaced_by: JTI du nouveau token qui remplace celui-ci
        """
        from datetime import datetime, timezone
        self.used_at = datetime.now(timezone.utc)
        if replaced_by:
            self.replaced_by_jti = replaced_by

    def to_dict(self) -> dict:
        """
        Serialise le token en dictionnaire.
        Attention: ne jamais exposer token_hash!
        """
        return {
            "jti": self.jti,
            "session_id": str(self.session_id),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "is_valid": self.is_valid,
            "replaced_by_jti": self.replaced_by_jti,
        }


class RevokedToken(Base):
    """
    Blacklist des tokens JWT revoques.

    Quand un token doit etre invalide avant son expiration naturelle
    (logout, compromission, changement de mot de passe, etc.), son JTI
    est ajoute a cette table.

    Lors de chaque verification de token, on verifie que le JTI n'est pas
    dans cette blacklist.

    Attributs:
        jti: JWT ID du token revoque (cle primaire)
        expires_at: Date d'expiration originale du token
        revoked_at: Timestamp de la revocation

    Notes:
        - Les entrees peuvent etre purgees apres expires_at (le token serait invalide de toute facon)
        - Cette table doit etre indexee et optimisee pour les lectures frequentes
        - Envisager un cache Redis pour les performances en production
    """

    __tablename__ = "revoked_tokens"

    # JWT ID du token revoque - cle primaire
    # Correspond au claim 'jti' dans le payload JWT
    jti: Mapped[str] = mapped_column(Text, primary_key=True)

    # Date d'expiration originale du token
    # Permet de purger les entrees obsoletes (token expire de toute facon)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Timestamp de la revocation
    # Peut etre utile pour l'audit et le debug
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<RevokedToken(jti='{self.jti[:8]}...', revoked_at={self.revoked_at})>"

    @property
    def can_be_purged(self) -> bool:
        """
        Verifie si l'entree peut etre purgee de la blacklist.
        Un token expire n'a plus besoin d'etre dans la blacklist.
        """
        from datetime import datetime, timezone
        return self.expires_at <= datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialise l'entree en dictionnaire"""
        return {
            "jti": self.jti,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }
