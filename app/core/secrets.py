"""
Gestionnaire de secrets centralise pour MassaCorp.

Ce module fournit une abstraction pour la recuperation des secrets,
permettant de basculer facilement entre differentes sources:
- Variables d'environnement (dev)
- Fichiers Docker secrets (*_FILE)
- HashiCorp Vault (production)
- Infisical (production)
- AWS Secrets Manager (production)

Usage:
    from app.core.secrets import get_secret, SecretManager

    # Recuperer un secret
    jwt_secret = get_secret("JWT_SECRET")

    # Ou via le manager
    manager = SecretManager()
    db_url = manager.get("DATABASE_URL")
"""

import os
import logging
from functools import lru_cache
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class SecretBackend(str, Enum):
    """Backends supportes pour la gestion des secrets."""
    ENV = "env"  # Variables d'environnement
    FILE = "file"  # Fichiers Docker secrets
    VAULT = "vault"  # HashiCorp Vault
    INFISICAL = "infisical"  # Infisical
    AWS = "aws"  # AWS Secrets Manager


class SecretManager:
    """
    Gestionnaire centralise des secrets.

    En mode dev: utilise les variables d'environnement et fichiers.
    En mode prod: peut utiliser Vault, Infisical ou AWS Secrets Manager.
    """

    # Liste des secrets sensibles
    SENSITIVE_SECRETS = [
        "JWT_SECRET",
        "ENCRYPTION_KEY",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "REDIS_URL",
        "SMTP_PASSWORD",
        "GOOGLE_CLIENT_SECRET",
        "GITHUB_CLIENT_SECRET",
        "FACEBOOK_APP_SECRET",
        "CAPTCHA_SECRET_KEY",
        "WG_SERVER_PRIVATE_KEY",
    ]

    def __init__(self, backend: Optional[SecretBackend] = None):
        """
        Initialise le gestionnaire de secrets.

        Args:
            backend: Backend a utiliser. Si None, detecte automatiquement.
        """
        self.backend = backend or self._detect_backend()
        self._cache: Dict[str, str] = {}
        self._vault_client = None
        self._infisical_client = None

    def _detect_backend(self) -> SecretBackend:
        """Detecte automatiquement le backend a utiliser."""
        # Vault
        if os.getenv("VAULT_ADDR") and os.getenv("VAULT_TOKEN"):
            return SecretBackend.VAULT

        # Infisical
        if os.getenv("INFISICAL_CLIENT_ID") and os.getenv("INFISICAL_CLIENT_SECRET"):
            return SecretBackend.INFISICAL

        # AWS Secrets Manager
        if os.getenv("AWS_SECRET_NAME"):
            return SecretBackend.AWS

        # Defaut: env + fichiers
        return SecretBackend.ENV

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Recupere un secret.

        Args:
            key: Nom du secret
            default: Valeur par defaut si non trouve

        Returns:
            Valeur du secret ou default
        """
        # Cache
        if key in self._cache:
            return self._cache[key]

        value = None

        if self.backend == SecretBackend.VAULT:
            value = self._get_from_vault(key)
        elif self.backend == SecretBackend.INFISICAL:
            value = self._get_from_infisical(key)
        elif self.backend == SecretBackend.AWS:
            value = self._get_from_aws(key)
        else:
            # ENV + FILE fallback
            value = self._get_from_env_or_file(key)

        if value is None:
            return default

        # Cache le resultat
        self._cache[key] = value
        return value

    def _get_from_env_or_file(self, key: str) -> Optional[str]:
        """Recupere depuis env ou fichier *_FILE."""
        # D'abord verifier si un fichier est specifie
        file_path = os.getenv(f"{key}_FILE")
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    value = f.read().strip()
                    # Gerer le format KEY=VALUE
                    if value.startswith(f"{key}="):
                        value = value[len(f"{key}="):]
                    return value
            except OSError as e:
                logger.error(f"Erreur lecture {key}_FILE={file_path}: {e}")

        # Sinon variable d'environnement
        return os.getenv(key)

    def _get_from_vault(self, key: str) -> Optional[str]:
        """Recupere depuis HashiCorp Vault."""
        try:
            if self._vault_client is None:
                import hvac
                self._vault_client = hvac.Client(
                    url=os.getenv("VAULT_ADDR", "http://vault:8200"),
                    token=os.getenv("VAULT_TOKEN")
                )

            # Chemin par defaut: secret/data/massacorp/{key}
            path = os.getenv("VAULT_SECRET_PATH", "massacorp")
            secret = self._vault_client.secrets.kv.v2.read_secret_version(
                path=path,
                raise_on_deleted_version=True
            )
            return secret["data"]["data"].get(key)

        except ImportError:
            logger.warning("hvac non installe. pip install hvac")
            return self._get_from_env_or_file(key)
        except Exception as e:
            logger.error(f"Erreur Vault pour {key}: {e}")
            return self._get_from_env_or_file(key)

    def _get_from_infisical(self, key: str) -> Optional[str]:
        """Recupere depuis Infisical."""
        try:
            if self._infisical_client is None:
                from infisical_client import ClientSettings, InfisicalClient
                self._infisical_client = InfisicalClient(ClientSettings(
                    client_id=os.getenv("INFISICAL_CLIENT_ID"),
                    client_secret=os.getenv("INFISICAL_CLIENT_SECRET"),
                ))

            env = os.getenv("ENV", "dev")
            project_id = os.getenv("INFISICAL_PROJECT_ID")

            secret = self._infisical_client.getSecret(options={
                "secretName": key,
                "environment": env,
                "projectId": project_id
            })
            return secret.secret_value

        except ImportError:
            logger.warning("infisical-python non installe. pip install infisical-python")
            return self._get_from_env_or_file(key)
        except Exception as e:
            logger.error(f"Erreur Infisical pour {key}: {e}")
            return self._get_from_env_or_file(key)

    def _get_from_aws(self, key: str) -> Optional[str]:
        """Recupere depuis AWS Secrets Manager."""
        try:
            import boto3
            import json

            client = boto3.client(
                "secretsmanager",
                region_name=os.getenv("AWS_REGION", "eu-west-1")
            )

            secret_name = os.getenv("AWS_SECRET_NAME", "massacorp/secrets")
            response = client.get_secret_value(SecretId=secret_name)
            secrets = json.loads(response["SecretString"])
            return secrets.get(key)

        except ImportError:
            logger.warning("boto3 non installe. pip install boto3")
            return self._get_from_env_or_file(key)
        except Exception as e:
            logger.error(f"Erreur AWS pour {key}: {e}")
            return self._get_from_env_or_file(key)

    def clear_cache(self) -> None:
        """Vide le cache des secrets."""
        self._cache.clear()

    def is_sensitive(self, key: str) -> bool:
        """Verifie si un secret est sensible."""
        return key in self.SENSITIVE_SECRETS


@lru_cache()
def get_secret_manager() -> SecretManager:
    """Retourne une instance singleton du gestionnaire de secrets."""
    return SecretManager()


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Raccourci pour recuperer un secret.

    Args:
        key: Nom du secret
        default: Valeur par defaut

    Returns:
        Valeur du secret
    """
    return get_secret_manager().get(key, default)


