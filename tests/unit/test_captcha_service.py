"""
Tests unitaires pour CaptchaService
Validation reCAPTCHA v3 et hCaptcha
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.captcha import (
    CaptchaService,
    CaptchaProvider,
    CaptchaResult,
    CaptchaValidationError,
    get_captcha_service,
)


class TestCaptchaServiceInit:
    """Tests d'initialisation du service CAPTCHA."""

    def test_init_with_defaults(self):
        """Initialisation avec valeurs par defaut."""
        service = CaptchaService()
        assert service.provider == CaptchaProvider.RECAPTCHA
        assert service.score_threshold == 0.5
        assert service.timeout == 5

    def test_init_with_custom_values(self):
        """Initialisation avec valeurs personnalisees."""
        service = CaptchaService(
            enabled=True,
            provider="hcaptcha",
            secret_key="test_secret",
            score_threshold=0.7,
            timeout=10
        )
        assert service.enabled is True
        assert service.provider == CaptchaProvider.HCAPTCHA
        assert service.secret_key == "test_secret"
        assert service.score_threshold == 0.7
        assert service.timeout == 10

    def test_is_enabled_false_when_disabled(self):
        """is_enabled retourne False si desactive."""
        service = CaptchaService(enabled=False, secret_key="test")
        assert service.is_enabled() is False

    def test_is_enabled_false_when_no_secret(self):
        """is_enabled retourne False si pas de secret."""
        service = CaptchaService(enabled=True, secret_key="")
        assert service.is_enabled() is False

    def test_is_enabled_true_when_configured(self):
        """is_enabled retourne True si configure correctement."""
        service = CaptchaService(enabled=True, secret_key="test_secret")
        assert service.is_enabled() is True


class TestCaptchaValidation:
    """Tests de validation CAPTCHA."""

    @pytest.fixture
    def service_disabled(self):
        """Service CAPTCHA desactive."""
        return CaptchaService(enabled=False)

    @pytest.fixture
    def service_recaptcha(self):
        """Service reCAPTCHA active."""
        return CaptchaService(
            enabled=True,
            provider="recaptcha",
            secret_key="test_secret",
            score_threshold=0.5
        )

    @pytest.fixture
    def service_hcaptcha(self):
        """Service hCaptcha active."""
        return CaptchaService(
            enabled=True,
            provider="hcaptcha",
            secret_key="test_secret"
        )

    @pytest.mark.asyncio
    async def test_validate_disabled_service(self, service_disabled):
        """Validation reussit si service desactive."""
        result = await service_disabled.validate("any_token")
        assert result.success is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_validate_empty_token_raises(self, service_recaptcha):
        """Token vide leve CaptchaValidationError."""
        with pytest.raises(CaptchaValidationError) as exc:
            await service_recaptcha.validate("")
        assert "manquant" in exc.value.message

    @pytest.mark.asyncio
    async def test_validate_recaptcha_success(self, service_recaptcha):
        """Validation reCAPTCHA reussie."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "score": 0.9,
            "action": "login",
            "hostname": "example.com"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await service_recaptcha.validate(
                "valid_token",
                remote_ip="192.168.1.1",
                expected_action="login"
            )

            assert result.success is True
            assert result.score == 0.9
            assert result.action == "login"
            assert result.hostname == "example.com"

    @pytest.mark.asyncio
    async def test_validate_recaptcha_low_score(self, service_recaptcha):
        """Score reCAPTCHA trop bas leve exception."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "score": 0.2,
            "action": "login"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(CaptchaValidationError) as exc:
                await service_recaptcha.validate("token")
            assert "insuffisant" in exc.value.message

    @pytest.mark.asyncio
    async def test_validate_recaptcha_wrong_action(self, service_recaptcha):
        """Action incorrecte leve exception."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "score": 0.9,
            "action": "register"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(CaptchaValidationError) as exc:
                await service_recaptcha.validate("token", expected_action="login")
            assert "incorrecte" in exc.value.message

    @pytest.mark.asyncio
    async def test_validate_recaptcha_failed(self, service_recaptcha):
        """Validation reCAPTCHA echouee."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(CaptchaValidationError) as exc:
                await service_recaptcha.validate("invalid_token")
            assert "echouee" in exc.value.message
            assert "invalid-input-response" in exc.value.error_codes

    @pytest.mark.asyncio
    async def test_validate_hcaptcha_success(self, service_hcaptcha):
        """Validation hCaptcha reussie."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "hostname": "example.com"
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await service_hcaptcha.validate("valid_token")

            assert result.success is True
            assert result.hostname == "example.com"

    @pytest.mark.asyncio
    async def test_validate_hcaptcha_failed(self, service_hcaptcha):
        """Validation hCaptcha echouee."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-or-already-seen-response"]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises(CaptchaValidationError) as exc:
                await service_hcaptcha.validate("invalid_token")
            assert "hCaptcha" in exc.value.message

    @pytest.mark.asyncio
    async def test_validate_timeout_error(self, service_recaptcha):
        """Timeout leve exception."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timeout")

            with pytest.raises(CaptchaValidationError) as exc:
                await service_recaptcha.validate("token")
            assert "Timeout" in exc.value.message

    @pytest.mark.asyncio
    async def test_validate_http_error(self, service_recaptcha):
        """Erreur HTTP leve exception."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection error")

            with pytest.raises(CaptchaValidationError) as exc:
                await service_recaptcha.validate("token")
            assert "communication" in exc.value.message


