"""
Tests unitaires pour le systeme RBAC
Roles, Permissions, et Controle d'Acces
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.services.rbac import (
    RBACService,
    PermissionDeniedError,
    RoleNotFoundError,
    PermissionNotFoundError,
    RoleAlreadyExistsError,
    SystemRoleModificationError,
    DEFAULT_PERMISSIONS,
    DEFAULT_ROLES,
)


# =============================================================================
# Tests des Modeles RBAC
# =============================================================================

class TestPermissionModel:
    """Tests du modele Permission."""

    def test_permission_to_dict(self):
        """Serialisation en dictionnaire."""
        perm = Permission(
            id=1,
            code="users.read",
            name="Lecture utilisateurs",
            resource="users",
            action="read",
            description="Permet de lire les utilisateurs",
            is_active=True
        )
        data = perm.to_dict()
        assert data["id"] == 1
        assert data["code"] == "users.read"
        assert data["name"] == "Lecture utilisateurs"
        assert data["resource"] == "users"
        assert data["action"] == "read"
        assert data["is_active"] is True

    def test_permission_repr(self):
        """Representation string."""
        perm = Permission(id=1, code="users.read")
        assert "users.read" in repr(perm)


class TestRoleModel:
    """Tests du modele Role."""

    def test_role_is_global_true(self):
        """Role global si tenant_id is None."""
        role = Role(id=1, code="admin", name="Admin", tenant_id=None)
        assert role.is_global is True

    def test_role_is_global_false(self):
        """Role non global si tenant_id set."""
        role = Role(id=1, code="manager", name="Manager", tenant_id=1)
        assert role.is_global is False

    def test_role_to_dict_basic(self):
        """Serialisation basique."""
        role = Role(
            id=1,
            code="admin",
            name="Administrateur",
            tenant_id=None,
            description="Role admin",
            is_system=True,
            is_active=True
        )
        data = role.to_dict()
        assert data["id"] == 1
        assert data["code"] == "admin"
        assert data["is_system"] is True
        assert data["is_global"] is True

    def test_role_repr(self):
        """Representation string."""
        role = Role(id=1, code="admin", name="Admin", tenant_id=None)
        assert "admin" in repr(role)
        assert "global" in repr(role)


class TestUserRoleModel:
    """Tests du modele UserRole."""

    def test_user_role_is_expired_false(self):
        """Non expire si expires_at est None."""
        ur = UserRole(id=1, user_id=1, role_id=1, expires_at=None)
        assert ur.is_expired is False

    def test_user_role_is_expired_true(self):
        """Expire si expires_at est dans le passe."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        ur = UserRole(id=1, user_id=1, role_id=1, expires_at=past)
        assert ur.is_expired is True

    def test_user_role_is_valid_true(self):
        """Valide si non expire."""
        future = datetime.now(timezone.utc) + timedelta(days=1)
        ur = UserRole(id=1, user_id=1, role_id=1, expires_at=future)
        assert ur.is_valid is True

    def test_user_role_is_valid_false(self):
        """Non valide si expire."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        ur = UserRole(id=1, user_id=1, role_id=1, expires_at=past)
        assert ur.is_valid is False


# =============================================================================
# Tests du Service RBAC
# =============================================================================

class TestRBACServicePermissions:
    """Tests des verifications de permissions."""

    @pytest.fixture
    def mock_repos(self):
        """Mocks des repositories."""
        perm_repo = MagicMock()
        role_repo = MagicMock()
        user_role_repo = MagicMock()
        return perm_repo, role_repo, user_role_repo

    @pytest.fixture
    def service(self, mock_repos):
        """Service RBAC avec mocks."""
        perm_repo, role_repo, user_role_repo = mock_repos
        return RBACService(
            permission_repository=perm_repo,
            role_repository=role_repo,
            user_role_repository=user_role_repo
        )

    def test_is_enabled_returns_setting(self, service):
        """is_enabled retourne la valeur du setting."""
        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            assert service.is_enabled() is True

            mock_settings.RBAC_ENABLED = False
            assert service.is_enabled() is False

    def test_check_permission_disabled_rbac(self, service, mock_repos):
        """check_permission retourne True si RBAC desactive."""
        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = False
            result = service.check_permission(user_id=1, permission_code="any")
            assert result is True

    def test_check_permission_superuser_bypass(self, service, mock_repos):
        """Superuser bypass si configure."""
        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            mock_settings.RBAC_SUPERUSER_BYPASS = True
            result = service.check_permission(
                user_id=1,
                permission_code="any",
                is_superuser=True
            )
            assert result is True

    def test_check_permission_calls_repo(self, service, mock_repos):
        """check_permission appelle le repository."""
        perm_repo, role_repo, user_role_repo = mock_repos
        user_role_repo.user_has_permission.return_value = True

        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            mock_settings.RBAC_SUPERUSER_BYPASS = True

            result = service.check_permission(
                user_id=1,
                permission_code="users.read",
                is_superuser=False
            )

            user_role_repo.user_has_permission.assert_called_once_with(1, "users.read")
            assert result is True

    def test_require_permission_raises_on_denied(self, service, mock_repos):
        """require_permission leve exception si refuse."""
        perm_repo, role_repo, user_role_repo = mock_repos
        user_role_repo.user_has_permission.return_value = False

        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            mock_settings.RBAC_SUPERUSER_BYPASS = True

            with pytest.raises(PermissionDeniedError) as exc:
                service.require_permission(
                    user_id=1,
                    permission_code="users.delete",
                    is_superuser=False
                )
            assert exc.value.permission == "users.delete"

    def test_check_any_permission(self, service, mock_repos):
        """check_any_permission avec plusieurs permissions."""
        perm_repo, role_repo, user_role_repo = mock_repos
        user_role_repo.user_has_any_permission.return_value = True

        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            mock_settings.RBAC_SUPERUSER_BYPASS = True

            result = service.check_any_permission(
                user_id=1,
                permission_codes=["users.read", "users.write"],
                is_superuser=False
            )
            assert result is True

    def test_check_all_permissions(self, service, mock_repos):
        """check_all_permissions avec plusieurs permissions."""
        perm_repo, role_repo, user_role_repo = mock_repos
        user_role_repo.user_has_all_permissions.return_value = True

        with patch("app.services.rbac.settings") as mock_settings:
            mock_settings.RBAC_ENABLED = True
            mock_settings.RBAC_SUPERUSER_BYPASS = True

            result = service.check_all_permissions(
                user_id=1,
                permission_codes=["users.read", "users.write"],
                is_superuser=False
            )
            assert result is True

    def test_get_user_permissions(self, service, mock_repos):
        """get_user_permissions retourne les permissions."""
        perm_repo, role_repo, user_role_repo = mock_repos
        user_role_repo.get_user_permission_codes.return_value = {"users.read", "users.write"}

        result = service.get_user_permissions(user_id=1)
        assert result == {"users.read", "users.write"}


class TestRBACServiceRoles:
    """Tests de gestion des roles."""

    @pytest.fixture
    def mock_repos(self):
        """Mocks des repositories."""
        perm_repo = MagicMock()
        role_repo = MagicMock()
        user_role_repo = MagicMock()
        return perm_repo, role_repo, user_role_repo

    @pytest.fixture
    def service(self, mock_repos):
        """Service RBAC avec mocks."""
        perm_repo, role_repo, user_role_repo = mock_repos
        return RBACService(
            permission_repository=perm_repo,
            role_repository=role_repo,
            user_role_repository=user_role_repo
        )

    def test_assign_role_to_user(self, service, mock_repos):
        """Assignation d'un role a un utilisateur."""
        perm_repo, role_repo, user_role_repo = mock_repos

        # Mock du role
        mock_role = MagicMock()
        mock_role.id = 1
        mock_role.is_active = True
        role_repo.get_by_code.return_value = mock_role

        # Mock du UserRole cree
        mock_user_role = MagicMock()
        mock_user_role.to_dict.return_value = {"user_id": 1, "role_id": 1}
        user_role_repo.assign_role.return_value = mock_user_role

        result = service.assign_role_to_user(
            user_id=1,
            role_code="admin",
            tenant_id=None,
            assigned_by=2
        )

        role_repo.get_by_code.assert_called_once_with("admin", None)
        user_role_repo.assign_role.assert_called_once()
        assert result == {"user_id": 1, "role_id": 1}

    def test_assign_role_not_found(self, service, mock_repos):
        """Assignation d'un role inexistant leve exception."""
        perm_repo, role_repo, user_role_repo = mock_repos
        role_repo.get_by_code.return_value = None

        with pytest.raises(RoleNotFoundError):
            service.assign_role_to_user(user_id=1, role_code="nonexistent")

    def test_assign_role_inactive(self, service, mock_repos):
        """Assignation d'un role inactif leve exception."""
        perm_repo, role_repo, user_role_repo = mock_repos
        mock_role = MagicMock()
        mock_role.is_active = False
        role_repo.get_by_code.return_value = mock_role

        with pytest.raises(RoleNotFoundError):
            service.assign_role_to_user(user_id=1, role_code="inactive_role")

    def test_revoke_role_from_user(self, service, mock_repos):
        """Revocation d'un role."""
        perm_repo, role_repo, user_role_repo = mock_repos

        mock_role = MagicMock()
        mock_role.id = 1
        role_repo.get_by_code.return_value = mock_role
        user_role_repo.revoke_role.return_value = True

        result = service.revoke_role_from_user(user_id=1, role_code="admin")
        assert result is True
        user_role_repo.revoke_role.assert_called_once_with(1, 1)

    def test_create_role_success(self, service, mock_repos):
        """Creation d'un role."""
        perm_repo, role_repo, user_role_repo = mock_repos

        role_repo.get_by_code.return_value = None  # N'existe pas

        mock_role = MagicMock()
        mock_role.id = 1
        mock_role.to_dict.return_value = {"id": 1, "code": "custom_role"}
        role_repo.create_role.return_value = mock_role

        # Mock des permissions
        mock_perm = MagicMock()
        mock_perm.id = 1
        perm_repo.get_by_codes.return_value = [mock_perm]

        result = service.create_role(
            code="custom_role",
            name="Custom Role",
            permission_codes=["users.read"]
        )

        role_repo.create_role.assert_called_once()
        assert result == {"id": 1, "code": "custom_role"}

    def test_create_role_already_exists(self, service, mock_repos):
        """Creation d'un role existant leve exception."""
        perm_repo, role_repo, user_role_repo = mock_repos

        mock_existing = MagicMock()
        role_repo.get_by_code.return_value = mock_existing

        with pytest.raises(RoleAlreadyExistsError):
            service.create_role(code="admin", name="Admin")

    def test_update_role_system_role_raises(self, service, mock_repos):
        """Modification d'un role systeme leve exception."""
        perm_repo, role_repo, user_role_repo = mock_repos

        mock_role = MagicMock()
        mock_role.is_system = True
        mock_role.code = "admin"
        role_repo.get_by_id.return_value = mock_role

        with pytest.raises(SystemRoleModificationError):
            service.update_role(role_id=1, name="New Name")

    def test_delete_role_system_role_raises(self, service, mock_repos):
        """Suppression d'un role systeme leve exception."""
        perm_repo, role_repo, user_role_repo = mock_repos

        mock_role = MagicMock()
        mock_role.is_system = True
        mock_role.code = "admin"
        role_repo.get_by_id.return_value = mock_role

        with pytest.raises(SystemRoleModificationError):
            service.delete_role(role_id=1)


