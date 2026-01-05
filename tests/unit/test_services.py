"""
Tests unitaires pour les Services
TDD - Tests ecrits AVANT implementation
Couvre: UserService, AuthService
"""
import pytest
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch, PropertyMock


# ============================================================================
# Tests UserService Interface
# ============================================================================

class TestUserServiceInterface:
    """Tests pour verifier l'interface du UserService"""

    @pytest.mark.unit
    def test_user_service_exists(self):
        """UserService doit exister"""
        from app.services.user import UserService
        assert UserService is not None

    @pytest.mark.unit
    def test_user_service_has_create_user_method(self):
        """UserService doit avoir une methode create_user"""
        from app.services.user import UserService
        assert hasattr(UserService, "create_user")
        assert callable(getattr(UserService, "create_user"))

    @pytest.mark.unit
    def test_user_service_has_get_user_method(self):
        """UserService doit avoir une methode get_user"""
        from app.services.user import UserService
        assert hasattr(UserService, "get_user")
        assert callable(getattr(UserService, "get_user"))

    @pytest.mark.unit
    def test_user_service_has_get_user_by_email_method(self):
        """UserService doit avoir une methode get_user_by_email"""
        from app.services.user import UserService
        assert hasattr(UserService, "get_user_by_email")
        assert callable(getattr(UserService, "get_user_by_email"))

    @pytest.mark.unit
    def test_user_service_has_update_user_method(self):
        """UserService doit avoir une methode update_user"""
        from app.services.user import UserService
        assert hasattr(UserService, "update_user")
        assert callable(getattr(UserService, "update_user"))

    @pytest.mark.unit
    def test_user_service_has_delete_user_method(self):
        """UserService doit avoir une methode delete_user"""
        from app.services.user import UserService
        assert hasattr(UserService, "delete_user")
        assert callable(getattr(UserService, "delete_user"))

    @pytest.mark.unit
    def test_user_service_has_list_users_method(self):
        """UserService doit avoir une methode list_users"""
        from app.services.user import UserService
        assert hasattr(UserService, "list_users")
        assert callable(getattr(UserService, "list_users"))

    @pytest.mark.unit
    def test_user_service_has_change_password_method(self):
        """UserService doit avoir une methode change_password"""
        from app.services.user import UserService
        assert hasattr(UserService, "change_password")
        assert callable(getattr(UserService, "change_password"))


# ============================================================================
# Tests AuthService Interface
# ============================================================================

