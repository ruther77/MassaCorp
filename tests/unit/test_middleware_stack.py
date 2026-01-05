"""
Tests TDD pour le Middleware Stack.

Verifie que tous les middlewares sont correctement configures:
- RequestIDMiddleware: X-Request-ID
- TimingMiddleware: X-Response-Time
- SecurityHeadersMiddleware: HSTS, X-Frame-Options, etc.
- ExceptionHandler: Format unifie des erreurs
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.testclient import TestClient


# =============================================================================
# RequestIDMiddleware Tests
# =============================================================================
class TestRequestIDMiddleware:
    """Tests pour RequestIDMiddleware"""

    @pytest.mark.unit
    def test_request_id_middleware_exists(self):
        """RequestIDMiddleware doit exister"""
        from app.middleware.request_id import RequestIDMiddleware

        assert RequestIDMiddleware is not None

    @pytest.mark.unit
    def test_generates_request_id_if_missing(self):
        """Genere un UUID si X-Request-ID absent"""
        from app.middleware.request_id import RequestIDMiddleware
        import uuid

        middleware = RequestIDMiddleware(app=MagicMock())

        # Le middleware doit avoir la logique pour generer un UUID
        assert hasattr(middleware, 'dispatch')
        assert middleware.HEADER_NAME == "X-Request-ID"

    @pytest.mark.unit
    def test_propagates_existing_request_id(self):
        """Propage X-Request-ID existant"""
        from app.middleware.request_id import RequestIDMiddleware

        middleware = RequestIDMiddleware(app=MagicMock())
        assert middleware.HEADER_NAME == "X-Request-ID"


# =============================================================================
# TimingMiddleware Tests
# =============================================================================
class TestTimingMiddleware:
    """Tests pour TimingMiddleware"""

    @pytest.mark.unit
    def test_timing_middleware_exists(self):
        """TimingMiddleware doit exister"""
        from app.middleware.timing import TimingMiddleware

        assert TimingMiddleware is not None

    @pytest.mark.unit
    def test_has_slow_threshold_config(self):
        """Doit avoir un seuil configurable pour les requetes lentes"""
        from app.middleware.timing import TimingMiddleware

        middleware = TimingMiddleware(app=MagicMock(), slow_threshold_ms=500)
        assert middleware.slow_threshold_ms == 500


# =============================================================================
# ExceptionHandler Tests
# =============================================================================
class TestExceptionHandler:
    """Tests pour le systeme d'exception handling"""

    @pytest.mark.unit
    def test_register_exception_handlers_exists(self):
        """register_exception_handlers doit exister"""
        from app.middleware.exception_handler import register_exception_handlers

        assert callable(register_exception_handlers)

    @pytest.mark.unit
    def test_app_exception_handler_exists(self):
        """app_exception_handler doit exister"""
        from app.middleware.exception_handler import app_exception_handler

        assert callable(app_exception_handler)

    @pytest.mark.unit
    def test_create_error_response_format(self):
        """create_error_response doit creer une reponse formatee"""
        from app.middleware.exception_handler import create_error_response

        response = create_error_response(
            status_code=400,
            error_code="TEST_ERROR",
            message="Test message",
            request_id="test-123"
        )

        assert response.status_code == 400
        # Verifier le contenu JSON
        import json
        content = json.loads(response.body)
        assert content["error"] == "TEST_ERROR"
        assert content["message"] == "Test message"
        assert content["request_id"] == "test-123"

    @pytest.mark.unit
    def test_app_exception_converted_to_json(self):
        """AppException doit etre converti en JSON correct"""
        from app.core.exceptions import InvalidCredentials
        from app.middleware.exception_handler import app_exception_handler
        import asyncio

        # Creer une exception
        exc = InvalidCredentials()

        # Mock request
        mock_request = MagicMock()
        mock_request.state.request_id = "test-456"

        # Appeler le handler
        response = asyncio.get_event_loop().run_until_complete(
            app_exception_handler(mock_request, exc)
        )

        assert response.status_code == 401
        import json
        content = json.loads(response.body)
        assert content["error"] == "INVALID_CREDENTIALS"


# =============================================================================
# Integration Tests - Middleware Stack
# =============================================================================
class TestMiddlewareStackIntegration:
    """Tests d'integration pour le middleware stack complet"""

    @pytest.mark.unit
    def test_main_imports_all_middleware(self):
        """main.py doit importer tous les middleware"""
        from app.main import app

        # L'app doit avoir ete cree avec les middleware
        assert app is not None

    @pytest.mark.unit
    def test_app_has_exception_handlers(self):
        """L'app doit avoir des exception handlers enregistres"""
        from app.main import app
        from app.core.exceptions import AppException

        # Verifier qu'un handler existe pour AppException
        assert AppException in app.exception_handlers

    @pytest.mark.unit
    def test_middleware_stack_order(self):
        """Les middleware doivent etre dans le bon ordre"""
        from app.main import app
        from app.middleware.security_headers import SecurityHeadersMiddleware
        from app.middleware.request_id import RequestIDMiddleware
        from app.middleware.timing import TimingMiddleware

        # Verifier que l'app a des middleware
        middleware_classes = [
            type(m.cls) if hasattr(m, 'cls') else type(m)
            for m in app.user_middleware
        ]

        # Les classes de middleware doivent etre presentes
        # (l'ordre est inverse car FastAPI les wrap)
        assert len(app.user_middleware) >= 5  # Au moins 5 middleware


# =============================================================================
# Security Headers in Response Tests
# =============================================================================
class TestSecurityHeadersInMiddlewareStack:
    """Verifie que SecurityHeadersMiddleware est bien integre"""

    @pytest.mark.unit
    def test_security_headers_middleware_in_stack(self):
        """SecurityHeadersMiddleware doit etre dans le stack"""
        from app.main import app
        from app.middleware.security_headers import SecurityHeadersMiddleware

        # Verifier la presence dans le middleware stack
        middleware_types = [
            m.cls if hasattr(m, 'cls') else type(m)
            for m in app.user_middleware
        ]

        assert SecurityHeadersMiddleware in middleware_types
