"""
Configuration de l'application MassaCorp
Charge les variables d'environnement et definit les parametres
"""

import os
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration principale de l'application"""

    # General
    ENV: str = "dev"
    DEBUG: bool = False  # JAMAIS True en production
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "MassaCorp API"
    APP_VERSION: str = "0.1.0"

    # Base de donnees
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/massacorp"

    # Securite JWT
    JWT_SECRET: str = "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_LIFETIME: int = 900  # 15 minutes
    REFRESH_TOKEN_LIFETIME: int = 604800  # 7 jours

    # Chiffrement
    ENCRYPTION_KEY: str = "CHANGER_CLE_CHIFFREMENT_32_OCTETS"

    # WireGuard
    WG_SERVER_PUBLIC_KEY: str = ""
    WG_NETWORK: str = "10.10.0.0/24"

    # Redis
    REDIS_URL: str = "redis://:password@localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10  # Max connections in pool
    REDIS_HEALTH_CHECK_INTERVAL: int = 30  # Seconds between health checks
    REDIS_SOCKET_TIMEOUT: int = 5  # Socket timeout in seconds
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5  # Connection timeout in seconds

    # Database Pool Configuration
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800  # 30 minutes

    # Password Security
    PASSWORD_CHECK_HIBP: bool = True  # Check passwords against HaveIBeenPwned

    # HTTP Client Timeouts
    HTTP_TIMEOUT: int = 30  # seconds
    HTTP_CONNECT_TIMEOUT: int = 10  # seconds
    EXTERNAL_API_TIMEOUT: int = 60  # seconds

    # Security
    FORCE_HTTPS: bool = True
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver"

    # CORS
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    CORS_ALLOW_ALL: bool = False
    CORS_ALLOW_CREDENTIALS: bool = True

    # CAPTCHA (reCAPTCHA v3 ou hCaptcha)
    CAPTCHA_ENABLED: bool = False  # Activer en production
    CAPTCHA_PROVIDER: str = "recaptcha"  # "recaptcha" ou "hcaptcha"
    CAPTCHA_SITE_KEY: str = ""  # Cle publique (frontend)
    CAPTCHA_SECRET_KEY: str = ""  # Cle secrete (backend)
    CAPTCHA_SCORE_THRESHOLD: float = 0.5  # Score min pour reCAPTCHA v3 (0.0-1.0)
    CAPTCHA_TIMEOUT: int = 5  # Timeout validation en secondes

    # RBAC
    RBAC_ENABLED: bool = True  # Activer le controle d'acces par roles
    RBAC_SUPERUSER_BYPASS: bool = True  # Superusers bypass les permissions

    # Verification email
    EMAIL_VERIFICATION_REQUIRED: bool = False  # A activer en production

    # SMTP Configuration
    SMTP_ENABLED: bool = False  # Activer les emails
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_FROM_EMAIL: str = "noreply@massacorp.com"
    SMTP_FROM_NAME: str = "MassaCorp Security"
    SMTP_TIMEOUT: int = 10  # seconds

    # Alert Configuration
    ALERT_WEBHOOK_URL: str = ""  # Slack/Discord webhook
    ALERT_EMAIL_ENABLED: bool = False  # Send alerts by email
    ALERT_EMAIL_RECIPIENTS: str = ""  # Comma-separated admin emails

    # OAuth Configuration
    OAUTH_ENABLED: bool = True  # Enable OAuth authentication
    OAUTH_FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for callbacks

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Facebook OAuth
    FACEBOOK_APP_ID: str = ""
    FACEBOOK_APP_SECRET: str = ""

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Alias for compatibility
    @property
    def ENVIRONMENT(self) -> str:
        return self.ENV

    # Valeurs par defaut dangereuses (a ne JAMAIS utiliser en production)
    _DANGEROUS_DEFAULTS = [
        "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES",
        "CHANGER_CLE_CHIFFREMENT_32_OCTETS",
        "CHANGER_SECRET_JWT_MIN_32_CARACTERES",
        "postgresql+psycopg2://user:password@localhost:5432/massacorp",
        "redis://:password@localhost:6379/0",
        "changeme",
        "password",
        "secret",
    ]

    # Secrets supportes via *_FILE (Docker/K8s secrets)
    _FILE_SECRET_FIELDS = [
        "DATABASE_URL",
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "REDIS_URL",
        "SMTP_PASSWORD",
        "CAPTCHA_SECRET_KEY",
        "GOOGLE_CLIENT_SECRET",
        "GITHUB_CLIENT_SECRET",
        "FACEBOOK_APP_SECRET",
    ]

    def __init__(self, **values):
        super().__init__(**values)
        self._apply_file_overrides()

    def _apply_file_overrides(self) -> None:
        """
        Charge les secrets depuis les variables *_FILE si elles sont definies.
        """
        for field_name in self._FILE_SECRET_FIELDS:
            env_key = f"{field_name}_FILE"
            file_path = os.getenv(env_key)
            if not file_path:
                continue
            secret_value = self._read_secret_file(file_path=file_path, env_key=env_key)
            if secret_value:
                setattr(self, field_name, secret_value)

    @staticmethod
    def _read_secret_file(file_path: str, env_key: str) -> str:
        """
        Lit un secret depuis un fichier pointe par une variable *_FILE.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError as exc:
            raise ValueError(
                f"SECURITE CRITIQUE: impossible de lire {env_key}={file_path}: {exc}"
            ) from exc

    def get_allowed_hosts(self) -> List[str]:
        """
        Retourne la liste des hosts autorises pour TrustedHostMiddleware.
        """
        hosts = [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]
        if not hosts:
            return ["localhost"]
        return hosts

    def get_cors_origins(self) -> List[str]:
        """
        Retourne la liste des origines CORS autorisees.
        """
        if self.CORS_ALLOW_ALL:
            return ["*"]
        origins = [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]
        return origins

    def validate_secrets(self) -> None:
        """
        Valide que les secrets ne sont pas les valeurs par defaut.

        DOIT etre appele au demarrage en mode production.

        Raises:
            ValueError: Si un secret utilise une valeur par defaut en production
        """
        env_lower = self.ENV.lower()

        # En mode dev/test, on autorise les valeurs par defaut
        if env_lower in ("dev", "test", "development"):
            return

        # En production, verifier les secrets
        if self.JWT_SECRET in self._DANGEROUS_DEFAULTS:
            raise ValueError(
                "SECURITE CRITIQUE: JWT_SECRET utilise une valeur par defaut! "
                "Definissez une cle secrete unique via la variable d'environnement JWT_SECRET."
            )

        if self.ENCRYPTION_KEY in self._DANGEROUS_DEFAULTS:
            raise ValueError(
                "SECURITE CRITIQUE: ENCRYPTION_KEY utilise une valeur par defaut! "
                "Definissez une cle de chiffrement unique via la variable d'environnement ENCRYPTION_KEY."
            )

        # Verifier la longueur minimale des secrets
        if len(self.JWT_SECRET) < 32:
            raise ValueError(
                "SECURITE: JWT_SECRET doit faire au moins 32 caracteres."
            )

        if len(self.ENCRYPTION_KEY) < 32:
            raise ValueError(
                "SECURITE: ENCRYPTION_KEY doit faire au moins 32 caracteres."
            )

    def validate_production_config(self) -> list[str]:
        """
        Valide la configuration pour l'environnement de production.

        Retourne une liste de warnings (non-bloquants) et leve des exceptions
        pour les problemes critiques.

        Returns:
            Liste de warnings a logger

        Raises:
            ValueError: Pour les problemes critiques
        """
        warnings = []

        # Verifier les secrets d'abord
        self.validate_secrets()

        env_lower = self.ENV.lower()

        # En mode dev/test, pas de verification supplementaire
        if env_lower in ("dev", "test", "development"):
            return warnings

        # DEBUG doit etre False en production
        if self.DEBUG:
            raise ValueError(
                "SECURITE CRITIQUE: DEBUG=True en production! "
                "Definissez DEBUG=False."
            )

        # LOG_LEVEL ne doit pas etre DEBUG en production
        if self.LOG_LEVEL.upper() == "DEBUG":
            warnings.append(
                "SECURITE: LOG_LEVEL=DEBUG en production peut exposer des infos sensibles. "
                "Utilisez INFO ou WARNING."
            )

        # ALLOWED_HOSTS ne doit pas etre * en production
        if self.ALLOWED_HOSTS.strip() == "*":
            raise ValueError(
                "SECURITE CRITIQUE: ALLOWED_HOSTS='*' en production. "
                "Definissez les hosts autorises explicitement."
            )

        # CORS ne doit pas autoriser toutes les origines en production
        if self.CORS_ALLOW_ALL or "*" in self.get_cors_origins():
            raise ValueError(
                "SECURITE CRITIQUE: CORS_ALLOW_ALL interdit en production. "
                "Definissez CORS_ALLOWED_ORIGINS explicitement."
            )

        # Credentials + CORS exige des origines explicites
        if self.CORS_ALLOW_CREDENTIALS and not self.get_cors_origins():
            warnings.append(
                "SECURITE: CORS_ALLOW_CREDENTIALS=True sans origines explicites."
            )

        # CAPTCHA doit etre active en production
        if not self.CAPTCHA_ENABLED:
            raise ValueError(
                "SECURITE CRITIQUE: CAPTCHA desactive en production. "
                "Activez CAPTCHA_ENABLED=True pour la protection anti-bot."
            )

        if self.CAPTCHA_ENABLED and (not self.CAPTCHA_SITE_KEY or not self.CAPTCHA_SECRET_KEY):
            raise ValueError(
                "SECURITE CRITIQUE: CAPTCHA active sans cle publique ou cle secrete."
            )

        # SMTP securise si active
        if self.SMTP_ENABLED:
            if not self.SMTP_USE_TLS and not self.SMTP_USE_SSL:
                raise ValueError(
                    "SECURITE CRITIQUE: SMTP sans TLS/SSL en production."
                )
            if not self.SMTP_USER or not self.SMTP_PASSWORD:
                raise ValueError(
                    "SECURITE CRITIQUE: SMTP active sans authentification."
                )

        # OAuth: chaque provider doit avoir ID + secret
        if self.OAUTH_ENABLED:
            providers = {
                "google": (self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET),
                "github": (self.GITHUB_CLIENT_ID, self.GITHUB_CLIENT_SECRET),
                "facebook": (self.FACEBOOK_APP_ID, self.FACEBOOK_APP_SECRET),
            }
            any_configured = False
            for provider, (client_id, client_secret) in providers.items():
                if client_id or client_secret:
                    if not client_id or not client_secret:
                        raise ValueError(
                            f"SECURITE CRITIQUE: OAuth {provider} incomplet (id/secret)."
                        )
                    any_configured = True
            if not any_configured:
                warnings.append(
                    "SECURITE: OAUTH_ENABLED=True sans provider configure."
                )

        # Verification email recommande en production
        if not self.EMAIL_VERIFICATION_REQUIRED:
            warnings.append(
                "SECURITE: verification email desactivee en production."
            )

        # Verifier que les URLs sensibles ne sont pas des placeholders
        if not self.DATABASE_URL or self.DATABASE_URL in self._DANGEROUS_DEFAULTS:
            raise ValueError(
                "SECURITE CRITIQUE: DATABASE_URL non configure ou valeur par defaut."
            )

        weak_markers = ("password", "changeme", "default")
        if any(marker in self.DATABASE_URL.lower() for marker in weak_markers):
            raise ValueError(
                "SECURITE CRITIQUE: DATABASE_URL contient un mot de passe faible."
            )

        if not self.REDIS_URL or self.REDIS_URL in self._DANGEROUS_DEFAULTS:
            warnings.append(
                "SECURITE: REDIS_URL non configure ou valeur par defaut. "
                "Le rate limiting sera degrade en memoire."
            )
        elif any(marker in self.REDIS_URL.lower() for marker in weak_markers):
            warnings.append(
                "SECURITE: REDIS_URL contient un mot de passe faible."
            )

        return warnings

    @property
    def is_production(self) -> bool:
        """Retourne True si en mode production."""
        return self.ENV.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        """Retourne True si en mode developpement."""
        return self.ENV.lower() in ("dev", "development")

    @property
    def is_testing(self) -> bool:
        """Retourne True si en mode test."""
        return self.ENV.lower() == "test"

    @property
    def is_strict_env(self) -> bool:
        """Retourne True si l'environnement impose des controles stricts."""
        return self.ENV.lower() not in ("dev", "development", "test")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorer les variables d'env supplementaires


@lru_cache()
def get_settings() -> Settings:
    """Retourne les settings (cache pour performance)"""
    env = os.getenv("ENV", "dev").lower()
    env_file = ".env" if env in ("dev", "development", "test") else None
    return Settings(_env_file=env_file)
