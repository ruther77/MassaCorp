"""
Repository pour RestaurantConsumption.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.models.restaurant.consumption import RestaurantConsumption, RestaurantConsumptionType
from app.repositories.base import TenantAwareBaseRepository


class RestaurantConsumptionRepository(TenantAwareBaseRepository[RestaurantConsumption]):
    """Repository pour les consommations de plats."""

    model = RestaurantConsumption

    def get_by_period(
        self,
        start_date: date,
        end_date: date,
        consumption_type: Optional[RestaurantConsumptionType] = None
    ) -> List[RestaurantConsumption]:
        """Recupere les consommations sur une periode, optionnellement filtrees par type."""
        stmt = (
            select(RestaurantConsumption)
            .options(joinedload(RestaurantConsumption.plat))
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date >= start_date,
                RestaurantConsumption.date <= end_date
            )
        )
        if consumption_type is not None:
            stmt = stmt.where(RestaurantConsumption.type == consumption_type)
        stmt = stmt.order_by(RestaurantConsumption.date.desc())
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_by_plat(
        self,
        plat_id: int,
        limit: int = 100
    ) -> List[RestaurantConsumption]:
        """Recupere les consommations d'un plat."""
        stmt = (
            select(RestaurantConsumption)
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.plat_id == plat_id
            )
            .order_by(RestaurantConsumption.date.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_losses(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[RestaurantConsumption]:
        """Recupere les pertes."""
        stmt = (
            select(RestaurantConsumption)
            .options(joinedload(RestaurantConsumption.plat))
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.type == RestaurantConsumptionType.PERTE
            )
        )
        if start_date:
            stmt = stmt.where(RestaurantConsumption.date >= start_date)
        if end_date:
            stmt = stmt.where(RestaurantConsumption.date <= end_date)
        stmt = stmt.order_by(RestaurantConsumption.date.desc())
        return list(self.session.execute(stmt).unique().scalars().all())

    def get_total_cost_by_period(
        self,
        start_date: date,
        end_date: date
    ) -> int:
        """Calcule le cout total des consommations sur une periode."""
        stmt = (
            select(
                func.coalesce(
                    func.sum(RestaurantConsumption.quantite * RestaurantConsumption.cout),
                    0
                )
            )
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date >= start_date,
                RestaurantConsumption.date <= end_date
            )
        )
        return self.session.execute(stmt).scalar() or 0

    def get_total_loss_cost(
        self,
        start_date: date,
        end_date: date
    ) -> int:
        """Calcule le cout total des pertes sur une periode."""
        stmt = (
            select(
                func.coalesce(
                    func.sum(RestaurantConsumption.quantite * RestaurantConsumption.cout),
                    0
                )
            )
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date >= start_date,
                RestaurantConsumption.date <= end_date,
                RestaurantConsumption.type == RestaurantConsumptionType.PERTE
            )
        )
        return self.session.execute(stmt).scalar() or 0

    def get_plat_count_by_period(
        self,
        plat_id: int,
        start_date: date,
        end_date: date
    ) -> int:
        """Compte le nombre de consommations d'un plat sur une periode."""
        stmt = (
            select(func.coalesce(func.sum(RestaurantConsumption.quantite), 0))
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.plat_id == plat_id,
                RestaurantConsumption.date >= start_date,
                RestaurantConsumption.date <= end_date,
                RestaurantConsumption.type != RestaurantConsumptionType.PERTE
            )
        )
        return self.session.execute(stmt).scalar() or 0

    def get_sales_by_plat(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[tuple]:
        """
        Recupere les ventes par plat (best sellers).
        Returns: List of (plat_id, total_quantity, total_revenue)
        """
        stmt = (
            select(
                RestaurantConsumption.plat_id,
                func.sum(RestaurantConsumption.quantite).label("total_qty"),
                func.sum(RestaurantConsumption.quantite * RestaurantConsumption.prix_vente).label("total_revenue")
            )
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date >= start_date,
                RestaurantConsumption.date <= end_date,
                RestaurantConsumption.type == RestaurantConsumptionType.VENTE
            )
            .group_by(RestaurantConsumption.plat_id)
            .order_by(func.sum(RestaurantConsumption.quantite).desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).all())

    def get_daily_stats(
        self,
        target_date: date
    ) -> dict:
        """
        Recupere les stats d'une journee.
        Returns: Dict avec total_ventes, total_pertes, total_revenue, total_cost
        """
        # Ventes
        sales_stmt = (
            select(
                func.coalesce(func.sum(RestaurantConsumption.quantite), 0).label("qty"),
                func.coalesce(func.sum(RestaurantConsumption.quantite * RestaurantConsumption.prix_vente), 0).label("revenue"),
                func.coalesce(func.sum(RestaurantConsumption.quantite * RestaurantConsumption.cout), 0).label("cost")
            )
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date == target_date,
                RestaurantConsumption.type == RestaurantConsumptionType.VENTE
            )
        )
        sales = self.session.execute(sales_stmt).one()

        # Pertes
        loss_stmt = (
            select(
                func.coalesce(func.sum(RestaurantConsumption.quantite), 0).label("qty"),
                func.coalesce(func.sum(RestaurantConsumption.quantite * RestaurantConsumption.cout), 0).label("cost")
            )
            .where(
                RestaurantConsumption.tenant_id == self.tenant_id,
                RestaurantConsumption.date == target_date,
                RestaurantConsumption.type == RestaurantConsumptionType.PERTE
            )
        )
        losses = self.session.execute(loss_stmt).one()

        return {
            "sales_count": sales.qty,
            "sales_revenue": sales.revenue,
            "sales_cost": sales.cost,
            "loss_count": losses.qty,
            "loss_cost": losses.cost,
        }
