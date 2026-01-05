"""
Models pour l'audit et la securite de l'application.

Ce module contient les modeles SQLAlchemy pour:
- AuditLog: Journal d'audit des actions sensibles (connexions, modifications, etc.)
- LoginAttempt: Historique des tentatives de connexion pour detection d'attaques brute-force

Ces modeles sont essentiels pour la conformite RGPD et la securite du systeme.
Ils permettent de tracer toutes les actions sensibles et de detecter les comportements suspects.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Tenant
    from app.models.session import Session


class AuditLog(Base):
    """
    Journal d'audit pour tracer toutes les actions sensibles du systeme.

    Ce modele enregistre les evenements de securite tels que:
    - Connexions reussies/echouees
    - Modifications de mot de passe
    - Changements de roles/permissions
    - Operations administratives sensibles
    - Acces aux donnees sensibles

    Attributs:
        id: Identifiant unique auto-incremente
        event_type: Type d'evenement (ex: LOGIN, LOGOUT, PASSWORD_CHANGE, etc.)
        user_id: FK vers l'utilisateur concerne (optionnel si action anonyme)
        tenant_id: FK vers le tenant concerne (optionnel)
        session_id: ID de la session associee (optionnel)
        ip: Adresse IP de l'origine de l'action
        user_agent: User-Agent du navigateur/client
        success: Indique si l'action a reussi ou echoue
        metadata: Donnees supplementaires au format JSON (details de l'action)
        created_at: Timestamp de l'evenement

    Notes:
        - Les logs d'audit ne doivent JAMAIS etre supprimes (retention legale)
        - Les relations user/tenant ont ON DELETE SET NULL pour preserver l'historique
        - Le champ metadata peut contenir des informations contextuelles variables
    """

    __tablename__ = "audit_log"

    # Identifiant unique auto-incremente
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Type d'evenement (ex: LOGIN, LOGOUT, PASSWORD_CHANGE, ROLE_UPDATE, etc.)
    # Utilise pour filtrer et categoriser les logs
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Reference vers l'utilisateur concerne par l'action
    # Nullable car certaines actions peuvent etre anonymes (tentative de login avec email inconnu)
    # ON DELETE SET NULL preserve l'historique meme si l'utilisateur est supprime
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Reference vers le tenant concerne
    # Nullable pour les actions systeme non liees a un tenant specifique
    # ON DELETE SET NULL preserve l'historique
    tenant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Reference vers la session active au moment de l'action
    # Permet de corréler plusieurs actions a une meme session
    session_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True
    )

    # Adresse IP d'origine de l'action (IPv4 ou IPv6)
    # Essentiel pour la detection de comportements suspects
    ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # User-Agent du client HTTP
    # Aide a identifier le type de client et detecter les anomalies
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Indicateur de succes/echec de l'action
    # Ex: login reussi vs login echoue (mauvais mot de passe)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Donnees supplementaires en JSON pour stocker des details variables
    # Ex: ancien/nouveau role, raison d'echec, resource modifiee, etc.
    # Note: Le nom de colonne en DB est 'metadata', mais on utilise 'extra_data' en Python
    # car 'metadata' est un nom reserve par SQLAlchemy DeclarativeBase
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Nom de la colonne en base de donnees
        JSONB,
        nullable=True
    )

    # Timestamp de l'evenement avec timezone UTC
    # Defini automatiquement par le serveur DB
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Relations pour faciliter les requetes ORM
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped[Optional["Tenant"]] = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, event_type='{self.event_type}', success={self.success})>"

    def to_dict(self) -> dict:
        """
        Serialise l'entree d'audit en dictionnaire.
        Utilise pour les API de consultation des logs.
        """
        return {
            "id": self.id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "session_id": str(self.session_id) if self.session_id else None,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "success": self.success,
            "metadata": self.extra_data,  # Retourne sous le nom 'metadata' pour l'API
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LoginAttempt(Base):
    """
    Enregistre toutes les tentatives de connexion (reussies ou echouees).

    Ce modele est utilise pour:
    - Detection des attaques brute-force sur les comptes
    - Rate limiting base sur IP ou identifiant
    - Analyse des patterns de connexion suspects
    - Blocage temporaire apres N echecs consecutifs

    Attributs:
        id: Identifiant unique auto-incremente
        identifier: Email ou username utilise pour la tentative
        ip: Adresse IP d'origine de la tentative
        attempted_at: Timestamp de la tentative
        success: Indique si la connexion a reussi

    Notes:
        - Cette table peut contenir beaucoup d'enregistrements, prevoir une purge periodique
        - Les index sur identifier et ip sont essentiels pour les requetes de rate limiting
        - Les donnees peuvent etre agregees/archivees apres une periode de retention
    """

    __tablename__ = "login_attempts"

    # Identifiant unique auto-incremente
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Identifiant utilise pour la tentative (email ou username)
    # Peut ne pas correspondre a un utilisateur existant (tentative avec email inconnu)
    identifier: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Adresse IP d'origine de la tentative (IPv4 ou IPv6)
    # Essentiel pour le rate limiting par IP
    ip: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Timestamp de la tentative avec timezone UTC
    # L'index sur ce champ est crucial pour les requetes de fenetre temporelle
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    # Resultat de la tentative: True = connexion reussie, False = echec
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:
        return f"<LoginAttempt(id={self.id}, identifier='{self.identifier}', success={self.success})>"

    def to_dict(self) -> dict:
        """
        Serialise la tentative de connexion en dictionnaire.
        Attention: ne pas exposer ces donnees aux utilisateurs standards.
        """
        return {
            "id": self.id,
            "identifier": self.identifier,
            "ip": self.ip,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
            "success": self.success,
        }
