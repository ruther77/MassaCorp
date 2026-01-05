"""
Service de reinitialisation de mot de passe.

Fonctionnalites:
- Generation de tokens securises (delegue au repository)
- Validation et utilisation de tokens
- Expiration 1 heure
- Usage unique
- Rate limiting (max 3 demandes/heure/utilisateur)
"""
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import AppException
from app.models.password_reset import PasswordResetToken
from app.repositories.password_reset import PasswordResetRepository
from app.repositories.user import UserRepository
from app.repositories.session import SessionRepository


# =============================================================================
# Exceptions specifiques
# =============================================================================


class PasswordResetException(AppException):
    """Exception de base pour password reset."""
    pass


class RateLimitExceeded(PasswordResetException):
    """Trop de demandes de reset."""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Trop de demandes de reinitialisation. Reessayez plus tard."


class TokenExpired(PasswordResetException):
    """Token de reset expire."""
    status_code = 400
    error_code = "TOKEN_EXPIRED"
    message = "Le lien de reinitialisation a expire."


class TokenAlreadyUsed(PasswordResetException):
    """Token de reset deja utilise."""
    status_code = 400
    error_code = "TOKEN_ALREADY_USED"
    message = "Ce lien de reinitialisation a deja ete utilise."


class InvalidToken(PasswordResetException):
    """Token de reset invalide."""
    status_code = 400
    error_code = "INVALID_TOKEN"
    message = "Lien de reinitialisation invalide."


# =============================================================================
# Service
# =============================================================================


class PasswordResetService:
    """
    Service de reinitialisation de mot de passe.

    Utilise les repositories pour toutes les operations DB.
    Ajoute la logique metier (validation, exceptions, rate limiting).
    """

    def __init__(
        self,
        repository: PasswordResetRepository,
        user_repository: Optional[UserRepository] = None,
        session_repository: Optional[SessionRepository] = None
    ):
        """
        Initialise le service.

        Args:
            repository: Repository pour les tokens de reset
            user_repository: Repository pour les utilisateurs (optionnel)
            session_repository: Repository pour les sessions (optionnel)
        """
        self.repo = repository
        self.user_repo = user_repository
        self.session_repo = session_repository

    # =========================================================================
    # Methodes utilitaires (delegue au repository)
    # =========================================================================

    @staticmethod
    def generate_reset_token() -> str:
        """
        Genere un nouveau token de reset cryptographiquement securise.

        Returns:
            Token brut (32 chars, URL-safe, 256 bits d'entropie)
        """
        raw_token, _ = PasswordResetRepository.generate_token()
        return raw_token

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """
        Hash un token de reset avec SHA-256.

        Args:
            raw_token: Token brut

        Returns:
            Hash hex du token
        """
        return PasswordResetRepository.hash_token(raw_token)

    @staticmethod
    def get_expiration_time() -> datetime:
        """
        Retourne la date d'expiration pour un nouveau token.

        Returns:
            Date d'expiration (maintenant + 1 heure)
        """
        from datetime import timedelta
        return datetime.now(timezone.utc) + timedelta(hours=1)

    def request_reset(self, user_id: int) -> tuple[PasswordResetToken, str]:
        """
        Demande une reinitialisation de mot de passe.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Tuple (token_obj, raw_token) - raw_token a envoyer par email

        Raises:
            RateLimitExceeded: Si trop de demandes recentes
        """
        # Rate limiting
        if not self.repo.can_request_reset(user_id):
            raise RateLimitExceeded()

        # Creer le token (le repository genere et hash)
        token_obj, raw_token = self.repo.create_reset_token(user_id=user_id)

        return token_obj, raw_token

    def request_reset_by_email(self, email: str, tenant_id: int) -> Optional[tuple[PasswordResetToken, str]]:
        """
        Demande une reinitialisation par email.

        Args:
            email: Email de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            Tuple (token_obj, raw_token) ou None si utilisateur inexistant
            Note: Ne pas reveler si l'utilisateur existe ou non!

        Raises:
            RateLimitExceeded: Si trop de demandes recentes
        """
        if self.user_repo is None:
            raise ValueError("UserRepository requis pour request_reset_by_email")

        # Chercher l'utilisateur
        user = self.user_repo.get_by_email_and_tenant(email, tenant_id)

        if user is None:
            # Ne pas reveler que l'utilisateur n'existe pas
            return None

        return self.request_reset(user.id)

    def validate_token(self, raw_token: str) -> PasswordResetToken:
        """
        Valide un token de reset.

        Args:
            raw_token: Token brut recu par email

        Returns:
            Objet PasswordResetToken si valide

        Raises:
            InvalidToken: Token inexistant
            TokenExpired: Token expire
            TokenAlreadyUsed: Token deja utilise
        """
        # Utiliser la methode du repository qui hash et cherche
        token_obj = self.repo.validate_token(raw_token)

        if token_obj is None:
            raise InvalidToken()

        # Verifier expiration
        if token_obj.is_expired:
            raise TokenExpired()

        # Verifier usage
        if token_obj.is_used:
            raise TokenAlreadyUsed()

        return token_obj

    def reset_password(self, raw_token: str, new_password_hash: str) -> int:
        """
        Reinitialise le mot de passe.

        Args:
            raw_token: Token brut de reset
            new_password_hash: Hash du nouveau mot de passe (deja hashe!)

        Returns:
            user_id de l'utilisateur dont le mot de passe a ete change

        Raises:
            InvalidToken: Token invalide
            TokenExpired: Token expire
            TokenAlreadyUsed: Token deja utilise
        """
        # Valider le token
        token_obj = self.validate_token(raw_token)

        # Marquer le token comme utilise
        self.repo.use_token(token_obj.id)

        # Invalider les autres tokens de cet utilisateur
        self.repo.invalidate_all_for_user(token_obj.user_id)

        # Mettre a jour le mot de passe via user repository
        if self.user_repo:
            user = self.user_repo.get_by_id(token_obj.user_id)
            if user:
                user.password_hash = new_password_hash
                # Le flush sera fait par le context manager

        # Revoquer toutes les sessions (force re-login)
        if self.session_repo:
            self.session_repo.invalidate_all_sessions(user_id=token_obj.user_id)

        return token_obj.user_id

    def get_valid_token_for_user(self, user_id: int) -> Optional[PasswordResetToken]:
        """
        Recupere un token valide existant pour un utilisateur.

        Utile pour eviter de generer plusieurs tokens.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Token valide ou None
        """
        return self.repo.get_valid_token_for_user(user_id)

    def cleanup_expired_tokens(self, older_than_days: int = 7) -> int:
        """
        Supprime les tokens expires anciens.

        Args:
            older_than_days: Age minimum pour suppression

        Returns:
            Nombre de tokens supprimes
        """
        return self.repo.cleanup_expired(older_than_days=older_than_days)
