"""
Services metier pour MassaCorp API
Contient la logique metier separee des repositories

Modules disponibles:
- auth: Authentification (login, tokens)
- user: Gestion des utilisateurs
- tenant: Gestion des tenants
- audit: Logs d'audit (Phase 2)
- session: Gestion des sessions (Phase 2)
- token: Gestion des refresh tokens (Phase 2)
- rbac: Controle d'acces par roles (RBAC)
- captcha: Validation CAPTCHA (reCAPTCHA/hCaptcha)
- api_key: Gestion des API Keys (M2M auth)
- password_reset: Reinitialisation de mot de passe
- gdpr: Conformite GDPR (export, suppression, anonymisation)
- mfa: Authentification multi-facteur (Phase 3)
"""
from app.services.auth import AuthService
from app.services.user import UserService
from app.services.tenant import TenantService
from app.services.audit import AuditService
from app.services.session import SessionService
from app.services.token import TokenService
from app.services.rbac import RBACService
from app.services.captcha import CaptchaService, get_captcha_service
from app.services.api_key import APIKeyService
from app.services.password_reset import PasswordResetService
from app.services.gdpr import GDPRService
from app.services.mfa import MFAService, MFALockoutError, InvalidMFACodeError, MFANotConfiguredError
from app.services.exceptions import (
    ServiceException,
    EmailAlreadyExistsError,
    UserNotFoundError,
    TenantNotFoundError,
    InvalidCredentialsError,
    InactiveUserError,
    InvalidTokenError,
    PasswordMismatchError,
    MFARequiredError,
    MFAInvalidError,
)
# Exceptions Phase 2
from app.services.session import (
    SessionNotFoundError,
    SessionExpiredError,
    AccountLockedError,
)
from app.services.token import (
    TokenNotFoundError,
    TokenRevokedError,
    TokenExpiredError,
    TokenReplayDetectedError,
)
# Exceptions RBAC
from app.services.rbac import (
    RBACException,
    PermissionDeniedError,
    RoleNotFoundError,
    PermissionNotFoundError,
    RoleAlreadyExistsError,
    SystemRoleModificationError,
)
# Exceptions CAPTCHA
from app.services.captcha import CaptchaValidationError
# Exceptions API Key
from app.services.api_key import (
    APIKeyException,
    InvalidAPIKey,
    APIKeyRevoked,
    APIKeyExpired,
)
# Exceptions Password Reset
from app.services.password_reset import (
    PasswordResetException,
    RateLimitExceeded,
    TokenExpired as PasswordResetTokenExpired,
    TokenAlreadyUsed,
    InvalidToken as PasswordResetInvalidToken,
)

__all__ = [
    # Services Phase 1
    "AuthService",
    "UserService",
    "TenantService",
    # Services Phase 2
    "AuditService",
    "SessionService",
    "TokenService",
    # Services RBAC & CAPTCHA
    "RBACService",
    "CaptchaService",
    "get_captcha_service",
    # Services Phase 4
    "APIKeyService",
    "PasswordResetService",
    "GDPRService",
    "MFAService",
    # Exceptions Phase 1
    "ServiceException",
    "EmailAlreadyExistsError",
    "UserNotFoundError",
    "TenantNotFoundError",
    "InvalidCredentialsError",
    "InactiveUserError",
    "InvalidTokenError",
    "PasswordMismatchError",
    "MFARequiredError",
    "MFAInvalidError",
    # Exceptions Phase 2
    "SessionNotFoundError",
    "SessionExpiredError",
    "AccountLockedError",
    "TokenNotFoundError",
    "TokenRevokedError",
    "TokenExpiredError",
    "TokenReplayDetectedError",
    # Exceptions RBAC
    "RBACException",
    "PermissionDeniedError",
    "RoleNotFoundError",
    "PermissionNotFoundError",
    "RoleAlreadyExistsError",
    "SystemRoleModificationError",
    # Exceptions CAPTCHA
    "CaptchaValidationError",
    # Exceptions API Key
    "APIKeyException",
    "InvalidAPIKey",
    "APIKeyRevoked",
    "APIKeyExpired",
    # Exceptions Password Reset
    "PasswordResetException",
    "RateLimitExceeded",
    "PasswordResetTokenExpired",
    "TokenAlreadyUsed",
    "PasswordResetInvalidToken",
    # Exceptions MFA
    "MFALockoutError",
    "InvalidMFACodeError",
    "MFANotConfiguredError",
]
