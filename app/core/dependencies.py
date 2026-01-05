"""
Dependencies FastAPI pour MassaCorp API
Injection de dependances pour auth, DB, etc.

Row Level Security (RLS):
    Cette API utilise PostgreSQL RLS pour isoler les donnees par tenant.
    Chaque requete DB authentifiee configure automatiquement les variables
    de session PostgreSQL (app.current_tenant_id, app.current_user_id)
    qui sont utilisees par les policies RLS.
"""
import logging
from typing import Generator, Optional
from contextvars import ContextVar

logger = logging.getLogger(__name__)

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import SessionLocal

# Context variables pour RLS (thread-safe)
_current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)
_current_user_id: ContextVar[Optional[int]] = ContextVar("current_user_id", default=None)
from app.core.security import decode_token, InvalidTokenError, TokenExpiredError
from app.models import User
from app.repositories.user import UserRepository
from app.repositories.tenant import TenantRepository
from app.repositories.session import SessionRepository
from app.repositories.login_attempt import LoginAttemptRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.revoked_token import RevokedTokenRepository
from app.repositories.mfa import MFASecretRepository, MFARecoveryCodeRepository
from app.repositories.rbac import PermissionRepository, RoleRepository, UserRoleRepository
from app.repositories.api_key import APIKeyRepository
from app.repositories.api_key_usage import APIKeyUsageRepository
from app.repositories.password_reset import PasswordResetRepository
from app.repositories.oauth import OAuthRepository
from app.services.user import UserService
from app.services.auth import AuthService
from app.services.tenant import TenantService
from app.services.session import SessionService
from app.services.audit import AuditService
from app.services.token import TokenService
from app.services.mfa import MFAService
from app.services.rbac import RBACService
from app.services.api_key import APIKeyService
from app.services.password_reset import PasswordResetService
from app.services.gdpr import GDPRService
from app.services.oauth import OAuthService


# ============================================
# Security Scheme
# ============================================

# Bearer token auth
security = HTTPBearer(auto_error=False)


# ============================================
# Database Session
# ============================================

