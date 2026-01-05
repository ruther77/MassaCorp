"""
Schemas Pydantic pour l'authentification OAuth
Google, Facebook, GitHub, etc.
"""
from datetime import datetime
from typing import Optional, Literal
from enum import Enum

from pydantic import Field, HttpUrl

from app.schemas.base import BaseSchema


class OAuthProvider(str, Enum):
    """Providers OAuth supportes"""
    GOOGLE = "google"
    FACEBOOK = "facebook"
    GITHUB = "github"


class OAuthInitRequest(BaseSchema):
    """Requete pour initier le flow OAuth"""
    provider: OAuthProvider = Field(..., description="Provider OAuth")
    redirect_uri: Optional[str] = Field(None, description="URI de redirection apres auth")


class OAuthInitResponse(BaseSchema):
    """Response avec l'URL d'autorisation"""
    auth_url: str = Field(..., description="URL vers laquelle rediriger l'utilisateur")
    state: str = Field(..., description="State pour verification CSRF")


class OAuthCallbackRequest(BaseSchema):
    """Requete callback OAuth"""
    code: str = Field(..., description="Code d'autorisation du provider")
    state: str = Field(..., description="State pour verification CSRF")


class OAuthCallbackResponse(BaseSchema):
    """Response apres callback OAuth - soit tokens, soit creation requise"""
    success: bool = Field(default=True)
    # Si utilisateur existe deja
    access_token: Optional[str] = Field(None, description="Token JWT d'acces")
    refresh_token: Optional[str] = Field(None, description="Token JWT de refresh")
    token_type: Optional[str] = Field(None, description="Type de token (bearer)")
    expires_in: Optional[int] = Field(None, description="Duree de validite en secondes")
    # Si nouvel utilisateur (pas encore de compte)
    requires_registration: bool = Field(default=False, description="True si nouveau compte a creer")
    oauth_session_token: Optional[str] = Field(None, description="Token pour completer l'inscription")
    # Infos du profil OAuth
    provider: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class OAuthCompleteRegistrationRequest(BaseSchema):
    """Complete l'inscription d'un nouvel utilisateur OAuth"""
    oauth_session_token: str = Field(..., description="Token de session OAuth")
    first_name: str = Field(..., min_length=2, max_length=100, description="Prenom")
    last_name: str = Field(..., min_length=2, max_length=100, description="Nom")


class OAuthAccountRead(BaseSchema):
    """Lecture d'un compte OAuth lie"""
    id: int
    provider: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None


class OAuthAccountList(BaseSchema):
    """Liste des comptes OAuth d'un utilisateur"""
    accounts: list[OAuthAccountRead] = []


class OAuthUnlinkRequest(BaseSchema):
    """Requete pour delier un compte OAuth"""
    provider: OAuthProvider = Field(..., description="Provider a delier")


class OAuthProviderInfo(BaseSchema):
    """Informations sur un provider OAuth"""
    provider: str
    name: str
    icon: str
    color: str
    enabled: bool = True


class OAuthProvidersResponse(BaseSchema):
    """Liste des providers OAuth disponibles"""
    providers: list[OAuthProviderInfo] = []
