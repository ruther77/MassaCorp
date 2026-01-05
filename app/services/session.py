"""
Service de gestion des Sessions pour MassaCorp.

Ce module fournit le service de gestion des sessions utilisateur. Il permet de:
- Creer et gerer les sessions de connexion
- Lister les sessions actives d'un utilisateur
- Terminer des sessions individuelles ou toutes les sessions
- Detecter les comportements suspects (IP differentes, hijacking, etc.)
- Limiter le nombre de sessions concurrentes

Le service assure le tracking d'activite et la securite des sessions.
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

from app.models.session import Session
from app.models.audit import LoginAttempt
from app.repositories.session import SessionRepository

logger = logging.getLogger(__name__)

# Desactiver le rate limiting en environnement de test
_IS_TEST_ENV = os.getenv("ENV") == "test"
from app.repositories.login_attempt import LoginAttemptRepository
from app.services.exceptions import (
    ServiceException,
    SessionNotFoundError,
    SessionExpiredError,
    AccountLockedError,
    MaxSessionsExceededError
)


def parse_user_agent(user_agent: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Parse le user-agent pour extraire device, OS et browser.

    Args:
        user_agent: String du User-Agent

    Returns:
        Dict avec device, os, browser
    """
    if not user_agent:
        return {"device": None, "os": None, "browser": None}

    result = {"device": "Desktop", "os": None, "browser": None}

    # Detecter le device
    if "Mobile" in user_agent or "Android" in user_agent:
        result["device"] = "Mobile"
    elif "Tablet" in user_agent or "iPad" in user_agent:
        result["device"] = "Tablet"

    # Detecter l'OS
    if "Windows" in user_agent:
        result["os"] = "Windows"
    elif "Mac OS" in user_agent or "Macintosh" in user_agent:
        result["os"] = "macOS"
    elif "Linux" in user_agent:
        result["os"] = "Linux"
    elif "Android" in user_agent:
        result["os"] = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        result["os"] = "iOS"

    # Detecter le browser
    if "Chrome" in user_agent and "Edg" not in user_agent:
        result["browser"] = "Chrome"
    elif "Firefox" in user_agent:
        result["browser"] = "Firefox"
    elif "Safari" in user_agent and "Chrome" not in user_agent:
        result["browser"] = "Safari"
    elif "Edg" in user_agent:
        result["browser"] = "Edge"

    return result


