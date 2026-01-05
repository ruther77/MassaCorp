"""
Tests pour le module password_policy.

Verifie:
- Detection des mots de passe communs
- Verification HIBP (mock)
- Detection email/username dans password
- Validation combinee
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.password_policy import (
    COMMON_PASSWORDS,
    check_common_password,
    validate_not_common,
    CommonPasswordError,
    get_hibp_sha1_prefix,
    check_hibp_sync,
    validate_not_compromised,
    CompromisedPasswordError,
    check_password_contains_user_info,
    validate_not_user_info,
    PasswordContainsUserInfoError,
    validate_password_policy,
)
from app.core.security import validate_password_strength, PasswordValidationError


# =============================================================================
# Tests: Liste de mots de passe communs
# =============================================================================

class TestCommonPasswords:
    """Tests pour la detection de mots de passe communs."""

    def test_common_password_detected(self):
        """Les mots de passe communs sont detectes."""
        assert check_common_password("password") is True
        assert check_common_password("123456") is True
        assert check_common_password("qwerty") is True
        assert check_common_password("letmein") is True

    def test_common_password_case_insensitive(self):
        """Detection case-insensitive."""
        assert check_common_password("PASSWORD") is True
        assert check_common_password("Password") is True
        assert check_common_password("QWERTY") is True

    def test_common_password_with_suffix_stripped(self):
        """Detection avec suffixes numeriques/speciaux."""
        assert check_common_password("password!") is True
        assert check_common_password("password123") is True
        assert check_common_password("qwerty!@#") is True

    def test_strong_password_not_common(self):
        """Mots de passe forts ne sont pas detectes comme communs."""
        assert check_common_password("X7$kL9#mQ2@pN4!") is False
        assert check_common_password("UniqueP@ss123!") is False

    def test_empty_password(self):
        """Mot de passe vide."""
        assert check_common_password("") is False
        assert check_common_password(None) is False

    def test_validate_not_common_raises(self):
        """validate_not_common leve une exception pour mots de passe communs."""
        with pytest.raises(CommonPasswordError):
            validate_not_common("password")

    def test_validate_not_common_ok(self):
        """validate_not_common passe pour mots de passe non communs."""
        validate_not_common("UniqueP@ssword123!")  # Ne doit pas lever d'exception


# =============================================================================
# Tests: HIBP (Have I Been Pwned)
# =============================================================================

class TestHIBP:
    """Tests pour la verification HIBP."""

    def test_sha1_prefix_calculation(self):
        """Calcul correct du prefix SHA-1."""
        prefix, suffix = get_hibp_sha1_prefix("password")
        # SHA1("password") = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
        assert prefix == "5BAA6"
        assert suffix == "1E4C9B93F3F0682250B6CF8331B7EE68FD8"

    @patch("app.core.password_policy.httpx.Client")
    def test_check_hibp_found(self, mock_client_class):
        """Detection de mot de passe compromis."""
        # Mock response HIBP
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            "1E4C9B93F3F0682250B6CF8331B7EE68FD8:3861493\n"  # password
            "OTHER_SUFFIX:123\n"
        )

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        count = check_hibp_sync("password")
        assert count == 3861493

    @patch("app.core.password_policy.httpx.Client")
    def test_check_hibp_not_found(self, mock_client_class):
        """Mot de passe non compromis retourne 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OTHER_SUFFIX:123\nANOTHER:456\n"

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        count = check_hibp_sync("SuperSecureP@ss123!")
        assert count == 0

    @patch("app.core.password_policy.httpx.Client")
    def test_check_hibp_timeout(self, mock_client_class):
        """Timeout HIBP retourne None."""
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        count = check_hibp_sync("password")
        assert count is None

    @patch("app.core.password_policy.httpx.Client")
    def test_check_hibp_api_error(self, mock_client_class):
        """Erreur API HIBP retourne None."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = lambda self: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_class.return_value = mock_client

        count = check_hibp_sync("password")
        assert count is None

    @patch("app.core.password_policy.check_hibp_sync")
    def test_validate_not_compromised_raises(self, mock_check):
        """validate_not_compromised leve exception si compromis."""
        mock_check.return_value = 1000

        with pytest.raises(CompromisedPasswordError):
            validate_not_compromised("password")

    @patch("app.core.password_policy.check_hibp_sync")
    def test_validate_not_compromised_ok(self, mock_check):
        """validate_not_compromised passe si non compromis."""
        mock_check.return_value = 0
        validate_not_compromised("SuperSecure!")  # Ne doit pas lever

    @patch("app.core.password_policy.check_hibp_sync")
    def test_validate_not_compromised_fail_open(self, mock_check):
        """fail_open=True accepte en cas d'erreur API."""
        mock_check.return_value = None  # Erreur API
        validate_not_compromised("password", fail_open=True)  # Ne doit pas lever

    @patch("app.core.password_policy.check_hibp_sync")
    def test_validate_not_compromised_fail_closed(self, mock_check):
        """fail_open=False rejette en cas d'erreur API."""
        mock_check.return_value = None  # Erreur API

        with pytest.raises(CompromisedPasswordError):
            validate_not_compromised("password", fail_open=False)


