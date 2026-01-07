"""
Tests unitaires pour les models Restaurant Domain.
Tests COMPORTEMENTAUX uniquement.
"""
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock


# =============================================================================
# Tests d'INTERFACE - Verifient l'existence des attributs et methodes
# =============================================================================

class TestRestaurantIngredientInterface:
    """Tests d'interface pour RestaurantIngredient."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.ingredient import RestaurantIngredient

        required_attrs = [
            "id", "tenant_id", "name", "unit", "category",
            "prix_unitaire", "seuil_alerte", "default_supplier_id",
            "notes", "is_active", "created_at", "updated_at"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantIngredient, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_model_has_tablename(self):
        """Le model doit avoir un __tablename__."""
        from app.models.restaurant.ingredient import RestaurantIngredient

        assert hasattr(RestaurantIngredient, "__tablename__")
        assert RestaurantIngredient.__tablename__ == "restaurant_ingredients"

    @pytest.mark.unit
    def test_model_has_property_prix_unitaire_decimal(self):
        """Le model doit avoir la propriete prix_unitaire_decimal."""
        from app.models.restaurant.ingredient import RestaurantIngredient

        assert hasattr(RestaurantIngredient, "prix_unitaire_decimal")

    @pytest.mark.unit
    def test_unit_enum_has_expected_values(self):
        """RestaurantUnit doit avoir les valeurs attendues."""
        from app.models.restaurant.ingredient import RestaurantUnit

        expected_values = ["U", "KG", "L", "G", "CL", "ML"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantUnit), f"Missing unit: {value}"

    @pytest.mark.unit
    def test_category_enum_has_expected_values(self):
        """RestaurantIngredientCategory doit avoir les valeurs attendues."""
        from app.models.restaurant.ingredient import RestaurantIngredientCategory

        # Valeurs reelles du modele
        expected_values = ["VIANDE", "POISSON", "LEGUME", "FRUIT", "PRODUIT_LAITIER",
                          "EPICERIE", "CONDIMENT", "BOISSON", "AUTRE"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantIngredientCategory), f"Missing category: {value}"


class TestRestaurantPlatInterface:
    """Tests d'interface pour RestaurantPlat."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.plat import RestaurantPlat

        required_attrs = [
            "id", "tenant_id", "name", "category", "prix_vente",
            "description", "is_menu", "image_url", "notes",
            "is_active", "created_at", "updated_at"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantPlat, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_model_has_tablename(self):
        """Le model doit avoir un __tablename__."""
        from app.models.restaurant.plat import RestaurantPlat

        assert hasattr(RestaurantPlat, "__tablename__")
        assert RestaurantPlat.__tablename__ == "restaurant_plats"

    @pytest.mark.unit
    def test_model_has_computed_properties(self):
        """Le model doit avoir les proprietes calculees."""
        from app.models.restaurant.plat import RestaurantPlat

        computed_props = ["cout_total", "food_cost_ratio", "is_profitable"]
        for prop in computed_props:
            assert hasattr(RestaurantPlat, prop), f"Missing property: {prop}"

    @pytest.mark.unit
    def test_model_has_ingredients_relationship(self):
        """Le model doit avoir la relation ingredients."""
        from app.models.restaurant.plat import RestaurantPlat

        assert hasattr(RestaurantPlat, "ingredients")

    @pytest.mark.unit
    def test_category_enum_has_expected_values(self):
        """RestaurantPlatCategory doit avoir les valeurs attendues."""
        from app.models.restaurant.plat import RestaurantPlatCategory

        expected_values = ["ENTREE", "PLAT", "DESSERT", "BOISSON", "MENU"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantPlatCategory), f"Missing category: {value}"


class TestRestaurantPlatIngredientInterface:
    """Tests d'interface pour RestaurantPlatIngredient."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient

        required_attrs = [
            "id", "plat_id", "ingredient_id", "quantite", "notes"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantPlatIngredient, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_model_has_cout_ligne_property(self):
        """Le model doit avoir la propriete cout_ligne."""
        from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient

        assert hasattr(RestaurantPlatIngredient, "cout_ligne")

    @pytest.mark.unit
    def test_model_has_relationships(self):
        """Le model doit avoir les relations."""
        from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient

        assert hasattr(RestaurantPlatIngredient, "plat")
        assert hasattr(RestaurantPlatIngredient, "ingredient")


class TestRestaurantStockInterface:
    """Tests d'interface pour RestaurantStock."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.stock import RestaurantStock

        # Attributs reels du modele
        required_attrs = [
            "id", "tenant_id", "ingredient_id", "quantity",
            "last_inventory_date"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantStock, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_model_has_computed_properties(self):
        """Le model doit avoir les proprietes calculees."""
        from app.models.restaurant.stock import RestaurantStock

        # Proprietes reelles du modele
        computed_props = ["is_low", "is_empty", "needs_inventory"]
        for prop in computed_props:
            assert hasattr(RestaurantStock, prop), f"Missing property: {prop}"

    @pytest.mark.unit
    def test_movement_type_enum_has_expected_values(self):
        """RestaurantStockMovementType doit avoir les valeurs attendues."""
        from app.models.restaurant.stock import RestaurantStockMovementType

        # Valeurs reelles du modele
        expected_values = ["ENTREE", "SORTIE", "AJUSTEMENT", "PERTE", "TRANSFERT"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantStockMovementType), f"Missing type: {value}"


class TestRestaurantConsumptionInterface:
    """Tests d'interface pour RestaurantConsumption."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.consumption import RestaurantConsumption

        required_attrs = [
            "id", "tenant_id", "plat_id", "type", "quantite",
            "prix_vente", "cout", "date", "notes"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantConsumption, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_consumption_type_enum_has_expected_values(self):
        """RestaurantConsumptionType doit avoir les valeurs attendues."""
        from app.models.restaurant.consumption import RestaurantConsumptionType

        expected_values = ["VENTE", "PERTE", "REPAS_STAFF", "OFFERT"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantConsumptionType), f"Missing type: {value}"


class TestRestaurantChargeInterface:
    """Tests d'interface pour RestaurantCharge."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.charge import RestaurantCharge

        required_attrs = [
            "id", "tenant_id", "name", "type", "montant", "frequency",
            "date_debut", "date_fin", "notes", "is_active"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantCharge, attr), f"Missing attribute: {attr}"

    @pytest.mark.unit
    def test_model_has_computed_properties(self):
        """Le model doit avoir les proprietes calculees."""
        from app.models.restaurant.charge import RestaurantCharge

        computed_props = ["montant_mensuel", "is_current"]
        for prop in computed_props:
            assert hasattr(RestaurantCharge, prop), f"Missing property: {prop}"

    @pytest.mark.unit
    def test_charge_type_enum_has_expected_values(self):
        """RestaurantChargeType doit avoir les valeurs attendues."""
        from app.models.restaurant.charge import RestaurantChargeType

        # Valeurs reelles du modele
        expected_values = ["LOYER", "SALAIRES", "ELECTRICITE", "EAU", "GAZ",
                          "ASSURANCE", "ENTRETIEN", "MARKETING", "AUTRES"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantChargeType), f"Missing type: {value}"

    @pytest.mark.unit
    def test_frequency_enum_has_expected_values(self):
        """RestaurantChargeFrequency doit avoir les valeurs attendues."""
        from app.models.restaurant.charge import RestaurantChargeFrequency

        expected_values = ["MENSUEL", "TRIMESTRIEL", "ANNUEL", "PONCTUEL"]
        for value in expected_values:
            assert any(e.value == value for e in RestaurantChargeFrequency), f"Missing frequency: {value}"


class TestRestaurantEpicerieLinkInterface:
    """Tests d'interface pour RestaurantEpicerieLink."""

    @pytest.mark.unit
    def test_model_has_required_attributes(self):
        """Le model doit avoir les attributs requis."""
        from app.models.restaurant.epicerie_link import RestaurantEpicerieLink

        # Attributs reels du modele
        required_attrs = [
            "id", "tenant_id", "ingredient_id", "produit_id",
            "ratio", "is_primary"
        ]
        for attr in required_attrs:
            assert hasattr(RestaurantEpicerieLink, attr), f"Missing attribute: {attr}"


# =============================================================================
# Tests COMPORTEMENTAUX - Verifient le comportement des proprietes
# =============================================================================

class TestRestaurantIngredientBehavior:
    """Tests comportementaux pour RestaurantIngredient."""

    @pytest.mark.unit
    def test_prix_unitaire_decimal_converts_centimes_to_euros(self):
        """prix_unitaire_decimal doit convertir centimes en euros."""
        from app.models.restaurant.ingredient import (
            RestaurantIngredient,
            RestaurantUnit,
            RestaurantIngredientCategory,
        )

        ingredient = RestaurantIngredient(
            id=1,
            tenant_id=1,
            name="Tomate",
            unit=RestaurantUnit.KILOGRAMME,
            category=RestaurantIngredientCategory.LEGUME,
            prix_unitaire=350,  # 3.50 EUR en centimes
            is_active=True,
        )

        result = ingredient.prix_unitaire_decimal

        assert result == Decimal("3.50")

    @pytest.mark.unit
    def test_prix_unitaire_decimal_zero_when_no_price(self):
        """prix_unitaire_decimal doit retourner 0 si pas de prix."""
        from app.models.restaurant.ingredient import (
            RestaurantIngredient,
            RestaurantUnit,
            RestaurantIngredientCategory,
        )

        ingredient = RestaurantIngredient(
            id=1,
            tenant_id=1,
            name="Sel",
            unit=RestaurantUnit.GRAMME,
            category=RestaurantIngredientCategory.EPICERIE,  # Corrige: EPICERIE pas EPICE
            prix_unitaire=0,
            is_active=True,
        )

        result = ingredient.prix_unitaire_decimal

        assert result == Decimal("0")


class TestRestaurantPlatBehavior:
    """Tests comportementaux pour RestaurantPlat."""

    @pytest.mark.unit
    def test_cout_total_zero_when_no_ingredients(self):
        """cout_total doit etre 0 sans ingredients."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Test",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=1500,
            is_menu=False,
            is_active=True,
        )
        plat.ingredients = []

        result = plat.cout_total

        assert result == 0

    @pytest.mark.unit
    def test_cout_total_sums_ingredient_costs(self):
        """cout_total doit additionner les couts des ingredients."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Test",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=1500,
            is_menu=False,
            is_active=True,
        )

        # Mock des plat_ingredients avec cout_ligne
        ing1 = MagicMock()
        ing1.cout_ligne = 200
        ing2 = MagicMock()
        ing2.cout_ligne = 300
        plat.ingredients = [ing1, ing2]

        result = plat.cout_total

        assert result == 500

    @pytest.mark.unit
    def test_food_cost_ratio_calculated_correctly(self):
        """food_cost_ratio doit etre calcule correctement."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Test",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=1000,  # 10 EUR
            is_menu=False,
            is_active=True,
        )

        # Cout = 300 centimes (3 EUR)
        ing = MagicMock()
        ing.cout_ligne = 300
        plat.ingredients = [ing]

        result = plat.food_cost_ratio

        # 300 / 1000 * 100 = 30%
        assert result == Decimal("30.00")

    @pytest.mark.unit
    def test_food_cost_ratio_zero_when_zero_price(self):
        """food_cost_ratio doit etre 0 si prix de vente = 0."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Offert",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=0,
            is_menu=False,
            is_active=True,
        )
        plat.ingredients = []

        result = plat.food_cost_ratio

        assert result == Decimal("0")

    @pytest.mark.unit
    def test_is_profitable_true_under_35_percent(self):
        """is_profitable doit etre True si food_cost < 35%."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Rentable",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=1000,
            is_menu=False,
            is_active=True,
        )

        # Cout = 300 centimes = 30% < 35%
        ing = MagicMock()
        ing.cout_ligne = 300
        plat.ingredients = [ing]

        assert plat.is_profitable is True

    @pytest.mark.unit
    def test_is_profitable_false_over_35_percent(self):
        """is_profitable doit etre False si food_cost >= 35%."""
        from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory

        plat = RestaurantPlat(
            id=1,
            tenant_id=1,
            name="Plat Non Rentable",
            category=RestaurantPlatCategory.PLAT,
            prix_vente=1000,
            is_menu=False,
            is_active=True,
        )

        # Cout = 400 centimes = 40% > 35%
        ing = MagicMock()
        ing.cout_ligne = 400
        plat.ingredients = [ing]

        assert plat.is_profitable is False


class TestRestaurantPlatIngredientBehavior:
    """Tests comportementaux pour RestaurantPlatIngredient."""

    @pytest.mark.unit
    def test_cout_ligne_calculated_correctly(self):
        """cout_ligne doit etre quantite * prix_unitaire."""
        from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient

        plat_ing = RestaurantPlatIngredient(
            id=1,
            plat_id=1,
            ingredient_id=1,
            quantite=Decimal("2.5"),  # 2.5 kg
        )

        # Mock ingredient avec prix_unitaire
        mock_ingredient = MagicMock()
        mock_ingredient.prix_unitaire = 400  # 4 EUR/kg
        plat_ing.ingredient = mock_ingredient

        result = plat_ing.cout_ligne

        # 2.5 * 400 = 1000 centimes
        assert result == 1000

    @pytest.mark.unit
    def test_cout_ligne_zero_when_no_ingredient(self):
        """cout_ligne doit etre 0 sans ingredient."""
        from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient

        plat_ing = RestaurantPlatIngredient(
            id=1,
            plat_id=1,
            ingredient_id=1,
            quantite=Decimal("2.5"),
        )
        plat_ing.ingredient = None

        result = plat_ing.cout_ligne

        assert result == 0


class TestRestaurantStockBehavior:
    """Tests comportementaux pour RestaurantStock."""

    @pytest.mark.unit
    def test_is_low_true_below_threshold(self):
        """is_low doit etre True sous le seuil."""
        from app.models.restaurant.stock import RestaurantStock

        stock = RestaurantStock(
            id=1,
            tenant_id=1,
            ingredient_id=1,
            quantity=Decimal("5"),  # Corrige: quantity pas quantite_actuelle
        )

        # Mock ingredient avec seuil_alerte
        mock_ingredient = MagicMock()
        mock_ingredient.seuil_alerte = Decimal("10")
        stock.ingredient = mock_ingredient

        result = stock.is_low  # Corrige: is_low pas is_low_stock

        assert result is True

    @pytest.mark.unit
    def test_is_low_false_above_threshold(self):
        """is_low doit etre False au-dessus du seuil."""
        from app.models.restaurant.stock import RestaurantStock

        stock = RestaurantStock(
            id=1,
            tenant_id=1,
            ingredient_id=1,
            quantity=Decimal("15"),
        )

        mock_ingredient = MagicMock()
        mock_ingredient.seuil_alerte = Decimal("10")
        stock.ingredient = mock_ingredient

        result = stock.is_low

        assert result is False

    @pytest.mark.unit
    def test_is_low_false_when_no_threshold(self):
        """is_low doit etre False sans seuil defini."""
        from app.models.restaurant.stock import RestaurantStock

        stock = RestaurantStock(
            id=1,
            tenant_id=1,
            ingredient_id=1,
            quantity=Decimal("5"),
        )

        mock_ingredient = MagicMock()
        mock_ingredient.seuil_alerte = None
        stock.ingredient = mock_ingredient

        result = stock.is_low

        assert result is False

    @pytest.mark.unit
    def test_is_empty_true_when_zero_quantity(self):
        """is_empty doit etre True si quantite <= 0."""
        from app.models.restaurant.stock import RestaurantStock

        stock = RestaurantStock(
            id=1,
            tenant_id=1,
            ingredient_id=1,
            quantity=Decimal("0"),
        )
        stock.ingredient = None

        assert stock.is_empty is True

    @pytest.mark.unit
    def test_is_empty_false_when_positive_quantity(self):
        """is_empty doit etre False si quantite > 0."""
        from app.models.restaurant.stock import RestaurantStock

        stock = RestaurantStock(
            id=1,
            tenant_id=1,
            ingredient_id=1,
            quantity=Decimal("5"),
        )
        stock.ingredient = None

        assert stock.is_empty is False


class TestRestaurantChargeBehavior:
    """Tests comportementaux pour RestaurantCharge."""

    @pytest.mark.unit
    def test_montant_mensuel_same_for_monthly(self):
        """montant_mensuel doit etre identique pour frequence mensuelle."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Loyer",
            type=RestaurantChargeType.LOYER,
            montant=150000,  # 1500 EUR
            frequency=RestaurantChargeFrequency.MENSUEL,
            date_debut=date.today(),
            is_active=True,
        )

        result = charge.montant_mensuel

        assert result == 150000

    @pytest.mark.unit
    def test_montant_mensuel_divided_for_quarterly(self):
        """montant_mensuel doit diviser par 3 pour frequence trimestrielle."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Assurance",
            type=RestaurantChargeType.ASSURANCE,
            montant=90000,  # 900 EUR / trimestre
            frequency=RestaurantChargeFrequency.TRIMESTRIEL,
            date_debut=date.today(),
            is_active=True,
        )

        result = charge.montant_mensuel

        # 90000 / 3 = 30000
        assert result == 30000

    @pytest.mark.unit
    def test_montant_mensuel_divided_for_yearly(self):
        """montant_mensuel doit diviser par 12 pour frequence annuelle."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Licence",
            type=RestaurantChargeType.AUTRES,  # Corrige: AUTRES pas AUTRE
            montant=1200000,  # 12000 EUR / an
            frequency=RestaurantChargeFrequency.ANNUEL,
            date_debut=date.today(),
            is_active=True,
        )

        result = charge.montant_mensuel

        # 1200000 / 12 = 100000
        assert result == 100000

    @pytest.mark.unit
    def test_is_current_true_when_within_dates(self):
        """is_current doit etre True si date actuelle entre debut et fin."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )
        from datetime import timedelta

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Loyer",
            type=RestaurantChargeType.LOYER,
            montant=150000,
            frequency=RestaurantChargeFrequency.MENSUEL,
            date_debut=date.today() - timedelta(days=30),
            date_fin=date.today() + timedelta(days=30),
            is_active=True,
        )

        result = charge.is_current

        assert result is True

    @pytest.mark.unit
    def test_is_current_false_when_past_end_date(self):
        """is_current doit etre False si date_fin depassee."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )
        from datetime import timedelta

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Ancien Loyer",
            type=RestaurantChargeType.LOYER,
            montant=150000,
            frequency=RestaurantChargeFrequency.MENSUEL,
            date_debut=date.today() - timedelta(days=90),
            date_fin=date.today() - timedelta(days=30),  # Termine il y a 30 jours
            is_active=True,
        )

        result = charge.is_current

        assert result is False

    @pytest.mark.unit
    def test_is_current_true_when_no_end_date(self):
        """is_current doit etre True sans date de fin."""
        from app.models.restaurant.charge import (
            RestaurantCharge,
            RestaurantChargeType,
            RestaurantChargeFrequency,
        )
        from datetime import timedelta

        charge = RestaurantCharge(
            id=1,
            tenant_id=1,
            name="Loyer Indefini",
            type=RestaurantChargeType.LOYER,
            montant=150000,
            frequency=RestaurantChargeFrequency.MENSUEL,
            date_debut=date.today() - timedelta(days=30),
            date_fin=None,
            is_active=True,
        )

        result = charge.is_current

        assert result is True
