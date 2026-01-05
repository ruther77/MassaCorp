"""
Service de gestion des Tokens pour MassaCorp.

Ce module fournit le service de gestion des refresh tokens JWT. Il permet de:
- Stocker et valider les refresh tokens
- Revoquer des tokens individuels ou tous les tokens d'un user
- Detecter les attaques de replay (reutilisation de tokens)
- Implementer la rotation de tokens

Le service assure la securite des tokens avec blacklist et hachage.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from app.core.security import hash_token, verify_token_hash
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.revoked_token import RevokedTokenRepository
from app.services.exceptions import ServiceException, TokenRevokedError


class TokenNotFoundError(ServiceException):
    """Token non trouve"""

    def __init__(self, jti: str = None):
        super().__init__(
            message="Token non trouve",
            code="TOKEN_NOT_FOUND"
        )
        self.jti = jti


# TokenRevokedError est importe de exceptions.py pour eviter la duplication


class TokenExpiredError(ServiceException):
    """Token expire"""

    def __init__(self, jti: str = None):
        super().__init__(
            message="Ce token a expire",
            code="TOKEN_EXPIRED"
        )
        self.jti = jti


class TokenReplayDetectedError(ServiceException):
    """Attaque de replay detectee"""

    def __init__(self, jti: str = None):
        super().__init__(
            message="Reutilisation de token detectee - possible compromission",
            code="TOKEN_REPLAY_DETECTED"
        )
        self.jti = jti


class SessionAbsolutelyExpiredError(ServiceException):
    """Session a depasse son expiration absolue (30 jours max)"""

    def __init__(self, session_id: str = None):
        super().__init__(
            message="Session expiree - reconnexion requise (limite de 30 jours atteinte)",
            code="SESSION_ABSOLUTE_EXPIRED"
        )
        self.session_id = session_id


class TokenService:
    """
    Service pour la gestion des refresh tokens.

    Gere le stockage, la validation et la revocation des tokens
    avec detection d'attaques.
    """

    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        revoked_token_repository: RevokedTokenRepository
    ):
        """
        Initialise le service avec les repositories necessaires.

        Args:
            refresh_token_repository: Repository pour les refresh tokens
            revoked_token_repository: Repository pour la blacklist
        """
        self.refresh_token_repository = refresh_token_repository
        self.revoked_token_repository = revoked_token_repository

    def store_refresh_token(
        self,
        jti: str,
        user_id: int,
        tenant_id: int,
        expires_at: datetime,
        session_id: Optional[str] = None,
        raw_token: Optional[str] = None,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_absolute_expiry: Optional[datetime] = None
    ) -> Any:
        """
        Stocke un nouveau refresh token.

        Le token brut est hashe avec SHA256 avant stockage.
        Le token original n'est JAMAIS stocke en base de donnees.

        Args:
            jti: JWT ID unique du token
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            expires_at: Date d'expiration
            session_id: ID de la session (OBLIGATOIRE)
            raw_token: Token brut a hasher (OBLIGATOIRE)
            device_name: Nom du device
            ip_address: Adresse IP
            user_agent: User-Agent
            session_absolute_expiry: Expiration absolue de la session (limite dure)

        Returns:
            Le token stocke

        Raises:
            ValueError: Si expires_at est dans le passe, session_id manquant ou raw_token manquant
            SessionAbsolutelyExpiredError: Si la session a depasse son expiration absolue
        """
        # Validation du session_id - OBLIGATOIRE
        if not session_id:
            raise ValueError("session_id est obligatoire pour le stockage du token")
        now = datetime.now(timezone.utc)

        # Verifier l'expiration absolue de la session
        if session_absolute_expiry is not None and session_absolute_expiry <= now:
            logger.warning(
                f"Tentative de creation de token pour session expiree absolument: "
                f"session_id={session_id}, absolute_expiry={session_absolute_expiry}"
            )
            raise SessionAbsolutelyExpiredError(session_id=session_id)

        # Valider l'expiration
        if expires_at <= now:
            raise ValueError("expires_at doit etre dans le futur")

        # Limiter l'expiration max a 30 jours
        max_expiry = now + timedelta(days=30)
        if expires_at > max_expiry:
            expires_at = max_expiry

        # SECURITE: Limiter aussi par l'expiration absolue de la session
        # Le token ne peut pas expirer apres la session
        if session_absolute_expiry is not None and expires_at > session_absolute_expiry:
            logger.debug(
                f"Token expires_at ({expires_at}) limite par session_absolute_expiry "
                f"({session_absolute_expiry})"
            )
            expires_at = session_absolute_expiry

        # Hasher le token brut - OBLIGATOIRE pour la securite
        if not raw_token:
            raise ValueError("raw_token est obligatoire pour le stockage securise")

        token_hash = hash_token(raw_token)

        return self.refresh_token_repository.store_token(
            jti=jti,
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=expires_at,
            session_id=session_id,
            token_hash=token_hash,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def validate_refresh_token(self, jti: str) -> bool:
        """
        Valide un refresh token.

        Verifie:
        - Le token existe
        - Il n'est pas utilise/revoque
        - Il n'est pas expire
        - Il n'est pas dans la blacklist

        Args:
            jti: JWT ID du token

        Returns:
            True si le token est valide
        """
        # Verifier la blacklist d'abord (plus rapide)
        if self.revoked_token_repository.is_revoked(jti):
            return False

        # Verifier le token dans la DB
        return self.refresh_token_repository.is_valid(jti)

    def verify_refresh_token(self, jti: str, raw_token: str) -> bool:
        """
        Verifie un refresh token par comparaison de hash.

        Compare le hash du token brut fourni avec le hash stocke en base.
        Cette methode est resistante aux timing attacks.

        Args:
            jti: JWT ID du token
            raw_token: Token brut a verifier

        Returns:
            True si le token est valide et correspond au hash stocke
        """
        # Recuperer le token stocke
        stored_token = self.refresh_token_repository.get_by_jti(jti)

        if stored_token is None:
            return False

        # Verifier que le token n'a pas ete utilise
        if stored_token.used_at is not None:
            return False

        # Verifier l'expiration
        now = datetime.now(timezone.utc)
        if stored_token.expires_at <= now:
            return False

        # Verifier le hash du token
        return verify_token_hash(raw_token, stored_token.token_hash)

    def revoke_refresh_token(
        self,
        jti: str,
        add_to_blacklist: bool = True
    ) -> bool:
        """
        Revoque un refresh token.

        Args:
            jti: JWT ID du token
            add_to_blacklist: Ajouter a la blacklist

        Returns:
            True si le token a ete revoque
        """
        # Recuperer le token pour connaitre son expiration
        token = self.refresh_token_repository.get_by_jti(jti)

        # Revoquer dans la DB
        revoked = self.refresh_token_repository.revoke_token(jti)

        # Ajouter a la blacklist si demande
        if add_to_blacklist and token:
            self.revoked_token_repository.add_to_blacklist(
                jti=jti,
                expires_at=token.expires_at
            )

        # Comportement idempotent: retourne True meme si token deja revoque
        # Log si token inconnu pour debug (mais pas un echec)
        if not revoked and not token:
            logger.debug(f"Token jti={jti} not found for revocation (may already be revoked)")

        return True  # Idempotent - revocation toujours consideree reussie

    def revoke_all_user_tokens(
        self,
        user_id: int,
        tenant_id: Optional[int] = None,
        add_to_blacklist: bool = True
    ) -> int:
        """
        Revoque tous les tokens d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel)
            add_to_blacklist: Ajouter a la blacklist

        Returns:
            Nombre de tokens revoques
        """
        count = self.refresh_token_repository.revoke_all_for_user(
            user_id=user_id,
            tenant_id=tenant_id
        )

        return count

    def is_token_revoked(self, jti: str) -> bool:
        """
        Verifie si un token est revoque.

        Verifie d'abord la blacklist (rapide), puis la DB.

        Args:
            jti: JWT ID du token

        Returns:
            True si le token est revoque
        """
        # Verifier la blacklist
        if self.revoked_token_repository.is_revoked(jti):
            return True

        # Verifier dans la DB
        return not self.refresh_token_repository.is_valid(jti)

    def cleanup_expired_tokens(
        self,
        grace_period_days: int = 0
    ) -> Dict[str, int]:
        """
        Nettoie les tokens expires.

        Args:
            grace_period_days: Delai de grace apres expiration

        Returns:
            Dict avec le nombre de tokens et blacklist nettoyes
        """
        tokens_cleaned = self.refresh_token_repository.cleanup_expired()
        blacklist_cleaned = self.revoked_token_repository.cleanup_expired()

        return {
            "tokens_cleaned": tokens_cleaned,
            "blacklist_cleaned": blacklist_cleaned,
            "total": tokens_cleaned + blacklist_cleaned
        }

    def get_user_tokens(
        self,
        user_id: int,
        tenant_id: Optional[int] = None,
        include_revoked: bool = False
    ) -> List[Any]:
        """
        Recupere les tokens d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel, pour filtrage)
            include_revoked: Inclure les tokens revoques

        Returns:
            Liste des tokens
        """
        return self.refresh_token_repository.get_by_user_id(
            user_id=user_id,
            tenant_id=tenant_id,
            include_revoked=include_revoked
        )

    def rotate_refresh_token(
        self,
        old_jti: str,
        new_jti: str,
        new_expires_at: datetime,
        session_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Marque l'ancien token comme utilise lors d'une rotation.

        Cette methode gere uniquement le marquage de l'ancien token.
        Le stockage du nouveau token est fait separement par l'appelant
        via store_refresh_token().

        Args:
            old_jti: JTI de l'ancien token
            new_jti: JTI du nouveau token (pour reference replaced_by)
            new_expires_at: Expiration du nouveau token (non utilise)
            session_id: ID de la session (non utilise)

        Returns:
            L'ancien token marque comme utilise, ou None si non trouve

        Raises:
            TokenReplayDetectedError: Si l'ancien token a deja ete utilise
        """
        # Recuperer l'ancien token
        old_token = self.refresh_token_repository.get_by_jti(old_jti)

        if old_token is None:
            return None

        # Verifier si deja utilise (replay attack)
        if old_token.used_at is not None:
            # Attaque de replay detectee!
            # On devrait revoquer toute la famille de tokens
            raise TokenReplayDetectedError(jti=old_jti)

        # Marquer l'ancien comme utilise
        old_token.mark_as_used(replaced_by=new_jti)

        # SECURITE CRITIQUE: Persister le marquage en DB immediatement
        # Sans flush(), le token reste reutilisable jusqu'au commit de la transaction
        # Cela permettrait une attaque de replay dans la fenetre de temps
        self.refresh_token_repository.session.flush()

        # Creer le nouveau token
        # Note: Cette implementation simplifiee ne cree pas le nouveau token
        # car on n'a pas toutes les infos necessaires (user_id, tenant_id)
        # En production, on les recupererait de la session

        return old_token  # Retourne l'ancien pour reference

    def detect_token_replay(self, jti: str) -> bool:
        """
        Detecte une tentative de replay de token.

        Un token est considere comme replay s'il a deja ete utilise
        (used_at != None).

        Args:
            jti: JWT ID du token

        Returns:
            True si c'est un replay
        """
        token = self.refresh_token_repository.get_by_jti(jti)

        if token is None:
            return False

        return token.used_at is not None

    # --- Methodes ajoutees pour corrections TDD ---

    def get_token_by_jti(self, jti: str) -> Optional[Any]:
        """
        Recupere un token par son JTI.

        Cette methode encapsule l'acces au repository pour respecter
        le principe de separation des couches.

        Args:
            jti: JWT ID du token

        Returns:
            Le token ou None si non trouve
        """
        return self.refresh_token_repository.get_by_jti(jti)

    def rotate_refresh_token_complete(
        self,
        old_jti: str,
        new_jti: str,
        new_expires_at: datetime,
        session_id: str,
        raw_token: str,
        session_absolute_expiry: Optional[datetime] = None
    ) -> Optional[Any]:
        """
        Effectue une rotation complete de refresh token.

        Cette methode:
        1. Verifie l'ancien token
        2. Le marque comme utilise
        3. Cree et stocke le nouveau token

        Args:
            old_jti: JTI de l'ancien token
            new_jti: JTI du nouveau token
            new_expires_at: Expiration du nouveau token
            session_id: ID de la session
            raw_token: Token brut a hasher
            session_absolute_expiry: Expiration absolue de la session (limite dure)

        Returns:
            Le nouveau token cree

        Raises:
            TokenReplayDetectedError: Si l'ancien token a deja ete utilise
            SessionAbsolutelyExpiredError: Si la session a depasse son expiration absolue
        """
        now = datetime.now(timezone.utc)

        # Verifier l'expiration absolue de la session AVANT toute operation
        if session_absolute_expiry is not None and session_absolute_expiry <= now:
            logger.warning(
                f"Tentative de rotation pour session expiree absolument: "
                f"session_id={session_id}, absolute_expiry={session_absolute_expiry}"
            )
            raise SessionAbsolutelyExpiredError(session_id=session_id)

        # Recuperer l'ancien token
        old_token = self.refresh_token_repository.get_by_jti(old_jti)

        if old_token is None:
            return None

        # Verifier si deja utilise (replay attack)
        if old_token.used_at is not None:
            raise TokenReplayDetectedError(jti=old_jti)

        # Marquer l'ancien comme utilise
        old_token.mark_as_used(replaced_by=new_jti)

        # SECURITE: Limiter l'expiration du nouveau token par l'expiration absolue
        effective_expires_at = new_expires_at
        if session_absolute_expiry is not None and new_expires_at > session_absolute_expiry:
            logger.debug(
                f"Token rotation: expires_at ({new_expires_at}) limite par "
                f"session_absolute_expiry ({session_absolute_expiry})"
            )
            effective_expires_at = session_absolute_expiry

        # Hasher le nouveau token
        token_hash = hash_token(raw_token)

        # Creer le nouveau token avec les infos de l'ancien
        new_token = self.refresh_token_repository.store_token(
            jti=new_jti,
            user_id=old_token.user_id,
            tenant_id=old_token.tenant_id,
            expires_at=effective_expires_at,
            session_id=session_id,
            token_hash=token_hash,
            device_name=getattr(old_token, 'device_name', None),
            ip_address=getattr(old_token, 'ip_address', None),
            user_agent=getattr(old_token, 'user_agent', None)
        )

        return new_token
