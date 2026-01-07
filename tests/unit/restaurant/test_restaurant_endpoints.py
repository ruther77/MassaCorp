"""
Tests unitaires pour les endpoints API Restaurant Domain.
Comprend tests d'INTERFACE (hasattr) et tests COMPORTEMENTAUX.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# =============================================================================
# Tests d'INTERFACE - Verifient l'existence des endpoints et schemas
# =============================================================================

class TestRestaurantRouterInterface:
    """Tests d'interface pour le router restaurant."""

    @pytest.mark.unit
    def test_router_exists(self):
        """Le router doit exister."""
        from app.api.v1.endpoints.restaurant import router

        assert router is not None

    @pytest.mark.unit
    def test_router_has_correct_prefix(self):
        """Le router doit avoir le prefix /restaurant."""
        from app.api.v1.endpoints.restaurant import router

        assert router.prefix == "/restaurant"

    @pytest.mark.unit
    def test_router_has_restaurant_tag(self):
        """Le router doit avoir le tag Restaurant."""
        from app.api.v1.endpoints.restaurant import router

        assert "Restaurant" in router.tags


class TestIngredientSchemasInterface:
    """Tests d'interface pour les schemas Ingredient."""

    @pytest.mark.unit
    def test_ingredient_create_schema_has_required_fields(self):
        """IngredientCreate doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import IngredientCreate

        fields = IngredientCreate.model_fields.keys()
        required = ["name", "unit"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_ingredient_response_schema_has_required_fields(self):
        """IngredientResponse doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import IngredientResponse

        fields = IngredientResponse.model_fields.keys()
        required = ["id", "name", "unit", "category", "prix_unitaire", "is_active"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_ingredient_update_schema_exists(self):
        """IngredientUpdate doit exister."""
        from app.api.v1.endpoints.restaurant import IngredientUpdate

        assert IngredientUpdate is not None


class TestPlatSchemasInterface:
    """Tests d'interface pour les schemas Plat."""

    @pytest.mark.unit
    def test_plat_create_schema_has_required_fields(self):
        """PlatCreate doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import PlatCreate

        fields = PlatCreate.model_fields.keys()
        required = ["name", "prix_vente"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_plat_response_schema_has_computed_fields(self):
        """PlatResponse doit avoir les champs calcules."""
        from app.api.v1.endpoints.restaurant import PlatResponse

        fields = PlatResponse.model_fields.keys()
        computed = ["cout_total", "food_cost_ratio", "is_profitable"]
        for field in computed:
            assert field in fields, f"Missing computed field: {field}"

    @pytest.mark.unit
    def test_plat_detail_response_has_ingredients(self):
        """PlatDetailResponse doit avoir la liste d'ingredients."""
        from app.api.v1.endpoints.restaurant import PlatDetailResponse

        fields = PlatDetailResponse.model_fields.keys()
        assert "ingredients" in fields

    @pytest.mark.unit
    def test_plat_ingredient_input_schema_exists(self):
        """PlatIngredientInput doit exister."""
        from app.api.v1.endpoints.restaurant import PlatIngredientInput

        fields = PlatIngredientInput.model_fields.keys()
        required = ["ingredient_id", "quantite"]
        for field in required:
            assert field in fields, f"Missing field: {field}"


class TestStockSchemasInterface:
    """Tests d'interface pour les schemas Stock."""

    @pytest.mark.unit
    def test_stock_response_schema_has_required_fields(self):
        """StockResponse doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import StockResponse

        fields = StockResponse.model_fields.keys()
        required = ["id", "ingredient_id", "quantity", "valeur_stock", "is_low_stock"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_stock_movement_create_schema_exists(self):
        """StockMovementCreate doit exister."""
        from app.api.v1.endpoints.restaurant import StockMovementCreate

        fields = StockMovementCreate.model_fields.keys()
        required = ["ingredient_id", "quantite", "movement_type"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_stock_adjustment_schema_exists(self):
        """StockAdjustment doit exister."""
        from app.api.v1.endpoints.restaurant import StockAdjustment

        fields = StockAdjustment.model_fields.keys()
        required = ["ingredient_id", "nouvelle_quantite"]
        for field in required:
            assert field in fields, f"Missing field: {field}"


class TestConsumptionSchemasInterface:
    """Tests d'interface pour les schemas Consumption."""

    @pytest.mark.unit
    def test_consumption_create_schema_has_required_fields(self):
        """ConsumptionCreate doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import ConsumptionCreate

        fields = ConsumptionCreate.model_fields.keys()
        required = ["plat_id"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_consumption_response_schema_has_required_fields(self):
        """ConsumptionResponse doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import ConsumptionResponse

        fields = ConsumptionResponse.model_fields.keys()
        required = ["id", "plat_id", "type", "quantite", "prix_vente", "cout", "date"]
        for field in required:
            assert field in fields, f"Missing field: {field}"


class TestChargeSchemasInterface:
    """Tests d'interface pour les schemas Charge."""

    @pytest.mark.unit
    def test_charge_create_schema_has_required_fields(self):
        """ChargeCreate doit avoir les champs requis."""
        from app.api.v1.endpoints.restaurant import ChargeCreate

        fields = ChargeCreate.model_fields.keys()
        required = ["name", "charge_type", "montant"]
        for field in required:
            assert field in fields, f"Missing field: {field}"

    @pytest.mark.unit
    def test_charge_response_schema_has_computed_fields(self):
        """ChargeResponse doit avoir le champ montant_mensuel."""
        from app.api.v1.endpoints.restaurant import ChargeResponse

        fields = ChargeResponse.model_fields.keys()
        assert "montant_mensuel" in fields


class TestDependenciesInterface:
    """Tests d'interface pour les dependencies."""

    @pytest.mark.unit
    def test_get_ingredient_service_exists(self):
        """get_ingredient_service doit exister."""
        from app.api.v1.endpoints.restaurant import get_ingredient_service

        assert callable(get_ingredient_service)

    @pytest.mark.unit
    def test_get_plat_service_exists(self):
        """get_plat_service doit exister."""
        from app.api.v1.endpoints.restaurant import get_plat_service

        assert callable(get_plat_service)

    @pytest.mark.unit
    def test_get_stock_service_exists(self):
        """get_stock_service doit exister."""
        from app.api.v1.endpoints.restaurant import get_stock_service

        assert callable(get_stock_service)

    @pytest.mark.unit
    def test_get_consumption_service_exists(self):
        """get_consumption_service doit exister."""
        from app.api.v1.endpoints.restaurant import get_consumption_service

        assert callable(get_consumption_service)

    @pytest.mark.unit
    def test_get_charge_service_exists(self):
        """get_charge_service doit exister."""
        from app.api.v1.endpoints.restaurant import get_charge_service

        assert callable(get_charge_service)


# =============================================================================
# Tests COMPORTEMENTAUX - Validation des schemas
# =============================================================================

class TestIngredientCreateValidation:
    """Tests de validation pour IngredientCreate."""

    @pytest.mark.unit
    def test_name_cannot_be_empty(self):
        """name ne peut pas etre vide."""
        from app.api.v1.endpoints.restaurant import IngredientCreate
        from app.models.restaurant.ingredient import RestaurantUnit
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IngredientCreate(name="", unit=RestaurantUnit.KILOGRAMME)

    @pytest.mark.unit
    def test_prix_unitaire_cannot_be_negative(self):
        """prix_unitaire ne peut pas etre negatif."""
        from app.api.v1.endpoints.restaurant import IngredientCreate
        from app.models.restaurant.ingredient import RestaurantUnit
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            IngredientCreate(
                name="Test",
                unit=RestaurantUnit.KILOGRAMME,
                prix_unitaire=-100
            )

    @pytest.mark.unit
    def test_valid_ingredient_create(self):
        """Un IngredientCreate valide doit etre accepte."""
        from app.api.v1.endpoints.restaurant import IngredientCreate
        from app.models.restaurant.ingredient import RestaurantUnit

        ingredient = IngredientCreate(
            name="Tomate",
            unit=RestaurantUnit.KILOGRAMME,
            prix_unitaire=350,
        )

        assert ingredient.name == "Tomate"
        assert ingredient.unit == RestaurantUnit.KILOGRAMME
        assert ingredient.prix_unitaire == 350


class TestPlatCreateValidation:
    """Tests de validation pour PlatCreate."""

    @pytest.mark.unit
    def test_prix_vente_must_be_positive(self):
        """prix_vente doit etre positif."""
        from app.api.v1.endpoints.restaurant import PlatCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlatCreate(name="Test", prix_vente=0)

    @pytest.mark.unit
    def test_name_cannot_be_empty(self):
        """name ne peut pas etre vide."""
        from app.api.v1.endpoints.restaurant import PlatCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PlatCreate(name="", prix_vente=1500)

    @pytest.mark.unit
    def test_valid_plat_with_ingredients(self):
        """Un PlatCreate avec ingredients doit etre accepte."""
        from app.api.v1.endpoints.restaurant import PlatCreate, PlatIngredientInput

        plat = PlatCreate(
            name="Salade Nicoise",
            prix_vente=1200,
            ingredients=[
                PlatIngredientInput(ingredient_id=1, quantite=Decimal("0.3")),
                PlatIngredientInput(ingredient_id=2, quantite=Decimal("0.1")),
            ]
        )

        assert plat.name == "Salade Nicoise"
        assert len(plat.ingredients) == 2


class TestStockMovementCreateValidation:
    """Tests de validation pour StockMovementCreate."""

    @pytest.mark.unit
    def test_quantite_must_be_positive(self):
        """quantite doit etre positive."""
        from app.api.v1.endpoints.restaurant import StockMovementCreate
        from app.models.restaurant.stock import RestaurantStockMovementType
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StockMovementCreate(
                ingredient_id=1,
                quantite=Decimal("0"),
                movement_type=RestaurantStockMovementType.ENTREE
            )

    @pytest.mark.unit
    def test_valid_stock_movement(self):
        """Un StockMovementCreate valide doit etre accepte."""
        from app.api.v1.endpoints.restaurant import StockMovementCreate
        from app.models.restaurant.stock import RestaurantStockMovementType

        movement = StockMovementCreate(
            ingredient_id=1,
            quantite=Decimal("5.5"),
            movement_type=RestaurantStockMovementType.ENTREE,
            cout_unitaire=350,
        )

        assert movement.ingredient_id == 1
        assert movement.quantite == Decimal("5.5")


class TestChargeCreateValidation:
    """Tests de validation pour ChargeCreate."""

    @pytest.mark.unit
    def test_montant_must_be_positive(self):
        """montant doit etre positif."""
        from app.api.v1.endpoints.restaurant import ChargeCreate
        from app.models.restaurant.charge import RestaurantChargeType
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChargeCreate(
                name="Test",
                charge_type=RestaurantChargeType.LOYER,
                montant=0
            )

    @pytest.mark.unit
    def test_valid_charge_create(self):
        """Un ChargeCreate valide doit etre accepte."""
        from app.api.v1.endpoints.restaurant import ChargeCreate
        from app.models.restaurant.charge import (
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )

        charge = ChargeCreate(
            name="Loyer",
            charge_type=RestaurantChargeType.LOYER,
            montant=150000,
            frequency=RestaurantChargeFrequency.MENSUEL,
        )

        assert charge.name == "Loyer"
        assert charge.montant == 150000


class TestConsumptionCreateValidation:
    """Tests de validation pour ConsumptionCreate."""

    @pytest.mark.unit
    def test_quantite_must_be_at_least_one(self):
        """quantite doit etre >= 1."""
        from app.api.v1.endpoints.restaurant import ConsumptionCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ConsumptionCreate(plat_id=1, quantite=0)

    @pytest.mark.unit
    def test_valid_consumption_create(self):
        """Un ConsumptionCreate valide doit etre accepte."""
        from app.api.v1.endpoints.restaurant import ConsumptionCreate

        consumption = ConsumptionCreate(
            plat_id=1,
            quantite=3,
            prix_vente=1200,
        )

        assert consumption.plat_id == 1
        assert consumption.quantite == 3
        assert consumption.prix_vente == 1200


# =============================================================================
# Tests de l'enregistrement du router
# =============================================================================

class TestRouterRegistration:
    """Tests pour verifier l'enregistrement du router."""

    @pytest.mark.unit
    def test_restaurant_router_is_registered(self):
        """Le router restaurant doit etre enregistre dans api_router."""
        from app.api.v1.router import api_router

        # Verifie que le prefix /restaurant est present
        prefixes = [route.path for route in api_router.routes]
        restaurant_routes = [p for p in prefixes if "/restaurant" in p]

        assert len(restaurant_routes) > 0, "No restaurant routes registered"

    @pytest.mark.unit
    def test_ingredient_endpoints_exist(self):
        """Les endpoints ingredient doivent exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/ingredients" in p for p in paths)

    @pytest.mark.unit
    def test_plat_endpoints_exist(self):
        """Les endpoints plat doivent exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/plats" in p for p in paths)

    @pytest.mark.unit
    def test_stock_endpoints_exist(self):
        """Les endpoints stock doivent exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/stock" in p for p in paths)

    @pytest.mark.unit
    def test_consumption_endpoints_exist(self):
        """Les endpoints consumption doivent exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/consumptions" in p for p in paths)

    @pytest.mark.unit
    def test_charge_endpoints_exist(self):
        """Les endpoints charge doivent exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/charges" in p for p in paths)

    @pytest.mark.unit
    def test_dashboard_endpoint_exists(self):
        """L'endpoint dashboard doit exister."""
        from app.api.v1.router import api_router

        paths = [route.path for route in api_router.routes]

        assert any("/restaurant/dashboard" in p for p in paths)
