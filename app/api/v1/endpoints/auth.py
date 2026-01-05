"""
Endpoints d'authentification pour MassaCorp API
Login, logout, refresh, password reset

Ce module gere les endpoints:
- POST /auth/login: Connexion utilisateur avec audit logging
- POST /auth/logout: Deconnexion avec revocation de session/token
- POST /auth/refresh: Rotation securisee des tokens
- GET /auth/me: Informations utilisateur courant
- POST /auth/verify-token: Validation de token
- POST /auth/change-password: Changement de mot de passe
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_db,
    get_auth_service,
    get_current_user,
    get_user_service,
    get_mfa_service,
    get_session_service,
)
from app.core.config import get_settings
from app.core.logging import mask_email
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    LogoutRequest,
    ChangePasswordRequest,
    AuthStatusResponse,
    MFALoginRequest,
    MFARequiredResponse,
    RegisterRequest,
    UserRead,
    success_response,
    error_response,
)
from app.services.mfa import MFAService
from app.services.auth import AuthService
from app.services.user import UserService
from app.services.session import SessionService
from app.services.captcha import get_captcha_service, CaptchaValidationError
from app.services.exceptions import PasswordMismatchError, AccountLockedError
from app.services.token import TokenReplayDetectedError

settings = get_settings()


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Connexion utilisateur",
    description="Authentifie un utilisateur et retourne les tokens JWT ou demande MFA/CAPTCHA"
)
async def login(
    request: LoginRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    session_service: SessionService = Depends(get_session_service)
):
    """
    Authentifie un utilisateur avec email et mot de passe.

    Processus Phase 2 + Phase 3 + CAPTCHA:
    - Verification CAPTCHA si trop d'echecs (bruteforce protection)
    - Verification lockout (brute-force protection)
    - Authentification email/password
    - Si MFA active: retourne mfa_required + mfa_session_token
    - Sinon: creation session et stockage refresh token
    - Audit logging

    Retourne (sans MFA):
    - access_token: Token JWT d'acces (courte duree)
    - refresh_token: Token JWT de refresh (longue duree)
    - expires_in: Duree de validite en secondes

    Retourne (avec MFA):
    - mfa_required: True
    - mfa_session_token: Token pour completer l'authentification MFA

    Retourne (CAPTCHA requis):
    - captcha_required: True
    - captcha_site_key: Cle publique pour le frontend

    Le tenant_id DOIT etre fourni dans le header X-Tenant-ID.
    """
    # Recuperer tenant_id depuis header X-Tenant-ID (OBLIGATOIRE)
    tenant_id_header = http_request.headers.get("X-Tenant-ID")
    if not tenant_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Tenant-ID requis"
        )
    try:
        tenant_id = int(tenant_id_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID invalide: doit etre un entier"
        )

    # Extraire les infos client pour audit
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    # Verification CAPTCHA si active et requis
    captcha_service = get_captcha_service()
    if captcha_service.is_enabled():
        # Verifier si CAPTCHA est requis (apres N echecs)
        captcha_required = session_service.is_captcha_required(
            email=request.email,
            ip_address=client_ip
        )

        if captcha_required:
            if not request.captcha_token:
                # Pas de token CAPTCHA, demander au client
                return LoginResponse(
                    success=False,
                    captcha_required=True,
                    captcha_site_key=settings.CAPTCHA_SITE_KEY,
                    message="Verification CAPTCHA requise suite a plusieurs tentatives echouees"
                )

            # Valider le token CAPTCHA
            try:
                await captcha_service.validate(
                    token=request.captcha_token,
                    remote_ip=client_ip,
                    expected_action="login"
                )
            except CaptchaValidationError as e:
                return LoginResponse(
                    success=False,
                    captcha_required=True,
                    captcha_site_key=settings.CAPTCHA_SITE_KEY,
                    message=f"Validation CAPTCHA echouee: {e.message}"
                )

    try:
        result = auth_service.login(
            email=request.email,
            password=request.password,
            tenant_id=tenant_id,
            ip_address=client_ip,
            user_agent=user_agent
        )
    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=e.message
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe invalide"
        )

    # Verifier si MFA est requis - retour unifie LoginResponse
    if result.get("mfa_required"):
        return LoginResponse(
            success=True,
            mfa_required=True,
            mfa_session_token=result["mfa_session_token"],
            message=result.get("message", "MFA verification required")
        )

    # Login complet sans MFA - retour unifie LoginResponse
    return LoginResponse(
        success=True,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"],
        mfa_required=False
    )


@router.post(
    "/login/mfa",
    response_model=TokenResponse,
    summary="Completer l'authentification MFA",
    description="Complete l'authentification avec le code TOTP apres login initial"
)
def login_mfa(
    request: MFALoginRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Complete l'authentification MFA (etape 2 du login).

    Apres un login initial qui retourne mfa_required=True,
    utiliser ce endpoint avec le mfa_session_token et le code TOTP.

    Args:
        mfa_session_token: Token de session MFA recu a l'etape 1
        totp_code: Code TOTP a 6 chiffres genere par l'app authenticator

    Retourne:
        access_token: Token JWT d'acces
        refresh_token: Token JWT de refresh
        expires_in: Duree de validite en secondes

    Le header X-Tenant-ID est requis pour coherence avec login.
    """
    # Validation X-Tenant-ID (coherence avec login step 1)
    tenant_id_header = http_request.headers.get("X-Tenant-ID")
    if not tenant_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Tenant-ID requis"
        )
    try:
        tenant_id = int(tenant_id_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID invalide: doit etre un entier"
        )

    # Extraire les infos client pour audit
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    result = auth_service.complete_mfa_login(
        mfa_session_token=request.mfa_session_token,
        totp_code=request.totp_code,
        ip_address=client_ip,
        user_agent=user_agent,
        expected_tenant_id=tenant_id  # Validation cross-tenant
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Code MFA invalide ou session expiree"
        )

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"]
    )


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription publique",
    description="Cree un nouveau compte utilisateur"
)
def register(
    request: RegisterRequest,
    http_request: Request,
    user_service: UserService = Depends(get_user_service)
):
    """
    Inscription publique d'un nouvel utilisateur.

    Cree un compte utilisateur avec les informations fournies.
    Le compte est cree en mode inactif (is_active=True) mais
    non verifie (is_verified=False).

    Le tenant_id DOIT etre fourni dans le header X-Tenant-ID.

    Args:
        email: Adresse email (unique par tenant)
        password: Mot de passe (min 12 chars, majuscule, minuscule, chiffre, special)
        first_name: Prenom (min 2 chars)
        last_name: Nom (min 2 chars)

    Returns:
        Utilisateur cree (sans le hash du mot de passe)

    Raises:
        400: Donnees invalides ou email deja utilise
        400: Header X-Tenant-ID manquant
    """
    # Recuperer tenant_id depuis header X-Tenant-ID (OBLIGATOIRE)
    tenant_id_header = http_request.headers.get("X-Tenant-ID")
    if not tenant_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Tenant-ID requis"
        )
    try:
        tenant_id = int(tenant_id_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID invalide: doit etre un entier"
        )

    # Extraire les infos client pour audit
    client_ip = http_request.client.host if http_request.client else None

    try:
        user = user_service.create_user(
            email=request.email,
            password=request.password,
            tenant_id=tenant_id,
            first_name=request.first_name,
            last_name=request.last_name,
            is_active=True,
            is_verified=False,
            is_superuser=False
        )

        logger.info(
            f"Nouvel utilisateur inscrit: {mask_email(user.email)} "
            f"(tenant_id={tenant_id}, ip={client_ip})"
        )

        return UserRead(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at
        )

    except Exception as e:
        from app.services.exceptions import EmailAlreadyExistsError, TenantNotFoundError
        if isinstance(e, EmailAlreadyExistsError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cet email est deja utilise"
            )
        elif isinstance(e, TenantNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant invalide"
            )
        else:
            logger.error(f"Erreur inscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'inscription"
            )


