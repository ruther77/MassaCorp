"""
Tests TDD pour les corrections CRITIQUES de securite.

Ces tests verifient les fixes des 5 problemes critiques identifies:
1. Secrets hardcodes en configuration
2. Conversion int() non securisee sur payload.get("sub")
3. Acces payload sans validation prealable
4. IDOR cross-tenant dans get_current_user
5. Session courante non identifiable par JTI
"""
import pytest
import re
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from uuid import uuid4


# =============================================================================
# 1 - Validation secrets non-hardcodes
# =============================================================================
class TestSecretsValidation:
    """Les secrets ne doivent pas avoir les valeurs par defaut en production"""

    @pytest.mark.unit
    def test_settings_has_validate_secrets_method(self):
        """Settings doit avoir une methode de validation des secrets"""
        from app.core.config import Settings

        settings = Settings()

        # La methode doit exister
        assert hasattr(settings, 'validate_secrets')
        assert callable(getattr(settings, 'validate_secrets'))

    @pytest.mark.unit
    def test_validate_secrets_raises_on_default_jwt_secret(self):
        """validate_secrets doit lever une erreur si JWT_SECRET est la valeur par defaut"""
        from app.core.config import Settings

        settings = Settings()
        settings.ENV = "production"
        settings.JWT_SECRET = "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES"

        with pytest.raises(ValueError) as exc_info:
            settings.validate_secrets()

        assert "JWT_SECRET" in str(exc_info.value)

    @pytest.mark.unit
    def test_validate_secrets_raises_on_default_encryption_key(self):
        """validate_secrets doit lever une erreur si ENCRYPTION_KEY est la valeur par defaut"""
        from app.core.config import Settings

        settings = Settings()
        settings.ENV = "production"
        settings.JWT_SECRET = "a_valid_secret_key_32_characters_long!"
        settings.ENCRYPTION_KEY = "CHANGER_CLE_CHIFFREMENT_32_OCTETS"

        with pytest.raises(ValueError) as exc_info:
            settings.validate_secrets()

        assert "ENCRYPTION_KEY" in str(exc_info.value)

    @pytest.mark.unit
    def test_validate_secrets_passes_in_dev_mode(self):
        """validate_secrets ne doit pas lever d'erreur en mode dev"""
        from app.core.config import Settings

        settings = Settings()
        settings.ENV = "dev"
        settings.JWT_SECRET = "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES"

        # Ne devrait pas lever d'exception en mode dev
        settings.validate_secrets()  # Pas d'exception = OK

    @pytest.mark.unit
    def test_validate_secrets_passes_with_valid_secrets(self):
        """validate_secrets passe si les secrets sont valides"""
        from app.core.config import Settings

        settings = Settings()
        settings.ENV = "production"
        settings.JWT_SECRET = "my_super_secure_production_jwt_key!"  # 36 chars
        settings.ENCRYPTION_KEY = "my_super_secure_encryption_32chars"  # 34 chars

        # Ne devrait pas lever d'exception
        settings.validate_secrets()