# =============================================================================
# Tests: Email/Username dans password
# =============================================================================

class TestUserInfoInPassword:
    """Tests pour la detection d'infos utilisateur dans le password."""

    def test_email_in_password(self):
        """Email detecte dans password."""
        assert check_password_contains_user_info(
            "john.doe@example.com123!",
            email="john.doe@example.com"
        ) is True

    def test_email_local_part_in_password(self):
        """Partie locale de l'email detectee."""
        assert check_password_contains_user_info(
            "john.doe123!@#",
            email="john.doe@example.com"
        ) is True

    def test_username_in_password(self):
        """Username detecte dans password."""
        assert check_password_contains_user_info(
            "johnsmith123!@#",
            username="johnsmith"
        ) is True

    def test_case_insensitive(self):
        """Detection case-insensitive."""
        assert check_password_contains_user_info(
            "JOHNDOE123!@#",
            email="johndoe@example.com"
        ) is True

    def test_no_user_info(self):
        """Password sans infos utilisateur."""
        assert check_password_contains_user_info(
            "SecureP@ssword123!",
            email="john@example.com",
            username="johndoe"
        ) is False

    def test_short_username_ignored(self):
        """Username court (< 3 chars) ignore."""
        assert check_password_contains_user_info(
            "ab123!@#XYZ",
            username="ab"
        ) is False

    def test_validate_not_user_info_raises(self):
        """validate_not_user_info leve exception si infos detectees."""
        with pytest.raises(PasswordContainsUserInfoError):
            validate_not_user_info(
                "johndoe123!@#",
                email="johndoe@example.com"
            )

    def test_validate_not_user_info_ok(self):
        """validate_not_user_info passe sans infos."""
        validate_not_user_info(
            "SecureP@ssword123!",
            email="john@example.com"
        )


# =============================================================================
# Tests: Validation combinee
# =============================================================================

class TestValidatePasswordPolicy:
    """Tests pour validate_password_policy."""

    def test_common_password_rejected(self):
        """Mot de passe commun rejete."""
        with pytest.raises(CommonPasswordError):
            validate_password_policy("Password1!", check_hibp=False)

    def test_user_info_rejected(self):
        """Password avec infos utilisateur rejete."""
        with pytest.raises(PasswordContainsUserInfoError):
            validate_password_policy(
                "johndoe123!@#XYZ",
                email="johndoe@example.com",
                check_hibp=False
            )

    @patch("app.core.password_policy.check_hibp_sync")
    def test_compromised_rejected(self, mock_check):
        """Password compromis rejete."""
        mock_check.return_value = 1000

        with pytest.raises(CompromisedPasswordError):
            validate_password_policy(
                "UniqueP@ss123!",
                check_hibp=True
            )

    @patch("app.core.password_policy.check_hibp_sync")
    def test_valid_password_accepted(self, mock_check):
        """Password valide accepte."""
        mock_check.return_value = 0

        # Ne doit pas lever d'exception
        validate_password_policy(
            "X7$kL9#mQ2@pN4!",
            email="user@example.com",
            username="user123",
            check_hibp=True
        )


