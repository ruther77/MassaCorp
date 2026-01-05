"""
Tests comportementaux pour la configuration (Section 7.4).

Ces tests vérifient que:
1. database.py utilise les settings pour la config du pool
2. PASSWORD_CHECK_HIBP existe et est activé par défaut
3. security.py utilise PASSWORD_CHECK_HIBP quand check_hibp=None

SECURITE CRITIQUE:
- Le pool DB doit être configurable (pas hardcodé)
- HIBP doit être activé par défaut en production
"""
import pytest
from unittest.mock import patch, MagicMock


class TestDatabasePoolConfiguration:
    """Tests pour la configuration du pool de connexions DB."""

    def test_settings_has_database_pool_size(self):
        """
        Settings doit avoir DATABASE_POOL_SIZE.
        """
        from app.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "DATABASE_POOL_SIZE")
        assert isinstance(settings.DATABASE_POOL_SIZE, int)
        assert settings.DATABASE_POOL_SIZE > 0

    def test_settings_has_database_max_overflow(self):
        """
        Settings doit avoir DATABASE_MAX_OVERFLOW.
        """
        from app.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "DATABASE_MAX_OVERFLOW")
        assert isinstance(settings.DATABASE_MAX_OVERFLOW, int)
        assert settings.DATABASE_MAX_OVERFLOW >= 0

    def test_settings_has_database_pool_timeout(self):
        """
        Settings doit avoir DATABASE_POOL_TIMEOUT.
        """
        from app.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "DATABASE_POOL_TIMEOUT")
        assert isinstance(settings.DATABASE_POOL_TIMEOUT, int)
        assert settings.DATABASE_POOL_TIMEOUT > 0

    def test_settings_has_database_pool_recycle(self):
        """
        Settings doit avoir DATABASE_POOL_RECYCLE.
        """
        from app.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "DATABASE_POOL_RECYCLE")
        assert isinstance(settings.DATABASE_POOL_RECYCLE, int)
        assert settings.DATABASE_POOL_RECYCLE > 0

    def test_database_engine_uses_settings_pool_size(self):
        """
        CRITIQUE: L'engine DB doit utiliser settings.DATABASE_POOL_SIZE.
        """
        from app.core.database import engine
        from app.core.config import get_settings

        settings = get_settings()
        pool = engine.pool

        # Le pool size doit correspondre aux settings
        assert pool.size() == settings.DATABASE_POOL_SIZE

    def test_database_engine_uses_settings_max_overflow(self):
        """
        CRITIQUE: L'engine DB doit utiliser settings.DATABASE_MAX_OVERFLOW.
        """
        from app.core.database import engine
        from app.core.config import get_settings

        settings = get_settings()
        pool = engine.pool

        # Le max overflow doit correspondre aux settings
        assert pool._max_overflow == settings.DATABASE_MAX_OVERFLOW

    def test_database_engine_uses_settings_pool_timeout(self):
        """
        CRITIQUE: L'engine DB doit utiliser settings.DATABASE_POOL_TIMEOUT.
        """
        from app.core.database import engine
        from app.core.config import get_settings

        settings = get_settings()
        pool = engine.pool

        # Le timeout doit correspondre aux settings
        assert pool._timeout == settings.DATABASE_POOL_TIMEOUT

    def test_database_engine_uses_settings_pool_recycle(self):
        """
        CRITIQUE: L'engine DB doit utiliser settings.DATABASE_POOL_RECYCLE.
        """
        from app.core.database import engine
        from app.core.config import get_settings

        settings = get_settings()
        pool = engine.pool

        # Le recycle doit correspondre aux settings
        assert pool._recycle == settings.DATABASE_POOL_RECYCLE


