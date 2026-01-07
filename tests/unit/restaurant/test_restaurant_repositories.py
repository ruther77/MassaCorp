"""
Tests unitaires pour les repositories Restaurant Domain.
Comprend tests d'INTERFACE (hasattr) et tests COMPORTEMENTAUX.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# =============================================================================
# Tests d'INTERFACE - Verifient l'existence des methodes
# =============================================================================

class TestRestaurantIngredientRepositoryInterface:
    """Tests d'interface pour RestaurantIngredientRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.ingredient import RestaurantIngredientRepository

        required_methods = [
            "get",
            "create",
            "get_active",
            "get_by_category",
            "get_by_name",
            "search_by_name",
            "get_low_stock",
        ]
        for method in required_methods:
            assert hasattr(RestaurantIngredientRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantIngredientRepository, TenantAwareBaseRepository)

    @pytest.mark.unit
    def test_repository_has_model_attribute(self):
        """Le repository doit avoir l'attribut model."""
        from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
        from app.models.restaurant.ingredient import RestaurantIngredient

        assert hasattr(RestaurantIngredientRepository, "model")
        assert RestaurantIngredientRepository.model == RestaurantIngredient


class TestRestaurantPlatRepositoryInterface:
    """Tests d'interface pour RestaurantPlatRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.plat import RestaurantPlatRepository

        required_methods = [
            "get",
            "create",
            "get_active",
            "get_by_category",
            "get_with_ingredients",
            "get_menus",
            "search_by_name",
            "get_unprofitable",
        ]
        for method in required_methods:
            assert hasattr(RestaurantPlatRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.plat import RestaurantPlatRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantPlatRepository, TenantAwareBaseRepository)


class TestRestaurantPlatIngredientRepositoryInterface:
    """Tests d'interface pour RestaurantPlatIngredientRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.plat import RestaurantPlatIngredientRepository

        required_methods = [
            "get",
            "create",
            "get_by_plat",
            "exists",
            "delete_by_plat",
        ]
        for method in required_methods:
            assert hasattr(RestaurantPlatIngredientRepository, method), f"Missing method: {method}"


class TestRestaurantStockRepositoryInterface:
    """Tests d'interface pour RestaurantStockRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.stock import RestaurantStockRepository

        required_methods = [
            "get",
            "create",
            "get_by_ingredient",
            "get_or_create",
            "get_all_with_ingredients",
            "get_low_stock",
        ]
        for method in required_methods:
            assert hasattr(RestaurantStockRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.stock import RestaurantStockRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantStockRepository, TenantAwareBaseRepository)


class TestRestaurantStockMovementRepositoryInterface:
    """Tests d'interface pour RestaurantStockMovementRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.stock import RestaurantStockMovementRepository

        required_methods = [
            "get",
            "create",
            "get_by_stock",
            "get_recent",
        ]
        for method in required_methods:
            assert hasattr(RestaurantStockMovementRepository, method), f"Missing method: {method}"


class TestRestaurantConsumptionRepositoryInterface:
    """Tests d'interface pour RestaurantConsumptionRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.consumption import RestaurantConsumptionRepository

        required_methods = [
            "get",
            "create",
            "get_by_period",
            "get_by_plat",
            "get_total_cost_by_period",
        ]
        for method in required_methods:
            assert hasattr(RestaurantConsumptionRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.consumption import RestaurantConsumptionRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantConsumptionRepository, TenantAwareBaseRepository)


class TestRestaurantChargeRepositoryInterface:
    """Tests d'interface pour RestaurantChargeRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.charge import RestaurantChargeRepository

        required_methods = [
            "get",
            "create",
            "get_active",
            "get_current",
            "get_by_type",
            "get_total_mensuel",
            "get_by_frequency",
            "get_summary_by_type",
        ]
        for method in required_methods:
            assert hasattr(RestaurantChargeRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.charge import RestaurantChargeRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantChargeRepository, TenantAwareBaseRepository)


class TestRestaurantEpicerieLinkRepositoryInterface:
    """Tests d'interface pour RestaurantEpicerieLinkRepository."""

    @pytest.mark.unit
    def test_repository_has_required_methods(self):
        """Le repository doit avoir les methodes requises."""
        from app.repositories.restaurant.epicerie_link import RestaurantEpicerieLinkRepository

        required_methods = [
            "get",
            "create",
            "get_by_ingredient",
            "get_primary_by_ingredient",
            "get_by_produit",
            "exists",
            "set_primary",
        ]
        for method in required_methods:
            assert hasattr(RestaurantEpicerieLinkRepository, method), f"Missing method: {method}"

    @pytest.mark.unit
    def test_repository_inherits_tenant_aware_base(self):
        """Le repository doit heriter de TenantAwareBaseRepository."""
        from app.repositories.restaurant.epicerie_link import RestaurantEpicerieLinkRepository
        from app.repositories.base import TenantAwareBaseRepository

        assert issubclass(RestaurantEpicerieLinkRepository, TenantAwareBaseRepository)


# =============================================================================
# Tests d'INTERFACE - Module __init__.py
# =============================================================================

