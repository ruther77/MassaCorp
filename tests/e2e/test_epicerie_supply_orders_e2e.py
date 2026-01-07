"""
Tests E2E pour les commandes fournisseurs epicerie.

Ces tests verifient les workflows complets:
1. Lister les commandes
2. Creer une commande
3. Confirmer/Expedier/Recevoir une commande
4. Annuler une commande
5. Gestion des lignes de commande
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Client de test FastAPI."""
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Obtient un token d'authentification admin."""
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

    if response.json().get("mfa_required"):
        pytest.skip("Admin requires MFA, cannot authenticate in E2E test")

    pytest.skip(f"Cannot authenticate admin: {response.status_code}")


@pytest.fixture
def test_vendor(client, admin_token):
    """Cree un fournisseur de test pour les commandes."""
    # D'abord, creer une entite finance si elle n'existe pas
    entity_response = client.get(
        "/api/v1/finance/entities",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    if entity_response.status_code == 200:
        entities = entity_response.json()
        if entities:
            entity_id = entities[0]["id"]
        else:
            # Creer une entite
            create_entity = client.post(
                "/api/v1/finance/entities",
                json={
                    "name": "Test Entity",
                    "code": "TEST",
                    "currency": "EUR"
                },
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if create_entity.status_code in [200, 201]:
                entity_id = create_entity.json()["id"]
            else:
                pytest.skip("Cannot create test entity")
    else:
        pytest.skip("Cannot get entities")

    # Creer un fournisseur
    vendor_response = client.post(
        "/api/v1/finance/vendors",
        json={
            "entity_id": entity_id,
            "name": "Test Vendor E2E",
            "code": "TVE2E",
            "is_active": True
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    if vendor_response.status_code in [200, 201]:
        return vendor_response.json()

    # Si le vendor existe deja, on le recupere
    if vendor_response.status_code == 400:
        # Essayer de le recuperer par entite
        get_vendors = client.get(
            f"/api/v1/finance/vendors?entity_id={entity_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if get_vendors.status_code == 200:
            vendors = get_vendors.json()
            if vendors:
                return vendors[0]

    pytest.skip("Cannot create or get test vendor")


class TestSupplyOrdersListE2E:
    """Scenario E2E: Lister les commandes fournisseurs."""

    def test_list_orders_requires_auth(self, client):
        """E2E: La liste des commandes requiert authentification."""
        response = client.get("/api/v1/epicerie/orders")
        assert response.status_code == 401

    def test_list_orders_with_auth(self, client, admin_token):
        """E2E: Un admin peut lister les commandes."""
        response = client.get(
            "/api/v1/epicerie/orders",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    def test_list_orders_with_pagination(self, client, admin_token):
        """E2E: La pagination fonctionne correctement."""
        response = client.get(
            "/api/v1/epicerie/orders?page=1&page_size=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 10

    def test_list_orders_filter_by_status(self, client, admin_token):
        """E2E: Filtrer les commandes par statut."""
        response = client.get(
            "/api/v1/epicerie/orders?statut=en_attente",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Toutes les commandes retournees doivent avoir ce statut
        for order in data["data"]:
            assert order["statut"] == "en_attente"


class TestSupplyOrdersCRUDE2E:
    """Scenario E2E: CRUD complet commandes fournisseurs."""

    def test_create_order_requires_vendor(self, client, admin_token):
        """E2E: La creation requiert un fournisseur valide."""
        response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": 999999,  # ID inexistant
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 400
        assert "fournisseur" in response.json().get("message", "").lower()

    def test_create_order_basic(self, client, admin_token, test_vendor):
        """E2E: Creer une commande basique."""
        response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat(),
                "date_livraison_prevue": (date.today() + timedelta(days=3)).isoformat(),
                "notes": "Test E2E commande"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        data = response.json()["data"]

        assert data["vendor_id"] == test_vendor["id"]
        assert data["statut"] == "en_attente"
        assert data["notes"] == "Test E2E commande"
        assert "id" in data

        return data["id"]

    def test_create_order_with_lines(self, client, admin_token, test_vendor):
        """E2E: Creer une commande avec des lignes."""
        response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat(),
                "lines": [
                    {
                        "designation": "Produit Test 1",
                        "quantity": 10,
                        "prix_unitaire": 500  # 5.00 EUR en centimes
                    },
                    {
                        "designation": "Produit Test 2",
                        "quantity": 5,
                        "prix_unitaire": 1000  # 10.00 EUR en centimes
                    }
                ]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 201
        data = response.json()["data"]

        assert len(data["lines"]) == 2
        assert data["nb_lignes"] == 2
        # Total: 10*500 + 5*1000 = 5000 + 5000 = 10000 centimes
        assert data["montant_ht"] == 10000

    def test_get_order_detail(self, client, admin_token, test_vendor):
        """E2E: Recuperer le detail d'une commande."""
        # Creer une commande d'abord
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_id = create_response.json()["data"]["id"]

        # Recuperer le detail
        response = client.get(
            f"/api/v1/epicerie/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()["data"]

        assert data["id"] == order_id
        assert "lines" in data
        assert "vendor" in data

    def test_delete_order_only_pending(self, client, admin_token, test_vendor):
        """E2E: Seules les commandes en attente peuvent etre supprimees."""
        # Creer une commande
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_id = create_response.json()["data"]["id"]

        # Supprimer - devrait reussir car en_attente
        response = client.delete(
            f"/api/v1/epicerie/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 204

        # Verifier que la commande n'existe plus
        get_response = client.get(
            f"/api/v1/epicerie/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert get_response.status_code == 404


class TestSupplyOrdersWorkflowE2E:
    """Scenario E2E: Workflow complet d'une commande."""

    def test_full_order_workflow(self, client, admin_token, test_vendor):
        """E2E: Workflow complet: creation -> confirmation -> expedition -> reception."""
        # 1. Creer
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat(),
                "lines": [
                    {
                        "designation": "Produit Workflow",
                        "quantity": 5,
                        "prix_unitaire": 1000
                    }
                ]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert create_response.status_code == 201
        order_id = create_response.json()["data"]["id"]
        assert create_response.json()["data"]["statut"] == "en_attente"

        # 2. Confirmer
        confirm_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/confirm",
            json={
                "date_livraison_prevue": (date.today() + timedelta(days=2)).isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert confirm_response.status_code == 200
        assert confirm_response.json()["data"]["statut"] == "confirmee"

        # 3. Expedier
        ship_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/ship",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert ship_response.status_code == 200
        assert ship_response.json()["data"]["statut"] == "expediee"

        # 4. Recevoir
        receive_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/receive",
            json={
                "date_livraison_reelle": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert receive_response.status_code == 200
        assert receive_response.json()["data"]["statut"] == "livree"
        assert receive_response.json()["data"]["date_livraison_reelle"] == date.today().isoformat()

    def test_cancel_order(self, client, admin_token, test_vendor):
        """E2E: Annuler une commande."""
        # Creer une commande
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_id = create_response.json()["data"]["id"]

        # Confirmer
        client.post(
            f"/api/v1/epicerie/orders/{order_id}/confirm",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Annuler
        cancel_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/cancel",
            json={"raison": "Test annulation E2E"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert cancel_response.status_code == 200
        assert cancel_response.json()["data"]["statut"] == "annulee"

    def test_cannot_cancel_delivered_order(self, client, admin_token, test_vendor):
        """E2E: Impossible d'annuler une commande deja livree."""
        # Creer et livrer une commande
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_id = create_response.json()["data"]["id"]

        # Confirmer -> Expedier -> Recevoir
        client.post(f"/api/v1/epicerie/orders/{order_id}/confirm", json={},
                    headers={"Authorization": f"Bearer {admin_token}"})
        client.post(f"/api/v1/epicerie/orders/{order_id}/ship", json={},
                    headers={"Authorization": f"Bearer {admin_token}"})
        client.post(f"/api/v1/epicerie/orders/{order_id}/receive",
                    json={"date_livraison_reelle": date.today().isoformat()},
                    headers={"Authorization": f"Bearer {admin_token}"})

        # Essayer d'annuler - doit echouer
        cancel_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/cancel",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert cancel_response.status_code == 400


class TestSupplyOrderLinesE2E:
    """Scenario E2E: Gestion des lignes de commande."""

    def test_add_line_to_order(self, client, admin_token, test_vendor):
        """E2E: Ajouter une ligne a une commande existante."""
        # Creer une commande sans lignes
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat()
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_id = create_response.json()["data"]["id"]

        # Ajouter une ligne
        add_line_response = client.post(
            f"/api/v1/epicerie/orders/{order_id}/lines",
            json={
                "designation": "Nouveau Produit",
                "quantity": 3,
                "prix_unitaire": 750
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert add_line_response.status_code == 201
        line_data = add_line_response.json()["data"]

        assert line_data["designation"] == "Nouveau Produit"
        assert line_data["quantity"] == 3
        assert line_data["prix_unitaire"] == 750
        assert line_data["montant_ligne"] == 2250  # 3 * 750

    def test_update_line(self, client, admin_token, test_vendor):
        """E2E: Modifier une ligne de commande."""
        # Creer une commande avec une ligne
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat(),
                "lines": [
                    {
                        "designation": "Produit Original",
                        "quantity": 2,
                        "prix_unitaire": 500
                    }
                ]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_data = create_response.json()["data"]
        order_id = order_data["id"]
        line_id = order_data["lines"][0]["id"]

        # Modifier la ligne
        update_response = client.put(
            f"/api/v1/epicerie/orders/{order_id}/lines/{line_id}",
            json={
                "quantity": 5,
                "prix_unitaire": 600
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert update_response.status_code == 200
        line_data = update_response.json()["data"]

        assert line_data["quantity"] == 5
        assert line_data["prix_unitaire"] == 600
        assert line_data["montant_ligne"] == 3000  # 5 * 600

    def test_delete_line(self, client, admin_token, test_vendor):
        """E2E: Supprimer une ligne de commande."""
        # Creer une commande avec une ligne
        create_response = client.post(
            "/api/v1/epicerie/orders",
            json={
                "vendor_id": test_vendor["id"],
                "date_commande": date.today().isoformat(),
                "lines": [
                    {
                        "designation": "Produit a Supprimer",
                        "quantity": 1,
                        "prix_unitaire": 100
                    }
                ]
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        if create_response.status_code != 201:
            pytest.skip("Cannot create test order")

        order_data = create_response.json()["data"]
        order_id = order_data["id"]
        line_id = order_data["lines"][0]["id"]

        # Supprimer la ligne
        delete_response = client.delete(
            f"/api/v1/epicerie/orders/{order_id}/lines/{line_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert delete_response.status_code == 204

        # Verifier que la commande n'a plus de lignes
        get_response = client.get(
            f"/api/v1/epicerie/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert get_response.status_code == 200
        assert len(get_response.json()["data"]["lines"]) == 0
