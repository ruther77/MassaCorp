"""
Repositories RBAC pour MassaCorp API
Gestion des Roles, Permissions et Assignations
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.repositories.base import BaseRepository
from app.models.rbac import Permission, Role, RolePermission, UserRole


class PermissionRepository(BaseRepository[Permission]):
    """Repository pour les permissions."""

    model = Permission

    def get_by_code(self, code: str) -> Optional[Permission]:
        """
        Recupere une permission par son code unique.

        Args:
            code: Code de la permission (ex: users.read)

        Returns:
            Permission ou None
        """
        return (
            self.session.query(Permission)
            .filter(Permission.code == code)
            .first()
        )

    def get_by_resource(
        self,
        resource: str,
        only_active: bool = True
    ) -> List[Permission]:
        """
        Recupere toutes les permissions d'une ressource.

        Args:
            resource: Ressource (ex: users, tenants)
            only_active: Filtrer les permissions actives uniquement

        Returns:
            Liste des permissions
        """
        query = self.session.query(Permission).filter(Permission.resource == resource)
        if only_active:
            query = query.filter(Permission.is_active == True)
        return query.all()

    def get_active_permissions(self) -> List[Permission]:
        """Recupere toutes les permissions actives."""
        return (
            self.session.query(Permission)
            .filter(Permission.is_active == True)
            .order_by(Permission.resource, Permission.action)
            .all()
        )

    def get_by_codes(self, codes: List[str]) -> List[Permission]:
        """
        Recupere plusieurs permissions par leurs codes.

        Args:
            codes: Liste de codes

        Returns:
            Liste des permissions trouvees
        """
        if not codes:
            return []
        return (
            self.session.query(Permission)
            .filter(Permission.code.in_(codes))
            .filter(Permission.is_active == True)
            .all()
        )

    def create_permission(
        self,
        code: str,
        name: str,
        resource: str,
        action: str,
        description: Optional[str] = None
    ) -> Permission:
        """
        Cree une nouvelle permission.

        Args:
            code: Code unique (ex: users.read)
            name: Nom lisible
            resource: Ressource concernee
            action: Action sur la ressource
            description: Description optionnelle

        Returns:
            Permission creee
        """
        permission = Permission(
            code=code,
            name=name,
            resource=resource,
            action=action,
            description=description,
            is_active=True
        )
        self.session.add(permission)
        self.session.flush()
        return permission

    def bulk_create(self, permissions_data: List[Dict]) -> List[Permission]:
        """
        Cree plusieurs permissions en une fois.

        Args:
            permissions_data: Liste de dicts avec code, name, resource, action

        Returns:
            Liste des permissions creees
        """
        permissions = []
        for data in permissions_data:
            # Eviter les doublons
            existing = self.get_by_code(data["code"])
            if not existing:
                perm = Permission(**data, is_active=True)
                self.session.add(perm)
                permissions.append(perm)
        self.session.flush()
        return permissions


class RoleRepository(BaseRepository[Role]):
    """Repository pour les roles."""

    model = Role

    def get_by_code(
        self,
        code: str,
        tenant_id: Optional[int] = None
    ) -> Optional[Role]:
        """
        Recupere un role par son code.

        Args:
            code: Code du role
            tenant_id: ID du tenant (None = role global uniquement)

        Returns:
            Role ou None
        """
        query = self.session.query(Role).filter(Role.code == code)

        if tenant_id is not None:
            # Chercher role tenant-specific OU global
            query = query.filter(
                or_(
                    Role.tenant_id == tenant_id,
                    Role.tenant_id.is_(None)
                )
            )
        else:
            # Uniquement roles globaux
            query = query.filter(Role.tenant_id.is_(None))

        return query.first()

    def get_tenant_roles(
        self,
        tenant_id: int,
        include_global: bool = True,
        only_active: bool = True
    ) -> List[Role]:
        """
        Recupere les roles disponibles pour un tenant.

        Args:
            tenant_id: ID du tenant
            include_global: Inclure les roles globaux
            only_active: Filtrer les roles actifs uniquement

        Returns:
            Liste des roles
        """
        if include_global:
            query = self.session.query(Role).filter(
                or_(
                    Role.tenant_id == tenant_id,
                    Role.tenant_id.is_(None)
                )
            )
        else:
            query = self.session.query(Role).filter(Role.tenant_id == tenant_id)

        if only_active:
            query = query.filter(Role.is_active == True)

        return query.options(joinedload(Role.permissions)).all()

    def get_global_roles(self, only_active: bool = True) -> List[Role]:
        """
        Recupere tous les roles globaux.

        Args:
            only_active: Filtrer les roles actifs uniquement

        Returns:
            Liste des roles globaux
        """
        query = self.session.query(Role).filter(Role.tenant_id.is_(None))
        if only_active:
            query = query.filter(Role.is_active == True)
        return query.all()

    def create_role(
        self,
        code: str,
        name: str,
        tenant_id: Optional[int] = None,
        description: Optional[str] = None,
        is_system: bool = False
    ) -> Role:
        """
        Cree un nouveau role.

        Args:
            code: Code unique du role
            name: Nom lisible
            tenant_id: Tenant proprietaire (None = global)
            description: Description optionnelle
            is_system: Role systeme non modifiable

        Returns:
            Role cree
        """
        role = Role(
            code=code,
            name=name,
            tenant_id=tenant_id,
            description=description,
            is_system=is_system,
            is_active=True
        )
        self.session.add(role)
        self.session.flush()
        return role

    def add_permission_to_role(
        self,
        role_id: int,
        permission_id: int
    ) -> RolePermission:
        """
        Ajoute une permission a un role.

        Args:
            role_id: ID du role
            permission_id: ID de la permission

        Returns:
            RolePermission cree
        """
        # Verifier si deja associe
        existing = (
            self.session.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
            .first()
        )
        if existing:
            return existing

        rp = RolePermission(role_id=role_id, permission_id=permission_id)
        self.session.add(rp)
        self.session.flush()
        return rp

    def remove_permission_from_role(
        self,
        role_id: int,
        permission_id: int
    ) -> bool:
        """
        Retire une permission d'un role.

        Args:
            role_id: ID du role
            permission_id: ID de la permission

        Returns:
            True si supprime, False si non trouve
        """
        rp = (
            self.session.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            )
            .first()
        )
        if rp:
            self.session.delete(rp)
            self.session.flush()
            return True
        return False

    def set_role_permissions(
        self,
        role_id: int,
        permission_ids: List[int]
    ) -> None:
        """
        Definit les permissions d'un role (remplace toutes les existantes).

        Args:
            role_id: ID du role
            permission_ids: Liste des IDs de permissions
        """
        # Supprimer les permissions existantes
        self.session.query(RolePermission).filter(
            RolePermission.role_id == role_id
        ).delete()

        # Ajouter les nouvelles
        for perm_id in permission_ids:
            rp = RolePermission(role_id=role_id, permission_id=perm_id)
            self.session.add(rp)

        self.session.flush()

    def get_role_with_permissions(self, role_id: int) -> Optional[Role]:
        """
        Recupere un role avec ses permissions chargees.

        Args:
            role_id: ID du role

        Returns:
            Role avec permissions ou None
        """
        return (
            self.session.query(Role)
            .options(
                joinedload(Role.permissions).joinedload(RolePermission.permission)
            )
            .filter(Role.id == role_id)
            .first()
        )


class UserRoleRepository(BaseRepository[UserRole]):
    """Repository pour les assignations utilisateur-role."""

    model = UserRole

    def get_user_roles(
        self,
        user_id: int,
        include_expired: bool = False
    ) -> List[UserRole]:
        """
        Recupere les roles d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            include_expired: Inclure les assignations expirees

        Returns:
            Liste des UserRole
        """
        query = (
            self.session.query(UserRole)
            .options(
                joinedload(UserRole.role).joinedload(Role.permissions)
            )
            .filter(UserRole.user_id == user_id)
        )

        if not include_expired:
            query = query.filter(
                or_(
                    UserRole.expires_at.is_(None),
                    UserRole.expires_at > datetime.now(timezone.utc)
                )
            )

        return query.all()

    def get_user_permission_codes(self, user_id: int) -> Set[str]:
        """
        Recupere tous les codes de permission d'un utilisateur.

        Collecte les permissions de tous ses roles actifs.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Set de codes de permission
        """
        user_roles = self.get_user_roles(user_id, include_expired=False)
        permissions: Set[str] = set()

        for ur in user_roles:
            if ur.role and ur.role.is_active:
                for rp in ur.role.permissions:
                    if rp.permission and rp.permission.is_active:
                        permissions.add(rp.permission.code)

        return permissions

    def user_has_permission(self, user_id: int, permission_code: str) -> bool:
        """
        Verifie si un utilisateur a une permission specifique.

        Args:
            user_id: ID de l'utilisateur
            permission_code: Code de la permission

        Returns:
            True si permission accordee
        """
        permissions = self.get_user_permission_codes(user_id)
        return permission_code in permissions

    def user_has_any_permission(
        self,
        user_id: int,
        permission_codes: List[str]
    ) -> bool:
        """
        Verifie si un utilisateur a au moins une des permissions.

        Args:
            user_id: ID de l'utilisateur
            permission_codes: Liste de codes de permission

        Returns:
            True si au moins une permission accordee
        """
        user_perms = self.get_user_permission_codes(user_id)
        return bool(user_perms & set(permission_codes))

    def user_has_all_permissions(
        self,
        user_id: int,
        permission_codes: List[str]
    ) -> bool:
        """
        Verifie si un utilisateur a toutes les permissions.

        Args:
            user_id: ID de l'utilisateur
            permission_codes: Liste de codes de permission

        Returns:
            True si toutes les permissions accordees
        """
        user_perms = self.get_user_permission_codes(user_id)
        return set(permission_codes).issubset(user_perms)

    def assign_role(
        self,
        user_id: int,
        role_id: int,
        assigned_by: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ) -> UserRole:
        """
        Assigne un role a un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            role_id: ID du role
            assigned_by: ID de l'utilisateur qui assigne
            expires_at: Date d'expiration optionnelle

        Returns:
            UserRole cree
        """
        # Verifier si deja assigne
        existing = (
            self.session.query(UserRole)
            .filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            )
            .first()
        )

        if existing:
            # Mettre a jour l'expiration si fournie
            if expires_at is not None:
                existing.expires_at = expires_at
            self.session.flush()
            return existing

        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            expires_at=expires_at
        )
        self.session.add(user_role)
        self.session.flush()
        return user_role

    def revoke_role(self, user_id: int, role_id: int) -> bool:
        """
        Revoque un role d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            role_id: ID du role

        Returns:
            True si revoque, False si non trouve
        """
        user_role = (
            self.session.query(UserRole)
            .filter(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            )
            .first()
        )

        if user_role:
            self.session.delete(user_role)
            self.session.flush()
            return True
        return False

    def revoke_all_roles(self, user_id: int) -> int:
        """
        Revoque tous les roles d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de roles revoques
        """
        count = (
            self.session.query(UserRole)
            .filter(UserRole.user_id == user_id)
            .delete()
        )
        self.session.flush()
        return count

    def get_users_with_role(
        self,
        role_id: int,
        tenant_id: Optional[int] = None
    ) -> List[UserRole]:
        """
        Recupere tous les utilisateurs ayant un role.

        Args:
            role_id: ID du role
            tenant_id: Filtrer par tenant (optionnel)

        Returns:
            Liste des UserRole
        """
        query = (
            self.session.query(UserRole)
            .options(joinedload(UserRole.user))
            .filter(UserRole.role_id == role_id)
            .filter(
                or_(
                    UserRole.expires_at.is_(None),
                    UserRole.expires_at > datetime.now(timezone.utc)
                )
            )
        )

        if tenant_id is not None:
            query = query.join(UserRole.user).filter(
                UserRole.user.has(tenant_id=tenant_id)
            )

        return query.all()

    def get_user_role_by_id(self, user_role_id: int) -> Optional[UserRole]:
        """
        Recupere une assignation par son ID.

        Args:
            user_role_id: ID de l'assignation

        Returns:
            UserRole ou None
        """
        return (
            self.session.query(UserRole)
            .options(
                joinedload(UserRole.role),
                joinedload(UserRole.user)
            )
            .filter(UserRole.id == user_role_id)
            .first()
        )

    def cleanup_expired(self) -> int:
        """
        Supprime les assignations expirees.

        Returns:
            Nombre d'assignations supprimees
        """
        count = (
            self.session.query(UserRole)
            .filter(
                UserRole.expires_at.isnot(None),
                UserRole.expires_at < datetime.now(timezone.utc)
            )
            .delete()
        )
        self.session.flush()
        return count
