"""
Tests unitaires TDD pour le service MFA.

Ce service gere:
- Generation et verification TOTP (pyotp)
- Setup MFA avec QR code
- Generation et verification des recovery codes
- Activation/desactivation MFA

TDD: Ces tests sont ecrits AVANT l'implementation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from typing import List


class TestMFAServiceSetup:
    """Tests pour le setup MFA (generation secret, QR code)"""

    @pytest.fixture
    def mock_secret_repo(self):
        """Repository MFASecret mocke"""
        return MagicMock()

    @pytest.fixture
    def mock_recovery_repo(self):
        """Repository MFARecoveryCode mocke"""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_secret_repo, mock_recovery_repo):
        """Service MFA avec repos mockes"""
        from app.services.mfa import MFAService
        return MFAService(
            mfa_secret_repository=mock_secret_repo,
            mfa_recovery_code_repository=mock_recovery_repo
        )

    def test_generate_secret_returns_base32_string(self, service):
        """generate_secret retourne un secret base32 valide"""
        secret = service.generate_secret()

        assert secret is not None
        assert len(secret) >= 16  # TOTP secrets sont minimum 16 chars
        # Verifier que c'est du base32 valide
        import base64
        try:
            base64.b32decode(secret)
            valid = True
        except Exception:
            valid = False
        assert valid

    def test_generate_secret_unique(self, service):
        """generate_secret retourne des secrets uniques"""
        secrets = [service.generate_secret() for _ in range(10)]
        unique_secrets = set(secrets)
        assert len(unique_secrets) == 10

    def test_get_provisioning_uri(self, service):
        """get_provisioning_uri retourne une URI otpauth valide"""
        secret = "JBSWY3DPEHPK3PXP"
        email = "user@example.com"
        issuer = "MassaCorp"

        uri = service.get_provisioning_uri(
            secret=secret,
            email=email,
            issuer=issuer
        )

        assert uri.startswith("otpauth://totp/")
        assert "MassaCorp" in uri
        assert "user@example.com" in uri or "user%40example.com" in uri
        assert "secret=" in uri

    def test_setup_mfa_creates_secret(self, service, mock_secret_repo):
        """setup_mfa cree un nouveau secret pour l'utilisateur"""
        mock_secret_repo.get_by_user_id.return_value = None

        result = service.setup_mfa(
            user_id=1,
            tenant_id=1,
            email="user@example.com"
        )

        assert "secret" in result
        assert "provisioning_uri" in result
        assert "qr_code" in result or "qr_code_base64" in result
        mock_secret_repo.create_or_update.assert_called_once()

    def test_setup_mfa_returns_existing_if_not_enabled(self, service, mock_secret_repo):
        """setup_mfa retourne le secret existant si pas encore active"""
        from app.models.mfa import MFASecret

        existing = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="EXISTINGSECRET",
            enabled=False
        )
        mock_secret_repo.get_by_user_id.return_value = existing

        result = service.setup_mfa(
            user_id=1,
            tenant_id=1,
            email="user@example.com"
        )

        assert result["secret"] == "EXISTINGSECRET"

    def test_setup_mfa_raises_if_already_enabled(self, service, mock_secret_repo):
        """setup_mfa leve une exception si MFA deja active"""
        from app.models.mfa import MFASecret
        from app.services.mfa import MFAAlreadyEnabledError

        existing = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = existing

        with pytest.raises(MFAAlreadyEnabledError):
            service.setup_mfa(
                user_id=1,
                tenant_id=1,
                email="user@example.com"
            )