def get_db() -> Generator[Session, None, None]:
    """
    Fournit une session DB avec auto-commit/rollback.
    Utilise comme dependance FastAPI.

    Yields:
        Session SQLAlchemy

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _set_rls_context(db: Session, tenant_id: Optional[int], user_id: Optional[int] = None) -> None:
    """
    Configure les variables de session PostgreSQL pour RLS.

    Ces variables sont utilisees par les policies RLS pour filtrer
    automatiquement les donnees au niveau de la base de donnees.

    IMPORTANT: Utilise SET ROLE pour activer un role qui respecte RLS.
    Le superuser massa bypass RLS, donc on switch vers massacorp_app.

    Args:
        db: Session SQLAlchemy
        tenant_id: ID du tenant courant
        user_id: ID de l'utilisateur courant (optionnel)
    """
    # Switch to app role that respects RLS (superuser bypasses RLS)
    db.execute(text("SET ROLE massacorp_app"))

    if tenant_id is not None:
        db.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"), {"tid": str(tenant_id)})
        logger.debug(f"RLS context set: tenant_id={tenant_id}")

    if user_id is not None:
        db.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(user_id)})
        logger.debug(f"RLS context set: user_id={user_id}")


def get_db_with_rls(
    tenant_id: int,
    user_id: Optional[int] = None
) -> Generator[Session, None, None]:
    """
    Fournit une session DB avec RLS active.

    Configure les variables de session PostgreSQL avant de retourner
    la session, permettant aux policies RLS de filtrer les donnees.

    Args:
        tenant_id: ID du tenant pour l'isolation des donnees
        user_id: ID de l'utilisateur pour les policies user-level

    Yields:
        Session SQLAlchemy avec RLS configure

    Usage:
        # Dans un endpoint authentifie
        @router.get("/data")
        def get_data(
            current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)
        ):
            # RLS est automatiquement configure via get_current_user_with_rls
            ...
    """
    db = SessionLocal()
    try:
        _set_rls_context(db, tenant_id, user_id)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # Reset RLS context and role
        db.execute(text("RESET ROLE"))
        db.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
        db.execute(text("SELECT set_config('app.current_user_id', '', true)"))
        db.close()


def get_tenant_id_from_header(request: Request) -> Optional[int]:
    """
    Extrait le tenant_id depuis le header X-Tenant-ID.

    Utilise pour les requetes non-authentifiees (login, register, etc.)
    ou pour overrider le tenant context.

    Args:
        request: Request FastAPI

    Returns:
        tenant_id ou None
    """
    tenant_header = request.headers.get("X-Tenant-ID")
    if tenant_header:
        try:
            return int(tenant_header)
        except ValueError:
            pass
    return None


def get_db_with_tenant_header(
    request: Request
) -> Generator[Session, None, None]:
    """
    Fournit une session DB avec RLS basee sur le header X-Tenant-ID.

    Utilise pour les endpoints publics qui necessitent quand meme
    l'isolation par tenant (login, register, password reset).

    Args:
        request: Request FastAPI avec header X-Tenant-ID

    Yields:
        Session SQLAlchemy avec RLS configure
    """
    tenant_id = get_tenant_id_from_header(request)
    db = SessionLocal()
    try:
        if tenant_id is not None:
            _set_rls_context(db, tenant_id)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if tenant_id is not None:
            db.execute(text("RESET ROLE"))
            db.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
        db.close()


def get_db_authenticated() -> Generator[Session, None, None]:
    """
    Fournit une session DB avec RLS basee sur l'utilisateur authentifie.

    IMPORTANT: Cette dependance DOIT etre utilisee APRES get_current_user
    dans la signature de l'endpoint pour que les context vars soient sets.

    Usage:
        @router.get("/data")
        def get_data(
            current_user: User = Depends(get_current_user),  # DOIT etre en premier
            db: Session = Depends(get_db_authenticated)      # Utilise le context
        ):
            # RLS est automatiquement active avec tenant_id et user_id
            return db.query(Data).all()  # Filtre automatiquement par tenant

    Yields:
        Session SQLAlchemy avec RLS configure via context variables
    """
    tenant_id = _current_tenant_id.get()
    user_id = _current_user_id.get()

    db = SessionLocal()
    try:
        if tenant_id is not None:
            _set_rls_context(db, tenant_id, user_id)
        else:
            logger.warning("get_db_authenticated called without RLS context - ensure get_current_user runs first")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        # Reset RLS context and role
        if tenant_id is not None:
            db.execute(text("RESET ROLE"))
            db.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
            db.execute(text("SELECT set_config('app.current_user_id', '', true)"))
        db.close()


# ============================================
# Repositories with RLS
# ============================================

def get_user_repository_rls(
    db: Session = Depends(get_db_authenticated)
) -> UserRepository:
    """Fournit le repository User avec RLS active"""
    return UserRepository(db)


def get_session_repository_rls(
    db: Session = Depends(get_db_authenticated)
) -> SessionRepository:
    """Fournit le repository Session avec RLS active"""
    return SessionRepository(db)


def get_audit_repository_rls(
    db: Session = Depends(get_db_authenticated)
) -> AuditLogRepository:
    """Fournit le repository Audit avec RLS active"""
    return AuditLogRepository(db)


# ============================================
# Repositories
# ============================================

def get_user_repository(
    db: Session = Depends(get_db)
) -> UserRepository:
    """Fournit le repository User"""
    return UserRepository(db)


def get_tenant_repository(
    db: Session = Depends(get_db)
) -> TenantRepository:
    """Fournit le repository Tenant"""
    return TenantRepository(db)


def get_session_repository(
    db: Session = Depends(get_db)
) -> SessionRepository:
    """Fournit le repository Session"""
    return SessionRepository(db)


def get_login_attempt_repository(
    db: Session = Depends(get_db)
) -> LoginAttemptRepository:
    """Fournit le repository LoginAttempt"""
    return LoginAttemptRepository(db)


def get_audit_repository(
    db: Session = Depends(get_db)
) -> AuditLogRepository:
    """Fournit le repository Audit"""
    return AuditLogRepository(db)


def get_refresh_token_repository(
    db: Session = Depends(get_db)
) -> RefreshTokenRepository:
    """Fournit le repository RefreshToken"""
    return RefreshTokenRepository(db)


def get_revoked_token_repository(
    db: Session = Depends(get_db)
) -> RevokedTokenRepository:
    """Fournit le repository RevokedToken"""
    return RevokedTokenRepository(db)


def get_mfa_secret_repository(
    db: Session = Depends(get_db)
) -> MFASecretRepository:
    """Fournit le repository MFASecret"""
    return MFASecretRepository(db)


def get_mfa_recovery_code_repository(
    db: Session = Depends(get_db)
) -> MFARecoveryCodeRepository:
    """Fournit le repository MFARecoveryCode"""
    return MFARecoveryCodeRepository(db)


def get_api_key_repository(
    db: Session = Depends(get_db)
) -> APIKeyRepository:
    """Fournit le repository APIKey"""
    return APIKeyRepository(db)


def get_api_key_usage_repository(
    db: Session = Depends(get_db)
) -> APIKeyUsageRepository:
    """Fournit le repository APIKeyUsage pour logging d'utilisation"""
    return APIKeyUsageRepository(db)


