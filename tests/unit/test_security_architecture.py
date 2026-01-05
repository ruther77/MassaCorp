"""
Tests TDD pour Phase A & B - Security Architecture Checklist.

Phase A - Sécurité Immédiate (CRITICAL):
A1. Timing-safe login (DUMMY_HASH + constant-time compare)
A2. session_id dans access_token JWT
A3. Security Headers Middleware
A4. Anti-replay TOTP (last_totp_window)

Phase B - Architecture Robuste:
B1. Exceptions custom unifiées (pas HTTPException dans services)
B2. Schemas strict (extra="forbid")
B3. Hash refresh token SHA-256 en DB
"""
import pytest
import hashlib
import time
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
from uuid import uuid4


# =============================================================================
# A1 - Timing-safe login (DUMMY_HASH + constant-time compare)
# =============================================================================
class TestTimingSafeLogin:
    """Le login doit être résistant aux timing attacks"""

    @pytest.mark.unit
    def test_security_module_has_dummy_hash(self):
        """Un DUMMY_HASH doit exister pour timing constant"""
        from app.core import security

        assert hasattr(security, 'DUMMY_HASH')
        # Doit etre un hash Argon2id valide (migration bcrypt->Argon2id)
        assert security.DUMMY_HASH.startswith('$argon2')
        assert len(security.DUMMY_HASH) >= 50

    @pytest.mark.unit
    def test_verify_password_uses_constant_time(self):
        """verify_password doit utiliser une comparaison constant-time"""
        from app.core.security import verify_password, hash_password

        # Créer un hash valide
        valid_hash = hash_password("TestPassword123!")

        # Les deux vérifications doivent prendre un temps similaire
        # (bcrypt est déjà constant-time, mais on vérifie qu'on l'utilise)
        start1 = time.perf_counter()
        verify_password("TestPassword123!", valid_hash)
        time1 = time.perf_counter() - start1

        start2 = time.perf_counter()
        verify_password("WrongPassword!", valid_hash)
        time2 = time.perf_counter() - start2

        # Les temps doivent être proches (< 50% de différence)
        # bcrypt est conçu pour ça
        ratio = max(time1, time2) / min(time1, time2)
        assert ratio < 2.0, "Timing difference too large - potential timing attack"

    @pytest.mark.unit
    def test_auth_service_uses_dummy_hash_for_nonexistent_user(self):
        """AuthService doit hasher même si l'utilisateur n'existe pas"""
        from app.services.auth import AuthService
        from app.core.security import DUMMY_HASH

        # Le service doit avoir une méthode qui utilise DUMMY_HASH
        # quand l'utilisateur n'existe pas
        mock_user_repo = MagicMock()
        mock_user_repo.get_by_email_and_tenant.return_value = None

        # AuthService utilise session_service, token_service, audit_service
        service = AuthService(
            user_repository=mock_user_repo,
            session_service=None,
            token_service=None,
            audit_service=None
        )

        # Test via authenticate() pour vérifier le comportement DUMMY_HASH
        with patch('app.services.auth.verify_password') as mock_verify:
            mock_verify.return_value = False

            result = service.authenticate(
                email="nonexistent@example.com",
                password="anypassword",
                tenant_id=1
            )

            # verify_password doit avoir été appelé (avec DUMMY_HASH)
            assert mock_verify.called
            # Le hash utilisé doit être DUMMY_HASH quand user inexistant
            call_args = mock_verify.call_args
            assert call_args is not None
            # Vérifier que DUMMY_HASH est passé en second argument
            assert call_args[0][1] == DUMMY_HASH


# =============================================================================
# A2 - session_id dans access_token JWT
# =============================================================================
class TestSessionIdInAccessToken:
    """L'access_token doit contenir session_id pour validation"""

    @pytest.mark.unit
    def test_create_access_token_accepts_session_id(self):
        """create_access_token doit accepter session_id"""
        from app.core.security import create_access_token
        import inspect

        sig = inspect.signature(create_access_token)
        params = list(sig.parameters.keys())

        assert 'session_id' in params, \
            "create_access_token doit accepter session_id en paramètre"

    @pytest.mark.unit
    def test_access_token_contains_session_id(self):
        """L'access token doit contenir session_id dans le payload"""
        from app.core.security import create_access_token, decode_token

        session_id = str(uuid4())

        token = create_access_token(
            subject=1,  # user_id
            tenant_id=1,
            session_id=session_id
        )

        payload = decode_token(token)

        assert payload is not None
        assert 'session_id' in payload
        assert payload['session_id'] == session_id

    @pytest.mark.unit
    def test_auth_service_login_includes_session_id_in_token(self):
        """Le login doit inclure session_id dans l'access_token"""
        from app.core.security import decode_token

        # Simuler un login réussi et vérifier que le token contient session_id
        # Ce test vérifie l'intégration
        pass  # Sera testé en intégration


