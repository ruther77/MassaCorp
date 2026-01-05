"""
Schemas Pydantic pour la conformite GDPR.

Utilises pour:
- Export des donnees (Art. 15)
- Suppression des donnees (Art. 17)
- Anonymisation
- Inventaire des donnees (Art. 30)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


# =============================================================================
# Export Data (Art. 15 - Right to Access)
# =============================================================================


class GDPRUserData(BaseSchema):
    """Donnees utilisateur pour export"""
    id: int
    email: str
    created_at: Optional[str]
    is_active: bool
    tenant_id: int
    mfa_enabled: bool


class GDPRSessionData(BaseSchema):
    """Donnees de session pour export"""
    id: str
    created_at: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    is_active: bool
    revoked_at: Optional[str]


class GDPRAuditData(BaseSchema):
    """Donnees d'audit pour export"""
    event_type: Optional[str]
    created_at: Optional[str]
    ip_address: Optional[str]


class GDPRRetentionInfo(BaseSchema):
    """Informations sur la retention des donnees"""
    policy: str
    contact: str


class GDPRExportResponse(BaseSchema):
    """
    Response complete d'export GDPR (Art. 15).

    Contient toutes les donnees personnelles de l'utilisateur.
    """
    export_date: str
    user: GDPRUserData
    sessions: List[GDPRSessionData]
    audit_logs: List[GDPRAuditData]
    data_retention: GDPRRetentionInfo


# =============================================================================
# Delete Data (Art. 17 - Right to Erasure)
# =============================================================================


class GDPRDeleteRequest(BaseSchema):
    """Request pour suppression des donnees"""
    user_id: int = Field(..., description="ID de l'utilisateur a supprimer")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Raison de la suppression (pour audit)"
    )
    confirm: bool = Field(
        ...,
        description="Confirmation de la suppression (doit etre True)"
    )


class GDPRDeleteResponse(BaseSchema):
    """Response apres suppression"""
    success: bool
    message: str
    deleted_user_id: int


# =============================================================================
# Anonymize Data
# =============================================================================


class GDPRAnonymizeRequest(BaseSchema):
    """Request pour anonymisation des donnees"""
    user_id: int = Field(..., description="ID de l'utilisateur a anonymiser")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Raison de l'anonymisation"
    )


class GDPRAnonymizeResponse(BaseSchema):
    """Response apres anonymisation"""
    success: bool
    message: str
    anonymized_user_id: int


# =============================================================================
# Data Inventory (Art. 30)
# =============================================================================


class DataCategory(BaseSchema):
    """Categorie de donnees collectees"""
    category: str
    fields: List[str]
    purpose: str
    retention: str
    legal_basis: str


class DataProcessor(BaseSchema):
    """Sous-traitant des donnees"""
    name: str
    location: str
    dpa_in_place: bool


class DataSubjectRights(BaseSchema):
    """Droits des personnes concernees"""
    access: str
    deletion: str
    portability: str
    rectification: str


class GDPRInventoryResponse(BaseSchema):
    """
    Inventaire des donnees (Art. 30 RGPD).

    Document les categories de donnees collectees,
    leurs finalites et les droits des utilisateurs.
    """
    tenant_id: int
    generated_at: str
    data_categories: List[DataCategory]
    data_processors: List[DataProcessor]
    data_subject_rights: DataSubjectRights