@router.post(
    "/logout",
    summary="Deconnexion utilisateur",
    description="Revoque le token de refresh et termine la session"
)
def logout(
    http_request: Request,
    request: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Deconnecte l'utilisateur courant.

    Processus Phase 2:
    - Revocation du refresh token specifique
    - Termination de la session associee
    - Audit logging

    Options:
    - refresh_token: Token de refresh a revoquer
    - session_id: ID de la session a terminer (UUID)
    - all_sessions: Revoquer toutes les sessions (defaut False)

    Note: Le body JSON peut etre vide {} ou omis - tous les champs sont optionnels.
    """
    # Gerer le cas ou request est None (body vide ou absent)
    if request is None:
        request = LogoutRequest()

    refresh_token = request.refresh_token
    session_id = request.session_id
    all_sessions = request.all_sessions

    # Extraire les infos client pour audit
    client_ip = http_request.client.host if http_request.client else None

    auth_service.logout(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        refresh_token=refresh_token,
        session_id=session_id,
        all_sessions=all_sessions,
        ip_address=client_ip
    )

    return success_response(message="Deconnexion reussie")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rafraichir les tokens",
    description="Genere de nouveaux tokens a partir d'un refresh token valide"
)
def refresh_tokens(
    request: RefreshTokenRequest,
    http_request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Rafraichit les tokens JWT avec rotation securisee.

    Processus Phase 2:
    - Verification blacklist Redis
    - Detection de replay attack
    - Rotation du token (ancien invalide, nouveau cree)
    - Audit logging

    Le refresh_token doit etre valide et non revoque.
    Retourne une nouvelle paire access/refresh tokens.
    """
    # Extraire les infos client pour audit
    client_ip = http_request.client.host if http_request.client else None

    try:
        result = auth_service.refresh_tokens(
            refresh_token=request.refresh_token,
            ip_address=client_ip
        )
    except TokenReplayDetectedError:
        # SECURITE: Message generique - ne pas reveler l'attaque de replay
        # Log l'incident pour investigation
        logger.warning(f"Token replay detecte depuis IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide"
        )

    if result is None:
        # SECURITE: Message generique - ne pas reveler si expire ou invalide
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide"
        )

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"]
    )


