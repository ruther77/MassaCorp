"""
Schemas Pydantic pour l'authentification multi-facteur (MFA).

Ce module fournit les schemas pour:
- Setup MFA (generation secret + QR code)
- Verification TOTP
- Gestion codes de recuperation
- Status MFA
"""
from datetime import datetime
from typing import List, Optional

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema, ResponseBase


class MFASetupRequest(BaseSchema):
    """Requete de setup MFA (optionnel, peut etre vide)"""
    pass


class MFASetupResponse(ResponseBase):
    """Response du setup MFA avec secret et QR code"""
    secret: str = Field(..., description="Secret TOTP en base32")
    provisioning_uri: str = Field(..., description="URI otpauth:// pour configuration")
    qr_code_base64: Optional[str] = Field(None, description="QR code en base64 (PNG)")


class MFAVerifyRequest(BaseSchema):
    """Requete de verification code TOTP"""
    code: str = Field(
        ...,
        min_length=6,
        max_length=9,
        description="Code TOTP a 6 chiffres ou code de recuperation (XXXX-XXXX)"
    )

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Nettoie le code (espaces, tirets)"""
        return v.strip().replace(" ", "").replace("-", "")


class MFAEnableRequest(BaseSchema):
    """Requete d'activation MFA avec code de verification"""
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Code TOTP pour confirmer l'activation"
    )

    @field_validator("code")
    @classmethod
    def validate_totp_code(cls, v: str) -> str:
        """Valide que le code est numerique"""
        cleaned = v.strip()
        if not cleaned.isdigit():
            raise ValueError("Le code doit contenir uniquement des chiffres")
        if len(cleaned) != 6:
            raise ValueError("Le code doit avoir exactement 6 chiffres")
        return cleaned


class MFAEnableResponse(ResponseBase):
    """Response d'activation MFA avec codes de recuperation"""
    enabled: bool = True
    recovery_codes: List[str] = Field(
        ...,
        description="Codes de recuperation a sauvegarder (affiches une seule fois)"
    )


class MFADisableRequest(BaseSchema):
    """Requete de desactivation MFA"""
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Code TOTP pour confirmer la desactivation"
    )

    @field_validator("code")
    @classmethod
    def validate_totp_code(cls, v: str) -> str:
        """Valide que le code est numerique"""
        cleaned = v.strip()
        if not cleaned.isdigit():
            raise ValueError("Le code doit contenir uniquement des chiffres")
        if len(cleaned) != 6:
            raise ValueError("Le code doit avoir exactement 6 chiffres")
        return cleaned


class MFADisableResponse(ResponseBase):
    """Response de desactivation MFA"""
    enabled: bool = False
    message: str = "MFA desactive avec succes"


class MFAStatusResponse(ResponseBase):
    """Status MFA d'un utilisateur"""
    enabled: bool = Field(..., description="MFA active ou non")
    configured: bool = Field(..., description="Secret MFA existe")
    recovery_codes_remaining: int = Field(
        ...,
        ge=0,
        description="Nombre de codes de recuperation restants"
    )
    last_used_at: Optional[datetime] = Field(
        None,
        description="Derniere verification MFA reussie"
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Date de configuration MFA"
    )


class MFARecoveryVerifyRequest(BaseSchema):
    """Requete de verification code de recuperation"""
    code: str = Field(
        ...,
        min_length=8,
        max_length=9,
        description="Code de recuperation (format XXXX-XXXX)"
    )

    @field_validator("code")
    @classmethod
    def normalize_recovery_code(cls, v: str) -> str:
        """Normalise le code (majuscules)"""
        return v.strip().upper()


class MFARecoveryVerifyResponse(ResponseBase):
    """Response verification code de recuperation"""
    valid: bool = Field(..., description="Code valide et consomme")
    recovery_codes_remaining: int = Field(
        ...,
        ge=0,
        description="Nombre de codes restants apres utilisation"
    )


class MFARegenerateCodesRequest(BaseSchema):
    """Requete de regeneration des codes de recuperation"""
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Code TOTP pour confirmer la regeneration"
    )

    @field_validator("code")
    @classmethod
    def validate_totp_code(cls, v: str) -> str:
        """Valide que le code est numerique"""
        cleaned = v.strip()
        if not cleaned.isdigit():
            raise ValueError("Le code doit contenir uniquement des chiffres")
        if len(cleaned) != 6:
            raise ValueError("Le code doit avoir exactement 6 chiffres")
        return cleaned


class MFARegenerateCodesResponse(ResponseBase):
    """Response regeneration codes de recuperation"""
    recovery_codes: List[str] = Field(
        ...,
        description="Nouveaux codes de recuperation"
    )


class MFALoginVerifyRequest(BaseSchema):
    """Requete de verification MFA pendant login"""
    code: str = Field(
        ...,
        min_length=6,
        max_length=9,
        description="Code TOTP ou code de recuperation"
    )
    use_recovery: bool = Field(
        default=False,
        description="Utiliser un code de recuperation au lieu du TOTP"
    )

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Nettoie le code"""
        return v.strip().replace(" ", "")
