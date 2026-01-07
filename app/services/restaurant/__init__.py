"""
Services Restaurant Domain.
Logique metier pour la gestion du restaurant.
"""
from app.services.restaurant.ingredient import (
    RestaurantIngredientService,
    IngredientNotFoundError,
    IngredientNameExistsError,
)
from app.services.restaurant.plat import (
    RestaurantPlatService,
    PlatNotFoundError,
    InvalidPlatError,
)
from app.services.restaurant.stock import (
    RestaurantStockService,
    StockNotFoundError,
    InsufficientStockError,
    InvalidStockOperationError,
)
from app.services.restaurant.consumption import (
    RestaurantConsumptionService,
    InvalidConsumptionError,
)
from app.services.restaurant.charge import (
    RestaurantChargeService,
    ChargeNotFoundError,
    InvalidChargeError,
)

__all__ = [
    # Services
    "RestaurantIngredientService",
    "RestaurantPlatService",
    "RestaurantStockService",
    "RestaurantConsumptionService",
    "RestaurantChargeService",
    # Errors
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
