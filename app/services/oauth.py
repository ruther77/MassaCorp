"""
Service OAuth pour l'authentification sociale
Support Google, Facebook, GitHub
"""
import logging
import secrets
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import mask_email
from app.models import User, OAuthAccount
from app.repositories.user import UserRepository
from app.repositories.oauth import OAuthRepository
from app.repositories.tenant import TenantRepository
from app.services.auth import AuthService

logger = logging.getLogger(__name__)
settings = get_settings()


class OAuthError(Exception):
    """Erreur OAuth"""
    def __init__(self, message: str, provider: str = None):
        self.message = message
        self.provider = provider
        super().__init__(message)


class OAuthProviderConfig:
    """Configuration d'un provider OAuth"""
    def __init__(
        self,
        name: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
        userinfo_url: str,
        scopes: list[str],
        icon: str = "",
        color: str = "#000000"
    ):
        self.name = name
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.userinfo_url = userinfo_url
        self.scopes = scopes
        self.icon = icon
        self.color = color

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


# Configuration des providers
OAUTH_PROVIDERS: Dict[str, OAuthProviderConfig] = {
    "google": OAuthProviderConfig(
        name="Google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
        scopes=["openid", "email", "profile"],
        icon="google",
        color="#4285F4"
    ),
    "facebook": OAuthProviderConfig(
        name="Facebook",
        client_id=settings.FACEBOOK_APP_ID,
        client_secret=settings.FACEBOOK_APP_SECRET,
        authorize_url="https://www.facebook.com/v18.0/dialog/oauth",
        token_url="https://graph.facebook.com/v18.0/oauth/access_token",
        userinfo_url="https://graph.facebook.com/me?fields=id,name,email,picture",
        scopes=["email", "public_profile"],
        icon="facebook",
        color="#1877F2"
    ),
    "github": OAuthProviderConfig(
        name="GitHub",
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        scopes=["user:email", "read:user"],
        icon="github",
        color="#24292E"
    ),
}


