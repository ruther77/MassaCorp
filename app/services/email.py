"""
Service d'envoi d'emails via SMTP.

Supporte:
- SMTP standard (TLS/SSL)
- Templates HTML
- Mode test (log only)

Configuration via variables d'environnement:
- SMTP_ENABLED: Activer l'envoi d'emails
- SMTP_HOST: Serveur SMTP
- SMTP_PORT: Port SMTP (587 TLS, 465 SSL, 25 plain)
- SMTP_USER: Utilisateur SMTP
- SMTP_PASSWORD: Mot de passe SMTP
- SMTP_USE_TLS: Utiliser STARTTLS
- SMTP_USE_SSL: Utiliser SSL direct
- SMTP_FROM_EMAIL: Adresse expediteur
- SMTP_FROM_NAME: Nom expediteur
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from dataclasses import dataclass
from app.core.logging import mask_email

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Representation d'un email."""
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None


class EmailService:
    """
    Service d'envoi d'emails via SMTP.

    En mode desactive (SMTP_ENABLED=False), les emails sont logues
    mais pas envoyes (utile pour dev/test).
    """

    def __init__(
        self,
        enabled: bool = False,
        host: str = "localhost",
        port: int = 587,
        user: str = "",
        password: str = "",
        use_tls: bool = True,
        use_ssl: bool = False,
        from_email: str = "noreply@massacorp.com",
        from_name: str = "MassaCorp Security",
        timeout: int = 10,
    ):
        """
        Initialise le service email.

        Args:
            enabled: Activer l'envoi reel
            host: Serveur SMTP
            port: Port SMTP
            user: Utilisateur SMTP (vide si auth non requise)
            password: Mot de passe SMTP
            use_tls: Utiliser STARTTLS (port 587)
            use_ssl: Utiliser SSL direct (port 465)
            from_email: Adresse expediteur
            from_name: Nom expediteur
            timeout: Timeout connexion en secondes
        """
        self.enabled = enabled
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.from_email = from_email
        self.from_name = from_name
        self.timeout = timeout

    def _create_message(self, email: EmailMessage) -> MIMEMultipart:
        """Cree le message MIME."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email.subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = email.to

        # Partie texte (fallback)
        msg.attach(MIMEText(email.body_text, "plain", "utf-8"))

        # Partie HTML (si fournie)
        if email.body_html:
            msg.attach(MIMEText(email.body_html, "html", "utf-8"))

        return msg

    async def send(self, email: EmailMessage) -> bool:
        """
        Envoie un email.

        Args:
            email: Message a envoyer

        Returns:
            True si envoye avec succes (ou logue si desactive)
        """
        # En mode desactive, juste logger
        if not self.enabled:
            logger.info(
                f"[EMAIL DISABLED] Would send to {mask_email(email.to)}: {email.subject}"
            )
            logger.debug(f"[EMAIL DISABLED] Body: {email.body_text[:200]}...")
            return True

        try:
            msg = self._create_message(email)

            # Connexion SSL directe (port 465)
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.host, self.port, context=context, timeout=self.timeout
                ) as server:
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            # Connexion avec STARTTLS (port 587)
            elif self.use_tls:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.starttls(context=ssl.create_default_context())
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            # Connexion plain (port 25 - non recommande)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            logger.info(f"Email sent to {mask_email(email.to)}: {email.subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipients refused: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except TimeoutError:
            logger.error(f"SMTP connection timeout to {self.host}:{self.port}")
            return False
        except Exception as e:
            logger.error(f"Unexpected email error: {e}")
            return False

    async def send_security_alert(
        self,
        to: str,
        subject: str,
        message: str,
        action_required: Optional[str] = None,
    ) -> bool:
        """
        Envoie une alerte de securite formatee.

        Args:
            to: Destinataire
            subject: Sujet
            message: Message principal
            action_required: Action recommandee (optionnel)

        Returns:
            True si envoye
        """
        # Template HTML simple
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f8f9fa; }}
        .action {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }}
        .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Security Alert</h1>
        </div>
        <div class="content">
            <p>{message}</p>
            {"<div class='action'><strong>Action Required:</strong> " + action_required + "</div>" if action_required else ""}
        </div>
        <div class="footer">
            <p>This is an automated security notification from MassaCorp.</p>
            <p>If you did not trigger this action, please contact support immediately.</p>
        </div>
    </div>
</body>
</html>
"""

        # Version texte
        text = f"""
SECURITY ALERT
==============

{message}

{"ACTION REQUIRED: " + action_required if action_required else ""}

---
This is an automated security notification from MassaCorp.
If you did not trigger this action, please contact support immediately.
"""

        email = EmailMessage(
            to=to,
            subject=f"[MassaCorp Security] {subject}",
            body_text=text.strip(),
            body_html=html,
        )

        return await self.send(email)

    async def send_bruteforce_notification(
        self,
        to: str,
        failed_attempts: int,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Notifie un utilisateur de tentatives de connexion suspectes.

        Args:
            to: Email de l'utilisateur
            failed_attempts: Nombre de tentatives echouees
            ip_address: IP source (si connue)

        Returns:
            True si envoye
        """
        ip_info = f" from IP {ip_address}" if ip_address else ""
        message = (
            f"We detected {failed_attempts} failed login attempts on your account{ip_info}. "
            f"Your account has been temporarily locked for security."
        )

        return await self.send_security_alert(
            to=to,
            subject="Suspicious Login Activity Detected",
            message=message,
            action_required=(
                "If this was not you, please change your password immediately "
                "and enable two-factor authentication."
            ),
        )

    async def send_recovery_code_used(self, to: str, codes_remaining: int) -> bool:
        """
        Notifie un utilisateur qu'un code de recuperation a ete utilise.

        Args:
            to: Email de l'utilisateur
            codes_remaining: Nombre de codes restants

        Returns:
            True si envoye
        """
        message = (
            f"A recovery code was just used to access your account. "
            f"You have {codes_remaining} recovery codes remaining."
        )

        action = None
        if codes_remaining <= 2:
            action = (
                "You are running low on recovery codes. "
                "Please generate new codes from your account settings."
            )

        return await self.send_security_alert(
            to=to,
            subject="Recovery Code Used",
            message=message,
            action_required=action,
        )

    async def send_mfa_disabled(self, to: str) -> bool:
        """
        Notifie un utilisateur que MFA a ete desactive.

        Args:
            to: Email de l'utilisateur

        Returns:
            True si envoye
        """
        return await self.send_security_alert(
            to=to,
            subject="Two-Factor Authentication Disabled",
            message=(
                "Two-factor authentication has been disabled on your account. "
                "Your account is now less secure."
            ),
            action_required=(
                "If you did not make this change, please secure your account immediately "
                "by changing your password and re-enabling two-factor authentication."
            ),
        )


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Retourne l'instance globale du service email."""
    global _email_service
    if _email_service is None:
        from app.core.config import get_settings
        settings = get_settings()
        _email_service = EmailService(
            enabled=settings.SMTP_ENABLED,
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_USE_TLS,
            use_ssl=settings.SMTP_USE_SSL,
            from_email=settings.SMTP_FROM_EMAIL,
            from_name=settings.SMTP_FROM_NAME,
            timeout=settings.SMTP_TIMEOUT,
        )
    return _email_service
