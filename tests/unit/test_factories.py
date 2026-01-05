"""
Tests comportementaux pour les factories FactoryBoy.

Ces tests vérifient que les factories génèrent des objets valides
et cohérents avec les modèles SQLAlchemy.
"""
import pytest


class TestTenantFactory:
    """Tests pour TenantFactory."""

    def test_tenant_factory_creates_valid_tenant(self):
        """
        La factory doit créer un Tenant valide.
        """
        from tests.factories import TenantFactory

        tenant = TenantFactory.build()

        assert tenant.id is not None
        assert tenant.name is not None
        assert tenant.slug is not None
        assert tenant.is_active is True

    def test_tenant_factory_generates_unique_slugs(self):
        """
        La factory doit générer des slugs uniques.
        """
        from tests.factories import TenantFactory

        tenant1 = TenantFactory.build()
        tenant2 = TenantFactory.build()

        assert tenant1.slug != tenant2.slug

    def test_tenant_factory_allows_overrides(self):
        """
        La factory doit permettre de surcharger les valeurs.
        """
        from tests.factories import TenantFactory

        tenant = TenantFactory.build(name="Custom Corp", is_active=False)

        assert tenant.name == "Custom Corp"
        assert tenant.is_active is False


class TestUserFactory:
    """Tests pour UserFactory."""

    def test_user_factory_creates_valid_user(self):
        """
        La factory doit créer un User valide.
        """
        from tests.factories import UserFactory

        user = UserFactory.build()

        assert user.id is not None
        assert user.email is not None
        assert user.password_hash is not None
        assert user.is_active is True
        assert user.is_verified is True

    def test_user_factory_generates_unique_emails(self):
        """
        La factory doit générer des emails uniques.
        """
        from tests.factories import UserFactory

        user1 = UserFactory.build()
        user2 = UserFactory.build()

        assert user1.email != user2.email

    def test_user_factory_password_hash_is_valid_argon2id(self):
        """
        Le password_hash doit etre un hash Argon2id valide.
        (Migration bcrypt -> Argon2id)
        """
        from tests.factories import UserFactory

        user = UserFactory.build()

        assert user.password_hash.startswith("$argon2id$")

    def test_user_factory_with_custom_password(self):
        """
        La factory doit permettre de créer un user avec mot de passe custom.
        """
        from tests.factories import UserFactory
        from app.core.security import verify_password

        user = UserFactory.create_with_password("CustomP@ss123!")

        assert verify_password("CustomP@ss123!", user.password_hash)

    def test_admin_user_factory(self):
        """
        AdminUserFactory doit créer des superusers.
        """
        from tests.factories.user import AdminUserFactory

        admin = AdminUserFactory.build()

        assert admin.is_superuser is True

    def test_unverified_user_factory(self):
        """
        UnverifiedUserFactory doit créer des users non vérifiés.
        """
        from tests.factories.user import UnverifiedUserFactory

        user = UnverifiedUserFactory.build()

        assert user.is_verified is False

    def test_inactive_user_factory(self):
        """
        InactiveUserFactory doit créer des users désactivés.
        """
        from tests.factories.user import InactiveUserFactory

        user = InactiveUserFactory.build()

        assert user.is_active is False


class TestSessionFactory:
    """Tests pour SessionFactory."""

    def test_session_factory_creates_valid_session(self):
        """
        La factory doit créer une Session valide.
        """
        from tests.factories import SessionFactory
        import uuid

        session = SessionFactory.build()

        assert session.id is not None
        assert isinstance(session.id, uuid.UUID)
        assert session.created_at is not None
        assert session.revoked_at is None
        assert session.is_active is True

    def test_session_factory_generates_unique_ids(self):
        """
        La factory doit générer des IDs uniques.
        """
        from tests.factories import SessionFactory

        session1 = SessionFactory.build()
        session2 = SessionFactory.build()

        assert session1.id != session2.id

    def test_revoked_session_factory(self):
        """
        create_revoked doit créer une session révoquée.
        """
        from tests.factories import SessionFactory

        session = SessionFactory.create_revoked()

        assert session.revoked_at is not None
        assert session.is_active is False

    def test_expired_session_factory(self):
        """
        create_expired doit créer une session expirée.
        """
        from tests.factories import SessionFactory

        session = SessionFactory.create_expired()

        assert session.is_absolute_expired is True


