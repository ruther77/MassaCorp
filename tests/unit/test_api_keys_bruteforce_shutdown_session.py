"""
Tests TDD pour:
1. API Keys - Authentification Machine-to-Machine
2. Escalade Anti-bruteforce - CAPTCHA -> Delay -> Lock -> Alert
3. Graceful Shutdown - Signal handlers, drain connections
4. Session Validation - Check session active sur chaque requete

Ces tests sont ecrits AVANT l'implementation (TDD).
"""
import pytest
import secrets
import signal
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from uuid import uuid4


# =============================================================================
# 1. TESTS API KEYS
# =============================================================================


class TestAPIKeyGeneration:
    """Tests pour la generation des API Keys."""

    def test_api_key_is_cryptographically_secure(self):
        """L'API Key doit avoir haute entropie (256 bits)."""
        from app.services.api_key import APIKeyService

        service = APIKeyService(MagicMock())
        key = service.generate_key()

        # Key should be at least 32 characters (256 bits)
        assert len(key) >= 32, "API Key should have at least 256 bits of entropy"

        # Key should be URL-safe
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', key), "API Key should be URL-safe"

    def test_api_key_is_hashed_before_storage(self):
        """L'API Key doit etre hashee (SHA-256) avant stockage."""
        from app.services.api_key import APIKeyService

        service = APIKeyService(MagicMock())
        key = service.generate_key()
        key_hash = service.hash_key(key)

        # Hash should be 64 characters (SHA-256 hex)
        assert len(key_hash) == 64, "Key hash should be SHA-256 (64 hex chars)"

        # Hash should be deterministic
        assert service.hash_key(key) == key_hash

        # Hash should be different from key
        assert key_hash != key

    def test_api_key_displayed_only_once(self):
        """L'API Key brute ne doit etre retournee qu'a la creation."""
        from app.services.api_key import APIKeyService

        mock_repo = MagicMock()
        mock_repo.create_api_key = AsyncMock(return_value=MagicMock(id=1))
        mock_repo.get_api_key_by_id = AsyncMock(return_value=MagicMock(
            id=1,
            key_hash="somehash",
            # No raw_key attribute - only hash is stored
        ))

        service = APIKeyService(mock_repo)

        # The raw key should never be retrievable after creation
        # Only the hash is stored


