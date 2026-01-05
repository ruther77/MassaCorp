"""
Endpoints OAuth pour l'authentification sociale
Google, Facebook, GitHub
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_db,
    get_oauth_repository,
    get_user_repository,
    get_tenant_repository,
    get_auth_service,
    get_current_user,
)
from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models import User
from app.schemas import (
    OAuthProvider,
    OAuthInitResponse,
    OAuthCallbackResponse,
    OAuthCompleteRegistrationRequest,
    OAuthAccountRead,
    OAuthAccountList,
    OAuthUnlinkRequest,
    OAuthProvidersResponse,
    OAuthProviderInfo,
    TokenResponse,
    success_response,
    error_response,
)
from app.services.oauth import OAuthService, OAuthError
from app.services.auth import AuthService
from app.repositories.oauth import OAuthRepository
from app.repositories.user import UserRepository
from app.repositories.tenant import TenantRepository

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/oauth", tags=["OAuth"])


def get_oauth_service_with_auth(
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
) -> OAuthService:
    """Injecte le service OAuth avec AuthService"""
    oauth_repo = OAuthRepository(db)
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    redis_client = get_redis_client()

    return OAuthService(
        oauth_repository=oauth_repo,
        user_repository=user_repo,
        tenant_repository=tenant_repo,
        auth_service=auth_service,
        redis_client=redis_client
    )


@router.get(
    "/providers",
    response_model=OAuthProvidersResponse,
    summary="Liste des providers OAuth",
    description="Retourne la liste des providers OAuth configures et actifs"
)
def get_providers(
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Retourne la liste des providers OAuth disponibles.

    Chaque provider inclut:
    - provider: identifiant (google, facebook, github)
    - name: nom affichable
    - icon: nom de l'icone
    - color: couleur du bouton
    - enabled: toujours True (seuls les configures sont retournes)
    """
    providers = oauth_service.get_available_providers()
    return OAuthProvidersResponse(
        providers=[OAuthProviderInfo(**p) for p in providers]
    )