class TestRefreshTokenFactory:
    """Tests pour RefreshTokenFactory."""

    def test_refresh_token_factory_creates_valid_token(self):
        """
        La factory doit créer un RefreshToken valide.
        """
        from tests.factories import RefreshTokenFactory

        token = RefreshTokenFactory.build()

        assert token.jti is not None
        assert token.token_hash is not None
        assert token.expires_at is not None
        assert token.used_at is None
        assert token.is_valid is True

    def test_used_refresh_token_factory(self):
        """
        create_used doit créer un token déjà utilisé.
        """
        from tests.factories import RefreshTokenFactory

        token = RefreshTokenFactory.create_used()

        assert token.used_at is not None
        assert token.is_valid is False

    def test_expired_refresh_token_factory(self):
        """
        create_expired doit créer un token expiré.
        """
        from tests.factories import RefreshTokenFactory

        token = RefreshTokenFactory.create_expired()

        assert token.is_expired is True


class TestMFASecretFactory:
    """Tests pour MFASecretFactory."""

    def test_mfa_secret_factory_creates_valid_secret(self):
        """
        La factory doit créer un MFASecret valide.
        """
        from tests.factories import MFASecretFactory

        mfa = MFASecretFactory.build()

        assert mfa.secret is not None
        assert len(mfa.secret) == 32  # base32 encoded
        assert mfa.enabled is False

    def test_enabled_mfa_secret_factory(self):
        """
        create_enabled doit créer un MFA activé.
        """
        from tests.factories import MFASecretFactory

        mfa = MFASecretFactory.create_enabled()

        assert mfa.enabled is True

    def test_mfa_secret_generates_valid_totp(self):
        """
        Le secret MFA doit générer des codes TOTP valides.
        """
        from tests.factories import MFASecretFactory
        import pyotp

        mfa = MFASecretFactory.build()

        # Generate TOTP code from secret
        totp = pyotp.TOTP(mfa.secret)
        code = totp.now()

        assert len(code) == 6
        assert code.isdigit()

        # Verify the code is valid
        assert totp.verify(code)


class TestMFARecoveryCodeFactory:
    """Tests pour MFARecoveryCodeFactory."""

    def test_mfa_recovery_code_factory_creates_valid_code(self):
        """
        La factory doit créer un MFARecoveryCode valide.
        """
        from tests.factories import MFARecoveryCodeFactory

        code = MFARecoveryCodeFactory.build()

        assert code.id is not None
        assert code.code_hash is not None
        assert code.used_at is None

    def test_used_recovery_code_factory(self):
        """
        create_used doit créer un code déjà utilisé.
        """
        from tests.factories import MFARecoveryCodeFactory

        code = MFARecoveryCodeFactory.create_used()

        assert code.used_at is not None


class TestAPIKeyFactory:
    """Tests pour APIKeyFactory."""

    def test_api_key_factory_creates_valid_key(self):
        """
        La factory doit créer une APIKey valide.
        """
        from tests.factories import APIKeyFactory

        api_key = APIKeyFactory.build()

        assert api_key.id is not None
        assert api_key.name is not None
        assert api_key.key_hash is not None
        assert api_key.key_prefix is not None
        assert api_key.revoked_at is None  # Not revoked

    def test_expired_api_key_factory(self):
        """
        create_expired doit créer une clé expirée.
        """
        from tests.factories import APIKeyFactory
        from datetime import datetime, timezone

        api_key = APIKeyFactory.create_expired()

        assert api_key.expires_at < datetime.now(timezone.utc)

    def test_revoked_api_key_factory(self):
        """
        create_revoked doit créer une clé révoquée.
        """
        from tests.factories import APIKeyFactory

        api_key = APIKeyFactory.create_revoked()

        assert api_key.revoked_at is not None

    def test_api_key_with_custom_scopes(self):
        """
        create_with_scopes doit créer une clé avec scopes spécifiques.
        """
        from tests.factories import APIKeyFactory

        api_key = APIKeyFactory.create_with_scopes(["users:read", "users:write"])

        assert api_key.scopes == ["users:read", "users:write"]
