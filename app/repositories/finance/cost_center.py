"""
Repository pour FinanceCostCenter.
"""
from typing import List, Optional

from app.models.finance.cost_center import FinanceCostCenter
from app.repositories.base import TenantAwareBaseRepository


class FinanceCostCenterRepository(TenantAwareBaseRepository[FinanceCostCenter]):
    """
    Repository pour les centres de couts.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceCostCenter

    def get_by_entity(self, entity_id: int) -> List[FinanceCostCenter]:
        """Recupere tous les centres de couts d'une entite."""
        return (
            self._tenant_query()
            .filter(FinanceCostCenter.entity_id == entity_id)
            .order_by(FinanceCostCenter.code)
            .all()
        )

    def get_active_by_entity(self, entity_id: int) -> List[FinanceCostCenter]:
        """Recupere les centres de couts actifs d'une entite."""
        return (
            self._tenant_query()
            .filter(
                FinanceCostCenter.entity_id == entity_id,
                FinanceCostCenter.is_active == True
            )
            .order_by(FinanceCostCenter.code)
            .all()
        )

    def get_by_code(self, entity_id: int, code: str) -> Optional[FinanceCostCenter]:
        """Recupere un centre de couts par son code."""
        return (
            self._tenant_query()
            .filter(
                FinanceCostCenter.entity_id == entity_id,
                FinanceCostCenter.code == code
            )
            .first()
        )

    def search_by_name(self, entity_id: int, name: str) -> List[FinanceCostCenter]:
        """Recherche des centres de couts par nom."""
        return (
            self._tenant_query()
            .filter(
                FinanceCostCenter.entity_id == entity_id,
                FinanceCostCenter.name.ilike(f"%{name}%")
            )
            .order_by(FinanceCostCenter.name)
            .all()
        )
