"""
Repository pour RestaurantIngredient.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.restaurant.ingredient import (
    RestaurantIngredient,
    RestaurantIngredientCategory,
)
from app.repositories.base import TenantAwareBaseRepository


class RestaurantIngredientRepository(TenantAwareBaseRepository[RestaurantIngredient]):
    """Repository pour les ingredients restaurant."""

    model = RestaurantIngredient

    def get_active(self) -> List[RestaurantIngredient]:
        """Recupere tous les ingredients actifs."""
        stmt = (
            select(RestaurantIngredient)
            .where(
                RestaurantIngredient.tenant_id == self.tenant_id,
                RestaurantIngredient.is_active == True
            )
            .order_by(RestaurantIngredient.name)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_category(
        self,
        category: RestaurantIngredientCategory,
        active_only: bool = True
    ) -> List[RestaurantIngredient]:
        """Recupere les ingredients par categorie."""
        stmt = select(RestaurantIngredient).where(
            RestaurantIngredient.tenant_id == self.tenant_id,
            RestaurantIngredient.category == category
        )
        if active_only:
            stmt = stmt.where(RestaurantIngredient.is_active == True)
        stmt = stmt.order_by(RestaurantIngredient.name)
        return list(self.session.execute(stmt).scalars().all())

    def get_by_name(self, name: str) -> Optional[RestaurantIngredient]:
        """Recupere un ingredient par nom (exact)."""
        stmt = select(RestaurantIngredient).where(
            RestaurantIngredient.tenant_id == self.tenant_id,
            RestaurantIngredient.name == name
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def search_by_name(self, query: str) -> List[RestaurantIngredient]:
        """Recherche ingredients par nom (like)."""
        stmt = (
            select(RestaurantIngredient)
            .where(
                RestaurantIngredient.tenant_id == self.tenant_id,
                RestaurantIngredient.name.ilike(f"%{query}%"),
                RestaurantIngredient.is_active == True
            )
            .order_by(RestaurantIngredient.name)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_with_stock(self, ingredient_id: int) -> Optional[RestaurantIngredient]:
        """Recupere un ingredient avec son stock."""
        stmt = (
            select(RestaurantIngredient)
            .options(joinedload(RestaurantIngredient.stock))
            .where(
                RestaurantIngredient.tenant_id == self.tenant_id,
                RestaurantIngredient.id == ingredient_id
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_with_links(self, ingredient_id: int) -> Optional[RestaurantIngredient]:
        """Recupere un ingredient avec ses liens epicerie."""
        stmt = (
            select(RestaurantIngredient)
            .options(joinedload(RestaurantIngredient.epicerie_links))
            .where(
                RestaurantIngredient.tenant_id == self.tenant_id,
                RestaurantIngredient.id == ingredient_id
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_low_stock(self) -> List[RestaurantIngredient]:
        """Recupere les ingredients en stock bas."""
        # Charge tous les ingredients actifs avec stock
        stmt = (
            select(RestaurantIngredient)
            .options(joinedload(RestaurantIngredient.stock))
            .where(
                RestaurantIngredient.tenant_id == self.tenant_id,
                RestaurantIngredient.is_active == True,
                RestaurantIngredient.seuil_alerte.isnot(None)
            )
        )
        ingredients = self.session.execute(stmt).unique().scalars().all()
        # Filtre ceux en stock bas
        return [i for i in ingredients if i.stock and i.stock.is_low]