class TestAuthServiceInterface:
    """Tests pour verifier l'interface du AuthService"""

    @pytest.mark.unit
    def test_auth_service_exists(self):
        """AuthService doit exister"""
        from app.services.auth import AuthService
        assert AuthService is not None

    @pytest.mark.unit
    def test_auth_service_has_authenticate_method(self):
        """AuthService doit avoir une methode authenticate"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "authenticate")
        assert callable(getattr(AuthService, "authenticate"))

    @pytest.mark.unit
    def test_auth_service_has_login_method(self):
        """AuthService doit avoir une methode login"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "login")
        assert callable(getattr(AuthService, "login"))

    @pytest.mark.unit
    def test_auth_service_has_logout_method(self):
        """AuthService doit avoir une methode logout"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "logout")
        assert callable(getattr(AuthService, "logout"))

    @pytest.mark.unit
    def test_auth_service_has_refresh_tokens_method(self):
        """AuthService doit avoir une methode refresh_tokens"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "refresh_tokens")
        assert callable(getattr(AuthService, "refresh_tokens"))

    @pytest.mark.unit
    def test_auth_service_has_validate_token_method(self):
        """AuthService doit avoir une methode validate_token"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "validate_token")
        assert callable(getattr(AuthService, "validate_token"))

    @pytest.mark.unit
    def test_auth_service_has_get_current_user_method(self):
        """AuthService doit avoir une methode get_current_user"""
        from app.services.auth import AuthService
        assert hasattr(AuthService, "get_current_user")
        assert callable(getattr(AuthService, "get_current_user"))


# ============================================================================
# Tests UserService avec Mocks
# ============================================================================

class TestUserServiceWithMocks:
    """Tests UserService avec repositories mockes"""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock du UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def mock_tenant_repo(self):
        """Mock du TenantRepository"""
        from app.repositories.tenant import TenantRepository
        return MagicMock(spec=TenantRepository)

    @pytest.fixture
    def user_service(self, mock_user_repo, mock_tenant_repo):
        """Instance UserService avec mocks"""
        from app.services.user import UserService
        return UserService(
            user_repository=mock_user_repo,
            tenant_repository=mock_tenant_repo
        )

    @pytest.mark.unit
    def test_user_service_stores_repositories(
        self,
        user_service,
        mock_user_repo,
        mock_tenant_repo
    ):
        """UserService doit stocker les repositories"""
        assert user_service.user_repository == mock_user_repo
        assert user_service.tenant_repository == mock_tenant_repo

    @pytest.mark.unit
    def test_create_user_hashes_password(self, user_service, mock_user_repo):
        """create_user doit hasher le mot de passe"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user_repo.create.return_value = mock_user
        mock_user_repo.email_exists_in_tenant.return_value = False

        user_data = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "tenant_id": 1
        }

        result = user_service.create_user(**user_data)

        # Le password doit etre hashe avant create
        call_args = mock_user_repo.create.call_args
        assert "password" not in call_args[0][0]
        assert "password_hash" in call_args[0][0]

    @pytest.mark.unit
    def test_create_user_checks_email_exists(self, user_service, mock_user_repo):
        """create_user doit verifier si l'email existe"""
        mock_user_repo.email_exists_in_tenant.return_value = True

        user_data = {
            "email": "existing@example.com",
            "password": "SecurePass123!",
            "tenant_id": 1
        }

        with pytest.raises(Exception):  # EmailAlreadyExistsError
            user_service.create_user(**user_data)

    @pytest.mark.unit
    def test_get_user_calls_repository(self, user_service, mock_user_repo):
        """get_user doit appeler le repository"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user_repo.get_by_id.return_value = mock_user

        result = user_service.get_user(user_id=1)

        mock_user_repo.get_by_id.assert_called_once_with(1)

    @pytest.mark.unit
    def test_get_user_by_email_calls_repository(self, user_service, mock_user_repo):
        """get_user_by_email doit appeler le repository"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        result = user_service.get_user_by_email(
            email="test@example.com",
            tenant_id=1
        )

        mock_user_repo.get_by_email_and_tenant.assert_called_once()

    @pytest.mark.unit
    def test_change_password_verifies_current(self, user_service, mock_user_repo):
        """change_password doit verifier le mot de passe actuel"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.password_hash = "$2b$12$wronghash"
        mock_user_repo.get_by_id.return_value = mock_user

        with pytest.raises(Exception):  # InvalidPasswordError
            user_service.change_password(
                user_id=1,
                current_password="wrong",
                new_password="NewSecure123!"
            )

    @pytest.mark.unit
    def test_list_users_with_pagination(self, user_service, mock_user_repo):
        """list_users doit supporter la pagination"""
        mock_user_repo.get_by_tenant.return_value = []
        mock_user_repo.count_by_tenant.return_value = 0

        result = user_service.list_users(
            tenant_id=1,
            skip=10,
            limit=20
        )

        mock_user_repo.get_by_tenant.assert_called_once_with(
            tenant_id=1,
            skip=10,
            limit=20
        )


# ============================================================================
# Tests AuthService avec Mocks
# ============================================================================

class TestAuthServiceWithMocks:
    """Tests AuthService avec repositories mockes"""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock du UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def auth_service(self, mock_user_repo):
        """Instance AuthService avec mock"""
        from app.services.auth import AuthService
        return AuthService(user_repository=mock_user_repo)

    @pytest.mark.unit
    def test_auth_service_stores_repository(self, auth_service, mock_user_repo):
        """AuthService doit stocker le repository"""
        assert auth_service.user_repository == mock_user_repo

    @pytest.mark.unit
    def test_authenticate_checks_email(self, auth_service, mock_user_repo):
        """authenticate doit verifier l'email"""
        mock_user_repo.get_by_email_and_tenant.return_value = None

        result = auth_service.authenticate(
            email="notfound@example.com",
            password="password",
            tenant_id=1
        )

        assert result is None

    @pytest.mark.unit
    def test_authenticate_checks_password(self, auth_service, mock_user_repo):
        """authenticate doit verifier le mot de passe"""
        from app.models import User
        from app.core.security import hash_password

        mock_user = MagicMock(spec=User)
        mock_user.password_hash = hash_password("correct_password")
        mock_user.is_active = True
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        # Mauvais mot de passe
        result = auth_service.authenticate(
            email="test@example.com",
            password="wrong_password",
            tenant_id=1
        )

        assert result is None

    @pytest.mark.unit
    def test_authenticate_checks_is_active(self, auth_service, mock_user_repo):
        """authenticate doit verifier is_active"""
        from app.models import User
        from app.core.security import hash_password

        mock_user = MagicMock(spec=User)
        mock_user.password_hash = hash_password("password123")
        mock_user.is_active = False
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        result = auth_service.authenticate(
            email="test@example.com",
            password="password123",
            tenant_id=1
        )

        assert result is None

    @pytest.mark.unit
    def test_authenticate_returns_user_on_success(self, auth_service, mock_user_repo):
        """authenticate doit retourner l'user si succes"""
        from app.models import User
        from app.core.security import hash_password

        password = "SecurePass123!"
        mock_user = MagicMock(spec=User)
        mock_user.password_hash = hash_password(password)
        mock_user.is_active = True
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        result = auth_service.authenticate(
            email="test@example.com",
            password=password,
            tenant_id=1
        )

        assert result is not None
        assert result.id == 1

    @pytest.mark.unit
    def test_login_returns_tokens(self, auth_service, mock_user_repo):
        """login doit retourner access et refresh tokens"""
        from app.models import User
        from app.core.security import hash_password

        password = "SecurePass123!"
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password(password)
        mock_user.is_active = True
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        result = auth_service.login(
            email="test@example.com",
            password=password,
            tenant_id=1
        )

        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result
        assert "expires_in" in result

    @pytest.mark.unit
    def test_login_updates_last_login(self, auth_service, mock_user_repo):
        """login doit mettre a jour last_login_at"""
        from app.models import User
        from app.core.security import hash_password

        password = "SecurePass123!"
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password(password)
        mock_user.is_active = True
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        auth_service.login(
            email="test@example.com",
            password=password,
            tenant_id=1
        )

        mock_user_repo.update_last_login.assert_called_once_with(1)

    @pytest.mark.unit
    def test_validate_token_decodes_jwt(self, auth_service):
        """validate_token doit decoder le JWT"""
        from app.core.security import create_access_token

        token = create_access_token(subject=1, tenant_id=1)

        result = auth_service.validate_token(token)

        assert result is not None
        assert result["sub"] == "1"
        assert result["tenant_id"] == 1

    @pytest.mark.unit
    def test_validate_token_returns_none_for_invalid(self, auth_service):
        """validate_token doit retourner None pour token invalide"""
        result = auth_service.validate_token("invalid.token.here")

        assert result is None

    @pytest.mark.unit
    def test_refresh_tokens_validates_refresh_token(self, auth_service, mock_user_repo):
        """refresh_tokens doit valider le refresh token"""
        from app.core.security import create_refresh_token

        # Token valide
        refresh_token = create_refresh_token(subject=1, tenant_id=1)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.email = "test@example.com"
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        result = auth_service.refresh_tokens(refresh_token)

        assert result is not None
        assert "access_token" in result
        assert "refresh_token" in result

    @pytest.mark.unit
    def test_refresh_tokens_rejects_access_token(self, auth_service):
        """refresh_tokens doit rejeter un access token"""
        from app.core.security import create_access_token

        access_token = create_access_token(subject=1, tenant_id=1)

        result = auth_service.refresh_tokens(access_token)

        assert result is None

    @pytest.mark.unit
    def test_get_current_user_from_token(self, auth_service, mock_user_repo):
        """get_current_user doit recuperer l'user depuis le token"""
        from app.core.security import create_access_token
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_id.return_value = mock_user

        token = create_access_token(subject=1, tenant_id=1)

        result = auth_service.get_current_user(token)

        assert result is not None
        mock_user_repo.get_by_id.assert_called_once_with(1)


