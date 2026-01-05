"""
Configuration globale pytest pour MassaCorp API
Fixtures partagees entre tous les tests

Environnement de test (ENV=test):
- Rate limiting middleware desactive (app/main.py)
- Brute-force protection desactive (app/services/session.py)
- Login attempts nettoyes avant chaque test

Note importante:
Le header X-Tenant-ID est obligatoire pour les endpoints /auth/login et /auth/login/mfa.
Tous les tests d'integration doivent l'inclure: headers={"X-Tenant-ID": "1"}
"""
import os
import pytest
from typing import Generator, Dict, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Configuration environnement de test
# Ceci desactive le rate limiting et la protection brute-force
os.environ["ENV"] = "test"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.core.config import get_settings, Settings
from app.core.database import Base
from app.core.dependencies import get_db
from app.main import app


# ============================================
# Configuration Base de Donnees Test
# ============================================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings pour environnement de test"""
    return get_settings()


@pytest.fixture(scope="session")
def test_db_url(test_settings: Settings) -> str:
    """URL de la base de donnees de test"""
    # Utiliser la meme DB avec rollback apres chaque test
    return test_settings.DATABASE_URL


@pytest.fixture(scope="session")
def db_engine(test_db_url: str):
    """
    Engine SQLAlchemy pour les tests.
    Utilise la DB existante avec rollback.
    """
    engine = create_engine(
        test_db_url,
        pool_pre_ping=True,
        echo=False  # Mettre True pour debug SQL
    )

    # Nettoyer les login_attempts au debut de la session de tests
    # pour eviter le rate limiting accumule
    with engine.connect() as conn:
        try:
            conn.execute(text("DELETE FROM login_attempts"))
            conn.commit()
        except Exception:
            conn.rollback()

    yield engine

    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Session de DB pour les tests.
    Les tests d'integration utilisent la vraie DB (pas de SAVEPOINT)
    car les tests doivent voir les donnees creees par l'API.

    Note: Nettoie les LoginAttempt avant chaque test pour eviter le rate limiting.
    """
    # Creer une session directe (pas de SAVEPOINT)
    TestSessionLocal = sessionmaker(bind=db_engine)
    session = TestSessionLocal()

    # Nettoyer les tentatives de login avant chaque test
    try:
        session.execute(text("DELETE FROM login_attempts"))
        session.commit()
    except Exception:
        session.rollback()

    yield session

    session.close()


# ============================================
# Client API Test
# ============================================

@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    TestClient FastAPI avec override de get_db.
    Utilise la session de test avec rollback.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ============================================
# Fixtures Donnees de Test
# ============================================

@pytest.fixture
def sample_password() -> str:
    """Mot de passe valide pour les tests"""
    return "SecureP@ssw0rd123!"


@pytest.fixture
def weak_passwords() -> list:
    """Liste de mots de passe faibles pour tests de validation"""
    return [
        "",                      # Vide
        "short",                 # Trop court
        "nouppercase123!",       # Pas de majuscule
        "NOLOWERCASE123!",       # Pas de minuscule
        "NoSpecialChar123",      # Pas de caractere special
        "NoNumbers!ABC",         # Pas de chiffre
        "a" * 200,               # Trop long
    ]


@pytest.fixture
def sample_email() -> str:
    """Email valide pour les tests"""
    return "test@massacorp.local"


@pytest.fixture
def invalid_emails() -> list:
    """Liste d'emails invalides pour tests de validation"""
    return [
        "",
        "invalid",
        "invalid@",
        "@invalid.com",
        "invalid@.com",
        "invalid@domain",
        "in valid@domain.com",
    ]


@pytest.fixture
def sample_user_data(sample_email: str, sample_password: str) -> Dict[str, Any]:
    """Donnees utilisateur valides pour creation"""
    return {
        "email": sample_email,
        "password": sample_password,
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def sample_tenant_data() -> Dict[str, Any]:
    """Donnees tenant valides pour creation"""
    return {
        "name": "Test Tenant",
        "slug": "test-tenant",
    }


# ============================================
# Fixtures JWT
# ============================================

@pytest.fixture
def jwt_payload_valid() -> Dict[str, Any]:
    """Payload JWT valide"""
    now = datetime.now(timezone.utc)
    return {
        "sub": 1,  # user_id
        "tenant_id": 1,
        "email": "test@massacorp.local",
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "iat": int(now.timestamp()),
        "type": "access",
    }


@pytest.fixture
def jwt_payload_expired() -> Dict[str, Any]:
    """Payload JWT expire"""
    now = datetime.now(timezone.utc)
    return {
        "sub": 1,
        "tenant_id": 1,
        "email": "test@massacorp.local",
        "exp": int((now - timedelta(minutes=15)).timestamp()),  # Expire
        "iat": int((now - timedelta(minutes=30)).timestamp()),
        "type": "access",
    }


@pytest.fixture
def jwt_payload_refresh() -> Dict[str, Any]:
    """Payload JWT refresh token"""
    now = datetime.now(timezone.utc)
    return {
        "sub": 1,
        "tenant_id": 1,
        "exp": int((now + timedelta(days=7)).timestamp()),
        "iat": int(now.timestamp()),
        "type": "refresh",
        "jti": "unique-token-id-123",
    }


# ============================================
# Helpers
# ============================================

@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Headers d'authentification vides (a completer par les tests)"""
    return {"Authorization": "Bearer "}


def create_auth_headers(token: str) -> Dict[str, str]:
    """Helper pour creer des headers avec token"""
    return {"Authorization": f"Bearer {token}"}


# ============================================
# Markers pytest
# ============================================

def pytest_configure(config):
    """Configuration des markers personnalises"""
    config.addinivalue_line(
        "markers", "unit: Tests unitaires (pas de DB)"
    )
    config.addinivalue_line(
        "markers", "integration: Tests integration (avec DB)"
    )
    config.addinivalue_line(
        "markers", "e2e: Tests end-to-end (API complete)"
    )
    config.addinivalue_line(
        "markers", "security: Tests de securite"
    )
    config.addinivalue_line(
        "markers", "slow: Tests lents (> 1s)"
    )
