"""
Service de validation CAPTCHA pour MassaCorp.

Supporte:
- Google reCAPTCHA v3 (score-based, invisible)
- hCaptcha (privacy-focused alternative)

Le CAPTCHA est requis apres N echecs de login (voir BruteforceProtection).
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CaptchaProvider(Enum):
    """Providers CAPTCHA supportes."""
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"


@dataclass
class CaptchaResult:
    """Resultat de la validation CAPTCHA."""
    success: bool
    score: Optional[float] = None  # reCAPTCHA v3 uniquement
    action: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: Optional[list] = None


class CaptchaValidationError(Exception):
    """Erreur de validation CAPTCHA."""

    def __init__(self, message: str, error_codes: Optional[list] = None):
        self.message = message
        self.error_codes = error_codes or []
        super().__init__(self.message)


class CaptchaService:
    """
    Service de validation CAPTCHA.

    Valide les tokens CAPTCHA cote serveur pour prevenir les bots.
    """

    # URLs de validation
    RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"
    HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"

    def __init__(
        self,
        enabled: bool = None,
        provider: str = None,
        secret_key: str = None,
        score_threshold: float = None,
        timeout: int = None
    ):
        """
        Initialise le service CAPTCHA.

        Args:
            enabled: Activer la validation (defaut: settings.CAPTCHA_ENABLED)
            provider: Provider CAPTCHA (defaut: settings.CAPTCHA_PROVIDER)
            secret_key: Cle secrete (defaut: settings.CAPTCHA_SECRET_KEY)
            score_threshold: Score minimum pour reCAPTCHA v3
            timeout: Timeout pour la requete de validation
        """
        self.enabled = enabled if enabled is not None else settings.CAPTCHA_ENABLED
        self.provider = CaptchaProvider(provider or settings.CAPTCHA_PROVIDER)
        self.secret_key = secret_key or settings.CAPTCHA_SECRET_KEY
        self.score_threshold = score_threshold or settings.CAPTCHA_SCORE_THRESHOLD
        self.timeout = timeout or settings.CAPTCHA_TIMEOUT

    def is_enabled(self) -> bool:
        """Verifie si le CAPTCHA est active."""
        return self.enabled and bool(self.secret_key)

    async def validate(
        self,
        token: str,
        remote_ip: Optional[str] = None,
        expected_action: Optional[str] = None
    ) -> CaptchaResult:
        """
        Valide un token CAPTCHA.

        Args:
            token: Token CAPTCHA du frontend
            remote_ip: IP du client (optionnel mais recommande)
            expected_action: Action attendue pour reCAPTCHA v3

        Returns:
            CaptchaResult avec le resultat de la validation

        Raises:
            CaptchaValidationError: Si la validation echoue
        """
        if not self.is_enabled():
            # CAPTCHA desactive, on laisse passer
            logger.debug("CAPTCHA disabled, skipping validation")
            return CaptchaResult(success=True, score=1.0)

        if not token:
            raise CaptchaValidationError("Token CAPTCHA manquant")

        try:
            if self.provider == CaptchaProvider.RECAPTCHA:
                return await self._validate_recaptcha(token, remote_ip, expected_action)
            else:
                return await self._validate_hcaptcha(token, remote_ip)
        except httpx.TimeoutException:
            logger.error("CAPTCHA validation timeout")
            # En cas de timeout, on peut choisir de laisser passer ou bloquer
            # Ici on bloque par securite
            raise CaptchaValidationError("Timeout lors de la validation CAPTCHA")
        except httpx.HTTPError as e:
            logger.error(f"CAPTCHA HTTP error: {e}")
            raise CaptchaValidationError("Erreur de communication avec le service CAPTCHA")

    async def _validate_recaptcha(
        self,
        token: str,
        remote_ip: Optional[str],
        expected_action: Optional[str]
    ) -> CaptchaResult:
        """Valide un token reCAPTCHA v3."""
        data = {
            "secret": self.secret_key,
            "response": token,
        }
        if remote_ip:
            data["remoteip"] = remote_ip

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.RECAPTCHA_VERIFY_URL, data=data)
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            logger.warning(f"reCAPTCHA validation failed: {error_codes}")
            raise CaptchaValidationError(
                "Validation reCAPTCHA echouee",
                error_codes=error_codes
            )

        score = result.get("score", 0.0)
        action = result.get("action")

        # Verifier le score (reCAPTCHA v3)
        if score < self.score_threshold:
            logger.warning(f"reCAPTCHA score too low: {score} < {self.score_threshold}")
            raise CaptchaValidationError(
                f"Score CAPTCHA insuffisant ({score:.2f})"
            )

        # Verifier l'action si specifiee
        if expected_action and action != expected_action:
            logger.warning(f"reCAPTCHA action mismatch: {action} != {expected_action}")
            raise CaptchaValidationError(
                f"Action CAPTCHA incorrecte"
            )

        return CaptchaResult(
            success=True,
            score=score,
            action=action,
            hostname=result.get("hostname")
        )

    async def _validate_hcaptcha(
        self,
        token: str,
        remote_ip: Optional[str]
    ) -> CaptchaResult:
        """Valide un token hCaptcha."""
        data = {
            "secret": self.secret_key,
            "response": token,
        }
        if remote_ip:
            data["remoteip"] = remote_ip

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.HCAPTCHA_VERIFY_URL, data=data)
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            error_codes = result.get("error-codes", [])
            logger.warning(f"hCaptcha validation failed: {error_codes}")
            raise CaptchaValidationError(
                "Validation hCaptcha echouee",
                error_codes=error_codes
            )

        return CaptchaResult(
            success=True,
            hostname=result.get("hostname")
        )

    async def validate_or_skip(
        self,
        token: Optional[str],
        remote_ip: Optional[str] = None,
        required: bool = False
    ) -> CaptchaResult:
        """
        Valide un token CAPTCHA si fourni ou requis.

        Methode utilitaire pour les cas ou le CAPTCHA est optionnel
        sauf si le bruteforce protection l'exige.

        Args:
            token: Token CAPTCHA (peut etre None)
            remote_ip: IP du client
            required: Si True, le token est obligatoire

        Returns:
            CaptchaResult

        Raises:
            CaptchaValidationError: Si requis et token invalide/manquant
        """
        if not self.is_enabled():
            return CaptchaResult(success=True, score=1.0)

        if not token:
            if required:
                raise CaptchaValidationError("Token CAPTCHA requis")
            return CaptchaResult(success=True, score=1.0)

        return await self.validate(token, remote_ip)


# Instance globale (singleton)
_captcha_service: Optional[CaptchaService] = None


def get_captcha_service() -> CaptchaService:
    """Retourne l'instance globale du service CAPTCHA."""
    global _captcha_service
    if _captcha_service is None:
        _captcha_service = CaptchaService()
    return _captcha_service
