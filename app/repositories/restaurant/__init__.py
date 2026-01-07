"""
Repositories Restaurant Domain.
Acces aux donnees avec isolation multi-tenant.
"""
from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
from app.repositories.restaurant.plat import (
    RestaurantPlatRepository,
    RestaurantPlatIngredientRepository,
)
from app.repositories.restaurant.stock import (
    RestaurantStockRepository,
    RestaurantStockMovementRepository,
)
from app.repositories.restaurant.consumption import RestaurantConsumptionRepository
from app.repositories.restaurant.charge import RestaurantChargeRepository
from app.repositories.restaurant.epicerie_link import RestaurantEpicerieLinkRepository

__all__ = [
    "RestaurantIngredientRepository",
    "RestaurantPlatRepository",
    "RestaurantPlatIngredientRepository",
    "RestaurantStockRepository",
    "RestaurantStockMovementRepository",
    "RestaurantConsumptionRepository",
    "RestaurantChargeRepository",
    "RestaurantEpicerieLinkRepository",
]
