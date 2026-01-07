"""
Tests comportementaux pour la section 7.5 de l'audit.

Ces tests verifient:
1. GDPR Export/Delete avec MFA et API Keys
2. Validation E.164 pour telephone
3. Validation IP et limite user_agent
4. Redis pool configuration
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


# =============================================================================
# Tests GDPR - Export avec MFA et API Keys
# =============================================================================


class TestGDPRExportWithMFA:
    """Tests pour l'export GDPR incluant les donnees MFA."""

    def test_gdpr_service_accepts_mfa_repositories(self):
        """
        GDPRService doit accepter les repositories MFA dans son constructeur.
        """
        from app.services.gdpr import GDPRService

        mock_user_repo = MagicMock()
        mock_session_repo = MagicMock()
        mock_audit_repo = MagicMock()
        mock_mfa_secret_repo = MagicMock()
        mock_mfa_recovery_repo = MagicMock()
        mock_api_key_repo = MagicMock()

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=mock_api_key_repo
        )

        assert service.mfa_secret_repo == mock_mfa_secret_repo
        assert service.mfa_recovery_repo == mock_mfa_recovery_repo
        assert service.api_key_repo == mock_api_key_repo

    def test_export_user_data_includes_mfa_data(self):
        """
        export_user_data() doit inclure les donnees MFA dans l'export.
        """
        from app.services.gdpr import GDPRService

        # Setup mocks
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.is_active = True
        mock_user.tenant_id = 1

        mock_mfa_secret = MagicMock()
        mock_mfa_secret.enabled = True
        mock_mfa_secret.created_at = datetime.now(timezone.utc)
        mock_mfa_secret.last_used_at = datetime.now(timezone.utc)

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = mock_user

        mock_session_repo = MagicMock()
        mock_session_repo.get_all_sessions.return_value = []

        mock_audit_repo = MagicMock()
        mock_audit_repo.get_by_user.return_value = []

        mock_mfa_secret_repo = MagicMock()
        mock_mfa_secret_repo.get_by_user_id.return_value = mock_mfa_secret

        mock_mfa_recovery_repo = MagicMock()
        mock_mfa_recovery_repo.get_all_for_user.return_value = []

        mock_api_key_repo = MagicMock()
        mock_api_key_repo.get_by_tenant.return_value = []

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=mock_api_key_repo
        )

        result = service.export_user_data(1)

        assert "mfa_data" in result
        assert result["mfa_data"]["enabled"] is True
        assert "recovery_codes" in result
        assert "api_keys" in result

    def test_export_user_data_includes_recovery_codes(self):
        """
        export_user_data() doit inclure les codes de recuperation MFA.
        """
        from app.services.gdpr import GDPRService

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.is_active = True
        mock_user.tenant_id = 1

        mock_recovery_code = MagicMock()
        mock_recovery_code.id = 1
        mock_recovery_code.used_at = None
        mock_recovery_code.created_at = datetime.now(timezone.utc)

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = mock_user

        mock_session_repo = MagicMock()
        mock_session_repo.get_all_sessions.return_value = []

        mock_audit_repo = MagicMock()
        mock_audit_repo.get_by_user.return_value = []

        mock_mfa_secret_repo = MagicMock()
        mock_mfa_secret_repo.get_by_user_id.return_value = None

        mock_mfa_recovery_repo = MagicMock()
        mock_mfa_recovery_repo.get_all_for_user.return_value = [mock_recovery_code]

        mock_api_key_repo = MagicMock()
        mock_api_key_repo.get_by_tenant.return_value = []

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=mock_api_key_repo
        )

        result = service.export_user_data(1)

        assert len(result["recovery_codes"]) == 1
        assert result["recovery_codes"][0]["id"] == 1
        assert result["recovery_codes"][0]["is_used"] is False

    def test_export_user_data_includes_api_keys(self):
        """
        export_user_data() doit inclure les API keys creees par l'utilisateur.
        """
        from app.services.gdpr import GDPRService

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.created_at = datetime.now(timezone.utc)
        mock_user.is_active = True
        mock_user.tenant_id = 1

        mock_api_key = MagicMock()
        mock_api_key.id = 100
        mock_api_key.name = "Test API Key"
        mock_api_key.key_prefix = "mc_sk_..."
        mock_api_key.scopes = ["users:read"]
        mock_api_key.created_at = datetime.now(timezone.utc)
        mock_api_key.expires_at = None
        mock_api_key.revoked_at = None
        mock_api_key.last_used_at = None
        mock_api_key.is_valid = True
        mock_api_key.created_by_user_id = 1  # Created by this user

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = mock_user

        mock_session_repo = MagicMock()
        mock_session_repo.get_all_sessions.return_value = []

        mock_audit_repo = MagicMock()
        mock_audit_repo.get_by_user.return_value = []

        mock_mfa_secret_repo = MagicMock()
        mock_mfa_secret_repo.get_by_user_id.return_value = None

        mock_mfa_recovery_repo = MagicMock()
        mock_mfa_recovery_repo.get_all_for_user.return_value = []

        mock_api_key_repo = MagicMock()
        mock_api_key_repo.get_by_tenant.return_value = [mock_api_key]

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=mock_api_key_repo
        )

        result = service.export_user_data(1)

        assert len(result["api_keys"]) == 1
        assert result["api_keys"][0]["id"] == 100
        assert result["api_keys"][0]["name"] == "Test API Key"