class TestRestaurantRepositoriesModuleInterface:
    """Tests d'interface pour le module repositories restaurant."""

    @pytest.mark.unit
    def test_module_exports_all_repositories(self):
        """Le module doit exporter tous les repositories."""
        from app.repositories import restaurant

        required_exports = [
            "RestaurantIngredientRepository",
            "RestaurantPlatRepository",
            "RestaurantPlatIngredientRepository",
            "RestaurantStockRepository",
            "RestaurantStockMovementRepository",
            "RestaurantConsumptionRepository",
            "RestaurantChargeRepository",
            "RestaurantEpicerieLinkRepository",
        ]
        for export in required_exports:
            assert hasattr(restaurant, export), f"Missing export: {export}"


class TestRestaurantServicesModuleInterface:
    """Tests d'interface pour le module services restaurant."""

    @pytest.mark.unit
    def test_module_exports_all_services(self):
        """Le module doit exporter tous les services."""
        from app.services import restaurant

        required_exports = [
            "RestaurantIngredientService",
            "RestaurantPlatService",
            "RestaurantStockService",
            "RestaurantConsumptionService",
            "RestaurantChargeService",
        ]
        for export in required_exports:
            assert hasattr(restaurant, export), f"Missing export: {export}"

    @pytest.mark.unit
    def test_module_exports_all_exceptions(self):
        """Le module doit exporter toutes les exceptions."""
        from app.services import restaurant

        required_exports = [
            "IngredientNotFoundError",
            "IngredientNameExistsError",
            "PlatNotFoundError",
            "InvalidPlatError",
            "StockNotFoundError",
            "InsufficientStockError",
            "InvalidStockOperationError",
            "InvalidConsumptionError",
            "ChargeNotFoundError",
            "InvalidChargeError",
        ]
        for export in required_exports:
            assert hasattr(restaurant, export), f"Missing export: {export}"


class TestRestaurantModelsModuleInterface:
    """Tests d'interface pour le module models restaurant."""

    @pytest.mark.unit
    def test_module_exports_all_models(self):
        """Le module doit exporter tous les models."""
        from app.models import restaurant

        required_exports = [
            "RestaurantIngredient",
            "RestaurantUnit",
            "RestaurantIngredientCategory",
            "RestaurantPlat",
            "RestaurantPlatCategory",
            "RestaurantPlatIngredient",
            "RestaurantStock",
            "RestaurantStockMovement",
            "RestaurantStockMovementType",
            "RestaurantConsumption",
            "RestaurantConsumptionType",
            "RestaurantCharge",
            "RestaurantChargeType",
            "RestaurantChargeFrequency",
            "RestaurantEpicerieLink",
        ]
        for export in required_exports:
            assert hasattr(restaurant, export), f"Missing export: {export}"


# =============================================================================
# Tests COMPORTEMENTAUX - Isolation Multi-Tenant
# =============================================================================

class TestTenantIsolation:
    """Tests pour verifier l'isolation multi-tenant."""

    @pytest.mark.unit
    def test_repository_requires_tenant_id(self):
        """Les repositories tenant-aware doivent exiger tenant_id."""
        from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
        import inspect

        sig = inspect.signature(RestaurantIngredientRepository.__init__)
        params = list(sig.parameters.keys())

        assert "tenant_id" in params

    @pytest.mark.unit
    def test_repository_stores_tenant_id(self):
        """Les repositories doivent stocker tenant_id."""
        from app.repositories.restaurant.ingredient import RestaurantIngredientRepository

        mock_db = MagicMock()
        repo = RestaurantIngredientRepository(mock_db, tenant_id=42)

        assert repo.tenant_id == 42

    @pytest.mark.unit
    def test_plat_repository_requires_tenant_id(self):
        """RestaurantPlatRepository doit exiger tenant_id."""
        from app.repositories.restaurant.plat import RestaurantPlatRepository

        mock_db = MagicMock()
        repo = RestaurantPlatRepository(mock_db, tenant_id=99)

        assert repo.tenant_id == 99

    @pytest.mark.unit
    def test_stock_repository_requires_tenant_id(self):
        """RestaurantStockRepository doit exiger tenant_id."""
        from app.repositories.restaurant.stock import RestaurantStockRepository

        mock_db = MagicMock()
        repo = RestaurantStockRepository(mock_db, tenant_id=123)

        assert repo.tenant_id == 123

    @pytest.mark.unit
    def test_charge_repository_requires_tenant_id(self):
        """RestaurantChargeRepository doit exiger tenant_id."""
        from app.repositories.restaurant.charge import RestaurantChargeRepository

        mock_db = MagicMock()
        repo = RestaurantChargeRepository(mock_db, tenant_id=456)

        assert repo.tenant_id == 456

    @pytest.mark.unit
    def test_consumption_repository_requires_tenant_id(self):
        """RestaurantConsumptionRepository doit exiger tenant_id."""
        from app.repositories.restaurant.consumption import RestaurantConsumptionRepository

        mock_db = MagicMock()
        repo = RestaurantConsumptionRepository(mock_db, tenant_id=789)

        assert repo.tenant_id == 789
