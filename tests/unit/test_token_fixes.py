"""
Tests TDD - Corrections Token et Refresh

Tests RED ecrits AVANT implementation pour:
- Issue #4: Double stockage refresh token
- Issue #5: Session non verifiee au refresh
- Issue #12: get_user_tokens() code mort

Ces tests DOIVENT echouer avant implementation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
from uuid import uuid4


class TestRefreshTokenRotation:
    """Tests Issue #4: Double stockage refresh token"""

    @pytest.fixture
    def mock_refresh_token_repo(self):
        """Mock RefreshTokenRepository"""
        from app.repositories.refresh_token import RefreshTokenRepository
        return MagicMock(spec=RefreshTokenRepository)

    @pytest.fixture
    def mock_revoked_token_repo(self):
        """Mock RevokedTokenRepository"""
        from app.repositories.revoked_token import RevokedTokenRepository
        return MagicMock(spec=RevokedTokenRepository)

    @pytest.fixture
    def token_service(self, mock_refresh_token_repo, mock_revoked_token_repo):
        """TokenService avec mocks"""
        from app.services.token import TokenService
        return TokenService(
            refresh_token_repository=mock_refresh_token_repo,
            revoked_token_repository=mock_revoked_token_repo
        )

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def mock_session_service(self):
        """Mock SessionService"""
        from app.services.session import SessionService
        service = MagicMock(spec=SessionService)
        service.is_account_locked.return_value = False
        return service

    @pytest.fixture
    def mock_token_service(self):
        """Mock TokenService"""
        from app.services.token import TokenService
        mock = MagicMock(spec=TokenService)
        mock.refresh_token_repository = MagicMock()
        return mock

    @pytest.fixture
    def mock_audit_service(self):
        """Mock AuditService"""
        from app.services.audit import AuditService
        return MagicMock(spec=AuditService)

    @pytest.fixture
    def mock_mfa_service(self):
        """Mock MFAService"""
        from app.services.mfa import MFAService
        service = MagicMock(spec=MFAService)
        service.is_mfa_enabled.return_value = False
        return service

    @pytest.fixture
    def auth_service(
        self,
        mock_user_repo,
        mock_session_service,
        mock_token_service,
        mock_audit_service,
        mock_mfa_service
    ):
        """AuthService avec mocks"""
        from app.services.auth import AuthService
        return AuthService(
            user_repository=mock_user_repo,
            session_service=mock_session_service,
            token_service=mock_token_service,
            audit_service=mock_audit_service,
            mfa_service=mock_mfa_service
        )

    @pytest.mark.unit
    def test_refresh_tokens_calls_store_once(
        self,
        auth_service,
        mock_token_service,
        mock_user_repo,
        mock_session_service
    ):
        """refresh_tokens() ne doit appeler store_refresh_token qu'une seule fois"""
        # Setup
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        mock_old_token = MagicMock()
        mock_old_token.session_id = uuid4()
        mock_old_token.used_at = None
        mock_old_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_token_service.refresh_token_repository.get_by_jti.return_value = mock_old_token
        mock_token_service.validate_refresh_token.return_value = True
        mock_token_service.verify_refresh_token.return_value = True
        mock_token_service.is_token_revoked.return_value = False
        mock_token_service.detect_token_replay.return_value = False

        # Mock session active
        mock_session = MagicMock()
        mock_session.is_active = True
        mock_session_service.get_session_by_id.return_value = mock_session

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "tenant_id": 1,
                "type": "refresh",
                "jti": "old-jti"
            }
            with patch("app.services.auth.get_token_payload") as mock_get_payload:
                mock_get_payload.return_value = {
                    "jti": "new-jti",
                    "exp": int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
                }
                with patch("app.services.auth.create_access_token", return_value="new_access"):
                    with patch("app.services.auth.create_refresh_token", return_value="new_refresh"):
                        auth_service.refresh_tokens(
                            refresh_token="old_refresh_token",
                            ip_address="10.10.0.2"
                        )

        # Assert - store_refresh_token appele UNE SEULE FOIS
        store_calls = mock_token_service.store_refresh_token.call_count
        assert store_calls == 1, \
            f"store_refresh_token appele {store_calls} fois, attendu 1"

    @pytest.mark.unit
    def test_refresh_tokens_does_not_call_rotate_and_store(
        self,
        auth_service,
        mock_token_service,
        mock_user_repo
    ):
        """refresh_tokens() ne doit PAS appeler rotate ET store separement"""
        # Setup similaire
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        mock_old_token = MagicMock()
        mock_old_token.session_id = uuid4()
        mock_old_token.used_at = None
        mock_old_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_token_service.refresh_token_repository.get_by_jti.return_value = mock_old_token
        mock_token_service.validate_refresh_token.return_value = True
        mock_token_service.verify_refresh_token.return_value = True

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "tenant_id": 1,
                "type": "refresh",
                "jti": "old-jti"
            }
            with patch("app.services.auth.create_access_token", return_value="new_access"):
                with patch("app.services.auth.create_refresh_token", return_value="new_refresh"):
                    auth_service.refresh_tokens(
                        refresh_token="old_refresh_token",
                        ip_address="10.10.0.2"
                    )

        # Soit rotate, soit store, mais pas les deux
        rotate_calls = mock_token_service.rotate_refresh_token.call_count
        store_calls = mock_token_service.store_refresh_token.call_count

        # On attend: rotate=0 et store=1, OU rotate=1 et store=0
        total_storage_ops = rotate_calls + store_calls
        assert total_storage_ops <= 1, \
            f"Double stockage detecte: rotate={rotate_calls}, store={store_calls}"