class TestGDPRDeleteWithMFA:
    """Tests pour la suppression GDPR incluant les donnees MFA."""

    def test_delete_user_data_removes_mfa_secret(self):
        """
        delete_user_data() doit supprimer le secret MFA.
        """
        from app.services.gdpr import GDPRService

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = mock_user
        mock_user_repo.delete.return_value = True

        mock_session_repo = MagicMock()
        mock_audit_repo = MagicMock()

        mock_mfa_secret_repo = MagicMock()
        mock_mfa_recovery_repo = MagicMock()

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=None
        )

        service.delete_user_data(1, "GDPR request", performed_by=2)

        mock_mfa_secret_repo.delete_by_user_id.assert_called_once_with(1)
        mock_mfa_recovery_repo.delete_all_for_user.assert_called_once_with(1)

    def test_anonymize_user_data_removes_mfa(self):
        """
        anonymize_user_data() doit supprimer les donnees MFA.
        """
        from app.services.gdpr import GDPRService

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1

        mock_user_repo = MagicMock()
        mock_user_repo.get_by_id.return_value = mock_user

        mock_session_repo = MagicMock()
        mock_audit_repo = MagicMock()

        mock_mfa_secret_repo = MagicMock()
        mock_mfa_recovery_repo = MagicMock()

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo,
            mfa_secret_repository=mock_mfa_secret_repo,
            mfa_recovery_repository=mock_mfa_recovery_repo,
            api_key_repository=None
        )

        service.anonymize_user_data(1, "GDPR request", performed_by=2)

        mock_mfa_secret_repo.delete_by_user_id.assert_called_once_with(1)
        mock_mfa_recovery_repo.delete_all_for_user.assert_called_once_with(1)


class TestGDPRSchemas:
    """Tests pour les schemas GDPR."""

    def test_gdpr_export_response_has_mfa_fields(self):
        """
        GDPRExportResponse doit avoir les champs MFA et API keys.
        """
        from app.schemas.gdpr import GDPRExportResponse

        # Verifier que les champs existent dans le schema
        fields = GDPRExportResponse.model_fields
        assert "mfa_data" in fields
        assert "recovery_codes" in fields
        assert "api_keys" in fields

    def test_gdpr_mfa_data_schema(self):
        """
        GDPRMFAData doit avoir les champs requis.
        """
        from app.schemas.gdpr import GDPRMFAData

        data = GDPRMFAData(
            enabled=True,
            created_at="2024-01-01T00:00:00Z",
            last_used_at="2024-01-02T00:00:00Z"
        )

        assert data.enabled is True
        assert data.created_at == "2024-01-01T00:00:00Z"

    def test_gdpr_api_key_data_schema(self):
        """
        GDPRAPIKeyData doit avoir les champs requis.
        """
        from app.schemas.gdpr import GDPRAPIKeyData

        data = GDPRAPIKeyData(
            id=1,
            name="Test Key",
            key_prefix="mc_sk_...",
            scopes=["users:read"],
            created_at="2024-01-01T00:00:00Z",
            expires_at=None,
            revoked_at=None,
            last_used_at=None,
            is_valid=True
        )

        assert data.id == 1
        assert data.name == "Test Key"
        assert data.is_valid is True


# =============================================================================
# Tests Validation E.164 pour telephone
# =============================================================================


