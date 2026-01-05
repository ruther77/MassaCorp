# Scripts - Utilitaires MassaCorp

Scripts d'administration et d'initialisation de la base de données.

## Structure

```
scripts/
├── __init__.py          # Package Python
├── README.md            # Ce fichier
└── seed.py              # Script de seed (tenants + admin)
```

## Scripts disponibles

### seed.py - Initialisation des données

Script idempotent pour créer les données de base (tenants et admin initial).

**Fonctionnalités:**
- Création des tenants par défaut (Epicerie, Restaurant, Autre)
- Création de l'utilisateur admin avec mot de passe sécurisé
- Vérification préalable des tables (migrations)
- Idempotent: peut être relancé sans effet si données existent

**Usage:**

```bash
# Depuis la racine du projet
python -m app.scripts.seed

# Depuis Docker
docker exec massacorp_api python -m app.scripts.seed
```

**Sortie attendue:**

```
============================================================
           MassaCorp - Script de Seed
============================================================

Verification des tables...
  ✓ Tables OK

[1/2] Creation des tenants...
  ✓ Tenant 'Epicerie' cree (ID: 1)
  ✓ Tenant 'Restaurant' cree (ID: 2)
  ✓ Tenant 'Autre' cree (ID: 3)

[2/2] Creation de l'admin...
  ✓ Admin 'admin@massacorp.dev' cree (ID: 1)

============================================================
                    RESUME DU SEED
============================================================

Tenants:
  - Epicerie (slug: epicerie, ID: 1)
  - Restaurant (slug: restaurant, ID: 2)
  - Autre (slug: autre, ID: 3)

------------------------------------------------------------
   ATTENTION: Conservez ces informations en lieu sur!
------------------------------------------------------------

  Admin Email:    admin@massacorp.dev
  Admin Password: xK7#mP2$vL9@nQ4!
  Tenant:         epicerie (ID: 1)

  Ce mot de passe ne sera plus affiche!
------------------------------------------------------------

============================================================
                 Seed termine avec succes!
============================================================
```

**Configuration du seed:**

| Variable | Valeur | Description |
|----------|--------|-------------|
| `SEED_TENANTS` | Epicerie, Restaurant, Autre | Tenants à créer |
| `SEED_ADMIN.email` | admin@massacorp.dev | Email de l'admin |
| `SEED_ADMIN.is_superuser` | True | Droits superuser |

## Sécurité

### Génération du mot de passe

Le mot de passe admin est généré de manière sécurisée:
- 20 caractères
- Contient: majuscules, minuscules, chiffres, caractères spéciaux
- Utilise `secrets` (CSPRNG)
- N'est affiché qu'une seule fois

```python
def generate_secure_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = [
        secrets.choice(string.ascii_uppercase),  # 1 majuscule
        secrets.choice(string.ascii_lowercase),  # 1 minuscule
        secrets.choice(string.digits),           # 1 chiffre
        secrets.choice("!@#$%^&*"),              # 1 spécial
    ]
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(password)
    return "".join(password)
```

## Workflow de déploiement

```bash
# 1. Appliquer les migrations
alembic upgrade head

# 2. Exécuter le seed
python -m app.scripts.seed

# 3. (Optionnel) Vérifier les données
docker exec massacorp_db psql -U massa -d MassaCorp -c "SELECT * FROM tenants;"
docker exec massacorp_db psql -U massa -d MassaCorp -c "SELECT id, email, is_superuser FROM users;"
```

## Prérequis

1. Base de données PostgreSQL accessible
2. Tables créées via migrations Alembic
3. Variable `DATABASE_URL` configurée

## Créer un nouveau script

```python
# app/scripts/mon_script.py
"""
Description du script
"""
import sys
from app.core.database import SessionLocal

def main():
    session = SessionLocal()
    try:
        # Logique du script
        session.commit()
        return 0
    except Exception as e:
        session.rollback()
        print(f"Erreur: {e}")
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    sys.exit(main())
```

Exécution:
```bash
python -m app.scripts.mon_script
```