class TestRefreshTokenSessionValidation:
    """Tests Issue #5: Session non verifiee au refresh"""

    @pytest.fixture
    def mock_session_service(self):
        """Mock SessionService"""
        from app.services.session import SessionService
        return MagicMock(spec=SessionService)

    @pytest.fixture
    def mock_token_service(self):
        """Mock TokenService"""
        from app.services.token import TokenService
        mock = MagicMock(spec=TokenService)
        mock.refresh_token_repository = MagicMock()
        return mock

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def mock_audit_service(self):
        """Mock AuditService"""
        from app.services.audit import AuditService
        return MagicMock(spec=AuditService)

    @pytest.fixture
    def mock_mfa_service(self):
        """Mock MFAService"""
        from app.services.mfa import MFAService
        service = MagicMock(spec=MFAService)
        service.is_mfa_enabled.return_value = False
        return service

    @pytest.fixture
    def auth_service(
        self,
        mock_user_repo,
        mock_session_service,
        mock_token_service,
        mock_audit_service,
        mock_mfa_service
    ):
        """AuthService avec mocks"""
        from app.services.auth import AuthService
        return AuthService(
            user_repository=mock_user_repo,
            session_service=mock_session_service,
            token_service=mock_token_service,
            audit_service=mock_audit_service,
            mfa_service=mock_mfa_service
        )

    @pytest.mark.unit
    def test_refresh_checks_session_is_active(
        self,
        auth_service,
        mock_session_service,
        mock_token_service,
        mock_user_repo
    ):
        """refresh_tokens() doit verifier que la session est active"""
        # Setup
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        session_id = uuid4()
        mock_old_token = MagicMock()
        mock_old_token.session_id = session_id
        mock_old_token.used_at = None
        mock_old_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_token_service.refresh_token_repository.get_by_jti.return_value = mock_old_token
        mock_token_service.validate_refresh_token.return_value = True
        mock_token_service.verify_refresh_token.return_value = True
        mock_token_service.is_token_revoked.return_value = False
        mock_token_service.detect_token_replay.return_value = False

        # Mock active session
        mock_session = MagicMock()
        mock_session.is_active = True
        mock_session_service.get_session_by_id.return_value = mock_session

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "tenant_id": 1,
                "type": "refresh",
                "jti": "old-jti"
            }
            with patch("app.services.auth.create_access_token", return_value="new_access"):
                with patch("app.services.auth.create_refresh_token", return_value="new_refresh"):
                    auth_service.refresh_tokens(
                        refresh_token="old_refresh_token",
                        ip_address="10.10.0.2"
                    )

        # Assert - session_service.is_session_valid ou get_session_by_id appele
        # avec le session_id du token
        session_check_called = (
            mock_session_service.is_session_valid.called or
            mock_session_service.get_session_by_id.called
        )
        assert session_check_called, \
            "refresh_tokens doit verifier la validite de la session"

    @pytest.mark.unit
    def test_refresh_fails_if_session_revoked(
        self,
        auth_service,
        mock_session_service,
        mock_token_service,
        mock_user_repo
    ):
        """refresh_tokens() echoue si la session est revoquee"""
        # Setup
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        session_id = uuid4()
        mock_old_token = MagicMock()
        mock_old_token.session_id = session_id
        mock_old_token.used_at = None
        mock_old_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_token_service.refresh_token_repository.get_by_jti.return_value = mock_old_token
        mock_token_service.validate_refresh_token.return_value = True
        mock_token_service.verify_refresh_token.return_value = True

        # Session revoquee
        mock_revoked_session = MagicMock()
        mock_revoked_session.is_active = False
        mock_revoked_session.revoked_at = datetime.now(timezone.utc)
        mock_session_service.get_session_by_id.return_value = mock_revoked_session
        mock_session_service.is_session_valid.return_value = False

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "tenant_id": 1,
                "type": "refresh",
                "jti": "old-jti"
            }

            result = auth_service.refresh_tokens(
                refresh_token="old_refresh_token",
                ip_address="10.10.0.2"
            )

        # Assert - doit retourner None ou lever exception
        assert result is None, \
            "refresh_tokens doit echouer si la session est revoquee"


