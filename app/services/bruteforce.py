"""
Service de protection anti-bruteforce avec escalade progressive.

Niveaux d'escalade:
1. NONE (< 3 echecs) - Pas d'action
2. CAPTCHA (3-4 echecs) - Requiert verification CAPTCHA
3. DELAY (5-9 echecs) - Delai progressif avant reponse
4. LOCK (10-14 echecs) - Compte temporairement verrouille
5. ALERT (>= 15 echecs) - Alerte envoyee aux admins

La fenetre de comptage est de 15 minutes.
"""
import math
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class EscalationLevel(Enum):
    """Niveaux d'escalade anti-bruteforce."""
    NONE = "none"
    CAPTCHA = "captcha"
    DELAY = "delay"
    LOCK = "lock"
    ALERT = "alert"


# =============================================================================
# Protocol pour le repository
# =============================================================================


class LoginAttemptRepositoryProtocol(Protocol):
    """Interface pour le repository des tentatives de login."""

    async def count_failed_attempts(
        self,
        identifier: str,
        ip: Optional[str],
        window_minutes: int
    ) -> int:
        """Compte les tentatives echouees dans la fenetre."""
        ...

    async def record_attempt(
        self,
        identifier: str,
        ip: str,
        success: bool,
        tenant_id: Optional[int]
    ) -> None:
        """Enregistre une tentative."""
        ...


# =============================================================================
# Service
# =============================================================================


