"""
Endpoints GDPR pour MassaCorp API.

Ce module gere les endpoints de conformite GDPR:
- GET /gdpr/export: Export des donnees (Art. 15 - Right to Access)
- DELETE /gdpr/delete: Suppression des donnees (Art. 17 - Right to Erasure)
- POST /gdpr/anonymize: Anonymisation des donnees
- GET /gdpr/inventory: Inventaire des donnees (Art. 30)

Securite:
- Authentification requise pour tous les endpoints
- Suppression/anonymisation reservees aux admins
- Audit logging de toutes les operations
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.dependencies import (
    get_current_user,
    get_current_superuser,
    get_gdpr_service,
    get_audit_service,
)
from app.core.exceptions import NotFound
from app.models import User
from app.schemas.gdpr import (
    GDPRExportResponse,
    GDPRDeleteRequest,
    GDPRDeleteResponse,
    GDPRAnonymizeRequest,
    GDPRAnonymizeResponse,
    GDPRInventoryResponse,
    GDPRUserData,
    GDPRSessionData,
    GDPRAuditData,
    GDPRMFAData,
    GDPRRecoveryCodeData,
    GDPRAPIKeyData,
    GDPRRetentionInfo,
    DataCategory,
    DataProcessor,
    DataSubjectRights,
)
from app.services.gdpr import GDPRService
from app.services.audit import AuditService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gdpr", tags=["GDPR Compliance"])


def _build_export_response(export_data: dict) -> GDPRExportResponse:
    """
    Construit une reponse GDPRExportResponse a partir des donnees brutes.

    Args:
        export_data: Dictionnaire retourne par GDPRService.export_user_data()

    Returns:
        GDPRExportResponse formate
    """
    # Build MFA data if present
    mfa_data = None
    if export_data.get("mfa_data"):
        mfa_data = GDPRMFAData(**export_data["mfa_data"])

    return GDPRExportResponse(
        export_date=export_data["export_date"],
        user=GDPRUserData(**export_data["user"]),
        sessions=[GDPRSessionData(**s) for s in export_data["sessions"]],
        audit_logs=[GDPRAuditData(**a) for a in export_data["audit_logs"]],
        mfa_data=mfa_data,
        recovery_codes=[GDPRRecoveryCodeData(**c) for c in export_data.get("recovery_codes", [])],
        api_keys=[GDPRAPIKeyData(**k) for k in export_data.get("api_keys", [])],
        data_retention=GDPRRetentionInfo(**export_data["data_retention"])
    )


@router.get(
    "/export",
    response_model=GDPRExportResponse,
    summary="Exporter mes donnees (Art. 15)",
    description="Exporte toutes les donnees personnelles de l'utilisateur courant"
)
def export_my_data(
    http_request: Request,
    current_user: User = Depends(get_current_user),
    gdpr_service: GDPRService = Depends(get_gdpr_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Exporte les donnees personnelles de l'utilisateur courant.

    Conformite GDPR Article 15 - Droit d'acces.

    Retourne:
    - Donnees du profil utilisateur
    - Historique des sessions
    - Logs d'audit (1000 derniers)
    - Informations sur la retention des donnees

    Le format JSON est utilisable pour la portabilite des donnees.
    """
    client_ip = http_request.client.host if http_request.client else None

    # Exporter les donnees
    try:
        export_data = gdpr_service.export_user_data(current_user.id)
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    # Logger l'action
    audit_service.log_action(
        action="gdpr_data_export",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="gdpr",
        ip_address=client_ip,
        details={"export_type": "self"}
    )

    return _build_export_response(export_data)


