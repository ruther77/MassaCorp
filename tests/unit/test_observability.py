"""
Tests pour les fonctionnalites d'observabilite.

Couvre:
- Structured logging avec sanitization
- Metriques
- Health checks
- Cleanup tasks
"""
import pytest
from unittest.mock import MagicMock, patch


# =============================================================================
# Tests Structured Logging
# =============================================================================
class TestStructuredLogging:
    """Tests pour le logging structure"""

    @pytest.mark.unit
    def test_sanitize_dict_redacts_passwords(self):
        """Les mots de passe doivent etre masques"""
        from app.core.logging import sanitize_dict

        data = {
            "email": "user@example.com",
            "password": "supersecret123",
            "name": "Test User"
        }

        result = sanitize_dict(data)

        assert result["email"] == "user@example.com"
        assert "supersecret" not in result["password"]
        assert "[REDACTED]" in result["password"]
        assert result["name"] == "Test User"

    @pytest.mark.unit
    def test_sanitize_dict_redacts_tokens(self):
        """Les tokens doivent etre masques"""
        from app.core.logging import sanitize_dict

        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx",
            "refresh_token": "long_refresh_token_value",
        }

        result = sanitize_dict(data)

        assert "[REDACTED]" in result["access_token"]
        assert "[REDACTED]" in result["refresh_token"]

    @pytest.mark.unit
    def test_sanitize_dict_handles_nested(self):
        """Doit sanitizer les dictionnaires imbriques"""
        from app.core.logging import sanitize_dict

        data = {
            "user": {
                "email": "test@example.com",
                "password_hash": "bcrypt_hash_value"
            }
        }

        result = sanitize_dict(data)

        assert result["user"]["email"] == "test@example.com"
        assert "[REDACTED]" in result["user"]["password_hash"]

    @pytest.mark.unit
    def test_json_formatter_exists(self):
        """JSONFormatter doit exister"""
        from app.core.logging import JSONFormatter

        assert JSONFormatter is not None

    @pytest.mark.unit
    def test_configure_logging_works(self):
        """configure_logging ne doit pas lever d'exception"""
        from app.core.logging import configure_logging

        # Ne doit pas lever d'exception
        configure_logging(level="DEBUG", json_format=False)


# =============================================================================
# Tests Metrics
# =============================================================================
class TestMetrics:
    """Tests pour les metriques"""

    @pytest.mark.unit
    def test_metrics_registry_exists(self):
        """MetricsRegistry doit exister"""
        from app.core.metrics import MetricsRegistry

        assert MetricsRegistry is not None

    @pytest.mark.unit
    def test_metrics_instance_exists(self):
        """L'instance globale metrics doit exister"""
        from app.core.metrics import metrics

        assert metrics is not None

    @pytest.mark.unit
    def test_simple_counter_increment(self):
        """SimpleCounter doit s'incrementer"""
        from app.core.metrics import SimpleCounter

        counter = SimpleCounter("test_counter", "Test", ["label1"])
        counter.inc(label1="value1")
        counter.inc(label1="value1")
        counter.inc(label1="value2")

        assert counter.get(label1="value1") == 2
        assert counter.get(label1="value2") == 1

    @pytest.mark.unit
    def test_simple_histogram_observe(self):
        """SimpleHistogram doit enregistrer les observations"""
        from app.core.metrics import SimpleHistogram

        histogram = SimpleHistogram("test_histogram", "Test", ["method"])
        histogram.observe(0.5, method="GET")
        histogram.observe(1.5, method="GET")

        assert histogram.get_count(method="GET") == 2
        assert histogram.get_sum(method="GET") == 2.0

    @pytest.mark.unit
    def test_metrics_middleware_exists(self):
        """MetricsMiddleware doit exister"""
        from app.core.metrics import MetricsMiddleware

        assert MetricsMiddleware is not None


# =============================================================================
# Tests Health Checks
# =============================================================================
class TestHealthChecks:
    """Tests pour les health checks"""

    @pytest.mark.unit
    def test_health_router_exists(self):
        """Le router health doit exister"""
        from app.api.health import router

        assert router is not None

    @pytest.mark.unit
    def test_health_endpoint_in_app(self):
        """L'endpoint /health doit etre dans l'app"""
        from app.main import app

        routes = [route.path for route in app.routes]
        assert "/health" in routes

    @pytest.mark.unit
    def test_ready_endpoint_in_app(self):
        """L'endpoint /ready doit etre dans l'app"""
        from app.main import app

        routes = [route.path for route in app.routes]
        assert "/ready" in routes

    @pytest.mark.unit
    def test_check_database_function_exists(self):
        """La fonction check_database doit exister"""
        from app.api.health import check_database

        assert callable(check_database)


# =============================================================================
# Tests Cleanup Tasks
# =============================================================================
class TestCleanupTasks:
    """Tests pour les taches de nettoyage"""

    @pytest.mark.unit
    def test_cleanup_module_exists(self):
        """Le module cleanup doit exister"""
        from app.tasks import cleanup

        assert cleanup is not None

    @pytest.mark.unit
    def test_cleanup_revoked_tokens_function_exists(self):
        """La fonction cleanup_revoked_tokens doit exister"""
        from app.tasks.cleanup import cleanup_revoked_tokens

        assert callable(cleanup_revoked_tokens)

    @pytest.mark.unit
    def test_cleanup_refresh_tokens_function_exists(self):
        """La fonction cleanup_refresh_tokens doit exister"""
        from app.tasks.cleanup import cleanup_refresh_tokens

        assert callable(cleanup_refresh_tokens)

    @pytest.mark.unit
    def test_cleanup_old_sessions_function_exists(self):
        """La fonction cleanup_old_sessions doit exister"""
        from app.tasks.cleanup import cleanup_old_sessions

        assert callable(cleanup_old_sessions)

    @pytest.mark.unit
    def test_retention_config_exists(self):
        """La config de retention doit exister"""
        from app.tasks.cleanup import RETENTION_CONFIG

        assert "revoked_tokens" in RETENTION_CONFIG
        assert "refresh_tokens" in RETENTION_CONFIG
        assert "sessions_revoked" in RETENTION_CONFIG

    @pytest.mark.unit
    def test_cleanup_all_sync_function_exists(self):
        """La fonction cleanup_all_sync doit exister"""
        from app.tasks.cleanup import cleanup_all_sync

        assert callable(cleanup_all_sync)
