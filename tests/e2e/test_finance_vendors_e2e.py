"""
Tests E2E pour les endpoints Finance Vendors.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestFinanceVendorsE2E:
    """Tests E2E pour la gestion des fournisseurs."""

    @pytest.fixture
    def auth_headers(self, client: TestClient):
        """Obtient les headers d'authentification."""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@massacorp.dev", "password": "Massacorp2024!"},
            headers={"X-Tenant-ID": "1"}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    @pytest.fixture
    def entity_id(self, client: TestClient, auth_headers):
        """Cree ou recupere une entite pour les tests."""
        # Essayer de creer une entite
        response = client.post(
            "/api/v1/finance/entities",
            headers=auth_headers,
            json={"name": "Test Entity Vendors", "code": "TESTVENDORS", "currency": "EUR"}
        )
        if response.status_code == 201:
            return response.json()["id"]
        # Si existe deja, recuperer la liste
        response = client.get("/api/v1/finance/entities", headers=auth_headers)
        entities = response.json()
        return entities[0]["id"] if entities else None

    def test_create_vendor_returns_201(self, client: TestClient, auth_headers, entity_id):
        """Creation d'un fournisseur retourne 201."""
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={
                "entity_id": entity_id,
                "name": "Test Vendor",
                "contact_name": "Contact Test",
                "contact_phone": "0123456789",
                "contact_email": "test@vendor.com",
                "payment_terms_days": 30
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Vendor"
        assert data["contact_name"] == "Contact Test"
        assert data["is_active"] is True
        assert data["payment_terms_days"] == 30

    def test_create_vendor_with_full_address(self, client: TestClient, auth_headers, entity_id):
        """Creation d'un fournisseur avec adresse complete."""
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={
                "entity_id": entity_id,
                "name": "Vendor With Address",
                "address": "123 Rue Test",
                "postal_code": "75001",
                "city": "Paris",
                "country": "FR"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["address"] == "123 Rue Test"
        assert data["postal_code"] == "75001"
        assert data["city"] == "Paris"
        assert data["country"] == "FR"

    def test_list_vendors_returns_array(self, client: TestClient, auth_headers, entity_id):
        """Liste des fournisseurs retourne un tableau."""
        # D'abord creer un vendor
        client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor for List Test"}
        )
        # Lister
        response = client.get(
            f"/api/v1/finance/vendors?entity_id={entity_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_vendors_active_only_filter(self, client: TestClient, auth_headers, entity_id):
        """Le filtre active_only fonctionne."""
        # Creer et desactiver un vendor
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor To Deactivate Filter"}
        )
        vendor_id = create_resp.json()["id"]
        client.post(f"/api/v1/finance/vendors/{vendor_id}/deactivate", headers=auth_headers)

        # Lister avec active_only=true
        response = client.get(
            f"/api/v1/finance/vendors?entity_id={entity_id}&active_only=true",
            headers=auth_headers
        )
        data = response.json()
        # Le vendor desactive ne doit pas apparaitre
        inactive_found = any(v["id"] == vendor_id for v in data)
        assert not inactive_found, "Le fournisseur desactive ne devrait pas apparaitre"

    def test_get_vendor_by_id(self, client: TestClient, auth_headers, entity_id):
        """Recuperation d'un fournisseur par ID."""
        # Creer
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor Get By ID Test"}
        )
        vendor_id = create_resp.json()["id"]

        # Recuperer
        response = client.get(f"/api/v1/finance/vendors/{vendor_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == vendor_id
        assert data["name"] == "Vendor Get By ID Test"

    def test_get_vendor_not_found_returns_404(self, client: TestClient, auth_headers):
        """Fournisseur inexistant retourne 404."""
        response = client.get("/api/v1/finance/vendors/999999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_vendor(self, client: TestClient, auth_headers, entity_id):
        """Mise a jour d'un fournisseur."""
        # Creer
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor Update Test"}
        )
        vendor_id = create_resp.json()["id"]

        # Mettre a jour
        response = client.put(
            f"/api/v1/finance/vendors/{vendor_id}",
            headers=auth_headers,
            json={"name": "Updated Vendor Name", "payment_terms_days": 60}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Vendor Name"
        assert data["payment_terms_days"] == 60

    def test_deactivate_vendor(self, client: TestClient, auth_headers, entity_id):
        """Desactivation d'un fournisseur."""
        # Creer
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor Deactivate Test"}
        )
        vendor_id = create_resp.json()["id"]

        # Desactiver
        response = client.post(f"/api/v1/finance/vendors/{vendor_id}/deactivate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_activate_vendor(self, client: TestClient, auth_headers, entity_id):
        """Reactivation d'un fournisseur."""
        # Creer et desactiver
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor Activate Test"}
        )
        vendor_id = create_resp.json()["id"]
        client.post(f"/api/v1/finance/vendors/{vendor_id}/deactivate", headers=auth_headers)

        # Reactiver
        response = client.post(f"/api/v1/finance/vendors/{vendor_id}/activate", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_search_vendors_by_name(self, client: TestClient, auth_headers, entity_id):
        """Recherche de fournisseurs par nom."""
        # Creer un vendor avec un nom specifique
        client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "UNIQUE_SEARCH_NAME_XYZ"}
        )

        # Rechercher
        response = client.get(
            f"/api/v1/finance/vendors/search?entity_id={entity_id}&name=UNIQUE_SEARCH",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any("UNIQUE_SEARCH_NAME_XYZ" in v["name"] for v in data)

    def test_create_vendor_requires_name(self, client: TestClient, auth_headers, entity_id):
        """Creation sans nom retourne 422."""
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id}
        )
        assert response.status_code == 422

    def test_create_vendor_requires_entity_id(self, client: TestClient, auth_headers):
        """Creation sans entity_id retourne 422."""
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"name": "Test Without Entity"}
        )
        assert response.status_code == 422

    def test_vendor_with_banking_info(self, client: TestClient, auth_headers, entity_id):
        """Creation d'un fournisseur avec infos bancaires."""
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={
                "entity_id": entity_id,
                "name": "Vendor With Bank Info",
                "iban": "FR7630006000011234567890189",
                "bic": "BNPAFRPP"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["iban"] == "FR7630006000011234567890189"
        assert data["bic"] == "BNPAFRPP"

    def test_vendor_with_code_uppercased(self, client: TestClient, auth_headers, entity_id):
        """Creation d'un fournisseur avec code (mis en majuscules)."""
        import uuid
        unique_code = f"VCODE{uuid.uuid4().hex[:6].upper()}"
        response = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={
                "entity_id": entity_id,
                "name": "Vendor With Code",
                "code": unique_code.lower()
            }
        )
        assert response.status_code == 201
        data = response.json()
        # Le code doit etre en majuscules
        assert data["code"] == unique_code

    def test_delete_vendor(self, client: TestClient, auth_headers, entity_id):
        """Suppression d'un fournisseur."""
        # Creer
        create_resp = client.post(
            "/api/v1/finance/vendors",
            headers=auth_headers,
            json={"entity_id": entity_id, "name": "Vendor Delete Test"}
        )
        vendor_id = create_resp.json()["id"]

        # Supprimer
        response = client.delete(f"/api/v1/finance/vendors/{vendor_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verifier qu'il n'existe plus
        get_resp = client.get(f"/api/v1/finance/vendors/{vendor_id}", headers=auth_headers)
        assert get_resp.status_code == 404