# =============================================================================
# 2 - Securiser int(payload.get('sub'))
# =============================================================================
class TestPayloadSubConversion:
    """La conversion de payload['sub'] doit etre securisee"""

    @pytest.mark.unit
    def test_get_current_user_handles_none_sub(self):
        """get_current_user doit gerer sub=None proprement"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        # Simuler un payload avec sub=None
        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": None}

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            assert exc_info.value.status_code == 401

    @pytest.mark.unit
    def test_get_current_user_handles_missing_sub(self):
        """get_current_user doit gerer l'absence de sub proprement"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        # Simuler un payload sans sub
        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access"}  # Pas de "sub"

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            assert exc_info.value.status_code == 401

    @pytest.mark.unit
    def test_get_current_user_handles_invalid_sub_format(self):
        """get_current_user doit gerer un sub non-numerique"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        # Simuler un payload avec sub invalide
        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": "not_a_number"}

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            assert exc_info.value.status_code == 401

    @pytest.mark.unit
    def test_auth_service_refresh_handles_none_sub(self):
        """AuthService.refresh_tokens doit gerer sub=None"""
        from app.services.auth import AuthService

        mock_user_repo = MagicMock()
        service = AuthService(user_repository=mock_user_repo)

        # Simuler un token avec sub=None
        with patch('app.services.auth.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "refresh", "sub": None, "jti": "test"}

            result = service.refresh_tokens("fake_token")

            # Doit retourner None, pas crasher
            assert result is None


# =============================================================================
# 3 - Valider payload avant acces
# =============================================================================
class TestPayloadValidation:
    """Le payload doit etre valide avant d'acceder a ses champs"""

    @pytest.mark.unit
    def test_auth_service_complete_mfa_handles_none_payload(self):
        """complete_mfa_login doit gerer un payload None"""
        from app.services.auth import AuthService

        mock_user_repo = MagicMock()
        mock_mfa_service = MagicMock()
        service = AuthService(
            user_repository=mock_user_repo,
            mfa_service=mock_mfa_service
        )

        # Simuler un token qui decode en None
        with patch('app.services.auth.decode_token') as mock_decode:
            mock_decode.return_value = None

            result = service.complete_mfa_login(
                mfa_session_token="invalid_token",
                totp_code="123456"
            )

            assert result is None

    @pytest.mark.unit
    def test_auth_service_validates_payload_type_before_access(self):
        """complete_mfa_login doit valider le type avant d'acceder aux autres champs"""
        from app.services.auth import AuthService

        mock_user_repo = MagicMock()
        service = AuthService(user_repository=mock_user_repo)

        # Payload valide mais type incorrect
        with patch('app.services.auth.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": "1"}  # Mauvais type

            result = service.complete_mfa_login(
                mfa_session_token="fake_token",
                totp_code="123456"
            )

            # Doit retourner None car type != mfa_session
            assert result is None


# =============================================================================
# 4 - Validation cross-tenant IDOR
# =============================================================================
class TestCrossTenantValidation:
    """L'utilisateur du token doit appartenir au bon tenant"""

    @pytest.mark.unit
    def test_get_current_user_validates_tenant_match(self):
        """get_current_user doit verifier que token.tenant_id == user.tenant_id"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        # User appartient au tenant 1
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        # Token revendique tenant 2 (different!)
        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "1",
                "tenant_id": 2  # Mismatch!
            }

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            # Doit etre rejete avec message generique (securite)
            # On ne revele pas que c'est un mismatch de tenant
            assert exc_info.value.status_code == 401
            assert exc_info.value.detail == "Token invalide"

    @pytest.mark.unit
    def test_get_current_user_passes_when_tenant_matches(self):
        """get_current_user passe si token.tenant_id == user.tenant_id"""
        from app.core.dependencies import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "1",
                "tenant_id": 1  # Match!
            }

            result = get_current_user(mock_credentials, mock_user_repo)

            assert result == mock_user

    @pytest.mark.unit
    def test_optional_current_user_validates_tenant(self):
        """get_optional_current_user doit aussi valider le tenant"""
        from app.core.dependencies import get_optional_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "1",
                "tenant_id": 2  # Mismatch!
            }

            result = get_optional_current_user(mock_credentials, mock_user_repo)

            # Doit retourner None (pas d'exception car optionnel)
            assert result is None


# =============================================================================
# 5 - Identifier session courante par JTI
# =============================================================================
class TestSessionCurrentIdentification:
    """La session courante doit etre identifiable via le JTI du token"""

    @pytest.mark.unit
    def test_sessions_endpoint_has_current_session_id_dependency(self):
        """L'endpoint sessions doit avoir acces au session_id courant"""
        from app.api.v1.endpoints import sessions
        import inspect

        # Verifier que la fonction list_sessions accepte current_session_id
        list_sessions_func = sessions.list_sessions
        sig = inspect.signature(list_sessions_func)
        params = list(sig.parameters.keys())

        # current_session_id ou session_id doit etre un parametre
        has_session_param = any(
            'session' in p.lower() and 'service' not in p.lower()
            for p in params
        )
        assert has_session_param, \
            f"list_sessions devrait avoir un parametre session_id. Params: {params}"

    @pytest.mark.unit
    def test_get_current_session_id_dependency_exists(self):
        """Une dependance get_current_session_id doit exister"""
        from app.core import dependencies

        assert hasattr(dependencies, 'get_current_session_id')
        assert callable(getattr(dependencies, 'get_current_session_id'))

    @pytest.mark.unit
    def test_get_current_session_id_extracts_from_token(self):
        """get_current_session_id doit extraire le session_id du refresh token lie"""
        from app.core.dependencies import get_current_session_id
        from fastapi.security import HTTPAuthorizationCredentials
        from uuid import UUID

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_token_service = MagicMock()
        session_uuid = uuid4()

        # Simuler un token avec session_id
        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {
                "type": "access",
                "sub": "1",
                "session_id": str(session_uuid)
            }

            result = get_current_session_id(mock_credentials)

            assert result == session_uuid

    @pytest.mark.unit
    def test_session_list_marks_current_correctly(self):
        """La liste des sessions doit marquer is_current=True pour la courante"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        service = SessionService(session_repository=mock_session_repo)

        current_session_id = uuid4()
        other_session_id = uuid4()

        mock_sessions = [
            MagicMock(id=current_session_id, is_active=True, tenant_id=1),
            MagicMock(id=other_session_id, is_active=True, tenant_id=1)
        ]
        mock_session_repo.get_active_sessions.return_value = mock_sessions

        result = service.get_user_sessions_with_current(
            user_id=1,
            current_session_id=current_session_id
        )

        current = next(s for s in result if s["id"] == current_session_id)
        other = next(s for s in result if s["id"] == other_session_id)

        assert current["is_current"] is True
        assert other["is_current"] is False


# =============================================================================
# Tests supplementaires de securite
# =============================================================================
class TestSecurityEdgeCases:
    """Tests des cas limites de securite"""

    @pytest.mark.unit
    def test_payload_sub_as_string_zero(self):
        """sub='0' doit etre rejete (user_id 0 invalide)"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = None  # Pas d'user avec id=0

        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": "0"}

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            assert exc_info.value.status_code == 401

    @pytest.mark.unit
    def test_payload_sub_negative(self):
        """sub negatif doit etre rejete"""
        from app.core.dependencies import get_current_user
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "fake_token"

        mock_user_repo = MagicMock()

        with patch('app.core.dependencies.decode_token') as mock_decode:
            mock_decode.return_value = {"type": "access", "sub": "-1"}

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(mock_credentials, mock_user_repo)

            assert exc_info.value.status_code == 401
