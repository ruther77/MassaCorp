"""
Tests pour le module de gestion et rotation des secrets.

Couvre:
- SecretManager: recuperation des secrets depuis differentes sources
- SecretRotationPolicy: politique de rotation
- SecretRotator: generation de nouveaux secrets
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestSecretManager:
    """Tests pour SecretManager"""

    @pytest.mark.unit
    def test_secret_manager_detects_env_backend(self):
        """SecretManager detecte le backend ENV par defaut"""
        from app.core.secrets import SecretManager, SecretBackend

        with patch.dict(os.environ, {}, clear=True):
            manager = SecretManager()
            assert manager.backend == SecretBackend.ENV

    @pytest.mark.unit
    def test_secret_manager_detects_vault_backend(self):
        """SecretManager detecte Vault quand configure"""
        from app.core.secrets import SecretManager, SecretBackend

        with patch.dict(os.environ, {
            "VAULT_ADDR": "http://vault:8200",
            "VAULT_TOKEN": "test-token"
        }):
            manager = SecretManager()
            assert manager.backend == SecretBackend.VAULT

    @pytest.mark.unit
    def test_secret_manager_detects_infisical_backend(self):
        """SecretManager detecte Infisical quand configure"""
        from app.core.secrets import SecretManager, SecretBackend

        with patch.dict(os.environ, {
            "INFISICAL_CLIENT_ID": "client-id",
            "INFISICAL_CLIENT_SECRET": "client-secret"
        }):
            manager = SecretManager()
            assert manager.backend == SecretBackend.INFISICAL

    @pytest.mark.unit
    def test_secret_manager_detects_aws_backend(self):
        """SecretManager detecte AWS quand configure"""
        from app.core.secrets import SecretManager, SecretBackend

        with patch.dict(os.environ, {
            "AWS_SECRET_NAME": "massacorp/secrets"
        }):
            manager = SecretManager()
            assert manager.backend == SecretBackend.AWS

    @pytest.mark.unit
    def test_get_from_env(self):
        """SecretManager recupere depuis les variables d'environnement"""
        from app.core.secrets import SecretManager

        with patch.dict(os.environ, {"TEST_SECRET": "test-value"}):
            manager = SecretManager()
            value = manager.get("TEST_SECRET")
            assert value == "test-value"

    @pytest.mark.unit
    def test_get_returns_default_if_not_found(self):
        """SecretManager retourne default si secret non trouve"""
        from app.core.secrets import SecretManager

        with patch.dict(os.environ, {}, clear=True):
            manager = SecretManager()
            value = manager.get("NONEXISTENT_SECRET", default="default-value")
            assert value == "default-value"

    @pytest.mark.unit
    def test_cache_stores_retrieved_secrets(self):
        """SecretManager cache les secrets recuperes"""
        from app.core.secrets import SecretManager

        with patch.dict(os.environ, {"CACHED_SECRET": "cached-value"}):
            manager = SecretManager()

            # Premiere recuperation
            value1 = manager.get("CACHED_SECRET")

            # Supprimer de l'environnement
            with patch.dict(os.environ, {}, clear=True):
                # Doit toujours retourner la valeur cachee
                value2 = manager.get("CACHED_SECRET")

            assert value1 == value2 == "cached-value"

    @pytest.mark.unit
    def test_clear_cache(self):
        """SecretManager.clear_cache() vide le cache"""
        from app.core.secrets import SecretManager

        with patch.dict(os.environ, {"TEST": "value"}):
            manager = SecretManager()
            manager.get("TEST")
            assert "TEST" in manager._cache

            manager.clear_cache()
            assert "TEST" not in manager._cache

    @pytest.mark.unit
    def test_is_sensitive(self):
        """SecretManager.is_sensitive() identifie les secrets sensibles"""
        from app.core.secrets import SecretManager

        manager = SecretManager()

        assert manager.is_sensitive("JWT_SECRET") is True
        assert manager.is_sensitive("ENCRYPTION_KEY") is True
        assert manager.is_sensitive("DATABASE_URL") is True
        assert manager.is_sensitive("RANDOM_VAR") is False


class TestSecretRotationPolicy:
    """Tests pour SecretRotationPolicy"""

    @pytest.mark.unit
    def test_get_rotation_period_known_secrets(self):
        """SecretRotationPolicy retourne les bonnes periodes"""
        from app.core.secrets import SecretRotationPolicy

        assert SecretRotationPolicy.get_rotation_period("JWT_SECRET") == 90
        assert SecretRotationPolicy.get_rotation_period("ENCRYPTION_KEY") == 180
        assert SecretRotationPolicy.get_rotation_period("POSTGRES_PASSWORD") == 30
        assert SecretRotationPolicy.get_rotation_period("REDIS_PASSWORD") == 30

    @pytest.mark.unit
    def test_get_rotation_period_unknown_secret(self):
        """SecretRotationPolicy retourne 90 jours par defaut"""
        from app.core.secrets import SecretRotationPolicy

        assert SecretRotationPolicy.get_rotation_period("UNKNOWN_SECRET") == 90

    @pytest.mark.unit
    def test_should_rotate_expired(self):
        """should_rotate retourne True si periode depassee"""
        from app.core.secrets import SecretRotationPolicy

        # JWT_SECRET a une periode de 90 jours
        assert SecretRotationPolicy.should_rotate("JWT_SECRET", 90) is True
        assert SecretRotationPolicy.should_rotate("JWT_SECRET", 100) is True

    @pytest.mark.unit
    def test_should_rotate_not_expired(self):
        """should_rotate retourne False si periode non depassee"""
        from app.core.secrets import SecretRotationPolicy

        assert SecretRotationPolicy.should_rotate("JWT_SECRET", 30) is False
        assert SecretRotationPolicy.should_rotate("JWT_SECRET", 89) is False


