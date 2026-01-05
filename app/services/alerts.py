"""
Service d'alertes pour les evenements critiques de securite.

Supporte plusieurs canaux de notification:
- Logs (toujours actif)
- Webhook (Slack, Discord, custom)
- Email (via SMTP) - pour alertes admin ET notifications utilisateur

Configuration via variables d'environnement:
- ALERT_WEBHOOK_URL: URL du webhook (Slack, Discord, etc.)
- ALERT_EMAIL_ENABLED: Activer les alertes email admin
- ALERT_EMAIL_RECIPIENTS: Emails admin (comma-separated)
- SMTP_*: Configuration SMTP (voir email.py)
"""
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import os

import httpx

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Niveaux de severite des alertes."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertService:
    """
    Service centralisé pour l'envoi d'alertes de securite.

    Toutes les alertes sont loguees. Les alertes critiques
    sont aussi envoyees aux canaux configures (webhook, email).
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        email_enabled: bool = False,
        email_recipients: Optional[str] = None,
    ):
        """
        Initialise le service d'alertes.

        Args:
            webhook_url: URL du webhook (Slack, Discord, etc.)
            email_enabled: Activer les alertes email admin
            email_recipients: Emails admin (comma-separated)
        """
        self.webhook_url = webhook_url or os.getenv("ALERT_WEBHOOK_URL")
        self.email_enabled = email_enabled or os.getenv("ALERT_EMAIL_ENABLED", "").lower() == "true"
        recipients = email_recipients or os.getenv("ALERT_EMAIL_RECIPIENTS", "")
        self.email_recipients = [e.strip() for e in recipients.split(",") if e.strip()]

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        context: Optional[dict] = None
    ) -> bool:
        """
        Envoie une alerte via tous les canaux configures.

        Args:
            title: Titre court de l'alerte
            message: Message detaille
            severity: Niveau de severite
            context: Donnees contextuelles additionnelles

        Returns:
            True si au moins un canal a reussi
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Toujours logger
        log_message = f"[{severity.value.upper()}] {title}: {message}"
        if context:
            log_message += f" | Context: {context}"

        if severity == AlertSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == AlertSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        success = True

        # Webhook (Slack-compatible format)
        if self.webhook_url and severity == AlertSeverity.CRITICAL:
            try:
                await self._send_webhook(title, message, severity, timestamp, context)
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")
                success = False

        # Email to admin recipients
        if self.email_enabled and self.email_recipients and severity == AlertSeverity.CRITICAL:
            try:
                await self._send_admin_email(title, message, severity, timestamp, context)
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")
                success = False

        return success

    async def _send_admin_email(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        timestamp: str,
        context: Optional[dict]
    ) -> None:
        """Envoie une alerte par email aux admins."""
        from app.services.email import get_email_service, EmailMessage

        email_service = get_email_service()

        # Construire le body
        body_parts = [
            f"Security Alert: {title}",
            f"Severity: {severity.value.upper()}",
            f"Time: {timestamp}",
            "",
            message,
        ]

        if context:
            body_parts.append("")
            body_parts.append("Context:")
            for key, value in context.items():
                body_parts.append(f"  - {key}: {value}")

        body_text = "\n".join(body_parts)

        # Envoyer a chaque recipient
        for recipient in self.email_recipients:
            email = EmailMessage(
                to=recipient,
                subject=f"[CRITICAL] {title}",
                body_text=body_text,
            )
            await email_service.send(email)

    async def _send_webhook(
        self,
        title: str,
        message: str,
        severity: AlertSeverity,
        timestamp: str,
        context: Optional[dict]
    ) -> None:
        """Envoie une alerte via webhook (format Slack-compatible)."""
        # Format compatible Slack/Discord
        color = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9800",
            AlertSeverity.CRITICAL: "#ff0000"
        }.get(severity, "#808080")

        payload = {
            "attachments": [{
                "color": color,
                "title": f":warning: {title}" if severity == AlertSeverity.CRITICAL else title,
                "text": message,
                "fields": [
                    {"title": "Severity", "value": severity.value.upper(), "short": True},
                    {"title": "Timestamp", "value": timestamp, "short": True}
                ],
                "footer": "MassaCorp Security Alert"
            }]
        }

        if context:
            for key, value in context.items():
                payload["attachments"][0]["fields"].append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value),
                    "short": True
                })

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.webhook_url, json=payload)
            response.raise_for_status()

    async def bruteforce_alert(
        self,
        identifier: str,
        ip: Optional[str],
        failed_count: int
    ) -> bool:
        """
        Alerte specifique pour attaque bruteforce detectee.

        Args:
            identifier: Email ou username cible
            ip: Adresse IP source
            failed_count: Nombre de tentatives echouees
        """
        return await self.send_alert(
            title="Brute Force Attack Detected",
            message=f"{failed_count} failed login attempts detected for {identifier}",
            severity=AlertSeverity.CRITICAL,
            context={
                "identifier": identifier,
                "source_ip": ip or "unknown",
                "failed_attempts": failed_count,
                "action": "Account locked"
            }
        )

    async def notify_user_bruteforce(
        self,
        user_email: str,
        failed_attempts: int,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Notifie l'utilisateur de tentatives de connexion suspectes.

        Args:
            user_email: Email de l'utilisateur
            failed_attempts: Nombre de tentatives echouees
            ip_address: IP source

        Returns:
            True si notification envoyee
        """
        try:
            from app.services.email import get_email_service
            email_service = get_email_service()
            return await email_service.send_bruteforce_notification(
                to=user_email,
                failed_attempts=failed_attempts,
                ip_address=ip_address,
            )
        except Exception as e:
            logger.error(f"Failed to notify user of bruteforce: {e}")
            return False

    async def notify_user_recovery_code_used(
        self,
        user_email: str,
        codes_remaining: int,
    ) -> bool:
        """
        Notifie l'utilisateur qu'un code de recuperation a ete utilise.

        Args:
            user_email: Email de l'utilisateur
            codes_remaining: Nombre de codes restants

        Returns:
            True si notification envoyee
        """
        try:
            from app.services.email import get_email_service
            email_service = get_email_service()
            return await email_service.send_recovery_code_used(
                to=user_email,
                codes_remaining=codes_remaining,
            )
        except Exception as e:
            logger.error(f"Failed to notify user of recovery code use: {e}")
            return False

    async def notify_user_mfa_disabled(self, user_email: str) -> bool:
        """
        Notifie l'utilisateur que MFA a ete desactive.

        Args:
            user_email: Email de l'utilisateur

        Returns:
            True si notification envoyee
        """
        try:
            from app.services.email import get_email_service
            email_service = get_email_service()
            return await email_service.send_mfa_disabled(to=user_email)
        except Exception as e:
            logger.error(f"Failed to notify user of MFA disable: {e}")
            return False


# Instance globale (singleton pattern)
_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Retourne l'instance globale du service d'alertes."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