def get_password_reset_repository(
    db: Session = Depends(get_db)
) -> PasswordResetRepository:
    """Fournit le repository PasswordReset"""
    return PasswordResetRepository(db)


def get_oauth_repository(
    db: Session = Depends(get_db)
) -> OAuthRepository:
    """Fournit le repository OAuth"""
    return OAuthRepository(db)


# ============================================
# Services
# ============================================

def get_user_service(
    user_repo: UserRepository = Depends(get_user_repository),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    login_attempt_repo: LoginAttemptRepository = Depends(get_login_attempt_repository)
) -> UserService:
    """
    Fournit le service User avec audit logging et session management.

    SessionService est injecte pour permettre la revocation des sessions
    lors d'un changement de mot de passe (securite critique).
    Il n'y a PAS de dependance circulaire car SessionService ne depend pas
    de UserService.
    """
    # Creer les services inline
    audit_service = AuditService(audit_repository=audit_repo)
    session_service = SessionService(
        session_repository=session_repo,
        login_attempt_repository=login_attempt_repo
    )

    return UserService(
        user_repository=user_repo,
        tenant_repository=tenant_repo,
        session_service=session_service,
        audit_service=audit_service
    )


def get_session_service(
    session_repo: SessionRepository = Depends(get_session_repository),
    login_attempt_repo: LoginAttemptRepository = Depends(get_login_attempt_repository)
) -> SessionService:
    """Fournit le service Session"""
    return SessionService(
        session_repository=session_repo,
        login_attempt_repository=login_attempt_repo
    )


def get_audit_service(
    audit_repo: AuditLogRepository = Depends(get_audit_repository)
) -> AuditService:
    """Fournit le service Audit"""
    return AuditService(audit_repository=audit_repo)


def get_token_service(
    refresh_token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    revoked_token_repo: RevokedTokenRepository = Depends(get_revoked_token_repository)
) -> TokenService:
    """Fournit le service Token"""
    return TokenService(
        refresh_token_repository=refresh_token_repo,
        revoked_token_repository=revoked_token_repo
    )


def get_mfa_service(
    mfa_secret_repo: MFASecretRepository = Depends(get_mfa_secret_repository),
    mfa_recovery_code_repo: MFARecoveryCodeRepository = Depends(get_mfa_recovery_code_repository)
) -> MFAService:
    """Fournit le service MFA"""
    return MFAService(
        mfa_secret_repository=mfa_secret_repo,
        mfa_recovery_code_repository=mfa_recovery_code_repo
    )


