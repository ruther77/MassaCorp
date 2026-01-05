"""
Service Tenant pour MassaCorp
Logique metier pour la gestion des tenants
"""
from typing import Dict, List, Optional, Any

from app.models import Tenant
from app.repositories.tenant import TenantRepository
from app.services.exceptions import TenantNotFoundError


class TenantService:
    """
    Service pour la gestion des tenants

    Contient la logique metier pour:
    - Creation/modification/suppression tenants
    - Gestion des settings
    """

    def __init__(self, tenant_repository: TenantRepository):
        """
        Initialise le service avec le repository

        Args:
            tenant_repository: Repository pour les tenants
        """
        self.tenant_repository = tenant_repository

    def create_tenant(
        self,
        name: str,
        slug: str,
        settings: Optional[Dict] = None
    ) -> Tenant:
        """
        Cree un nouveau tenant

        Args:
            name: Nom du tenant
            slug: Slug unique
            settings: Settings optionnels

        Returns:
            Tenant cree

        Raises:
            ValueError: Si le slug existe deja
        """
        # Verifier que le slug n'existe pas
        if self.tenant_repository.slug_exists(slug.lower()):
            raise ValueError(f"Le slug {slug} existe deja")

        tenant_data = {
            "name": name,
            "slug": slug.lower(),
            "settings": settings or {},
            "is_active": True,
        }

        return self.tenant_repository.create(tenant_data)

    def get_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """
        Recupere un tenant par ID

        Args:
            tenant_id: ID du tenant

        Returns:
            Tenant trouve ou None
        """
        return self.tenant_repository.get_by_id(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """
        Recupere un tenant par slug

        Args:
            slug: Slug du tenant

        Returns:
            Tenant trouve ou None
        """
        return self.tenant_repository.get_by_slug(slug.lower())

    def update_tenant(
        self,
        tenant_id: int,
        data: Dict[str, Any]
    ) -> Optional[Tenant]:
        """
        Met a jour un tenant

        Args:
            tenant_id: ID du tenant
            data: Donnees a mettre a jour

        Returns:
            Tenant mis a jour ou None

        Raises:
            TenantNotFoundError: Si le tenant n'existe pas
        """
        tenant = self.tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id=tenant_id)

        # Filtrer les champs modifiables
        allowed_fields = {"name", "settings", "is_active"}
        filtered_data = {k: v for k, v in data.items() if k in allowed_fields}

        return self.tenant_repository.update(tenant_id, filtered_data)

    def delete_tenant(self, tenant_id: int) -> bool:
        """
        Supprime un tenant

        Args:
            tenant_id: ID du tenant

        Returns:
            True si supprime

        Raises:
            TenantNotFoundError: Si le tenant n'existe pas
        """
        tenant = self.tenant_repository.get_by_id(tenant_id)
        if tenant is None:
            raise TenantNotFoundError(tenant_id=tenant_id)

        return self.tenant_repository.delete(tenant_id)

    def list_tenants(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[Tenant]:
        """
        Liste les tenants avec pagination

        Args:
            skip: Nombre a sauter
            limit: Nombre maximum
            active_only: Seulement les tenants actifs

        Returns:
            Liste des tenants
        """
        if active_only:
            return self.tenant_repository.get_active_tenants(skip=skip, limit=limit)
        return self.tenant_repository.get_all(skip=skip, limit=limit)

    def deactivate_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """
        Desactive un tenant

        Args:
            tenant_id: ID du tenant

        Returns:
            Tenant desactive ou None
        """
        return self.tenant_repository.deactivate(tenant_id)

    def activate_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """
        Active un tenant

        Args:
            tenant_id: ID du tenant

        Returns:
            Tenant active ou None
        """
        return self.tenant_repository.activate(tenant_id)
