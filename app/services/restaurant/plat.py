"""
Service pour la gestion des plats restaurant.
"""
from decimal import Decimal
from typing import List, Optional, Dict

from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory
from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient
from app.repositories.restaurant.plat import (
    RestaurantPlatRepository,
    RestaurantPlatIngredientRepository,
)
from app.repositories.restaurant.ingredient import RestaurantIngredientRepository


class PlatNotFoundError(Exception):
    """Plat non trouve."""
    def __init__(self, plat_id: int):
        self.plat_id = plat_id
        super().__init__(f"Plat {plat_id} non trouve")


class InvalidPlatError(Exception):
    """Donnees de plat invalides."""
    pass


class RestaurantPlatService:
    """
    Service pour la gestion des plats.

    Responsabilites:
    - CRUD plats
    - Gestion de la composition (ingredients)
    - Calcul des couts
    """

    def __init__(
        self,
        plat_repo: RestaurantPlatRepository,
        plat_ingredient_repo: RestaurantPlatIngredientRepository,
        ingredient_repo: RestaurantIngredientRepository,
    ):
        self.plat_repo = plat_repo
        self.plat_ingredient_repo = plat_ingredient_repo
        self.ingredient_repo = ingredient_repo

    def create_plat(
        self,
        name: str,
        prix_vente: int,
        category: RestaurantPlatCategory = RestaurantPlatCategory.PLAT,
        description: Optional[str] = None,
        is_menu: bool = False,
        image_url: Optional[str] = None,
        notes: Optional[str] = None,
        ingredients: Optional[List[Dict]] = None,
    ) -> RestaurantPlat:
        """
        Cree un nouveau plat.

        Args:
            name: Nom du plat
            prix_vente: Prix de vente en centimes
            category: Categorie du plat
            description: Description
            is_menu: Est-ce un menu compose
            image_url: URL de l'image
            notes: Notes
            ingredients: Liste des ingredients [{ingredient_id, quantite, notes}]

        Returns:
            Plat cree
        """
        if prix_vente <= 0:
            raise InvalidPlatError("Le prix de vente doit etre positif")

        plat = self.plat_repo.create({
            "tenant_id": self.plat_repo.tenant_id,
            "name": name,
            "prix_vente": prix_vente,
            "category": category,
            "description": description,
            "is_menu": is_menu,
            "image_url": image_url,
            "notes": notes,
            "is_active": True,
        })

        # Ajouter les ingredients
        if ingredients:
            for ing in ingredients:
                self._add_ingredient_to_plat(
                    plat.id,
                    ing["ingredient_id"],
                    Decimal(str(ing["quantite"])),
                    ing.get("notes")
                )

        return plat

    def get_plat(self, plat_id: int) -> RestaurantPlat:
        """Recupere un plat par ID."""
        plat = self.plat_repo.get(plat_id)
        if not plat:
            raise PlatNotFoundError(plat_id)
        return plat

    def get_plat_with_ingredients(self, plat_id: int) -> RestaurantPlat:
        """Recupere un plat avec ses ingredients."""
        plat = self.plat_repo.get_with_ingredients(plat_id)
        if not plat:
            raise PlatNotFoundError(plat_id)
        return plat

    def get_active_plats(self) -> List[RestaurantPlat]:
        """Recupere tous les plats actifs."""
        return self.plat_repo.get_active()

    def get_plats_by_category(
        self,
        category: RestaurantPlatCategory
    ) -> List[RestaurantPlat]:
        """Recupere les plats d'une categorie."""
        return self.plat_repo.get_by_category(category)

    def get_menus(self) -> List[RestaurantPlat]:
        """Recupere les menus."""
        return self.plat_repo.get_menus()

    def search_plats(self, query: str) -> List[RestaurantPlat]:
        """Recherche plats par nom."""
        return self.plat_repo.search_by_name(query)

    def update_plat(
        self,
        plat_id: int,
        name: Optional[str] = None,
        prix_vente: Optional[int] = None,
        category: Optional[RestaurantPlatCategory] = None,
        description: Optional[str] = None,
        is_menu: Optional[bool] = None,
        image_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RestaurantPlat:
        """Met a jour un plat."""
        plat = self.get_plat(plat_id)

        if name is not None:
            plat.name = name
        if prix_vente is not None:
            if prix_vente <= 0:
                raise InvalidPlatError("Le prix de vente doit etre positif")
            plat.prix_vente = prix_vente
        if category is not None:
            plat.category = category
        if description is not None:
            plat.description = description
        if is_menu is not None:
            plat.is_menu = is_menu
        if image_url is not None:
            plat.image_url = image_url
        if notes is not None:
            plat.notes = notes

        self.plat_repo.session.flush()
        return plat

    def deactivate_plat(self, plat_id: int) -> RestaurantPlat:
        """Desactive un plat."""
        plat = self.get_plat(plat_id)
        plat.is_active = False
        self.plat_repo.session.flush()
        return plat

    def _add_ingredient_to_plat(
        self,
        plat_id: int,
        ingredient_id: int,
        quantite: Decimal,
        notes: Optional[str] = None
    ) -> RestaurantPlatIngredient:
        """Ajoute un ingredient a un plat."""
        # Verifier que l'ingredient existe
        ingredient = self.ingredient_repo.get(ingredient_id)
        if not ingredient:
            raise InvalidPlatError(f"Ingredient {ingredient_id} non trouve")

        if quantite <= 0:
            raise InvalidPlatError("La quantite doit etre positive")

        plat_ingredient = self.plat_ingredient_repo.create({
            "plat_id": plat_id,
            "ingredient_id": ingredient_id,
            "quantite": quantite,
            "notes": notes,
        })
        return plat_ingredient

    def add_ingredient(
        self,
        plat_id: int,
        ingredient_id: int,
        quantite: Decimal,
        notes: Optional[str] = None
    ) -> RestaurantPlatIngredient:
        """Ajoute un ingredient a un plat existant."""
        # Verifier que le plat existe
        self.get_plat(plat_id)

        # Verifier que la ligne n'existe pas deja
        if self.plat_ingredient_repo.exists(plat_id, ingredient_id):
            raise InvalidPlatError(
                f"L'ingredient {ingredient_id} est deja dans le plat"
            )

        return self._add_ingredient_to_plat(plat_id, ingredient_id, quantite, notes)

    def update_ingredient_quantity(
        self,
        plat_id: int,
        ingredient_id: int,
        quantite: Decimal
    ) -> RestaurantPlatIngredient:
        """Met a jour la quantite d'un ingredient dans un plat."""
        if quantite <= 0:
            raise InvalidPlatError("La quantite doit etre positive")

        lines = self.plat_ingredient_repo.get_by_plat(plat_id)
        for line in lines:
            if line.ingredient_id == ingredient_id:
                line.quantite = quantite
                self.plat_repo.session.flush()
                return line

        raise InvalidPlatError(
            f"L'ingredient {ingredient_id} n'est pas dans le plat {plat_id}"
        )

    def remove_ingredient(self, plat_id: int, ingredient_id: int) -> bool:
        """Retire un ingredient d'un plat."""
        lines = self.plat_ingredient_repo.get_by_plat(plat_id)
        for line in lines:
            if line.ingredient_id == ingredient_id:
                self.plat_repo.session.delete(line)
                self.plat_repo.session.flush()
                return True
        return False

    def set_ingredients(
        self,
        plat_id: int,
        ingredients: List[Dict]
    ) -> RestaurantPlat:
        """
        Definit la liste complete des ingredients d'un plat.
        Remplace tous les ingredients existants.

        Args:
            plat_id: ID du plat
            ingredients: Liste [{ingredient_id, quantite, notes}]

        Returns:
            Plat mis a jour
        """
        # Verifier que le plat existe
        self.get_plat(plat_id)

        # Supprimer les lignes existantes
        self.plat_ingredient_repo.delete_by_plat(plat_id)

        # Ajouter les nouvelles lignes
        for ing in ingredients:
            self._add_ingredient_to_plat(
                plat_id,
                ing["ingredient_id"],
                Decimal(str(ing["quantite"])),
                ing.get("notes")
            )

        return self.get_plat_with_ingredients(plat_id)

    def calculate_cost(self, plat_id: int) -> int:
        """Calcule le cout total d'un plat en centimes."""
        plat = self.get_plat_with_ingredients(plat_id)
        return plat.cout_total

    def calculate_food_cost_ratio(self, plat_id: int) -> Decimal:
        """Calcule le ratio food cost d'un plat."""
        plat = self.get_plat_with_ingredients(plat_id)
        return plat.food_cost_ratio

    def get_unprofitable_plats(self, threshold: int = 35) -> List[RestaurantPlat]:
        """Recupere les plats avec un food cost > threshold%."""
        return self.plat_repo.get_unprofitable(threshold)
