"""
Metriques pour MassaCorp API.

Module de metriques qui fonctionne avec ou sans prometheus_client.
Fournit des compteurs et histogrammes pour:
- Requetes HTTP
- Authentification
- Sessions
- Base de donnees

Usage:
    from app.core.metrics import metrics

    # Compter une requete
    metrics.http_requests_total.inc(method="GET", path="/api/v1/users", status=200)

    # Mesurer une duree
    with metrics.http_request_duration.time(method="GET", path="/api/v1/users"):
        # ... traitement
        pass

Installation Prometheus (optionnel):
    pip install prometheus-client

    Puis ajouter l'endpoint /metrics:
    from app.core.metrics import get_metrics_response
    @app.get("/metrics")
    def metrics():
        return get_metrics_response()
"""
import time
import logging
from typing import Dict, Any, Optional
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock

logger = logging.getLogger(__name__)

# Tenter d'importer prometheus_client
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed - using in-memory metrics")


# =============================================================================
# Fallback metrics (sans prometheus)
# =============================================================================

class SimpleCounter:
    """Compteur simple thread-safe."""

    def __init__(self, name: str, description: str, labels: list = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, amount: float = 1, **labels) -> None:
        """Incremente le compteur."""
        key = tuple(labels.get(l, "") for l in self.labels)
        with self._lock:
            self._values[key] += amount

    def get(self, **labels) -> float:
        """Retourne la valeur du compteur."""
        key = tuple(labels.get(l, "") for l in self.labels)
        return self._values.get(key, 0)

    def get_all(self) -> Dict[tuple, float]:
        """Retourne toutes les valeurs."""
        return dict(self._values)