@router.get(
    "/export/{user_id}",
    response_model=GDPRExportResponse,
    summary="Exporter donnees utilisateur (Admin)",
    description="Exporte les donnees d'un utilisateur specifique (admin uniquement)"
)
def export_user_data(
    user_id: int,
    http_request: Request,
    current_user: User = Depends(get_current_superuser),
    gdpr_service: GDPRService = Depends(get_gdpr_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Exporte les donnees d'un utilisateur specifique (admin uniquement).

    Utilisez ce endpoint pour les demandes d'acces de tiers
    ou pour l'assistance utilisateur.

    Args:
        user_id: ID de l'utilisateur dont exporter les donnees

    Requires:
        Privileges superuser
    """
    client_ip = http_request.client.host if http_request.client else None

    try:
        export_data = gdpr_service.export_user_data(user_id)
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    # Logger l'action
    audit_service.log_action(
        action="gdpr_data_export_admin",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="gdpr",
        ip_address=client_ip,
        details={"exported_user_id": user_id}
    )

    return _build_export_response(export_data)


@router.delete(
    "/delete",
    response_model=GDPRDeleteResponse,
    summary="Supprimer donnees utilisateur (Art. 17)",
    description="Supprime toutes les donnees d'un utilisateur (admin uniquement)"
)
def delete_user_data(
    request: GDPRDeleteRequest,
    http_request: Request,
    current_user: User = Depends(get_current_superuser),
    gdpr_service: GDPRService = Depends(get_gdpr_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Supprime toutes les donnees d'un utilisateur.

    Conformite GDPR Article 17 - Droit a l'effacement.

    ATTENTION: Cette operation est IRREVERSIBLE!

    Args:
        user_id: ID de l'utilisateur a supprimer
        reason: Raison de la suppression (obligatoire pour audit)
        confirm: Doit etre True pour confirmer

    Requires:
        Privileges superuser

    Effects:
    - Toutes les sessions sont revoquees
    - Le compte est supprime (cascade sur sessions)
    - Un log d'audit est conserve (conformite)
    """
    client_ip = http_request.client.host if http_request.client else None

    # Verification de confirmation
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation requise (confirm=true)"
        )

    # Interdire la suppression de son propre compte via cet endpoint
    if request.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas supprimer votre propre compte via cet endpoint"
        )

    try:
        deleted = gdpr_service.delete_user_data(
            user_id=request.user_id,
            reason=request.reason,
            performed_by=current_user.id
        )
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression"
        )

    # Logger l'action dans l'audit
    audit_service.log_action(
        action="gdpr_user_deleted",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="gdpr",
        ip_address=client_ip,
        details={
            "deleted_user_id": request.user_id,
            "reason": request.reason,
            "performed_by": current_user.id
        }
    )

    logger.warning(
        f"GDPR: User {request.user_id} deleted by admin {current_user.id}, "
        f"reason: {request.reason}"
    )

    return GDPRDeleteResponse(
        success=True,
        message="Donnees utilisateur supprimees avec succes",
        deleted_user_id=request.user_id
    )


@router.post(
    "/anonymize",
    response_model=GDPRAnonymizeResponse,
    summary="Anonymiser donnees utilisateur",
    description="Anonymise les donnees d'un utilisateur (admin uniquement)"
)
def anonymize_user_data(
    request: GDPRAnonymizeRequest,
    http_request: Request,
    current_user: User = Depends(get_current_superuser),
    gdpr_service: GDPRService = Depends(get_gdpr_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Anonymise les donnees d'un utilisateur.

    Alternative a la suppression complete:
    - Les PII sont remplacees par des valeurs anonymes
    - Le compte est desactive
    - Les donnees statistiques restent exploitables
    - L'utilisateur ne peut plus se connecter

    Args:
        user_id: ID de l'utilisateur a anonymiser
        reason: Raison de l'anonymisation

    Requires:
        Privileges superuser
    """
    client_ip = http_request.client.host if http_request.client else None

    # Interdire l'anonymisation de son propre compte
    if request.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas anonymiser votre propre compte"
        )

    try:
        anonymized = gdpr_service.anonymize_user_data(
            user_id=request.user_id,
            reason=request.reason,
            performed_by=current_user.id
        )
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouve"
        )

    if not anonymized:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'anonymisation"
        )

    # Logger l'action dans l'audit
    audit_service.log_action(
        action="gdpr_user_anonymized",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="gdpr",
        ip_address=client_ip,
        details={
            "anonymized_user_id": request.user_id,
            "reason": request.reason,
            "performed_by": current_user.id
        }
    )

    logger.info(
        f"GDPR: User {request.user_id} anonymized by admin {current_user.id}, "
        f"reason: {request.reason}"
    )

    return GDPRAnonymizeResponse(
        success=True,
        message="Donnees utilisateur anonymisees avec succes",
        anonymized_user_id=request.user_id
    )


@router.get(
    "/inventory",
    response_model=GDPRInventoryResponse,
    summary="Inventaire des donnees (Art. 30)",
    description="Retourne l'inventaire des donnees collectees par le tenant"
)
def get_data_inventory(
    current_user: User = Depends(get_current_user),
    gdpr_service: GDPRService = Depends(get_gdpr_service)
):
    """
    Retourne l'inventaire des donnees collectees.

    Conformite GDPR Article 30 - Registre des traitements.

    Document:
    - Les categories de donnees collectees
    - Les finalites de traitement
    - Les bases legales
    - Les durees de retention
    - Les sous-traitants
    - Les droits des personnes concernees

    Ce document aide a la conformite et peut etre fourni
    aux autorites de controle sur demande.
    """
    inventory_data = gdpr_service.get_data_inventory(current_user.tenant_id)

    return GDPRInventoryResponse(
        tenant_id=inventory_data["tenant_id"],
        generated_at=inventory_data["generated_at"],
        data_categories=[
            DataCategory(**cat) for cat in inventory_data["data_categories"]
        ],
        data_processors=[
            DataProcessor(**proc) for proc in inventory_data["data_processors"]
        ],
        data_subject_rights=DataSubjectRights(**inventory_data["data_subject_rights"])
    )