class BruteforceProtection:
    """
    Service de protection anti-bruteforce.

    Implemente une escalade progressive:
    - CAPTCHA apres N echecs
    - Delai progressif apres M echecs
    - Verrouillage temporaire apres P echecs
    - Alerte admin apres Q echecs
    """

    # Seuils d'escalade (configurables)
    CAPTCHA_THRESHOLD = 3    # Requiert CAPTCHA apres 3 echecs
    DELAY_THRESHOLD = 5      # Ajoute delai apres 5 echecs
    LOCK_THRESHOLD = 10      # Verrouille apres 10 echecs
    ALERT_THRESHOLD = 15     # Alerte apres 15 echecs

    # Configuration
    WINDOW_MINUTES = 15      # Fenetre de comptage
    MAX_DELAY_SECONDS = 30   # Delai maximum
    LOCK_DURATION_MINUTES = 15  # Duree du verrouillage

    def __init__(self, repository: Optional[LoginAttemptRepositoryProtocol] = None):
        """
        Initialise le service.

        Args:
            repository: Repository pour les tentatives (optionnel pour tests)
        """
        self.repo = repository

    async def get_escalation_level(
        self,
        identifier: str,
        ip: Optional[str] = None
    ) -> EscalationLevel:
        """
        Determine le niveau d'escalade pour un identifier/IP.

        Args:
            identifier: Email ou username
            ip: Adresse IP (optionnel)

        Returns:
            Niveau d'escalade actuel
        """
        if not self.repo:
            return EscalationLevel.NONE

        # Compter les tentatives echouees
        failed_count = await self.repo.count_failed_attempts(
            identifier=identifier,
            ip=ip,
            window_minutes=self.WINDOW_MINUTES
        )

        return self._determine_level(failed_count)

    def _determine_level(self, failed_count: int) -> EscalationLevel:
        """
        Determine le niveau selon le nombre d'echecs.

        Args:
            failed_count: Nombre de tentatives echouees

        Returns:
            Niveau d'escalade
        """
        if failed_count >= self.ALERT_THRESHOLD:
            return EscalationLevel.ALERT
        elif failed_count >= self.LOCK_THRESHOLD:
            return EscalationLevel.LOCK
        elif failed_count >= self.DELAY_THRESHOLD:
            return EscalationLevel.DELAY
        elif failed_count >= self.CAPTCHA_THRESHOLD:
            return EscalationLevel.CAPTCHA
        else:
            return EscalationLevel.NONE

    def calculate_delay(self, failed_count: int) -> float:
        """
        Calcule le delai a appliquer selon le nombre d'echecs.

        Formule: delay = min(2^(n-DELAY_THRESHOLD), MAX_DELAY)
        Ex: 5 echecs -> 1s, 6 -> 2s, 7 -> 4s, 8 -> 8s, etc.

        Args:
            failed_count: Nombre de tentatives echouees

        Returns:
            Delai en secondes
        """
        if failed_count < self.DELAY_THRESHOLD:
            return 0.0

        exponent = failed_count - self.DELAY_THRESHOLD
        delay = min(math.pow(2, exponent), self.MAX_DELAY_SECONDS)
        return delay

    async def check_and_enforce(
        self,
        identifier: str,
        ip: Optional[str] = None
    ) -> dict:
        """
        Verifie le niveau d'escalade et retourne les actions requises.

        Args:
            identifier: Email ou username
            ip: Adresse IP

        Returns:
            Dict avec les actions requises:
            - level: Niveau actuel
            - captcha_required: True si CAPTCHA necessaire
            - delay_seconds: Delai a appliquer
            - locked: True si compte verrouille
            - alert_sent: True si alerte envoyee
        """
        level = await self.get_escalation_level(identifier, ip)

        result = {
            "level": level,
            "captcha_required": False,
            "delay_seconds": 0.0,
            "locked": False,
            "alert_sent": False,
        }

        if not self.repo:
            return result

        failed_count = await self.repo.count_failed_attempts(
            identifier=identifier,
            ip=ip,
            window_minutes=self.WINDOW_MINUTES
        )

        if level == EscalationLevel.CAPTCHA:
            result["captcha_required"] = True

        elif level == EscalationLevel.DELAY:
            result["captcha_required"] = True
            result["delay_seconds"] = self.calculate_delay(failed_count)

        elif level == EscalationLevel.LOCK:
            result["captcha_required"] = True
            result["locked"] = True
            result["delay_seconds"] = self.MAX_DELAY_SECONDS

        elif level == EscalationLevel.ALERT:
            result["captcha_required"] = True
            result["locked"] = True
            result["delay_seconds"] = self.MAX_DELAY_SECONDS
            result["alert_sent"] = True
            # Envoyer alerte via le service d'alertes
            await self._send_bruteforce_alert(identifier, ip, failed_count)

        return result

    async def _send_bruteforce_alert(
        self,
        identifier: str,
        ip: Optional[str],
        failed_count: int
    ) -> None:
        """
        Envoie une alerte pour attaque bruteforce.

        Args:
            identifier: Email ou username cible
            ip: Adresse IP source
            failed_count: Nombre de tentatives echouees
        """
        try:
            from app.services.alerts import get_alert_service
            alert_service = get_alert_service()
            await alert_service.bruteforce_alert(identifier, ip, failed_count)
        except Exception as e:
            # Ne pas bloquer l'authentification si l'alerte echoue
            logger.error(f"Failed to send bruteforce alert: {e}")
            # Log critique en fallback
            logger.critical(
                f"Brute force attack detected: {failed_count} failed attempts "
                f"for {identifier} from {ip}"
            )

    async def record_failed_attempt(
        self,
        identifier: str,
        ip: str,
        tenant_id: Optional[int] = None
    ) -> None:
        """
        Enregistre une tentative echouee.

        Args:
            identifier: Email ou username
            ip: Adresse IP
            tenant_id: ID du tenant (optionnel)
        """
        if self.repo:
            await self.repo.record_attempt(
                identifier=identifier,
                ip=ip,
                success=False,
                tenant_id=tenant_id
            )

    async def record_successful_attempt(
        self,
        identifier: str,
        ip: str,
        tenant_id: Optional[int] = None
    ) -> None:
        """
        Enregistre une tentative reussie.

        Args:
            identifier: Email ou username
            ip: Adresse IP
            tenant_id: ID du tenant (optionnel)
        """
        if self.repo:
            await self.repo.record_attempt(
                identifier=identifier,
                ip=ip,
                success=True,
                tenant_id=tenant_id
            )

    def is_locked(self, level: EscalationLevel) -> bool:
        """
        Verifie si le niveau implique un verrouillage.

        Args:
            level: Niveau d'escalade

        Returns:
            True si verrouille
        """
        return level in (EscalationLevel.LOCK, EscalationLevel.ALERT)

    def requires_captcha(self, level: EscalationLevel) -> bool:
        """
        Verifie si le niveau requiert un CAPTCHA.

        Args:
            level: Niveau d'escalade

        Returns:
            True si CAPTCHA requis
        """
        return level != EscalationLevel.NONE
