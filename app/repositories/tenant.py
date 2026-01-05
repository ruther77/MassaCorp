"""
Repository pour les Tenants
Gestion multi-tenant de MassaCorp
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import Tenant
from app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """
    Repository pour les operations sur les Tenants

    Fournit des methodes specifiques pour la gestion
    des tenants dans un contexte multi-tenant
    """

    model = Tenant

    def __init__(self, session: Session):
        """Initialise le repository avec une session DB"""
        super().__init__(session)

    def get_by_slug(self, slug: str) -> Optional[Tenant]:
        """
        Recupere un tenant par son slug

        Args:
            slug: Slug unique du tenant

        Returns:
            Le tenant trouve ou None
        """
        return (
            self.session.query(self.model)
            .filter(self.model.slug == slug.lower())
            .first()
        )

    def get_active_tenants(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tenant]:
        """
        Recupere tous les tenants actifs

        Args:
            skip: Nombre de tenants a sauter
            limit: Nombre maximum de tenants

        Returns:
            Liste des tenants actifs
        """
        return (
            self.session.query(self.model)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_name(self, name: str) -> Optional[Tenant]:
        """
        Recupere un tenant par son nom

        Args:
            name: Nom du tenant

        Returns:
            Le tenant trouve ou None
        """
        return (
            self.session.query(self.model)
            .filter(self.model.name == name)
            .first()
        )

    def slug_exists(self, slug: str) -> bool:
        """
        Verifie si un slug existe deja

        Args:
            slug: Slug a verifier

        Returns:
            True si existe, False sinon
        """
        return self.get_by_slug(slug) is not None

    def count_active(self) -> int:
        """
        Compte le nombre de tenants actifs

        Returns:
            Nombre de tenants actifs
        """
        from sqlalchemy import func
        return (
            self.session.query(func.count(self.model.id))
            .filter(self.model.is_active == True)
            .scalar() or 0
        )

    def deactivate(self, id: int) -> Optional[Tenant]:
        """
        Desactive un tenant

        Args:
            id: ID du tenant

        Returns:
            Le tenant desactive ou None
        """
        return self.update(id, {"is_active": False})

    def activate(self, id: int) -> Optional[Tenant]:
        """
        Active un tenant

        Args:
            id: ID du tenant

        Returns:
            Le tenant active ou None
        """
        return self.update(id, {"is_active": True})
