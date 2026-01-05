"""
Client Redis pour MassaCorp
Cache, sessions OAuth, rate limiting
"""
import logging
from typing import Optional

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Client Redis global (singleton)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Retourne le client Redis global.

    Utilise un pattern singleton pour reutiliser la connexion.
    Retourne None si Redis n'est pas configure ou indisponible.

    Returns:
        Client Redis ou None
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        logger.warning("REDIS_URL non configure, OAuth state storage desactive")
        return None

    try:
        _redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        # Test de connexion
        _redis_client.ping()
        logger.info("Connexion Redis etablie")
        return _redis_client

    except redis.ConnectionError as e:
        logger.warning(f"Impossible de se connecter a Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur Redis: {e}")
        return None


def close_redis_client() -> None:
    """Ferme la connexion Redis"""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
        _redis_client = None