@router.get(
    "/me",
    response_model=AuthStatusResponse,
    summary="Statut d'authentification",
    description="Retourne le statut d'authentification de l'utilisateur courant"
)
def get_auth_status(
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Retourne les informations d'authentification de l'utilisateur courant.
    Inclut le statut MFA reel depuis MFAService.
    """
    # Recuperer le statut MFA reel
    mfa_status = mfa_service.get_mfa_status(current_user.id)
    mfa_enabled = mfa_status.get("enabled", False)

    return AuthStatusResponse(
        authenticated=True,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        mfa_required=mfa_enabled,  # MFA requis si active
        mfa_enabled=mfa_enabled
    )


@router.post(
    "/change-password",
    summary="Changer le mot de passe",
    description="Change le mot de passe de l'utilisateur courant"
)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    Change le mot de passe de l'utilisateur courant.

    Requiert:
    - current_password: Mot de passe actuel
    - new_password: Nouveau mot de passe (min 8 chars, complexite requise)
    """
    try:
        user_service.change_password(
            user_id=current_user.id,
            current_password=request.current_password,
            new_password=request.new_password
        )
        return success_response(message="Mot de passe modifie avec succes")

    except PasswordMismatchError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect"
        )


@router.post(
    "/verify-token",
    summary="Verifier un token",
    description="Verifie si un token JWT est valide"
)
def verify_token(
    current_user: User = Depends(get_current_user)
):
    """
    Verifie que le token JWT est valide.
    Si cette route repond avec succes, le token est valide.
    """
    return success_response(
        data={"user_id": current_user.id, "valid": True},
        message="Token valide"
    )
