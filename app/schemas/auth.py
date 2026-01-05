"""
Schemas Pydantic pour l'authentification
Login, tokens, refresh, logout
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.base import BaseSchema


class LoginRequest(BaseSchema):
    """Requete de connexion"""
    email: EmailStr = Field(..., description="Adresse email")
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Mot de passe (max 128 caracteres)"
    )
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=6, description="Code MFA (si active)")
    captcha_token: Optional[str] = Field(None, description="Token CAPTCHA (requis apres echecs multiples)")

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        """Normalise l'email en minuscules"""
        return v.lower().strip()


class TokenResponse(BaseSchema):
    """Response contenant les tokens"""
    access_token: str = Field(..., description="Token JWT d'acces")
    refresh_token: str = Field(..., description="Token JWT de refresh")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Duree de validite en secondes")


class TokenPayload(BaseSchema):
    """Payload decode d'un token JWT"""
    sub: str = Field(..., description="ID utilisateur")
    tenant_id: int = Field(..., description="ID tenant")
    email: Optional[str] = None
    type: str = Field(..., description="Type de token (access/refresh)")
    exp: int = Field(..., description="Timestamp d'expiration")
    iat: int = Field(..., description="Timestamp de creation")
    jti: Optional[str] = Field(None, description="ID unique du token (refresh)")


class RefreshTokenRequest(BaseSchema):
    """Requete de refresh de token"""
    refresh_token: str = Field(..., description="Token de refresh valide")


class LogoutRequest(BaseSchema):
    """
    Requete de deconnexion.

    Options:
    - refresh_token: Revoque le token de refresh specifique
    - session_id: Termine une session specifique (UUID)
    - all_sessions: Termine toutes les sessions de l'utilisateur
    """
    refresh_token: Optional[str] = Field(None, description="Token de refresh a revoquer")
    session_id: Optional[str] = Field(None, description="ID de session a terminer (UUID)")
    all_sessions: bool = Field(default=False, description="Revoquer toutes les sessions")


class PasswordResetRequest(BaseSchema):
    """Requete de reset de mot de passe"""
    email: EmailStr = Field(..., description="Email du compte")

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower().strip()


class PasswordResetConfirm(BaseSchema):
    """Confirmation de reset de mot de passe"""
    token: str = Field(..., description="Token de reset")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Valide la force du mot de passe"""
        from app.core.security import validate_password_strength
        validate_password_strength(v)
        return v


class ChangePasswordRequest(BaseSchema):
    """Requete de changement de mot de passe"""
    current_password: str = Field(..., description="Mot de passe actuel")
    new_password: str = Field(..., min_length=8, description="Nouveau mot de passe")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        from app.core.security import validate_password_strength
        validate_password_strength(v)
        return v


class AuthStatusResponse(BaseSchema):
    """Status d'authentification"""
    authenticated: bool = False
    user_id: Optional[int] = None
    tenant_id: Optional[int] = None
    email: Optional[str] = None
    mfa_required: bool = False
    mfa_enabled: bool = False


class MFALoginRequest(BaseSchema):
    """Requete pour completer le login MFA (etape 2)"""
    mfa_session_token: str = Field(..., description="Token de session MFA")
    totp_code: str = Field(..., min_length=6, max_length=6, description="Code TOTP a 6 chiffres")

    @field_validator("totp_code")
    @classmethod
    def validate_totp_format(cls, v: str) -> str:
        """Valide que le code TOTP contient uniquement des chiffres"""
        if not v.isdigit():
            raise ValueError("Le code TOTP doit contenir uniquement des chiffres")
        return v


class MFARequiredResponse(BaseSchema):
    """Response quand MFA est requis"""
    mfa_required: bool = True
    mfa_session_token: str = Field(..., description="Token de session MFA pour l'etape 2")
    message: str = Field(default="MFA verification required")


class LoginResponse(BaseSchema):
    """
    Response unifiee pour le login - coherente que MFA soit requis ou non.

    Cas 1: Login sans MFA (success=True, mfa_required=False)
        - access_token, refresh_token, token_type, expires_in remplis
        - mfa_session_token est None

    Cas 2: MFA requis (success=True, mfa_required=True)
        - mfa_session_token rempli
        - access_token, refresh_token sont None

    Cas 3: CAPTCHA requis (success=False, captcha_required=True)
        - captcha_required, captcha_site_key remplis
        - Tous les tokens sont None
    """
    success: bool = Field(default=True, description="Login reussi (credentials valides)")
    # Champs tokens - optionnels si MFA requis
    access_token: Optional[str] = Field(None, description="Token JWT d'acces")
    refresh_token: Optional[str] = Field(None, description="Token JWT de refresh")
    token_type: Optional[str] = Field(None, description="Type de token (bearer)")
    expires_in: Optional[int] = Field(None, description="Duree de validite en secondes")
    # Champs MFA - optionnels si login complet
    mfa_required: bool = Field(default=False, description="True si MFA requis pour completer")
    mfa_session_token: Optional[str] = Field(None, description="Token de session MFA")
    # Champs CAPTCHA - pour bruteforce protection
    captcha_required: bool = Field(default=False, description="True si CAPTCHA requis")
    captcha_site_key: Optional[str] = Field(None, description="Cle publique CAPTCHA (frontend)")
    message: Optional[str] = Field(None, description="Message informatif")


class RegisterRequest(BaseSchema):
    """Requete d'inscription publique"""
    email: EmailStr = Field(..., description="Adresse email")
    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="Mot de passe (min 12 caracteres)"
    )
    first_name: str = Field(..., min_length=2, max_length=100, description="Prenom")
    last_name: str = Field(..., min_length=2, max_length=100, description="Nom")

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        """Normalise l'email en minuscules"""
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Valide la force du mot de passe"""
        from app.core.security import validate_password_strength
        validate_password_strength(v)
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        if v:
            return v.strip()
        return v
