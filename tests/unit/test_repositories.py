"""
Tests unitaires pour les Repositories
TDD - Tests ecrits AVANT implementation
Couvre: BaseRepository, UserRepository, TenantRepository
"""
import pytest
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session


# ============================================================================
# Tests BaseRepository
# ============================================================================

class TestBaseRepositoryInterface:
    """Tests pour verifier l'interface du BaseRepository"""

    @pytest.mark.unit
    def test_base_repository_has_create_method(self):
        """BaseRepository doit avoir une methode create"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "create")
        assert callable(getattr(BaseRepository, "create"))

    @pytest.mark.unit
    def test_base_repository_has_get_method(self):
        """BaseRepository doit avoir une methode get"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "get")
        assert callable(getattr(BaseRepository, "get"))

    @pytest.mark.unit
    def test_base_repository_has_get_by_id_method(self):
        """BaseRepository doit avoir une methode get_by_id"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "get_by_id")
        assert callable(getattr(BaseRepository, "get_by_id"))

    @pytest.mark.unit
    def test_base_repository_has_get_all_method(self):
        """BaseRepository doit avoir une methode get_all"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "get_all")
        assert callable(getattr(BaseRepository, "get_all"))

    @pytest.mark.unit
    def test_base_repository_has_update_method(self):
        """BaseRepository doit avoir une methode update"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "update")
        assert callable(getattr(BaseRepository, "update"))

    @pytest.mark.unit
    def test_base_repository_has_delete_method(self):
        """BaseRepository doit avoir une methode delete"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "delete")
        assert callable(getattr(BaseRepository, "delete"))

    @pytest.mark.unit
    def test_base_repository_has_count_method(self):
        """BaseRepository doit avoir une methode count"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "count")
        assert callable(getattr(BaseRepository, "count"))

    @pytest.mark.unit
    def test_base_repository_has_exists_method(self):
        """BaseRepository doit avoir une methode exists"""
        from app.repositories.base import BaseRepository
        assert hasattr(BaseRepository, "exists")
        assert callable(getattr(BaseRepository, "exists"))


class TestBaseRepositoryGeneric:
    """Tests pour le comportement generique du BaseRepository"""

    @pytest.mark.unit
    def test_base_repository_is_generic(self):
        """BaseRepository doit etre une classe generique"""
        from app.repositories.base import BaseRepository
        from typing import Generic, TypeVar
        # Verifie que c'est une classe generique
        assert hasattr(BaseRepository, "__orig_bases__")

    @pytest.mark.unit
    def test_base_repository_accepts_model_type(self):
        """BaseRepository doit accepter un type de model"""
        from app.repositories.base import BaseRepository
        from app.models import Tenant

        class TenantRepository(BaseRepository[Tenant]):
            pass

        # Doit pouvoir etre instancie
        mock_session = MagicMock(spec=Session)
        repo = TenantRepository(mock_session)
        assert repo is not None


# ============================================================================
# Tests TenantRepository
# ============================================================================

class TestTenantRepositoryInterface:
    """Tests pour l'interface TenantRepository"""

    @pytest.mark.unit
    def test_tenant_repository_exists(self):
        """TenantRepository doit exister"""
        from app.repositories.tenant import TenantRepository
        assert TenantRepository is not None

    @pytest.mark.unit
    def test_tenant_repository_has_get_by_slug_method(self):
        """TenantRepository doit avoir get_by_slug"""
        from app.repositories.tenant import TenantRepository
        assert hasattr(TenantRepository, "get_by_slug")
        assert callable(getattr(TenantRepository, "get_by_slug"))

    @pytest.mark.unit
    def test_tenant_repository_has_get_active_tenants_method(self):
        """TenantRepository doit avoir get_active_tenants"""
        from app.repositories.tenant import TenantRepository
        assert hasattr(TenantRepository, "get_active_tenants")
        assert callable(getattr(TenantRepository, "get_active_tenants"))


# ============================================================================
# Tests UserRepository
# ============================================================================