# =============================================================================
# Tests: Integration avec validate_password_strength
# =============================================================================

class TestValidatePasswordStrengthIntegration:
    """Tests d'integration avec la fonction principale."""

    def test_common_password_rejected_by_strength(self):
        """validate_password_strength rejette les mots de passe communs."""
        # "Password1!" respecte les regles de complexite mais est commun
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("Password1!")

        assert "commun" in str(exc_info.value).lower()

    def test_user_info_rejected_by_strength(self):
        """validate_password_strength rejette password avec email."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength(
                "JohnDoe123!@#",
                email="johndoe@example.com"
            )

        assert "email" in str(exc_info.value).lower() or "utilisateur" in str(exc_info.value).lower()

    def test_strong_password_accepted(self):
        """validate_password_strength accepte un mot de passe fort."""
        result = validate_password_strength(
            "X7$kL9#mQ2@pN4!",
            email="user@example.com",
            check_hibp=False
        )
        assert result is True

    def test_basic_validation_still_works(self):
        """Les regles de base fonctionnent toujours."""
        # Trop court
        with pytest.raises(PasswordValidationError):
            validate_password_strength("Short1!")

        # Pas de majuscule
        with pytest.raises(PasswordValidationError):
            validate_password_strength("nouppercase1!")

        # Pas de minuscule
        with pytest.raises(PasswordValidationError):
            validate_password_strength("NOLOWERCASE1!")

        # Pas de chiffre
        with pytest.raises(PasswordValidationError):
            validate_password_strength("NoDigits!@#")

        # Pas de caractere special
        with pytest.raises(PasswordValidationError):
            validate_password_strength("NoSpecial123")

    @patch("app.core.password_policy.check_hibp_sync")
    def test_hibp_check_when_enabled(self, mock_check):
        """HIBP est appele quand check_hibp=True."""
        mock_check.return_value = 0

        validate_password_strength(
            "UniqueP@ss123!XYZ",
            check_hibp=True
        )

        mock_check.assert_called_once()

    def test_hibp_not_called_by_default(self):
        """HIBP n'est pas appele par defaut."""
        with patch("app.core.password_policy.check_hibp_sync") as mock_check:
            validate_password_strength(
                "UniqueP@ss123!XYZ",
                check_hibp=False
            )
            mock_check.assert_not_called()


# =============================================================================
# Tests: Edge cases
# =============================================================================

class TestEdgeCases:
    """Tests pour les cas limites."""

    def test_empty_email_and_username(self):
        """Email et username vides sont ignores."""
        assert check_password_contains_user_info(
            "Password123!",
            email="",
            username=""
        ) is False

    def test_none_email_and_username(self):
        """Email et username None sont ignores."""
        assert check_password_contains_user_info(
            "Password123!",
            email=None,
            username=None
        ) is False

    def test_password_exactly_like_email(self):
        """Password = email exactement."""
        assert check_password_contains_user_info(
            "john@example.com",
            email="john@example.com"
        ) is True

    def test_unicode_password(self):
        """Mots de passe avec caracteres unicode."""
        # Ne doit pas crasher
        result = check_common_password("pässwörd")
        assert isinstance(result, bool)

    def test_very_long_password(self):
        """Tres long mot de passe."""
        long_pass = "A" * 100 + "b1!"
        # Ne doit pas crasher et n'est pas commun
        assert check_common_password(long_pass) is False