class TestRBACServiceInitialization:
    """Tests d'initialisation RBAC."""

    @pytest.fixture
    def mock_repos(self):
        """Mocks des repositories."""
        perm_repo = MagicMock()
        role_repo = MagicMock()
        user_role_repo = MagicMock()
        return perm_repo, role_repo, user_role_repo

    @pytest.fixture
    def service(self, mock_repos):
        """Service RBAC avec mocks."""
        perm_repo, role_repo, user_role_repo = mock_repos
        return RBACService(
            permission_repository=perm_repo,
            role_repository=role_repo,
            user_role_repository=user_role_repo
        )

    def test_initialize_default_permissions(self, service, mock_repos):
        """Initialisation des permissions par defaut."""
        perm_repo, role_repo, user_role_repo = mock_repos
        perm_repo.bulk_create.return_value = [MagicMock()] * 5

        count = service.initialize_default_permissions()
        assert count == 5
        perm_repo.bulk_create.assert_called_once()

    def test_initialize_default_roles(self, service, mock_repos):
        """Initialisation des roles par defaut."""
        perm_repo, role_repo, user_role_repo = mock_repos

        # Aucun role n'existe
        role_repo.get_by_code.return_value = None

        # Mocks pour creation
        mock_role = MagicMock()
        mock_role.id = 1
        role_repo.create_role.return_value = mock_role

        mock_perm = MagicMock()
        mock_perm.id = 1
        perm_repo.get_by_code.return_value = mock_perm

        count = service.initialize_default_roles()
        assert count == len(DEFAULT_ROLES)

    def test_initialize_rbac_complete(self, service, mock_repos):
        """Initialisation complete."""
        perm_repo, role_repo, user_role_repo = mock_repos

        perm_repo.bulk_create.return_value = [MagicMock()] * 3
        role_repo.get_by_code.return_value = None

        mock_role = MagicMock()
        mock_role.id = 1
        role_repo.create_role.return_value = mock_role
        perm_repo.get_by_code.return_value = MagicMock(id=1)

        result = service.initialize_rbac()

        assert "permissions_created" in result
        assert "roles_created" in result


