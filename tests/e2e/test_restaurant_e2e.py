"""
Tests E2E pour les endpoints Restaurant.
Verifie le comportement complet de l'API Restaurant.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestRestaurantIngredientsE2E:
    """Tests E2E pour les ingredients restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    def test_create_ingredient_returns_201(self, client: TestClient, auth_headers):
        """Creer un ingredient doit retourner 201."""
        response = client.post(
            "/api/v1/restaurant/ingredients",
            json={
                "name": "Tomate E2E",
                "unit": "KG",
                "category": "LEGUME",
                "prix_unitaire": 350,
                "seuil_alerte": 5.0,
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Tomate E2E"
        assert data["unit"] == "KG"
        assert data["prix_unitaire"] == 350
        assert data["is_active"] is True

    def test_create_ingredient_rejects_duplicate_name(self, client: TestClient, auth_headers):
        """Creer un ingredient avec nom existant doit retourner 409."""
        # Premiere creation
        client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "Duplicata Test", "unit": "KG"},
            headers=auth_headers
        )

        # Tentative de doublon
        response = client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "Duplicata Test", "unit": "G"},
            headers=auth_headers
        )

        assert response.status_code == 409

    def test_list_ingredients_returns_active_only(self, client: TestClient, auth_headers):
        """Lister les ingredients doit retourner uniquement les actifs."""
        response = client.get(
            "/api/v1/restaurant/ingredients",
            headers=auth_headers
        )

        assert response.status_code == 200
        ingredients = response.json()
        for ing in ingredients:
            assert ing["is_active"] is True

    def test_update_ingredient_modifies_price(self, client: TestClient, auth_headers):
        """Modifier un ingredient doit mettre a jour le prix."""
        # Creer l'ingredient
        create_resp = client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "Ingredient Prix Test", "unit": "KG", "prix_unitaire": 100},
            headers=auth_headers
        )
        ing_id = create_resp.json()["id"]

        # Modifier le prix
        update_resp = client.patch(
            f"/api/v1/restaurant/ingredients/{ing_id}",
            json={"prix_unitaire": 250},
            headers=auth_headers
        )

        assert update_resp.status_code == 200
        assert update_resp.json()["prix_unitaire"] == 250

    def test_deactivate_ingredient(self, client: TestClient, auth_headers):
        """Desactiver un ingredient doit fonctionner."""
        # Creer l'ingredient
        create_resp = client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "A Desactiver", "unit": "U"},
            headers=auth_headers
        )
        ing_id = create_resp.json()["id"]

        # Desactiver
        delete_resp = client.delete(
            f"/api/v1/restaurant/ingredients/{ing_id}",
            headers=auth_headers
        )

        assert delete_resp.status_code == 204

    def test_search_ingredients(self, client: TestClient, auth_headers):
        """Rechercher des ingredients doit fonctionner."""
        # Creer quelques ingredients
        client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "Oignon Jaune", "unit": "KG"},
            headers=auth_headers
        )
        client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": "Oignon Rouge", "unit": "KG"},
            headers=auth_headers
        )

        # Rechercher
        response = client.get(
            "/api/v1/restaurant/ingredients/search?q=Oignon",
            headers=auth_headers
        )

        assert response.status_code == 200
        results = response.json()
        assert len(results) >= 2
        for r in results:
            assert "Oignon" in r["name"]


