"""
Security Headers Middleware pour MassaCorp API.

Ajoute les headers de securite HTTP recommandes:
- Strict-Transport-Security (HSTS)
- X-Content-Type-Options
- X-Frame-Options
- Referrer-Policy
- Cache-Control pour les endpoints auth
- HTTPS redirect en production
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from app.core.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour ajouter les headers de securite HTTP.

    Ces headers protegent contre:
    - Downgrade attacks (HSTS)
    - MIME sniffing (X-Content-Type-Options)
    - Clickjacking (X-Frame-Options)
    - Information leakage (Referrer-Policy)
    """

    # Headers de securite a ajouter a toutes les responses
    security_headers = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-XSS-Protection": "1; mode=block",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    # Endpoints qui necessitent Cache-Control: no-store
    AUTH_PATHS = {"/auth/", "/api/v1/auth/", "/mfa/", "/api/v1/mfa/"}

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Ajoute les headers de securite a chaque response.

        Inclut:
        - HTTPS redirect en production (si FORCE_HTTPS=True)
        - Headers de securite sur toutes les responses

        Args:
            request: La requete entrante
            call_next: Le prochain handler

        Returns:
            Response avec les headers de securite ajoutes
        """
        settings = get_settings()

        # HTTPS redirect en production
        if settings.FORCE_HTTPS and settings.is_production:
            # Verifier si la requete est en HTTPS
            # X-Forwarded-Proto est set par les reverse proxies (nginx, traefik)
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            is_https = (
                request.url.scheme == "https" or
                forwarded_proto.lower() == "https"
            )

            if not is_https:
                # Rediriger vers HTTPS
                https_url = request.url.replace(scheme="https")
                return RedirectResponse(
                    url=str(https_url),
                    status_code=301  # Permanent redirect
                )

        response = await call_next(request)

        # Ajouter les headers de securite
        for header, value in self.security_headers.items():
            response.headers[header] = value

        # Cache-Control pour les endpoints sensibles
        path = request.url.path
        if any(auth_path in path for auth_path in self.AUTH_PATHS):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response
