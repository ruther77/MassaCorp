"""
Repository pour RestaurantStock et RestaurantStockMovement.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.restaurant.stock import (
    RestaurantStock,
    RestaurantStockMovement,
    RestaurantStockMovementType,
)
from app.repositories.base import TenantAwareBaseRepository, BaseRepository


class RestaurantStockRepository(TenantAwareBaseRepository[RestaurantStock]):
    """Repository pour le stock des ingredients."""

    model = RestaurantStock

    def get_by_ingredient(self, ingredient_id: int) -> Optional[RestaurantStock]:
        """Recupere le stock d'un ingredient."""
        stmt = select(RestaurantStock).where(
            RestaurantStock.tenant_id == self.tenant_id,
            RestaurantStock.ingredient_id == ingredient_id
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_or_create(self, ingredient_id: int) -> RestaurantStock:
        """Recupere ou cree le stock d'un ingredient."""
        stock = self.get_by_ingredient(ingredient_id)
        if not stock:
            stock = RestaurantStock(
                tenant_id=self.tenant_id,
                ingredient_id=ingredient_id,
                quantity=Decimal("0")
            )
            self.session.add(stock)
            self.session.flush()
        return stock

    def get_all_with_ingredients(self) -> List[RestaurantStock]:
        """Recupere tous les stocks avec les ingredients."""
        stmt = (
            select(RestaurantStock)
            .options(joinedload(RestaurantStock.ingredient))
            .where(RestaurantStock.tenant_id == self.tenant_id)
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_low_stock(self) -> List[RestaurantStock]:
        """Recupere les stocks bas."""
        stocks = self.get_all_with_ingredients()
        return [s for s in stocks if s.is_low]

    def get_empty_stock(self) -> List[RestaurantStock]:
        """Recupere les stocks vides."""
        stmt = (
            select(RestaurantStock)
            .options(joinedload(RestaurantStock.ingredient))
            .where(
                RestaurantStock.tenant_id == self.tenant_id,
                RestaurantStock.quantity <= 0
            )
        )
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_needing_inventory(self) -> List[RestaurantStock]:
        """Recupere les stocks necessitant un inventaire."""
        stocks = self.get_all_with_ingredients()
        return [s for s in stocks if s.needs_inventory]

    def update_quantity(
        self,
        ingredient_id: int,
        delta: Decimal,
        movement_type: RestaurantStockMovementType,
        reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> RestaurantStock:
        """
        Met a jour la quantite de stock et enregistre le mouvement.

        Args:
            ingredient_id: ID de l'ingredient
            delta: Variation de quantite (positive ou negative)
            movement_type: Type de mouvement
            reference: Reference du mouvement
            notes: Notes

        Returns:
            Stock mis a jour
        """
        stock = self.get_or_create(ingredient_id)

        # Mise a jour quantite
        stock.quantity += delta

        # Enregistrement du mouvement
        movement = RestaurantStockMovement(
            stock_id=stock.id,
            type=movement_type,
            quantity=abs(delta),
            date_mouvement=date.today(),
            reference=reference,
            notes=notes
        )
        self.session.add(movement)
        self.session.flush()

        return stock


class RestaurantStockMovementRepository(BaseRepository[RestaurantStockMovement]):
    """Repository pour les mouvements de stock."""

    model = RestaurantStockMovement

    def get_by_stock(
        self,
        stock_id: int,
        limit: int = 50
    ) -> List[RestaurantStockMovement]:
        """Recupere les mouvements d'un stock."""
        stmt = (
            select(RestaurantStockMovement)
            .where(RestaurantStockMovement.stock_id == stock_id)
            .order_by(RestaurantStockMovement.date_mouvement.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_period(
        self,
        stock_id: int,
        start_date: date,
        end_date: date
    ) -> List[RestaurantStockMovement]:
        """Recupere les mouvements sur une periode."""
        stmt = (
            select(RestaurantStockMovement)
            .where(
                RestaurantStockMovement.stock_id == stock_id,
                RestaurantStockMovement.date_mouvement >= start_date,
                RestaurantStockMovement.date_mouvement <= end_date
            )
            .order_by(RestaurantStockMovement.date_mouvement)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_type(
        self,
        stock_id: int,
        movement_type: RestaurantStockMovementType
    ) -> List[RestaurantStockMovement]:
        """Recupere les mouvements par type."""
        stmt = (
            select(RestaurantStockMovement)
            .where(
                RestaurantStockMovement.stock_id == stock_id,
                RestaurantStockMovement.type == movement_type
            )
            .order_by(RestaurantStockMovement.date_mouvement.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_recent(self, limit: int = 50) -> List[RestaurantStockMovement]:
        """Recupere les mouvements recents tous stocks confondus."""
        stmt = (
            select(RestaurantStockMovement)
            .order_by(RestaurantStockMovement.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
