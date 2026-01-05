#!/usr/bin/env python3
"""
Script de rotation des secrets MassaCorp.

Usage:
    python scripts/rotate_secrets.py --help
    python scripts/rotate_secrets.py --list           # Lister les secrets et leur politique
    python scripts/rotate_secrets.py --check          # Verifier si rotation necessaire
    python scripts/rotate_secrets.py --rotate jwt     # Pivoter JWT_SECRET
    python scripts/rotate_secrets.py --rotate all     # Pivoter tous les secrets
    python scripts/rotate_secrets.py --rotate all --force  # Forcer rotation

ATTENTION: Ce script genere de nouveaux secrets mais ne les applique pas
automatiquement. Vous devez:
1. Mettre a jour le gestionnaire de secrets (Vault/Infisical/AWS)
2. Redemarrer les services concernes
3. Pour POSTGRES_PASSWORD: executer ALTER USER dans PostgreSQL
4. Pour REDIS_PASSWORD: redemarrer Redis avec le nouveau mot de passe
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Ajouter le chemin racine au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.secrets import (
    SecretRotationPolicy,
    SecretRotator,
    get_secret_rotator,
)


def print_header(title: str) -> None:
    """Affiche un header formate."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def list_secrets() -> None:
    """Liste tous les secrets et leur politique de rotation."""
    print_header("Politique de rotation des secrets")

    print(f"{'Secret':<25} {'Periode (jours)':<15} {'Prochaine rotation'}")
    print("-" * 60)

    for secret, period in SecretRotationPolicy.ROTATION_PERIODS.items():
        # Calculer la prochaine rotation (fictive, basee sur aujourd'hui)
        next_rotation = datetime.now() + timedelta(days=period)
        print(f"{secret:<25} {period:<15} {next_rotation.strftime('%Y-%m-%d')}")


def check_rotation_status() -> None:
    """Verifie si des secrets doivent etre pivotes."""
    print_header("Statut de rotation des secrets")

    # Note: En production, vous devriez stocker la date de derniere rotation
    # dans le gestionnaire de secrets ou une base de donnees
    print("ATTENTION: Ce script ne peut pas verifier les dates reelles de rotation.")
    print("Implementez un suivi des dates de rotation dans votre gestionnaire de secrets.")
    print()
    print("Recommandations basees sur les periodes standards:")
    print()

    for secret, period in SecretRotationPolicy.ROTATION_PERIODS.items():
        print(f"  - {secret}: rotation tous les {period} jours")


def rotate_secret(secret_type: str, force: bool = False) -> None:
    """Effectue la rotation d'un secret."""
    rotator = get_secret_rotator()

    print_header(f"Rotation de secret: {secret_type.upper()}")

    if secret_type == "jwt":
        new_secret = rotator.rotate_jwt_secret()
        print(f"Nouveau JWT_SECRET genere:")
        print(f"  {new_secret}")
        print()
        print("ATTENTION: Tous les tokens JWT existants seront invalides!")
        print("Actions requises:")
        print("  1. Mettre a jour JWT_SECRET dans votre gestionnaire de secrets")
        print("  2. Redemarrer l'API")
        print("  3. Les utilisateurs devront se reconnecter")

    elif secret_type == "encryption":
        new_key = rotator.rotate_encryption_key()
        print(f"Nouvelle ENCRYPTION_KEY generee:")
        print(f"  {new_key}")
        print()
        print("ATTENTION: Les donnees chiffrees avec l'ancienne cle doivent etre migrees!")
        print("Actions requises:")
        print("  1. Sauvegarder l'ancienne ENCRYPTION_KEY")
        print("  2. Re-chiffrer les donnees sensibles (TOTP secrets, etc.)")
        print("  3. Mettre a jour ENCRYPTION_KEY dans le gestionnaire de secrets")
        print("  4. Redemarrer l'API")

    elif secret_type == "postgres":
        new_password = rotator.rotate_database_password()
        print(f"Nouveau POSTGRES_PASSWORD genere:")
        print(f"  {new_password}")
        print()
        print("Actions requises:")
        print("  1. Executer dans PostgreSQL:")
        print(f"     ALTER USER massa WITH PASSWORD '{new_password}';")
        print("  2. Mettre a jour POSTGRES_PASSWORD et DATABASE_URL")
        print("  3. Redemarrer l'API")

    elif secret_type == "redis":
        new_password = rotator.rotate_redis_password()
        print(f"Nouveau REDIS_PASSWORD genere:")
        print(f"  {new_password}")
        print()
        print("Actions requises:")
        print("  1. Mettre a jour REDIS_PASSWORD et REDIS_URL")
        print("  2. Redemarrer Redis avec: redis-server --requirepass <new_password>")
        print("  3. Redemarrer l'API")

    elif secret_type == "all":
        print("Rotation de tous les secrets...")
        print()

        rotated = rotator.rotate_all(force=force)

        if not rotated:
            print("Aucun secret a pivoter selon la politique actuelle.")
            print("Utilisez --force pour forcer la rotation.")
            return

        for name, value in rotated.items():
            print(f"{name}:")
            print(f"  {value}")
            print()

        print("=" * 60)
        print("ATTENTION: Mettez a jour tous ces secrets dans votre gestionnaire!")
        print("Suivez les instructions specifiques pour chaque type de secret.")

    else:
        print(f"Type de secret inconnu: {secret_type}")
        print("Types valides: jwt, encryption, postgres, redis, all")
        sys.exit(1)


def main() -> None:
    """Point d'entree principal."""
    parser = argparse.ArgumentParser(
        description="Gestionnaire de rotation des secrets MassaCorp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Lister les secrets et leur politique de rotation"
    )

    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Verifier si des secrets doivent etre pivotes"
    )

    parser.add_argument(
        "--rotate", "-r",
        metavar="TYPE",
        help="Pivoter un secret (jwt, encryption, postgres, redis, all)"
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Forcer la rotation meme si pas encore necessaire"
    )

    args = parser.parse_args()

    if args.list:
        list_secrets()
    elif args.check:
        check_rotation_status()
    elif args.rotate:
        rotate_secret(args.rotate, force=args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
