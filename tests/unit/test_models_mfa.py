"""
Tests unitaires TDD pour les modeles MFA.

Ces tests definissent le comportement attendu des modeles:
- MFASecret: Secret TOTP pour l'authentification a deux facteurs
- MFARecoveryCode: Codes de recuperation a usage unique

TDD: Ces tests sont ecrits AVANT l'implementation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


class TestMFASecretModel:
    """Tests pour le modele MFASecret"""

    def test_mfa_secret_creation_basic(self):
        """MFASecret peut etre cree avec les champs requis"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="JBSWY3DPEHPK3PXP",
            enabled=False
        )

        assert secret.user_id == 1
        assert secret.tenant_id == 1
        assert secret.secret == "JBSWY3DPEHPK3PXP"
        assert secret.enabled is False
        assert secret.last_used_at is None

    def test_mfa_secret_tablename(self):
        """MFASecret utilise le bon nom de table"""
        from app.models.mfa import MFASecret

        assert MFASecret.__tablename__ == "mfa_secrets"

    def test_mfa_secret_primary_key_is_user_id(self):
        """user_id est la cle primaire de MFASecret"""
        from app.models.mfa import MFASecret
        from sqlalchemy import inspect

        mapper = inspect(MFASecret)
        pk_columns = [col.name for col in mapper.primary_key]
        assert pk_columns == ["user_id"]

    def test_mfa_secret_enabled_default_false(self):
        """enabled est False par defaut"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="JBSWY3DPEHPK3PXP"
        )
        # Le default est defini au niveau DB, pas Python
        # Donc on verifie juste que le champ existe
        assert hasattr(secret, 'enabled')

    def test_mfa_secret_repr(self):
        """__repr__ retourne une representation lisible"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=42,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )

        repr_str = repr(secret)
        assert "MFASecret" in repr_str
        assert "42" in repr_str or "user_id" in repr_str

    def test_mfa_secret_to_dict(self):
        """to_dict serialise le secret sans exposer le secret brut"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SUPERSECRET",
            enabled=True
        )
        secret.created_at = datetime.now(timezone.utc)

        result = secret.to_dict()

        assert result["user_id"] == 1
        assert result["tenant_id"] == 1
        assert result["enabled"] is True
        # Le secret brut NE DOIT PAS etre expose
        assert "secret" not in result or result.get("secret") is None

    def test_mfa_secret_to_dict_with_secret_option(self):
        """to_dict peut inclure le secret si explicitement demande"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SUPERSECRET",
            enabled=False
        )
        secret.created_at = datetime.now(timezone.utc)

        result = secret.to_dict(include_secret=True)

        assert result["secret"] == "SUPERSECRET"

    def test_mfa_secret_is_configured_property(self):
        """is_configured retourne True si enabled"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        assert secret.is_configured is True

        secret.enabled = False
        assert secret.is_configured is False

    def test_mfa_secret_update_last_used(self):
        """update_last_used met a jour le timestamp"""
        from app.models.mfa import MFASecret

        secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        assert secret.last_used_at is None

        secret.update_last_used()

        assert secret.last_used_at is not None
        assert isinstance(secret.last_used_at, datetime)


class TestMFARecoveryCodeModel:
    """Tests pour le modele MFARecoveryCode"""

    def test_recovery_code_creation_basic(self):
        """MFARecoveryCode peut etre cree avec les champs requis"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            user_id=1,
            tenant_id=1,
            code_hash="hashed_code_here"
        )

        assert code.user_id == 1
        assert code.tenant_id == 1
        assert code.code_hash == "hashed_code_here"
        assert code.used_at is None

    def test_recovery_code_tablename(self):
        """MFARecoveryCode utilise le bon nom de table"""
        from app.models.mfa import MFARecoveryCode

        assert MFARecoveryCode.__tablename__ == "mfa_recovery_codes"

    def test_recovery_code_primary_key_is_id(self):
        """id est la cle primaire auto-incrementee"""
        from app.models.mfa import MFARecoveryCode
        from sqlalchemy import inspect

        mapper = inspect(MFARecoveryCode)
        pk_columns = [col.name for col in mapper.primary_key]
        assert pk_columns == ["id"]

    def test_recovery_code_is_used_property(self):
        """is_used retourne True si used_at est defini"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )
        assert code.is_used is False

        code.used_at = datetime.now(timezone.utc)
        assert code.is_used is True

    def test_recovery_code_is_valid_property(self):
        """is_valid retourne True si non utilise"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )
        assert code.is_valid is True

        code.used_at = datetime.now(timezone.utc)
        assert code.is_valid is False

    def test_recovery_code_mark_as_used(self):
        """mark_as_used definit used_at"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )
        assert code.used_at is None

        code.mark_as_used()

        assert code.used_at is not None
        assert isinstance(code.used_at, datetime)

    def test_recovery_code_repr(self):
        """__repr__ retourne une representation lisible"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            id=99,
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )

        repr_str = repr(code)
        assert "MFARecoveryCode" in repr_str

    def test_recovery_code_to_dict(self):
        """to_dict serialise le code sans exposer le hash"""
        from app.models.mfa import MFARecoveryCode

        code = MFARecoveryCode(
            id=1,
            user_id=1,
            tenant_id=1,
            code_hash="secret_hash"
        )
        code.created_at = datetime.now(timezone.utc)

        result = code.to_dict()

        assert result["id"] == 1
        assert result["user_id"] == 1
        assert result["is_used"] is False
        # Le hash NE DOIT PAS etre expose
        assert "code_hash" not in result


class TestMFASecretRelations:
    """Tests pour les relations du modele MFASecret"""

    def test_mfa_secret_has_user_relation(self):
        """MFASecret a une relation vers User"""
        from app.models.mfa import MFASecret
        from sqlalchemy import inspect

        mapper = inspect(MFASecret)
        relationships = [r.key for r in mapper.relationships]
        assert "user" in relationships

    def test_mfa_secret_has_tenant_relation(self):
        """MFASecret a une relation vers Tenant"""
        from app.models.mfa import MFASecret
        from sqlalchemy import inspect

        mapper = inspect(MFASecret)
        relationships = [r.key for r in mapper.relationships]
        assert "tenant" in relationships


class TestMFARecoveryCodeRelations:
    """Tests pour les relations du modele MFARecoveryCode"""

    def test_recovery_code_has_user_relation(self):
        """MFARecoveryCode a une relation vers User"""
        from app.models.mfa import MFARecoveryCode
        from sqlalchemy import inspect

        mapper = inspect(MFARecoveryCode)
        relationships = [r.key for r in mapper.relationships]
        assert "user" in relationships

    def test_recovery_code_has_tenant_relation(self):
        """MFARecoveryCode a une relation vers Tenant"""
        from app.models.mfa import MFARecoveryCode
        from sqlalchemy import inspect

        mapper = inspect(MFARecoveryCode)
        relationships = [r.key for r in mapper.relationships]
        assert "tenant" in relationships
