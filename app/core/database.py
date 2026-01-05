"""
Configuration de la connexion a la base de donnees
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings

# Importer Base depuis models pour coherence
from app.models.base import Base

settings = get_settings()

# Creer le moteur SQLAlchemy
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verifie la connexion avant utilisation
    pool_size=10,
    max_overflow=20,
)

# Session locale
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Generateur de session de base de donnees
    Utilise comme dependance FastAPI
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
