"""
Taches de nettoyage pour MassaCorp.

Ce module contient les fonctions de maintenance pour nettoyer:
- Tokens revoques expires
- Refresh tokens expires
- Sessions revoquees anciennes
- Tentatives de login anciennes

Usage:
    # Via CLI
    python -m app.tasks.cleanup --all
    python -m app.tasks.cleanup --tokens
    python -m app.tasks.cleanup --sessions

    # Programmatiquement
    from app.tasks.cleanup import cleanup_all
    await cleanup_all(db_session)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import delete, select, func
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration de retention
# =============================================================================

RETENTION_CONFIG = {
    "revoked_tokens": 0,       # Supprimer des que expire
    "refresh_tokens": 0,       # Supprimer des que expire
    "sessions_revoked": 90,    # Garder 90 jours apres revocation
    "login_attempts": 30,      # Garder 30 jours
    "audit_logs": 365,         # Garder 1 an (compliance)
}


# =============================================================================
# Fonctions de nettoyage synchrones
# =============================================================================

def cleanup_revoked_tokens(db: Session) -> int:
    """
    Supprime les tokens revoques dont l'expiration est passee.

    Un token revoque n'a plus besoin d'etre dans la blacklist
    une fois qu'il est naturellement expire.

    Args:
        db: Session SQLAlchemy

    Returns:
        Nombre de tokens supprimes
    """
    from app.models.session import RevokedToken

    now = datetime.now(timezone.utc)

    result = db.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < now)
    )
    deleted = result.rowcount
    db.commit()

    if deleted > 0:
        logger.info(f"Cleanup: {deleted} revoked tokens supprimes")

    return deleted


def cleanup_refresh_tokens(db: Session) -> int:
    """
    Supprime les refresh tokens expires.

    Args:
        db: Session SQLAlchemy

    Returns:
        Nombre de tokens supprimes
    """
    from app.models.session import RefreshToken

    now = datetime.now(timezone.utc)

    result = db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now)
    )
    deleted = result.rowcount
    db.commit()

    if deleted > 0:
        logger.info(f"Cleanup: {deleted} refresh tokens expires supprimes")

    return deleted


def cleanup_old_sessions(db: Session, days: int = 90) -> int:
    """
    Supprime les sessions revoquees depuis plus de N jours.

    Args:
        db: Session SQLAlchemy
        days: Nombre de jours de retention

    Returns:
        Nombre de sessions supprimees
    """
    from app.models.session import Session as SessionModel

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = db.execute(
        delete(SessionModel).where(
            SessionModel.revoked_at.isnot(None),
            SessionModel.revoked_at < cutoff
        )
    )
    deleted = result.rowcount
    db.commit()

    if deleted > 0:
        logger.info(f"Cleanup: {deleted} sessions revoquees supprimees (> {days} jours)")

    return deleted


def cleanup_login_attempts(db: Session, days: int = 30) -> int:
    """
    Supprime les tentatives de login anciennes.

    Args:
        db: Session SQLAlchemy
        days: Nombre de jours de retention

    Returns:
        Nombre de tentatives supprimees
    """
    from app.models.login_attempt import LoginAttempt

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        result = db.execute(
            delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff)
        )
        deleted = result.rowcount
        db.commit()

        if deleted > 0:
            logger.info(f"Cleanup: {deleted} login attempts supprimes (> {days} jours)")

        return deleted
    except Exception as e:
        logger.warning(f"Cleanup login_attempts skipped: {e}")
        db.rollback()
        return 0


def cleanup_all_sync(db: Session) -> Dict[str, int]:
    """
    Execute toutes les taches de nettoyage.

    Args:
        db: Session SQLAlchemy

    Returns:
        Dict avec le nombre d'elements supprimes par categorie
    """
    results = {
        "revoked_tokens": cleanup_revoked_tokens(db),
        "refresh_tokens": cleanup_refresh_tokens(db),
        "sessions": cleanup_old_sessions(db, RETENTION_CONFIG["sessions_revoked"]),
        "login_attempts": cleanup_login_attempts(db, RETENTION_CONFIG["login_attempts"]),
    }

    total = sum(results.values())
    logger.info(f"Cleanup total: {total} elements supprimes")

    return results


# =============================================================================
# Fonctions de nettoyage asynchrones
# =============================================================================

async def async_cleanup_revoked_tokens(db: AsyncSession) -> int:
    """Version asynchrone de cleanup_revoked_tokens."""
    from app.models.session import RevokedToken

    now = datetime.now(timezone.utc)

    result = await db.execute(
        delete(RevokedToken).where(RevokedToken.expires_at < now)
    )
    deleted = result.rowcount
    await db.commit()

    if deleted > 0:
        logger.info(f"Async cleanup: {deleted} revoked tokens supprimes")

    return deleted


async def async_cleanup_refresh_tokens(db: AsyncSession) -> int:
    """Version asynchrone de cleanup_refresh_tokens."""
    from app.models.session import RefreshToken

    now = datetime.now(timezone.utc)

    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < now)
    )
    deleted = result.rowcount
    await db.commit()

    if deleted > 0:
        logger.info(f"Async cleanup: {deleted} refresh tokens expires supprimes")

    return deleted


async def async_cleanup_all(db: AsyncSession) -> Dict[str, int]:
    """
    Execute toutes les taches de nettoyage de maniere asynchrone.

    Args:
        db: AsyncSession SQLAlchemy

    Returns:
        Dict avec le nombre d'elements supprimes par categorie
    """
    results = {
        "revoked_tokens": await async_cleanup_revoked_tokens(db),
        "refresh_tokens": await async_cleanup_refresh_tokens(db),
    }

    total = sum(results.values())
    logger.info(f"Async cleanup total: {total} elements supprimes")

    return results


# =============================================================================
# Count functions (dry-run)
# =============================================================================

def count_cleanup_candidates(db: Session) -> Dict[str, int]:
    """
    Compte les elements qui seraient supprimes (pour dry-run).

    Args:
        db: Session SQLAlchemy

    Returns:
        Dict avec le nombre d'elements par categorie
    """
    from app.models.session import RevokedToken, RefreshToken
    from app.models.session import Session as SessionModel
    from app.models.login_attempt import LoginAttempt

    now = datetime.now(timezone.utc)
    session_cutoff = now - timedelta(days=RETENTION_CONFIG["sessions_revoked"])
    login_cutoff = now - timedelta(days=RETENTION_CONFIG["login_attempts"])

    counts = {}

    # Revoked tokens expires
    counts["revoked_tokens"] = db.query(func.count(RevokedToken.id)).filter(
        RevokedToken.expires_at < now
    ).scalar() or 0

    # Refresh tokens expires
    counts["refresh_tokens"] = db.query(func.count(RefreshToken.id)).filter(
        RefreshToken.expires_at < now
    ).scalar() or 0

    # Sessions revoquees anciennes
    counts["sessions"] = db.query(func.count(SessionModel.id)).filter(
        SessionModel.revoked_at.isnot(None),
        SessionModel.revoked_at < session_cutoff
    ).scalar() or 0

    # Login attempts anciens
    try:
        counts["login_attempts"] = db.query(func.count(LoginAttempt.id)).filter(
            LoginAttempt.attempted_at < login_cutoff
        ).scalar() or 0
    except Exception:
        counts["login_attempts"] = 0

    return counts


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Point d'entree CLI pour les taches de nettoyage."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Cleanup expired tokens and sessions")
    parser.add_argument("--all", action="store_true", help="Run all cleanup tasks")
    parser.add_argument("--tokens", action="store_true", help="Cleanup expired tokens")
    parser.add_argument("--sessions", action="store_true", help="Cleanup old sessions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")

    args = parser.parse_args()

    if not any([args.all, args.tokens, args.sessions]):
        parser.print_help()
        sys.exit(1)

    # Import database session
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if args.dry_run:
            print("DRY RUN - No changes will be made")
            counts = count_cleanup_candidates(db)
            print("\nElements qui seraient supprimes:")
            for table, count in counts.items():
                print(f"  {table}: {count}")
            print(f"\nTotal: {sum(counts.values())}")
            return

        if args.all:
            results = cleanup_all_sync(db)
            for table, count in results.items():
                print(f"  {table}: {count} deleted")
        else:
            if args.tokens:
                count = cleanup_revoked_tokens(db)
                count += cleanup_refresh_tokens(db)
                print(f"Tokens deleted: {count}")

            if args.sessions:
                count = cleanup_old_sessions(db)
                print(f"Sessions deleted: {count}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
