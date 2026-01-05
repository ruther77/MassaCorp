"""
Endpoints de reinitialisation de mot de passe pour MassaCorp API.

Ce module gere les endpoints:
- POST /password-reset/request: Demande de reinitialisation
- POST /password-reset/confirm: Confirmation avec nouveau mot de passe
- GET /password-reset/validate/{token}: Valider un token (optionnel)

Securite:
- Rate limiting (3 demandes/heure/utilisateur)
- Tokens expires apres 1 heure
- Tokens a usage unique (hashees en base)
- Pas de divulgation d'existence de compte
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.dependencies import (
    get_password_reset_service,
    get_audit_service,
)
from app.core.config import get_settings
from app.core.logging import mask_email
from app.core.security import hash_password
from app.schemas import (
    PasswordResetRequest,
    PasswordResetConfirm,
    success_response,
)
from app.services.password_reset import (
    PasswordResetService,
    RateLimitExceeded,
    TokenExpired,
    TokenAlreadyUsed,
    InvalidToken,
)
from app.services.audit import AuditService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/password-reset", tags=["Password Reset"])


@router.post(
    "/request",
    summary="Demander une reinitialisation",
    description="Envoie un email de reinitialisation de mot de passe"
)
def request_password_reset(
    request: PasswordResetRequest,
    http_request: Request,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Demande une reinitialisation de mot de passe.

    Un email sera envoye avec un lien de reinitialisation.

    SECURITE:
    - La response est toujours la meme, que l'email existe ou non
    - Cela evite l'enumeration des comptes
    - Rate limiting: max 3 demandes par heure par email

    Args:
        email: Adresse email du compte

    Returns:
        Message de succes (toujours, meme si email inexistant)
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

    client_ip = http_request.client.host if http_request.client else None

    try:
        result = password_reset_service.request_reset_by_email(
            email=request.email,
            tenant_id=tenant_id
        )

        # Si l'utilisateur existe, result contient (token_obj, raw_token)
        if result:
            token_obj, raw_token = result

            # En production: envoyer l'email avec raw_token
            # Pour dev, on log le token (NE PAS FAIRE EN PROD!)
            settings = get_settings()
            if settings.is_development or settings.is_testing:
                logger.info(
                    f"Password reset token genere pour {mask_email(request.email)}: {raw_token[:8]}..."
                )

            # Logger l'action
            audit_service.log_action(
                action="password_reset_requested",
                user_id=token_obj.user_id,
                tenant_id=tenant_id,
                resource="password_reset",
                ip_address=client_ip,
                details={"email": request.email}
            )

    except RateLimitExceeded:
        # Ne pas reveler le rate limiting (security by obscurity)
        # Mais logger pour monitoring
        logger.warning(f"Rate limit exceeded for password reset: {mask_email(request.email)}")

    # Toujours retourner le meme message
    return success_response(
        message="Si un compte existe avec cet email, un lien de reinitialisation sera envoye."
    )


@router.post(
    "/confirm",
    summary="Confirmer la reinitialisation",
    description="Definit un nouveau mot de passe avec le token recu"
)
def confirm_password_reset(
    request: PasswordResetConfirm,
    http_request: Request,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Confirme la reinitialisation avec le nouveau mot de passe.

    Le token doit etre valide, non expire et non utilise.
    Apres utilisation:
    - Le mot de passe est change
    - Toutes les sessions sont revoquees
    - Tous les tokens de reset sont invalides

    Args:
        token: Token recu par email
        new_password: Nouveau mot de passe (min 8 chars, complexite requise)

    Returns:
        Message de succes
    """
    client_ip = http_request.client.host if http_request.client else None

    try:
        # Hasher le nouveau mot de passe
        new_password_hash = hash_password(request.new_password)

        # Effectuer le reset
        user_id = password_reset_service.reset_password(
            raw_token=request.token,
            new_password_hash=new_password_hash
        )

        # Logger l'action
        audit_service.log_action(
            action="password_reset_completed",
            user_id=user_id,
            tenant_id=None,  # On n'a pas le tenant_id ici
            resource="password_reset",
            ip_address=client_ip,
            details={}
        )

        return success_response(
            message="Mot de passe reinitialise avec succes. Toutes vos sessions ont ete deconnectees."
        )

    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de reinitialisation invalide ou expire"
        )

    except TokenExpired:
        # SECURITE: Message generique - ne pas reveler que le token existait
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de reinitialisation invalide ou expire"
        )

    except TokenAlreadyUsed:
        # SECURITE: Message generique - ne pas reveler que le token a ete utilise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de reinitialisation invalide ou expire"
        )


@router.get(
    "/validate/{token}",
    summary="Valider un token",
    description="Verifie si un token de reset est valide (sans l'utiliser)"
)
def validate_reset_token(
    token: str,
    password_reset_service: PasswordResetService = Depends(get_password_reset_service)
):
    """
    Valide un token de reinitialisation sans l'utiliser.

    Utile pour le frontend: verifier le token avant d'afficher
    le formulaire de nouveau mot de passe.

    Args:
        token: Token de reinitialisation

    Returns:
        valid: True si le token est valide
    """
    try:
        password_reset_service.validate_token(token)
        return success_response(
            data={"valid": True},
            message="Token valide"
        )

    except (InvalidToken, TokenExpired, TokenAlreadyUsed) as e:
        return success_response(
            data={"valid": False, "reason": e.error_code},
            message=str(e.message)
        )
