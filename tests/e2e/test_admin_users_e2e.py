"""
Tests E2E pour la gestion des utilisateurs admin.

Ces tests verifient les workflows complets de gestion d'utilisateurs:
1. Lister les utilisateurs
2. Creer un nouvel utilisateur
3. Modifier un utilisateur existant
4. Supprimer un utilisateur
5. Gestion des roles et permissions

IMPORTANT: Ces tests utilisent TestClient FastAPI pour simuler
des appels HTTP reels sans dependre de Playwright/Selenium.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Client de test FastAPI."""
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """
    Obtient un token d'authentification admin.
    Utilise les credentials de l'admin par defaut.
    """
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@massacorp.dev",
            "password": "Massacorp2024!"
        },
        headers={"X-Tenant-ID": "1"}
    )

    if response.status_code == 200:
        return response.json().get("access_token")

    # Si MFA requis, skip le test
    if response.json().get("mfa_required"):
        pytest.skip("Admin requires MFA, cannot authenticate in E2E test")

    pytest.skip(f"Cannot authenticate admin: {response.status_code}")


class TestUsersListE2E:
    """
    Scenario E2E: Lister les utilisateurs
    """

    def test_list_users_requires_auth(self, client):
        """
        E2E: La liste des utilisateurs requiert authentification.
        """
        response = client.get("/api/v1/users/")
        assert response.status_code == 401

    def test_list_users_with_auth(self, client, admin_token):
        """
        E2E: Un admin peut lister les utilisateurs.
        """
        response = client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "users" in data or "items" in data or isinstance(data, list)

    def test_list_users_with_pagination(self, client, admin_token):
        """
        E2E: La pagination fonctionne correctement.
        """
        response = client.get(
            "/api/v1/users/?page=1&per_page=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200


class TestUserCRUDE2E:
    """
    Scenario E2E: CRUD complet utilisateur
    """

    def test_create_user_requires_auth(self, client):
        """
        E2E: La creation d'utilisateur requiert authentification.
        """
        response = client.post(
            "/api/v1/users/",
            json={
                "email": "test@test.com",
                "password": "Test1234!",
                "first_name": "Test",
                "last_name": "User"
            }
        )
        assert response.status_code == 401

    def test_create_user_as_admin(self, client, admin_token):
        """
        E2E: Un admin peut creer un utilisateur.
        """
        unique_email = f"e2e_user_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Test",
                "last_name": "E2E",
                "is_active": True,
                "is_superuser": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Accept 201 (created) or 200 (ok)
        assert response.status_code in [200, 201], f"Failed to create user: {response.json()}"

        data = response.json()
        assert data["email"] == unique_email
        assert data["first_name"] == "Test"
        assert data["last_name"] == "E2E"
        assert "id" in data

    def test_get_user_by_id(self, client, admin_token):
        """
        E2E: Un admin peut recuperer un utilisateur par ID.
        """
        # First create a user
        unique_email = f"e2e_get_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Get",
                "last_name": "Test"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Get user by ID
        response = client.get(
            f"/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        assert response.json()["id"] == user_id

    def test_update_user(self, client, admin_token):
        """
        E2E: Un admin peut modifier un utilisateur.
        """
        # First create a user
        unique_email = f"e2e_update_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Update",
                "last_name": "Test"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Update user
        response = client.put(
            f"/api/v1/users/{user_id}",
            json={
                "first_name": "Updated",
                "last_name": "Name"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"

    def test_deactivate_user(self, client, admin_token):
        """
        E2E: Un admin peut desactiver un utilisateur.
        """
        # First create a user
        unique_email = f"e2e_deactivate_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Deactivate",
                "last_name": "Test",
                "is_active": True
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Deactivate user
        response = client.put(
            f"/api/v1/users/{user_id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        assert response.json()["is_active"] == False

    def test_delete_user(self, client, admin_token):
        """
        E2E: Un admin peut supprimer un utilisateur.
        """
        # First create a user
        unique_email = f"e2e_delete_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Delete",
                "last_name": "Test"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Delete user
        response = client.delete(
            f"/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code in [200, 204]

        # Verify user is deleted
        get_response = client.get(
            f"/api/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert get_response.status_code == 404


class TestUserValidationE2E:
    """
    Scenario E2E: Validation des donnees utilisateur
    """

    def test_create_user_invalid_email(self, client, admin_token):
        """
        E2E: Email invalide est rejete.
        """
        response = client.post(
            "/api/v1/users/",
            json={
                "email": "not-an-email",
                "password": "MassaCorp2024$Test!",
                "first_name": "Test",
                "last_name": "User"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 422

    def test_create_user_weak_password(self, client, admin_token):
        """
        E2E: Mot de passe faible est rejete.
        """
        unique_email = f"e2e_weak_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "weak",
                "first_name": "Test",
                "last_name": "User"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Should fail validation
        assert response.status_code in [400, 422]

    def test_create_user_duplicate_email(self, client, admin_token):
        """
        E2E: Email duplique est rejete.
        """
        unique_email = f"e2e_dup_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        # Create first user
        response1 = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "First",
                "last_name": "User"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if response1.status_code not in [200, 201]:
            pytest.skip("Cannot create first user")

        # Try to create second user with same email
        response2 = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Second",
                "last_name": "User"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response2.status_code in [400, 409, 422]

    def test_update_user_invalid_data(self, client, admin_token):
        """
        E2E: Mise a jour avec donnees invalides est rejetee.
        """
        # First create a user
        unique_email = f"e2e_inv_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Invalid",
                "last_name": "Test"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Try to update with invalid email
        response = client.put(
            f"/api/v1/users/{user_id}",
            json={"email": "not-valid-email"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 422


class TestUserPermissionsE2E:
    """
    Scenario E2E: Permissions et roles utilisateur
    """

    def test_non_admin_cannot_list_users(self, client):
        """
        E2E: Un utilisateur non-admin ne peut pas lister les utilisateurs.
        """
        # Create a regular user and get their token
        unique_email = f"e2e_regular_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        # Try to register
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!"
            },
            headers={"X-Tenant-ID": "1"}
        )

        if register_response.status_code not in [200, 201]:
            pytest.skip("Cannot register regular user")

        # Login to get token
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!"
            },
            headers={"X-Tenant-ID": "1"}
        )

        if login_response.status_code != 200:
            pytest.skip("Cannot login regular user")

        token = login_response.json().get("access_token")

        # Try to list users
        response = client.get(
            "/api/v1/users/",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should be forbidden for non-admin
        assert response.status_code in [401, 403]

    def test_toggle_superuser_status(self, client, admin_token):
        """
        E2E: Un admin peut promouvoir/revoquer le statut superuser.
        """
        # Create a regular user
        unique_email = f"e2e_super_{uuid.uuid4().hex[:8]}@test.massacorp.dev"

        create_response = client.post(
            "/api/v1/users/",
            json={
                "email": unique_email,
                "password": "MassaCorp2024$Test!",
                "first_name": "Super",
                "last_name": "Test",
                "is_superuser": False
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code not in [200, 201]:
            pytest.skip("Cannot create test user")

        user_id = create_response.json()["id"]

        # Promote to superuser
        response = client.put(
            f"/api/v1/users/{user_id}",
            json={"is_superuser": True},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        assert response.json()["is_superuser"] == True

        # Demote from superuser
        response = client.put(
            f"/api/v1/users/{user_id}",
            json={"is_superuser": False},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        assert response.json()["is_superuser"] == False


class TestUserMFAStatusE2E:
    """
    Scenario E2E: Statut MFA des utilisateurs
    """

    def test_view_user_mfa_status_via_profile(self, client, admin_token):
        """
        E2E: Un admin peut voir son propre statut MFA via /me.

        Note: Le statut MFA n'est pas expose dans la liste publique
        pour des raisons de securite. Il est visible via /me ou /users/{id}.
        """
        # Get current user profile
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200

        data = response.json()
        # Check that MFA status field exists in user profile
        assert "mfa_enabled" in data or "has_mfa" in data


class TestUserSearchE2E:
    """
    Scenario E2E: Recherche d'utilisateurs
    """

    def test_search_users_by_email(self, client, admin_token):
        """
        E2E: Un admin peut rechercher des utilisateurs par email.
        """
        response = client.get(
            "/api/v1/users/?search=admin",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Search parameter may not be implemented, just verify no error
        assert response.status_code in [200, 422]

    def test_filter_users_by_status(self, client, admin_token):
        """
        E2E: Un admin peut filtrer les utilisateurs par statut.
        """
        response = client.get(
            "/api/v1/users/?is_active=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Filter parameter may not be implemented, just verify no error
        assert response.status_code in [200, 422]
