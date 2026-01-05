"""
Modeles RBAC (Role-Based Access Control) pour MassaCorp
Gestion des roles et permissions avec isolation multi-tenant

Architecture:
- Permission: Actions atomiques (users.read, users.write, etc.)
- Role: Ensemble de permissions (admin, viewer, editor, etc.)
- UserRole: Association User <-> Role avec scope tenant
- RolePermission: Association Role <-> Permission
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tenant import Tenant


class Permission(Base, TimestampMixin):
    """
    Permission atomique dans le systeme.

    Format recommande: resource.action
    Exemples:
        - users.read, users.write, users.delete
        - tenants.manage
        - reports.export
        - audit.view

    Attributs:
        id: Identifiant unique
        code: Code unique de la permission (ex: users.read)
        name: Nom lisible (ex: "Lecture des utilisateurs")
        description: Description detaillee
        resource: Ressource concernee (ex: users, tenants, reports)
        action: Action sur la ressource (ex: read, write, delete)
        is_active: Permission active ou desactivee
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Identifiant unique de la permission
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)

    # Metadonnees
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Decomposition resource.action
    resource: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)

    # Etat
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relations
    roles: Mapped[List["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        {"comment": "Permissions atomiques du systeme RBAC"},
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, code='{self.code}')>"

    def to_dict(self) -> dict:
        """Serialise la permission en dictionnaire."""
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "resource": self.resource,
            "action": self.action,
            "is_active": self.is_active,
        }


class Role(Base, TimestampMixin):
    """
    Role regroupant des permissions.

    Les roles peuvent etre:
    - Globaux (tenant_id = NULL): Admin systeme, disponibles partout
    - Specifiques au tenant: Personnalises par chaque tenant

    Attributs:
        id: Identifiant unique
        tenant_id: Tenant proprietaire (NULL = role global)
        code: Code unique du role (ex: admin, viewer, editor)
        name: Nom lisible (ex: "Administrateur")
        description: Description du role
        is_system: Role systeme non modifiable
        is_active: Role actif ou desactive
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Tenant (NULL = role global disponible pour tous les tenants)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Identifiant du role
    code: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # Metadonnees
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Flags
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relations
    tenant: Mapped[Optional["Tenant"]] = relationship(
        "Tenant",
        back_populates="roles"
    )

    permissions: Mapped[List["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    users: Mapped[List["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Code unique par tenant (ou global si tenant_id NULL)
        UniqueConstraint("tenant_id", "code", name="uq_role_tenant_code"),
        {"comment": "Roles RBAC avec support multi-tenant"},
    )

    def __repr__(self) -> str:
        tenant = f"tenant={self.tenant_id}" if self.tenant_id else "global"
        return f"<Role(id={self.id}, code='{self.code}', {tenant})>"

    @property
    def is_global(self) -> bool:
        """Verifie si c'est un role global (disponible tous tenants)."""
        return self.tenant_id is None

    def get_permission_codes(self) -> List[str]:
        """Retourne la liste des codes de permission du role."""
        return [rp.permission.code for rp in self.permissions if rp.permission.is_active]

    def has_permission(self, permission_code: str) -> bool:
        """Verifie si le role a une permission specifique."""
        return permission_code in self.get_permission_codes()

    def to_dict(self, include_permissions: bool = False) -> dict:
        """Serialise le role en dictionnaire."""
        data = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "is_system": self.is_system,
            "is_global": self.is_global,
            "is_active": self.is_active,
        }
        if include_permissions:
            data["permissions"] = self.get_permission_codes()
        return data


class RolePermission(Base, TimestampMixin):
    """
    Association Role <-> Permission.

    Table de liaison many-to-many entre roles et permissions.
    """

    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relations
    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    permission: Mapped["Permission"] = relationship("Permission", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        {"comment": "Association roles-permissions"},
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


class UserRole(Base, TimestampMixin):
    """
    Association User <-> Role.

    Attributs:
        user_id: Utilisateur
        role_id: Role assigne
        assigned_by: ID de l'utilisateur qui a fait l'assignation
        expires_at: Date d'expiration optionnelle (roles temporaires)
    """

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Audit
    assigned_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Expiration optionnelle pour les roles temporaires
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relations
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        backref="user_roles"
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")

    assigner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_by]
    )

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        {"comment": "Association utilisateurs-roles"},
    )

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"

    @property
    def is_expired(self) -> bool:
        """Verifie si l'assignation de role a expire."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Verifie si l'assignation est valide (non expiree)."""
        return not self.is_expired

    def to_dict(self) -> dict:
        """Serialise l'assignation en dictionnaire."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role_id": self.role_id,
            "role_code": self.role.code if self.role else None,
            "assigned_by": self.assigned_by,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
