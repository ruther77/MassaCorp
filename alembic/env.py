"""
Configuration Alembic pour les migrations de base de donnees
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

# Objet de configuration Alembic
config = context.config

# Configuration du logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata pour autogenerate - importer tous les modeles
from app.models.base import Base
# Importer tous les modeles pour que leurs tables soient enregistrees
from app.models import (  # noqa: F401
    User, Tenant, Session, AuditLog, LoginAttempt,
    RefreshToken, RevokedToken, MFASecret, MFARecoveryCode,
    PasswordResetToken, APIKey
)
target_metadata = Base.metadata


def get_database_url() -> str:
    """Recupere l'URL de la base de donnees depuis l'environnement"""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL non definie")
    return url


def run_migrations_offline() -> None:
    """
    Execute les migrations en mode 'offline'.
    Configure le contexte avec juste une URL.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Execute les migrations en mode 'online'.
    Cree un Engine et associe une connexion au contexte.
    """
    # Utiliser l'URL depuis l'environnement
    url = get_database_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