class OAuthService:
    """Service pour l'authentification OAuth"""

    # Cache Redis pour les states OAuth (anti-CSRF)
    STATE_PREFIX = "oauth_state:"
    STATE_TTL = 600  # 10 minutes

    # Cache pour les sessions OAuth (inscription en cours)
    SESSION_PREFIX = "oauth_session:"
    SESSION_TTL = 1800  # 30 minutes

    def __init__(
        self,
        oauth_repository: OAuthRepository,
        user_repository: UserRepository,
        tenant_repository: TenantRepository,
        auth_service: AuthService,
        redis_client=None
    ):
        self.oauth_repository = oauth_repository
        self.user_repository = user_repository
        self.tenant_repository = tenant_repository
        self.auth_service = auth_service
        self.redis = redis_client

    def get_available_providers(self) -> list[dict]:
        """Retourne la liste des providers OAuth configures"""
        providers = []
        for key, config in OAUTH_PROVIDERS.items():
            if config.is_configured:
                providers.append({
                    "provider": key,
                    "name": config.name,
                    "icon": config.icon,
                    "color": config.color,
                    "enabled": True
                })
        return providers

    def get_provider_config(self, provider: str) -> OAuthProviderConfig:
        """Recupere la configuration d'un provider"""
        if provider not in OAUTH_PROVIDERS:
            raise OAuthError(f"Provider '{provider}' non supporte", provider)

        config = OAUTH_PROVIDERS[provider]
        if not config.is_configured:
            raise OAuthError(f"Provider '{provider}' non configure", provider)

        return config

    def generate_state(self, tenant_id: int, provider: str) -> str:
        """Genere un state unique pour la verification CSRF"""
        state = secrets.token_urlsafe(32)

        # Stocker dans Redis avec les metadonnees
        if self.redis:
            data = {
                "tenant_id": tenant_id,
                "provider": provider,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            self.redis.setex(
                f"{self.STATE_PREFIX}{state}",
                self.STATE_TTL,
                json.dumps(data)
            )

        return state

    def verify_state(self, state: str) -> Optional[dict]:
        """Verifie un state et retourne les metadonnees"""
        if not self.redis:
            return {"tenant_id": 1, "provider": "unknown"}  # Fallback sans Redis

        key = f"{self.STATE_PREFIX}{state}"
        data = self.redis.get(key)

        if not data:
            return None

        # Supprimer le state (usage unique)
        self.redis.delete(key)

        return json.loads(data)

    def get_authorization_url(
        self,
        provider: str,
        tenant_id: int,
        redirect_uri: str
    ) -> Tuple[str, str]:
        """
        Genere l'URL d'autorisation OAuth.

        Returns:
            Tuple (auth_url, state)
        """
        config = self.get_provider_config(provider)
        state = self.generate_state(tenant_id, provider)

        params = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
        }

        # Parametres specifiques par provider
        if provider == "google":
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        auth_url = f"{config.authorize_url}?{urlencode(params)}"
        return auth_url, state

    async def exchange_code_for_token(
        self,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> dict:
        """Echange le code d'autorisation contre un token"""
        config = self.get_provider_config(provider)

        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.token_url,
                data=data,
                headers=headers,
                timeout=10.0
            )

            if response.status_code != 200:
                logger.error(f"OAuth token exchange failed: {response.text}")
                raise OAuthError(f"Echec d'authentification {config.name}", provider)

            return response.json()

    async def get_user_info(self, provider: str, access_token: str) -> dict:
        """Recupere les informations utilisateur du provider"""
        config = self.get_provider_config(provider)

        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                config.userinfo_url,
                headers=headers,
                timeout=10.0
            )

            if response.status_code != 200:
                logger.error(f"OAuth userinfo failed: {response.text}")
                raise OAuthError(f"Impossible de recuperer le profil {config.name}", provider)

            user_data = response.json()

            # GitHub: besoin d'un appel supplementaire pour l'email
            if provider == "github" and not user_data.get("email"):
                email_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers=headers,
                    timeout=10.0
                )
                if email_response.status_code == 200:
                    emails = email_response.json()
                    primary = next((e for e in emails if e.get("primary")), None)
                    if primary:
                        user_data["email"] = primary["email"]

            return self._normalize_user_info(provider, user_data)

    def _normalize_user_info(self, provider: str, data: dict) -> dict:
        """Normalise les donnees utilisateur selon le provider"""
        if provider == "google":
            return {
                "provider_user_id": data.get("id"),
                "email": data.get("email"),
                "name": data.get("name"),
                "first_name": data.get("given_name"),
                "last_name": data.get("family_name"),
                "avatar_url": data.get("picture"),
            }
        elif provider == "facebook":
            picture = data.get("picture", {}).get("data", {}).get("url")
            return {
                "provider_user_id": data.get("id"),
                "email": data.get("email"),
                "name": data.get("name"),
                "first_name": data.get("name", "").split(" ")[0] if data.get("name") else None,
                "last_name": " ".join(data.get("name", "").split(" ")[1:]) if data.get("name") else None,
                "avatar_url": picture,
            }
        elif provider == "github":
            name_parts = (data.get("name") or "").split(" ", 1)
            return {
                "provider_user_id": str(data.get("id")),
                "email": data.get("email"),
                "name": data.get("name") or data.get("login"),
                "first_name": name_parts[0] if name_parts else data.get("login"),
                "last_name": name_parts[1] if len(name_parts) > 1 else None,
                "avatar_url": data.get("avatar_url"),
            }

        return data

    async def authenticate(
        self,
        provider: str,
        code: str,
        state: str,
        redirect_uri: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> dict:
        """
        Authentifie un utilisateur via OAuth.

        Returns:
            Dict avec soit les tokens JWT, soit une session pour completer l'inscription
        """
        # Verifier le state
        state_data = self.verify_state(state)
        if not state_data:
            raise OAuthError("State invalide ou expire", provider)

        tenant_id = state_data["tenant_id"]

        # Echanger le code contre un token
        token_data = await self.exchange_code_for_token(provider, code, redirect_uri)
        access_token = token_data.get("access_token")

        if not access_token:
            raise OAuthError("Token non recu du provider", provider)

        # Recuperer les infos utilisateur
        user_info = await self.get_user_info(provider, access_token)
        provider_user_id = user_info.get("provider_user_id")
        email = user_info.get("email")

        if not provider_user_id:
            raise OAuthError("ID utilisateur non fourni par le provider", provider)

        # Chercher un compte OAuth existant
        oauth_account = self.oauth_repository.get_by_provider_user(
            provider=provider,
            provider_user_id=provider_user_id,
            tenant_id=tenant_id
        )

        if oauth_account and oauth_account.user_id:
            # Compte OAuth lie a un utilisateur existant - login direct
            user = self.user_repository.get_by_id(oauth_account.user_id)
            if not user:
                raise OAuthError("Utilisateur non trouve", provider)

            if not user.is_active:
                raise OAuthError("Compte desactive", provider)

            # Mettre a jour les tokens OAuth
            self.oauth_repository.update(oauth_account.id, {
                "access_token": access_token,
                "refresh_token": token_data.get("refresh_token"),
                "expires_at": self._calculate_expiry(token_data.get("expires_in")),
            })

            # Generer les tokens JWT
            result = self.auth_service.create_session_tokens(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return {
                "success": True,
                "requires_registration": False,
                "access_token": result["access_token"],
                "refresh_token": result["refresh_token"],
                "token_type": "bearer",
                "expires_in": result["expires_in"],
                "provider": provider,
                "email": email,
                "name": user_info.get("name"),
            }

        # Verifier si l'email existe deja (utilisateur avec mot de passe)
        if email:
            existing_user = self.user_repository.get_by_email_and_tenant(email, tenant_id)
            if existing_user:
                # Lier le compte OAuth a l'utilisateur existant
                oauth_account = self.oauth_repository.create({
                    "user_id": existing_user.id,
                    "tenant_id": tenant_id,
                    "provider": provider,
                    "provider_user_id": provider_user_id,
                    "email": email,
                    "name": user_info.get("name"),
                    "avatar_url": user_info.get("avatar_url"),
                    "access_token": access_token,
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_at": self._calculate_expiry(token_data.get("expires_in")),
                })

                # Login direct
                result = self.auth_service.create_session_tokens(
                    user=existing_user,
                    ip_address=ip_address,
                    user_agent=user_agent
                )

                return {
                    "success": True,
                    "requires_registration": False,
                    "access_token": result["access_token"],
                    "refresh_token": result["refresh_token"],
                    "token_type": "bearer",
                    "expires_in": result["expires_in"],
                    "provider": provider,
                    "email": email,
                    "name": user_info.get("name"),
                }

        # Nouvel utilisateur - creer une session temporaire
        session_token = secrets.token_urlsafe(32)
        session_data = {
            "provider": provider,
            "provider_user_id": provider_user_id,
            "tenant_id": tenant_id,
            "email": email,
            "name": user_info.get("name"),
            "first_name": user_info.get("first_name"),
            "last_name": user_info.get("last_name"),
            "avatar_url": user_info.get("avatar_url"),
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
        }

        if self.redis:
            self.redis.setex(
                f"{self.SESSION_PREFIX}{session_token}",
                self.SESSION_TTL,
                json.dumps(session_data)
            )

        return {
            "success": True,
            "requires_registration": True,
            "oauth_session_token": session_token,
            "provider": provider,
            "email": email,
            "name": user_info.get("name"),
            "avatar_url": user_info.get("avatar_url"),
        }

    def complete_registration(
        self,
        oauth_session_token: str,
        first_name: str,
        last_name: str,
        ip_address: str = None,
        user_agent: str = None
    ) -> dict:
        """Complete l'inscription d'un nouvel utilisateur OAuth"""
        if not self.redis:
            raise OAuthError("Service temporairement indisponible")

        # Recuperer les donnees de session
        key = f"{self.SESSION_PREFIX}{oauth_session_token}"
        data = self.redis.get(key)

        if not data:
            raise OAuthError("Session OAuth expiree ou invalide")

        session_data = json.loads(data)

        # Supprimer la session (usage unique)
        self.redis.delete(key)

        tenant_id = session_data["tenant_id"]
        email = session_data.get("email")
        provider = session_data["provider"]
        provider_user_id = session_data["provider_user_id"]

        # Verifier que l'email n'existe pas deja
        if email:
            existing = self.user_repository.get_by_email_and_tenant(email, tenant_id)
            if existing:
                raise OAuthError("Cet email est deja utilise")

        # Creer l'utilisateur
        from app.core.security import hash_password

        user = self.user_repository.create({
            "email": email or f"{provider}_{provider_user_id}@oauth.local",
            "password_hash": None,  # Pas de mot de passe pour OAuth
            "tenant_id": tenant_id,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
            "is_verified": True,  # Email verifie par le provider
        })

        # Creer le compte OAuth
        self.oauth_repository.create({
            "user_id": user.id,
            "tenant_id": tenant_id,
            "provider": provider,
            "provider_user_id": provider_user_id,
            "email": email,
            "name": session_data.get("name"),
            "avatar_url": session_data.get("avatar_url"),
            "access_token": session_data.get("access_token"),
            "refresh_token": session_data.get("refresh_token"),
            "expires_at": self._calculate_expiry(session_data.get("expires_in")),
        })

        # Generer les tokens JWT
        result = self.auth_service.create_session_tokens(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(f"Nouvel utilisateur OAuth cree: {mask_email(user.email)} via {provider}")

        return {
            "success": True,
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": "bearer",
            "expires_in": result["expires_in"],
        }

    def _calculate_expiry(self, expires_in: int = None) -> Optional[datetime]:
        """Calcule la date d'expiration du token"""
        if expires_in:
            return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return None

    def get_user_oauth_accounts(self, user_id: int) -> list[OAuthAccount]:
        """Recupere les comptes OAuth lies a un utilisateur"""
        return self.oauth_repository.get_by_user(user_id)

    def unlink_account(self, user_id: int, provider: str) -> bool:
        """Delie un compte OAuth d'un utilisateur"""
        account = self.oauth_repository.get_by_user_and_provider(user_id, provider)
        if not account:
            raise OAuthError(f"Compte {provider} non trouve", provider)

        # Verifier que l'utilisateur a un autre moyen de connexion
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise OAuthError("Utilisateur non trouve")

        other_accounts = self.oauth_repository.get_by_user(user_id)
        has_password = user.password_hash is not None
        has_other_oauth = len([a for a in other_accounts if a.provider != provider]) > 0

        if not has_password and not has_other_oauth:
            raise OAuthError(
                "Impossible de delier le dernier moyen de connexion. "
                "Ajoutez un mot de passe ou liez un autre compte OAuth d'abord."
            )

        return self.oauth_repository.delete(account.id)
