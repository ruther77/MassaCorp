"""
MassaCorp API - Point d'entree principal
API securisee avec WireGuard et isolation complete
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.timing import TimingMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.exception_handler import register_exception_handlers

# Configuration du logging
settings = get_settings()

# Utiliser le logging structure en production, console en dev
from app.core.logging import configure_logging, get_logger
configure_logging(
    level=settings.LOG_LEVEL,
    json_format=settings.ENV != "dev",  # JSON en prod, console en dev
    include_console=True
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application
    Execute au demarrage et a l'arret
    """
    # Demarrage
    logger.info("=" * 50)
    logger.info(f"Demarrage de {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environnement: {settings.ENV}")
    logger.info(f"Debug: {settings.DEBUG}")
    logger.info(f"Reseau WireGuard: {settings.WG_NETWORK}")
    logger.info("=" * 50)

    # Validation complete de la configuration en production
    try:
        warnings = settings.validate_production_config()
        logger.info("Validation de la configuration: OK")

        # Logger les warnings (non-bloquants)
        for warning in warnings:
            logger.warning(warning)

    except ValueError as e:
        logger.critical(f"SECURITE: {e}")
        if settings.is_strict_env:
            raise  # Bloquer le demarrage en production

    yield

    # Arret
    logger.info("Arret de l'application...")


# Creation de l'application FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API securisee MassaCorp - Accessible uniquement via WireGuard",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV == "dev" else None,
    redoc_url="/redoc" if settings.ENV == "dev" else None,
)

# ============================================
# Middleware Stack (ordre CRITIQUE - dernier ajoute = premier execute)
# ============================================

# 8. Trusted Hosts (validation Host header)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.get_allowed_hosts()
)

# 7. CORS (doit etre premier execute pour preflight)
cors_origins = settings.get_cors_origins()
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS and "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Response-Time"],
)

# 6. Security Headers (HSTS, X-Frame-Options, etc.)
app.add_middleware(SecurityHeadersMiddleware)

# 5. Rate Limiting (protection brute-force)
app.add_middleware(
    RateLimitMiddleware,
    redis_url=getattr(settings, 'REDIS_URL', None),
    default_limit=60,
    login_limit=5,
    window_seconds=60,
    enabled=settings.ENV != "test"
)

# 4.5 Tenant Extraction (multi-tenant isolation)
# Note: required=False car certains endpoints valident le tenant inline
# pour des messages d'erreur plus specifiques
app.add_middleware(TenantMiddleware, required=False)

# 4. GZip Compression (optimisation)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 3. Request ID (tracabilite)
app.add_middleware(RequestIDMiddleware)

# 2. Timing (metriques performance)
app.add_middleware(TimingMiddleware, slow_threshold_ms=1000)

# 1. Exception Handlers (enregistres separement)
register_exception_handlers(app)


# ============================================
# Routes de base
# ============================================

@app.get("/", tags=["Root"])
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "Bienvenue sur MassaCorp API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.ENV == "dev" else "Desactive en production"
    }


@app.get("/api/v1/info", tags=["Info"])
async def api_info(request: Request):
    """Informations sur l'API et le client"""
    return {
        "api_version": "v1",
        "client_ip": request.client.host if request.client else "unknown",
        "headers": dict(request.headers),
        "wireguard_network": settings.WG_NETWORK,
        "message": "Vous etes connecte via le tunnel WireGuard"
    }


# ============================================
# Health Check Routes
# ============================================

from app.api.health import router as health_router
app.include_router(health_router)


# Note: Exception handlers sont enregistres via register_exception_handlers()
# Voir app/middleware/exception_handler.py pour les details


# ============================================
# Import des routers API v1
# ============================================

from app.api.v1.router import api_router

# Inclusion du router API v1
app.include_router(api_router, prefix="/api/v1")