def get_api_key_service(
    api_key_repo: APIKeyRepository = Depends(get_api_key_repository),
    usage_repo: APIKeyUsageRepository = Depends(get_api_key_usage_repository)
) -> APIKeyService:
    """Fournit le service APIKey pour l'authentification M2M avec logging"""
    return APIKeyService(repository=api_key_repo, usage_repository=usage_repo)


def get_password_reset_service(
    password_reset_repo: PasswordResetRepository = Depends(get_password_reset_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository)
) -> PasswordResetService:
    """Fournit le service PasswordReset avec toutes ses dependances"""
    return PasswordResetService(
        repository=password_reset_repo,
        user_repository=user_repo,
        session_repository=session_repo
    )


def get_gdpr_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_repository)
) -> GDPRService:
    """
    Fournit le service GDPR pour la conformite.

    Gere:
    - Export des donnees utilisateur (Art. 15)
    - Suppression des donnees (Art. 17)
    - Anonymisation des donnees
    - Inventaire des donnees (Art. 30)
    """
    return GDPRService(
        user_repository=user_repo,
        session_repository=session_repo,
        audit_repository=audit_repo
    )


def get_oauth_service(
    oauth_repo: OAuthRepository = Depends(get_oauth_repository),
    user_repo: UserRepository = Depends(get_user_repository),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    auth_service: "AuthService" = None  # Inject later to avoid circular
) -> OAuthService:
    """
    Fournit le service OAuth pour l'authentification sociale.

    Note: auth_service est injecte manuellement dans l'endpoint
    pour eviter les dependances circulaires.
    """
    from app.core.redis import get_redis_client
    redis_client = get_redis_client()

    return OAuthService(
        oauth_repository=oauth_repo,
        user_repository=user_repo,
        tenant_repository=tenant_repo,
        auth_service=auth_service,
        redis_client=redis_client
    )


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    session_service: SessionService = Depends(get_session_service),
    token_service: TokenService = Depends(get_token_service),
    audit_service: AuditService = Depends(get_audit_service),
    mfa_service: MFAService = Depends(get_mfa_service)
) -> AuthService:
    """
    Fournit le service Auth avec integration Phase 2 + Phase 3.

    Inclut:
    - SessionService: gestion des sessions et brute-force protection
    - TokenService: stockage et revocation des refresh tokens
    - AuditService: logging des evenements de securite
    - MFAService: verification TOTP et flow MFA (Phase 3)
    """
    return AuthService(
        user_repository=user_repo,
        session_service=session_service,
        token_service=token_service,
        audit_service=audit_service,
        mfa_service=mfa_service
    )


def get_tenant_service(
    tenant_repo: TenantRepository = Depends(get_tenant_repository)
) -> TenantService:
    """Fournit le service Tenant"""
    return TenantService(tenant_repository=tenant_repo)


# ============================================
# Authentication
# ============================================

def get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Extrait et valide le payload du token JWT.
    Retourne None si pas de token ou token invalide.

    Args:
        credentials: Credentials Bearer

    Returns:
        Payload du token ou None
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        return payload
    except (InvalidTokenError, TokenExpiredError):
        return None


