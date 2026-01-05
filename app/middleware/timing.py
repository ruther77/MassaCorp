"""
Timing Middleware pour MassaCorp API.

Mesure et log le temps de reponse de chaque requete.
Utile pour les metriques et le monitoring des performances.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour mesurer le temps de reponse.

    Fonctionnalites:
    - Mesure le temps de traitement de chaque requete
    - Ajoute X-Response-Time header (en ms)
    - Log les requetes lentes (> slow_threshold_ms)
    - Stocke dans request.state.response_time_ms
    """

    def __init__(self, app, slow_threshold_ms: int = 1000):
        """
        Initialise le middleware.

        Args:
            app: L'application FastAPI
            slow_threshold_ms: Seuil en ms pour logger les requetes lentes
        """
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Mesure le temps de reponse de chaque requete.

        Args:
            request: La requete entrante
            call_next: Le prochain handler

        Returns:
            Response avec X-Response-Time header
        """
        start_time = time.perf_counter()

        response = await call_next(request)

        # Calculer le temps de reponse en ms
        process_time_ms = (time.perf_counter() - start_time) * 1000

        # Ajouter le header
        response.headers["X-Response-Time"] = f"{process_time_ms:.2f}ms"

        # Log les requetes lentes
        if process_time_ms > self.slow_threshold_ms:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time_ms:.2f}ms (threshold: {self.slow_threshold_ms}ms) "
                f"[request_id={request_id}]"
            )

        return response
