"""
Repository pour FinanceCategory.
"""
from typing import List, Optional

from app.models.finance.category import FinanceCategory, FinanceCategoryType
from app.repositories.base import TenantAwareBaseRepository


class FinanceCategoryRepository(TenantAwareBaseRepository[FinanceCategory]):
    """
    Repository pour les categories financieres.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceCategory

    def get_by_entity(self, entity_id: int) -> List[FinanceCategory]:
        """Recupere toutes les categories d'une entite."""
        return (
            self._tenant_query()
            .filter(FinanceCategory.entity_id == entity_id)
            .order_by(FinanceCategory.name)
            .all()
        )

    def get_by_type(
        self,
        entity_id: int,
        category_type: FinanceCategoryType
    ) -> List[FinanceCategory]:
        """Recupere les categories par type."""
        return (
            self._tenant_query()
            .filter(
                FinanceCategory.entity_id == entity_id,
                FinanceCategory.type == category_type
            )
            .order_by(FinanceCategory.name)
            .all()
        )

    def get_root_categories(self, entity_id: int) -> List[FinanceCategory]:
        """Recupere les categories racines (sans parent)."""
        return (
            self._tenant_query()
            .filter(
                FinanceCategory.entity_id == entity_id,
                FinanceCategory.parent_id == None
            )
            .order_by(FinanceCategory.name)
            .all()
        )

    def get_children(self, parent_id: int) -> List[FinanceCategory]:
        """Recupere les categories enfants."""
        return (
            self._tenant_query()
            .filter(FinanceCategory.parent_id == parent_id)
            .order_by(FinanceCategory.name)
            .all()
        )

    def get_tree(self, entity_id: int) -> List[FinanceCategory]:
        """
        Recupere l'arbre complet des categories.
        Les enfants sont accessibles via la relation 'children'.
        """
        return self.get_root_categories(entity_id)

    def get_by_code(self, entity_id: int, code: str) -> Optional[FinanceCategory]:
        """Recupere une categorie par son code."""
        return (
            self._tenant_query()
            .filter(
                FinanceCategory.entity_id == entity_id,
                FinanceCategory.code == code
            )
            .first()
        )

    def search_by_name(self, entity_id: int, name: str) -> List[FinanceCategory]:
        """Recherche des categories par nom."""
        return (
            self._tenant_query()
            .filter(
                FinanceCategory.entity_id == entity_id,
                FinanceCategory.name.ilike(f"%{name}%")
            )
            .order_by(FinanceCategory.name)
            .all()
        )
