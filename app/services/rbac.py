"""
Service RBAC pour MassaCorp API
Gestion des Roles, Permissions et Controle d'Acces

Ce service fournit:
- Verification des permissions utilisateur
- Gestion des roles et permissions
- Assignation de roles aux utilisateurs
- Permissions par defaut et systeme
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from app.core.config import get_settings
from app.repositories.rbac import PermissionRepository, RoleRepository, UserRoleRepository
from app.services.exceptions import ServiceException

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# Exceptions RBAC
# ============================================================================

class RBACException(ServiceException):
    """Exception de base pour les erreurs RBAC."""
    pass


class PermissionDeniedError(RBACException):
    """Permission refusee."""

    def __init__(self, permission: str = None, message: str = None):
        if message:
            msg = message
        elif permission:
            msg = f"Permission refusee: {permission}"
        else:
            msg = "Permission refusee"
        super().__init__(message=msg, code="PERMISSION_DENIED")
        self.permission = permission


class RoleNotFoundError(RBACException):
    """Role non trouve."""

    def __init__(self, role_id: int = None, role_code: str = None):
        if role_code:
            message = f"Role avec code '{role_code}' non trouve"
        else:
            message = f"Role avec ID {role_id} non trouve"
        super().__init__(message=message, code="ROLE_NOT_FOUND")
        self.role_id = role_id
        self.role_code = role_code


class PermissionNotFoundError(RBACException):
    """Permission non trouvee."""

    def __init__(self, permission_code: str):
        super().__init__(
            message=f"Permission '{permission_code}' non trouvee",
            code="PERMISSION_NOT_FOUND"
        )
        self.permission_code = permission_code


class RoleAlreadyExistsError(RBACException):
    """Role avec ce code existe deja."""

    def __init__(self, code: str, tenant_id: Optional[int] = None):
        tenant_info = f" pour tenant {tenant_id}" if tenant_id else " (global)"
        super().__init__(
            message=f"Role '{code}' existe deja{tenant_info}",
            code="ROLE_EXISTS"
        )
        self.role_code = code
        self.tenant_id = tenant_id


class SystemRoleModificationError(RBACException):
    """Tentative de modification d'un role systeme."""

    def __init__(self, role_code: str):
        super().__init__(
            message=f"Le role systeme '{role_code}' ne peut pas etre modifie",
            code="SYSTEM_ROLE_MODIFICATION"
        )
        self.role_code = role_code


# ============================================================================
# Permissions par defaut
# ============================================================================

DEFAULT_PERMISSIONS = [
    # Users
    {"code": "users.read", "name": "Lecture utilisateurs", "resource": "users", "action": "read"},
    {"code": "users.write", "name": "Modification utilisateurs", "resource": "users", "action": "write"},
    {"code": "users.delete", "name": "Suppression utilisateurs", "resource": "users", "action": "delete"},
    {"code": "users.manage", "name": "Gestion complete utilisateurs", "resource": "users", "action": "manage"},

    # Tenants
    {"code": "tenants.read", "name": "Lecture tenants", "resource": "tenants", "action": "read"},
    {"code": "tenants.write", "name": "Modification tenants", "resource": "tenants", "action": "write"},
    {"code": "tenants.manage", "name": "Gestion complete tenants", "resource": "tenants", "action": "manage"},

    # Roles
    {"code": "roles.read", "name": "Lecture roles", "resource": "roles", "action": "read"},
    {"code": "roles.write", "name": "Modification roles", "resource": "roles", "action": "write"},
    {"code": "roles.assign", "name": "Assignation roles", "resource": "roles", "action": "assign"},
    {"code": "roles.manage", "name": "Gestion complete roles", "resource": "roles", "action": "manage"},

    # Audit
    {"code": "audit.read", "name": "Lecture logs audit", "resource": "audit", "action": "read"},
    {"code": "audit.export", "name": "Export logs audit", "resource": "audit", "action": "export"},

    # Sessions
    {"code": "sessions.read", "name": "Lecture sessions", "resource": "sessions", "action": "read"},
    {"code": "sessions.revoke", "name": "Revocation sessions", "resource": "sessions", "action": "revoke"},

    # Reports
    {"code": "reports.read", "name": "Lecture rapports", "resource": "reports", "action": "read"},
    {"code": "reports.export", "name": "Export rapports", "resource": "reports", "action": "export"},

    # Settings
    {"code": "settings.read", "name": "Lecture parametres", "resource": "settings", "action": "read"},
    {"code": "settings.write", "name": "Modification parametres", "resource": "settings", "action": "write"},
]

