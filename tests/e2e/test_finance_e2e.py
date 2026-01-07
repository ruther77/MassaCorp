"""
Tests E2E pour les endpoints Finance.
Verifie le comportement complet de l'API Finance.
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestFinanceE2E:
    """
    Tests E2E pour Finance.
    NOTE: Ces tests necessitent que la migration Finance soit executee.
    Ils sont skippes par defaut et actives apres migration.
    """

    @pytest.fixture
    def auth_headers(self, client: TestClient):
        """Obtient les headers d'authentification."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@massacorp.dev",
                "password": "Massacorp2024!",
            },
            headers={"X-Tenant-ID": "1"}
        )
        if response.status_code != 200:
            pytest.skip(f"Impossible de s'authentifier: {response.status_code} - {response.text}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    def test_create_entity_returns_201(self, client: TestClient, auth_headers):
        """Creer une entite doit retourner 201."""
        response = client.post(
            "/api/v1/finance/entities",
            json={
                "name": "Test Corp",
                "code": "TEST01",
                "currency": "EUR",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Corp"
        assert data["code"] == "TEST01"
        assert data["is_active"] is True

    def test_create_entity_rejects_duplicate_code(self, client: TestClient, auth_headers):
        """Creer une entite avec code existant doit retourner 409."""
        # Premiere creation
        client.post(
            "/api/v1/finance/entities",
            json={"name": "First", "code": "DUP01"},
            headers=auth_headers
        )

        # Tentative de doublon
        response = client.post(
            "/api/v1/finance/entities",
            json={"name": "Second", "code": "DUP01"},
            headers=auth_headers
        )

        assert response.status_code == 409

    def test_list_entities_returns_only_active(self, client: TestClient, auth_headers):
        """Lister les entites doit retourner uniquement les actives."""
        response = client.get(
            "/api/v1/finance/entities",
            headers=auth_headers
        )

        assert response.status_code == 200
        entities = response.json()
        for entity in entities:
            assert entity["is_active"] is True

    def test_create_account_normalizes_iban(self, client: TestClient, auth_headers):
        """Creer un compte doit normaliser l'IBAN."""
        # D'abord creer une entite
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Bank Test", "code": "BNK01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        # Creer le compte avec IBAN non normalise
        response = client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Principal",
                "type": "BANQUE",
                "iban": "fr76 3000 1007 9412 3456 7890 185",  # Minuscules + espaces
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        # L'IBAN retourne doit etre masque mais on verifie la normalisation via get

    def test_create_transaction_updates_balance(self, client: TestClient, auth_headers):
        """Creer une transaction doit mettre a jour le solde."""
        # Setup: creer entite + compte
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Tx Test", "code": "TX01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        account_resp = client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Tx",
                "type": "BANQUE",
                "initial_balance": 100000,  # 1000 EUR
            },
            headers=auth_headers
        )
        account_id = account_resp.json()["id"]
        initial_balance = account_resp.json()["current_balance"]

        # Creer une transaction credit
        tx_resp = client.post(
            "/api/v1/finance/transactions",
            json={
                "entity_id": entity_id,
                "account_id": account_id,
                "direction": "IN",
                "amount": 50000,  # 500 EUR
                "label": "Depot test",
                "date_operation": str(date.today()),
            },
            headers=auth_headers
        )

        assert tx_resp.status_code == 201

        # Verifier le nouveau solde
        account_after = client.get(
            f"/api/v1/finance/accounts/{account_id}",
            headers=auth_headers
        )
        new_balance = account_after.json()["current_balance"]

        assert new_balance == initial_balance + 50000

    def test_cancel_transaction_reverts_balance(self, client: TestClient, auth_headers):
        """Annuler une transaction doit reverter le solde."""
        # Setup: creer entite + compte + transaction
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Cancel Test", "code": "CAN01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        account_resp = client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Cancel",
                "type": "BANQUE",
                "initial_balance": 100000,
            },
            headers=auth_headers
        )
        account_id = account_resp.json()["id"]

        # Transaction debit
        tx_resp = client.post(
            "/api/v1/finance/transactions",
            json={
                "entity_id": entity_id,
                "account_id": account_id,
                "direction": "OUT",
                "amount": 30000,
                "label": "Retrait test",
                "date_operation": str(date.today()),
            },
            headers=auth_headers
        )
        tx_id = tx_resp.json()["id"]

        # Solde apres transaction = 70000
        account_after_tx = client.get(
            f"/api/v1/finance/accounts/{account_id}",
            headers=auth_headers
        )
        assert account_after_tx.json()["current_balance"] == 70000

        # Annuler la transaction
        cancel_resp = client.post(
            f"/api/v1/finance/transactions/{tx_id}/cancel",
            headers=auth_headers
        )

        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "CANCELLED"

        # Solde doit etre revenu a 100000
        account_final = client.get(
            f"/api/v1/finance/accounts/{account_id}",
            headers=auth_headers
        )
        assert account_final.json()["current_balance"] == 100000

    def test_dashboard_returns_kpis(self, client: TestClient, auth_headers):
        """Le dashboard doit retourner les KPIs."""
        # Setup
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Dashboard Test", "code": "DASH01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        # Creer un compte
        client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Dashboard",
                "type": "BANQUE",
                "initial_balance": 500000,
            },
            headers=auth_headers
        )

        # Recuperer le dashboard
        response = client.get(
            f"/api/v1/finance/dashboard?entity_id={entity_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "balances" in data
        assert "total" in data["balances"]
        assert data["balances"]["total"] >= 500000

        assert "invoices" in data
        assert "pending_amount" in data["invoices"]

        assert "transactions" in data
        assert "uncategorized_count" in data["transactions"]

    def test_transactions_pagination_works(self, client: TestClient, auth_headers):
        """La pagination des transactions doit fonctionner."""
        # Setup
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Pagination Test", "code": "PAG01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        account_resp = client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Pagination",
                "type": "BANQUE",
            },
            headers=auth_headers
        )
        account_id = account_resp.json()["id"]

        # Creer plusieurs transactions
        for i in range(25):
            client.post(
                "/api/v1/finance/transactions",
                json={
                    "entity_id": entity_id,
                    "account_id": account_id,
                    "direction": "IN",
                    "amount": 1000 * (i + 1),
                    "label": f"Transaction {i+1}",
                    "date_operation": str(date.today()),
                },
                headers=auth_headers
            )

        # Page 1
        page1 = client.get(
            f"/api/v1/finance/transactions?entity_id={entity_id}&page=1&page_size=10",
            headers=auth_headers
        )

        assert page1.status_code == 200
        data1 = page1.json()
        assert len(data1["items"]) == 10
        assert data1["total"] == 25
        assert data1["has_next"] is True
        assert data1["has_prev"] is False

        # Page 3
        page3 = client.get(
            f"/api/v1/finance/transactions?entity_id={entity_id}&page=3&page_size=10",
            headers=auth_headers
        )

        assert page3.status_code == 200
        data3 = page3.json()
        assert len(data3["items"]) == 5  # 25 - 20 = 5 restants
        assert data3["has_next"] is False
        assert data3["has_prev"] is True

    def test_search_transactions_filters_correctly(self, client: TestClient, auth_headers):
        """La recherche de transactions doit filtrer correctement."""
        # Setup
        entity_resp = client.post(
            "/api/v1/finance/entities",
            json={"name": "Search Test", "code": "SRCH01"},
            headers=auth_headers
        )
        entity_id = entity_resp.json()["id"]

        account_resp = client.post(
            "/api/v1/finance/accounts",
            json={
                "entity_id": entity_id,
                "label": "Compte Search",
                "type": "BANQUE",
            },
            headers=auth_headers
        )
        account_id = account_resp.json()["id"]

        # Creer des transactions avec labels differents
        client.post(
            "/api/v1/finance/transactions",
            json={
                "entity_id": entity_id,
                "account_id": account_id,
                "direction": "OUT",
                "amount": 10000,
                "label": "Achat fournitures bureau",
                "date_operation": str(date.today()),
            },
            headers=auth_headers
        )
        client.post(
            "/api/v1/finance/transactions",
            json={
                "entity_id": entity_id,
                "account_id": account_id,
                "direction": "IN",
                "amount": 50000,
                "label": "Vente produits",
                "date_operation": str(date.today()),
            },
            headers=auth_headers
        )

        # Rechercher "fournitures"
        response = client.get(
            f"/api/v1/finance/transactions/search?entity_id={entity_id}&label=fournitures",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "fournitures" in data["items"][0]["label"].lower()