class TestMFAServiceVerification:
    """Tests pour la verification TOTP"""

    @pytest.fixture
    def mock_secret_repo(self):
        return MagicMock()

    @pytest.fixture
    def mock_recovery_repo(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_secret_repo, mock_recovery_repo):
        from app.services.mfa import MFAService
        return MFAService(
            mfa_secret_repository=mock_secret_repo,
            mfa_recovery_code_repository=mock_recovery_repo
        )

    def test_verify_totp_valid_code(self, service, mock_secret_repo):
        """verify_totp retourne True pour un code valide"""
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        result = service.verify_totp(user_id=1, code=valid_code)

        assert result is True
        mock_secret_repo.update_last_used.assert_called_once()

    def test_verify_totp_invalid_code(self, service, mock_secret_repo):
        """verify_totp retourne False pour un code invalide"""
        from app.models.mfa import MFASecret

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="JBSWY3DPEHPK3PXP",
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        result = service.verify_totp(user_id=1, code="000000")

        assert result is False

    def test_verify_totp_no_mfa_configured(self, service, mock_secret_repo):
        """verify_totp retourne False si MFA pas configure"""
        mock_secret_repo.get_by_user_id.return_value = None

        result = service.verify_totp(user_id=1, code="123456")

        assert result is False

    def test_verify_totp_mfa_not_enabled(self, service, mock_secret_repo):
        """verify_totp retourne False si MFA pas active"""
        from app.models.mfa import MFASecret

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=False
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        result = service.verify_totp(user_id=1, code="123456")

        assert result is False

    def test_verify_totp_with_window(self, service, mock_secret_repo):
        """verify_totp accepte les codes dans une fenetre de temps"""
        import pyotp
        secret = pyotp.random_base32()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        # Generer le code actuel
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        result = service.verify_totp(user_id=1, code=valid_code, window=1)

        assert result is True


class TestMFAServiceActivation:
    """Tests pour l'activation/desactivation MFA"""

    @pytest.fixture
    def mock_secret_repo(self):
        return MagicMock()

    @pytest.fixture
    def mock_recovery_repo(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_secret_repo, mock_recovery_repo):
        from app.services.mfa import MFAService
        return MFAService(
            mfa_secret_repository=mock_secret_repo,
            mfa_recovery_code_repository=mock_recovery_repo
        )

    def test_enable_mfa_with_valid_code(self, service, mock_secret_repo, mock_recovery_repo):
        """enable_mfa active le MFA apres verification du code"""
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=False
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa
        mock_secret_repo.enable_mfa.return_value = True

        result = service.enable_mfa(user_id=1, code=valid_code)

        assert result["enabled"] is True
        assert "recovery_codes" in result
        mock_secret_repo.enable_mfa.assert_called_once()
        mock_recovery_repo.create_codes_for_user.assert_called_once()

    def test_enable_mfa_generates_recovery_codes(self, service, mock_secret_repo, mock_recovery_repo):
        """enable_mfa genere des codes de recuperation"""
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=False
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa
        mock_secret_repo.enable_mfa.return_value = True

        result = service.enable_mfa(user_id=1, code=valid_code)

        assert len(result["recovery_codes"]) == 10  # 10 codes par defaut

    def test_enable_mfa_invalid_code_raises(self, service, mock_secret_repo):
        """enable_mfa leve une exception si code invalide"""
        from app.models.mfa import MFASecret
        from app.services.mfa import InvalidMFACodeError

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="JBSWY3DPEHPK3PXP",
            enabled=False
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        with pytest.raises(InvalidMFACodeError):
            service.enable_mfa(user_id=1, code="000000")

    def test_disable_mfa_with_valid_code(self, service, mock_secret_repo, mock_recovery_repo):
        """disable_mfa desactive le MFA apres verification"""
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa
        mock_secret_repo.disable_mfa.return_value = True

        result = service.disable_mfa(user_id=1, code=valid_code)

        assert result is True
        mock_secret_repo.disable_mfa.assert_called_once()
        mock_recovery_repo.delete_all_for_user.assert_called_once()

    def test_disable_mfa_invalid_code_raises(self, service, mock_secret_repo):
        """disable_mfa leve une exception si code invalide"""
        from app.models.mfa import MFASecret
        from app.services.mfa import InvalidMFACodeError

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="JBSWY3DPEHPK3PXP",
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        with pytest.raises(InvalidMFACodeError):
            service.disable_mfa(user_id=1, code="000000")