# =============================================================================
# Tests des Exceptions RBAC
# =============================================================================

class TestRBACExceptions:
    """Tests des exceptions RBAC."""

    def test_permission_denied_error(self):
        """PermissionDeniedError."""
        error = PermissionDeniedError(permission="users.delete")
        assert error.permission == "users.delete"
        assert error.code == "PERMISSION_DENIED"

    def test_permission_denied_error_custom_message(self):
        """PermissionDeniedError avec message custom."""
        error = PermissionDeniedError(message="Acces refuse")
        # Le message custom est bien utilise
        assert error.message == "Acces refuse"

    def test_role_not_found_by_id(self):
        """RoleNotFoundError par ID."""
        error = RoleNotFoundError(role_id=123)
        assert error.role_id == 123
        assert "123" in error.message

    def test_role_not_found_by_code(self):
        """RoleNotFoundError par code."""
        error = RoleNotFoundError(role_code="admin")
        assert error.role_code == "admin"
        assert "admin" in error.message

    def test_permission_not_found(self):
        """PermissionNotFoundError."""
        error = PermissionNotFoundError("users.delete")
        assert error.permission_code == "users.delete"

    def test_role_already_exists(self):
        """RoleAlreadyExistsError."""
        error = RoleAlreadyExistsError("admin", tenant_id=1)
        assert error.role_code == "admin"
        assert error.tenant_id == 1

    def test_system_role_modification(self):
        """SystemRoleModificationError."""
        error = SystemRoleModificationError("admin")
        assert error.role_code == "admin"
        assert "systeme" in error.message


