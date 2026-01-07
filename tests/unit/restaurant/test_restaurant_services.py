"""
Tests unitaires pour les services Restaurant Domain.
Comprend tests d'INTERFACE (hasattr) et tests COMPORTEMENTAUX.
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch


# =============================================================================
# Tests d'INTERFACE - Verifient l'existence des methodes
# =============================================================================

class TestRestaurantIngredientServiceInterface:
    """Tests d'interface pour RestaurantIngredientService."""

    @pytest.mark.unit
    def test_service_has_required_methods(self):
        """Le service doit avoir les methodes requises."""
        from app.services.restaurant.ingredient import RestaurantIngredientService

        required_methods = [
            "create_ingredient",
            "get_ingredient",
            "get_active_ingredients",
            "get_ingredients_by_category",
            "search_ingredients",
            "update_ingredient",
            "update_price",
            "deactivate_ingredient",
            "get_low_stock_ingredients",
        ]
        for method in required_methods:
            assert hasattr(RestaurantIngredientService, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_service_has_init_with_repos(self):
        """Le service doit accepter les repositories dans __init__."""
        from app.services.restaurant.ingredient import RestaurantIngredientService
        import inspect

        sig = inspect.signature(RestaurantIngredientService.__init__)
        params = list(sig.parameters.keys())

        assert "ingredient_repo" in params
        assert "stock_repo" in params

    @pytest.mark.unit
    def test_exceptions_are_defined(self):
        """Les exceptions custom doivent etre definies."""
        from app.services.restaurant.ingredient import (
            IngredientNotFoundError,
            IngredientNameExistsError,
        )

        assert issubclass(IngredientNotFoundError, Exception)
        assert issubclass(IngredientNameExistsError, Exception)


class TestRestaurantPlatServiceInterface:
    """Tests d'interface pour RestaurantPlatService."""

    @pytest.mark.unit
    def test_service_has_required_methods(self):
        """Le service doit avoir les methodes requises."""
        from app.services.restaurant.plat import RestaurantPlatService

        required_methods = [
            "create_plat",
            "get_plat",
            "get_plat_with_ingredients",
            "get_active_plats",
            "get_plats_by_category",
            "get_menus",
            "search_plats",
            "update_plat",
            "deactivate_plat",
            "add_ingredient",
            "update_ingredient_quantity",
            "remove_ingredient",
            "set_ingredients",
            "calculate_cost",
            "calculate_food_cost_ratio",
            "get_unprofitable_plats",
        ]
        for method in required_methods:
            assert hasattr(RestaurantPlatService, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_exceptions_are_defined(self):
        """Les exceptions custom doivent etre definies."""
        from app.services.restaurant.plat import (
            PlatNotFoundError,
            InvalidPlatError,
        )

        assert issubclass(PlatNotFoundError, Exception)
        assert issubclass(InvalidPlatError, Exception)


class TestRestaurantStockServiceInterface:
    """Tests d'interface pour RestaurantStockService."""

    @pytest.mark.unit
    def test_service_has_required_methods(self):
        """Le service doit avoir les methodes requises."""
        from app.services.restaurant.stock import RestaurantStockService

        required_methods = [
            "get_stock",
            "get_or_create_stock",
            "get_all_stocks",
            "get_low_stock_items",
            "add_stock",
            "remove_stock",
            "adjust_stock",
            "record_loss",
            "get_movements",
            "get_recent_movements",
            "get_stock_alerts",
        ]
        for method in required_methods:
            assert hasattr(RestaurantStockService, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_exceptions_are_defined(self):
        """Les exceptions custom doivent etre definies."""
        from app.services.restaurant.stock import (
            StockNotFoundError,
            InsufficientStockError,
            InvalidStockOperationError,
        )

        assert issubclass(StockNotFoundError, Exception)
        assert issubclass(InsufficientStockError, Exception)
        assert issubclass(InvalidStockOperationError, Exception)


class TestRestaurantConsumptionServiceInterface:
    """Tests d'interface pour RestaurantConsumptionService."""

    @pytest.mark.unit
    def test_service_has_required_methods(self):
        """Le service doit avoir les methodes requises."""
        from app.services.restaurant.consumption import RestaurantConsumptionService

        required_methods = [
            "record_sale",
            "record_loss",
            "record_staff_meal",
            "record_offert",
            "get_consumptions_by_date",
            "get_consumptions_by_plat",
            "get_daily_summary",
            "get_best_sellers",
            "get_loss_report",
        ]
        for method in required_methods:
            assert hasattr(RestaurantConsumptionService, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_exceptions_are_defined(self):
        """Les exceptions custom doivent etre definies."""
        from app.services.restaurant.consumption import InvalidConsumptionError

        assert issubclass(InvalidConsumptionError, Exception)


class TestRestaurantChargeServiceInterface:
    """Tests d'interface pour RestaurantChargeService."""

    @pytest.mark.unit
    def test_service_has_required_methods(self):
        """Le service doit avoir les methodes requises."""
        from app.services.restaurant.charge import RestaurantChargeService

        required_methods = [
            "create_charge",
            "get_charge",
            "get_active_charges",
            "get_current_charges",
            "get_charges_by_type",
            "get_charges_by_frequency",
            "update_charge",
            "deactivate_charge",
            "end_charge",
            "get_total_monthly_charges",
            "get_charges_summary",
            "get_charges_breakdown",
            "calculate_daily_charge",
            "project_annual_charges",
        ]
        for method in required_methods:
            assert hasattr(RestaurantChargeService, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_exceptions_are_defined(self):
        """Les exceptions custom doivent etre definies."""
        from app.services.restaurant.charge import (
            ChargeNotFoundError,
            InvalidChargeError,
        )

        assert issubclass(ChargeNotFoundError, Exception)
        assert issubclass(InvalidChargeError, Exception)


# =============================================================================
# Tests COMPORTEMENTAUX - Verifient le comportement des services
# =============================================================================

class TestRestaurantIngredientServiceBehavior:
    """Tests comportementaux pour RestaurantIngredientService."""

    @pytest.mark.unit
    def test_create_ingredient_raises_if_name_exists(self):
        """create_ingredient doit lever une erreur si le nom existe."""
        from app.services.restaurant.ingredient import (
            RestaurantIngredientService,
            IngredientNameExistsError,
        )
        from app.models.restaurant.ingredient import RestaurantUnit

        # Mock repos
        ingredient_repo = MagicMock()
        ingredient_repo.get_by_name.return_value = MagicMock()  # Existe deja
        stock_repo = MagicMock()

        service = RestaurantIngredientService(ingredient_repo, stock_repo)

        with pytest.raises(IngredientNameExistsError):
            service.create_ingredient(
                name="Tomate",
                unit=RestaurantUnit.KILOGRAMME,
            )

    @pytest.mark.unit
    def test_create_ingredient_creates_initial_stock(self):
        """create_ingredient doit creer le stock initial."""
        from app.services.restaurant.ingredient import RestaurantIngredientService
        from app.models.restaurant.ingredient import RestaurantUnit

        ingredient_repo = MagicMock()
        ingredient_repo.get_by_name.return_value = None  # N'existe pas
        ingredient_repo.tenant_id = 1

        created_ingredient = MagicMock()
        created_ingredient.id = 1
        ingredient_repo.create.return_value = created_ingredient

        stock_repo = MagicMock()

        service = RestaurantIngredientService(ingredient_repo, stock_repo)

        result = service.create_ingredient(
            name="Tomate",
            unit=RestaurantUnit.KILOGRAMME,
        )

        # Verifie que get_or_create est appele avec l'ID
        stock_repo.get_or_create.assert_called_once_with(created_ingredient.id)

    @pytest.mark.unit
    def test_get_ingredient_raises_if_not_found(self):
        """get_ingredient doit lever une erreur si non trouve."""
        from app.services.restaurant.ingredient import (
            RestaurantIngredientService,
            IngredientNotFoundError,
        )

        ingredient_repo = MagicMock()
        ingredient_repo.get.return_value = None
        stock_repo = MagicMock()

        service = RestaurantIngredientService(ingredient_repo, stock_repo)

        with pytest.raises(IngredientNotFoundError):
            service.get_ingredient(999)

    @pytest.mark.unit
    def test_update_price_rejects_negative(self):
        """update_price doit refuser les prix negatifs."""
        from app.services.restaurant.ingredient import RestaurantIngredientService

        ingredient_repo = MagicMock()
        ingredient_repo.get.return_value = MagicMock()
        stock_repo = MagicMock()

        service = RestaurantIngredientService(ingredient_repo, stock_repo)

        with pytest.raises(ValueError, match="negatif"):
            service.update_price(1, -100)


class TestRestaurantPlatServiceBehavior:
    """Tests comportementaux pour RestaurantPlatService."""

    @pytest.mark.unit
    def test_create_plat_rejects_zero_price(self):
        """create_plat doit refuser un prix de vente <= 0."""
        from app.services.restaurant.plat import (
            RestaurantPlatService,
            InvalidPlatError,
        )

        plat_repo = MagicMock()
        plat_ing_repo = MagicMock()
        ingredient_repo = MagicMock()

        service = RestaurantPlatService(plat_repo, plat_ing_repo, ingredient_repo)

        with pytest.raises(InvalidPlatError, match="positif"):
            service.create_plat(name="Test", prix_vente=0)

    @pytest.mark.unit
    def test_create_plat_with_ingredients(self):
        """create_plat doit ajouter les ingredients fournis."""
        from app.services.restaurant.plat import RestaurantPlatService

        plat_repo = MagicMock()
        plat_repo.tenant_id = 1
        created_plat = MagicMock()
        created_plat.id = 1
        plat_repo.create.return_value = created_plat

        plat_ing_repo = MagicMock()

        ingredient_repo = MagicMock()
        ingredient_repo.get.return_value = MagicMock()  # Ingredient existe

        service = RestaurantPlatService(plat_repo, plat_ing_repo, ingredient_repo)

        ingredients = [
            {"ingredient_id": 1, "quantite": "0.5"},
            {"ingredient_id": 2, "quantite": "0.3"},
        ]

        service.create_plat(
            name="Test",
            prix_vente=1500,
            ingredients=ingredients
        )

        # Doit creer 2 lignes d'ingredients
        assert plat_ing_repo.create.call_count == 2

    @pytest.mark.unit
    def test_get_plat_raises_if_not_found(self):
        """get_plat doit lever une erreur si non trouve."""
        from app.services.restaurant.plat import (
            RestaurantPlatService,
            PlatNotFoundError,
        )

        plat_repo = MagicMock()
        plat_repo.get.return_value = None
        plat_ing_repo = MagicMock()
        ingredient_repo = MagicMock()

        service = RestaurantPlatService(plat_repo, plat_ing_repo, ingredient_repo)

        with pytest.raises(PlatNotFoundError):
            service.get_plat(999)

    @pytest.mark.unit
    def test_add_ingredient_checks_duplicate(self):
        """add_ingredient doit verifier les doublons."""
        from app.services.restaurant.plat import (
            RestaurantPlatService,
            InvalidPlatError,
        )

        plat_repo = MagicMock()
        plat_repo.get.return_value = MagicMock()  # Plat existe

        plat_ing_repo = MagicMock()
        plat_ing_repo.exists.return_value = True  # Ingredient deja present

        ingredient_repo = MagicMock()

        service = RestaurantPlatService(plat_repo, plat_ing_repo, ingredient_repo)

        with pytest.raises(InvalidPlatError, match="deja dans le plat"):
            service.add_ingredient(1, 1, Decimal("0.5"))


class TestRestaurantStockServiceBehavior:
    """Tests comportementaux pour RestaurantStockService."""

    @pytest.mark.unit
    def test_add_stock_rejects_zero_quantity(self):
        """add_stock doit refuser une quantite <= 0."""
        from app.services.restaurant.stock import (
            RestaurantStockService,
            InvalidStockOperationError,
        )

        stock_repo = MagicMock()
        movement_repo = MagicMock()
        ingredient_repo = MagicMock()

        service = RestaurantStockService(stock_repo, movement_repo, ingredient_repo)

        with pytest.raises(InvalidStockOperationError, match="positive"):
            service.add_stock(1, Decimal("0"))

    @pytest.mark.unit
    def test_remove_stock_insufficient_raises_error(self):
        """remove_stock doit lever erreur si stock insuffisant."""
        from app.services.restaurant.stock import (
            RestaurantStockService,
            InsufficientStockError,
        )
        from app.models.restaurant.stock import RestaurantStockMovementType

        stock_repo = MagicMock()
        mock_stock = MagicMock()
        mock_stock.quantity = Decimal("5")
        stock_repo.get_by_ingredient.return_value = mock_stock
        stock_repo.get_or_create.return_value = mock_stock

        movement_repo = MagicMock()
        ingredient_repo = MagicMock()

        service = RestaurantStockService(stock_repo, movement_repo, ingredient_repo)

        with pytest.raises(InsufficientStockError):
            service.remove_stock(
                ingredient_id=1,
                quantite=Decimal("10"),  # Plus que dispo
                movement_type=RestaurantStockMovementType.SORTIE,
                allow_negative=False,
            )

    @pytest.mark.unit
    def test_adjust_stock_rejects_negative(self):
        """adjust_stock doit refuser une quantite negative."""
        from app.services.restaurant.stock import (
            RestaurantStockService,
            InvalidStockOperationError,
        )

        stock_repo = MagicMock()
        movement_repo = MagicMock()
        ingredient_repo = MagicMock()

        service = RestaurantStockService(stock_repo, movement_repo, ingredient_repo)

        with pytest.raises(InvalidStockOperationError, match="negative"):
            service.adjust_stock(1, Decimal("-5"))

    @pytest.mark.unit
    def test_add_stock_updates_quantity(self):
        """add_stock doit mettre a jour la quantite en stock."""
        from app.services.restaurant.stock import RestaurantStockService
        from app.models.restaurant.stock import RestaurantStockMovementType

        stock_repo = MagicMock()
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.quantity = Decimal("10")
        stock_repo.get_or_create.return_value = mock_stock

        movement_repo = MagicMock()
        movement_repo.create.return_value = MagicMock(id=1)

        ingredient_repo = MagicMock()

        service = RestaurantStockService(stock_repo, movement_repo, ingredient_repo)

        service.add_stock(
            ingredient_id=1,
            quantite=Decimal("5"),
            movement_type=RestaurantStockMovementType.ENTREE,
        )

        # Verifie que la quantite est incrementee
        assert mock_stock.quantity == Decimal("15")


class TestRestaurantChargeServiceBehavior:
    """Tests comportementaux pour RestaurantChargeService."""

    @pytest.mark.unit
    def test_create_charge_rejects_zero_amount(self):
        """create_charge doit refuser un montant <= 0."""
        from app.services.restaurant.charge import (
            RestaurantChargeService,
            InvalidChargeError,
        )
        from app.models.restaurant.charge import RestaurantChargeType

        charge_repo = MagicMock()

        service = RestaurantChargeService(charge_repo)

        with pytest.raises(InvalidChargeError, match="positif"):
            service.create_charge(
                name="Test",
                charge_type=RestaurantChargeType.LOYER,
                montant=0,
            )

    @pytest.mark.unit
    def test_create_charge_rejects_end_before_start(self):
        """create_charge doit refuser date_fin < date_debut."""
        from app.services.restaurant.charge import (
            RestaurantChargeService,
            InvalidChargeError,
        )
        from app.models.restaurant.charge import RestaurantChargeType
        from datetime import timedelta

        charge_repo = MagicMock()

        service = RestaurantChargeService(charge_repo)

        with pytest.raises(InvalidChargeError, match="apres"):
            service.create_charge(
                name="Test",
                charge_type=RestaurantChargeType.LOYER,
                montant=100000,
                date_debut=date.today(),
                date_fin=date.today() - timedelta(days=30),
            )

    @pytest.mark.unit
    def test_get_charge_raises_if_not_found(self):
        """get_charge doit lever erreur si non trouvee."""
        from app.services.restaurant.charge import (
            RestaurantChargeService,
            ChargeNotFoundError,
        )

        charge_repo = MagicMock()
        charge_repo.get.return_value = None

        service = RestaurantChargeService(charge_repo)

        with pytest.raises(ChargeNotFoundError):
            service.get_charge(999)

    @pytest.mark.unit
    def test_calculate_daily_charge_divides_by_30(self):
        """calculate_daily_charge doit diviser par 30."""
        from app.services.restaurant.charge import RestaurantChargeService

        charge_repo = MagicMock()
        charge_repo.get_total_mensuel.return_value = 300000  # 3000 EUR

        service = RestaurantChargeService(charge_repo)

        result = service.calculate_daily_charge()

        # 300000 / 30 = 10000
        assert result == 10000


class TestRestaurantConsumptionServiceBehavior:
    """Tests comportementaux pour RestaurantConsumptionService."""

    @pytest.mark.unit
    def test_record_sale_rejects_zero_quantity(self):
        """record_sale doit refuser une quantite <= 0."""
        from app.services.restaurant.consumption import (
            RestaurantConsumptionService,
            InvalidConsumptionError,
        )

        consumption_repo = MagicMock()
        plat_service = MagicMock()
        stock_service = MagicMock()

        service = RestaurantConsumptionService(
            consumption_repo, plat_service, stock_service
        )

        with pytest.raises(InvalidConsumptionError, match="positive"):
            service.record_sale(plat_id=1, quantite=0)

    @pytest.mark.unit
    def test_record_sale_uses_plat_price_by_default(self):
        """record_sale doit utiliser le prix du plat par defaut."""
        from app.services.restaurant.consumption import RestaurantConsumptionService

        consumption_repo = MagicMock()
        consumption_repo.tenant_id = 1
        consumption_repo.create.return_value = MagicMock(id=1)

        mock_plat = MagicMock()
        mock_plat.prix_vente = 1500
        mock_plat.cout_total = 400
        mock_plat.ingredients = []

        plat_service = MagicMock()
        plat_service.get_plat_with_ingredients.return_value = mock_plat

        stock_service = MagicMock()

        service = RestaurantConsumptionService(
            consumption_repo, plat_service, stock_service
        )

        service.record_sale(plat_id=1, quantite=1)

        # Verifie que le prix utilise est celui du plat
        call_args = consumption_repo.create.call_args[0][0]
        assert call_args["prix_vente"] == 1500

    @pytest.mark.unit
    def test_record_sale_uses_custom_price_when_provided(self):
        """record_sale doit utiliser le prix custom si fourni."""
        from app.services.restaurant.consumption import RestaurantConsumptionService

        consumption_repo = MagicMock()
        consumption_repo.tenant_id = 1
        consumption_repo.create.return_value = MagicMock(id=1)

        mock_plat = MagicMock()
        mock_plat.prix_vente = 1500
        mock_plat.cout_total = 400
        mock_plat.ingredients = []

        plat_service = MagicMock()
        plat_service.get_plat_with_ingredients.return_value = mock_plat

        stock_service = MagicMock()

        service = RestaurantConsumptionService(
            consumption_repo, plat_service, stock_service
        )

        service.record_sale(plat_id=1, quantite=1, prix_vente=1200)

        call_args = consumption_repo.create.call_args[0][0]
        assert call_args["prix_vente"] == 1200

    @pytest.mark.unit
    def test_get_daily_summary_calculates_margin(self):
        """get_daily_summary doit calculer la marge."""
        from app.services.restaurant.consumption import RestaurantConsumptionService
        from app.models.restaurant.consumption import RestaurantConsumptionType

        # Mock consommations
        mock_sale = MagicMock()
        mock_sale.type = RestaurantConsumptionType.VENTE
        mock_sale.quantite = 2
        mock_sale.prix_vente = 1500
        mock_sale.cout = 400

        consumption_repo = MagicMock()
        consumption_repo.get_by_period.return_value = [mock_sale]

        plat_service = MagicMock()
        stock_service = MagicMock()

        service = RestaurantConsumptionService(
            consumption_repo, plat_service, stock_service
        )

        result = service.get_daily_summary(date.today())

        # Revenue = 2 * 1500 = 3000
        # Cost = 2 * 400 = 800
        # Margin = 3000 - 800 = 2200
        assert result["total_revenue"] == 3000
        assert result["total_cost"] == 800
        assert result["margin"] == 2200
