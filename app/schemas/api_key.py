"""
Schemas Pydantic pour les API Keys.

Utilises pour:
- Creation d'API Keys
- Listing des keys
- Validation
"""
from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema, TimestampSchema
from app.models.api_key import APIKeyScopes


class APIKeyCreate(BaseSchema):
    """Schema pour creer une API Key"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nom descriptif de la key"
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Date d'expiration (optionnel, None = jamais)"
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Scopes autorises (ex: ['users:read', 'sessions:read']). None = tous les droits."
    )

    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Valide que les scopes sont connus."""
        if v is None:
            return v
        if not APIKeyScopes.validate_scopes(v):
            valid = APIKeyScopes.all_scopes()
            raise ValueError(f"Scopes invalides. Valides: {valid}")
        return v


class APIKeyRead(TimestampSchema):
    """Schema pour lire une API Key (sans la valeur)"""
    id: int
    name: str
    tenant_id: int
    key_prefix: str = Field(description="Prefixe de la key (pour identification)")
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Scopes autorises. None = tous les droits (legacy)."
    )
    is_revoked: bool
    is_expired: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_by_user_id: Optional[int]


class APIKeyCreated(BaseSchema):
    """
    Schema retourne apres creation.

    IMPORTANT: raw_key n'est retournee qu'une seule fois!
    """
    id: int
    name: str
    raw_key: str = Field(description="Cle brute - A SAUVEGARDER IMMEDIATEMENT!")
    key_prefix: str
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Scopes autorises pour cette key."
    )
    expires_at: Optional[datetime]
    message: str = "Cle API creee. Sauvegardez cette valeur, elle ne sera plus affichee."


class APIKeyList(BaseSchema):
    """Schema pour la liste des API Keys"""
    keys: List[APIKeyRead]
    total: int
    active_count: int


class APIKeyRevokeResponse(BaseSchema):
    """Schema de reponse apres revocation"""
    success: bool = True
    message: str
    revoked_key_id: int
