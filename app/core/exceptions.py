"""
Exceptions applicatives pour MassaCorp API.

Ces exceptions sont utilisees par les services et automatiquement
converties en responses HTTP par le exception handler.

Usage:
    from app.core.exceptions import InvalidCredentials
    raise InvalidCredentials()

Le exception handler convertira en:
    HTTP 401: {"error": "INVALID_CREDENTIALS", "message": "Invalid email or password"}
"""
from typing import Optional, Dict, Any
from datetime import datetime


class AppException(Exception):
    """
    Exception de base pour l'application.

    Toutes les exceptions metier heritent de cette classe.
    Fournit status_code HTTP et error_code pour le client.
    """
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise l'exception pour la response JSON"""
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# Authentication Exceptions (401)
# =============================================================================

class InvalidCredentials(AppException):
    """Email ou mot de passe invalide"""
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class TokenExpired(AppException):
    """Token JWT expire"""
    status_code = 401
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired"


class TokenRevoked(AppException):
    """Token JWT revoque"""
    status_code = 401
    error_code = "TOKEN_REVOKED"
    message = "Token has been revoked"


class TokenInvalid(AppException):
    """Token JWT invalide (signature, format, etc.)"""
    status_code = 401
    error_code = "TOKEN_INVALID"
    message = "Invalid token"


class SessionExpired(AppException):
    """Session expiree ou revoquee"""
    status_code = 401
    error_code = "SESSION_EXPIRED"
    message = "Session has expired"


class SessionRevoked(AppException):
    """Session revoquee (logout, force-logout, etc.)"""
    status_code = 401
    error_code = "SESSION_REVOKED"
    message = "Session has been revoked"


class InvalidSession(AppException):
    """Session invalide ou manquante"""
    status_code = 401
    error_code = "INVALID_SESSION"
    message = "Invalid or missing session"


class MFAInvalid(AppException):
    """Code MFA invalide"""
    status_code = 401
    error_code = "MFA_INVALID"
    message = "Invalid MFA code"


# =============================================================================
# Authorization Exceptions (403)
# =============================================================================

class MFARequired(AppException):
    """MFA requis pour cette action"""
    status_code = 403
    error_code = "MFA_REQUIRED"
    message = "Multi-factor authentication required"


class AccountLocked(AppException):
    """Compte verrouille (trop de tentatives)"""
    status_code = 403
    error_code = "ACCOUNT_LOCKED"
    message = "Account is temporarily locked"

    def __init__(self, until: datetime = None, minutes: int = None):
        details = {}
        if until:
            details["locked_until"] = until.isoformat()
        if minutes:
            details["retry_after_minutes"] = minutes
        super().__init__(details=details)


class AccountInactive(AppException):
    """Compte desactive"""
    status_code = 403
    error_code = "ACCOUNT_INACTIVE"
    message = "Account is inactive"


class PermissionDenied(AppException):
    """Permission refusee"""
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "You don't have permission to perform this action"


class TenantMismatch(AppException):
    """Tenant du token ne correspond pas"""
    status_code = 403
    error_code = "TENANT_MISMATCH"
    message = "Tenant access denied"


# =============================================================================
# Resource Exceptions (404, 409)
# =============================================================================

class NotFound(AppException):
    """Resource non trouvee"""
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"

    def __init__(self, resource: str = None):
        message = f"{resource} not found" if resource else None
        super().__init__(message=message)


class AlreadyExists(AppException):
    """Resource existe deja"""
    status_code = 409
    error_code = "ALREADY_EXISTS"
    message = "Resource already exists"


class EmailAlreadyExists(AlreadyExists):
    """Email deja utilise"""
    error_code = "EMAIL_ALREADY_EXISTS"
    message = "Email is already registered"


# =============================================================================
# Validation Exceptions (400, 422)
# =============================================================================

class BadRequest(AppException):
    """Requete invalide"""
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "Invalid request"


class ValidationError(AppException):
    """Erreur de validation"""
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class PasswordTooWeak(ValidationError):
    """Mot de passe trop faible"""
    error_code = "PASSWORD_TOO_WEAK"
    message = "Password does not meet security requirements"


# =============================================================================
# Rate Limiting (429)
# =============================================================================

class RateLimitExceeded(AppException):
    """Trop de requetes"""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"

    def __init__(self, retry_after: int = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(details=details)


class TOTPReplayDetected(RateLimitExceeded):
    """Code TOTP deja utilise (anti-replay)"""
    error_code = "TOTP_REPLAY"
    message = "TOTP code already used"


# =============================================================================
# Token Replay Attack (401)
# =============================================================================

class TokenReplayDetected(AppException):
    """Replay attack detecte sur refresh token"""
    status_code = 401
    error_code = "TOKEN_REPLAY"
    message = "Token reuse detected - session revoked for security"
