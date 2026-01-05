"""
Endpoints utilisateurs pour MassaCorp API
CRUD, profil, admin
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_db,
    get_user_service,
    get_current_user,
    get_current_superuser,
    get_current_tenant_id,
    get_mfa_service,
    get_audit_service,
)
from app.services.mfa import MFAService
from app.services.audit import AuditService
from app.models import User
from app.schemas import (
    UserCreate,
    UserCreateByAdmin,
    UserUpdate,
    UserUpdateByAdmin,
    UserRead,
    UserReadFull,
    UserProfile,
    UserList,
    success_response,
    paginated_response,
)
from app.services.user import UserService
from app.services.exceptions import (
    EmailAlreadyExistsError,
    UserNotFoundError,
    TenantNotFoundError,
)


router = APIRouter(prefix="/users", tags=["Users"])


# ============================================
# Profil Utilisateur (self)
# ============================================

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Mon profil",
    description="Recupere le profil de l'utilisateur connecte"
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Retourne le profil complet de l'utilisateur connecte.
    Inclut le statut MFA reel.
    """
    # Recuperer le statut MFA reel
    mfa_status = mfa_service.get_mfa_status(current_user.id)
    has_mfa = mfa_status.get("enabled", False)

    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        phone=current_user.phone,
        is_verified=current_user.is_verified,
        has_mfa=has_mfa,
        tenant_id=current_user.tenant_id,
        tenant_name=current_user.tenant.name if current_user.tenant else None,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.put(
    "/me",
    response_model=UserRead,
    summary="Modifier mon profil",
    description="Met a jour le profil de l'utilisateur connecte"
)
def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """
    Met a jour les informations du profil de l'utilisateur connecte.

    Champs modifiables:
    - first_name
    - last_name
    - phone
    """
    updated_user = user_service.update_user(
        user_id=current_user.id,
        data=data.model_dump(exclude_unset=True)
    )

    return UserRead.model_validate(updated_user)


# ============================================
# CRUD Utilisateurs (Admin)
# ============================================

@router.get(
    "",
    response_model=UserList,
    summary="Lister les utilisateurs",
    description="Liste les utilisateurs du tenant (admin requis)"
)
def list_users(
    skip: int = Query(0, ge=0, description="Nombre a sauter"),
    limit: int = Query(20, ge=1, le=100, description="Nombre maximum"),
    current_user: User = Depends(get_current_superuser),
    tenant_id: int = Depends(get_current_tenant_id),
    user_service: UserService = Depends(get_user_service)
):
    """
    Liste les utilisateurs du tenant avec pagination.
    Requiert les privileges superuser.
    """
    users = user_service.list_users(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit
    )
    total = user_service.count_users(tenant_id)

    return UserList(
        users=[UserRead.model_validate(u) for u in users],
        total=total
    )


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Creer un utilisateur",
    description="Cree un nouvel utilisateur (admin requis)"
)
def create_user(
    data: UserCreateByAdmin,
    current_user: User = Depends(get_current_superuser),
    tenant_id: int = Depends(get_current_tenant_id),
    user_service: UserService = Depends(get_user_service)
):
    """
    Cree un nouvel utilisateur dans le tenant.
    Requiert les privileges superuser.
    """
    try:
        new_user = user_service.create_user(
            email=data.email,
            password=data.password,
            tenant_id=tenant_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            is_active=data.is_active,
            is_verified=data.is_verified,
            is_superuser=data.is_superuser
        )
        return UserRead.model_validate(new_user)

    except EmailAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e.message)
        )
    except TenantNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message)
        )


@router.get(
    "/{user_id}",
    response_model=UserReadFull,
    summary="Obtenir un utilisateur",
    description="Recupere un utilisateur par ID (admin requis)"
)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service)
):
    """
    Recupere les details complets d'un utilisateur.
    Requiert les privileges superuser.
    """
    user = user_service.get_user(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    # Verifier que l'utilisateur appartient au meme tenant
    if user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse"
        )

    return UserReadFull.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserReadFull,
    summary="Modifier un utilisateur",
    description="Met a jour un utilisateur (admin requis)"
)
def update_user(
    user_id: int,
    data: UserUpdateByAdmin,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service)
):
    """
    Met a jour les informations d'un utilisateur.
    Requiert les privileges superuser.
    """
    # Verifier que l'utilisateur existe et appartient au tenant
    user = user_service.get_user(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    if user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse"
        )

    try:
        updated_user = user_service.update_user(
            user_id=user_id,
            data=data.model_dump(exclude_unset=True)
        )
        return UserReadFull.model_validate(updated_user)

    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un utilisateur",
    description="Supprime un utilisateur (admin requis)"
)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Supprime un utilisateur.
    Requiert les privileges superuser.
    """
    # Verifier que l'utilisateur existe et appartient au tenant
    user = user_service.get_user(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    if user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse"
        )

    # Empecher la suppression de soi-meme
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer son propre compte"
        )

    try:
        user_service.delete_user(user_id)
        # Audit de la suppression
        audit_service.log_action(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            action="user.deleted",
            resource="user",
            resource_id=str(user_id),
            details={"deleted_user_email": user.email}
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )


# ============================================
# Actions Admin
# ============================================

@router.post(
    "/{user_id}/verify",
    summary="Verifier un utilisateur",
    description="Marque un utilisateur comme verifie (admin requis)"
)
def verify_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service)
):
    """
    Marque un utilisateur comme verifie (email confirme).
    Requiert les privileges superuser.
    """
    user = user_service.get_user(user_id)

    if user is None or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    user_service.verify_user(user_id)
    return success_response(message="Utilisateur verifie")


@router.post(
    "/{user_id}/activate",
    summary="Activer un utilisateur",
    description="Active un compte utilisateur (admin requis)"
)
def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Active un compte utilisateur.
    Requiert les privileges superuser.
    """
    user = user_service.get_user(user_id)

    if user is None or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    user_service.activate_user(user_id)

    # Audit de l'activation
    audit_service.log_action(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="user.activated",
        resource="user",
        resource_id=str(user_id),
        details={"activated_user_email": user.email}
    )

    return success_response(message="Utilisateur active")


@router.post(
    "/{user_id}/deactivate",
    summary="Desactiver un utilisateur",
    description="Desactive un compte utilisateur (admin requis)"
)
def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    user_service: UserService = Depends(get_user_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Desactive un compte utilisateur.
    Requiert les privileges superuser.
    """
    user = user_service.get_user(user_id)

    if user is None or user.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    # Empecher la desactivation de soi-meme
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de desactiver son propre compte"
        )

    user_service.deactivate_user(user_id)

    # Audit de la desactivation
    audit_service.log_action(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        action="user.deactivated",
        resource="user",
        resource_id=str(user_id),
        details={"deactivated_user_email": user.email}
    )

    return success_response(message="Utilisateur desactive")
