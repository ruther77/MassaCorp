"""
Endpoints de gestion des API Keys pour MassaCorp API.

Ce module gere les endpoints:
- POST /api-keys: Creer une nouvelle API Key
- GET /api-keys: Lister les API Keys du tenant
- GET /api-keys/{key_id}: Details d'une API Key
- DELETE /api-keys/{key_id}: Revoquer une API Key

Securite:
- Authentification requise pour tous les endpoints
- Isolation multi-tenant automatique
- Audit logging des operations sensibles
- Les keys sont hashees en base (SHA-256)
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.dependencies import (
    get_current_user,
    get_api_key_service,
    get_audit_service,
)
from app.models import User
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyRead,
    APIKeyCreated,
    APIKeyList,
    APIKeyRevokeResponse,
)
from app.services.api_key import APIKeyService
from app.services.audit import AuditService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post(
    "",
    response_model=APIKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Creer une API Key",
    description="Cree une nouvelle API Key pour le tenant courant"
)
def create_api_key(
    request: APIKeyCreate,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    api_key_service: APIKeyService = Depends(get_api_key_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Cree une nouvelle API Key.

    IMPORTANT: La valeur raw_key n'est retournee qu'une seule fois!
    Sauvegardez-la immediatement dans un endroit securise.

    La key est hashee en base et ne peut pas etre recuperee.

    Args:
        name: Nom descriptif de la key
        expires_at: Date d'expiration optionnelle

    Returns:
        APIKeyCreated avec raw_key (unique affichage)
    """
    api_key, raw_key = api_key_service.create_key(
        tenant_id=current_user.tenant_id,
        name=request.name,
        expires_at=request.expires_at,
        created_by_user_id=current_user.id,
        scopes=request.scopes
    )

    # Logger l'action
    client_ip = http_request.client.host if http_request.client else None
    audit_service.log_action(
        action="api_key_created",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="api_key",
        resource_id=api_key.id,
        ip_address=client_ip,
        details={"key_name": request.name, "scopes": request.scopes}
    )

    return APIKeyCreated(
        id=api_key.id,
        name=api_key.name,
        raw_key=raw_key,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at
    )


@router.get(
    "",
    response_model=APIKeyList,
    summary="Lister les API Keys",
    description="Retourne toutes les API Keys du tenant courant"
)
def list_api_keys(
    include_revoked: bool = False,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    Liste les API Keys du tenant courant.

    Par defaut, exclut les keys revoquees.
    Utilisez include_revoked=true pour les voir.

    Args:
        include_revoked: Inclure les keys revoquees
        skip: Offset pour pagination
        limit: Limite pour pagination

    Returns:
        Liste des API Keys avec total et count actives
    """
    keys = api_key_service.list_keys(
        tenant_id=current_user.tenant_id,
        include_revoked=include_revoked,
        skip=skip,
        limit=limit
    )

    # Compter les keys actives
    active_count = sum(1 for k in keys if not k.is_revoked and not k.is_expired)

    key_reads = [
        APIKeyRead(
            id=k.id,
            name=k.name,
            tenant_id=k.tenant_id,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            is_revoked=k.is_revoked,
            is_expired=k.is_expired,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            created_by_user_id=k.created_by_user_id,
            created_at=k.created_at,
            updated_at=k.updated_at
        )
        for k in keys
    ]

    return APIKeyList(
        keys=key_reads,
        total=len(key_reads),
        active_count=active_count
    )


@router.get(
    "/{key_id}",
    response_model=APIKeyRead,
    summary="Details d'une API Key",
    description="Retourne les details d'une API Key specifique"
)
def get_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    api_key_service: APIKeyService = Depends(get_api_key_service)
):
    """
    Recupere les details d'une API Key.

    La key doit appartenir au tenant courant.
    La valeur de la key n'est jamais retournee (hashee en base).

    Args:
        key_id: ID de la key

    Returns:
        Details de l'API Key (sans la valeur)
    """
    api_key = api_key_service.get_key_by_id(key_id)

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key non trouvee"
        )

    # Verification multi-tenant
    if api_key.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key non trouvee"
        )

    return APIKeyRead(
        id=api_key.id,
        name=api_key.name,
        tenant_id=api_key.tenant_id,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_revoked=api_key.is_revoked,
        is_expired=api_key.is_expired,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_by_user_id=api_key.created_by_user_id,
        created_at=api_key.created_at,
        updated_at=api_key.updated_at
    )


@router.delete(
    "/{key_id}",
    response_model=APIKeyRevokeResponse,
    summary="Revoquer une API Key",
    description="Revoque une API Key (ne peut plus etre utilisee)"
)
def revoke_api_key(
    key_id: int,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    api_key_service: APIKeyService = Depends(get_api_key_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Revoque une API Key.

    La key ne pourra plus etre utilisee pour l'authentification.
    Cette operation est irreversible.

    La key doit appartenir au tenant courant.

    Args:
        key_id: ID de la key a revoquer

    Returns:
        Confirmation de revocation
    """
    # Verification d'existence et multi-tenant en une operation
    api_key = api_key_service.get_key_by_id(key_id)

    if api_key is None or api_key.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key non trouvee"
        )

    if api_key.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette API Key est deja revoquee"
        )

    # Revoquer la key
    revoked = api_key_service.revoke_key(
        key_id=key_id,
        tenant_id=current_user.tenant_id
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la revocation"
        )

    # Logger l'action
    client_ip = http_request.client.host if http_request.client else None
    audit_service.log_action(
        action="api_key_revoked",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="api_key",
        resource_id=key_id,
        ip_address=client_ip,
        details={"key_name": api_key.name}
    )

    return APIKeyRevokeResponse(
        success=True,
        message="API Key revoquee avec succes",
        revoked_key_id=key_id
    )
