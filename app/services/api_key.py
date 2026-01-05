"""
Service pour la gestion des API Keys.

Fonctionnalites:
- Creation de keys securisees (delegue au repository)
- Validation avec check expiration et revocation
- Revocation de keys
- Isolation par tenant
- Logging d'utilisation pour audit
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.core.exceptions import AppException
from app.models.api_key import APIKey, APIKeyUsage
from app.repositories.api_key import APIKeyRepository
from app.repositories.api_key_usage import APIKeyUsageRepository


# =============================================================================
# Exceptions specifiques
# =============================================================================


class APIKeyException(AppException):
    """Exception de base pour API Keys."""
    pass


class InvalidAPIKey(APIKeyException):
    """API Key invalide ou inexistante."""
    status_code = 401
    error_code = "INVALID_API_KEY"
    message = "Cle API invalide."


class APIKeyRevoked(APIKeyException):
    """API Key revoquee."""
    status_code = 401
    error_code = "API_KEY_REVOKED"
    message = "Cette cle API a ete revoquee."


class APIKeyExpired(APIKeyException):
    """API Key expiree."""
    status_code = 401
    error_code = "API_KEY_EXPIRED"
    message = "Cette cle API a expire."


class APIKeyScopeInsufficient(APIKeyException):
    """API Key n'a pas le scope requis."""
    status_code = 403
    error_code = "API_KEY_SCOPE_INSUFFICIENT"
    message = "Cette cle API n'a pas les permissions requises."


class APIKeyRateLimitExceeded(APIKeyException):
    """API Key a depasse la limite de requetes."""
    status_code = 429
    error_code = "API_KEY_RATE_LIMIT_EXCEEDED"
    message = "Limite de requetes depassee pour cette cle API."


# =============================================================================
# Service
# =============================================================================