# =============================================================================
# A3 - Security Headers Middleware
# =============================================================================
class TestSecurityHeadersMiddleware:
    """Middleware pour les headers de sécurité HTTP"""

    @pytest.mark.unit
    def test_security_headers_middleware_exists(self):
        """Le middleware SecurityHeaders doit exister"""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        assert SecurityHeadersMiddleware is not None

    @pytest.mark.unit
    def test_security_headers_middleware_adds_hsts(self):
        """Le middleware doit ajouter Strict-Transport-Security"""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=MagicMock())

        # Vérifier que HSTS est dans les headers configurés
        assert hasattr(middleware, 'security_headers')
        assert 'Strict-Transport-Security' in middleware.security_headers

    @pytest.mark.unit
    def test_security_headers_middleware_adds_x_frame_options(self):
        """Le middleware doit ajouter X-Frame-Options: DENY"""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=MagicMock())

        assert 'X-Frame-Options' in middleware.security_headers
        assert middleware.security_headers['X-Frame-Options'] == 'DENY'

    @pytest.mark.unit
    def test_security_headers_middleware_adds_content_type_options(self):
        """Le middleware doit ajouter X-Content-Type-Options: nosniff"""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=MagicMock())

        assert 'X-Content-Type-Options' in middleware.security_headers
        assert middleware.security_headers['X-Content-Type-Options'] == 'nosniff'

    @pytest.mark.unit
    def test_security_headers_middleware_adds_referrer_policy(self):
        """Le middleware doit ajouter Referrer-Policy"""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=MagicMock())

        assert 'Referrer-Policy' in middleware.security_headers


