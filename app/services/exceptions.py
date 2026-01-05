"""
Exceptions metier pour les Services MassaCorp
"""


class ServiceException(Exception):
    """Exception de base pour les services"""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class EmailAlreadyExistsError(ServiceException):
    """Email deja utilise dans ce tenant"""

    def __init__(self, email: str):
        super().__init__(
            message=f"L'email {email} est deja utilise",
            code="EMAIL_EXISTS"
        )
        self.email = email


class UserNotFoundError(ServiceException):
    """Utilisateur non trouve"""

    def __init__(self, user_id: int = None, email: str = None):
        if email:
            message = f"Utilisateur avec email {email} non trouve"
        else:
            message = f"Utilisateur avec ID {user_id} non trouve"
        super().__init__(message=message, code="USER_NOT_FOUND")
        self.user_id = user_id
        self.email = email


class TenantNotFoundError(ServiceException):
    """Tenant non trouve"""

    def __init__(self, tenant_id: int = None, slug: str = None):
        if slug:
            message = f"Tenant avec slug {slug} non trouve"
        else:
            message = f"Tenant avec ID {tenant_id} non trouve"
        super().__init__(message=message, code="TENANT_NOT_FOUND")
        self.tenant_id = tenant_id
        self.slug = slug


class InvalidCredentialsError(ServiceException):
    """Identifiants invalides"""

    def __init__(self):
        super().__init__(
            message="Email ou mot de passe invalide",
            code="INVALID_CREDENTIALS"
        )


class InactiveUserError(ServiceException):
    """Utilisateur desactive"""

    def __init__(self, user_id: int = None):
        super().__init__(
            message="Ce compte utilisateur est desactive",
            code="INACTIVE_USER"
        )
        self.user_id = user_id


class InvalidTokenError(ServiceException):
    """Token JWT invalide ou expire"""

    def __init__(self, reason: str = None):
        message = "Token invalide ou expire"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message=message, code="INVALID_TOKEN")
        self.reason = reason


class PasswordMismatchError(ServiceException):
    """Mot de passe actuel incorrect"""

    def __init__(self):
        super().__init__(
            message="Le mot de passe actuel est incorrect",
            code="PASSWORD_MISMATCH"
        )


class MFARequiredError(ServiceException):
    """MFA requis pour cette action"""

    def __init__(self):
        super().__init__(
            message="L'authentification MFA est requise",
            code="MFA_REQUIRED"
        )


class MFAInvalidError(ServiceException):
    """Code MFA invalide"""

    def __init__(self):
        super().__init__(
            message="Code MFA invalide",
            code="MFA_INVALID"
        )


# ============================================================================
# Exceptions Phase 2 - Audit, Sessions, Tokens
# ============================================================================


class SessionNotFoundError(ServiceException):
    """Session non trouvee"""

    def __init__(self, session_id: str = None):
        super().__init__(
            message="Session non trouvee",
            code="SESSION_NOT_FOUND"
        )
        self.session_id = session_id


class SessionExpiredError(ServiceException):
    """Session expiree"""

    def __init__(self, session_id: str = None):
        super().__init__(
            message="La session a expire",
            code="SESSION_EXPIRED"
        )
        self.session_id = session_id


class TokenRevokedError(ServiceException):
    """Token deja revoque"""

    def __init__(self, jti: str = None):
        super().__init__(
            message="Ce token a ete revoque",
            code="TOKEN_REVOKED"
        )
        self.jti = jti


class InvalidDateRangeError(ServiceException):
    """Plage de dates invalide (start_date > end_date)"""

    def __init__(self, message: str = None):
        super().__init__(
            message=message or "La date de debut doit etre anterieure a la date de fin",
            code="INVALID_DATE_RANGE"
        )


class DateRangeTooLargeError(ServiceException):
    """Plage de dates trop grande"""

    def __init__(self, max_days: int = 90):
        super().__init__(
            message=f"La plage de dates ne peut pas depasser {max_days} jours",
            code="DATE_RANGE_TOO_LARGE"
        )
        self.max_days = max_days


class RetentionPeriodError(ServiceException):
    """Tentative de suppression avant la periode de retention minimum"""

    def __init__(self, min_days: int = 30):
        super().__init__(
            message=f"Les logs doivent etre conserves au minimum {min_days} jours",
            code="RETENTION_PERIOD_ERROR"
        )
        self.min_days = min_days


class InvalidExpirationError(ServiceException):
    """Date d'expiration dans le passe"""

    def __init__(self):
        super().__init__(
            message="La date d'expiration doit etre dans le futur",
            code="INVALID_EXPIRATION"
        )


class ExpirationTooLongError(ServiceException):
    """Date d'expiration trop eloignee"""

    def __init__(self, max_days: int = 30):
        super().__init__(
            message=f"La duree d'expiration ne peut pas depasser {max_days} jours",
            code="EXPIRATION_TOO_LONG"
        )
        self.max_days = max_days


class TokenRefreshRateLimitError(ServiceException):
    """Trop de refreshs de tokens en peu de temps"""

    def __init__(self, max_refreshes: int = 10, window_minutes: int = 1):
        super().__init__(
            message=f"Trop de rafraichissements de token ({max_refreshes} max par {window_minutes} minute(s))",
            code="TOKEN_REFRESH_RATE_LIMIT"
        )
        self.max_refreshes = max_refreshes
        self.window_minutes = window_minutes


class MaxSessionsExceededError(ServiceException):
    """Nombre maximum de sessions atteint"""

    def __init__(self, max_sessions: int = 5):
        super().__init__(
            message=f"Nombre maximum de sessions actives atteint ({max_sessions})",
            code="MAX_SESSIONS_EXCEEDED"
        )
        self.max_sessions = max_sessions


class AccountLockedError(ServiceException):
    """Compte verrouille suite a trop de tentatives"""

    def __init__(self, email: str = None, lockout_minutes: int = 30):
        super().__init__(
            message=f"Compte verrouille. Reessayez dans {lockout_minutes} minutes.",
            code="ACCOUNT_LOCKED"
        )
        self.email = email
        self.lockout_minutes = lockout_minutes
