"""
Endpoints de gestion des Sessions pour MassaCorp API.

Ce module gere les endpoints:
- GET /sessions: Liste les sessions actives de l'utilisateur
- GET /sessions/{session_id}: Details d'une session specifique
- DELETE /sessions/{session_id}: Termine une session specifique
- DELETE /sessions: Termine toutes les sessions (sauf courante)

Securite:
- Authentification requise pour tous les endpoints
- Isolation multi-tenant automatique
- Audit logging des operations sensibles
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request

logger = logging.getLogger(__name__)

from app.core.dependencies import (
    get_current_user,
    get_session_service,
    get_audit_service,
    get_current_session_id,
)
from app.models import User
from app.schemas import (
    SessionRead,
    SessionList,
    SessionTerminateRequest,
    SessionTerminateResponse,
    success_response,
)
from app.services.session import SessionService
from app.services.audit import AuditService


router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _parse_user_agent(user_agent: str) -> dict:
    """
    Parse le User-Agent pour extraire device/browser/os.

    Implementation simplifiee - en production utiliser user-agents ou ua-parser.

    Args:
        user_agent: String User-Agent brut

    Returns:
        Dict avec device_type, browser, os
    """
    if not user_agent:
        return {"device_type": "unknown", "browser": "unknown", "os": "unknown"}

    user_agent_lower = user_agent.lower()

    # Detection du device
    if "mobile" in user_agent_lower or "android" in user_agent_lower:
        device_type = "mobile"
    elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    # Detection du navigateur
    if "chrome" in user_agent_lower and "edg" not in user_agent_lower:
        browser = "Chrome"
    elif "firefox" in user_agent_lower:
        browser = "Firefox"
    elif "safari" in user_agent_lower and "chrome" not in user_agent_lower:
        browser = "Safari"
    elif "edg" in user_agent_lower:
        browser = "Edge"
    else:
        browser = "Other"

    # Detection de l'OS
    if "windows" in user_agent_lower:
        os_name = "Windows"
    elif "mac" in user_agent_lower:
        os_name = "macOS"
    elif "linux" in user_agent_lower:
        os_name = "Linux"
    elif "android" in user_agent_lower:
        os_name = "Android"
    elif "iphone" in user_agent_lower or "ipad" in user_agent_lower:
        os_name = "iOS"
    else:
        os_name = "Other"

    return {
        "device_type": device_type,
        "browser": browser,
        "os": os_name
    }


@router.get(
    "",
    response_model=SessionList,
    summary="Liste des sessions",
    description="Retourne toutes les sessions actives de l'utilisateur courant"
)
def list_sessions(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    current_session_id: Optional[UUID] = Depends(get_current_session_id)
):
    """
    Liste les sessions de l'utilisateur courant.

    Par defaut, retourne uniquement les sessions actives.
    Utilisez include_inactive=true pour voir aussi les sessions terminees.

    La session courante est marquee avec is_current=true.
    """
    sessions = session_service.get_user_sessions(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive
    )

    # Transformer en schemas avec infos device
    session_reads = []
    active_count = 0

    for session in sessions:
        ua_info = _parse_user_agent(session.user_agent or "")

        # Identifier la session courante via session_id du token
        is_current = current_session_id is not None and session.id == current_session_id

        session_read = SessionRead(
            id=session.id,
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            ip_address=session.ip,
            user_agent=session.user_agent,
            is_active=session.is_active,
            last_seen_at=session.last_seen_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
            device_type=ua_info["device_type"],
            browser=ua_info["browser"],
            os=ua_info["os"],
            is_current=is_current
        )
        session_reads.append(session_read)

        if session.is_active:
            active_count += 1

    return SessionList(
        sessions=session_reads,
        total=len(session_reads),
        active_count=active_count
    )


@router.get(
    "/{session_id}",
    response_model=SessionRead,
    summary="Details d'une session",
    description="Retourne les details d'une session specifique"
)
def get_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    current_session_id: Optional[UUID] = Depends(get_current_session_id)
):
    """
    Recupere les details d'une session specifique.

    L'utilisateur ne peut voir que ses propres sessions.
    La verification de propriete est faite en une seule requete
    pour prevenir les attaques IDOR (enumeration d'UUID).
    """
    # Recupere la session UNIQUEMENT si elle appartient a l'utilisateur
    # Retourne None dans les deux cas (inexistante ou non-possedee)
    session = session_service.get_session_for_user(session_id, current_user.id)

    if session is None:
        # Reponse identique pour session inexistante ou non-possedee
        # pour ne pas divulguer d'information sur l'existence de sessions
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvee"
        )

    ua_info = _parse_user_agent(session.user_agent or "")

    # Identifier si c'est la session courante
    is_current = current_session_id is not None and session.id == current_session_id

    return SessionRead(
        id=session.id,
        user_id=session.user_id,
        tenant_id=session.tenant_id,
        ip_address=session.ip,
        user_agent=session.user_agent,
        is_active=session.is_active,
        last_seen_at=session.last_seen_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
        device_type=ua_info["device_type"],
        browser=ua_info["browser"],
        os=ua_info["os"],
        is_current=is_current
    )


@router.delete(
    "/{session_id}",
    response_model=SessionTerminateResponse,
    summary="Terminer une session",
    description="Termine une session specifique"
)
def terminate_session(
    session_id: UUID,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Termine une session specifique.

    L'utilisateur ne peut terminer que ses propres sessions.
    La verification de propriete est faite en une seule requete (IDOR safe).
    Un audit log est cree pour cette action.
    """
    # Recupere la session UNIQUEMENT si elle appartient a l'utilisateur
    # Verification atomique pour prevenir les attaques IDOR
    session = session_service.get_session_for_user(session_id, current_user.id)

    if session is None:
        # Reponse identique pour session inexistante ou non-possedee
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session non trouvee"
        )

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette session est deja terminee"
        )

    # Terminer la session (user_id pour double verification)
    terminated = session_service.terminate_session(
        session_id=session_id,
        user_id=current_user.id
    )

    # Logger l'action
    client_ip = http_request.client.host if http_request.client else None
    audit_service.log_action(
        action="session_terminated",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="session",
        ip_address=client_ip,
        details={"terminated_session_ip": session.ip, "session_id": str(session_id)}
    )

    return SessionTerminateResponse(
        terminated_count=1 if terminated else 0,
        message="Session terminee avec succes"
    )


