"""
Middleware de gestion du shutdown gracieux.

Pendant l'arret:
- Rejette les nouvelles requetes avec 503
- Permet les health checks
- Compte les requetes actives
"""
import logging
from typing import Callable, Set

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class ShutdownMiddleware:
    """
    Middleware pour gerer les requetes pendant le shutdown.

    Fonctionnalites:
    - Rejette les nouvelles requetes avec 503 Service Unavailable
    - Permet les health checks (/health, /ready)
    - Compte les requetes actives pour le drain
    """

    # Paths toujours autorises pendant le shutdown
    ALLOWED_PATHS: Set[str] = {
        "/health",
        "/ready",
        "/health/deep",
    }

    def __init__(self, app: ASGIApp, shutdown_handler=None):
        """
        Initialise le middleware.

        Args:
            app: Application ASGI
            shutdown_handler: Handler de shutdown (optionnel)
        """
        self.app = app
        self.shutdown_handler = shutdown_handler

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Process la requete.

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")

        # Verifier si shutdown en cours
        if self.shutdown_handler and self.shutdown_handler.is_shutting_down:
            # Permettre les health checks
            if path in self.ALLOWED_PATHS:
                await self.app(scope, receive, send)
                return

            # Rejeter les autres requetes
            logger.debug(f"Rejecting request to {path} during shutdown")
            response = JSONResponse(
                status_code=503,
                content={
                    "error": "SERVICE_UNAVAILABLE",
                    "message": "Server is shutting down. Please retry later.",
                },
                headers={
                    "Retry-After": "30",
                    "Connection": "close",
                }
            )
            await response(scope, receive, send)
            return

        # Compter les requetes actives
        if self.shutdown_handler:
            self.shutdown_handler.increment_requests()

        try:
            await self.app(scope, receive, send)
        finally:
            if self.shutdown_handler:
                self.shutdown_handler.decrement_requests()
