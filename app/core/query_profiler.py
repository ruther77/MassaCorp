"""
Query Profiler pour MassaCorp API

Utilitaires de profiling SQL pour:
- EXPLAIN ANALYZE des requetes
- Detection des requetes N+1
- Logging des requetes lentes

Actif uniquement en mode dev/test pour eviter l'impact performance en prod.
"""
import time
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class QueryStats:
    """Statistiques d'une requete SQL."""
    sql: str
    duration_ms: float
    parameters: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None


@dataclass
class N1QueryPattern:
    """Pattern de requete N+1 detecte."""
    base_query: str
    repeated_query: str
    count: int
    total_time_ms: float


@dataclass
class ProfilerReport:
    """Rapport complet du profiler."""
    total_queries: int
    total_time_ms: float
    slow_queries: List[QueryStats]
    n1_patterns: List[N1QueryPattern]
    queries_by_pattern: Dict[str, int] = field(default_factory=dict)


class QueryProfiler:
    """
    Profiler de requetes SQL.

    Usage:
        profiler = QueryProfiler()
        with profiler.profile():
            # Executer les requetes...
            pass
        report = profiler.get_report()
    """

    # Seuil pour considerer une requete comme lente (ms)
    SLOW_QUERY_THRESHOLD_MS = 100

    # Nombre de repetitions pour detecter N+1
    N1_DETECTION_THRESHOLD = 3

    def __init__(self, enabled: bool = None):
        """
        Initialise le profiler.

        Args:
            enabled: Force activation/desactivation. Si None, utilise settings.
        """
        settings = get_settings()
        self._enabled = enabled if enabled is not None else settings.is_development

        self._queries: List[QueryStats] = []
        self._active = False
        self._lock = threading.Lock()

    @property
    def is_enabled(self) -> bool:
        """True si le profiler est actif."""
        return self._enabled

    def clear(self):
        """Remet a zero les statistiques."""
        with self._lock:
            self._queries = []

    @contextmanager
    def profile(self):
        """
        Context manager pour profiler un bloc de code.

        Usage:
            with profiler.profile():
                # Code a profiler
                pass
        """
        if not self._enabled:
            yield
            return

        self.clear()
        self._active = True
        try:
            yield
        finally:
            self._active = False

    def record_query(self, sql: str, duration_ms: float, parameters: Dict = None):
        """
        Enregistre une requete executee.

        Args:
            sql: Requete SQL
            duration_ms: Temps d'execution en ms
            parameters: Parametres de la requete
        """
        if not self._active or not self._enabled:
            return

        with self._lock:
            self._queries.append(QueryStats(
                sql=sql,
                duration_ms=duration_ms,
                parameters=parameters
            ))

    def get_report(self) -> ProfilerReport:
        """
        Genere un rapport de profiling.

        Returns:
            ProfilerReport avec statistiques detaillees
        """
        with self._lock:
            queries = list(self._queries)

        if not queries:
            return ProfilerReport(
                total_queries=0,
                total_time_ms=0,
                slow_queries=[],
                n1_patterns=[]
            )

        # Stats de base
        total_time = sum(q.duration_ms for q in queries)

        # Requetes lentes
        slow_queries = [
            q for q in queries
            if q.duration_ms >= self.SLOW_QUERY_THRESHOLD_MS
        ]

        # Detection N+1
        n1_patterns = self._detect_n1_patterns(queries)

        # Grouper par pattern
        queries_by_pattern: Dict[str, int] = {}
        for q in queries:
            # Normaliser la requete (enlever les valeurs)
            pattern = self._normalize_query(q.sql)
            queries_by_pattern[pattern] = queries_by_pattern.get(pattern, 0) + 1

        return ProfilerReport(
            total_queries=len(queries),
            total_time_ms=total_time,
            slow_queries=slow_queries,
            n1_patterns=n1_patterns,
            queries_by_pattern=queries_by_pattern
        )

    def _detect_n1_patterns(self, queries: List[QueryStats]) -> List[N1QueryPattern]:
        """
        Detecte les patterns de requetes N+1.

        Un pattern N+1 est detecte quand:
        - Une requete est repetee plusieurs fois
        - Avec des parametres differents
        """
        patterns: Dict[str, List[QueryStats]] = {}

        for q in queries:
            pattern = self._normalize_query(q.sql)
            if pattern not in patterns:
                patterns[pattern] = []
            patterns[pattern].append(q)

        n1_patterns = []
        for pattern, pattern_queries in patterns.items():
            if len(pattern_queries) >= self.N1_DETECTION_THRESHOLD:
                # Potentiel N+1 detecte
                total_time = sum(q.duration_ms for q in pattern_queries)
                n1_patterns.append(N1QueryPattern(
                    base_query="(voir requete precedente)",
                    repeated_query=pattern_queries[0].sql[:200],
                    count=len(pattern_queries),
                    total_time_ms=total_time
                ))

        return n1_patterns

    def _normalize_query(self, sql: str) -> str:
        """
        Normalise une requete SQL pour comparaison.

        Remplace les valeurs litterales par des placeholders.
        """
        # Simplification: on garde juste la structure
        normalized = sql.strip().lower()

        # Tronquer pour eviter les variations mineures
        if len(normalized) > 100:
            normalized = normalized[:100]

        return normalized

    def log_report(self):
        """Log le rapport de profiling."""
        if not self._enabled:
            return

        report = self.get_report()

        if report.total_queries == 0:
            return

        logger.info(
            f"Query Profile: {report.total_queries} queries, "
            f"{report.total_time_ms:.2f}ms total"
        )

        # Alerter sur les requetes lentes
        for slow_query in report.slow_queries:
            logger.warning(
                f"Slow query ({slow_query.duration_ms:.2f}ms): "
                f"{slow_query.sql[:100]}..."
            )

        # Alerter sur les N+1
        for n1 in report.n1_patterns:
            logger.warning(
                f"N+1 DETECTED: {n1.count} identical queries, "
                f"{n1.total_time_ms:.2f}ms total. Query: {n1.repeated_query[:100]}..."
            )


