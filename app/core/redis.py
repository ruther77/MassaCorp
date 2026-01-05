"""
Client Redis pour MassaCorp
Cache, sessions OAuth, rate limiting, token blacklist

Configuration via settings:
- REDIS_URL: URL de connexion Redis
- REDIS_MAX_CONNECTIONS: Taille max du pool de connexions
- REDIS_HEALTH_CHECK_INTERVAL: Intervalle de health check en secondes
- REDIS_SOCKET_TIMEOUT: Timeout socket en secondes
- REDIS_SOCKET_CONNECT_TIMEOUT: Timeout de connexion en secondes
"""
import logging
from typing import Optional

import redis
from redis.connection import ConnectionPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Pool de connexions Redis global (singleton)
_redis_pool: Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


def get_redis_pool() -> Optional[ConnectionPool]:
    """
    Retourne le pool de connexions Redis global.

    Cree le pool a la premiere utilisation avec les parametres de settings.

    Returns:
        ConnectionPool ou None si Redis n'est pas configure
    """
    global _redis_pool

    if _redis_pool is not None:
        return _redis_pool

    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        logger.warning("REDIS_URL non configure, Redis desactive")
        return None

    try:
        _redis_pool = ConnectionPool.from_url(
            redis_url,
            max_connections=getattr(settings, 'REDIS_MAX_CONNECTIONS', 10),
            socket_timeout=getattr(settings, 'REDIS_SOCKET_TIMEOUT', 5),
            socket_connect_timeout=getattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT', 5),
            health_check_interval=getattr(settings, 'REDIS_HEALTH_CHECK_INTERVAL', 30),
            decode_responses=True,
        )
        logger.info(
            f"Pool Redis cree (max_connections={settings.REDIS_MAX_CONNECTIONS}, "
            f"health_check_interval={settings.REDIS_HEALTH_CHECK_INTERVAL}s)"
        )
        return _redis_pool

    except Exception as e:
        logger.error(f"Erreur creation pool Redis: {e}")
        return None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Retourne le client Redis global utilisant le pool de connexions.

    Utilise un pattern singleton pour reutiliser le client.
    Retourne None si Redis n'est pas configure ou indisponible.

    Returns:
        Client Redis ou None
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    pool = get_redis_pool()
    if pool is None:
        return None

    try:
        _redis_client = redis.Redis(connection_pool=pool)
        # Test de connexion
        _redis_client.ping()
        logger.info("Connexion Redis etablie via pool")
        return _redis_client

    except redis.ConnectionError as e:
        logger.warning(f"Impossible de se connecter a Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur Redis: {e}")
        return None


def close_redis_client() -> None:
    """Ferme le client et le pool Redis"""
    global _redis_client, _redis_pool

    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None

    if _redis_pool is not None:
        try:
            _redis_pool.disconnect()
        except Exception:
            pass
        _redis_pool = None


def get_redis_pool_stats() -> Optional[dict]:
    """
    Retourne les statistiques du pool Redis.

    Utile pour le monitoring et le debugging.

    Returns:
        Dict avec stats ou None si pool non disponible
    """
    if _redis_pool is None:
        return None

    return {
        "max_connections": _redis_pool.max_connections,
        "connection_class": _redis_pool.connection_class.__name__,
        "created_connections": len(_redis_pool._created_connections) if hasattr(_redis_pool, '_created_connections') else "N/A",
        "available_connections": len(_redis_pool._available_connections) if hasattr(_redis_pool, '_available_connections') else "N/A",
        "in_use_connections": len(_redis_pool._in_use_connections) if hasattr(_redis_pool, '_in_use_connections') else "N/A",
    }