DEFAULT_ROLES = [
    {
        "code": "admin",
        "name": "Administrateur",
        "description": "Acces complet a toutes les fonctionnalites",
        "is_system": True,
        "permissions": ["users.manage", "tenants.manage", "roles.manage", "audit.read",
                       "audit.export", "sessions.read", "sessions.revoke", "reports.read",
                       "reports.export", "settings.read", "settings.write"],
    },
    {
        "code": "manager",
        "name": "Manager",
        "description": "Gestion des utilisateurs et rapports",
        "is_system": True,
        "permissions": ["users.read", "users.write", "roles.read", "roles.assign",
                       "audit.read", "sessions.read", "reports.read", "reports.export"],
    },
    {
        "code": "viewer",
        "name": "Lecteur",
        "description": "Acces en lecture seule",
        "is_system": True,
        "permissions": ["users.read", "roles.read", "reports.read"],
    },
]


# ============================================================================
# Service RBAC
# ============================================================================

class RBACService:
    """
    Service de gestion RBAC.

    Fournit les operations de controle d'acces et de gestion des roles.
    """

    def __init__(
        self,
        permission_repository: PermissionRepository,
        role_repository: RoleRepository,
        user_role_repository: UserRoleRepository
    ):
        """
        Initialise le service RBAC.

        Args:
            permission_repository: Repository des permissions
            role_repository: Repository des roles
            user_role_repository: Repository des assignations
        """
        self.permission_repo = permission_repository
        self.role_repo = role_repository
        self.user_role_repo = user_role_repository

    # =========================================================================
    # Verification des permissions
    # =========================================================================

    def is_enabled(self) -> bool:
        """
        Verifie si le RBAC est active.

        SECURITE: En production (DEBUG=False), RBAC ne peut PAS etre desactive.
        Cela empeche une desactivation accidentelle qui donnerait acces a tout.
        """
        if not settings.RBAC_ENABLED:
            # SECURITE: Empecher la desactivation en production
            if not settings.DEBUG:
                logger.critical(
                    "SECURITE CRITIQUE: Tentative de desactiver RBAC en production! "
                    "RBAC_ENABLED=False ignore. Definir DEBUG=True pour desactiver RBAC."
                )
                return True  # Force RBAC actif en prod
            else:
                logger.warning(
                    "ATTENTION: RBAC desactive (RBAC_ENABLED=False). "
                    "TOUTES les permissions sont accordees. Mode developpement uniquement!"
                )
                return False
        return True

    def check_permission(
        self,
        user_id: int,
        permission_code: str,
        is_superuser: bool = False
    ) -> bool:
        """
        Verifie si un utilisateur a une permission.

        Args:
            user_id: ID de l'utilisateur
            permission_code: Code de la permission requise
            is_superuser: L'utilisateur est-il superuser

        Returns:
            True si permission accordee
        """
        # RBAC desactive = tout est permis (uniquement en dev, voir is_enabled())
        if not self.is_enabled():
            return True

        # Superuser bypass si configure
        if is_superuser and settings.RBAC_SUPERUSER_BYPASS:
            return True

        return self.user_role_repo.user_has_permission(user_id, permission_code)

    def require_permission(
        self,
        user_id: int,
        permission_code: str,
        is_superuser: bool = False
    ) -> None:
        """
        Verifie une permission et leve une exception si refusee.

        Args:
            user_id: ID de l'utilisateur
            permission_code: Code de la permission requise
            is_superuser: L'utilisateur est-il superuser

        Raises:
            PermissionDeniedError: Si permission refusee
        """
        if not self.check_permission(user_id, permission_code, is_superuser):
            logger.warning(
                f"Permission denied: user={user_id}, permission={permission_code}"
            )
            raise PermissionDeniedError(permission=permission_code)

    def check_any_permission(
        self,
        user_id: int,
        permission_codes: List[str],
        is_superuser: bool = False
    ) -> bool:
        """
        Verifie si un utilisateur a au moins une des permissions.

        Args:
            user_id: ID de l'utilisateur
            permission_codes: Liste de codes de permission
            is_superuser: L'utilisateur est-il superuser

        Returns:
            True si au moins une permission accordee
        """
        if not self.is_enabled():
            return True

        if is_superuser and settings.RBAC_SUPERUSER_BYPASS:
            return True

        return self.user_role_repo.user_has_any_permission(user_id, permission_codes)

    def check_all_permissions(
        self,
        user_id: int,
        permission_codes: List[str],
        is_superuser: bool = False
    ) -> bool:
        """
        Verifie si un utilisateur a toutes les permissions.

        Args:
            user_id: ID de l'utilisateur
            permission_codes: Liste de codes de permission
            is_superuser: L'utilisateur est-il superuser

        Returns:
            True si toutes les permissions accordees
        """
        if not self.is_enabled():
            return True

        if is_superuser and settings.RBAC_SUPERUSER_BYPASS:
            return True

        return self.user_role_repo.user_has_all_permissions(user_id, permission_codes)

    def get_user_permissions(self, user_id: int) -> Set[str]:
        """
        Recupere toutes les permissions d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Set de codes de permission
        """
        return self.user_role_repo.get_user_permission_codes(user_id)

    # =========================================================================
    # Gestion des roles utilisateur
    # =========================================================================

    def get_user_roles(
        self,
        user_id: int,
        include_expired: bool = False
    ) -> List[Dict]:
        """
        Recupere les roles d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            include_expired: Inclure les roles expires

        Returns:
            Liste des roles avec leurs permissions
        """
        user_roles = self.user_role_repo.get_user_roles(user_id, include_expired)
        return [
            {
                "id": ur.id,
                "role": ur.role.to_dict(include_permissions=True) if ur.role else None,
                "assigned_by": ur.assigned_by,
                "expires_at": ur.expires_at.isoformat() if ur.expires_at else None,
                "is_expired": ur.is_expired,
            }
            for ur in user_roles
        ]

    def assign_role_to_user(
        self,
        user_id: int,
        role_code: str,
        tenant_id: Optional[int] = None,
        assigned_by: Optional[int] = None,
        expires_at: Optional[datetime] = None
    ) -> Dict:
        """
        Assigne un role a un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            role_code: Code du role
            tenant_id: ID du tenant pour chercher le role
            assigned_by: ID de l'utilisateur qui assigne
            expires_at: Date d'expiration optionnelle

        Returns:
            Assignation creee

        Raises:
            RoleNotFoundError: Si le role n'existe pas
        """
        role = self.role_repo.get_by_code(role_code, tenant_id)
        if not role:
            raise RoleNotFoundError(role_code=role_code)

        if not role.is_active:
            raise RoleNotFoundError(role_code=role_code)

        user_role = self.user_role_repo.assign_role(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by,
            expires_at=expires_at
        )

        logger.info(
            f"Role assigned: user={user_id}, role={role_code}, "
            f"by={assigned_by}, expires={expires_at}"
        )

        return user_role.to_dict()

    def revoke_role_from_user(
        self,
        user_id: int,
        role_code: str,
        tenant_id: Optional[int] = None,
        revoked_by: Optional[int] = None
    ) -> bool:
        """
        Revoque un role d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            role_code: Code du role
            tenant_id: ID du tenant
            revoked_by: ID de l'utilisateur qui revoque

        Returns:
            True si revoque
        """
        role = self.role_repo.get_by_code(role_code, tenant_id)
        if not role:
            return False

        result = self.user_role_repo.revoke_role(user_id, role.id)

        if result:
            logger.info(f"Role revoked: user={user_id}, role={role_code}, by={revoked_by}")

        return result

    def revoke_all_roles(self, user_id: int, revoked_by: Optional[int] = None) -> int:
        """
        Revoque tous les roles d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            revoked_by: ID de l'utilisateur qui revoque

        Returns:
            Nombre de roles revoques
        """
        count = self.user_role_repo.revoke_all_roles(user_id)
        if count > 0:
            logger.info(f"All roles revoked: user={user_id}, count={count}, by={revoked_by}")
        return count

    # =========================================================================
    # Gestion des roles
    # =========================================================================

    def get_tenant_roles(
        self,
        tenant_id: int,
        include_global: bool = True
    ) -> List[Dict]:
        """
        Recupere les roles disponibles pour un tenant.

        Args:
            tenant_id: ID du tenant
            include_global: Inclure les roles globaux

        Returns:
            Liste des roles
        """
        roles = self.role_repo.get_tenant_roles(tenant_id, include_global)
        return [role.to_dict(include_permissions=True) for role in roles]

    def create_role(
        self,
        code: str,
        name: str,
        tenant_id: Optional[int] = None,
        description: Optional[str] = None,
        permission_codes: Optional[List[str]] = None
    ) -> Dict:
        """
        Cree un nouveau role.

        Args:
            code: Code unique du role
            name: Nom lisible
            tenant_id: Tenant proprietaire (None = global)
            description: Description
            permission_codes: Codes des permissions a assigner

        Returns:
            Role cree

        Raises:
            RoleAlreadyExistsError: Si le code existe deja
        """
        existing = self.role_repo.get_by_code(code, tenant_id)
        if existing:
            raise RoleAlreadyExistsError(code, tenant_id)

        role = self.role_repo.create_role(
            code=code,
            name=name,
            tenant_id=tenant_id,
            description=description,
            is_system=False
        )

        # Assigner les permissions
        if permission_codes:
            permissions = self.permission_repo.get_by_codes(permission_codes)
            for perm in permissions:
                self.role_repo.add_permission_to_role(role.id, perm.id)

        logger.info(f"Role created: code={code}, tenant={tenant_id}")

        return role.to_dict(include_permissions=True)

    def update_role(
        self,
        role_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        permission_codes: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Met a jour un role.

        Args:
            role_id: ID du role
            name: Nouveau nom
            description: Nouvelle description
            permission_codes: Nouveaux codes de permission

        Returns:
            Role mis a jour ou None

        Raises:
            SystemRoleModificationError: Si role systeme
        """
        role = self.role_repo.get_by_id(role_id)
        if not role:
            return None

        if role.is_system:
            raise SystemRoleModificationError(role.code)

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description

        if update_data:
            self.role_repo.update(role_id, update_data)

        if permission_codes is not None:
            permissions = self.permission_repo.get_by_codes(permission_codes)
            self.role_repo.set_role_permissions(role_id, [p.id for p in permissions])

        logger.info(f"Role updated: id={role_id}")

        return self.role_repo.get_role_with_permissions(role_id).to_dict(include_permissions=True)

    def delete_role(self, role_id: int) -> bool:
        """
        Supprime un role.

        Args:
            role_id: ID du role

        Returns:
            True si supprime

        Raises:
            SystemRoleModificationError: Si role systeme
        """
        role = self.role_repo.get_by_id(role_id)
        if not role:
            return False

        if role.is_system:
            raise SystemRoleModificationError(role.code)

        result = self.role_repo.delete(role_id)
        if result:
            logger.info(f"Role deleted: id={role_id}, code={role.code}")
        return result

    # =========================================================================
    # Gestion des permissions
    # =========================================================================

    def get_all_permissions(self) -> List[Dict]:
        """
        Recupere toutes les permissions actives.

        Returns:
            Liste des permissions
        """
        permissions = self.permission_repo.get_active_permissions()
        return [p.to_dict() for p in permissions]

    def get_permissions_by_resource(self, resource: str) -> List[Dict]:
        """
        Recupere les permissions d'une ressource.

        Args:
            resource: Nom de la ressource

        Returns:
            Liste des permissions
        """
        permissions = self.permission_repo.get_by_resource(resource)
        return [p.to_dict() for p in permissions]

    # =========================================================================
    # Initialisation
    # =========================================================================

    def initialize_default_permissions(self) -> int:
        """
        Cree les permissions par defaut si elles n'existent pas.

        Returns:
            Nombre de permissions creees
        """
        created = self.permission_repo.bulk_create(DEFAULT_PERMISSIONS)
        if created:
            logger.info(f"Created {len(created)} default permissions")
        return len(created)

    def initialize_default_roles(self) -> int:
        """
        Cree les roles par defaut si ils n'existent pas.

        Returns:
            Nombre de roles crees
        """
        count = 0
        for role_data in DEFAULT_ROLES:
            existing = self.role_repo.get_by_code(role_data["code"])
            if not existing:
                role = self.role_repo.create_role(
                    code=role_data["code"],
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system=role_data["is_system"]
                )

                # Assigner les permissions
                for perm_code in role_data["permissions"]:
                    perm = self.permission_repo.get_by_code(perm_code)
                    if perm:
                        self.role_repo.add_permission_to_role(role.id, perm.id)

                count += 1
                logger.info(f"Created default role: {role_data['code']}")

        return count

    def initialize_rbac(self) -> Dict[str, int]:
        """
        Initialise completement le systeme RBAC.

        Returns:
            Stats d'initialisation
        """
        perms_created = self.initialize_default_permissions()
        roles_created = self.initialize_default_roles()

        return {
            "permissions_created": perms_created,
            "roles_created": roles_created
        }

    # =========================================================================
    # Utilitaires
    # =========================================================================

    def cleanup_expired_assignments(self) -> int:
        """
        Nettoie les assignations de roles expirees.

        Returns:
            Nombre d'assignations supprimees
        """
        count = self.user_role_repo.cleanup_expired()
        if count > 0:
            logger.info(f"Cleaned up {count} expired role assignments")
        return count
