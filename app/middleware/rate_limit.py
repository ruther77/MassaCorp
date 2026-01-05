"""
Middleware de Rate Limiting pour MassaCorp API.

Ce module implemente un rate limiter avec:
- Stockage Redis pour le comptage des requetes
- Fallback en memoire si Redis non disponible
- Configuration par endpoint et par role
- Headers standard X-RateLimit-*

Configuration:
- RATE_LIMIT_PER_MINUTE: Limite globale par IP (defaut: 60)
- RATE_LIMIT_LOGIN: Limite pour /auth/login (defaut: 5)
- RATE_LIMIT_BURST: Burst temporaire autorise (defaut: 10)

Algorithme: Sliding Window avec Redis ZSET ou Token Bucket en memoire.
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Tentative d'import Redis (optionnel)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting pour FastAPI.

    Limite le nombre de requetes par IP avec:
    - Limites differentes par endpoint (login plus strict)
    - Stockage Redis ou fallback en memoire
    - Headers de rate limit dans les reponses

    Usage:
        app.add_middleware(
            RateLimitMiddleware,
            redis_url="redis://localhost:6379",
            default_limit=60,
            login_limit=5
        )
    """

    def __init__(
        self,
        app,
        redis_url: Optional[str] = None,
        default_limit: int = 60,
        login_limit: int = 5,
        window_seconds: int = 60,
        enabled: bool = True
    ):
        """
        Initialise le middleware.

        Args:
            app: Application FastAPI
            redis_url: URL de connexion Redis (optionnel)
            default_limit: Limite par defaut par minute
            login_limit: Limite pour /auth/login
            window_seconds: Fenetre de temps en secondes
            enabled: Active/desactive le rate limiting
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.login_limit = login_limit
        self.window_seconds = window_seconds
        self.enabled = enabled

        # Configuration des limites par endpoint
        self.endpoint_limits: Dict[str, int] = {
            "/api/v1/auth/login": login_limit,
            "/api/v1/auth/refresh": 30,  # Plus permissif que login
            "/api/v1/auth/logout": 30,
            # MFA endpoints - limites strictes pour prevenir brute-force
            "/api/v1/mfa/verify": 5,  # 5 tentatives/min max (TOTP 6 digits)
            "/api/v1/mfa/enable": 5,  # 5 tentatives/min
            "/api/v1/mfa/disable": 5,  # 5 tentatives/min
            "/api/v1/mfa/recovery/verify": 3,  # 3 tentatives/min (plus strict)
            "/api/v1/mfa/recovery/regenerate": 3,  # 3 tentatives/min
        }

        # Initialiser le backend de stockage
        self.redis_client = None
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=1
                )
                # Test de connexion
                self.redis_client.ping()
            except Exception as e:
                # SECURITE: Log explicite du fallback - rate limiting potentiellement degrade
                logger.warning(
                    f"Rate limiting Redis non disponible, fallback memoire active: {e}. "
                    "ATTENTION: Rate limiting en memoire ne protege pas contre les attaques distribuees."
                )
                self.redis_client = None

        # Fallback en memoire si pas de Redis
        if self.redis_client is None:
            self._memory_store: Dict[str, list] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """
        Extrait l'IP client de la requete.

        Gere les proxies via X-Forwarded-For.

        Args:
            request: Requete FastAPI

        Returns:
            Adresse IP du client
        """
        # Verifier X-Forwarded-For pour les proxies
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Prendre la premiere IP (client original)
            return forwarded.split(",")[0].strip()

        # Fallback sur l'IP directe
        if request.client:
            return request.client.host

        return "unknown"

    def _get_limit_for_path(self, path: str) -> int:
        """
        Retourne la limite pour un chemin donne.

        Args:
            path: Chemin de l'endpoint

        Returns:
            Limite de requetes par minute
        """
        return self.endpoint_limits.get(path, self.default_limit)

    def _check_rate_limit_redis(
        self,
        key: str,
        limit: int
    ) -> Tuple[bool, int, int]:
        """
        Verifie le rate limit avec Redis (sliding window).

        Args:
            key: Cle unique (IP:path)
            limit: Limite de requetes

        Returns:
            Tuple (allowed, remaining, reset_time)
        """
        now = time.time()
        window_start = now - self.window_seconds

        pipe = self.redis_client.pipeline()

        # Supprimer les anciennes entrees
        pipe.zremrangebyscore(key, 0, window_start)

        # Compter les requetes dans la fenetre
        pipe.zcard(key)

        # Ajouter la requete courante
        pipe.zadd(key, {str(now): now})

        # Expiration de la cle
        pipe.expire(key, self.window_seconds)

        results = pipe.execute()
        current_count = results[1]

        remaining = max(0, limit - current_count - 1)
        reset_time = int(now + self.window_seconds)

        return current_count < limit, remaining, reset_time

    def _check_rate_limit_memory(
        self,
        key: str,
        limit: int
    ) -> Tuple[bool, int, int]:
        """
        Verifie le rate limit en memoire (token bucket simplifie).

        Args:
            key: Cle unique (IP:path)
            limit: Limite de requetes

        Returns:
            Tuple (allowed, remaining, reset_time)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Nettoyer les anciennes entrees
        self._memory_store[key] = [
            ts for ts in self._memory_store[key]
            if ts > window_start
        ]

        current_count = len(self._memory_store[key])

        if current_count < limit:
            self._memory_store[key].append(now)
            remaining = limit - current_count - 1
            allowed = True
        else:
            remaining = 0
            allowed = False

        reset_time = int(now + self.window_seconds)

        return allowed, remaining, reset_time

    def _check_rate_limit(
        self,
        client_ip: str,
        path: str
    ) -> Tuple[bool, int, int]:
        """
        Verifie si la requete est autorisee.

        Args:
            client_ip: IP du client
            path: Chemin de l'endpoint

        Returns:
            Tuple (allowed, remaining, reset_time)
        """
        limit = self._get_limit_for_path(path)
        key = f"ratelimit:{client_ip}:{path}"

        if self.redis_client:
            try:
                return self._check_rate_limit_redis(key, limit)
            except Exception as e:
                # SECURITE: Log de l'erreur Redis runtime - protection potentiellement degradee
                logger.error(
                    f"Rate limiting Redis erreur runtime pour {key}: {e}. "
                    "Fallback memoire utilise - protection distribuee compromise."
                )

        return self._check_rate_limit_memory(key, limit)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """
        Intercepte les requetes pour appliquer le rate limiting.

        Args:
            request: Requete entrante
            call_next: Handler suivant

        Returns:
            Response avec headers rate limit
        """
        # Si desactive, passer directement
        if not self.enabled:
            return await call_next(request)

        # Ne pas limiter certains endpoints (health, etc.)
        path = request.url.path
        if path in ["/health", "/", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # Verifier le rate limit
        client_ip = self._get_client_ip(request)
        allowed, remaining, reset_time = self._check_rate_limit(client_ip, path)

        # Ajouter les headers de rate limit
        headers = {
            "X-RateLimit-Limit": str(self._get_limit_for_path(path)),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_time),
        }

        if not allowed:
            # Rate limit atteint
            headers["Retry-After"] = str(self.window_seconds)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Trop de requetes. Veuillez reessayer plus tard.",
                    "retry_after": self.window_seconds
                },
                headers=headers
            )

        # Requete autorisee
        response = await call_next(request)

        # Ajouter les headers a la reponse
        for header_name, header_value in headers.items():
            response.headers[header_name] = header_value

        return response


def get_rate_limit_middleware(
    redis_url: Optional[str] = None,
    default_limit: int = 60,
    login_limit: int = 5,
    enabled: bool = True
) -> type:
    """
    Factory pour creer un middleware configure.

    Usage:
        from app.middleware.rate_limit import get_rate_limit_middleware

        app.add_middleware(
            get_rate_limit_middleware(
                redis_url="redis://localhost:6379",
                login_limit=5
            )
        )
    """
    class ConfiguredRateLimitMiddleware(RateLimitMiddleware):
        def __init__(self, app):
            super().__init__(
                app,
                redis_url=redis_url,
                default_limit=default_limit,
                login_limit=login_limit,
                enabled=enabled
            )

    return ConfiguredRateLimitMiddleware