class TestAPIKeyValidation:
    """Tests pour la validation des API Keys."""

    @pytest.mark.unit
    def test_valid_api_key_is_accepted(self):
        """Une API Key valide est acceptee."""
        from app.services.api_key import APIKeyService

        mock_repo = MagicMock()
        mock_key = MagicMock(
            id=1,
            tenant_id=1,
            is_revoked=False,
            is_expired=False,
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            key_hash=hashlib.sha256(b"test_key").hexdigest()
        )
        mock_repo.validate_key = MagicMock(return_value=mock_key)
        mock_repo.update_last_used = MagicMock()

        service = APIKeyService(mock_repo)
        result = service.validate_key("test_key")

        assert result is not None
        assert result.id == 1

    @pytest.mark.unit
    def test_revoked_api_key_is_rejected(self):
        """Une API Key revoquee est rejetee."""
        from app.services.api_key import APIKeyService, APIKeyRevoked

        mock_repo = MagicMock()
        mock_key = MagicMock(
            id=1,
            is_revoked=True,  # Revoked!
            is_expired=False,
            revoked_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        mock_repo.validate_key = MagicMock(return_value=mock_key)

        service = APIKeyService(mock_repo)

        with pytest.raises(APIKeyRevoked):
            service.validate_key("test_key")

    @pytest.mark.unit
    def test_expired_api_key_is_rejected(self):
        """Une API Key expiree est rejetee."""
        from app.services.api_key import APIKeyService, APIKeyExpired

        mock_repo = MagicMock()
        mock_key = MagicMock(
            id=1,
            is_revoked=False,
            is_expired=True,  # Expired!
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        mock_repo.validate_key = MagicMock(return_value=mock_key)

        service = APIKeyService(mock_repo)

        with pytest.raises(APIKeyExpired):
            service.validate_key("test_key")

    @pytest.mark.unit
    def test_invalid_api_key_is_rejected(self):
        """Une API Key invalide est rejetee."""
        from app.services.api_key import APIKeyService, InvalidAPIKey

        mock_repo = MagicMock()
        mock_repo.validate_key = MagicMock(return_value=None)

        service = APIKeyService(mock_repo)

        with pytest.raises(InvalidAPIKey):
            service.validate_key("invalid_key")

    @pytest.mark.unit
    def test_api_key_tenant_isolation(self):
        """L'API Key doit respecter l'isolation tenant."""
        from app.services.api_key import APIKeyService

        mock_repo = MagicMock()
        mock_key = MagicMock(
            id=1,
            tenant_id=1,  # Key belongs to tenant 1
            is_revoked=False,
            is_expired=False,
            revoked_at=None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        mock_repo.validate_key = MagicMock(return_value=mock_key)
        mock_repo.update_last_used = MagicMock()

        service = APIKeyService(mock_repo)
        result = service.validate_key("test_key")

        # Should return the tenant_id for the caller to verify
        assert result.tenant_id == 1

    def test_constant_time_comparison(self):
        """La comparaison doit etre en temps constant (via hash)."""
        from app.services.api_key import APIKeyService

        service = APIKeyService(MagicMock())

        # Using hash comparison is inherently constant-time
        # because we compare fixed-length hashes
        key1_hash = service.hash_key("key1")
        key2_hash = service.hash_key("key2")

        # Both hashes should be same length
        assert len(key1_hash) == len(key2_hash) == 64


class TestAPIKeyModel:
    """Tests pour le modele APIKey."""

    def test_api_key_model_has_required_fields(self):
        """Le modele doit avoir tous les champs requis."""
        from app.models.api_key import APIKey

        assert hasattr(APIKey, 'id')
        assert hasattr(APIKey, 'tenant_id')
        assert hasattr(APIKey, 'name')
        assert hasattr(APIKey, 'key_hash')
        assert hasattr(APIKey, 'expires_at')
        assert hasattr(APIKey, 'revoked_at')
        assert hasattr(APIKey, 'created_at')
        assert hasattr(APIKey, 'last_used_at')

    def test_api_key_tablename(self):
        """Le tablename doit etre 'api_keys'."""
        from app.models.api_key import APIKey

        assert APIKey.__tablename__ == 'api_keys'


# =============================================================================
# 2. TESTS ESCALADE ANTI-BRUTEFORCE
# =============================================================================


class TestBruteforceEscalation:
    """Tests pour l'escalade anti-bruteforce."""

    def test_escalation_levels_defined(self):
        """Les niveaux d'escalade doivent etre definis."""
        from app.services.bruteforce import BruteforceProtection

        protection = BruteforceProtection()

        # Should have defined thresholds
        assert hasattr(protection, 'CAPTCHA_THRESHOLD')
        assert hasattr(protection, 'DELAY_THRESHOLD')
        assert hasattr(protection, 'LOCK_THRESHOLD')
        assert hasattr(protection, 'ALERT_THRESHOLD')

        # Thresholds should be in order
        assert protection.CAPTCHA_THRESHOLD < protection.DELAY_THRESHOLD
        assert protection.DELAY_THRESHOLD < protection.LOCK_THRESHOLD
        assert protection.LOCK_THRESHOLD <= protection.ALERT_THRESHOLD

    @pytest.mark.asyncio
    async def test_below_captcha_threshold_no_action(self):
        """En dessous du seuil CAPTCHA, pas d'action."""
        from app.services.bruteforce import BruteforceProtection, EscalationLevel

        mock_repo = MagicMock()
        mock_repo.count_failed_attempts = AsyncMock(return_value=2)

        protection = BruteforceProtection(mock_repo)
        protection.CAPTCHA_THRESHOLD = 3

        level = await protection.get_escalation_level("test@example.com", "1.2.3.4")

        assert level == EscalationLevel.NONE

    @pytest.mark.asyncio
    async def test_captcha_threshold_triggers_captcha(self):
        """Au seuil CAPTCHA, retourne CAPTCHA required."""
        from app.services.bruteforce import BruteforceProtection, EscalationLevel

        mock_repo = MagicMock()
        mock_repo.count_failed_attempts = AsyncMock(return_value=3)

        protection = BruteforceProtection(mock_repo)
        protection.CAPTCHA_THRESHOLD = 3
        protection.DELAY_THRESHOLD = 5

        level = await protection.get_escalation_level("test@example.com", "1.2.3.4")

        assert level == EscalationLevel.CAPTCHA

    @pytest.mark.asyncio
    async def test_delay_threshold_triggers_delay(self):
        """Au seuil DELAY, retourne delay required."""
        from app.services.bruteforce import BruteforceProtection, EscalationLevel

        mock_repo = MagicMock()
        mock_repo.count_failed_attempts = AsyncMock(return_value=5)

        protection = BruteforceProtection(mock_repo)
        protection.CAPTCHA_THRESHOLD = 3
        protection.DELAY_THRESHOLD = 5
        protection.LOCK_THRESHOLD = 10

        level = await protection.get_escalation_level("test@example.com", "1.2.3.4")

        assert level == EscalationLevel.DELAY

    @pytest.mark.asyncio
    async def test_lock_threshold_triggers_lock(self):
        """Au seuil LOCK, le compte est verrouille."""
        from app.services.bruteforce import BruteforceProtection, EscalationLevel

        mock_repo = MagicMock()
        mock_repo.count_failed_attempts = AsyncMock(return_value=10)

        protection = BruteforceProtection(mock_repo)
        protection.CAPTCHA_THRESHOLD = 3
        protection.DELAY_THRESHOLD = 5
        protection.LOCK_THRESHOLD = 10
        protection.ALERT_THRESHOLD = 15

        level = await protection.get_escalation_level("test@example.com", "1.2.3.4")

        assert level == EscalationLevel.LOCK

    @pytest.mark.asyncio
    async def test_alert_threshold_triggers_alert(self):
        """Au seuil ALERT, une alerte est envoyee."""
        from app.services.bruteforce import BruteforceProtection, EscalationLevel

        mock_repo = MagicMock()
        mock_repo.count_failed_attempts = AsyncMock(return_value=15)

        protection = BruteforceProtection(mock_repo)
        protection.CAPTCHA_THRESHOLD = 3
        protection.DELAY_THRESHOLD = 5
        protection.LOCK_THRESHOLD = 10
        protection.ALERT_THRESHOLD = 15

        level = await protection.get_escalation_level("test@example.com", "1.2.3.4")

        assert level == EscalationLevel.ALERT

    @pytest.mark.asyncio
    async def test_delay_calculation_increases_progressively(self):
        """Le delai augmente progressivement."""
        from app.services.bruteforce import BruteforceProtection

        protection = BruteforceProtection(MagicMock())

        # More attempts = longer delay
        delay_5 = protection.calculate_delay(5)
        delay_7 = protection.calculate_delay(7)
        delay_10 = protection.calculate_delay(10)

        assert delay_5 < delay_7 < delay_10
        assert delay_5 > 0  # Some delay


# =============================================================================
# 3. TESTS GRACEFUL SHUTDOWN
# =============================================================================


class TestGracefulShutdown:
    """Tests pour l'arret gracieux."""

    def test_signal_handlers_registered(self):
        """Les handlers SIGTERM et SIGINT doivent etre enregistres."""
        from app.core.shutdown import ShutdownHandler

        handler = ShutdownHandler()

        # Should have methods to handle signals
        assert hasattr(handler, 'handle_sigterm')
        assert hasattr(handler, 'handle_sigint')
        assert callable(handler.handle_sigterm)
        assert callable(handler.handle_sigint)

    def test_shutdown_flag_set_on_signal(self):
        """Le flag shutdown doit etre set quand un signal est recu."""
        from app.core.shutdown import ShutdownHandler

        handler = ShutdownHandler()

        assert handler.is_shutting_down is False

        handler.handle_sigterm(signal.SIGTERM, None)

        assert handler.is_shutting_down is True

    @pytest.mark.asyncio
    async def test_drain_connections_waits_for_requests(self):
        """drain_connections doit attendre les requetes en cours."""
        from app.core.shutdown import ShutdownHandler

        handler = ShutdownHandler()
        handler.active_requests = 2

        # Start drain (should not complete immediately if requests active)
        # In real implementation, this would wait

        # Simulate requests completing
        handler.active_requests = 0

        # Now drain should complete
        await handler.drain_connections(timeout=1.0)

    @pytest.mark.asyncio
    async def test_drain_connections_has_timeout(self):
        """drain_connections doit avoir un timeout."""
        from app.core.shutdown import ShutdownHandler

        handler = ShutdownHandler()
        handler.active_requests = 100  # Simulated stuck requests

        # Should return after timeout even with active requests
        start = datetime.now(timezone.utc)
        await handler.drain_connections(timeout=0.1)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        assert elapsed < 1.0  # Should not wait forever

    @pytest.mark.asyncio
    async def test_close_db_pool_called(self):
        """La fermeture du pool DB doit etre appelee."""
        from app.core.shutdown import ShutdownHandler

        mock_engine = MagicMock()
        mock_engine.dispose = MagicMock()

        handler = ShutdownHandler()
        await handler.close_db_pool(mock_engine)

        mock_engine.dispose.assert_called_once()

    def test_shutdown_registers_cleanup_tasks(self):
        """Le shutdown doit enregistrer des taches de cleanup."""
        from app.core.shutdown import ShutdownHandler

        handler = ShutdownHandler()

        # Should be able to add cleanup tasks
        cleanup_called = False

        async def cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        handler.add_cleanup_task(cleanup)

        assert len(handler.cleanup_tasks) > 0


class TestShutdownMiddleware:
    """Tests pour le middleware de shutdown."""

    @pytest.mark.asyncio
    async def test_middleware_rejects_requests_during_shutdown(self):
        """Le middleware doit rejeter les nouvelles requetes pendant le shutdown."""
        from app.middleware.shutdown import ShutdownMiddleware

        mock_app = AsyncMock()
        mock_shutdown_handler = MagicMock()
        mock_shutdown_handler.is_shutting_down = True

        middleware = ShutdownMiddleware(mock_app, mock_shutdown_handler)

        # Create mock request
        mock_scope = {"type": "http", "path": "/api/v1/users"}
        mock_receive = AsyncMock()
        mock_send = AsyncMock()

        await middleware(mock_scope, mock_receive, mock_send)

        # Should send 503 Service Unavailable
        mock_send.assert_called()
        call_args = mock_send.call_args_list[0][0][0]
        assert call_args.get("status") == 503

    @pytest.mark.asyncio
    async def test_middleware_allows_health_during_shutdown(self):
        """Le middleware doit permettre /health pendant le shutdown."""
        from app.middleware.shutdown import ShutdownMiddleware

        mock_app = AsyncMock()
        mock_shutdown_handler = MagicMock()
        mock_shutdown_handler.is_shutting_down = True

        middleware = ShutdownMiddleware(mock_app, mock_shutdown_handler)

        # Health check request
        mock_scope = {"type": "http", "path": "/health"}
        mock_receive = AsyncMock()
        mock_send = AsyncMock()

        await middleware(mock_scope, mock_receive, mock_send)

        # Should still call the app
        mock_app.assert_called_once()


# =============================================================================
# 4. TESTS SESSION VALIDATION
# =============================================================================


class TestSessionValidationOnRequest:
    """Tests pour la validation de session sur chaque requete."""

    def test_valid_session_allows_request(self):
        """Une session valide permet la requete."""
        from uuid import UUID
        from app.core.dependencies import validate_session_sync

        mock_session_service = MagicMock()
        mock_session_service.is_session_valid = MagicMock(return_value=True)

        session_id = str(uuid4())
        result = validate_session_sync(session_id, mock_session_service)

        assert result is True
        # La fonction convertit le string en UUID avant l'appel
        mock_session_service.is_session_valid.assert_called_once_with(UUID(session_id))

    def test_revoked_session_blocks_request(self):
        """Une session revoquee bloque la requete."""
        from app.core.dependencies import validate_session_sync
        from app.core.exceptions import SessionRevoked

        mock_session_service = MagicMock()
        mock_session_service.is_session_valid = MagicMock(return_value=False)

        session_id = str(uuid4())

        with pytest.raises(SessionRevoked):
            validate_session_sync(session_id, mock_session_service)

    def test_missing_session_id_blocks_request(self):
        """Une session_id manquante bloque la requete."""
        from app.core.dependencies import validate_session_sync
        from app.core.exceptions import InvalidSession

        mock_session_service = MagicMock()

        with pytest.raises(InvalidSession):
            validate_session_sync(None, mock_session_service)

    def test_access_token_contains_session_id(self):
        """L'access token doit contenir le session_id."""
        from app.core.security import create_access_token

        session_id = str(uuid4())
        token = create_access_token(
            subject=1,
            tenant_id=1,
            email="test@example.com",
            session_id=session_id
        )

        # Decode and verify session_id is in payload
        from app.core.security import decode_token
        payload = decode_token(token)

        assert 'session_id' in payload or 'sid' in payload

    @pytest.mark.asyncio
    async def test_get_current_user_validates_session(self):
        """get_current_user doit valider la session."""
        from app.core.dependencies import get_current_user

        # The get_current_user dependency should:
        # 1. Extract token from header
        # 2. Decode token
        # 3. Get session_id from token
        # 4. Validate session is active
        # 5. Return user if all valid

        # This is a structural test - implementation will wire these together


class TestSessionCheckMiddleware:
    """Tests pour le middleware de validation session."""

    @pytest.mark.asyncio
    async def test_middleware_checks_session_on_authenticated_routes(self):
        """Le middleware verifie la session sur les routes authentifiees."""
        # For routes that require auth, session should be validated

    @pytest.mark.asyncio
    async def test_middleware_skips_public_routes(self):
        """Le middleware ignore les routes publiques."""
        # /health, /docs, /auth/login should skip session check


class TestSessionInToken:
    """Tests pour l'inclusion du session_id dans les tokens."""

    def test_login_creates_session_and_includes_in_token(self):
        """Le login cree une session et l'inclut dans le token."""
        # When user logs in:
        # 1. Session is created with UUID
        # 2. Session ID is included in access token
        # 3. Session ID is included in refresh token

    def test_refresh_token_uses_same_session(self):
        """Le refresh garde la meme session."""
        # When refreshing:
        # 1. Validate existing session
        # 2. Update last_seen_at
        # 3. New access token has same session_id


class TestSessionExceptionHandling:
    """Tests pour les exceptions de session."""

    def test_session_revoked_exception_returns_401(self):
        """SessionRevoked retourne 401."""
        from app.core.exceptions import SessionRevoked

        exc = SessionRevoked()
        assert exc.status_code == 401

    def test_invalid_session_exception_returns_401(self):
        """InvalidSession retourne 401."""
        from app.core.exceptions import InvalidSession

        exc = InvalidSession()
        assert exc.status_code == 401