class TestPhoneE164Validation:
    """Tests pour la validation du format E.164."""

    def test_valid_french_phone(self):
        """
        Un numero francais valide doit etre accepte.
        """
        from app.schemas.user import UserBase

        # Utiliser model_construct pour eviter la validation email
        user = UserBase.model_construct(
            email="test@example.com",
            phone="+33612345678"
        )
        # Re-valider juste le phone
        validated = UserBase.model_validate({"email": "test@example.com", "phone": "+33612345678"})
        assert validated.phone == "+33612345678"

    def test_valid_us_phone(self):
        """
        Un numero US valide doit etre accepte.
        """
        from app.schemas.user import UserBase

        validated = UserBase.model_validate({"email": "test@example.com", "phone": "+14155551234"})
        assert validated.phone == "+14155551234"

    def test_valid_international_phone(self):
        """
        Un numero international valide doit etre accepte.
        """
        from app.schemas.user import UserBase

        validated = UserBase.model_validate({"email": "test@example.com", "phone": "+447911123456"})
        assert validated.phone == "+447911123456"

    def test_invalid_phone_without_plus(self):
        """
        Un numero sans + doit etre rejete.
        """
        from app.schemas.user import UserBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserBase.model_validate({"email": "test@example.com", "phone": "33612345678"})

        assert "E.164" in str(exc_info.value)

    def test_invalid_phone_with_spaces(self):
        """
        Un numero avec espaces doit etre rejete.
        """
        from app.schemas.user import UserBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserBase.model_validate({"email": "test@example.com", "phone": "+33 6 12 34 56 78"})

        assert "E.164" in str(exc_info.value)

    def test_invalid_phone_with_dashes(self):
        """
        Un numero avec tirets doit etre rejete.
        """
        from app.schemas.user import UserBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserBase.model_validate({"email": "test@example.com", "phone": "+33-6-12-34-56-78"})

        assert "E.164" in str(exc_info.value)

    def test_invalid_phone_too_short(self):
        """
        Un numero trop court doit etre rejete.
        """
        from app.schemas.user import UserBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserBase.model_validate({"email": "test@example.com", "phone": "+3"})

        assert "E.164" in str(exc_info.value)

    def test_invalid_phone_starting_with_zero(self):
        """
        Un numero commencant par +0 doit etre rejete.
        """
        from app.schemas.user import UserBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserBase.model_validate({"email": "test@example.com", "phone": "+0612345678"})

        assert "E.164" in str(exc_info.value)

    def test_null_phone_is_accepted(self):
        """
        Un telephone null doit etre accepte.
        """
        from app.schemas.user import UserBase

        validated = UserBase.model_validate({"email": "test@example.com", "phone": None})
        assert validated.phone is None

    def test_empty_phone_becomes_null(self):
        """
        Un telephone vide doit devenir null.
        """
        from app.schemas.user import UserBase

        validated = UserBase.model_validate({"email": "test@example.com", "phone": "   "})
        assert validated.phone is None

    def test_user_update_phone_validation(self):
        """
        UserUpdate doit aussi valider le format E.164.
        """
        from app.schemas.user import UserUpdate
        from pydantic import ValidationError

        # Valide
        update = UserUpdate.model_validate({"phone": "+33612345678"})
        assert update.phone == "+33612345678"

        # Invalide
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"phone": "0612345678"})


# =============================================================================
# Tests Validation IP et user_agent
# =============================================================================


