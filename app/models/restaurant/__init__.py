"""
Models Restaurant Domain pour MassaCorp.
Gestion des ingredients, plats, stock et consommations.
"""
from app.models.restaurant.ingredient import (
    RestaurantIngredient,
    RestaurantUnit,
    RestaurantIngredientCategory,
)
from app.models.restaurant.plat import (
    RestaurantPlat,
    RestaurantPlatCategory,
)
from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient
from app.models.restaurant.epicerie_link import RestaurantEpicerieLink
from app.models.restaurant.stock import (
    RestaurantStock,
    RestaurantStockMovement,
    RestaurantStockMovementType,
)
from app.models.restaurant.consumption import (
    RestaurantConsumption,
    RestaurantConsumptionType,
)
from app.models.restaurant.charge import (
    RestaurantCharge,
    RestaurantChargeType,
    RestaurantChargeFrequency,
)

__all__ = [
    # Ingredient
    "RestaurantIngredient",
    "RestaurantUnit",
    "RestaurantIngredientCategory",
    # Plat
    "RestaurantPlat",
    "RestaurantPlatCategory",
    # Plat-Ingredient
    "RestaurantPlatIngredient",
    # Epicerie Link
    "RestaurantEpicerieLink",
    # Stock
    "RestaurantStock",
    "RestaurantStockMovement",
    "RestaurantStockMovementType",
    # Consumption
    "RestaurantConsumption",
    "RestaurantConsumptionType",
    # Charge
    "RestaurantCharge",
    "RestaurantChargeType",
    "RestaurantChargeFrequency",
]