class TestUserRepositoryInterface:
    """Tests pour l'interface UserRepository"""

    @pytest.mark.unit
    def test_user_repository_exists(self):
        """UserRepository doit exister"""
        from app.repositories.user import UserRepository
        assert UserRepository is not None

    @pytest.mark.unit
    def test_user_repository_has_get_by_email_method(self):
        """UserRepository doit avoir get_by_email"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "get_by_email")
        assert callable(getattr(UserRepository, "get_by_email"))

    @pytest.mark.unit
    def test_user_repository_has_get_by_email_and_tenant_method(self):
        """UserRepository doit avoir get_by_email_and_tenant"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "get_by_email_and_tenant")
        assert callable(getattr(UserRepository, "get_by_email_and_tenant"))

    @pytest.mark.unit
    def test_user_repository_has_get_active_users_method(self):
        """UserRepository doit avoir get_active_users"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "get_active_users")
        assert callable(getattr(UserRepository, "get_active_users"))

    @pytest.mark.unit
    def test_user_repository_has_get_by_tenant_method(self):
        """UserRepository doit avoir get_by_tenant"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "get_by_tenant")
        assert callable(getattr(UserRepository, "get_by_tenant"))

    @pytest.mark.unit
    def test_user_repository_has_verify_user_method(self):
        """UserRepository doit avoir verify_user"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "verify_user")
        assert callable(getattr(UserRepository, "verify_user"))

    @pytest.mark.unit
    def test_user_repository_has_update_last_login_method(self):
        """UserRepository doit avoir update_last_login"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "update_last_login")
        assert callable(getattr(UserRepository, "update_last_login"))

    @pytest.mark.unit
    def test_user_repository_has_update_password_method(self):
        """UserRepository doit avoir update_password"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "update_password")
        assert callable(getattr(UserRepository, "update_password"))

    @pytest.mark.unit
    def test_user_repository_has_count_by_tenant_method(self):
        """UserRepository doit avoir count_by_tenant"""
        from app.repositories.user import UserRepository
        assert hasattr(UserRepository, "count_by_tenant")
        assert callable(getattr(UserRepository, "count_by_tenant"))


# ============================================================================
# Tests Integration avec Session Mock
# ============================================================================

class TestUserRepositoryWithMockSession:
    """Tests UserRepository avec session mockee"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def user_repo(self, mock_session):
        """Instance UserRepository avec mock"""
        from app.repositories.user import UserRepository
        return UserRepository(mock_session)

    @pytest.mark.unit
    def test_user_repository_stores_session(self, user_repo, mock_session):
        """UserRepository doit stocker la session"""
        assert user_repo.session == mock_session

    @pytest.mark.unit
    def test_get_by_email_raises_runtime_error(self, user_repo, mock_session):
        """get_by_email doit lever RuntimeError - SUPPRIME pour securite multi-tenant"""
        # SECURITE: Cette methode est supprimee car elle violait l'isolation tenant
        with pytest.raises(RuntimeError) as exc_info:
            user_repo.get_by_email("test@example.com")

        assert "SUPPRIME" in str(exc_info.value)
        assert "get_by_email_and_tenant" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_by_email_and_tenant_filters_both(self, user_repo, mock_session):
        """get_by_email_and_tenant doit filtrer par email ET tenant"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = user_repo.get_by_email_and_tenant("test@example.com", tenant_id=1)

        mock_session.query.assert_called_once()


class TestTenantRepositoryWithMockSession:
    """Tests TenantRepository avec session mockee"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def tenant_repo(self, mock_session):
        """Instance TenantRepository avec mock"""
        from app.repositories.tenant import TenantRepository
        return TenantRepository(mock_session)

    @pytest.mark.unit
    def test_tenant_repository_stores_session(self, tenant_repo, mock_session):
        """TenantRepository doit stocker la session"""
        assert tenant_repo.session == mock_session

    @pytest.mark.unit
    def test_get_by_slug_calls_filter(self, tenant_repo, mock_session):
        """get_by_slug doit filtrer par slug"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = tenant_repo.get_by_slug("epicerie")

        mock_session.query.assert_called_once()


# ============================================================================
# Tests de Pagination
# ============================================================================

class TestRepositoryPagination:
    """Tests pour la pagination des repositories"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_get_all_with_pagination(self, mock_session):
        """get_all doit supporter skip et limit"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_all(skip=10, limit=20)

        mock_query.offset.assert_called_with(10)
        mock_query.limit.assert_called_with(20)

    @pytest.mark.unit
    def test_get_all_default_pagination(self, mock_session):
        """get_all doit avoir des valeurs par defaut pour skip/limit"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_all()

        # Par defaut: skip=0, limit=100
        mock_query.offset.assert_called_with(0)
        mock_query.limit.assert_called_with(100)


# ============================================================================
# Tests Multi-tenant
# ============================================================================