# ============================================================================
# Tests Exceptions Services
# ============================================================================

class TestServiceExceptions:
    """Tests pour les exceptions des services"""

    @pytest.mark.unit
    def test_email_already_exists_exception(self):
        """EmailAlreadyExistsError doit exister"""
        from app.services.exceptions import EmailAlreadyExistsError
        assert EmailAlreadyExistsError is not None

    @pytest.mark.unit
    def test_user_not_found_exception(self):
        """UserNotFoundError doit exister"""
        from app.services.exceptions import UserNotFoundError
        assert UserNotFoundError is not None

    @pytest.mark.unit
    def test_invalid_credentials_exception(self):
        """InvalidCredentialsError doit exister"""
        from app.services.exceptions import InvalidCredentialsError
        assert InvalidCredentialsError is not None

    @pytest.mark.unit
    def test_inactive_user_exception(self):
        """InactiveUserError doit exister"""
        from app.services.exceptions import InactiveUserError
        assert InactiveUserError is not None

    @pytest.mark.unit
    def test_invalid_token_exception(self):
        """InvalidTokenError doit exister"""
        from app.services.exceptions import InvalidTokenError
        assert InvalidTokenError is not None

    @pytest.mark.unit
    def test_password_mismatch_exception(self):
        """PasswordMismatchError doit exister"""
        from app.services.exceptions import PasswordMismatchError
        assert PasswordMismatchError is not None


