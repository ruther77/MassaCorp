"""
Repository pour la gestion des tentatives de connexion.

Ce module gere le tracking des tentatives de connexion pour la protection
contre les attaques brute-force et le rate limiting.

Fonctionnalites principales:
- Enregistrement des tentatives (reussies ou echouees)
- Comptage des echecs recents pour detection brute-force
- Verification de l'etat de verrouillage d'un compte
- Nettoyage des anciennes tentatives (conformite RGPD)

Notes de securite:
- Les emails sont normalises en minuscules pour eviter les contournements
- Le verrouillage est isole par tenant pour eviter les attaques cross-tenant
- Les anciennes tentatives sont purgees periodiquement pour limiter le stockage
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import LoginAttempt
from app.repositories.base import BaseRepository


class LoginAttemptRepository(BaseRepository[LoginAttempt]):
    """
    Repository pour les tentatives de connexion.

    Gere le tracking des tentatives pour la protection brute-force
    avec isolation multi-tenant.
    """

    model = LoginAttempt

    def record_attempt(
        self,
        email: str,
        tenant_id: int,
        success: bool,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> LoginAttempt:
        """
        Enregistre une tentative de connexion.

        L'email est normalise en minuscules pour eviter les contournements
        (User@TEST.com vs user@test.com).

        Args:
            email: Email utilise pour la tentative (sera normalise)
            tenant_id: ID du tenant concerne
            success: True si connexion reussie, False sinon
            ip_address: Adresse IP d'origine
            user_agent: User-Agent du client (optionnel)

        Returns:
            LoginAttempt: La tentative enregistree
        """
        # Normaliser l'email en minuscules
        normalized_email = email.lower().strip()

        # Construire l'identifiant unique: email@tenant_id
        # Permet l'isolation multi-tenant des tentatives
        identifier = f"{normalized_email}@tenant:{tenant_id}"

        attempt = LoginAttempt(
            identifier=identifier,
            ip=ip_address,
            success=success,
        )

        self.session.add(attempt)
        self.session.flush()
        return attempt

    def count_recent_failures(
        self,
        email: str,
        tenant_id: int,
        minutes: int = 15
    ) -> int:
        """
        Compte les echecs de connexion recents pour un email/tenant.

        Utilise pour determiner si un compte doit etre verrouille
        apres trop d'echecs.

        Args:
            email: Email a verifier
            tenant_id: ID du tenant
            minutes: Fenetre de temps en minutes (defaut: 15)

        Returns:
            Nombre d'echecs dans la fenetre de temps
        """
        normalized_email = email.lower().strip()
        identifier = f"{normalized_email}@tenant:{tenant_id}"

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.identifier == identifier)
            .filter(self.model.success == False)
            .filter(self.model.attempted_at >= cutoff)
            .scalar()
        )

        return count or 0

    def is_locked_out(
        self,
        email: str,
        tenant_id: int,
        max_attempts: int = 5,
        lockout_minutes: int = 30
    ) -> bool:
        """
        Verifie si un compte est verrouille suite a trop d'echecs.

        Le verrouillage est base sur le nombre d'echecs dans une fenetre
        de temps. Il est isole par tenant.

        Args:
            email: Email a verifier
            tenant_id: ID du tenant
            max_attempts: Nombre maximum d'echecs autorises (defaut: 5)
            lockout_minutes: Duree de la fenetre en minutes (defaut: 30)

        Returns:
            True si le compte est verrouille, False sinon
        """
        failures = self.count_recent_failures(email, tenant_id, lockout_minutes)
        return failures >= max_attempts

    def get_last_successful(
        self,
        email: str,
        tenant_id: int
    ) -> Optional[LoginAttempt]:
        """
        Recupere la derniere connexion reussie pour un email/tenant.

        Utile pour afficher "Derniere connexion: il y a X temps" dans l'UI.

        Args:
            email: Email a rechercher
            tenant_id: ID du tenant

        Returns:
            La derniere tentative reussie ou None
        """
        normalized_email = email.lower().strip()
        identifier = f"{normalized_email}@tenant:{tenant_id}"

        return (
            self.session.query(self.model)
            .filter(self.model.identifier == identifier)
            .filter(self.model.success == True)
            .order_by(self.model.attempted_at.desc())
            .first()
        )

    def cleanup_old_attempts(self, days: int = 90) -> int:
        """
        Supprime les tentatives de connexion anciennes.

        Conformite RGPD: les donnees de connexion ne doivent pas etre
        conservees indefiniment.

        Args:
            days: Age maximum en jours (defaut: 90)

        Returns:
            Nombre d'enregistrements supprimes
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        deleted = (
            self.session.query(self.model)
            .filter(self.model.attempted_at < cutoff)
            .delete(synchronize_session=False)
        )

        return deleted

    def count_recent_failed(
        self,
        email: str,
        window_minutes: int = 30
    ) -> int:
        """
        Compte les echecs de connexion recents pour un email (tous tenants).

        Utilise pour determiner si CAPTCHA est requis suite a plusieurs
        echecs sur un meme email.

        Args:
            email: Email a verifier
            window_minutes: Fenetre de temps en minutes (defaut: 30)

        Returns:
            Nombre d'echecs dans la fenetre de temps
        """
        normalized_email = email.lower().strip()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        # Chercher tous les identifiants contenant cet email (tous tenants)
        count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.identifier.like(f"{normalized_email}@tenant:%"))
            .filter(self.model.success == False)
            .filter(self.model.attempted_at >= cutoff)
            .scalar()
        )

        return count or 0

    def count_recent_failed_by_ip(
        self,
        ip_address: str,
        window_minutes: int = 30
    ) -> int:
        """
        Compte les echecs de connexion recents depuis une IP.

        Utilise pour detecter les attaques brute-force distribuees
        ciblant plusieurs comptes depuis une meme IP.

        Args:
            ip_address: Adresse IP a verifier
            window_minutes: Fenetre de temps en minutes (defaut: 30)

        Returns:
            Nombre d'echecs depuis cette IP dans la fenetre de temps
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        count = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.ip == ip_address)
            .filter(self.model.success == False)
            .filter(self.model.attempted_at >= cutoff)
            .scalar()
        )

        return count or 0