class TestMultiTenantIsolation:
    """Tests pour l'isolation multi-tenant"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_get_by_tenant_filters_by_tenant_id(self, mock_session):
        """get_by_tenant doit filtrer par tenant_id"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = repo.get_by_tenant(tenant_id=1)

        # Verifie qu'un filtre a ete applique
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_count_by_tenant_counts_only_tenant_users(self, mock_session):
        """count_by_tenant doit compter seulement les users du tenant"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5

        result = repo.count_by_tenant(tenant_id=1)

        assert result == 5


# ============================================================================
# Tests Create/Update/Delete
# ============================================================================

class TestRepositoryCRUD:
    """Tests pour les operations CRUD"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_create_adds_to_session(self, mock_session):
        """create doit ajouter l'objet a la session"""
        from app.repositories.user import UserRepository
        from app.models import User
        repo = UserRepository(mock_session)

        user_data = {
            "email": "test@example.com",
            "tenant_id": 1,
            "password_hash": "hashed"
        }

        repo.create(user_data)

        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_create_flushes_session(self, mock_session):
        """create doit faire un flush pour obtenir l'ID"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        user_data = {
            "email": "test@example.com",
            "tenant_id": 1,
            "password_hash": "hashed"
        }

        repo.create(user_data)

        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_update_modifies_attributes(self, mock_session):
        """update doit modifier les attributs de l'objet"""
        from app.repositories.user import UserRepository
        from app.models import User
        repo = UserRepository(mock_session)

        # Mock user existant
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        result = repo.update(1, {"first_name": "John"})

        mock_session.flush.assert_called()

    @pytest.mark.unit
    def test_delete_removes_from_session(self, mock_session):
        """delete doit supprimer l'objet de la session"""
        from app.repositories.user import UserRepository
        from app.models import User
        repo = UserRepository(mock_session)

        # Mock user existant
        mock_user = MagicMock(spec=User)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        result = repo.delete(1)

        mock_session.delete.assert_called_once_with(mock_user)

    @pytest.mark.unit
    def test_delete_returns_false_if_not_found(self, mock_session):
        """delete doit retourner False si l'objet n'existe pas"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.delete(999)

        assert result is False
        mock_session.delete.assert_not_called()


# ============================================================================
# Tests Specifiques User
# ============================================================================

class TestUserRepositorySpecificMethods:
    """Tests pour les methodes specifiques de UserRepository"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def user_repo(self, mock_session):
        """Instance UserRepository avec mock"""
        from app.repositories.user import UserRepository
        return UserRepository(mock_session)

    @pytest.mark.unit
    def test_verify_user_sets_is_verified_true(self, user_repo, mock_session):
        """verify_user doit mettre is_verified a True"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.is_verified = False
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        result = user_repo.verify_user(1)

        assert mock_user.is_verified is True

    @pytest.mark.unit
    def test_update_last_login_sets_timestamp(self, user_repo, mock_session):
        """update_last_login doit mettre a jour last_login_at"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.last_login_at = None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        result = user_repo.update_last_login(1)

        # last_login_at doit etre un datetime
        assert mock_user.last_login_at is not None

    @pytest.mark.unit
    def test_update_password_changes_hash(self, user_repo, mock_session):
        """update_password doit changer password_hash"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.password_hash = "old_hash"
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        new_hash = "new_secure_hash"
        result = user_repo.update_password(1, new_hash)

        assert mock_user.password_hash == new_hash

    @pytest.mark.unit
    def test_update_password_sets_changed_at(self, user_repo, mock_session):
        """update_password doit mettre a jour password_changed_at"""
        from app.models import User

        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.password_changed_at = None
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user

        result = user_repo.update_password(1, "new_hash")

        assert mock_user.password_changed_at is not None

    @pytest.mark.unit
    def test_get_active_users_filters_is_active(self, user_repo, mock_session):
        """get_active_users doit filtrer par is_active=True"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = user_repo.get_active_users()

        mock_query.filter.assert_called()


# ============================================================================
# Tests Exceptions
# ============================================================================

class TestRepositoryExceptions:
    """Tests pour la gestion des exceptions"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_repository_not_found_exception_exists(self):
        """RepositoryException doit exister"""
        from app.repositories.base import RepositoryException
        assert RepositoryException is not None

    @pytest.mark.unit
    def test_get_by_id_returns_none_if_not_found(self, mock_session):
        """get_by_id doit retourner None si non trouve"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.get_by_id(999)

        assert result is None

    @pytest.mark.unit
    def test_exists_returns_boolean(self, mock_session):
        """exists doit retourner un boolean"""
        from app.repositories.user import UserRepository
        repo = UserRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.exists(999)

        assert isinstance(result, bool)
        assert result is False