class TestSecretRotator:
    """Tests pour SecretRotator"""

    @pytest.mark.unit
    def test_generate_secret_length(self):
        """generate_secret genere un secret de la bonne longueur"""
        from app.core.secrets import SecretRotator

        secret = SecretRotator.generate_secret(32)
        # Base64 URL-safe: 32 bytes = ~43 caracteres
        assert len(secret) >= 40

    @pytest.mark.unit
    def test_generate_secret_unique(self):
        """generate_secret genere des secrets uniques"""
        from app.core.secrets import SecretRotator

        secrets = [SecretRotator.generate_secret() for _ in range(100)]
        assert len(set(secrets)) == 100

    @pytest.mark.unit
    def test_generate_password_length(self):
        """generate_password genere un mot de passe de la bonne longueur"""
        from app.core.secrets import SecretRotator

        password = SecretRotator.generate_password(32)
        assert len(password) == 32

    @pytest.mark.unit
    def test_generate_password_contains_special_chars(self):
        """generate_password contient des caracteres speciaux"""
        from app.core.secrets import SecretRotator

        # Generer plusieurs mots de passe et verifier les caracteres
        passwords = [SecretRotator.generate_password(32) for _ in range(10)]

        special_chars = "!@#$%^&*"
        has_special = any(
            any(c in special_chars for c in pwd)
            for pwd in passwords
        )

        assert has_special is True

    @pytest.mark.unit
    def test_rotate_jwt_secret(self):
        """rotate_jwt_secret genere un nouveau secret"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        new_secret = rotator.rotate_jwt_secret()

        assert new_secret is not None
        assert len(new_secret) >= 40

    @pytest.mark.unit
    def test_rotate_encryption_key(self):
        """rotate_encryption_key genere une nouvelle cle"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        new_key = rotator.rotate_encryption_key()

        assert new_key is not None
        assert len(new_key) >= 32

    @pytest.mark.unit
    def test_rotate_database_password(self):
        """rotate_database_password genere un nouveau mot de passe"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        new_password = rotator.rotate_database_password()

        assert new_password is not None
        assert len(new_password) == 32

    @pytest.mark.unit
    def test_rotate_redis_password(self):
        """rotate_redis_password genere un nouveau mot de passe"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        new_password = rotator.rotate_redis_password()

        assert new_password is not None
        assert len(new_password) == 32

    @pytest.mark.unit
    def test_rotate_all_with_force(self):
        """rotate_all avec force=True pivote tous les secrets"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        rotated = rotator.rotate_all(force=True)

        assert "JWT_SECRET" in rotated
        assert "ENCRYPTION_KEY" in rotated
        assert "POSTGRES_PASSWORD" in rotated
        assert "REDIS_PASSWORD" in rotated

    @pytest.mark.unit
    def test_rotated_secrets_are_unique(self):
        """Les secrets generes sont tous differents"""
        from app.core.secrets import SecretRotator

        rotator = SecretRotator()
        rotated = rotator.rotate_all(force=True)

        values = list(rotated.values())
        assert len(values) == len(set(values))


class TestGetSecretFunction:
    """Tests pour la fonction get_secret()"""

    @pytest.mark.unit
    def test_get_secret_shortcut(self):
        """get_secret() est un raccourci vers SecretManager.get()"""
        from app.core.secrets import get_secret

        with patch.dict(os.environ, {"SHORTCUT_TEST": "shortcut-value"}):
            # Vider le cache du singleton
            from app.core.secrets import get_secret_manager
            get_secret_manager.cache_clear()

            value = get_secret("SHORTCUT_TEST")
            assert value == "shortcut-value"

    @pytest.mark.unit
    def test_get_secret_with_default(self):
        """get_secret() accepte une valeur par defaut"""
        from app.core.secrets import get_secret

        # Vider le cache
        from app.core.secrets import get_secret_manager
        get_secret_manager.cache_clear()

        value = get_secret("NONEXISTENT", default="my-default")
        assert value == "my-default"


class TestSecretRotatorIntegration:
    """Tests d'integration pour la rotation des secrets"""

    @pytest.mark.unit
    def test_rotated_jwt_secret_is_valid_for_tokens(self):
        """Un JWT_SECRET genere peut etre utilise pour signer des tokens"""
        from app.core.secrets import SecretRotator
        from jose import jwt

        rotator = SecretRotator()
        new_secret = rotator.rotate_jwt_secret()

        # Creer un token avec le nouveau secret
        token = jwt.encode(
            {"sub": "1", "tenant_id": 1},
            new_secret,
            algorithm="HS256"
        )

        # Decoder avec le meme secret
        payload = jwt.decode(token, new_secret, algorithms=["HS256"])

        assert payload["sub"] == "1"
        assert payload["tenant_id"] == 1

    @pytest.mark.unit
    def test_old_tokens_fail_with_new_secret(self):
        """Les anciens tokens echouent avec un nouveau secret"""
        from app.core.secrets import SecretRotator
        from jose import jwt, JWTError

        rotator = SecretRotator()

        old_secret = "old-secret-key-32-chars-minimum!"
        new_secret = rotator.rotate_jwt_secret()

        # Token signe avec l'ancien secret
        old_token = jwt.encode(
            {"sub": "1"},
            old_secret,
            algorithm="HS256"
        )

        # Doit echouer avec le nouveau secret
        with pytest.raises(JWTError):
            jwt.decode(old_token, new_secret, algorithms=["HS256"])