class TestMFAServiceRecoveryCodes:
    """Tests pour les codes de recuperation"""

    @pytest.fixture
    def mock_secret_repo(self):
        return MagicMock()

    @pytest.fixture
    def mock_recovery_repo(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_secret_repo, mock_recovery_repo):
        from app.services.mfa import MFAService
        return MFAService(
            mfa_secret_repository=mock_secret_repo,
            mfa_recovery_code_repository=mock_recovery_repo
        )

    def test_generate_recovery_codes(self, service):
        """generate_recovery_codes genere des codes uniques"""
        codes = service.generate_recovery_codes(count=10)

        assert len(codes) == 10
        assert len(set(codes)) == 10  # Tous uniques
        # Chaque code doit etre un format lisible (ex: XXXX-XXXX)
        for code in codes:
            assert len(code) >= 8

    def test_verify_recovery_code_valid(self, service, mock_secret_repo, mock_recovery_repo):
        """verify_recovery_code valide un code correct"""
        from app.models.mfa import MFARecoveryCode

        # Le code brut et son hash
        code_plain = "ABCD-1234"

        mock_code = MFARecoveryCode(
            id=1,
            user_id=1,
            tenant_id=1,
            code_hash="hashed_value"  # En pratique, hash du code
        )
        mock_code.used_at = None

        # Mock pour simuler la verification de hash
        mock_recovery_repo.get_valid_codes_for_user.return_value = [mock_code]

        # Le service doit verifier le hash
        with patch.object(service, '_verify_code_hash', return_value=True):
            result = service.verify_recovery_code(user_id=1, code=code_plain)

        assert result is True

    def test_verify_recovery_code_marks_as_used(self, service, mock_secret_repo, mock_recovery_repo):
        """verify_recovery_code marque le code comme utilise"""
        from app.models.mfa import MFARecoveryCode

        mock_code = MFARecoveryCode(
            id=1,
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )
        mock_recovery_repo.get_valid_codes_for_user.return_value = [mock_code]

        with patch.object(service, '_verify_code_hash', return_value=True):
            service.verify_recovery_code(user_id=1, code="ABCD-1234")

        mock_recovery_repo.mark_code_as_used.assert_called_once()

    def test_verify_recovery_code_invalid(self, service, mock_recovery_repo):
        """verify_recovery_code retourne False pour code invalide"""
        mock_recovery_repo.get_valid_codes_for_user.return_value = []

        result = service.verify_recovery_code(user_id=1, code="INVALID")

        assert result is False

    def test_regenerate_recovery_codes(self, service, mock_secret_repo, mock_recovery_repo):
        """regenerate_recovery_codes remplace tous les codes"""
        import pyotp
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        from app.models.mfa import MFASecret
        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret=secret,
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        result = service.regenerate_recovery_codes(user_id=1, totp_code=valid_code)

        mock_recovery_repo.delete_all_for_user.assert_called_once()
        mock_recovery_repo.create_codes_for_user.assert_called_once()
        assert len(result) == 10

    def test_get_recovery_codes_count(self, service, mock_recovery_repo):
        """get_recovery_codes_count retourne le nombre de codes valides"""
        mock_recovery_repo.count_valid_codes.return_value = 7

        result = service.get_recovery_codes_count(user_id=1)

        assert result == 7


class TestMFAServiceStatus:
    """Tests pour le statut MFA"""

    @pytest.fixture
    def mock_secret_repo(self):
        return MagicMock()

    @pytest.fixture
    def mock_recovery_repo(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_secret_repo, mock_recovery_repo):
        from app.services.mfa import MFAService
        return MFAService(
            mfa_secret_repository=mock_secret_repo,
            mfa_recovery_code_repository=mock_recovery_repo
        )

    def test_get_mfa_status_enabled(self, service, mock_secret_repo, mock_recovery_repo):
        """get_mfa_status retourne le statut complet"""
        from app.models.mfa import MFASecret

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_mfa.created_at = datetime.now(timezone.utc)
        mock_mfa.last_used_at = datetime.now(timezone.utc)
        mock_secret_repo.get_by_user_id.return_value = mock_mfa
        mock_recovery_repo.count_valid_codes.return_value = 8

        result = service.get_mfa_status(user_id=1)

        assert result["enabled"] is True
        assert result["configured"] is True
        assert result["recovery_codes_remaining"] == 8
        assert "last_used_at" in result

    def test_get_mfa_status_not_configured(self, service, mock_secret_repo, mock_recovery_repo):
        """get_mfa_status retourne configured=False si pas de secret"""
        mock_secret_repo.get_by_user_id.return_value = None

        result = service.get_mfa_status(user_id=1)

        assert result["enabled"] is False
        assert result["configured"] is False
        assert result["recovery_codes_remaining"] == 0

    def test_is_mfa_required(self, service, mock_secret_repo):
        """is_mfa_required verifie si MFA est actif pour l'utilisateur"""
        from app.models.mfa import MFASecret

        mock_mfa = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_secret_repo.get_by_user_id.return_value = mock_mfa

        result = service.is_mfa_required(user_id=1)

        assert result is True

    def test_is_mfa_required_false(self, service, mock_secret_repo):
        """is_mfa_required retourne False si MFA pas active"""
        mock_secret_repo.get_by_user_id.return_value = None

        result = service.is_mfa_required(user_id=1)

        assert result is False
