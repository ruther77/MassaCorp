"""
Endpoints MFA pour MassaCorp API.

Ce module gere les endpoints d'authentification multi-facteur:
- POST /mfa/setup: Configure MFA pour l'utilisateur courant
- POST /mfa/enable: Active MFA avec verification du code TOTP
- POST /mfa/disable: Desactive MFA
- GET /mfa/status: Retourne le status MFA
- POST /mfa/verify: Verifie un code TOTP
- POST /mfa/recovery/verify: Verifie un code de recuperation
- POST /mfa/recovery/regenerate: Regenere les codes de recuperation
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user, get_mfa_service
from app.models import User
from app.schemas.mfa import (
    MFASetupResponse,
    MFAEnableRequest,
    MFAEnableResponse,
    MFADisableRequest,
    MFADisableResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MFARecoveryVerifyRequest,
    MFARecoveryVerifyResponse,
    MFARegenerateCodesRequest,
    MFARegenerateCodesResponse,
)
from app.schemas.base import success_response
from app.services.mfa import (
    MFAService,
    MFAAlreadyEnabledError,
    MFANotConfiguredError,
    InvalidMFACodeError,
    MFALockoutError,
)


router = APIRouter(prefix="/mfa", tags=["MFA"])


@router.post(
    "/setup",
    response_model=MFASetupResponse,
    summary="Configurer MFA",
    description="Configure MFA pour l'utilisateur courant et retourne le secret + QR code"
)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Configure MFA pour l'utilisateur courant.

    Genere un nouveau secret TOTP et retourne:
    - secret: Secret en base32 pour configuration manuelle
    - provisioning_uri: URI otpauth:// pour apps TOTP
    - qr_code_base64: QR code en PNG base64

    Si MFA est deja active, retourne une erreur 400.
    Si un secret existe mais n'est pas active, le retourne.
    """
    try:
        result = mfa_service.setup_mfa(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            email=current_user.email
        )
    except MFAAlreadyEnabledError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA est deja active pour cet utilisateur"
        )

    return MFASetupResponse(
        success=True,
        secret=result["secret"],
        provisioning_uri=result["provisioning_uri"],
        qr_code_base64=result.get("qr_code_base64")
    )


@router.post(
    "/enable",
    response_model=MFAEnableResponse,
    summary="Activer MFA",
    description="Active MFA apres verification du code TOTP"
)
def enable_mfa(
    request: MFAEnableRequest,
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Active MFA pour l'utilisateur courant.

    Requiert:
    - Un secret MFA configure (via /mfa/setup)
    - Un code TOTP valide pour verification

    Retourne:
    - enabled: True si active avec succes
    - recovery_codes: 10 codes de recuperation a sauvegarder

    IMPORTANT: Les codes de recuperation ne sont affiches qu'une seule fois.
    """
    try:
        result = mfa_service.enable_mfa(
            user_id=current_user.id,
            code=request.code
        )
    except MFANotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA n'est pas configure. Utilisez /mfa/setup d'abord."
        )
    except InvalidMFACodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code TOTP invalide"
        )

    return MFAEnableResponse(
        success=True,
        enabled=result["enabled"],
        recovery_codes=result["recovery_codes"]
    )


@router.post(
    "/disable",
    response_model=MFADisableResponse,
    summary="Desactiver MFA",
    description="Desactive MFA pour l'utilisateur courant"
)
def disable_mfa(
    request: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Desactive MFA pour l'utilisateur courant.

    Requiert un code TOTP valide pour confirmation.
    Supprime egalement tous les codes de recuperation.
    """
    try:
        mfa_service.disable_mfa(
            user_id=current_user.id,
            code=request.code
        )
    except MFANotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA n'est pas active pour cet utilisateur"
        )
    except InvalidMFACodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code TOTP invalide"
        )

    return MFADisableResponse(
        success=True,
        enabled=False,
        message="MFA desactive avec succes"
    )


@router.get(
    "/status",
    response_model=MFAStatusResponse,
    summary="Status MFA",
    description="Retourne le status MFA de l'utilisateur courant"
)
def get_mfa_status(
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Retourne le status MFA complet de l'utilisateur courant.

    Inclut:
    - enabled: MFA active ou non
    - configured: Secret MFA existe
    - recovery_codes_remaining: Nombre de codes non utilises
    - last_used_at: Derniere verification reussie
    - created_at: Date de configuration
    """
    status = mfa_service.get_mfa_status(current_user.id)

    return MFAStatusResponse(
        success=True,
        enabled=status["enabled"],
        configured=status["configured"],
        recovery_codes_remaining=status["recovery_codes_remaining"],
        last_used_at=status.get("last_used_at"),
        created_at=status.get("created_at")
    )


@router.post(
    "/verify",
    summary="Verifier code TOTP",
    description="Verifie un code TOTP pour l'utilisateur courant"
)
def verify_totp(
    request: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Verifie un code TOTP pour l'utilisateur courant.

    Utilisé pour:
    - Verifier que l'app TOTP est bien configuree
    - Operations sensibles necessitant re-authentification MFA

    Retourne valid: True/False.

    SECURITE: Lockout apres 5 echecs consecutifs (30 min).
    """
    # Verifier si MFA est configure et active
    if not mfa_service.is_mfa_required(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA n'est pas active pour cet utilisateur"
        )

    try:
        valid = mfa_service.verify_totp(
            user_id=current_user.id,
            code=request.code
        )
    except MFALockoutError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=e.message,
            headers={"Retry-After": str(e.lockout_minutes * 60)}
        )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code TOTP invalide"
        )

    return success_response(
        data={"valid": True},
        message="Code TOTP valide"
    )


@router.post(
    "/recovery/verify",
    response_model=MFARecoveryVerifyResponse,
    summary="Verifier code de recuperation",
    description="Verifie et consomme un code de recuperation"
)
def verify_recovery_code(
    request: MFARecoveryVerifyRequest,
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Verifie et consomme un code de recuperation.

    ATTENTION: Le code est consomme meme si valide.
    Utilisez cette route uniquement en cas de perte de l'app TOTP.
    """
    # Verifier si MFA est configure et active
    if not mfa_service.is_mfa_required(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA n'est pas active pour cet utilisateur"
        )

    valid = mfa_service.verify_recovery_code(
        user_id=current_user.id,
        code=request.code
    )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code de recuperation invalide ou deja utilise"
        )

    # Recuperer le nombre de codes restants
    remaining = mfa_service.get_recovery_codes_count(current_user.id)

    return MFARecoveryVerifyResponse(
        success=True,
        valid=True,
        recovery_codes_remaining=remaining
    )


@router.post(
    "/recovery/regenerate",
    response_model=MFARegenerateCodesResponse,
    summary="Regenerer codes de recuperation",
    description="Regenere de nouveaux codes de recuperation"
)
def regenerate_recovery_codes(
    request: MFARegenerateCodesRequest,
    current_user: User = Depends(get_current_user),
    mfa_service: MFAService = Depends(get_mfa_service)
):
    """
    Regenere les codes de recuperation.

    Requiert un code TOTP valide pour confirmation.
    Invalide tous les anciens codes.

    IMPORTANT: Les nouveaux codes ne sont affiches qu'une seule fois.
    """
    try:
        codes = mfa_service.regenerate_recovery_codes(
            user_id=current_user.id,
            totp_code=request.code
        )
    except MFANotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA n'est pas active pour cet utilisateur"
        )
    except InvalidMFACodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code TOTP invalide"
        )

    return MFARegenerateCodesResponse(
        success=True,
        recovery_codes=codes
    )