# ============================================
# Rotation automatique des secrets
# ============================================

class SecretRotationPolicy:
    """Politique de rotation des secrets."""

    # Duree de vie recommandee par type de secret (en jours)
    ROTATION_PERIODS = {
        "JWT_SECRET": 90,
        "ENCRYPTION_KEY": 180,
        "DATABASE_URL": 30,
        "POSTGRES_PASSWORD": 30,
        "REDIS_PASSWORD": 30,
        "SMTP_PASSWORD": 90,
        "GOOGLE_CLIENT_SECRET": 365,  # Sur compromission
        "GITHUB_CLIENT_SECRET": 365,  # Sur compromission
        "FACEBOOK_APP_SECRET": 365,  # Sur compromission
        "CAPTCHA_SECRET_KEY": 180,
        "WG_SERVER_PRIVATE_KEY": 365,
    }

    @classmethod
    def get_rotation_period(cls, secret_name: str) -> int:
        """Retourne la periode de rotation recommandee en jours."""
        return cls.ROTATION_PERIODS.get(secret_name, 90)

    @classmethod
    def should_rotate(cls, secret_name: str, last_rotation_days: int) -> bool:
        """Verifie si un secret doit etre pivote."""
        period = cls.get_rotation_period(secret_name)
        return last_rotation_days >= period


