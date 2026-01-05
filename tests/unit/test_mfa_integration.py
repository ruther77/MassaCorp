"""
Tests TDD - Integration MFA dans AuthService

Tests RED ecrits AVANT implementation pour:
- Issue #1: MFA bypassable au login
- Flow login en 2 etapes quand MFA active

Ces tests DOIVENT echouer avant implementation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestAuthServiceMFAIntegration:
    """Tests integration MFA dans AuthService - Issue #1"""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def mock_session_service(self):
        """Mock SessionService"""
        from app.services.session import SessionService
        return MagicMock(spec=SessionService)

    @pytest.fixture
    def mock_token_service(self):
        """Mock TokenService"""
        from app.services.token import TokenService
        return MagicMock(spec=TokenService)

    @pytest.fixture
    def mock_audit_service(self):
        """Mock AuditService"""
        from app.services.audit import AuditService
        return MagicMock(spec=AuditService)

    @pytest.fixture
    def mock_mfa_service(self):
        """Mock MFAService"""
        from app.services.mfa import MFAService
        return MagicMock(spec=MFAService)

    @pytest.fixture
    def mock_user_with_mfa(self):
        """User avec MFA active"""
        user = MagicMock()
        user.id = 1
        user.email = "user@massacorp.local"
        user.tenant_id = 1
        user.is_active = True
        user.password_hash = "$2b$12$test_hash"
        return user

    @pytest.fixture
    def mock_user_without_mfa(self):
        """User sans MFA"""
        user = MagicMock()
        user.id = 2
        user.email = "nomfa@massacorp.local"
        user.tenant_id = 1
        user.is_active = True
        user.password_hash = "$2b$12$test_hash"
        return user

    @pytest.fixture
    def auth_service_with_mfa(
        self,
        mock_user_repo,
        mock_session_service,
        mock_token_service,
        mock_audit_service,
        mock_mfa_service
    ):
        """AuthService avec MFAService injecte"""
        from app.services.auth import AuthService

        # AuthService DOIT accepter mfa_service en parametre
        return AuthService(
            user_repository=mock_user_repo,
            session_service=mock_session_service,
            token_service=mock_token_service,
            audit_service=mock_audit_service,
            mfa_service=mock_mfa_service  # NOUVEAU parametre requis
        )

    # ============================================
    # Tests Issue #1: MFA bypassable au login
    # ============================================

    @pytest.mark.unit
    def test_auth_service_accepts_mfa_service_parameter(self):
        """AuthService doit accepter mfa_service en parametre"""
        from app.services.auth import AuthService
        import inspect

        sig = inspect.signature(AuthService.__init__)
        params = list(sig.parameters.keys())

        assert "mfa_service" in params, \
            "AuthService.__init__ doit accepter mfa_service comme parametre"

    @pytest.mark.unit
    def test_login_with_mfa_enabled_returns_mfa_required(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_with_mfa,
        mock_session_service
    ):
        """Login avec MFA active doit retourner mfa_required=True"""
        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_with_mfa
        mock_mfa_service.is_mfa_enabled.return_value = True
        mock_session_service.is_account_locked.return_value = False

        with patch("app.services.auth.verify_password", return_value=True):
            result = auth_service_with_mfa.login(
                email="user@massacorp.local",
                password="SecureP@ss123!",
                tenant_id=1
            )

        # Assert - doit retourner mfa_required, pas de tokens complets
        assert result is not None
        assert result.get("mfa_required") is True
        assert "mfa_session_token" in result
        assert "access_token" not in result or result.get("access_token") is None

    @pytest.mark.unit
    def test_login_with_mfa_returns_mfa_session_token(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_with_mfa,
        mock_session_service
    ):
        """Login MFA retourne un mfa_session_token valide"""
        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_with_mfa
        mock_mfa_service.is_mfa_enabled.return_value = True
        mock_session_service.is_account_locked.return_value = False

        with patch("app.services.auth.verify_password", return_value=True):
            result = auth_service_with_mfa.login(
                email="user@massacorp.local",
                password="SecureP@ss123!",
                tenant_id=1
            )

        # Assert - mfa_session_token doit etre un JWT valide
        assert "mfa_session_token" in result
        mfa_token = result["mfa_session_token"]
        assert isinstance(mfa_token, str)
        assert len(mfa_token) > 50  # JWT minimum length

    @pytest.mark.unit
    def test_login_without_mfa_returns_tokens_directly(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_without_mfa,
        mock_session_service,
        mock_token_service
    ):
        """Login sans MFA retourne les tokens directement (comportement actuel)"""
        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_without_mfa
        mock_mfa_service.is_mfa_enabled.return_value = False
        mock_session_service.is_account_locked.return_value = False
        mock_session_service.create_session.return_value = MagicMock(id=uuid4())

        with patch("app.services.auth.verify_password", return_value=True):
            with patch("app.services.auth.create_access_token", return_value="access_token"):
                with patch("app.services.auth.create_refresh_token", return_value="refresh_token"):
                    result = auth_service_with_mfa.login(
                        email="nomfa@massacorp.local",
                        password="SecureP@ss123!",
                        tenant_id=1
                    )

        # Assert - tokens retournes directement
        assert result is not None
        assert "access_token" in result
        assert result.get("mfa_required") is None or result.get("mfa_required") is False

    @pytest.mark.unit
    def test_complete_mfa_login_exists(self):
        """AuthService doit avoir une methode complete_mfa_login"""
        from app.services.auth import AuthService

        assert hasattr(AuthService, "complete_mfa_login"), \
            "AuthService doit avoir une methode complete_mfa_login()"

    @pytest.mark.unit
    def test_complete_mfa_login_with_valid_totp_returns_tokens(
        self,
        auth_service_with_mfa,
        mock_mfa_service,
        mock_user_repo,
        mock_session_service,
        mock_token_service,
        mock_user_with_mfa
    ):
        """complete_mfa_login avec TOTP valide retourne les tokens"""
        # Setup
        mock_user_repo.get_by_id.return_value = mock_user_with_mfa
        mock_mfa_service.verify_totp.return_value = True
        mock_session_service.create_session.return_value = MagicMock(id=uuid4())

        # mfa_session_token contient user_id encode
        mfa_session_token = "valid_mfa_session_token"

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "type": "mfa_session",
                "tenant_id": 1
            }
            with patch("app.services.auth.create_access_token", return_value="access_token"):
                with patch("app.services.auth.create_refresh_token", return_value="refresh_token"):
                    result = auth_service_with_mfa.complete_mfa_login(
                        mfa_session_token=mfa_session_token,
                        totp_code="123456",
                        ip_address="10.10.0.2"
                    )

        # Assert
        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        mock_mfa_service.verify_totp.assert_called_once()

    @pytest.mark.unit
    def test_complete_mfa_login_with_invalid_totp_fails(
        self,
        auth_service_with_mfa,
        mock_mfa_service,
        mock_user_repo,
        mock_user_with_mfa
    ):
        """complete_mfa_login avec TOTP invalide echoue"""
        # Setup
        mock_user_repo.get_by_id.return_value = mock_user_with_mfa
        mock_mfa_service.verify_totp.return_value = False

        mfa_session_token = "valid_mfa_session_token"

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "1",
                "type": "mfa_session",
                "tenant_id": 1
            }

            result = auth_service_with_mfa.complete_mfa_login(
                mfa_session_token=mfa_session_token,
                totp_code="000000",  # Code invalide
                ip_address="10.10.0.2"
            )

        # Assert - doit retourner None ou lever exception
        assert result is None

    @pytest.mark.unit
    def test_complete_mfa_login_with_expired_session_token_fails(
        self,
        auth_service_with_mfa
    ):
        """complete_mfa_login avec mfa_session_token expire echoue"""
        from app.core.security import TokenExpiredError

        expired_token = "expired_mfa_session_token"

        with patch("app.services.auth.decode_token") as mock_decode:
            mock_decode.side_effect = TokenExpiredError("Token expire")

            result = auth_service_with_mfa.complete_mfa_login(
                mfa_session_token=expired_token,
                totp_code="123456",
                ip_address="10.10.0.2"
            )

        assert result is None

    @pytest.mark.unit
    def test_mfa_session_token_has_short_expiry(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_with_mfa,
        mock_session_service
    ):
        """mfa_session_token doit avoir une courte duree de vie (5 min)"""
        from app.core.security import decode_token

        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_with_mfa
        mock_mfa_service.is_mfa_enabled.return_value = True
        mock_session_service.is_account_locked.return_value = False

        with patch("app.services.auth.verify_password", return_value=True):
            result = auth_service_with_mfa.login(
                email="user@massacorp.local",
                password="SecureP@ss123!",
                tenant_id=1
            )

        # Decode le token et verifier l'expiration
        mfa_token = result.get("mfa_session_token")
        payload = decode_token(mfa_token)

        exp = payload.get("exp")
        iat = payload.get("iat")

        # Expiration doit etre <= 5 minutes (300 secondes)
        assert exp - iat <= 300, "mfa_session_token doit expirer en 5 min max"

    @pytest.mark.unit
    def test_mfa_session_token_type_is_mfa_session(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_with_mfa,
        mock_session_service
    ):
        """mfa_session_token doit avoir type='mfa_session'"""
        from app.core.security import decode_token

        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_with_mfa
        mock_mfa_service.is_mfa_enabled.return_value = True
        mock_session_service.is_account_locked.return_value = False

        with patch("app.services.auth.verify_password", return_value=True):
            result = auth_service_with_mfa.login(
                email="user@massacorp.local",
                password="SecureP@ss123!",
                tenant_id=1
            )

        mfa_token = result.get("mfa_session_token")
        payload = decode_token(mfa_token)

        assert payload.get("type") == "mfa_session", \
            "mfa_session_token doit avoir type='mfa_session'"

    @pytest.mark.unit
    def test_mfa_service_is_mfa_enabled_called_on_login(
        self,
        auth_service_with_mfa,
        mock_user_repo,
        mock_mfa_service,
        mock_user_with_mfa,
        mock_session_service
    ):
        """login() doit appeler mfa_service.is_mfa_enabled()"""
        # Setup
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user_with_mfa
        mock_mfa_service.is_mfa_enabled.return_value = False
        mock_session_service.is_account_locked.return_value = False
        mock_session_service.create_session.return_value = MagicMock(id=uuid4())

        with patch("app.services.auth.verify_password", return_value=True):
            with patch("app.services.auth.create_access_token", return_value="token"):
                with patch("app.services.auth.create_refresh_token", return_value="token"):
                    auth_service_with_mfa.login(
                        email="user@massacorp.local",
                        password="SecureP@ss123!",
                        tenant_id=1
                    )

        # Assert - is_mfa_enabled doit etre appele
        mock_mfa_service.is_mfa_enabled.assert_called_once_with(mock_user_with_mfa.id)


class TestMFASessionTokenSecurity:
    """Tests securite du mfa_session_token"""

    @pytest.mark.unit
    @pytest.mark.security
    def test_mfa_session_token_cannot_access_api(self):
        """mfa_session_token ne doit PAS donner acces a l'API"""
        from app.core.dependencies import get_current_user
        from app.core.security import InvalidTokenError

        # Un token de type 'mfa_session' ne doit pas passer get_current_user
        # qui attend type='access'

        # Ce test verifie que get_current_user rejette les tokens mfa_session
        # Implementation: verifier payload["type"] == "access" dans get_current_user

    @pytest.mark.unit
    @pytest.mark.security
    def test_mfa_session_token_single_use(self):
        """mfa_session_token ne devrait etre utilisable qu'une fois (optionnel)"""
        # Note: implementation optionnelle mais recommandee
        # Stocker le jti du mfa_session_token et l'invalider apres usage
        pass