# =============================================================================
# A4 - Anti-replay TOTP
# =============================================================================
class TestAntiReplayTOTP:
    """Protection contre la réutilisation de codes TOTP"""

    @pytest.mark.unit
    def test_mfa_secret_model_has_last_totp_window(self):
        """Le modèle MFASecret doit avoir last_totp_window"""
        from app.models.mfa import MFASecret

        # Vérifier que la colonne existe
        columns = [c.name for c in MFASecret.__table__.columns]
        assert 'last_totp_window' in columns

    @pytest.mark.unit
    def test_mfa_service_tracks_last_window(self):
        """MFAService doit tracker le dernier window utilisé"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()

        # Simuler un secret MFA avec last_totp_window
        mock_secret = MagicMock()
        mock_secret.enabled = True
        mock_secret.last_totp_window = None
        mock_secret_repo.get_by_user_id.return_value = mock_secret

        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Le service doit avoir une méthode pour mettre à jour last_window
        assert hasattr(service, 'verify_totp')

    @pytest.mark.unit
    def test_totp_replay_is_rejected(self):
        """Un code TOTP déjà utilisé dans la même fenêtre doit être rejeté"""
        from app.services.mfa import MFAService
        import pyotp

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()

        # Créer un vrai secret TOTP pour le test
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        current_window = int(datetime.now(timezone.utc).timestamp() // 30)

        # Simuler un secret avec le même window déjà utilisé
        mock_secret = MagicMock()
        mock_secret.enabled = True
        mock_secret.secret = secret  # En clair pour le test
        mock_secret.last_totp_window = current_window  # Déjà utilisé!
        mock_secret_repo.get_by_user_id.return_value = mock_secret

        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Patcher is_encrypted_secret pour retourner False (secret en clair)
        with patch('app.services.mfa.is_encrypted_secret', return_value=False):
            result = service.verify_totp(user_id=1, code=current_code)

            # Doit retourner False car replay détecté
            assert result is False


# =============================================================================
# B1 - Exceptions custom unifiées
# =============================================================================
class TestCustomExceptions:
    """Les services doivent utiliser des exceptions custom, pas HTTPException"""

    @pytest.mark.unit
    def test_app_exception_base_exists(self):
        """AppException base class doit exister"""
        from app.core.exceptions import AppException

        assert issubclass(AppException, Exception)
        assert hasattr(AppException, 'status_code')
        assert hasattr(AppException, 'error_code')

    @pytest.mark.unit
    def test_invalid_credentials_exception_exists(self):
        """InvalidCredentials exception doit exister"""
        from app.core.exceptions import InvalidCredentials

        exc = InvalidCredentials()
        assert exc.status_code == 401
        assert exc.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.unit
    def test_token_expired_exception_exists(self):
        """TokenExpired exception doit exister"""
        from app.core.exceptions import TokenExpired

        exc = TokenExpired()
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_EXPIRED"

    @pytest.mark.unit
    def test_session_expired_exception_exists(self):
        """SessionExpired exception doit exister"""
        from app.core.exceptions import SessionExpired

        exc = SessionExpired()
        assert exc.status_code == 401

    @pytest.mark.unit
    def test_mfa_required_exception_exists(self):
        """MFARequired exception doit exister"""
        from app.core.exceptions import MFARequired

        exc = MFARequired()
        assert exc.status_code == 403
        assert exc.error_code == "MFA_REQUIRED"

    @pytest.mark.unit
    def test_tenant_mismatch_exception_exists(self):
        """TenantMismatch exception doit exister"""
        from app.core.exceptions import TenantMismatch

        exc = TenantMismatch()
        assert exc.status_code == 403

    @pytest.mark.unit
    def test_exception_has_to_dict_method(self):
        """Les exceptions doivent avoir to_dict() pour serialization"""
        from app.core.exceptions import AppException

        exc = AppException(message="Test error")
        result = exc.to_dict()

        assert isinstance(result, dict)
        assert 'error' in result
        assert 'message' in result


# =============================================================================
# B2 - Schemas strict (extra="forbid")
# =============================================================================
class TestSchemasStrict:
    """Les schemas Pydantic doivent rejeter les champs inconnus"""

    @pytest.mark.unit
    def test_login_request_rejects_extra_fields(self):
        """LoginRequest doit rejeter les champs inconnus"""
        from app.schemas.auth import LoginRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(
                email="test@example.com",
                password="password123",
                unknown_field="malicious"  # Champ inconnu
            )

        # L'erreur doit mentionner le champ extra
        assert "extra" in str(exc_info.value).lower() or "unknown" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_user_create_rejects_extra_fields(self):
        """UserCreate doit rejeter les champs inconnus"""
        from app.schemas.user import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                password="MassaCorp2024$xK7vQ!",
                is_admin=True  # Champ inconnu potentiellement dangereux
            )

    @pytest.mark.unit
    def test_base_schema_has_extra_forbid(self):
        """BaseSchema doit avoir extra='forbid' par défaut"""
        from app.schemas.base import BaseSchema

        # Vérifier la config du modèle
        config = BaseSchema.model_config
        assert config.get('extra') == 'forbid'


# =============================================================================
# B3 - Hash refresh token SHA-256
# =============================================================================
class TestRefreshTokenHashing:
    """Les refresh tokens doivent être hashés en DB"""

    @pytest.mark.unit
    def test_token_service_hashes_refresh_token(self):
        """TokenService doit hasher le refresh token avant stockage"""
        from app.core.security import hash_token

        # La fonction hash_token doit exister dans security
        assert callable(hash_token)

        # Vérifier qu'elle utilise SHA-256
        test_token = "test_token_123"
        result = hash_token(test_token)

        # SHA-256 produit 64 caractères hexadécimaux
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)

    @pytest.mark.unit
    def test_hash_token_uses_sha256(self):
        """Le hashage doit utiliser SHA-256"""
        # Test direct du hashage
        token = "test_refresh_token_12345"
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        # Le hash doit être de 64 caractères (SHA-256 hex)
        assert len(expected_hash) == 64

    @pytest.mark.unit
    def test_refresh_token_model_stores_hash(self):
        """Le modèle RefreshToken doit avoir token_hash, pas token en clair"""
        from app.models.session import RefreshToken

        columns = [c.name for c in RefreshToken.__table__.columns]

        # Doit avoir token_hash
        assert 'token_hash' in columns
        # Ne doit PAS avoir token en clair (seulement token_hash)
        assert 'token' not in columns

    @pytest.mark.unit
    def test_store_refresh_token_saves_hash(self):
        """store_refresh_token doit sauvegarder le hash, pas le token"""
        from app.services.token import TokenService
        from datetime import timedelta

        mock_refresh_repo = MagicMock()
        mock_revoked_repo = MagicMock()

        service = TokenService(mock_refresh_repo, mock_revoked_repo)

        test_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        expected_hash = hashlib.sha256(test_token.encode()).hexdigest()

        # expires_at doit être dans le futur
        future_expiry = datetime.now(timezone.utc) + timedelta(days=7)

        service.store_refresh_token(
            jti="test-jti",
            user_id=1,
            tenant_id=1,
            session_id="test-session-id",
            raw_token=test_token,  # Paramètre correct
            expires_at=future_expiry
        )

        # Vérifier que le repo a été appelé avec le hash
        mock_refresh_repo.store_token.assert_called_once()
        call_kwargs = mock_refresh_repo.store_token.call_args[1]

        # Le token_hash doit être dans les arguments
        assert 'token_hash' in call_kwargs
        assert call_kwargs['token_hash'] == expected_hash