class SecretRotator:
    """
    Gestionnaire de rotation des secrets.

    Supporte la rotation pour:
    - JWT_SECRET: Genere un nouveau token aleatoire
    - ENCRYPTION_KEY: Genere une nouvelle cle de chiffrement
    - POSTGRES_PASSWORD: Change le mot de passe PostgreSQL
    - REDIS_PASSWORD: Change le mot de passe Redis
    """

    def __init__(self):
        self.manager = get_secret_manager()

    @staticmethod
    def generate_secret(length: int = 48) -> str:
        """Genere un secret aleatoire cryptographiquement sur."""
        import secrets as crypto_secrets
        return crypto_secrets.token_urlsafe(length)

    @staticmethod
    def generate_password(length: int = 32) -> str:
        """Genere un mot de passe aleatoire."""
        import secrets as crypto_secrets
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(crypto_secrets.choice(alphabet) for _ in range(length))

    def rotate_jwt_secret(self) -> str:
        """
        Genere un nouveau JWT_SECRET.

        ATTENTION: Invalide tous les tokens JWT existants!

        Returns:
            Nouveau secret
        """
        new_secret = self.generate_secret(48)
        logger.info("JWT_SECRET rotation effectuee")
        return new_secret

    def rotate_encryption_key(self) -> str:
        """
        Genere une nouvelle ENCRYPTION_KEY.

        ATTENTION: Les donnees chiffrees avec l'ancienne cle
        doivent etre re-chiffrees!

        Returns:
            Nouvelle cle
        """
        new_key = self.generate_secret(32)
        logger.info("ENCRYPTION_KEY rotation effectuee")
        return new_key

    def rotate_database_password(self) -> str:
        """
        Genere un nouveau mot de passe PostgreSQL.

        ATTENTION: Necessite une mise a jour de la base de donnees!

        Returns:
            Nouveau mot de passe
        """
        new_password = self.generate_password(32)
        logger.info("POSTGRES_PASSWORD rotation effectuee")
        return new_password

    def rotate_redis_password(self) -> str:
        """
        Genere un nouveau mot de passe Redis.

        ATTENTION: Necessite un redemarrage de Redis!

        Returns:
            Nouveau mot de passe
        """
        new_password = self.generate_password(32)
        logger.info("REDIS_PASSWORD rotation effectuee")
        return new_password

    def rotate_all(self, force: bool = False) -> Dict[str, str]:
        """
        Effectue la rotation de tous les secrets eligibles.

        Args:
            force: Forcer la rotation meme si pas encore necessaire

        Returns:
            Dictionnaire des nouveaux secrets
        """
        rotated = {}

        # JWT_SECRET
        if force or SecretRotationPolicy.should_rotate("JWT_SECRET", 90):
            rotated["JWT_SECRET"] = self.rotate_jwt_secret()

        # ENCRYPTION_KEY
        if force or SecretRotationPolicy.should_rotate("ENCRYPTION_KEY", 180):
            rotated["ENCRYPTION_KEY"] = self.rotate_encryption_key()

        # POSTGRES_PASSWORD
        if force or SecretRotationPolicy.should_rotate("POSTGRES_PASSWORD", 30):
            rotated["POSTGRES_PASSWORD"] = self.rotate_database_password()

        # REDIS_PASSWORD
        if force or SecretRotationPolicy.should_rotate("REDIS_PASSWORD", 30):
            rotated["REDIS_PASSWORD"] = self.rotate_redis_password()

        return rotated


def get_secret_rotator() -> SecretRotator:
    """Retourne une instance du rotateur de secrets."""
    return SecretRotator()