def _validate_and_extract_user_id(payload: dict) -> int:
    """
    Valide et extrait le user_id du payload JWT.

    Args:
        payload: Payload JWT decode

    Returns:
        user_id valide

    Raises:
        HTTPException 401: Si sub est manquant, None ou invalide
    """
    sub = payload.get("sub")

    if sub is None:
        # SECURITE: Message generique - ne pas exposer que le sub est manquant
        logger.debug("Token invalide: sub manquant")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        # SECURITE: Message generique pour ne pas exposer les details du token
        # Un attaquant ne doit pas savoir si c'est le format ou la valeur qui est invalide
        logger.debug("Token invalide: sub non convertible en int")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if user_id <= 0:
        # SECURITE: Message generique - ne pas exposer que le user_id est <= 0
        logger.debug(f"Token invalide: user_id <= 0 ({user_id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user_id


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: SessionRepository = Depends(get_session_repository)
) -> User:
    """
    Recupere l'utilisateur courant depuis le token JWT.
    Leve une HTTPException si non authentifie.

    SECURITE: Verifie que la session associee au token est toujours active.
    Cela permet de revoquer instantanement l'acces en invalidant la session,
    meme si l'access token n'est pas encore expire.

    Args:
        credentials: Credentials Bearer
        user_repo: Repository User
        session_repo: Repository Session

    Returns:
        User authentifie

    Raises:
        HTTPException 401: Si pas de token ou token invalide
        HTTPException 401: Si utilisateur non trouve ou inactif
        HTTPException 401: Si tenant mismatch (protection IDOR cross-tenant)
        HTTPException 401: Si session revoquee
    """
    from uuid import UUID

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = decode_token(credentials.credentials)
    except TokenExpiredError:
        # SECURITE: Message generique - ne pas reveler que le token etait valide
        logger.debug("Token expire")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Verifier le type de token
    if payload.get("type") != "access":
        # SECURITE: Message generique - ne pas reveler le type attendu
        logger.debug(f"Token type invalide: {payload.get('type')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # CRITICAL: Verifier que la session est toujours active
    session_id_str = payload.get("session_id")
    if session_id_str:
        try:
            session_id = UUID(session_id_str)
            session = session_repo.get_by_id(session_id)

            if session is None or not session.is_active:
                # SECURITE: Message generique - ne pas reveler que session existe mais revoquee
                logger.debug(f"Session revoquee ou inexistante: {session_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalide",
                    headers={"WWW-Authenticate": "Bearer"}
                )
        except (ValueError, TypeError) as e:
            # SECURITE: session_id malformed - log comme WARNING (bug ou attaque)
            # Ne pas ignorer silencieusement - pourrait masquer un probleme
            logger.warning(
                f"session_id malformed dans token: '{session_id_str}' - {e}. "
                "Verification session impossible."
            )

    # Valider et extraire le user_id de maniere securisee
    user_id = _validate_and_extract_user_id(payload)
    user = user_repo.get_by_id(user_id)

    if user is None:
        # SECURITE: Message generique - empeche enumeration des users
        logger.debug(f"User non trouve pour user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        # SECURITE: Message generique - empeche enumeration des comptes desactives
        logger.debug(f"User desactive: user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validation cross-tenant: le tenant du token doit correspondre au tenant de l'user
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and token_tenant_id != user.tenant_id:
        # SECURITE: Message generique - ne pas reveler le mismatch tenant
        logger.warning(f"Tenant mismatch: token={token_tenant_id}, user={user.tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Set RLS context variables for subsequent DB operations
    _current_tenant_id.set(user.tenant_id)
    _current_user_id.set(user.id)
    logger.debug(f"RLS context vars set: tenant_id={user.tenant_id}, user_id={user.id}")

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Alias pour get_current_user.
    Garantit que l'utilisateur est actif.

    Args:
        current_user: Utilisateur courant

    Returns:
        User actif
    """
    return current_user


def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Recupere l'utilisateur courant s'il est superuser.

    Args:
        current_user: Utilisateur courant

    Returns:
        User superuser

    Raises:
        HTTPException 403: Si pas superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privileges superuser requis"
        )
    return current_user


# ============================================
# Tenant Context
# ============================================

def get_current_tenant_id(
    current_user: User = Depends(get_current_user)
) -> int:
    """
    Recupere l'ID du tenant de l'utilisateur courant.

    Args:
        current_user: Utilisateur courant

    Returns:
        ID du tenant
    """
    return current_user.tenant_id


# ============================================
# Optional Authentication
# ============================================

def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Optional[User]:
    """
    Comme get_current_user mais retourne None si pas authentifie.
    Utile pour les endpoints publics avec contenu personnalise.

    Args:
        credentials: Credentials Bearer
        user_repo: Repository User

    Returns:
        User ou None
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
    except (InvalidTokenError, TokenExpiredError):
        return None

    if payload.get("type") != "access":
        return None

    # Valider sub de maniere securisee
    sub = payload.get("sub")
    if sub is None:
        return None

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        return None

    if user_id <= 0:
        return None

    user = user_repo.get_by_id(user_id)

    if user is None or not user.is_active:
        return None

    # Validation cross-tenant
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and token_tenant_id != user.tenant_id:
        return None

    return user


# ============================================
# Session ID from Token
# ============================================

def get_current_session_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional["UUID"]:
    """
    Extrait le session_id du token JWT courant.

    Utilise pour identifier la session courante lors de l'affichage
    de la liste des sessions.

    Args:
        credentials: Credentials Bearer

    Returns:
        UUID de la session ou None si non disponible
    """
    from uuid import UUID

    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
    except (InvalidTokenError, TokenExpiredError):
        return None

    session_id_str = payload.get("session_id")
    if session_id_str is None:
        return None

    try:
        return UUID(session_id_str)
    except (ValueError, TypeError):
        return None


# ============================================
# Session Validation
# ============================================

def validate_session_sync(
    session_id: Optional[str],
    session_service: SessionService
) -> bool:
    """
    Valide qu'une session est active (version synchrone).

    Args:
        session_id: ID de la session (string UUID)
        session_service: Service de gestion des sessions

    Returns:
        True si la session est valide

    Raises:
        InvalidSession: Si session_id est None ou vide
        SessionRevoked: Si la session est revoquee

    Note:
        Utilise la methode sync is_session_valid() du SessionService.
        Pour une version async, voir validate_session_async().
    """
    from uuid import UUID
    from app.core.exceptions import InvalidSession, SessionRevoked

    if not session_id:
        raise InvalidSession()

    # Convertir string en UUID
    try:
        session_uuid = UUID(session_id)
    except (ValueError, TypeError):
        raise InvalidSession()

    # Appel SYNCHRONE - pas de await
    is_valid = session_service.is_session_valid(session_uuid)

    if not is_valid:
        raise SessionRevoked()

    return True


async def validate_session(
    session_id: Optional[str],
    session_service: SessionService
) -> bool:
    """
    Valide qu'une session est active (version async-compatible).

    Wrapper async autour de validate_session_sync pour compatibilite
    avec les handlers async FastAPI.

    Args:
        session_id: ID de la session (string UUID)
        session_service: Service de gestion des sessions

    Returns:
        True si la session est valide

    Raises:
        InvalidSession: Si session_id est None ou vide
        SessionRevoked: Si la session est revoquee
    """
    # Delegation vers la version sync
    # Note: is_session_valid est une operation rapide (single DB query)
    # donc pas besoin de run_in_executor
    return validate_session_sync(session_id, session_service)


# ============================================
# RBAC Repositories
# ============================================

def get_permission_repository(
    db: Session = Depends(get_db)
) -> PermissionRepository:
    """Fournit le repository Permission"""
    return PermissionRepository(db)


def get_role_repository(
    db: Session = Depends(get_db)
) -> RoleRepository:
    """Fournit le repository Role"""
    return RoleRepository(db)


def get_user_role_repository(
    db: Session = Depends(get_db)
) -> UserRoleRepository:
    """Fournit le repository UserRole"""
    return UserRoleRepository(db)


# ============================================
# RBAC Service
# ============================================

def get_rbac_service(
    permission_repo: PermissionRepository = Depends(get_permission_repository),
    role_repo: RoleRepository = Depends(get_role_repository),
    user_role_repo: UserRoleRepository = Depends(get_user_role_repository)
) -> RBACService:
    """
    Fournit le service RBAC.

    Gere le controle d'acces par roles et permissions.
    """
    return RBACService(
        permission_repository=permission_repo,
        role_repository=role_repo,
        user_role_repository=user_role_repo
    )


# ============================================
# Permission Dependencies
# ============================================

def require_permission(permission_code: str):
    """
    Decorateur de dependance pour verifier une permission.

    Usage:
        @router.get("/users")
        def list_users(
            user: User = Depends(require_permission("users.read"))
        ):
            ...

    Args:
        permission_code: Code de la permission requise

    Returns:
        Fonction de dependance FastAPI
    """
    def permission_dependency(
        current_user: User = Depends(get_current_user),
        rbac_service: RBACService = Depends(get_rbac_service)
    ) -> User:
        rbac_service.require_permission(
            user_id=current_user.id,
            permission_code=permission_code,
            is_superuser=current_user.is_superuser
        )
        return current_user

    return permission_dependency


def require_any_permission(*permission_codes: str):
    """
    Decorateur de dependance pour verifier au moins une permission parmi plusieurs.

    Usage:
        @router.get("/data")
        def get_data(
            user: User = Depends(require_any_permission("data.read", "data.admin"))
        ):
            ...

    Args:
        permission_codes: Codes des permissions (au moins une requise)

    Returns:
        Fonction de dependance FastAPI
    """
    from app.services.rbac import PermissionDeniedError

    def permission_dependency(
        current_user: User = Depends(get_current_user),
        rbac_service: RBACService = Depends(get_rbac_service)
    ) -> User:
        if not rbac_service.check_any_permission(
            user_id=current_user.id,
            permission_codes=list(permission_codes),
            is_superuser=current_user.is_superuser
        ):
            raise PermissionDeniedError(
                message=f"Une des permissions suivantes est requise: {', '.join(permission_codes)}"
            )
        return current_user

    return permission_dependency


def require_all_permissions(*permission_codes: str):
    """
    Decorateur de dependance pour verifier toutes les permissions.

    Usage:
        @router.delete("/users/{id}")
        def delete_user(
            user: User = Depends(require_all_permissions("users.read", "users.delete"))
        ):
            ...

    Args:
        permission_codes: Codes des permissions (toutes requises)

    Returns:
        Fonction de dependance FastAPI
    """
    from app.services.rbac import PermissionDeniedError

    def permission_dependency(
        current_user: User = Depends(get_current_user),
        rbac_service: RBACService = Depends(get_rbac_service)
    ) -> User:
        if not rbac_service.check_all_permissions(
            user_id=current_user.id,
            permission_codes=list(permission_codes),
            is_superuser=current_user.is_superuser
        ):
            missing = set(permission_codes) - rbac_service.get_user_permissions(current_user.id)
            raise PermissionDeniedError(
                message=f"Permissions manquantes: {', '.join(missing)}"
            )
        return current_user

    return permission_dependency


class PermissionChecker:
    """
    Classe helper pour verification de permissions dans les endpoints.

    Usage:
        @router.get("/users")
        def list_users(
            current_user: User = Depends(get_current_user),
            rbac: RBACService = Depends(get_rbac_service),
            check: PermissionChecker = Depends(PermissionChecker)
        ):
            check.require("users.read", current_user, rbac)
            return {"users": [...]}
    """

    def require(
        self,
        permission_code: str,
        user: User,
        rbac_service: RBACService
    ) -> None:
        """Verifie une permission, leve exception si refusee."""
        rbac_service.require_permission(
            user_id=user.id,
            permission_code=permission_code,
            is_superuser=user.is_superuser
        )

    def check(
        self,
        permission_code: str,
        user: User,
        rbac_service: RBACService
    ) -> bool:
        """Verifie une permission, retourne bool."""
        return rbac_service.check_permission(
            user_id=user.id,
            permission_code=permission_code,
            is_superuser=user.is_superuser
        )