# ============================================================================
# Tests Logique Metier
# ============================================================================

class TestBusinessLogic:
    """Tests pour la logique metier des services"""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock du UserRepository"""
        from app.repositories.user import UserRepository
        return MagicMock(spec=UserRepository)

    @pytest.fixture
    def mock_tenant_repo(self):
        """Mock du TenantRepository"""
        from app.repositories.tenant import TenantRepository
        return MagicMock(spec=TenantRepository)

    @pytest.mark.unit
    def test_user_service_validates_tenant_exists(
        self,
        mock_user_repo,
        mock_tenant_repo
    ):
        """create_user doit verifier que le tenant existe"""
        from app.services.user import UserService
        from app.services.exceptions import TenantNotFoundError

        mock_tenant_repo.get_by_id.return_value = None

        service = UserService(
            user_repository=mock_user_repo,
            tenant_repository=mock_tenant_repo
        )

        with pytest.raises(TenantNotFoundError):
            service.create_user(
                email="test@example.com",
                password="SecurePass123!",
                tenant_id=999
            )

    @pytest.mark.unit
    def test_user_service_normalizes_email(
        self,
        mock_user_repo,
        mock_tenant_repo
    ):
        """create_user doit normaliser l'email en minuscules"""
        from app.services.user import UserService
        from app.models import User, Tenant

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user_repo.create.return_value = mock_user
        mock_user_repo.email_exists_in_tenant.return_value = False

        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant_repo.get_by_id.return_value = mock_tenant

        service = UserService(
            user_repository=mock_user_repo,
            tenant_repository=mock_tenant_repo
        )

        service.create_user(
            email="TEST@EXAMPLE.COM",
            password="SecurePass123!",
            tenant_id=1
        )

        call_args = mock_user_repo.create.call_args
        assert call_args[0][0]["email"] == "test@example.com"


# ============================================================================
# Tests Tenant Service
# ============================================================================

class TestTenantServiceInterface:
    """Tests pour l'interface TenantService (optionnel Phase 1)"""

    @pytest.mark.unit
    def test_tenant_service_exists(self):
        """TenantService doit exister"""
        from app.services.tenant import TenantService
        assert TenantService is not None

    @pytest.mark.unit
    def test_tenant_service_has_create_tenant(self):
        """TenantService doit avoir create_tenant"""
        from app.services.tenant import TenantService
        assert hasattr(TenantService, "create_tenant")

    @pytest.mark.unit
    def test_tenant_service_has_get_tenant(self):
        """TenantService doit avoir get_tenant"""
        from app.services.tenant import TenantService
        assert hasattr(TenantService, "get_tenant")

    @pytest.mark.unit
    def test_tenant_service_has_get_tenant_by_slug(self):
        """TenantService doit avoir get_tenant_by_slug"""
        from app.services.tenant import TenantService
        assert hasattr(TenantService, "get_tenant_by_slug")