class TestValidateOrSkip:
    """Tests de validate_or_skip."""

    @pytest.fixture
    def service(self):
        return CaptchaService(enabled=True, secret_key="test")

    @pytest.fixture
    def service_disabled(self):
        return CaptchaService(enabled=False)

    @pytest.mark.asyncio
    async def test_skip_when_disabled(self, service_disabled):
        """Skip si service desactive."""
        result = await service_disabled.validate_or_skip(None)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_skip_when_token_none_not_required(self, service):
        """Skip si token None et non requis."""
        result = await service.validate_or_skip(None, required=False)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_raises_when_required_no_token(self, service):
        """Leve exception si requis mais pas de token."""
        with pytest.raises(CaptchaValidationError) as exc:
            await service.validate_or_skip(None, required=True)
        assert "requis" in exc.value.message

    @pytest.mark.asyncio
    async def test_validates_when_token_provided(self, service):
        """Valide si token fourni."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "score": 0.9}
        mock_response.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await service.validate_or_skip("token")
            assert result.success is True


class TestCaptchaSingleton:
    """Tests du singleton."""

    def test_get_captcha_service_returns_instance(self):
        """get_captcha_service retourne une instance."""
        service = get_captcha_service()
        assert isinstance(service, CaptchaService)

    def test_get_captcha_service_returns_same_instance(self):
        """get_captcha_service retourne la meme instance."""
        service1 = get_captcha_service()
        service2 = get_captcha_service()
        assert service1 is service2


class TestCaptchaResult:
    """Tests de CaptchaResult."""

    def test_result_success(self):
        """CaptchaResult avec succes."""
        result = CaptchaResult(success=True, score=0.9, action="login")
        assert result.success is True
        assert result.score == 0.9
        assert result.action == "login"

    def test_result_failure(self):
        """CaptchaResult avec echec."""
        result = CaptchaResult(success=False, error_codes=["invalid-token"])
        assert result.success is False
        assert "invalid-token" in result.error_codes


class TestCaptchaValidationError:
    """Tests de CaptchaValidationError."""

    def test_error_with_message(self):
        """Exception avec message."""
        error = CaptchaValidationError("Test error")
        assert error.message == "Test error"
        assert str(error) == "Test error"

    def test_error_with_codes(self):
        """Exception avec codes d'erreur."""
        error = CaptchaValidationError("Test", error_codes=["code1", "code2"])
        assert error.error_codes == ["code1", "code2"]
