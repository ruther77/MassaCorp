"""
Repository pour FinanceVendor.
"""
from typing import List, Optional

from app.models.finance.vendor import FinanceVendor
from app.repositories.base import TenantAwareBaseRepository


class FinanceVendorRepository(TenantAwareBaseRepository[FinanceVendor]):
    """
    Repository pour les fournisseurs.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceVendor

    def get_by_entity(self, entity_id: int) -> List[FinanceVendor]:
        """Recupere tous les fournisseurs d'une entite."""
        return (
            self._tenant_query()
            .filter(FinanceVendor.entity_id == entity_id)
            .order_by(FinanceVendor.name)
            .all()
        )

    def get_active_by_entity(self, entity_id: int) -> List[FinanceVendor]:
        """Recupere les fournisseurs actifs d'une entite."""
        return (
            self._tenant_query()
            .filter(
                FinanceVendor.entity_id == entity_id,
                FinanceVendor.is_active == True
            )
            .order_by(FinanceVendor.name)
            .all()
        )

    def get_by_siret(self, siret: str) -> Optional[FinanceVendor]:
        """Recupere un fournisseur par SIRET."""
        return (
            self._tenant_query()
            .filter(FinanceVendor.siret == siret)
            .first()
        )

    def get_by_code(self, entity_id: int, code: str) -> Optional[FinanceVendor]:
        """Recupere un fournisseur par code."""
        return (
            self._tenant_query()
            .filter(
                FinanceVendor.entity_id == entity_id,
                FinanceVendor.code == code
            )
            .first()
        )

    def search_by_name(self, entity_id: int, name: str) -> List[FinanceVendor]:
        """Recherche des fournisseurs par nom."""
        return (
            self._tenant_query()
            .filter(
                FinanceVendor.entity_id == entity_id,
                FinanceVendor.name.ilike(f"%{name}%")
            )
            .order_by(FinanceVendor.name)
            .all()
        )

    def get_with_invoices(self, vendor_id: int) -> Optional[FinanceVendor]:
        """Recupere un fournisseur avec ses factures."""
        return self.get(vendor_id)  # Relations chargees via dynamic