class APIKeyService:
    """
    Service de gestion des API Keys.

    Utilise le repository pour toutes les operations DB.
    Ajoute la logique metier (validation, exceptions, rate limiting).
    """

    # Configuration rate limiting par defaut
    DEFAULT_RATE_LIMIT_REQUESTS = 1000  # Requetes max par fenetre
    DEFAULT_RATE_LIMIT_WINDOW_MINUTES = 60  # Fenetre en minutes

    def __init__(
        self,
        repository: APIKeyRepository,
        usage_repository: Optional[APIKeyUsageRepository] = None,
        rate_limit_requests: Optional[int] = None,
        rate_limit_window_minutes: Optional[int] = None
    ):
        """
        Initialise le service.

        Args:
            repository: Repository pour les operations DB
            usage_repository: Repository pour le logging d'utilisation (optionnel)
            rate_limit_requests: Nombre max de requetes par fenetre (defaut: 1000)
            rate_limit_window_minutes: Fenetre de temps en minutes (defaut: 60)
        """
        self.repo = repository
        self.usage_repo = usage_repository
        self.rate_limit_requests = rate_limit_requests or self.DEFAULT_RATE_LIMIT_REQUESTS
        self.rate_limit_window_minutes = rate_limit_window_minutes or self.DEFAULT_RATE_LIMIT_WINDOW_MINUTES

    # =========================================================================
    # Methodes utilitaires (delegue au repository)
    # =========================================================================

    @staticmethod
    def generate_key() -> str:
        """
        Genere une nouvelle API Key cryptographiquement securisee.

        Returns:
            Key brute (avec prefix mc_sk_, 256 bits d'entropie)
        """
        raw_key, _ = APIKeyRepository.generate_key()
        return raw_key

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """
        Hash une API Key avec SHA-256.

        Args:
            raw_key: Key brute

        Returns:
            Hash hex de la key
        """
        return APIKeyRepository.hash_key(raw_key)

    def create_key(
        self,
        tenant_id: int,
        name: str,
        expires_at: Optional[datetime] = None,
        created_by_user_id: Optional[int] = None,
        scopes: Optional[List[str]] = None
    ) -> tuple[APIKey, str]:
        """
        Cree une nouvelle API Key.

        Args:
            tenant_id: ID du tenant
            name: Nom descriptif
            expires_at: Date d'expiration (optionnel)
            created_by_user_id: User qui cree la key
            scopes: Liste des scopes autorises (None = tous les droits)

        Returns:
            Tuple (api_key, raw_key)
            IMPORTANT: raw_key n'est retourne qu'une seule fois!
        """
        api_key, raw_key = self.repo.create_api_key(
            tenant_id=tenant_id,
            name=name,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
            scopes=scopes
        )
        return api_key, raw_key

    def validate_key(self, raw_key: str) -> APIKey:
        """
        Valide une API Key et retourne l'objet si valide.

        Args:
            raw_key: Key brute

        Returns:
            Objet APIKey si valide

        Raises:
            InvalidAPIKey: Key inexistante
            APIKeyRevoked: Key revoquee
            APIKeyExpired: Key expiree
        """
        # Utiliser la methode du repository qui hash et cherche
        api_key = self.repo.validate_key(raw_key)

        if api_key is None:
            raise InvalidAPIKey()

        # Le repository retourne None si invalide, mais verifions aussi
        if api_key.is_revoked:
            raise APIKeyRevoked()

        if api_key.is_expired:
            raise APIKeyExpired()

        # Mettre a jour last_used_at
        self.repo.update_last_used(api_key.id)

        return api_key

    def revoke_key(self, key_id: int, tenant_id: Optional[int] = None) -> bool:
        """
        Revoque une API Key.

        Args:
            key_id: ID de la key a revoquer
            tenant_id: ID du tenant (pour verification)

        Returns:
            True si revoquee, False si non trouvee
        """
        return self.repo.revoke(key_id, tenant_id=tenant_id)

    def get_key_by_id(self, key_id: int) -> Optional[APIKey]:
        """
        Recupere une API Key par son ID.

        Args:
            key_id: ID de la key

        Returns:
            Objet APIKey ou None
        """
        return self.repo.get_by_id(key_id)

    def list_keys(
        self,
        tenant_id: int,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[APIKey]:
        """
        Liste les API keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            include_revoked: Inclure les keys revoquees
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des API keys
        """
        return self.repo.get_by_tenant(
            tenant_id=tenant_id,
            include_revoked=include_revoked,
            skip=skip,
            limit=limit
        )

    def count_keys(self, tenant_id: int, include_revoked: bool = False) -> int:
        """
        Compte les API keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            include_revoked: Inclure les keys revoquees

        Returns:
            Nombre de keys
        """
        return self.repo.count_by_tenant(
            tenant_id=tenant_id,
            include_revoked=include_revoked
        )

    def revoke_all_for_tenant(self, tenant_id: int) -> int:
        """
        Revoque toutes les API keys d'un tenant.

        Cas d'usage: compromission du tenant.

        Args:
            tenant_id: ID du tenant

        Returns:
            Nombre de keys revoquees
        """
        return self.repo.revoke_all_by_tenant(tenant_id)

    # =========================================================================
    # Validation avec scopes
    # =========================================================================

    def validate_key_with_scope(
        self,
        raw_key: str,
        required_scope: str
    ) -> APIKey:
        """
        Valide une API Key et verifie qu'elle a le scope requis.

        Args:
            raw_key: Key brute
            required_scope: Scope requis (ex: "users:read")

        Returns:
            Objet APIKey si valide et scope autorise

        Raises:
            InvalidAPIKey: Key inexistante
            APIKeyRevoked: Key revoquee
            APIKeyExpired: Key expiree
            APIKeyScopeInsufficient: Key n'a pas le scope requis
        """
        api_key = self.validate_key(raw_key)

        if not api_key.has_scope(required_scope):
            raise APIKeyScopeInsufficient()

        return api_key

    def validate_key_with_any_scope(
        self,
        raw_key: str,
        required_scopes: List[str]
    ) -> APIKey:
        """
        Valide une API Key et verifie qu'elle a au moins un scope.

        Args:
            raw_key: Key brute
            required_scopes: Liste des scopes (au moins un requis)

        Returns:
            Objet APIKey si valide et au moins un scope autorise

        Raises:
            InvalidAPIKey: Key inexistante
            APIKeyRevoked: Key revoquee
            APIKeyExpired: Key expiree
            APIKeyScopeInsufficient: Key n'a aucun des scopes requis
        """
        api_key = self.validate_key(raw_key)

        if not api_key.has_any_scope(required_scopes):
            raise APIKeyScopeInsufficient()

        return api_key

    # =========================================================================
    # Usage logging
    # =========================================================================

    def log_usage(
        self,
        api_key: APIKey,
        endpoint: str,
        method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_status: Optional[int] = None,
        response_time_ms: Optional[int] = None
    ) -> Optional[APIKeyUsage]:
        """
        Log une utilisation d'API Key.

        Args:
            api_key: L'API Key utilisee
            endpoint: Endpoint appele
            method: Methode HTTP
            ip_address: IP source
            user_agent: User-Agent
            response_status: Code HTTP reponse
            response_time_ms: Temps de reponse

        Returns:
            APIKeyUsage cree ou None si logging desactive
        """
        if self.usage_repo is None:
            return None

        return self.usage_repo.log_usage(
            api_key_id=api_key.id,
            tenant_id=api_key.tenant_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            response_status=response_status,
            response_time_ms=response_time_ms
        )

    def get_usage_stats(
        self,
        api_key_id: int,
        since: Optional[datetime] = None
    ) -> Optional[dict]:
        """
        Recupere les statistiques d'utilisation d'une API Key.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut (defaut: 24h)

        Returns:
            Dict avec statistiques ou None si logging desactive
        """
        if self.usage_repo is None:
            return None

        return self.usage_repo.get_usage_stats_by_key(api_key_id, since)

    def count_usage(
        self,
        api_key_id: int,
        since: Optional[datetime] = None
    ) -> int:
        """
        Compte les utilisations d'une API Key.

        Utile pour le rate limiting.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut (defaut: 1h)

        Returns:
            Nombre d'utilisations
        """
        if self.usage_repo is None:
            return 0

        return self.usage_repo.count_usage_by_key(api_key_id, since)

    # =========================================================================
    # Rate limiting
    # =========================================================================

    def check_rate_limit(
        self,
        api_key: APIKey,
        custom_limit: Optional[int] = None,
        custom_window_minutes: Optional[int] = None
    ) -> tuple[bool, int, int]:
        """
        Verifie si l'API Key a depasse sa limite de requetes.

        Args:
            api_key: L'API Key a verifier
            custom_limit: Limite personnalisee (defaut: config service)
            custom_window_minutes: Fenetre personnalisee (defaut: config service)

        Returns:
            Tuple (is_allowed, current_count, limit):
                - is_allowed: True si la requete est autorisee
                - current_count: Nombre de requetes dans la fenetre
                - limit: Limite appliquee
        """
        if self.usage_repo is None:
            # Sans logging, pas de rate limiting possible
            return (True, 0, self.rate_limit_requests)

        limit = custom_limit or self.rate_limit_requests
        window_minutes = custom_window_minutes or self.rate_limit_window_minutes

        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        current_count = self.usage_repo.count_usage_by_key(api_key.id, since)

        is_allowed = current_count < limit
        return (is_allowed, current_count, limit)

    def enforce_rate_limit(
        self,
        api_key: APIKey,
        custom_limit: Optional[int] = None,
        custom_window_minutes: Optional[int] = None
    ) -> None:
        """
        Verifie et applique la limite de requetes.

        Leve une exception si la limite est depassee.

        Args:
            api_key: L'API Key a verifier
            custom_limit: Limite personnalisee
            custom_window_minutes: Fenetre personnalisee

        Raises:
            APIKeyRateLimitExceeded: Si limite depassee
        """
        is_allowed, current_count, limit = self.check_rate_limit(
            api_key, custom_limit, custom_window_minutes
        )

        if not is_allowed:
            raise APIKeyRateLimitExceeded()

    def get_rate_limit_status(
        self,
        api_key: APIKey
    ) -> dict:
        """
        Retourne le statut du rate limiting pour une API Key.

        Utile pour les headers X-RateLimit-*.

        Args:
            api_key: L'API Key

        Returns:
            Dict avec limit, remaining, reset_seconds
        """
        is_allowed, current_count, limit = self.check_rate_limit(api_key)
        remaining = max(0, limit - current_count)

        return {
            "limit": limit,
            "remaining": remaining,
            "current": current_count,
            "window_minutes": self.rate_limit_window_minutes,
            "reset_seconds": self.rate_limit_window_minutes * 60
        }