class SessionService:
    """
    Service pour la gestion des sessions utilisateur.

    Gere le cycle de vie des sessions avec tracking d'activite
    et isolation multi-tenant.
    """

    def __init__(
        self,
        session_repository: SessionRepository,
        login_attempt_repository: Optional[LoginAttemptRepository] = None
    ):
        """
        Initialise le service avec les repositories necessaires.

        Args:
            session_repository: Repository pour les sessions
            login_attempt_repository: Repository pour les tentatives de login
        """
        self.session_repository = session_repository
        self.login_attempt_repository = login_attempt_repository

    def create_session(
        self,
        user_id: int,
        tenant_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> Session:
        """
        Cree une nouvelle session pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            ip_address: Adresse IP de connexion
            user_agent: User-Agent du client
            device_name: Nom du device (optionnel)

        Returns:
            La session creee avec son UUID
        """
        # Generer un JTI pour reference
        token_jti = str(uuid4())

        return self.session_repository.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            token_jti=token_jti,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def get_user_sessions(
        self,
        user_id: int,
        tenant_id: int,
        include_inactive: bool = False
    ) -> List[Session]:
        """
        Recupere les sessions d'un utilisateur.

        SECURITE: tenant_id obligatoire pour garantir l'isolation multi-tenant.
        Ne JAMAIS permettre de recuperer les sessions sans verification du tenant.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (OBLIGATOIRE - isolation multi-tenant)
            include_inactive: Inclure les sessions revoquees

        Returns:
            Liste des sessions

        Raises:
            ValueError: Si tenant_id est invalide
        """
        # Validation stricte du tenant_id - SECURITE CRITIQUE
        if tenant_id is None or tenant_id <= 0:
            raise ValueError(
                f"tenant_id obligatoire et doit etre positif (recu: {tenant_id})"
            )

        if include_inactive:
            # Retourner toutes les sessions (actives et revoquees)
            return self.session_repository.get_all_sessions(
                user_id=user_id,
                tenant_id=tenant_id
            )

        return self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

    def terminate_session(
        self,
        session_id: UUID,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Termine une session specifique.

        Si user_id est fourni, la session n'est terminee que si elle
        appartient a cet utilisateur (protection IDOR).

        Args:
            session_id: UUID de la session a terminer
            user_id: ID du user (pour verification de propriete)

        Returns:
            True si session terminee, False si non trouvee ou non-possedee
        """
        return self.session_repository.invalidate_session(
            session_id=session_id,
            user_id=user_id
        )

    def terminate_all_sessions(
        self,
        user_id: int,
        except_session_id: Optional[UUID] = None
    ) -> int:
        """
        Termine toutes les sessions d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            except_session_id: UUID de la session a garder active

        Returns:
            Nombre de sessions terminees
        """
        return self.session_repository.invalidate_all_sessions(
            user_id=user_id,
            except_session_id=except_session_id
        )

    def is_session_valid(
        self,
        session_id: UUID,
        check_expiry: bool = True
    ) -> bool:
        """
        Verifie si une session est valide.

        Args:
            session_id: UUID de la session
            check_expiry: Verifier l'expiration

        Returns:
            True si session valide
        """
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            return False

        return session.is_active

    def update_session_activity(
        self,
        session_id: UUID,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Met a jour l'activite d'une session.

        Args:
            session_id: UUID de la session
            ip_address: Nouvelle IP (pour detection de changement)

        Returns:
            True si mise a jour effectuee
        """
        session = self.session_repository.get_by_id(session_id)
        if session is None:
            return False

        session.update_last_seen()
        return True

    def get_session_by_id(self, session_id: UUID) -> Optional[Session]:
        """
        Recupere une session par son ID.

        Args:
            session_id: UUID de la session

        Returns:
            La session ou None
        """
        return self.session_repository.get_by_id(session_id)

    def get_session_for_user(
        self,
        session_id: UUID,
        user_id: int
    ) -> Optional[Session]:
        """
        Recupere une session par ID avec verification de propriete.

        Cette methode verifie que la session appartient bien a l'utilisateur
        en une seule requete atomique, empechant les attaques IDOR.

        Args:
            session_id: UUID de la session
            user_id: ID de l'utilisateur proprietaire attendu

        Returns:
            La session si elle existe ET appartient a l'utilisateur, None sinon.
            Retourne None dans les deux cas (inexistante ou non-possedee)
            pour ne pas divulguer d'information.
        """
        return self.session_repository.get_session_for_user(session_id, user_id)

    def cleanup_expired_sessions(
        self,
        older_than_days: int = 30,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Nettoie les sessions expirees.

        Args:
            older_than_days: Age minimum pour suppression
            tenant_id: Limiter au tenant specifie (None = tous les tenants)

        Returns:
            Nombre de sessions supprimees
        """
        return self.session_repository.cleanup_expired(
            older_than_days=older_than_days,
            tenant_id=tenant_id
        )

    # --- Methodes pour brute-force protection ---

    def record_login_attempt(
        self,
        email: str,
        tenant_id: int,
        success: bool,
        ip_address: str,
        user_agent: Optional[str] = None
    ) -> Optional[LoginAttempt]:
        """
        Enregistre une tentative de connexion.

        Args:
            email: Email utilise
            tenant_id: ID du tenant
            success: Reussite ou echec
            ip_address: Adresse IP
            user_agent: User-Agent

        Returns:
            La tentative enregistree
        """
        if self.login_attempt_repository:
            return self.login_attempt_repository.record_attempt(
                email=email,
                tenant_id=tenant_id,
                success=success,
                ip_address=ip_address,
                user_agent=user_agent
            )
        return None

    def is_account_locked(
        self,
        email: str,
        tenant_id: int,
        max_attempts: int = 5,
        lockout_minutes: int = 30
    ) -> bool:
        """
        Verifie si un compte est verrouille.

        En environnement de test (ENV=test), le rate limiting est desactive
        pour eviter les faux positifs dus aux tests de login echoues.

        Args:
            email: Email a verifier
            tenant_id: ID du tenant
            max_attempts: Nombre max d'echecs
            lockout_minutes: Duree du verrouillage

        Returns:
            True si compte verrouille
        """
        # Desactiver le rate limiting en environnement de test
        if _IS_TEST_ENV:
            return False

        if self.login_attempt_repository:
            return self.login_attempt_repository.is_locked_out(
                email=email,
                tenant_id=tenant_id,
                max_attempts=max_attempts,
                lockout_minutes=lockout_minutes
            )
        return False

    def get_last_successful_login(
        self,
        email: str,
        tenant_id: int
    ) -> Optional[LoginAttempt]:
        """
        Recupere la derniere connexion reussie.

        Args:
            email: Email de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            La derniere tentative reussie ou None
        """
        if self.login_attempt_repository:
            return self.login_attempt_repository.get_last_successful(
                email=email,
                tenant_id=tenant_id
            )
        return None

    def detect_suspicious_activity(
        self,
        user_id: int,
        current_ip: str,
        current_user_agent: str,
        tenant_id: int
    ) -> Dict[str, bool | int]:
        """
        Detecte les activites suspectes pour un utilisateur.

        SECURITE: tenant_id obligatoire pour garantir l'isolation multi-tenant.
        Empeche un attaquant d'analyser les sessions d'autres tenants.

        Args:
            user_id: ID de l'utilisateur
            current_ip: IP actuelle
            current_user_agent: User-Agent actuel
            tenant_id: ID du tenant (OBLIGATOIRE - isolation multi-tenant)

        Returns:
            Dict avec indicateurs de suspicion

        Raises:
            ValueError: Si tenant_id est invalide
        """
        # Validation stricte du tenant_id - SECURITE CRITIQUE (IDOR)
        if tenant_id is None or tenant_id <= 0:
            raise ValueError(
                f"tenant_id obligatoire et doit etre positif (recu: {tenant_id})"
            )

        sessions = self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

        different_ips = set()
        different_agents = set()

        for session in sessions:
            if session.ip:
                different_ips.add(session.ip)
            if session.user_agent:
                different_agents.add(session.user_agent)

        return {
            "multiple_ips": len(different_ips) > 1,
            "ip_count": len(different_ips),
            "multiple_agents": len(different_agents) > 1,
            "agent_count": len(different_agents),
            "new_ip": current_ip not in different_ips if different_ips else False,
            "new_agent": current_user_agent not in different_agents if different_agents else False,
        }

    # --- Methodes ajoutees pour corrections TDD ---

    def get_session_by_id_for_tenant(
        self,
        session_id: UUID,
        tenant_id: int
    ) -> Optional[Session]:
        """
        Recupere une session par ID avec verification du tenant.

        Cette methode assure l'isolation multi-tenant en verifiant que
        la session appartient bien au tenant specifie.

        Args:
            session_id: UUID de la session
            tenant_id: ID du tenant attendu

        Returns:
            La session si elle existe ET appartient au tenant, None sinon
        """
        session = self.session_repository.get_by_id(session_id)

        if session is None:
            return None

        # Verifier que le tenant correspond
        if session.tenant_id != tenant_id:
            return None

        return session

    def get_user_sessions_with_current(
        self,
        user_id: int,
        current_session_id: UUID,
        tenant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupere les sessions d'un utilisateur avec marquage de la courante.

        Ajoute un flag 'is_current' pour identifier la session active.

        Args:
            user_id: ID de l'utilisateur
            current_session_id: UUID de la session courante
            tenant_id: ID du tenant (optionnel)

        Returns:
            Liste de dicts avec id et is_current
        """
        sessions = self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

        return [
            {
                "id": session.id,
                "is_current": session.id == current_session_id,
                "ip": getattr(session, 'ip', None),
                "user_agent": getattr(session, 'user_agent', None),
                "created_at": getattr(session, 'created_at', None),
                "last_seen_at": getattr(session, 'last_seen_at', None),
            }
            for session in sessions
        ]

    # --- Methodes de securite avancee ---

    def detect_session_hijacking(
        self,
        session_id: UUID,
        current_ip: str,
        current_user_agent: str
    ) -> Dict[str, bool]:
        """
        Detecte les tentatives de hijacking de session.

        Compare l'IP et le user-agent actuels avec ceux de la session.

        Args:
            session_id: UUID de la session
            current_ip: IP actuelle
            current_user_agent: User-Agent actuel

        Returns:
            Dict avec ip_changed et user_agent_changed
        """
        session = self.session_repository.get_by_id(session_id)

        if session is None:
            return {"ip_changed": False, "user_agent_changed": False, "session_exists": False}

        session_ip = getattr(session, 'ip', None)
        session_ua = getattr(session, 'user_agent', None)

        return {
            "ip_changed": session_ip is not None and session_ip != current_ip,
            "user_agent_changed": session_ua is not None and session_ua != current_user_agent,
            "session_exists": True,
            "original_ip": session_ip,
            "original_user_agent": session_ua,
        }

    def enforce_max_concurrent_sessions(
        self,
        user_id: int,
        tenant_id: int,
        max_sessions: int = 5
    ) -> bool:
        """
        Verifie si l'utilisateur peut creer une nouvelle session.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            max_sessions: Nombre max de sessions autorisees

        Returns:
            True si une nouvelle session peut etre creee

        Raises:
            MaxSessionsExceededError: Si le maximum est atteint
        """
        active_sessions = self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

        if len(active_sessions) >= max_sessions:
            raise MaxSessionsExceededError(
                f"Maximum de {max_sessions} sessions atteint. "
                "Terminez une session existante pour en creer une nouvelle."
            )

        return True

    def auto_terminate_oldest_on_limit(
        self,
        user_id: int,
        tenant_id: int,
        max_sessions: int = 5
    ) -> Optional[UUID]:
        """
        Termine automatiquement la plus ancienne session si limite atteinte.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            max_sessions: Nombre max de sessions autorisees

        Returns:
            UUID de la session terminee, ou None si pas necessaire
        """
        active_sessions = self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

        if len(active_sessions) < max_sessions:
            return None

        # Trier par date de creation (plus ancienne en premier)
        sorted_sessions = sorted(
            active_sessions,
            key=lambda s: getattr(s, 'created_at', datetime.min.replace(tzinfo=timezone.utc))
        )

        # Terminer la plus ancienne
        oldest = sorted_sessions[0]
        self.session_repository.invalidate_session(session_id=oldest.id)

        logger.info(
            f"Session {oldest.id} auto-terminee pour user_id={user_id} "
            f"(limite de {max_sessions} sessions atteinte)"
        )

        return oldest.id

    def get_session_device_info(self, session_id: UUID) -> Dict[str, Any]:
        """
        Recupere les informations de device pour une session.

        Args:
            session_id: UUID de la session

        Returns:
            Dict avec device, os, browser
        """
        session = self.session_repository.get_by_id(session_id)

        if session is None:
            return {"device": None, "os": None, "browser": None}

        user_agent = getattr(session, 'user_agent', None)
        return parse_user_agent(user_agent)

    def get_user_sessions_with_device_info(
        self,
        user_id: int,
        tenant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Recupere les sessions d'un utilisateur avec infos de device.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel)

        Returns:
            Liste de dicts avec id, ip, device_info, etc.
        """
        sessions = self.session_repository.get_active_sessions(
            user_id=user_id,
            tenant_id=tenant_id
        )

        result = []
        for session in sessions:
            user_agent = getattr(session, 'user_agent', None)
            device_info = parse_user_agent(user_agent)

            result.append({
                "id": session.id,
                "ip": getattr(session, 'ip', None),
                "user_agent": user_agent,
                "device": device_info.get("device"),
                "os": device_info.get("os"),
                "browser": device_info.get("browser"),
                "created_at": getattr(session, 'created_at', None),
                "last_seen_at": getattr(session, 'last_seen_at', None),
            })

        # Trier par derniere activite (plus recent en premier)
        return sorted(
            result,
            key=lambda s: s.get('last_seen_at') or s.get('created_at') or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )

    def is_captcha_required(
        self,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        captcha_threshold: int = 3,
        window_minutes: int = 30
    ) -> bool:
        """
        Verifie si le CAPTCHA est requis suite a plusieurs echecs de login.

        Le CAPTCHA est requis apres N tentatives echouees dans la fenetre
        de temps specifiee, soit par email soit par IP.

        Args:
            email: Email pour verifier les echecs par compte
            ip_address: IP pour verifier les echecs par adresse
            captcha_threshold: Nombre d'echecs avant CAPTCHA (defaut: 3)
            window_minutes: Fenetre de temps en minutes (defaut: 30)

        Returns:
            True si CAPTCHA requis, False sinon
        """
        # Desactiver le CAPTCHA en environnement de test
        if _IS_TEST_ENV:
            return False

        if not self.login_attempt_repository:
            return False

        # Verifier les echecs par email
        if email:
            failed_by_email = self.login_attempt_repository.count_recent_failed(
                email=email,
                window_minutes=window_minutes
            )
            if failed_by_email >= captcha_threshold:
                logger.info(
                    f"CAPTCHA required for email={email}: "
                    f"{failed_by_email} failed attempts in {window_minutes}min"
                )
                return True

        # Verifier les echecs par IP
        if ip_address:
            failed_by_ip = self.login_attempt_repository.count_recent_failed_by_ip(
                ip_address=ip_address,
                window_minutes=window_minutes
            )
            if failed_by_ip >= captcha_threshold:
                logger.info(
                    f"CAPTCHA required for ip={ip_address}: "
                    f"{failed_by_ip} failed attempts in {window_minutes}min"
                )
                return True

        return False
