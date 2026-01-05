"""
Service d'Audit pour MassaCorp.

Ce module fournit le service de gestion des logs d'audit. Il permet de:
- Enregistrer toutes les actions sensibles du systeme
- Rechercher et filtrer les logs d'audit
- Exporter les logs pour conformite RGPD
- Obtenir des statistiques d'activite
- Detecter les comportements suspects (bruteforce, impossible travel)

Le service assure l'isolation multi-tenant stricte et la tracabilite
complete des actions utilisateur.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

from app.repositories.audit_log import AuditLogRepository
from app.services.exceptions import (
    ServiceException,
    InvalidDateRangeError,
    DateRangeTooLargeError
)

logger = logging.getLogger(__name__)

# Actions considerees comme sensibles (securite)
SENSITIVE_ACTIONS: Set[str] = {
    # Echecs de login
    "user.login_failed",
    "auth.login_failed",
    "login.failed",
    # Changements de mot de passe
    "password.change",
    "password.reset",
    "user.password_change",
    # Suppressions d'utilisateur
    "user.delete",
    "user.deleted",
    # Changements de permissions
    "permission.change",
    "role.change",
    "user.role_change",
    "user.permission_change",
    # MFA
    "mfa.disable",
    "mfa.recovery_used",
    # Sessions
    "session.invalidate_all",
}


class AuditService:
    """
    Service pour la gestion des logs d'audit.

    Fournit une interface haut niveau pour l'enregistrement et la recherche
    des actions d'audit avec isolation multi-tenant.
    """

    # Configuration
    MAX_DATE_RANGE_DAYS = 90  # Plage de dates max pour les recherches
    BRUTEFORCE_THRESHOLD = 5  # Nombre d'echecs pour detecter bruteforce
    BRUTEFORCE_WINDOW_MINUTES = 15  # Fenetre de temps pour bruteforce

    def __init__(self, audit_repository: AuditLogRepository):
        """
        Initialise le service avec le repository d'audit.

        Args:
            audit_repository: Repository pour les logs d'audit
        """
        self.audit_repository = audit_repository

    def _is_sensitive_action(self, action: str) -> bool:
        """
        Determine si une action est sensible.

        Args:
            action: Type d'action

        Returns:
            True si l'action est sensible
        """
        return action in SENSITIVE_ACTIONS

    def log_action(
        self,
        user_id: int,
        tenant_id: int,
        action: str,
        resource: Optional[str] = None,
        resource_type: Optional[str] = None,  # DEPRECATED - utiliser 'resource'
        resource_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        session_id: Optional[str] = None
    ) -> Any:
        """
        Enregistre une action d'audit.

        Cette methode est le point central pour tout enregistrement d'audit.
        Elle normalise les donnees et les stocke via le repository.

        Args:
            user_id: ID de l'utilisateur effectuant l'action
            tenant_id: ID du tenant concerne
            action: Type d'action (ex: "user.login", "password.change")
            resource: Type de ressource affectee (ex: "user", "session")
            resource_type: DEPRECATED - Utiliser 'resource' a la place
            resource_id: ID de la ressource (optionnel)
            details: Donnees supplementaires en JSON
            ip_address: Adresse IP de l'origine
            user_agent: User-Agent du client
            success: True si l'action a reussi
            session_id: ID de la session active

        Returns:
            Le log d'audit cree

        Raises:
            Exception: Re-raised apres logging CRITICAL si echec
        """
        # Gestion des parametres resource et resource_type
        # resource_type est DEPRECATED mais supporte pour compatibilite
        if resource_type is not None:
            if resource is None:
                # Cas normal: utilisation du parametre deprecated
                logger.warning(
                    "Le parametre 'resource_type' est deprecated, "
                    "utilisez 'resource' a la place"
                )
                resource_value = resource_type
            elif resource != resource_type:
                # CONFLIT: Les deux parametres fournis avec des valeurs differentes
                # Priorite a 'resource' mais log l'incohérence
                logger.error(
                    f"CONFLIT: resource='{resource}' et resource_type='{resource_type}' "
                    f"fournis avec des valeurs differentes. Utilisation de resource='{resource}'"
                )
                resource_value = resource
            else:
                # Les deux ont la meme valeur - pas de conflit
                resource_value = resource
        else:
            resource_value = resource

        # Construire les details enrichis
        enriched_details = details.copy() if details else {}
        if resource_value:
            enriched_details["resource"] = resource_value
        if resource_id:
            enriched_details["resource_id"] = resource_id

        # Determiner si l'action est sensible
        is_sensitive = self._is_sensitive_action(action)

        # Creer l'entree d'audit via le repository
        log_data = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "details": enriched_details if enriched_details else None,
            "session_id": session_id,
            "is_sensitive": is_sensitive,
        }

        try:
            return self.audit_repository.create(log_data)
        except Exception as e:
            # Echec d'audit est CRITIQUE - ne JAMAIS ignorer silencieusement
            logger.critical(
                f"ECHEC CRITIQUE: Impossible d'enregistrer l'audit! "
                f"action={action}, user_id={user_id}, tenant_id={tenant_id}, "
                f"error={str(e)}"
            )
            # Re-raise pour que l'appelant soit conscient de l'echec
            raise

    def get_user_audit_trail(
        self,
        user_id: int,
        tenant_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> List[Any]:
        """
        Recupere l'historique d'audit d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (pour isolation)
            skip: Offset pour pagination
            limit: Nombre max de resultats

        Returns:
            Liste des logs d'audit de l'utilisateur
        """
        return self.audit_repository.get_by_user(
            user_id=user_id,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )

    def get_tenant_audit_trail(
        self,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """
        Recupere l'historique d'audit d'un tenant.

        Args:
            tenant_id: ID du tenant
            start_date: Date de debut (optionnel)
            end_date: Date de fin (optionnel)
            skip: Offset pour pagination
            limit: Nombre max de resultats

        Returns:
            Liste des logs d'audit du tenant

        Raises:
            InvalidDateRangeError: Si start_date > end_date
            DateRangeTooLargeError: Si la plage depasse MAX_DATE_RANGE_DAYS
        """
        # Validation des dates
        if start_date and end_date:
            if start_date > end_date:
                raise InvalidDateRangeError(
                    "start_date doit etre anterieure a end_date"
                )
            date_range = (end_date - start_date).days
            if date_range > self.MAX_DATE_RANGE_DAYS:
                raise DateRangeTooLargeError(
                    f"La plage de dates ne peut pas depasser {self.MAX_DATE_RANGE_DAYS} jours"
                )

        return self.audit_repository.get_by_tenant(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )

    def search_audit_logs(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        actions: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """
        Recherche avancee dans les logs d'audit.

        Permet de combiner plusieurs filtres pour des analyses de securite.

        Args:
            tenant_id: ID du tenant (obligatoire)
            user_id: Filtrer par utilisateur
            actions: Liste des types d'actions
            start_date: Date de debut
            end_date: Date de fin
            resource_type: Type de ressource
            ip_address: Filtrer par adresse IP
            skip: Offset pagination
            limit: Limite resultats

        Returns:
            Liste des logs correspondants
        """
        return self.audit_repository.search(
            tenant_id=tenant_id,
            user_id=user_id,
            actions=actions,
            start_date=start_date,
            end_date=end_date,
            resource_type=resource_type,
            ip_address=ip_address,
            skip=skip,
            limit=limit
        )

    def delete_old_logs(self, days: int = 365, tenant_id: Optional[int] = None) -> int:
        """
        Supprime les logs d'audit anciens.

        Note: Cette operation doit etre utilisee avec precaution car
        les logs d'audit ont souvent une retention legale obligatoire.

        Args:
            days: Age minimum en jours pour suppression
            tenant_id: Limiter a un tenant (optionnel)

        Returns:
            Nombre de logs supprimes
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        return self.audit_repository.delete_older_than(
            cutoff_date=cutoff,
            tenant_id=tenant_id
        )

    def export_audit_logs(
        self,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json"
    ) -> List[Dict[str, Any]]:
        """
        Exporte les logs d'audit pour conformite.

        Utile pour les demandes RGPD ou les audits de securite.

        WARNING: Le caller doit valider que l'utilisateur a bien acces
        au tenant_id specifie avant d'appeler cette methode. Cette methode
        ne fait pas de verification d'autorisation.

        Args:
            tenant_id: ID du tenant (caller must verify access)
            start_date: Date de debut
            end_date: Date de fin
            format: Format d'export ("json" ou "csv")

        Returns:
            Liste des logs au format demande
        """
        logs = self.search_audit_logs(
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Limite haute pour export
        )

        # Convertir en dictionnaires avec gestion d'erreur explicite
        result = []
        for i, log in enumerate(logs):
            if hasattr(log, 'to_dict'):
                result.append(log.to_dict())
            else:
                # Ne pas retourner un dict vide silencieusement - log l'erreur
                logger.warning(
                    f"Audit log #{i} sans methode to_dict(): type={type(log).__name__}. "
                    "Export incomplet possible."
                )
                # Inclure les infos minimales disponibles au lieu d'un dict vide
                result.append({
                    "_export_error": "to_dict() non disponible",
                    "_type": type(log).__name__,
                    "_repr": repr(log)[:200]  # Limite pour eviter explosion
                })
        return result

    def get_action_stats(
        self,
        tenant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Obtient les statistiques par type d'action.

        Utile pour les tableaux de bord de securite.

        Args:
            tenant_id: ID du tenant
            start_date: Date de debut (optionnel)
            end_date: Date de fin (optionnel)

        Returns:
            Dict {action: count}
        """
        return self.audit_repository.count_by_action(tenant_id=tenant_id)

    # --- Methodes de securite avancee ---

    def detect_brute_force_by_ip(
        self,
        tenant_id: int,
        ip_address: str,
        window_minutes: Optional[int] = None,
        threshold: Optional[int] = None
    ) -> bool:
        """
        Detecte les tentatives de brute force par IP.

        Args:
            tenant_id: ID du tenant
            ip_address: Adresse IP a analyser
            window_minutes: Fenetre de temps (defaut: BRUTEFORCE_WINDOW_MINUTES)
            threshold: Seuil de detection (defaut: BRUTEFORCE_THRESHOLD)

        Returns:
            True si brute force detecte
        """
        window = window_minutes or self.BRUTEFORCE_WINDOW_MINUTES
        limit = threshold or self.BRUTEFORCE_THRESHOLD

        start_date = datetime.now(timezone.utc) - timedelta(minutes=window)

        failed_attempts = self.search_audit_logs(
            tenant_id=tenant_id,
            actions=["user.login_failed", "auth.login_failed", "login.failed"],
            ip_address=ip_address,
            start_date=start_date,
            limit=limit + 1
        )

        return len(failed_attempts) >= limit

    def detect_brute_force_by_user(
        self,
        tenant_id: int,
        user_id: int,
        window_minutes: Optional[int] = None,
        threshold: Optional[int] = None
    ) -> bool:
        """
        Detecte les tentatives de brute force par utilisateur.

        Args:
            tenant_id: ID du tenant
            user_id: ID de l'utilisateur cible
            window_minutes: Fenetre de temps (defaut: BRUTEFORCE_WINDOW_MINUTES)
            threshold: Seuil de detection (defaut: BRUTEFORCE_THRESHOLD)

        Returns:
            True si brute force detecte
        """
        window = window_minutes or self.BRUTEFORCE_WINDOW_MINUTES
        limit = threshold or self.BRUTEFORCE_THRESHOLD

        start_date = datetime.now(timezone.utc) - timedelta(minutes=window)

        failed_attempts = self.search_audit_logs(
            tenant_id=tenant_id,
            user_id=user_id,
            actions=["user.login_failed", "auth.login_failed", "login.failed"],
            start_date=start_date,
            limit=limit + 1
        )

        return len(failed_attempts) >= limit

    def detect_impossible_travel(
        self,
        tenant_id: int,
        user_id: int,
        current_ip: str,
        max_speed_kmh: int = 1000
    ) -> bool:
        """
        Detecte les connexions depuis des lieux geographiquement impossibles.

        Analyse les logs recents pour detecter si l'utilisateur s'est
        connecte depuis des lieux trop eloignes en un temps trop court.

        Args:
            tenant_id: ID du tenant
            user_id: ID de l'utilisateur
            current_ip: IP actuelle de connexion
            max_speed_kmh: Vitesse max realiste (defaut: 1000 km/h = avion)

        Returns:
            True si voyage impossible detecte
        """
        # Rechercher les connexions recentes (derniere heure)
        start_date = datetime.now(timezone.utc) - timedelta(hours=1)

        recent_logins = self.search_audit_logs(
            tenant_id=tenant_id,
            user_id=user_id,
            actions=["user.login", "auth.login"],
            start_date=start_date,
            limit=10
        )

        if len(recent_logins) < 2:
            return False

        # Pour une implementation complete, on aurait besoin de geolocalisation
        # Ici on detecte simplement si l'IP a change dans un court laps de temps
        ips = set()
        for log in recent_logins:
            if hasattr(log, 'ip_address') and log.ip_address:
                ips.add(log.ip_address)

        # Si plus de 2 IPs differentes en 1h, c'est suspect
        return len(ips) > 2

    def get_suspicious_ips(
        self,
        tenant_id: int,
        min_failures: Optional[int] = None,
        window_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Identifie les IPs suspectes (beaucoup d'echecs de login).

        Args:
            tenant_id: ID du tenant
            min_failures: Nombre min d'echecs (defaut: BRUTEFORCE_THRESHOLD)
            window_hours: Fenetre de temps en heures

        Returns:
            Liste de dicts {ip, failure_count, first_seen, last_seen}
        """
        threshold = min_failures or self.BRUTEFORCE_THRESHOLD
        start_date = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        failed_attempts = self.search_audit_logs(
            tenant_id=tenant_id,
            actions=["user.login_failed", "auth.login_failed", "login.failed"],
            start_date=start_date,
            limit=1000
        )

        # Agreger par IP
        ip_stats: Dict[str, Dict[str, Any]] = {}
        for log in failed_attempts:
            ip = getattr(log, 'ip_address', None)
            if not ip:
                continue

            if ip not in ip_stats:
                ip_stats[ip] = {
                    "ip": ip,
                    "failure_count": 0,
                    "first_seen": getattr(log, 'created_at', None),
                    "last_seen": getattr(log, 'created_at', None),
                }

            ip_stats[ip]["failure_count"] += 1
            created_at = getattr(log, 'created_at', None)
            if created_at:
                if ip_stats[ip]["first_seen"] is None or created_at < ip_stats[ip]["first_seen"]:
                    ip_stats[ip]["first_seen"] = created_at
                if ip_stats[ip]["last_seen"] is None or created_at > ip_stats[ip]["last_seen"]:
                    ip_stats[ip]["last_seen"] = created_at

        # Filtrer par seuil
        suspicious = [
            stats for stats in ip_stats.values()
            if stats["failure_count"] >= threshold
        ]

        # Trier par nombre d'echecs
        return sorted(suspicious, key=lambda x: x["failure_count"], reverse=True)