class SimpleHistogram:
    """Histogramme simple pour mesurer les durees."""

    def __init__(self, name: str, description: str, labels: list = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._counts: Dict[tuple, int] = defaultdict(int)
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def observe(self, value: float, **labels) -> None:
        """Enregistre une observation."""
        key = tuple(labels.get(l, "") for l in self.labels)
        with self._lock:
            self._counts[key] += 1
            self._sums[key] += value

    @contextmanager
    def time(self, **labels):
        """Context manager pour mesurer le temps."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.observe(duration, **labels)

    def get_count(self, **labels) -> int:
        """Retourne le nombre d'observations."""
        key = tuple(labels.get(l, "") for l in self.labels)
        return self._counts.get(key, 0)

    def get_sum(self, **labels) -> float:
        """Retourne la somme des observations."""
        key = tuple(labels.get(l, "") for l in self.labels)
        return self._sums.get(key, 0)


class SimpleGauge:
    """Gauge simple pour les valeurs qui montent et descendent."""

    def __init__(self, name: str, description: str, labels: list = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()

    def set(self, value: float, **labels) -> None:
        """Set la valeur du gauge."""
        key = tuple(labels.get(l, "") for l in self.labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1, **labels) -> None:
        """Incremente le gauge."""
        key = tuple(labels.get(l, "") for l in self.labels)
        with self._lock:
            self._values[key] += amount

    def dec(self, amount: float = 1, **labels) -> None:
        """Decremente le gauge."""
        key = tuple(labels.get(l, "") for l in self.labels)
        with self._lock:
            self._values[key] -= amount

    def get(self, **labels) -> float:
        """Retourne la valeur du gauge."""
        key = tuple(labels.get(l, "") for l in self.labels)
        return self._values.get(key, 0)


# =============================================================================
# Metrics Registry
# =============================================================================

class MetricsRegistry:
    """
    Registre central des metriques.

    Utilise prometheus_client si disponible, sinon des metriques simples.
    """

    def __init__(self):
        self._init_metrics()

    def _init_metrics(self):
        """Initialise les metriques."""
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()
        else:
            self._init_simple_metrics()

    def _init_prometheus_metrics(self):
        """Initialise les metriques Prometheus."""
        # HTTP Requests
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"]
        )
        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "path"]
        )

        # Authentication
        self.auth_login_total = Counter(
            "auth_login_total",
            "Total login attempts",
            ["status", "tenant_id"]
        )
        self.auth_mfa_verify_total = Counter(
            "auth_mfa_verify_total",
            "Total MFA verification attempts",
            ["status", "tenant_id"]
        )

        # Sessions
        self.active_sessions = Gauge(
            "active_sessions",
            "Number of active sessions",
            ["tenant_id"]
        )

        # Rate Limiting
        self.rate_limit_hits_total = Counter(
            "rate_limit_hits_total",
            "Total rate limit hits",
            ["endpoint", "tenant_id"]
        )

        # Database
        self.db_query_duration = Histogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["query_type"]
        )

    def _init_simple_metrics(self):
        """Initialise les metriques simples (fallback)."""
        # HTTP Requests
        self.http_requests_total = SimpleCounter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"]
        )
        self.http_request_duration = SimpleHistogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "path"]
        )

        # Authentication
        self.auth_login_total = SimpleCounter(
            "auth_login_total",
            "Total login attempts",
            ["status", "tenant_id"]
        )
        self.auth_mfa_verify_total = SimpleCounter(
            "auth_mfa_verify_total",
            "Total MFA verification attempts",
            ["status", "tenant_id"]
        )

        # Sessions
        self.active_sessions = SimpleGauge(
            "active_sessions",
            "Number of active sessions",
            ["tenant_id"]
        )

        # Rate Limiting
        self.rate_limit_hits_total = SimpleCounter(
            "rate_limit_hits_total",
            "Total rate limit hits",
            ["endpoint", "tenant_id"]
        )

        # Database
        self.db_query_duration = SimpleHistogram(
            "db_query_duration_seconds",
            "Database query duration in seconds",
            ["query_type"]
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques des metriques (pour debug).

        Returns:
            Dict avec les valeurs des metriques
        """
        if PROMETHEUS_AVAILABLE:
            return {"prometheus": True, "message": "Use /metrics endpoint"}

        return {
            "prometheus": False,
            "http_requests": self.http_requests_total.get_all(),
            "auth_logins": self.auth_login_total.get_all(),
            "rate_limit_hits": self.rate_limit_hits_total.get_all(),
        }


# Instance globale
metrics = MetricsRegistry()


def get_metrics_response():
    """
    Retourne la response pour l'endpoint /metrics.

    Returns:
        Response avec les metriques au format Prometheus
    """
    if PROMETHEUS_AVAILABLE:
        from starlette.responses import Response
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    # Fallback: retourner les stats en JSON
    from starlette.responses import JSONResponse
    return JSONResponse(content=metrics.get_stats())


# =============================================================================
# Middleware pour les metriques HTTP
# =============================================================================

class MetricsMiddleware:
    """
    Middleware pour collecter les metriques HTTP.

    Enregistre automatiquement:
    - http_requests_total
    - http_request_duration_seconds
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        start_time = time.perf_counter()
        status_code = 500  # Default en cas d'erreur

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            method = scope.get("method", "UNKNOWN")
            path = scope.get("path", "/")

            # Normaliser le path (eviter explosion de cardinalite)
            # Remplacer les IDs numeriques par {id}
            import re
            normalized_path = re.sub(r"/\d+", "/{id}", path)

            # Enregistrer les metriques
            if PROMETHEUS_AVAILABLE:
                metrics.http_requests_total.labels(
                    method=method,
                    path=normalized_path,
                    status=str(status_code)
                ).inc()
                metrics.http_request_duration.labels(
                    method=method,
                    path=normalized_path
                ).observe(duration)
            else:
                metrics.http_requests_total.inc(
                    method=method,
                    path=normalized_path,
                    status=str(status_code)
                )
                metrics.http_request_duration.observe(
                    duration,
                    method=method,
                    path=normalized_path
                )
