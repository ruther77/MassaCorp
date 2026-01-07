"""
Repository pour RestaurantEpicerieLink.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.restaurant.epicerie_link import RestaurantEpicerieLink
from app.repositories.base import TenantAwareBaseRepository


class RestaurantEpicerieLinkRepository(TenantAwareBaseRepository[RestaurantEpicerieLink]):
    """Repository pour les liens ingredient-produit epicerie."""

    model = RestaurantEpicerieLink

    def get_by_ingredient(self, ingredient_id: int) -> List[RestaurantEpicerieLink]:
        """Recupere tous les liens pour un ingredient."""
        stmt = (
            select(RestaurantEpicerieLink)
            .where(
                RestaurantEpicerieLink.tenant_id == self.tenant_id,
                RestaurantEpicerieLink.ingredient_id == ingredient_id
            )
            .order_by(RestaurantEpicerieLink.is_primary.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_primary_by_ingredient(
        self,
        ingredient_id: int
    ) -> Optional[RestaurantEpicerieLink]:
        """Recupere le lien principal pour un ingredient."""
        stmt = select(RestaurantEpicerieLink).where(
            RestaurantEpicerieLink.tenant_id == self.tenant_id,
            RestaurantEpicerieLink.ingredient_id == ingredient_id,
            RestaurantEpicerieLink.is_primary == True
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_produit(self, produit_id: int) -> List[RestaurantEpicerieLink]:
        """Recupere tous les liens pour un produit epicerie."""
        stmt = (
            select(RestaurantEpicerieLink)
            .options(joinedload(RestaurantEpicerieLink.ingredient))
            .where(
                RestaurantEpicerieLink.tenant_id == self.tenant_id,
                RestaurantEpicerieLink.produit_id == produit_id
            )
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def exists(self, ingredient_id: int, produit_id: int) -> bool:
        """Verifie si un lien existe."""
        stmt = select(RestaurantEpicerieLink).where(
            RestaurantEpicerieLink.tenant_id == self.tenant_id,
            RestaurantEpicerieLink.ingredient_id == ingredient_id,
            RestaurantEpicerieLink.produit_id == produit_id
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def set_primary(self, link_id: int) -> Optional[RestaurantEpicerieLink]:
        """
        Definit un lien comme principal.
        Desactive is_primary sur les autres liens du meme ingredient.
        """
        link = self.get(link_id)
        if not link:
            return None

        # Desactive les autres liens
        other_links = self.get_by_ingredient(link.ingredient_id)
        for other in other_links:
            if other.id != link_id:
                other.is_primary = False

        # Active celui-ci
        link.is_primary = True
        self.session.flush()

        return link
