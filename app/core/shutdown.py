"""
Gestionnaire d'arret gracieux pour MassaCorp API.

Fonctionnalites:
- Gestion des signaux SIGTERM et SIGINT
- Drain des connexions en cours
- Fermeture propre du pool DB
- Timeout configurable
"""
import asyncio
import signal
import logging
from typing import List, Callable, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ShutdownHandler:
    """
    Gestionnaire d'arret gracieux.

    Intercepte les signaux de terminaison et orchestre
    l'arret propre de l'application:
    1. Set le flag is_shutting_down
    2. Rejette les nouvelles requetes (via middleware)
    3. Attend la fin des requetes en cours (drain)
    4. Execute les taches de cleanup
    5. Ferme le pool DB
    """

    def __init__(self):
        """Initialise le handler."""
        self._is_shutting_down = False
        self._active_requests = 0
        self._cleanup_tasks: List[Callable] = []
        self._shutdown_event = asyncio.Event()

    @property
    def is_shutting_down(self) -> bool:
        """True si l'application est en cours d'arret."""
        return self._is_shutting_down

    @property
    def active_requests(self) -> int:
        """Nombre de requetes actives."""
        return self._active_requests

    @active_requests.setter
    def active_requests(self, value: int) -> None:
        """Set le nombre de requetes actives."""
        self._active_requests = value

    def handle_sigterm(self, signum: int, frame: Any) -> None:
        """
        Handler pour SIGTERM (docker stop, kubernetes).

        Args:
            signum: Numero du signal
            frame: Stack frame
        """
        logger.info(f"Received SIGTERM (signal {signum}), initiating graceful shutdown...")
        self._initiate_shutdown()

    def handle_sigint(self, signum: int, frame: Any) -> None:
        """
        Handler pour SIGINT (Ctrl+C).

        Args:
            signum: Numero du signal
            frame: Stack frame
        """
        logger.info(f"Received SIGINT (signal {signum}), initiating graceful shutdown...")
        self._initiate_shutdown()

    def _initiate_shutdown(self) -> None:
        """Demarre le processus d'arret."""
        self._is_shutting_down = True
        self._shutdown_event.set()

    def register_signals(self) -> None:
        """Enregistre les handlers de signaux."""
        signal.signal(signal.SIGTERM, self.handle_sigterm)
        signal.signal(signal.SIGINT, self.handle_sigint)
        logger.debug("Signal handlers registered for SIGTERM and SIGINT")

    def add_cleanup_task(self, task: Callable) -> None:
        """
        Ajoute une tache de cleanup a executer lors de l'arret.

        Args:
            task: Fonction async ou sync a executer
        """
        self._cleanup_tasks.append(task)

    def increment_requests(self) -> None:
        """Incremente le compteur de requetes actives."""
        self._active_requests += 1

    def decrement_requests(self) -> None:
        """Decremente le compteur de requetes actives."""
        self._active_requests = max(0, self._active_requests - 1)

    async def drain_connections(self, timeout: float = 30.0) -> None:
        """
        Attend la fin des requetes en cours avec timeout.

        Args:
            timeout: Temps max d'attente en secondes
        """
        logger.info(f"Draining connections, {self._active_requests} requests in progress...")

        start_time = datetime.now(timezone.utc)
        check_interval = 0.1  # 100ms

        while self._active_requests > 0:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed >= timeout:
                logger.warning(
                    f"Drain timeout reached after {timeout}s, "
                    f"{self._active_requests} requests still active"
                )
                break

            await asyncio.sleep(check_interval)

        logger.info("Connection drain complete")

    async def close_db_pool(self, engine: Any) -> None:
        """
        Ferme proprement le pool de connexions DB.

        Args:
            engine: SQLAlchemy engine
        """
        logger.info("Closing database connection pool...")
        try:
            engine.dispose()
            logger.info("Database pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing database pool: {e}")

    async def run_cleanup_tasks(self) -> None:
        """Execute toutes les taches de cleanup enregistrees."""
        logger.info(f"Running {len(self._cleanup_tasks)} cleanup tasks...")

        for task in self._cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}")

        logger.info("Cleanup tasks completed")

    async def shutdown(self, engine: Optional[Any] = None, timeout: float = 30.0) -> None:
        """
        Execute la sequence complete d'arret.

        Args:
            engine: SQLAlchemy engine (optionnel)
            timeout: Timeout pour le drain
        """
        logger.info("Starting graceful shutdown sequence...")

        # 1. Drain connections
        await self.drain_connections(timeout)

        # 2. Run cleanup tasks
        await self.run_cleanup_tasks()

        # 3. Close DB pool
        if engine:
            await self.close_db_pool(engine)

        logger.info("Graceful shutdown complete")

    @property
    def cleanup_tasks(self) -> List[Callable]:
        """Liste des taches de cleanup."""
        return self._cleanup_tasks


# Instance globale
shutdown_handler = ShutdownHandler()
