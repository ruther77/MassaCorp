"""
Script de seed pour MassaCorp
Cree les tenants par defaut et l'admin initial

Usage:
    python -m app.scripts.seed

Le script est idempotent - peut etre relance sans effet
si les donnees existent deja.
"""
import secrets
import string
import sys
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Tenant, User
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository


# ============================================
# Configuration du Seed
# ============================================

SEED_TENANTS = [
    {"name": "Epicerie", "slug": "epicerie"},
    {"name": "Restaurant", "slug": "restaurant"},
    {"name": "Autre", "slug": "autre"},  # Tenant agregateur pour cross-tenant queries
]

SEED_ADMIN = {
    "email": "admin@massacorp.dev",
    "first_name": "Admin",
    "last_name": "MassaCorp",
    "is_superuser": True,
    "is_active": True,
    "is_verified": True,
}


# ============================================
# Fonctions Utilitaires
# ============================================

def generate_secure_password(length: int = 16) -> str:
    """
    Genere un mot de passe securise aleatoire.

    Le mot de passe contient:
    - Lettres majuscules et minuscules
    - Chiffres
    - Caracteres speciaux

    Args:
        length: Longueur du mot de passe

    Returns:
        Mot de passe genere
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # S'assurer d'avoir au moins un de chaque type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*"),
    ]
    # Completer avec des caracteres aleatoires
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))
    # Melanger
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def print_banner():
    """Affiche le banner du script"""
    print("=" * 60)
    print("           MassaCorp - Script de Seed")
    print("=" * 60)
    print()


def print_success(message: str):
    """Affiche un message de succes"""
    print(f"  ✓ {message}")


def print_info(message: str):
    """Affiche un message d'information"""
    print(f"  ℹ {message}")


def print_warning(message: str):
    """Affiche un avertissement"""
    print(f"  ⚠ {message}")


def print_error(message: str):
    """Affiche une erreur"""
    print(f"  ✗ {message}")


# ============================================
# Fonctions de Seed
# ============================================

def seed_tenants(session: Session) -> dict:
    """
    Cree les tenants par defaut.

    Args:
        session: Session SQLAlchemy

    Returns:
        Dict avec les tenants crees/existants
    """
    print("\n[1/2] Creation des tenants...")
    tenant_repo = TenantRepository(session)
    tenants = {}

    for tenant_data in SEED_TENANTS:
        existing = tenant_repo.get_by_slug(tenant_data["slug"])

        if existing:
            print_info(f"Tenant '{tenant_data['name']}' existe deja (ID: {existing.id})")
            tenants[tenant_data["slug"]] = existing
        else:
            tenant = tenant_repo.create({
                "name": tenant_data["name"],
                "slug": tenant_data["slug"],
                "is_active": True,
                "settings": {},
            })
            session.flush()
            print_success(f"Tenant '{tenant_data['name']}' cree (ID: {tenant.id})")
            tenants[tenant_data["slug"]] = tenant

    return tenants


def seed_admin(session: Session, tenants: dict) -> tuple:
    """
    Cree l'utilisateur admin.

    Args:
        session: Session SQLAlchemy
        tenants: Dict des tenants

    Returns:
        Tuple (user, password) ou (None, None) si existe deja
    """
    print("\n[2/2] Creation de l'admin...")
    user_repo = UserRepository(session)

    # Utiliser le premier tenant (Epicerie)
    tenant = tenants.get("epicerie")
    if not tenant:
        print_error("Tenant 'epicerie' non trouve!")
        return None, None

    # Verifier si l'admin existe deja
    existing = user_repo.get_by_email_and_tenant(
        SEED_ADMIN["email"],
        tenant.id
    )

    if existing:
        print_info(f"Admin '{SEED_ADMIN['email']}' existe deja (ID: {existing.id})")
        return None, None

    # Generer un mot de passe securise
    password = generate_secure_password(20)
    password_hash = hash_password(password)

    # Creer l'admin
    admin = user_repo.create({
        "email": SEED_ADMIN["email"],
        "password_hash": password_hash,
        "tenant_id": tenant.id,
        "first_name": SEED_ADMIN["first_name"],
        "last_name": SEED_ADMIN["last_name"],
        "is_superuser": SEED_ADMIN["is_superuser"],
        "is_active": SEED_ADMIN["is_active"],
        "is_verified": SEED_ADMIN["is_verified"],
    })
    session.flush()

    print_success(f"Admin '{SEED_ADMIN['email']}' cree (ID: {admin.id})")
    return admin, password


def verify_tables_exist(session: Session) -> bool:
    """Verifie que les tables necessaires existent"""
    try:
        session.execute(text("SELECT 1 FROM tenants LIMIT 1"))
        session.execute(text("SELECT 1 FROM users LIMIT 1"))
        return True
    except Exception as e:
        print_error(f"Tables manquantes: {e}")
        print_warning("Executez d'abord: alembic upgrade head")
        return False


# ============================================
# Main
# ============================================

def main():
    """Point d'entree principal du script de seed"""
    print_banner()

    # Creer une session
    session = SessionLocal()

    try:
        # Verifier que les tables existent
        print("Verification des tables...")
        if not verify_tables_exist(session):
            return 1

        print_success("Tables OK")

        # Seed tenants
        tenants = seed_tenants(session)

        # Seed admin
        admin, password = seed_admin(session, tenants)

        # Commit
        session.commit()

        # Afficher le resume
        print("\n" + "=" * 60)
        print("                    RESUME DU SEED")
        print("=" * 60)

        print("\nTenants:")
        for slug, tenant in tenants.items():
            print(f"  - {tenant.name} (slug: {slug}, ID: {tenant.id})")

        if admin and password:
            print("\n" + "-" * 60)
            print("   ATTENTION: Conservez ces informations en lieu sur!")
            print("-" * 60)
            print(f"\n  Admin Email:    {admin.email}")
            print(f"  Admin Password: {password}")
            print(f"  Tenant:         epicerie (ID: {admin.tenant_id})")
            print("\n  Ce mot de passe ne sera plus affiche!")
            print("-" * 60)
        else:
            print("\n  Admin deja existant - aucun nouveau mot de passe genere")

        print("\n" + "=" * 60)
        print("                 Seed termine avec succes!")
        print("=" * 60 + "\n")

        return 0

    except Exception as e:
        session.rollback()
        print_error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
