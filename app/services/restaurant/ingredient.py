"""
Service pour la gestion des ingredients restaurant.
"""
from decimal import Decimal
from typing import List, Optional

from app.models.restaurant.ingredient import (
    RestaurantIngredient,
    RestaurantUnit,
    RestaurantIngredientCategory,
)
from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
from app.repositories.restaurant.stock import RestaurantStockRepository


class IngredientNotFoundError(Exception):
    """Ingredient non trouve."""
    def __init__(self, ingredient_id: int):
        self.ingredient_id = ingredient_id
        super().__init__(f"Ingredient {ingredient_id} non trouve")


class IngredientNameExistsError(Exception):
    """Nom d'ingredient deja utilise."""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Un ingredient avec le nom '{name}' existe deja")


class RestaurantIngredientService:
    """
    Service pour la gestion des ingredients.

    Responsabilites:
    - CRUD ingredients
    - Validation des donnees
    - Gestion des prix
    """

    def __init__(
        self,
        ingredient_repo: RestaurantIngredientRepository,
        stock_repo: RestaurantStockRepository
    ):
        self.ingredient_repo = ingredient_repo
        self.stock_repo = stock_repo

    def create_ingredient(
        self,
        name: str,
        unit: RestaurantUnit,
        category: RestaurantIngredientCategory = RestaurantIngredientCategory.AUTRE,
        prix_unitaire: int = 0,
        seuil_alerte: Optional[Decimal] = None,
        default_supplier_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> RestaurantIngredient:
        """
        Cree un nouvel ingredient.

        Args:
            name: Nom de l'ingredient
            unit: Unite de mesure
            category: Categorie
            prix_unitaire: Prix unitaire en centimes
            seuil_alerte: Seuil d'alerte stock
            default_supplier_id: ID du fournisseur par defaut
            notes: Notes

        Returns:
            Ingredient cree

        Raises:
            IngredientNameExistsError: Si le nom existe deja
        """
        # Verifier unicite du nom
        existing = self.ingredient_repo.get_by_name(name)
        if existing:
            raise IngredientNameExistsError(name)

        ingredient = self.ingredient_repo.create({
            "tenant_id": self.ingredient_repo.tenant_id,
            "name": name,
            "unit": unit,
            "category": category,
            "prix_unitaire": prix_unitaire,
            "seuil_alerte": seuil_alerte,
            "default_supplier_id": default_supplier_id,
            "notes": notes,
            "is_active": True,
        })

        # Creer le stock initial
        self.stock_repo.get_or_create(ingredient.id)

        return ingredient

    def get_ingredient(self, ingredient_id: int) -> RestaurantIngredient:
        """Recupere un ingredient par ID."""
        ingredient = self.ingredient_repo.get(ingredient_id)
        if not ingredient:
            raise IngredientNotFoundError(ingredient_id)
        return ingredient

    def get_active_ingredients(self) -> List[RestaurantIngredient]:
        """Recupere tous les ingredients actifs."""
        return self.ingredient_repo.get_active()

    def get_ingredients_by_category(
        self,
        category: RestaurantIngredientCategory
    ) -> List[RestaurantIngredient]:
        """Recupere les ingredients d'une categorie."""
        return self.ingredient_repo.get_by_category(category)

    def search_ingredients(self, query: str) -> List[RestaurantIngredient]:
        """Recherche ingredients par nom."""
        return self.ingredient_repo.search_by_name(query)

    def update_ingredient(
        self,
        ingredient_id: int,
        name: Optional[str] = None,
        unit: Optional[RestaurantUnit] = None,
        category: Optional[RestaurantIngredientCategory] = None,
        prix_unitaire: Optional[int] = None,
        seuil_alerte: Optional[Decimal] = None,
        default_supplier_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> RestaurantIngredient:
        """Met a jour un ingredient."""
        ingredient = self.get_ingredient(ingredient_id)

        if name is not None and name != ingredient.name:
            existing = self.ingredient_repo.get_by_name(name)
            if existing and existing.id != ingredient_id:
                raise IngredientNameExistsError(name)
            ingredient.name = name

        if unit is not None:
            ingredient.unit = unit
        if category is not None:
            ingredient.category = category
        if prix_unitaire is not None:
            ingredient.prix_unitaire = prix_unitaire
        if seuil_alerte is not None:
            ingredient.seuil_alerte = seuil_alerte
        if default_supplier_id is not None:
            ingredient.default_supplier_id = default_supplier_id
        if notes is not None:
            ingredient.notes = notes

        self.ingredient_repo.session.flush()
        return ingredient

    def update_price(self, ingredient_id: int, new_price: int) -> RestaurantIngredient:
        """
        Met a jour le prix d'un ingredient.

        Args:
            ingredient_id: ID de l'ingredient
            new_price: Nouveau prix en centimes

        Returns:
            Ingredient mis a jour
        """
        if new_price < 0:
            raise ValueError("Le prix ne peut pas etre negatif")

        ingredient = self.get_ingredient(ingredient_id)
        ingredient.prix_unitaire = new_price
        self.ingredient_repo.session.flush()
        return ingredient

    def deactivate_ingredient(self, ingredient_id: int) -> RestaurantIngredient:
        """Desactive un ingredient."""
        ingredient = self.get_ingredient(ingredient_id)
        ingredient.is_active = False
        self.ingredient_repo.session.flush()
        return ingredient

    def get_low_stock_ingredients(self) -> List[RestaurantIngredient]:
        """Recupere les ingredients en stock bas."""
        return self.ingredient_repo.get_low_stock()
