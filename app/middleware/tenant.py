"""
Tenant Middleware pour MassaCorp API.

Extrait et valide le X-Tenant-ID header pour l'isolation multi-tenant.
Stocke le tenant_id dans request.state pour acces ulterieur.

Integration avec le logging:
- Le tenant_id est automatiquement inclus dans tous les logs JSON
- Permet l'audit multi-tenant
"""
import logging
from typing import Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.logging import set_request_context

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour l'extraction et validation du tenant_id.

    Fonctionnalites:
    - Extrait X-Tenant-ID du header
    - Valide que c'est un entier positif
    - Stocke dans request.state.tenant_id
    - Exclut certains paths (health, docs, etc.)
    """

    # Paths qui n'ont pas besoin de tenant_id
    EXCLUDED_PATHS: Set[str] = {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Prefixes qui n'ont pas besoin de tenant_id
    EXCLUDED_PREFIXES: Set[str] = {
        "/docs",
        "/redoc",
    }

    HEADER_NAME = "X-Tenant-ID"

    def __init__(self, app, required: bool = True):
        """
        Initialise le middleware.

        Args:
            app: L'application FastAPI
            required: Si True, retourne 400 si header manquant (hors excluded paths)
        """
        super().__init__(app)
        self.required = required

    def _is_excluded(self, path: str) -> bool:
        """Verifie si le path est exclu de la validation tenant."""
        if path in self.EXCLUDED_PATHS:
            return True

        for prefix in self.EXCLUDED_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Extrait et valide le tenant_id pour chaque requete.

        Args:
            request: La requete entrante
            call_next: Le prochain handler

        Returns:
            Response ou erreur 400 si tenant invalide
        """
        path = request.url.path

        # Skip pour les paths exclus
        if self._is_excluded(path):
            request.state.tenant_id = None
            return await call_next(request)

        # Extraire le header
        tenant_id_header = request.headers.get(self.HEADER_NAME)

        if not tenant_id_header:
            if self.required:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "TENANT_REQUIRED",
                        "message": f"Header {self.HEADER_NAME} requis"
                    }
                )
            request.state.tenant_id = None
            return await call_next(request)

        # Valider que c'est un entier positif
        try:
            tenant_id = int(tenant_id_header)
            if tenant_id <= 0:
                raise ValueError("Tenant ID must be positive")
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "INVALID_TENANT",
                    "message": f"{self.HEADER_NAME} invalide: doit etre un entier positif"
                }
            )

        # Stocker dans request.state
        request.state.tenant_id = tenant_id

        # Configurer le contexte de logging avec le tenant_id
        # Tous les logs emis pendant cette requete incluront le tenant_id
        set_request_context(tenant_id=tenant_id)

        # Log pour audit (niveau DEBUG)
        logger.debug(f"Tenant {tenant_id} pour {request.method} {path}")

        return await call_next(request)
