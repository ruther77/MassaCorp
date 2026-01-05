"""
Request ID Middleware pour MassaCorp API.

Genere ou propage un X-Request-ID unique pour chaque requete.
Essentiel pour la tracabilite et le debugging distribue.

Integration avec le logging:
- Le request_id est automatiquement inclus dans tous les logs JSON
- Permet le tracing distribue end-to-end
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import set_request_context, clear_request_context


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour la gestion des Request IDs.

    Fonctionnalites:
    - Genere un UUID v4 si X-Request-ID absent
    - Propage le X-Request-ID existant (tracing distribue)
    - Stocke dans request.state.request_id
    - Set le contexte de logging pour inclure le request_id dans tous les logs
    - Ajoute X-Request-ID dans la response
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Traite chaque requete en ajoutant un Request ID.

        Args:
            request: La requete entrante
            call_next: Le prochain handler

        Returns:
            Response avec X-Request-ID header
        """
        # Recuperer ou generer le Request ID
        request_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())

        # Stocker dans request.state pour acces dans les handlers
        request.state.request_id = request_id

        # Configurer le contexte de logging avec le request_id
        # Tous les logs emis pendant cette requete incluront le request_id
        set_request_context(request_id=request_id)

        try:
            # Executer la requete
            response = await call_next(request)

            # Ajouter le Request ID dans la response
            response.headers[self.HEADER_NAME] = request_id

            return response
        finally:
            # Nettoyer le contexte de logging
            clear_request_context()
