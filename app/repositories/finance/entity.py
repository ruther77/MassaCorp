"""
Repository pour FinanceEntity et FinanceEntityMember.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.finance.entity import FinanceEntity, FinanceEntityMember
from app.repositories.base import TenantAwareBaseRepository, BaseRepository


class FinanceEntityRepository(TenantAwareBaseRepository[FinanceEntity]):
    """
    Repository pour les entites financieres.
    Isolation multi-tenant obligatoire.
    """
    model = FinanceEntity

    def get_by_code(self, code: str) -> Optional[FinanceEntity]:
        """Recupere une entite par son code."""
        return (
            self._tenant_query()
            .filter(FinanceEntity.code == code)
            .first()
        )

    def get_active(self) -> List[FinanceEntity]:
        """Recupere toutes les entites actives."""
        return (
            self._tenant_query()
            .filter(FinanceEntity.is_active == True)
            .order_by(FinanceEntity.name)
            .all()
        )

    def get_with_members(self, entity_id: int) -> Optional[FinanceEntity]:
        """Recupere une entite avec ses membres."""
        return self.get(entity_id)  # Relations chargees en selectin

    def search_by_name(self, name: str) -> List[FinanceEntity]:
        """Recherche des entites par nom (case-insensitive)."""
        return (
            self._tenant_query()
            .filter(FinanceEntity.name.ilike(f"%{name}%"))
            .order_by(FinanceEntity.name)
            .all()
        )


class FinanceEntityMemberRepository(BaseRepository[FinanceEntityMember]):
    """
    Repository pour les membres d'entites.
    Pas de TenantMixin car lie a une entite qui a deja l'isolation.
    """
    model = FinanceEntityMember

    def get_by_entity_and_user(
        self,
        entity_id: int,
        user_id: int
    ) -> Optional[FinanceEntityMember]:
        """Recupere un membre par entite et utilisateur."""
        return (
            self.session.query(FinanceEntityMember)
            .filter(
                FinanceEntityMember.entity_id == entity_id,
                FinanceEntityMember.user_id == user_id
            )
            .first()
        )

    def get_by_user(self, user_id: int) -> List[FinanceEntityMember]:
        """Recupere toutes les appartenances d'un utilisateur."""
        return (
            self.session.query(FinanceEntityMember)
            .filter(FinanceEntityMember.user_id == user_id)
            .all()
        )

    def get_by_entity(self, entity_id: int) -> List[FinanceEntityMember]:
        """Recupere tous les membres d'une entite."""
        return (
            self.session.query(FinanceEntityMember)
            .filter(FinanceEntityMember.entity_id == entity_id)
            .all()
        )

    def get_default_for_user(self, user_id: int) -> Optional[FinanceEntityMember]:
        """Recupere l'entite par defaut d'un utilisateur."""
        return (
            self.session.query(FinanceEntityMember)
            .filter(
                FinanceEntityMember.user_id == user_id,
                FinanceEntityMember.is_default == True
            )
            .first()
        )

    def set_default(self, entity_id: int, user_id: int) -> bool:
        """Definit une entite comme defaut pour un utilisateur."""
        # Retirer le defaut des autres entites
        self.session.query(FinanceEntityMember).filter(
            FinanceEntityMember.user_id == user_id
        ).update({"is_default": False})

        # Definir le nouveau defaut
        member = self.get_by_entity_and_user(entity_id, user_id)
        if member:
            member.is_default = True
            self.session.flush()
            return True
        return False