@router.delete(
    "",
    response_model=SessionTerminateResponse,
    summary="Terminer toutes les sessions",
    description="Termine toutes les sessions sauf la session courante"
)
def terminate_all_sessions(
    http_request: Request,
    request: SessionTerminateRequest = None,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    audit_service: AuditService = Depends(get_audit_service),
    current_session_id: Optional[UUID] = Depends(get_current_session_id)
):
    """
    Termine toutes les sessions de l'utilisateur.

    Par defaut, garde la session courante active.
    Utilisez terminate_all=true pour tout terminer (deconnexion complete).

    Un audit log est cree pour cette action.
    """
    # Utiliser le session_id du token pour identifier la session courante
    except_session_id = current_session_id

    if request and request.session_ids:
        # Terminer des sessions specifiques
        count = 0
        for session_id in request.session_ids:
            try:
                session_service.terminate_session(
                    session_id=session_id,
                    user_id=current_user.id
                )
                count += 1
            except Exception as e:
                # Logger l'erreur mais continuer le traitement des autres sessions
                logger.error(
                    f"Echec termination session {session_id} "
                    f"pour user {current_user.id}: {e}"
                )

        terminated_count = count
    else:
        # Terminer toutes les sessions
        terminated_count = session_service.terminate_all_sessions(
            user_id=current_user.id,
            except_session_id=except_session_id
        )

    # Logger l'action
    client_ip = http_request.client.host if http_request.client else None
    audit_service.log_action(
        action="all_sessions_terminated",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        resource="session",
        ip_address=client_ip,
        details={"terminated_count": terminated_count}
    )

    return SessionTerminateResponse(
        terminated_count=terminated_count,
        message=f"{terminated_count} session(s) terminee(s) avec succes"
    )