class TestTokenServiceCompleteness:
    """Tests Issue #12: get_user_tokens() code mort"""

    @pytest.fixture
    def mock_refresh_token_repo(self):
        """Mock RefreshTokenRepository"""
        from app.repositories.refresh_token import RefreshTokenRepository
        repo = MagicMock(spec=RefreshTokenRepository)

        # Mock tokens
        mock_tokens = [
            MagicMock(jti="token-1", user_id=1, expires_at=datetime.now(timezone.utc) + timedelta(days=1)),
            MagicMock(jti="token-2", user_id=1, expires_at=datetime.now(timezone.utc) + timedelta(days=2)),
        ]
        repo.get_by_user_id.return_value = mock_tokens
        return repo

    @pytest.fixture
    def mock_revoked_token_repo(self):
        """Mock RevokedTokenRepository"""
        from app.repositories.revoked_token import RevokedTokenRepository
        return MagicMock(spec=RevokedTokenRepository)

    @pytest.fixture
    def token_service(self, mock_refresh_token_repo, mock_revoked_token_repo):
        """TokenService"""
        from app.services.token import TokenService
        return TokenService(
            refresh_token_repository=mock_refresh_token_repo,
            revoked_token_repository=mock_revoked_token_repo
        )

    @pytest.mark.unit
    def test_get_user_tokens_returns_list(self, token_service):
        """get_user_tokens() doit retourner une liste de tokens"""
        result = token_service.get_user_tokens(user_id=1)

        assert isinstance(result, list), \
            "get_user_tokens doit retourner une liste"
        assert len(result) > 0, \
            "get_user_tokens ne doit pas retourner une liste vide si des tokens existent"

    @pytest.mark.unit
    def test_get_user_tokens_calls_repository(
        self,
        token_service,
        mock_refresh_token_repo
    ):
        """get_user_tokens() doit appeler le repository"""
        token_service.get_user_tokens(user_id=1)

        # Doit appeler une methode du repository pour recuperer les tokens
        assert mock_refresh_token_repo.get_by_user_id.called or \
               mock_refresh_token_repo.get_active_for_user.called, \
            "get_user_tokens doit appeler le repository"

    @pytest.mark.unit
    def test_get_user_tokens_filters_by_tenant(
        self,
        token_service,
        mock_refresh_token_repo
    ):
        """get_user_tokens() avec tenant_id filtre par tenant"""
        token_service.get_user_tokens(user_id=1, tenant_id=2)

        # Verifier que tenant_id est passe au repository
        call_args = mock_refresh_token_repo.get_by_user_id.call_args
        if call_args:
            # Verifier que tenant_id est dans les arguments
            args, kwargs = call_args
            assert 2 in args or kwargs.get("tenant_id") == 2, \
                "get_user_tokens doit filtrer par tenant_id"
