"""
Health Check endpoints pour MassaCorp API.

Fournit les endpoints de monitoring:
- /health: Liveness check (l'app repond)
- /ready: Readiness check (dependances OK)
- /health/deep: Deep health check (tous les details)

Ces endpoints sont exclus de l'authentification pour
permettre aux load balancers de les utiliser.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Health"])


# =============================================================================
# Health Check Functions
# =============================================================================

def check_database(db: Session) -> Dict[str, Any]:
    """
    Verifie la connexion a la base de donnees.

    Returns:
        Dict avec status et details
    """
    import time

    try:
        start = time.perf_counter()
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "error": str(e)}


def check_redis() -> Dict[str, Any]:
    """
    Verifie la connexion a Redis.

    Returns:
        Dict avec status et details
    """
    import time

    try:
        import redis
    except ImportError:
        return {"status": "not_configured", "reason": "redis package not installed"}

    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        return {"status": "not_configured", "reason": "REDIS_URL not set"}

    try:
        start = time.perf_counter()
        client = redis.from_url(redis_url, socket_timeout=5)
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        client.close()
        return {"status": "ok", "latency_ms": latency_ms}
    except redis.ConnectionError as e:
        logger.warning(f"Redis connection failed: {e}")
        return {"status": "unavailable", "error": str(e)}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/health",
    summary="Liveness check",
    description="Retourne 200 si l'application repond. Utilise par les load balancers.",
    include_in_schema=False
)
async def health():
    """
    Liveness probe.

    Retourne OK si l'application est en vie.
    Ne verifie pas les dependances.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Retourne 200 si l'application est prete a recevoir du trafic.",
    include_in_schema=False
)
async def ready(db: Session = Depends(get_db)):
    """
    Readiness probe.

    Verifie que les dependances critiques sont disponibles:
    - Base de donnees
    - Redis (si configure)

    Retourne 503 si une dependance critique est indisponible.
    """
    errors: List[str] = []

    # Check database
    db_status = check_database(db)
    if db_status["status"] != "ok":
        errors.append(f"database: {db_status.get('error', 'unknown error')}")

    # Check Redis (optionnel)
    redis_status = check_redis()
    if redis_status["status"] == "error":
        errors.append(f"redis: {redis_status.get('error', 'unknown error')}")

    if errors:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "errors": errors,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get(
    "/health/deep",
    summary="Deep health check",
    description="Retourne l'etat detaille de toutes les dependances."
)
async def deep_health(db: Session = Depends(get_db)):
    """
    Deep health check.

    Retourne l'etat detaille de:
    - Application (version, environnement)
    - Base de donnees
    - Redis
    - Metriques systeme

    Note: Cet endpoint peut etre lent, ne pas l'utiliser pour les probes K8s.
    """
    checks = {
        "database": check_database(db),
        "redis": check_redis(),
    }

    # Determiner le status global
    # Redis unavailable = degraded mais pas critical (app fonctionne sans)
    all_ok = all(
        c.get("status") in ("ok", "not_configured", "unavailable")
        for c in checks.values()
    )

    response = {
        "status": "ok" if all_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
        "checks": checks,
    }

    status_code = 200 if all_ok else 503

    return JSONResponse(status_code=status_code, content=response)


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Retourne les metriques au format Prometheus.",
    include_in_schema=False
)
async def metrics_endpoint():
    """
    Endpoint Prometheus metrics.

    Retourne les metriques au format Prometheus text.
    Si prometheus_client n'est pas installe, retourne les stats en JSON.
    """
    from app.core.metrics import get_metrics_response
    return get_metrics_response()