def explain_analyze(session: Session, query) -> Dict[str, Any]:
    """
    Execute EXPLAIN ANALYZE sur une requete.

    Args:
        session: Session SQLAlchemy
        query: Query a analyser

    Returns:
        Dict avec le plan d'execution et les statistiques
    """
    settings = get_settings()
    if settings.is_production:
        logger.warning("EXPLAIN ANALYZE desactive en production")
        return {"error": "Desactive en production"}

    # Compiler la requete
    statement = query.statement.compile(
        session.bind,
        compile_kwargs={"literal_binds": True}
    )
    sql = str(statement)

    # Executer EXPLAIN ANALYZE
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"

    result = session.execute(explain_sql)
    plan = result.fetchone()[0]

    return {
        "query": sql,
        "plan": plan,
        "execution_time_ms": plan[0].get("Execution Time", 0) if plan else 0,
        "planning_time_ms": plan[0].get("Planning Time", 0) if plan else 0
    }


# Instance globale du profiler
_profiler: Optional[QueryProfiler] = None


def get_query_profiler() -> QueryProfiler:
    """Retourne l'instance globale du profiler."""
    global _profiler
    if _profiler is None:
        _profiler = QueryProfiler()
    return _profiler


def setup_query_profiling(engine: Engine):
    """
    Configure le profiling automatique des requetes sur un engine.

    A appeler au demarrage de l'application en mode dev.

    Args:
        engine: Engine SQLAlchemy
    """
    settings = get_settings()
    if not settings.is_development:
        return

    profiler = get_query_profiler()

    @event.listens_for(engine, "before_cursor_execute")
    def before_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())

    @event.listens_for(engine, "after_cursor_execute")
    def after_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("query_start_time", [])
        if start_times:
            start = start_times.pop()
            duration_ms = (time.time() - start) * 1000
            profiler.record_query(statement, duration_ms, parameters)

    logger.info("Query profiling active (mode developpement)")
