"""
Repository pour la gestion des logs d'audit.

Ce module fournit les operations CRUD et de recherche pour les logs d'audit.
Les logs d'audit tracent toutes les actions sensibles du systeme (connexions,
modifications, operations administratives, etc.).

Fonctionnalites principales:
- Creation de logs avec tous les champs requis
- Recherche par utilisateur, tenant, action, periode
- Statistiques par type d'action pour tableaux de bord
- Isolation multi-tenant stricte pour toutes les requetes de lecture

Notes de securite:
- Les logs d'audit ne doivent JAMAIS etre supprimes (retention legale)
- Toutes les lectures sont filtrees par tenant_id pour l'isolation
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Repository pour les logs d'audit.

    Gere les operations sur les logs d'audit avec isolation multi-tenant
    et capacites de recherche avancees.
    """

    model = AuditLog

    def create(self, data: Dict[str, Any]) -> AuditLog:
        """
        Cree un nouveau log d'audit.

        Le mapping des champs est effectue pour supporter les noms de champs
        utilises dans l'API (action -> event_type, ip_address -> ip, etc.)

        Args:
            data: Dictionnaire contenant les donnees du log:
                - user_id: ID de l'utilisateur (optionnel)
                - tenant_id: ID du tenant (optionnel)
                - action ou event_type: Type d'action (LOGIN, LOGOUT, etc.)
                - resource_type, resource_id: Type et ID de la ressource (optionnel)
                - ip_address ou ip: Adresse IP de l'origine
                - user_agent: User-Agent du client
                - details ou extra_data: Donnees JSON supplementaires
                - success: Succes de l'action (defaut: True)

        Returns:
            AuditLog: Le log cree
        """
        # Mapping des noms de champs API vers les noms du modele
        mapped_data = {
            "event_type": data.get("action") or data.get("event_type"),
            "user_id": data.get("user_id"),
            "tenant_id": data.get("tenant_id"),
            "session_id": data.get("session_id"),
            "ip": data.get("ip_address") or data.get("ip"),
            "user_agent": data.get("user_agent"),
            "success": data.get("success", True),
        }

        # Gestion des details/extra_data - inclure resource_type/resource_id
        details = data.get("details") or data.get("extra_data") or {}
        if data.get("resource_type"):
            details["resource_type"] = data["resource_type"]
        if data.get("resource_id"):
            details["resource_id"] = data["resource_id"]
        if details:
            mapped_data["extra_data"] = details

        # Creer le log via le parent
        return super().create(mapped_data)

    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[int] = None
    ) -> List[AuditLog]:
        """
        Recupere les logs d'audit pour un utilisateur specifique.

        Args:
            user_id: ID de l'utilisateur
            skip: Nombre d'enregistrements a sauter (pagination)
            limit: Nombre maximum d'enregistrements a retourner
            tenant_id: ID du tenant pour filtrage additionnel (optionnel)

        Returns:
            Liste des logs d'audit tries par date decroissante
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        return (
            query
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Recupere les logs d'audit pour un tenant specifique.

        Garantit l'isolation multi-tenant en filtrant strictement par tenant_id.

        Args:
            tenant_id: ID du tenant
            skip: Nombre d'enregistrements a sauter (pagination)
            limit: Nombre maximum d'enregistrements a retourner

        Returns:
            Liste des logs d'audit tries par date decroissante
        """
        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_action(
        self,
        action: str,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Recupere les logs d'audit par type d'action.

        Permet de filtrer les logs par type d'evenement (LOGIN, LOGOUT,
        PASSWORD_CHANGE, etc.).

        Args:
            action: Type d'action a filtrer (ex: "LOGIN_SUCCESS")
            tenant_id: ID du tenant pour isolation
            skip: Nombre d'enregistrements a sauter
            limit: Nombre maximum d'enregistrements

        Returns:
            Liste des logs d'audit correspondants
        """
        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .filter(self.model.event_type == action)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        tenant_id: int
    ) -> List[AuditLog]:
        """
        Recupere les logs d'audit dans une plage de dates.

        Args:
            start_date: Date de debut (incluse)
            end_date: Date de fin (incluse)
            tenant_id: ID du tenant pour isolation

        Returns:
            Liste des logs d'audit dans la periode
        """
        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .filter(self.model.created_at >= start_date)
            .filter(self.model.created_at <= end_date)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def search(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        actions: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Recherche avancee avec filtres multiples.

        Permet de combiner plusieurs criteres de recherche pour des analyses
        de securite et audits.

        Args:
            tenant_id: ID du tenant (obligatoire pour isolation)
            user_id: ID de l'utilisateur (optionnel)
            actions: Liste des types d'actions a filtrer (optionnel)
            start_date: Date de debut (optionnel)
            end_date: Date de fin (optionnel)
            resource_type: Type de ressource a filtrer (optionnel)
            skip: Offset pour pagination
            limit: Limite de resultats

        Returns:
            Liste des logs correspondant aux criteres
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
        )

        # Filtre optionnel par user_id
        if user_id is not None:
            query = query.filter(self.model.user_id == user_id)

        # Filtre optionnel par actions (liste)
        if actions:
            query = query.filter(self.model.event_type.in_(actions))

        # Filtre optionnel par dates
        if start_date is not None:
            query = query.filter(self.model.created_at >= start_date)
        if end_date is not None:
            query = query.filter(self.model.created_at <= end_date)

        # Filtre par resource_type dans extra_data (JSONB)
        if resource_type is not None:
            query = query.filter(
                self.model.extra_data["resource_type"].astext == resource_type
            )

        return (
            query
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_action(self, tenant_id: int) -> Dict[str, int]:
        """
        Compte le nombre de logs par type d'action pour un tenant.

        Utile pour les tableaux de bord de securite et les statistiques.

        Args:
            tenant_id: ID du tenant

        Returns:
            Dictionnaire {action: count} avec le nombre de logs par action
        """
        results = (
            self.session.query(self.model.event_type, func.count(self.model.id))
            .filter(self.model.tenant_id == tenant_id)
            .group_by(self.model.event_type)
            .all()
        )

        return {action: count for action, count in results}

    def delete_older_than(
        self,
        cutoff_date: datetime,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Supprime les logs d'audit plus anciens que la date specifiee.

        ATTENTION: Cette operation est irreversible. Les logs d'audit
        ont souvent une retention legale obligatoire. Utiliser avec precaution.

        Args:
            cutoff_date: Date limite (les logs anterieurs seront supprimes)
            tenant_id: ID du tenant (optionnel, pour limiter a un tenant)

        Returns:
            Nombre de logs supprimes
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.created_at < cutoff_date)
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        deleted = query.delete(synchronize_session=False)
        return deleted
