"""
Tests comportementaux pour les headers de securite HTTP.

Ces tests verifient que les headers de securite sont correctement
appliques, notamment le Content-Security-Policy (CSP).

SECURITE CRITIQUE:
- CSP protege contre les attaques XSS
- HSTS force HTTPS
- X-Frame-Options/frame-ancestors protege contre le clickjacking
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.security_headers import SecurityHeadersMiddleware


class TestCSPHeader:
    """Tests pour le header Content-Security-Policy."""

    def test_csp_header_is_present(self):
        """CSP doit etre present dans les headers de securite."""
        assert "Content-Security-Policy" in SecurityHeadersMiddleware.security_headers

    def test_csp_default_src_self(self):
        """CSP doit avoir default-src 'self'."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    def test_csp_script_src_self(self):
        """CSP doit restreindre les scripts a 'self'."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "script-src 'self'" in csp

    def test_csp_frame_ancestors_none(self):
        """CSP doit bloquer le framing avec frame-ancestors 'none'."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    def test_csp_img_src_allows_data_for_qrcodes(self):
        """img-src doit autoriser data: pour les QR codes MFA base64."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "img-src" in csp
        assert "data:" in csp

    def test_csp_upgrade_insecure_requests(self):
        """CSP doit inclure upgrade-insecure-requests."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "upgrade-insecure-requests" in csp

    def test_csp_base_uri_self(self):
        """CSP doit restreindre base-uri a 'self'."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "base-uri 'self'" in csp

    def test_csp_form_action_self(self):
        """CSP doit restreindre form-action a 'self'."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "form-action 'self'" in csp


class TestOtherSecurityHeaders:
    """Tests pour les autres headers de securite."""

    def test_hsts_header_present(self):
        """HSTS doit etre present."""
        headers = SecurityHeadersMiddleware.security_headers
        assert "Strict-Transport-Security" in headers

    def test_hsts_includes_subdomains(self):
        """HSTS doit inclure les sous-domaines."""
        hsts = SecurityHeadersMiddleware.security_headers["Strict-Transport-Security"]
        assert "includeSubDomains" in hsts

    def test_hsts_preload_directive(self):
        """HSTS doit avoir la directive preload."""
        hsts = SecurityHeadersMiddleware.security_headers["Strict-Transport-Security"]
        assert "preload" in hsts

    def test_x_content_type_options_nosniff(self):
        """X-Content-Type-Options doit etre nosniff."""
        headers = SecurityHeadersMiddleware.security_headers
        assert headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_deny(self):
        """X-Frame-Options doit etre DENY."""
        headers = SecurityHeadersMiddleware.security_headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection_disabled(self):
        """
        X-XSS-Protection doit etre desactive (0).
        CSP est plus efficace et X-XSS-Protection peut causer des problemes.
        """
        headers = SecurityHeadersMiddleware.security_headers
        assert headers["X-XSS-Protection"] == "0"

    def test_referrer_policy_present(self):
        """Referrer-Policy doit etre present."""
        headers = SecurityHeadersMiddleware.security_headers
        assert "Referrer-Policy" in headers

    def test_permissions_policy_restrictive(self):
        """Permissions-Policy doit desactiver les fonctionnalites sensibles."""
        policy = SecurityHeadersMiddleware.security_headers["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy


class TestSecurityHeadersMiddlewareBehavior:
    """Tests comportementaux pour le middleware."""

    @pytest.fixture
    def middleware(self):
        """Cree une instance du middleware."""
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.mark.asyncio
    async def test_headers_added_to_response(self, middleware):
        """Le middleware doit ajouter les headers a la response."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/users"
        mock_request.url.scheme = "https"
        mock_request.headers = {}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        # Mock get_settings
        with patch('app.middleware.security_headers.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                FORCE_HTTPS=False,
                is_production=False
            )

            # Act
            await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "Content-Security-Policy" in mock_response.headers
        assert "Strict-Transport-Security" in mock_response.headers
        assert "X-Frame-Options" in mock_response.headers

    @pytest.mark.asyncio
    async def test_cache_control_for_auth_endpoints(self, middleware):
        """Les endpoints auth doivent avoir Cache-Control: no-store."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/auth/login"
        mock_request.url.scheme = "https"
        mock_request.headers = {}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        with patch('app.middleware.security_headers.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                FORCE_HTTPS=False,
                is_production=False
            )

            # Act
            await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert mock_response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"
        assert mock_response.headers.get("Pragma") == "no-cache"

    @pytest.mark.asyncio
    async def test_cache_control_for_mfa_endpoints(self, middleware):
        """Les endpoints MFA doivent avoir Cache-Control: no-store."""
        # Arrange
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/mfa/verify"
        mock_request.url.scheme = "https"
        mock_request.headers = {}

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request):
            return mock_response

        with patch('app.middleware.security_headers.get_settings') as mock_settings:
            mock_settings.return_value = MagicMock(
                FORCE_HTTPS=False,
                is_production=False
            )

            # Act
            await middleware.dispatch(mock_request, mock_call_next)

        # Assert
        assert "no-store" in mock_response.headers.get("Cache-Control", "")


class TestCSPCompliance:
    """Tests de conformite CSP."""

    def test_no_unsafe_eval_in_script_src(self):
        """
        SECURITE: script-src ne doit PAS contenir 'unsafe-eval'.
        unsafe-eval permet eval() qui est dangereux.
        """
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "'unsafe-eval'" not in csp

    def test_connect_src_restricted(self):
        """connect-src doit etre restreint."""
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        assert "connect-src 'self'" in csp

    def test_no_wildcard_sources(self):
        """
        SECURITE: Pas de wildcard (*) dans les sources critiques.
        """
        csp = SecurityHeadersMiddleware.security_headers["Content-Security-Policy"]
        # Verifier les directives critiques
        assert "script-src *" not in csp
        assert "connect-src *" not in csp
        assert "default-src *" not in csp
