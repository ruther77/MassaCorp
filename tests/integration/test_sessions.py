"""
Tests d'integration pour les Sessions Phase 2.

Tests end-to-end des endpoints:
- GET /sessions: Liste des sessions
- GET /sessions/{id}: Details d'une session
- DELETE /sessions/{id}: Terminer une session
- DELETE /sessions: Terminer toutes les sessions

Ces tests utilisent l'admin cree par le seed script.
"""
import pytest
from fastapi.testclient import TestClient


class TestSessionsList:
    """Tests pour GET /sessions"""

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict:
        """Obtient les headers d'authentification"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @pytest.mark.integration
    def test_list_sessions_authenticated(self, client: TestClient, auth_headers: dict):
        """GET /sessions retourne la liste des sessions"""
        response = client.get("/api/v1/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert "active_count" in data
        assert isinstance(data["sessions"], list)

    @pytest.mark.integration
    def test_list_sessions_requires_auth(self, client: TestClient):
        """GET /sessions sans token retourne 401"""
        response = client.get("/api/v1/sessions")

        assert response.status_code == 401

    @pytest.mark.integration
    def test_list_sessions_contains_device_info(self, client: TestClient, auth_headers: dict):
        """GET /sessions retourne les infos device"""
        response = client.get("/api/v1/sessions", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        if data["total"] > 0:
            session = data["sessions"][0]
            # Verifier que les champs device sont presents
            assert "device_type" in session
            assert "browser" in session
            assert "os" in session


class TestSessionDetail:
    """Tests pour GET /sessions/{session_id}"""

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict:
        """Obtient les headers d'authentification"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @pytest.mark.integration
    def test_get_session_not_found(self, client: TestClient, auth_headers: dict):
        """GET /sessions/{id} avec ID inexistant retourne 404"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/v1/sessions/{fake_uuid}",
            headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.integration
    def test_get_session_invalid_uuid(self, client: TestClient, auth_headers: dict):
        """GET /sessions/{id} avec UUID invalide retourne 422"""
        response = client.get(
            "/api/v1/sessions/invalid-uuid",
            headers=auth_headers
        )

        assert response.status_code == 422


class TestSessionTerminate:
    """Tests pour DELETE /sessions/{session_id}"""

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict:
        """Obtient les headers d'authentification"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @pytest.mark.integration
    def test_terminate_session_not_found(self, client: TestClient, auth_headers: dict):
        """DELETE /sessions/{id} avec ID inexistant retourne 404"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.delete(
            f"/api/v1/sessions/{fake_uuid}",
            headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.integration
    def test_terminate_session_requires_auth(self, client: TestClient):
        """DELETE /sessions/{id} sans token retourne 401"""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.delete(f"/api/v1/sessions/{fake_uuid}")

        assert response.status_code == 401


class TestTerminateAllSessions:
    """Tests pour DELETE /sessions"""

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict:
        """Obtient les headers d'authentification"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @pytest.mark.integration
    def test_terminate_all_sessions_success(self, client: TestClient, auth_headers: dict):
        """DELETE /sessions termine toutes les sessions"""
        response = client.request(
            "DELETE",
            "/api/v1/sessions",
            headers=auth_headers,
            json={"terminate_all": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert "terminated_count" in data
        assert "message" in data

    @pytest.mark.integration
    def test_terminate_all_sessions_requires_auth(self, client: TestClient):
        """DELETE /sessions sans token retourne 401"""
        response = client.delete("/api/v1/sessions")

        assert response.status_code == 401


class TestSessionSecurityScenarios:
    """Tests de securite pour les sessions"""

    @pytest.fixture
    def auth_headers(self, client: TestClient) -> dict:
        """Obtient les headers d'authentification"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response.status_code != 200:
            pytest.skip("Cannot get auth token - seed admin not available")
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @pytest.mark.integration
    def test_login_creates_session(self, client: TestClient):
        """Login cree une nouvelle session"""
        # Premier login
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response1.status_code != 200:
            pytest.skip("Cannot login - seed admin not available")

        token = response1.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Lister les sessions
        response2 = client.get("/api/v1/sessions", headers=headers)

        assert response2.status_code == 200
        data = response2.json()
        # On devrait avoir au moins une session
        assert data["active_count"] >= 1

    @pytest.mark.integration
    def test_multiple_logins_create_multiple_sessions(self, client: TestClient):
        """Plusieurs logins creent plusieurs sessions"""
        # Premier login
        response1 = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )
        if response1.status_code != 200:
            pytest.skip("Cannot login - seed admin not available")

        # Deuxieme login
        response2 = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "kZ5qv9gUG2@kBU8hu#DG"
            },
            headers={"X-Tenant-ID": "1"}  # Tenant requis depuis Issue #8
        )

        assert response2.status_code == 200

        # Utiliser le dernier token pour lister
        token = response2.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response3 = client.get("/api/v1/sessions", headers=headers)

        assert response3.status_code == 200
        data = response3.json()
        # On devrait avoir au moins 2 sessions actives
        assert data["active_count"] >= 2