class TestIPAddressValidation:
    """Tests pour la validation des adresses IP."""

    def test_valid_ipv4(self):
        """
        Une adresse IPv4 valide doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "192.168.1.1"})
        assert session.ip_address == "192.168.1.1"

    def test_valid_ipv4_public(self):
        """
        Une adresse IPv4 publique doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "8.8.8.8"})
        assert session.ip_address == "8.8.8.8"

    def test_valid_ipv6(self):
        """
        Une adresse IPv6 valide doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"})
        assert session.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

    def test_valid_ipv6_short(self):
        """
        Une adresse IPv6 raccourcie doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "::1"})
        assert session.ip_address == "::1"

    def test_valid_ipv6_loopback(self):
        """
        L'adresse IPv6 loopback doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "::1"})
        assert session.ip_address == "::1"

    def test_invalid_ip_hostname(self):
        """
        Un hostname doit etre rejete lors de la creation (SessionCreate).
        SessionBase en mode lecture accepte les valeurs invalides.
        """
        from app.schemas.session import SessionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SessionCreate.model_validate({"ip_address": "localhost"})

        assert "IP" in str(exc_info.value) or "invalide" in str(exc_info.value)

    def test_invalid_ip_format(self):
        """
        Une adresse IP mal formatee doit etre rejetee lors de la creation.
        """
        from app.schemas.session import SessionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SessionCreate.model_validate({"ip_address": "256.256.256.256"})

    def test_invalid_ip_with_port(self):
        """
        Une adresse IP avec port doit etre rejetee lors de la creation.
        """
        from app.schemas.session import SessionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SessionCreate.model_validate({"ip_address": "192.168.1.1:8080"})

    def test_null_ip_is_accepted(self):
        """
        Une IP null doit etre acceptee.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": None})
        assert session.ip_address is None

    def test_empty_ip_becomes_null(self):
        """
        Une IP vide doit devenir null.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"ip_address": "   "})
        assert session.ip_address is None


class TestUserAgentValidation:
    """Tests pour la validation du user_agent."""

    def test_valid_user_agent(self):
        """
        Un user_agent valide doit etre accepte.
        """
        from app.schemas.session import SessionBase

        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"
        session = SessionBase.model_validate({"user_agent": ua})
        assert session.user_agent == ua

    def test_user_agent_max_length(self):
        """
        La longueur max du user_agent est de 512 caracteres.
        """
        from app.schemas.session import MAX_USER_AGENT_LENGTH

        assert MAX_USER_AGENT_LENGTH == 512

    def test_long_user_agent_is_truncated(self):
        """
        Un user_agent trop long doit etre tronque.
        """
        from app.schemas.session import SessionBase, MAX_USER_AGENT_LENGTH

        long_ua = "X" * 1000
        session = SessionBase.model_validate({"user_agent": long_ua})
        assert len(session.user_agent) == MAX_USER_AGENT_LENGTH

    def test_null_user_agent_is_accepted(self):
        """
        Un user_agent null doit etre accepte.
        """
        from app.schemas.session import SessionBase

        session = SessionBase.model_validate({"user_agent": None})
        assert session.user_agent is None


# =============================================================================
# Tests Redis Pool Configuration
# =============================================================================


class TestRedisSettings:
    """Tests pour les settings Redis."""

    def test_redis_settings_exist(self):
        """
        Les settings Redis doivent exister dans la configuration.
        """
        from app.core.config import Settings

        settings = Settings()

        assert hasattr(settings, 'REDIS_URL')
        assert hasattr(settings, 'REDIS_MAX_CONNECTIONS')
        assert hasattr(settings, 'REDIS_HEALTH_CHECK_INTERVAL')
        assert hasattr(settings, 'REDIS_SOCKET_TIMEOUT')
        assert hasattr(settings, 'REDIS_SOCKET_CONNECT_TIMEOUT')

    def test_redis_settings_defaults(self):
        """
        Les settings Redis doivent avoir des valeurs par defaut raisonnables.
        """
        from app.core.config import Settings

        settings = Settings()

        assert settings.REDIS_MAX_CONNECTIONS == 10
        assert settings.REDIS_HEALTH_CHECK_INTERVAL == 30
        assert settings.REDIS_SOCKET_TIMEOUT == 5
        assert settings.REDIS_SOCKET_CONNECT_TIMEOUT == 5


class TestRedisPoolFunctions:
    """Tests pour les fonctions Redis."""

    def test_get_redis_pool_function_exists(self):
        """
        La fonction get_redis_pool doit exister.
        """
        from app.core.redis import get_redis_pool

        assert callable(get_redis_pool)

    def test_get_redis_client_function_exists(self):
        """
        La fonction get_redis_client doit exister.
        """
        from app.core.redis import get_redis_client

        assert callable(get_redis_client)

    def test_close_redis_client_function_exists(self):
        """
        La fonction close_redis_client doit exister.
        """
        from app.core.redis import close_redis_client

        assert callable(close_redis_client)

    def test_get_redis_pool_stats_function_exists(self):
        """
        La fonction get_redis_pool_stats doit exister.
        """
        from app.core.redis import get_redis_pool_stats

        assert callable(get_redis_pool_stats)

    def test_redis_module_uses_connection_pool(self):
        """
        Le module redis doit utiliser ConnectionPool.
        """
        import app.core.redis as redis_module
        from redis.connection import ConnectionPool

        # Verifier que le module importe ConnectionPool
        assert "ConnectionPool" in dir(redis_module) or hasattr(redis_module, 'get_redis_pool')


# =============================================================================
# Tests Data Inventory
# =============================================================================


class TestGDPRDataInventory:
    """Tests pour l'inventaire des donnees GDPR."""

    def test_data_inventory_includes_api_keys_category(self):
        """
        L'inventaire des donnees doit inclure la categorie API Keys.
        """
        from app.services.gdpr import GDPRService

        mock_user_repo = MagicMock()
        mock_session_repo = MagicMock()
        mock_audit_repo = MagicMock()

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo
        )

        inventory = service.get_data_inventory(tenant_id=1)

        categories = [cat["category"] for cat in inventory["data_categories"]]
        assert "API Keys" in categories

    def test_data_inventory_has_five_categories(self):
        """
        L'inventaire doit avoir 5 categories de donnees.
        """
        from app.services.gdpr import GDPRService

        mock_user_repo = MagicMock()
        mock_session_repo = MagicMock()
        mock_audit_repo = MagicMock()

        service = GDPRService(
            user_repository=mock_user_repo,
            session_repository=mock_session_repo,
            audit_repository=mock_audit_repo
        )

        inventory = service.get_data_inventory(tenant_id=1)

        assert len(inventory["data_categories"]) == 5