@pytest.mark.e2e
class TestRestaurantPlatsE2E:
    """Tests E2E pour les plats restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    @pytest.fixture
    def ingredient_id(self, client: TestClient, auth_headers):
        """Cree un ingredient de test et retourne son ID."""
        resp = client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": f"Ing Plat Test {date.today()}", "unit": "KG", "prix_unitaire": 400},
            headers=auth_headers
        )
        return resp.json()["id"]

    def test_create_plat_returns_201(self, client: TestClient, auth_headers):
        """Creer un plat doit retourner 201."""
        response = client.post(
            "/api/v1/restaurant/plats",
            json={
                "name": "Salade E2E",
                "prix_vente": 1200,
                "category": "ENTREE",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Salade E2E"
        assert data["prix_vente"] == 1200
        assert data["is_active"] is True

    def test_create_plat_with_ingredients(self, client: TestClient, auth_headers, ingredient_id):
        """Creer un plat avec ingredients doit fonctionner."""
        response = client.post(
            "/api/v1/restaurant/plats",
            json={
                "name": "Plat Compose E2E",
                "prix_vente": 1500,
                "ingredients": [
                    {"ingredient_id": ingredient_id, "quantite": "0.3"}
                ]
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["cout_total"] > 0

    def test_create_plat_rejects_zero_price(self, client: TestClient, auth_headers):
        """Creer un plat avec prix 0 doit echouer."""
        response = client.post(
            "/api/v1/restaurant/plats",
            json={"name": "Plat Gratuit", "prix_vente": 0},
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_get_plat_with_ingredients(self, client: TestClient, auth_headers, ingredient_id):
        """Recuperer un plat doit inclure ses ingredients."""
        # Creer le plat
        create_resp = client.post(
            "/api/v1/restaurant/plats",
            json={
                "name": "Plat Detail Test",
                "prix_vente": 1800,
                "ingredients": [
                    {"ingredient_id": ingredient_id, "quantite": "0.5"}
                ]
            },
            headers=auth_headers
        )
        plat_id = create_resp.json()["id"]

        # Recuperer le detail
        response = client.get(
            f"/api/v1/restaurant/plats/{plat_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "ingredients" in data
        assert len(data["ingredients"]) == 1

    def test_set_plat_ingredients_replaces_all(self, client: TestClient, auth_headers, ingredient_id):
        """Definir les ingredients doit remplacer tous les existants."""
        # Creer le plat
        create_resp = client.post(
            "/api/v1/restaurant/plats",
            json={"name": "Plat Set Ingredients", "prix_vente": 1500},
            headers=auth_headers
        )
        plat_id = create_resp.json()["id"]

        # Definir les ingredients
        response = client.put(
            f"/api/v1/restaurant/plats/{plat_id}/ingredients",
            json=[
                {"ingredient_id": ingredient_id, "quantite": "0.4"}
            ],
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["ingredients"]) == 1

    def test_food_cost_ratio_calculated(self, client: TestClient, auth_headers, ingredient_id):
        """Le food cost ratio doit etre calcule."""
        # Creer un plat avec ingredient
        response = client.post(
            "/api/v1/restaurant/plats",
            json={
                "name": "Plat Food Cost",
                "prix_vente": 1000,  # 10 EUR
                "ingredients": [
                    {"ingredient_id": ingredient_id, "quantite": "0.75"}  # 0.75 * 4 EUR = 3 EUR = 30%
                ]
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        # Le food cost devrait etre environ 30%
        assert data["food_cost_ratio"] >= 0
        assert "is_profitable" in data


@pytest.mark.e2e
class TestRestaurantStockE2E:
    """Tests E2E pour le stock restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    @pytest.fixture
    def ingredient_id(self, client: TestClient, auth_headers):
        """Cree un ingredient de test et retourne son ID."""
        resp = client.post(
            "/api/v1/restaurant/ingredients",
            json={"name": f"Ing Stock Test {date.today()}", "unit": "KG", "prix_unitaire": 500},
            headers=auth_headers
        )
        return resp.json()["id"]

    def test_add_stock_entry(self, client: TestClient, auth_headers, ingredient_id):
        """Ajouter du stock doit fonctionner."""
        response = client.post(
            "/api/v1/restaurant/stock/movement",
            json={
                "ingredient_id": ingredient_id,
                "quantite": "10.0",
                "movement_type": "ENTREE",
                "cout_unitaire": 450,
                "reference": "FAC-001",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        assert "id" in response.json()

    def test_stock_value_calculated(self, client: TestClient, auth_headers, ingredient_id):
        """La valeur du stock doit etre calculee."""
        # Ajouter du stock
        client.post(
            "/api/v1/restaurant/stock/movement",
            json={
                "ingredient_id": ingredient_id,
                "quantite": "5.0",
                "movement_type": "ENTREE",
                "cout_unitaire": 600,
            },
            headers=auth_headers
        )

        # Verifier le stock
        response = client.get(
            f"/api/v1/restaurant/stock/{ingredient_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert float(data["quantity"]) >= 5.0
        assert data["valeur_stock"] > 0

    def test_stock_adjust_inventory(self, client: TestClient, auth_headers, ingredient_id):
        """Ajuster le stock (inventaire) doit fonctionner."""
        # D'abord ajouter du stock
        client.post(
            "/api/v1/restaurant/stock/movement",
            json={
                "ingredient_id": ingredient_id,
                "quantite": "20.0",
                "movement_type": "ENTREE",
            },
            headers=auth_headers
        )

        # Ajuster a une nouvelle valeur
        response = client.post(
            "/api/v1/restaurant/stock/adjust",
            json={
                "ingredient_id": ingredient_id,
                "nouvelle_quantite": "15.5",
                "notes": "Inventaire physique",
            },
            headers=auth_headers
        )

        assert response.status_code == 201

        # Verifier la nouvelle quantite
        stock_resp = client.get(
            f"/api/v1/restaurant/stock/{ingredient_id}",
            headers=auth_headers
        )
        assert float(stock_resp.json()["quantity"]) == 15.5

    def test_total_stock_value(self, client: TestClient, auth_headers):
        """La valeur totale du stock doit etre calculee."""
        response = client.get(
            "/api/v1/restaurant/stock/value",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "total_value" in response.json()


@pytest.mark.e2e
class TestRestaurantConsumptionsE2E:
    """Tests E2E pour les consommations restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    @pytest.fixture
    def plat_id(self, client: TestClient, auth_headers):
        """Cree un plat de test et retourne son ID."""
        resp = client.post(
            "/api/v1/restaurant/plats",
            json={"name": f"Plat Conso Test {date.today()}", "prix_vente": 1500},
            headers=auth_headers
        )
        return resp.json()["id"]

    def test_record_sale(self, client: TestClient, auth_headers, plat_id):
        """Enregistrer une vente doit fonctionner."""
        response = client.post(
            "/api/v1/restaurant/consumptions/sale",
            json={
                "plat_id": plat_id,
                "quantite": 2,
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        assert "id" in response.json()

    def test_record_loss(self, client: TestClient, auth_headers, plat_id):
        """Enregistrer une perte doit fonctionner."""
        response = client.post(
            "/api/v1/restaurant/consumptions/loss",
            json={
                "plat_id": plat_id,
                "quantite": 1,
                "notes": "Plat brule",
            },
            headers=auth_headers
        )

        assert response.status_code == 201

    def test_record_staff_meal(self, client: TestClient, auth_headers, plat_id):
        """Enregistrer un repas staff doit fonctionner."""
        response = client.post(
            "/api/v1/restaurant/consumptions/staff-meal",
            json={
                "plat_id": plat_id,
                "quantite": 1,
            },
            headers=auth_headers
        )

        assert response.status_code == 201

    def test_daily_summary(self, client: TestClient, auth_headers, plat_id):
        """Le resume journalier doit fonctionner."""
        # Enregistrer quelques ventes
        client.post(
            "/api/v1/restaurant/consumptions/sale",
            json={"plat_id": plat_id, "quantite": 3},
            headers=auth_headers
        )

        # Recuperer le resume
        today = str(date.today())
        response = client.get(
            f"/api/v1/restaurant/consumptions/summary?target_date={today}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "total_cost" in data
        assert "margin" in data
        assert "ventes" in data

    def test_best_sellers(self, client: TestClient, auth_headers, plat_id):
        """Les meilleures ventes doivent fonctionner."""
        # Enregistrer des ventes
        for _ in range(5):
            client.post(
                "/api/v1/restaurant/consumptions/sale",
                json={"plat_id": plat_id, "quantite": 1},
                headers=auth_headers
            )

        today = str(date.today())
        response = client.get(
            f"/api/v1/restaurant/consumptions/best-sellers?start_date={today}&end_date={today}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.e2e
class TestRestaurantChargesE2E:
    """Tests E2E pour les charges restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    def test_create_charge_returns_201(self, client: TestClient, auth_headers):
        """Creer une charge doit retourner 201."""
        response = client.post(
            "/api/v1/restaurant/charges",
            json={
                "name": "Loyer E2E",
                "charge_type": "LOYER",
                "montant": 150000,
                "frequency": "MENSUEL",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Loyer E2E"
        assert data["montant"] == 150000
        assert data["montant_mensuel"] == 150000

    def test_create_quarterly_charge(self, client: TestClient, auth_headers):
        """Creer une charge trimestrielle calcule le mensuel."""
        response = client.post(
            "/api/v1/restaurant/charges",
            json={
                "name": "Assurance E2E",
                "charge_type": "ASSURANCE",
                "montant": 90000,  # 900 EUR / trimestre
                "frequency": "TRIMESTRIEL",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        # 90000 / 3 = 30000
        assert data["montant_mensuel"] == 30000

    def test_create_annual_charge(self, client: TestClient, auth_headers):
        """Creer une charge annuelle calcule le mensuel."""
        response = client.post(
            "/api/v1/restaurant/charges",
            json={
                "name": "Licence E2E",
                "charge_type": "AUTRES",
                "montant": 1200000,  # 12000 EUR / an
                "frequency": "ANNUEL",
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        # 1200000 / 12 = 100000
        assert data["montant_mensuel"] == 100000

    def test_charges_summary(self, client: TestClient, auth_headers):
        """Le resume des charges doit fonctionner."""
        # Creer des charges
        client.post(
            "/api/v1/restaurant/charges",
            json={"name": "Charge Summary 1", "charge_type": "LOYER", "montant": 100000},
            headers=auth_headers
        )
        client.post(
            "/api/v1/restaurant/charges",
            json={"name": "Charge Summary 2", "charge_type": "ENERGIE", "montant": 50000},
            headers=auth_headers
        )

        response = client.get(
            "/api/v1/restaurant/charges/summary",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "by_type" in data
        assert "total_mensuel" in data
        assert "total_annuel" in data

    def test_deactivate_charge(self, client: TestClient, auth_headers):
        """Desactiver une charge doit fonctionner."""
        # Creer la charge
        create_resp = client.post(
            "/api/v1/restaurant/charges",
            json={"name": "A Supprimer", "charge_type": "AUTRES", "montant": 10000},
            headers=auth_headers
        )
        charge_id = create_resp.json()["id"]

        # Desactiver
        response = client.delete(
            f"/api/v1/restaurant/charges/{charge_id}",
            headers=auth_headers
        )

        assert response.status_code == 204


@pytest.mark.e2e
class TestRestaurantDashboardE2E:
    """Tests E2E pour le dashboard restaurant."""

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
            pytest.skip(f"Impossible de s'authentifier: {response.status_code}")
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}

    def test_dashboard_returns_kpis(self, client: TestClient, auth_headers):
        """Le dashboard doit retourner les KPIs."""
        response = client.get(
            "/api/v1/restaurant/dashboard",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verifier la structure
        assert "date" in data
        assert "stock" in data
        assert "total_value" in data["stock"]
        assert "alerts_count" in data["stock"]

        assert "charges" in data
        assert "monthly_total" in data["charges"]

        assert "daily" in data
        assert "revenue" in data["daily"]
        assert "cost" in data["daily"]
        assert "margin" in data["daily"]

    def test_dashboard_with_specific_date(self, client: TestClient, auth_headers):
        """Le dashboard avec date specifique doit fonctionner."""
        yesterday = str(date.today() - timedelta(days=1))
        response = client.get(
            f"/api/v1/restaurant/dashboard?target_date={yesterday}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == yesterday
