"""
Repository pour le logging d'utilisation des API Keys.

Ce module gere l'audit et analytics des API Keys:
- Enregistrement de chaque utilisation
- Requetes pour audit et monitoring
- Statistiques d'utilisation
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy import func

from app.models.api_key import APIKeyUsage
from app.repositories.base import BaseRepository


class APIKeyUsageRepository(BaseRepository[APIKeyUsage]):
    """
    Repository pour le logging d'utilisation des API Keys.

    Chaque appel authentifie par API Key est enregistre pour:
    - Audit de securite
    - Detection d'anomalies
    - Rate limiting
    - Analytics
    """

    model = APIKeyUsage

    def log_usage(
        self,
        api_key_id: int,
        tenant_id: int,
        endpoint: str,
        method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_status: Optional[int] = None,
        response_time_ms: Optional[int] = None
    ) -> APIKeyUsage:
        """
        Enregistre une utilisation d'API Key.

        Args:
            api_key_id: ID de l'API Key utilisee
            tenant_id: ID du tenant
            endpoint: Endpoint appele (ex: "/api/v1/users")
            method: Methode HTTP (GET, POST, etc.)
            ip_address: IP source
            user_agent: User-Agent du client
            response_status: Code HTTP de reponse
            response_time_ms: Temps de reponse en millisecondes

        Returns:
            L'objet APIKeyUsage cree
        """
        usage = APIKeyUsage(
            api_key_id=api_key_id,
            tenant_id=tenant_id,
            endpoint=endpoint,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            response_status=response_status,
            response_time_ms=response_time_ms
        )

        self.session.add(usage)
        self.session.flush()

        return usage

    def get_usage_by_key(
        self,
        api_key_id: int,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[APIKeyUsage]:
        """
        Recupere l'historique d'utilisation d'une API Key.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut (defaut: 24h)
            limit: Nombre max d'entrees

        Returns:
            Liste des utilisations
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        return (
            self.session.query(self.model)
            .filter(self.model.api_key_id == api_key_id)
            .filter(self.model.used_at >= since)
            .order_by(self.model.used_at.desc())
            .limit(limit)
            .all()
        )

    def count_usage_by_key(
        self,
        api_key_id: int,
        since: Optional[datetime] = None
    ) -> int:
        """
        Compte les utilisations d'une API Key.

        Utile pour le rate limiting.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut (defaut: 1h)

        Returns:
            Nombre d'utilisations
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        return (
            self.session.query(func.count(self.model.id))
            .filter(self.model.api_key_id == api_key_id)
            .filter(self.model.used_at >= since)
            .scalar() or 0
        )

    def get_usage_by_tenant(
        self,
        tenant_id: int,
        since: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[APIKeyUsage]:
        """
        Recupere l'historique d'utilisation de toutes les API Keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            since: Date de debut (defaut: 24h)
            limit: Nombre max d'entrees

        Returns:
            Liste des utilisations
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .filter(self.model.used_at >= since)
            .order_by(self.model.used_at.desc())
            .limit(limit)
            .all()
        )

    def get_usage_stats_by_key(
        self,
        api_key_id: int,
        since: Optional[datetime] = None
    ) -> dict:
        """
        Statistiques d'utilisation d'une API Key.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut (defaut: 24h)

        Returns:
            Dict avec total_requests, success_count, error_count, avg_response_time
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        # Requete agregee
        result = (
            self.session.query(
                func.count(self.model.id).label('total'),
                func.count(self.model.id).filter(
                    self.model.response_status < 400
                ).label('success'),
                func.count(self.model.id).filter(
                    self.model.response_status >= 400
                ).label('errors'),
                func.avg(self.model.response_time_ms).label('avg_time')
            )
            .filter(self.model.api_key_id == api_key_id)
            .filter(self.model.used_at >= since)
            .first()
        )

        return {
            "total_requests": result.total or 0,
            "success_count": result.success or 0,
            "error_count": result.errors or 0,
            "avg_response_time_ms": float(result.avg_time) if result.avg_time else None
        }

    def cleanup_old_usage(
        self,
        older_than_days: int = 90,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Supprime les logs d'utilisation anciens.

        Args:
            older_than_days: Age minimum en jours
            tenant_id: Limiter au tenant specifie (None = tous)

        Returns:
            Nombre d'entrees supprimees
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        query = (
            self.session.query(self.model)
            .filter(self.model.used_at < cutoff)
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        deleted = query.delete(synchronize_session=False)
        return deleted

    def get_top_endpoints(
        self,
        api_key_id: int,
        since: Optional[datetime] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Top endpoints appeles par une API Key.

        Args:
            api_key_id: ID de l'API Key
            since: Date de debut
            limit: Nombre de resultats

        Returns:
            Liste de dicts avec endpoint, method, count
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        results = (
            self.session.query(
                self.model.endpoint,
                self.model.method,
                func.count(self.model.id).label('count')
            )
            .filter(self.model.api_key_id == api_key_id)
            .filter(self.model.used_at >= since)
            .group_by(self.model.endpoint, self.model.method)
            .order_by(func.count(self.model.id).desc())
            .limit(limit)
            .all()
        )

        return [
            {"endpoint": r.endpoint, "method": r.method, "count": r.count}
            for r in results
        ]
