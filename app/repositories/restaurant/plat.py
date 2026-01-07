"""
Repository pour RestaurantPlat.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.restaurant.plat import RestaurantPlat, RestaurantPlatCategory
from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient
from app.repositories.base import TenantAwareBaseRepository, BaseRepository


class RestaurantPlatRepository(TenantAwareBaseRepository[RestaurantPlat]):
    """Repository pour les plats."""

    model = RestaurantPlat

    def get_active(self) -> List[RestaurantPlat]:
        """Recupere tous les plats actifs avec leurs ingredients."""
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.is_active == True
            )
            .order_by(RestaurantPlat.category, RestaurantPlat.name)
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_by_category(
        self,
        category: RestaurantPlatCategory,
        active_only: bool = True
    ) -> List[RestaurantPlat]:
        """Recupere les plats par categorie avec leurs ingredients."""
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.category == category
            )
        )
        if active_only:
            stmt = stmt.where(RestaurantPlat.is_active == True)
        stmt = stmt.order_by(RestaurantPlat.name)
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_menus(self, active_only: bool = True) -> List[RestaurantPlat]:
        """Recupere les menus (pas les plats simples) avec leurs ingredients."""
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.is_menu == True
            )
        )
        if active_only:
            stmt = stmt.where(RestaurantPlat.is_active == True)
        stmt = stmt.order_by(RestaurantPlat.name)
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_with_ingredients(self, plat_id: int) -> Optional[RestaurantPlat]:
        """Recupere un plat avec ses ingredients."""
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.id == plat_id
            )
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def search_by_name(self, query: str) -> List[RestaurantPlat]:
        """Recherche plats par nom avec leurs ingredients."""
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.name.ilike(f"%{query}%"),
                RestaurantPlat.is_active == True
            )
            .order_by(RestaurantPlat.name)
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_unprofitable(self, threshold: int = 35) -> List[RestaurantPlat]:
        """Recupere les plats non rentables (food cost > threshold)."""
        # Charge tous les plats avec ingredients
        stmt = (
            select(RestaurantPlat)
            .options(
                joinedload(RestaurantPlat.ingredients)
                .joinedload(RestaurantPlatIngredient.ingredient)
            )
            .where(
                RestaurantPlat.tenant_id == self.tenant_id,
                RestaurantPlat.is_active == True
            )
        )
        plats = self.session.execute(stmt).unique().scalars().all()
        # Filtre ceux non rentables
        return [p for p in plats if p.food_cost_ratio > threshold]


class RestaurantPlatIngredientRepository(BaseRepository[RestaurantPlatIngredient]):
    """Repository pour les compositions de plats."""

    model = RestaurantPlatIngredient

    def get_by_plat(self, plat_id: int) -> List[RestaurantPlatIngredient]:
        """Recupere toutes les lignes d'un plat."""
        stmt = (
            select(RestaurantPlatIngredient)
            .options(joinedload(RestaurantPlatIngredient.ingredient))
            .where(RestaurantPlatIngredient.plat_id == plat_id)
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_by_ingredient(self, ingredient_id: int) -> List[RestaurantPlatIngredient]:
        """Recupere tous les plats utilisant un ingredient."""
        stmt = (
            select(RestaurantPlatIngredient)
            .options(joinedload(RestaurantPlatIngredient.plat))
            .where(RestaurantPlatIngredient.ingredient_id == ingredient_id)
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def delete_by_plat(self, plat_id: int) -> int:
        """Supprime toutes les lignes d'un plat."""
        lines = self.get_by_plat(plat_id)
        count = len(lines)
        for line in lines:
            self.session.delete(line)
        self.session.flush()
        return count

    def exists(self, plat_id: int, ingredient_id: int) -> bool:
        """Verifie si une ligne existe."""
        stmt = select(RestaurantPlatIngredient).where(
            RestaurantPlatIngredient.plat_id == plat_id,
            RestaurantPlatIngredient.ingredient_id == ingredient_id
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None
