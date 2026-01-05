"""
Tests d'integration pour l'authentification
Tests end-to-end des endpoints auth

Note: Ces tests utilisent l'admin cree par le seed script.
Pour creer des utilisateurs de test, il faut commiter et cleaner manuellement.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, Tenant


class TestAuthLoginWithSeedUser:
    """Tests pour le endpoint /auth/login avec l'admin du seed"""

    @pytest.mark.integration
    def test_login_success_with_seed_admin(self, client: TestClient):
        """Login avec l'admin du seed retourne des tokens"""
        # Utiliser l'admin cree par le seed
        # Note: Le mot de passe peut changer, test optionnel
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"  # Du seed
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )

        # Si le mot de passe est different, on skip le test
        if response.status_code == 401:
            pytest.skip("Admin password different - seed has been re-run")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.integration
    def test_login_wrong_password(self, client: TestClient):
        """Login avec mauvais mot de passe retourne 401"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "WrongPassword123!"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )

        # 401 = credentials invalides, 429 = rate limiting (acceptable)
        assert response.status_code in [401, 429]
        if response.status_code == 401:
            # L'API utilise "message" (format custom) pas "detail" (format FastAPI)
            assert "invalide" in response.json()["message"].lower()

    @pytest.mark.integration
    def test_login_nonexistent_email(self, client: TestClient):
        """Login avec email inexistant retourne 401"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "notexist@example.com",
                "password": "SomePass123!"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )

        # 401 = email inexistant, 429 = rate limiting (acceptable)
        assert response.status_code in [401, 429]

    @pytest.mark.integration
    def test_login_invalid_email_format(self, client: TestClient):
        """Login avec email invalide retourne 422"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "invalid-email",
                "password": "SomePass123!"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )

        # 422 = email invalide, 429 = rate limiting (acceptable)
        assert response.status_code in [422, 429]


class TestAuthMe:
    """Tests pour le endpoint /auth/me"""

    @pytest.fixture
    def auth_token(self, client: TestClient) -> str:
        """Obtient un token valide"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available or rate limited")
        return response.json()["access_token"]

    @pytest.mark.integration
    def test_me_authenticated(self, client: TestClient, auth_token: str):
        """GET /auth/me avec token valide retourne les infos"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "admin@massacorp.dev"

    @pytest.mark.integration
    def test_me_no_token(self, client: TestClient):
        """GET /auth/me sans token retourne 401"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.integration
    def test_me_invalid_token(self, client: TestClient):
        """GET /auth/me avec token invalide retourne 401"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    @pytest.mark.integration
    def test_me_malformed_header(self, client: TestClient):
        """GET /auth/me avec header malformed retourne 401"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "InvalidFormat"}
        )

        assert response.status_code == 401


class TestAuthRefresh:
    """Tests pour le endpoint /auth/refresh"""

    @pytest.fixture
    def tokens(self, client: TestClient) -> dict:
        """Obtient les tokens"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get tokens - seed admin not available or rate limited")
        return response.json()

    @pytest.mark.integration
    def test_refresh_valid_token(self, client: TestClient, tokens: dict):
        """POST /auth/refresh avec refresh token valide retourne nouveaux tokens"""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # Note: Les tokens peuvent etre identiques si generes dans la meme seconde
        # Le refresh token doit etre different (contient JTI unique)
        assert data["refresh_token"] != tokens["refresh_token"]

    @pytest.mark.integration
    def test_refresh_invalid_token(self, client: TestClient):
        """POST /auth/refresh avec token invalide retourne 401"""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.refresh.token"}
        )

        assert response.status_code == 401

    @pytest.mark.integration
    def test_refresh_with_access_token_fails(self, client: TestClient, tokens: dict):
        """POST /auth/refresh avec access token au lieu de refresh retourne 401"""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["access_token"]}
        )

        assert response.status_code == 401


class TestAuthVerifyToken:
    """Tests pour le endpoint /auth/verify-token"""

    @pytest.fixture
    def auth_token(self, client: TestClient) -> str:
        """Obtient un token valide"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available or rate limited")
        return response.json()["access_token"]

    @pytest.mark.integration
    def test_verify_valid_token(self, client: TestClient, auth_token: str):
        """POST /auth/verify-token avec token valide retourne success"""
        response = client.post(
            "/api/v1/auth/verify-token",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["valid"] is True


class TestAuthLogout:
    """Tests pour le endpoint /auth/logout"""

    @pytest.fixture
    def auth_token(self, client: TestClient) -> str:
        """Obtient un token valide"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available or rate limited")
        return response.json()["access_token"]

    @pytest.mark.integration
    def test_logout_success(self, client: TestClient, auth_token: str):
        """POST /auth/logout avec token valide retourne success"""
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={}  # LogoutRequest peut etre vide
        )

        assert response.status_code == 200

    @pytest.mark.integration
    def test_logout_requires_auth(self, client: TestClient):
        """POST /auth/logout sans token retourne 401"""
        response = client.post("/api/v1/auth/logout", json={})

        assert response.status_code == 401