@router.get(
    "/{provider}/authorize",
    response_model=OAuthInitResponse,
    summary="Initie le flow OAuth",
    description="Genere l'URL d'autorisation pour rediriger l'utilisateur"
)
def oauth_authorize(
    provider: OAuthProvider,
    http_request: Request,
    redirect_uri: Optional[str] = Query(None, description="URI de callback"),
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Initie le flow OAuth avec un provider.

    1. Genere un state unique (protection CSRF)
    2. Construit l'URL d'autorisation du provider
    3. Retourne l'URL pour redirection frontend

    Le frontend doit rediriger l'utilisateur vers auth_url.
    Apres authentification, le provider redirige vers redirect_uri avec un code.
    """
    # Recuperer tenant_id depuis header
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
            detail="X-Tenant-ID invalide"
        )

    # Construire redirect_uri si non fourni
    if not redirect_uri:
        redirect_uri = f"{settings.OAUTH_FRONTEND_URL}/auth/callback/{provider.value}"

    try:
        auth_url, state = oauth_service.get_authorization_url(
            provider=provider.value,
            tenant_id=tenant_id,
            redirect_uri=redirect_uri
        )

        return OAuthInitResponse(
            auth_url=auth_url,
            state=state
        )

    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.get(
    "/{provider}/callback",
    response_model=OAuthCallbackResponse,
    summary="Callback OAuth",
    description="Traite le callback du provider OAuth"
)
async def oauth_callback(
    provider: OAuthProvider,
    code: str = Query(..., description="Code d'autorisation"),
    state: str = Query(..., description="State pour verification CSRF"),
    http_request: Request = None,
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Traite le callback OAuth apres authentification chez le provider.

    1. Verifie le state (protection CSRF)
    2. Echange le code contre un token
    3. Recupere les infos utilisateur
    4. Si compte existant: retourne les tokens JWT
    5. Si nouveau: retourne oauth_session_token pour completer l'inscription

    Le redirect_uri doit correspondre exactement a celui utilise dans /authorize.
    """
    # Construire redirect_uri (doit correspondre a authorize)
    redirect_uri = f"{settings.OAUTH_FRONTEND_URL}/auth/callback/{provider.value}"

    # Extraire les infos client
    client_ip = http_request.client.host if http_request and http_request.client else None
    user_agent = http_request.headers.get("user-agent") if http_request else None

    try:
        result = await oauth_service.authenticate(
            provider=provider.value,
            code=code,
            state=state,
            redirect_uri=redirect_uri,
            ip_address=client_ip,
            user_agent=user_agent
        )

        return OAuthCallbackResponse(**result)

    except OAuthError as e:
        logger.warning(f"OAuth callback error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.post(
    "/complete-registration",
    response_model=TokenResponse,
    summary="Complete l'inscription OAuth",
    description="Finalise l'inscription d'un nouvel utilisateur OAuth"
)
def complete_registration(
    request: OAuthCompleteRegistrationRequest,
    http_request: Request,
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Complete l'inscription d'un nouvel utilisateur OAuth.

    Apres callback qui retourne requires_registration=True,
    le frontend envoie les informations manquantes (nom, prenom)
    avec le oauth_session_token pour creer le compte.

    Retourne les tokens JWT pour connexion immediate.
    """
    client_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    try:
        result = oauth_service.complete_registration(
            oauth_session_token=request.oauth_session_token,
            first_name=request.first_name,
            last_name=request.last_name,
            ip_address=client_ip,
            user_agent=user_agent
        )

        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type=result["token_type"],
            expires_in=result["expires_in"]
        )

    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.get(
    "/accounts",
    response_model=OAuthAccountList,
    summary="Liste des comptes OAuth lies",
    description="Retourne les comptes OAuth lies a l'utilisateur courant"
)
def get_linked_accounts(
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Retourne la liste des comptes OAuth lies a l'utilisateur.

    Permet a l'utilisateur de voir quels providers sont lies
    et de les gerer (delier si plusieurs moyens de connexion).
    """
    accounts = oauth_service.get_user_oauth_accounts(current_user.id)

    return OAuthAccountList(
        accounts=[
            OAuthAccountRead(
                id=a.id,
                provider=a.provider,
                email=a.email,
                name=a.name,
                avatar_url=a.avatar_url,
                created_at=a.created_at
            )
            for a in accounts
        ]
    )


@router.post(
    "/unlink",
    summary="Delier un compte OAuth",
    description="Supprime le lien entre un compte OAuth et l'utilisateur"
)
def unlink_account(
    request: OAuthUnlinkRequest,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Delie un compte OAuth de l'utilisateur.

    Conditions:
    - L'utilisateur doit avoir un autre moyen de connexion
      (mot de passe OU autre compte OAuth)
    - Impossible de delier le dernier moyen de connexion
    """
    try:
        oauth_service.unlink_account(
            user_id=current_user.id,
            provider=request.provider.value
        )

        return success_response(
            message=f"Compte {request.provider.value} delie avec succes"
        )

    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )


@router.get(
    "/{provider}/link",
    response_model=OAuthInitResponse,
    summary="Lier un nouveau compte OAuth",
    description="Initie le flow pour lier un compte OAuth a l'utilisateur existant"
)
def link_account(
    provider: OAuthProvider,
    current_user: User = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service_with_auth)
):
    """
    Initie le flow pour lier un nouveau compte OAuth.

    Similaire a /authorize mais pour un utilisateur deja connecte.
    Le callback detectera l'utilisateur existant et liera le compte.
    """
    redirect_uri = f"{settings.OAUTH_FRONTEND_URL}/auth/callback/{provider.value}"

    try:
        auth_url, state = oauth_service.get_authorization_url(
            provider=provider.value,
            tenant_id=current_user.tenant_id,
            redirect_uri=redirect_uri
        )

        return OAuthInitResponse(
            auth_url=auth_url,
            state=state
        )

    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
