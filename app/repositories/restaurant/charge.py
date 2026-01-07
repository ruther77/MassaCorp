"""
Repository pour RestaurantCharge.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import select, func

from app.models.restaurant.charge import (
    RestaurantCharge,
    RestaurantChargeType,
    RestaurantChargeFrequency,
)
from app.repositories.base import TenantAwareBaseRepository


class RestaurantChargeRepository(TenantAwareBaseRepository[RestaurantCharge]):
    """Repository pour les charges fixes."""

    model = RestaurantCharge

    def get_active(self) -> List[RestaurantCharge]:
        """Recupere toutes les charges actives."""
        today = date.today()
        stmt = (
            select(RestaurantCharge)
            .where(
                RestaurantCharge.tenant_id == self.tenant_id,
                RestaurantCharge.is_active == True,
                RestaurantCharge.date_debut <= today
            )
            .order_by(RestaurantCharge.type, RestaurantCharge.name)
        )
        charges = list(self.session.execute(stmt).scalars().all())
        # Filtre celles dont la date de fin n'est pas depassee
        return [c for c in charges if c.date_fin is None or c.date_fin >= today]

    def get_current(self) -> List[RestaurantCharge]:
        """Recupere les charges en cours de validite."""
        charges = self.get_active()
        return [c for c in charges if c.is_current]

    def get_by_type(
        self,
        charge_type: RestaurantChargeType,
        active_only: bool = True
    ) -> List[RestaurantCharge]:
        """Recupere les charges par type."""
        stmt = select(RestaurantCharge).where(
            RestaurantCharge.tenant_id == self.tenant_id,
            RestaurantCharge.type == charge_type
        )
        if active_only:
            stmt = stmt.where(RestaurantCharge.is_active == True)
        stmt = stmt.order_by(RestaurantCharge.name)
        return list(self.session.execute(stmt).scalars().all())

    def get_total_mensuel(self) -> int:
        """Calcule le total des charges mensuelles en centimes."""
        charges = self.get_current()
        return sum(c.montant_mensuel for c in charges)

    def get_by_frequency(
        self,
        frequency: RestaurantChargeFrequency
    ) -> List[RestaurantCharge]:
        """Recupere les charges par frequence."""
        stmt = (
            select(RestaurantCharge)
            .where(
                RestaurantCharge.tenant_id == self.tenant_id,
                RestaurantCharge.frequency == frequency,
                RestaurantCharge.is_active == True
            )
            .order_by(RestaurantCharge.name)
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_summary_by_type(self) -> dict:
        """Resume des charges par type (montant mensuel)."""
        charges = self.get_current()
        summary = {}
        for charge in charges:
            charge_type = charge.type.value
            if charge_type not in summary:
                summary[charge_type] = 0
            summary[charge_type] += charge.montant_mensuel
        return summary