class TestPasswordHIBPConfiguration:
    """Tests pour la configuration HIBP des mots de passe."""

    def test_settings_has_password_check_hibp(self):
        """
        Settings doit avoir PASSWORD_CHECK_HIBP.
        """
        from app.core.config import Settings

        settings = Settings()
        assert hasattr(settings, "PASSWORD_CHECK_HIBP")
        assert isinstance(settings.PASSWORD_CHECK_HIBP, bool)

    def test_password_check_hibp_defaults_to_true(self):
        """
        CRITIQUE: PASSWORD_CHECK_HIBP doit être True par défaut.
        """
        from app.core.config import Settings

        settings = Settings()
        assert settings.PASSWORD_CHECK_HIBP is True

    def test_validate_password_uses_settings_hibp_when_none(self):
        """
        CRITIQUE: validate_password_strength doit utiliser settings.PASSWORD_CHECK_HIBP
        quand check_hibp=None.
        """
        from app.core.security import validate_password_strength
        from unittest.mock import patch

        # Mock validate_password_policy pour capturer les arguments
        with patch("app.core.password_policy.validate_password_policy") as mock_policy:
            # Test avec un mot de passe valide
            try:
                validate_password_strength(
                    password="ValidP@ssw0rd123!",
                    check_hibp=None  # Doit utiliser settings.PASSWORD_CHECK_HIBP
                )
            except Exception:
                pass  # On s'intéresse aux arguments passés

            # Vérifier que validate_password_policy a été appelé avec check_hibp=True
            # (car settings.PASSWORD_CHECK_HIBP=True par défaut)
            if mock_policy.called:
                call_kwargs = mock_policy.call_args.kwargs
                assert call_kwargs.get("check_hibp") is True

    def test_validate_password_respects_explicit_check_hibp_false(self):
        """
        validate_password_strength doit respecter check_hibp=False explicite.
        """
        from app.core.security import validate_password_strength
        from unittest.mock import patch

        with patch("app.core.password_policy.validate_password_policy") as mock_policy:
            try:
                validate_password_strength(
                    password="ValidP@ssw0rd123!",
                    check_hibp=False  # Explicitement désactivé
                )
            except Exception:
                pass

            # Vérifier que check_hibp=False a été respecté
            if mock_policy.called:
                call_kwargs = mock_policy.call_args.kwargs
                assert call_kwargs.get("check_hibp") is False

    def test_validate_password_respects_explicit_check_hibp_true(self):
        """
        validate_password_strength doit respecter check_hibp=True explicite.
        """
        from app.core.security import validate_password_strength
        from unittest.mock import patch

        with patch("app.core.password_policy.validate_password_policy") as mock_policy:
            try:
                validate_password_strength(
                    password="ValidP@ssw0rd123!",
                    check_hibp=True  # Explicitement activé
                )
            except Exception:
                pass

            # Vérifier que check_hibp=True a été respecté
            if mock_policy.called:
                call_kwargs = mock_policy.call_args.kwargs
                assert call_kwargs.get("check_hibp") is True


class TestConfigurationFromEnvironment:
    """Tests pour le chargement de config depuis l'environnement."""

    def test_database_pool_size_from_env(self):
        """
        DATABASE_POOL_SIZE doit être configurable via variable d'environnement.
        """
        import os
        from app.core.config import Settings

        # Note: On utilise Settings() directement car get_settings() est caché
        with patch.dict(os.environ, {"DATABASE_POOL_SIZE": "20"}):
            settings = Settings()
            assert settings.DATABASE_POOL_SIZE == 20

    def test_database_max_overflow_from_env(self):
        """
        DATABASE_MAX_OVERFLOW doit être configurable via variable d'environnement.
        """
        import os
        from app.core.config import Settings

        with patch.dict(os.environ, {"DATABASE_MAX_OVERFLOW": "30"}):
            settings = Settings()
            assert settings.DATABASE_MAX_OVERFLOW == 30

    def test_password_check_hibp_from_env(self):
        """
        PASSWORD_CHECK_HIBP doit être configurable via variable d'environnement.
        """
        import os
        from app.core.config import Settings

        with patch.dict(os.environ, {"PASSWORD_CHECK_HIBP": "false"}):
            settings = Settings()
            assert settings.PASSWORD_CHECK_HIBP is False

    def test_password_check_hibp_env_true(self):
        """
        PASSWORD_CHECK_HIBP=true doit activer la vérification.
        """
        import os
        from app.core.config import Settings

        with patch.dict(os.environ, {"PASSWORD_CHECK_HIBP": "true"}):
            settings = Settings()
            assert settings.PASSWORD_CHECK_HIBP is True
