"""
Repositories pour MassaCorp API
Pattern Repository pour isolation acces DB

Modules disponibles:
- base: Repository generique avec operations CRUD
- tenant: Gestion des tenants
- user: Gestion des utilisateurs
- audit_log: Logs d'audit des actions sensibles (Phase 2)
- login_attempt: Tentatives de connexion (Phase 2)
- session: Sessions utilisateur (Phase 2)
- refresh_token: Tokens de rafraichissement (Phase 2)
- revoked_token: Blacklist des tokens revoques (Phase 2)
- api_key: API Keys pour authentification M2M
- password_reset: Tokens de reinitialisation de mot de passe
- rbac: Roles, Permissions et Assignations utilisateur
"""
from app.repositories.base import (
    BaseRepository,
    TenantAwareBaseRepository,
    RepositoryException,
    TenantIsolationError,
    PaginationError,
)
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository, TenantAwareUserRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.login_attempt import LoginAttemptRepository
from app.repositories.session import SessionRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.revoked_token import RevokedTokenRepository
from app.repositories.api_key import APIKeyRepository
from app.repositories.password_reset import PasswordResetRepository
from app.repositories.rbac import PermissionRepository, RoleRepository, UserRoleRepository
from app.repositories.oauth import OAuthRepository

# Epicerie
from app.repositories.epicerie import (
    SupplyOrderRepository,
    SupplyOrderLineRepository,
)

__all__ = [
    # Base
    "BaseRepository",
    "TenantAwareBaseRepository",
    "RepositoryException",
    "TenantIsolationError",
    "PaginationError",
    # Phase 1
    "TenantRepository",
    "UserRepository",
    "TenantAwareUserRepository",
    # Phase 2 - Audit et Securite
    "AuditLogRepository",
    "LoginAttemptRepository",
    "SessionRepository",
    "RefreshTokenRepository",
    "RevokedTokenRepository",
    # Phase 2 - API Keys et Password Reset
    "APIKeyRepository",
    "PasswordResetRepository",
    # RBAC
    "PermissionRepository",
    "RoleRepository",
    "UserRoleRepository",
    # OAuth
    "OAuthRepository",
    # Epicerie
    "SupplyOrderRepository",
    "SupplyOrderLineRepository",
]
