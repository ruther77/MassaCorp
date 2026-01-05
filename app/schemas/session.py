"""
Schemas Pydantic pour les Sessions MassaCorp.

Ce module definit les schemas pour:
- Lecture des sessions actives
- Termination de sessions
- Informations sur les devices connectes
"""
import ipaddress
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import BaseSchema, TimestampSchema

# Limite de longueur pour user_agent (evite les abus)
MAX_USER_AGENT_LENGTH = 512


def validate_ip_address(ip: str) -> str:
    """
    Valide une adresse IPv4 ou IPv6.

    Args:
        ip: Adresse IP a valider

    Returns:
        L'adresse IP validee

    Raises:
        ValueError: Si l'adresse IP est invalide
    """
    try:
        # ipaddress.ip_address valide IPv4 et IPv6
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        raise ValueError(f"Adresse IP invalide: {ip}")


class SessionBase(BaseSchema):
    """Schema de base pour une session"""
    ip_address: Optional[str] = Field(
        None,
        description="Adresse IP de connexion (IPv4 ou IPv6)"
    )
    user_agent: Optional[str] = Field(
        None,
        description="User-Agent du navigateur (max 512 caracteres, tronque si plus long)"
    )

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: Optional[str]) -> Optional[str]:
        """Valide le format IPv4 ou IPv6."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        return validate_ip_address(v)

    @field_validator("user_agent")
    @classmethod
    def truncate_user_agent(cls, v: Optional[str]) -> Optional[str]:
        """Tronque le user_agent si trop long."""
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > MAX_USER_AGENT_LENGTH:
            return v[:MAX_USER_AGENT_LENGTH]
        return v


class SessionRead(SessionBase, TimestampSchema):
    """Schema pour la lecture d'une session"""
    id: UUID = Field(..., description="ID unique de la session")
    user_id: int = Field(..., description="ID de l'utilisateur")
    tenant_id: int = Field(..., description="ID du tenant")
    is_active: bool = Field(..., description="Session active ou terminee")
    last_seen_at: Optional[datetime] = Field(None, description="Derniere activite")

    # Informations derivees (calcul cote serveur)
    device_type: Optional[str] = Field(None, description="Type de device (desktop, mobile, tablet)")
    browser: Optional[str] = Field(None, description="Navigateur detecte")
    os: Optional[str] = Field(None, description="Systeme d'exploitation detecte")
    is_current: bool = Field(False, description="True si c'est la session courante")

    class Config:
        from_attributes = True


class SessionList(BaseSchema):
    """Schema pour la liste des sessions"""
    sessions: List[SessionRead] = Field(..., description="Liste des sessions")
    total: int = Field(..., description="Nombre total de sessions")
    active_count: int = Field(..., description="Nombre de sessions actives")


class SessionTerminateRequest(BaseSchema):
    """Schema pour terminer une ou plusieurs sessions"""
    session_ids: Optional[List[UUID]] = Field(
        None,
        description="IDs des sessions a terminer (vide = toutes sauf courante)"
    )
    terminate_all: bool = Field(
        False,
        description="Terminer toutes les sessions sauf la courante"
    )


class SessionTerminateResponse(BaseSchema):
    """Schema pour la reponse de termination"""
    terminated_count: int = Field(..., description="Nombre de sessions terminees")
    message: str = Field(..., description="Message de confirmation")


class SessionActivity(BaseSchema):
    """Schema pour l'activite d'une session"""
    session_id: UUID = Field(..., description="ID de la session")
    action: str = Field(..., description="Type d'action (login, refresh, api_call)")
    timestamp: datetime = Field(..., description="Horodatage de l'action")
    ip_address: Optional[str] = Field(None, description="IP utilisee")
    details: Optional[dict] = Field(None, description="Details supplementaires")