# =============================================================================
# Tests des Constants RBAC
# =============================================================================

class TestRBACConstants:
    """Tests des constantes RBAC."""

    def test_default_permissions_structure(self):
        """Structure des permissions par defaut."""
        for perm in DEFAULT_PERMISSIONS:
            assert "code" in perm
            assert "name" in perm
            assert "resource" in perm
            assert "action" in perm
            # Code doit etre resource.action
            assert perm["code"] == f"{perm['resource']}.{perm['action']}"

    def test_default_roles_structure(self):
        """Structure des roles par defaut."""
        for role in DEFAULT_ROLES:
            assert "code" in role
            assert "name" in role
            assert "permissions" in role
            assert "is_system" in role

    def test_admin_role_has_all_manage_permissions(self):
        """Le role admin a les permissions manage."""
        admin = next(r for r in DEFAULT_ROLES if r["code"] == "admin")
        assert "users.manage" in admin["permissions"]
        assert "tenants.manage" in admin["permissions"]
        assert "roles.manage" in admin["permissions"]

    def test_viewer_role_read_only(self):
        """Le role viewer a seulement les permissions read."""
        viewer = next(r for r in DEFAULT_ROLES if r["code"] == "viewer")
        for perm in viewer["permissions"]:
            assert "read" in perm  # Toutes les permissions contiennent "read"
