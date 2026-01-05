# MassaCorp API

API sécurisée multi-tenant avec isolation réseau WireGuard pour la gestion d'entreprise.

## Vue d'ensemble

MassaCorp est une plateforme SaaS B2B sécurisée offrant:
- **Multi-tenancy** : Isolation complète des données par organisation
- **Authentification avancée** : JWT, MFA (TOTP), SSO (OIDC/SAML)
- **RBAC** : Contrôle d'accès granulaire basé sur les rôles
- **Sécurité réseau** : VPN WireGuard obligatoire pour l'accès API
- **Audit complet** : Traçabilité de toutes les actions

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.12 + FastAPI |
| Base de données | PostgreSQL 16 |
| Cache | Redis 7 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| VPN | WireGuard |
| Conteneurisation | Docker + Docker Compose |
| Tests | pytest + pytest-asyncio |

## Structure du projet

```
MassaCorp/
├── app/                    # Application FastAPI principale
│   ├── api/               # Endpoints REST (routers)
│   ├── core/              # Configuration, sécurité, database
│   ├── models/            # Modèles SQLAlchemy
│   ├── repositories/      # Couche d'accès aux données
│   ├── schemas/           # Schémas Pydantic (validation)
│   └── main.py            # Point d'entrée de l'application
├── alembic/               # Migrations de base de données
│   └── versions/          # Fichiers de migration
├── db/                    # Scripts SQL et documentation DB
│   ├── api_keys/          # Authentification machine-to-machine
│   ├── audit/             # Journalisation centralisée
│   ├── auth/              # Sessions et tokens
│   ├── features/          # Feature flags
│   ├── mfa/               # Authentification multi-facteurs
│   ├── rbac/              # Rôles et permissions
│   ├── security/          # Protection anti-bruteforce
│   ├── sql/               # Scripts d'initialisation
│   ├── sso/               # Single Sign-On
│   └── wireguard/         # Configuration VPN DB
├── docker/                # Configurations Docker additionnelles
├── prod/                  # Configuration production
├── scripts/               # Scripts utilitaires
├── tests/                 # Tests automatisés
│   ├── unit/              # Tests unitaires
│   ├── integration/       # Tests d'intégration
│   ├── e2e/               # Tests end-to-end
│   └── factories/         # Factories de test
├── wireguard/             # Configuration VPN WireGuard
│   ├── config/            # Fichiers de configuration WG
│   └── scripts/           # Scripts de gestion WG
├── docker-compose.yml     # Orchestration développement
├── docker-compose.wireguard.yml  # Orchestration avec WireGuard
├── Dockerfile             # Image Docker de l'API
├── pyproject.toml         # Dépendances Python (Poetry)
└── alembic.ini            # Configuration Alembic
```

## Prérequis

- Python 3.12+
- Docker & Docker Compose
- Poetry (gestionnaire de dépendances Python)
- WireGuard (pour l'accès VPN)

## Installation rapide

### 1. Cloner et configurer l'environnement

```bash
# Cloner le projet
git clone <repository-url>
cd MassaCorp

# Copier et configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs
```

### 2. Démarrage avec Docker (recommandé)

```bash
# Démarrer les services (DB + API)
docker-compose up -d

# Vérifier les logs
docker-compose logs -f api

# L'API est accessible sur http://localhost:8000
```

### 3. Démarrage en développement local

```bash
# Installer les dépendances
poetry install

# Activer l'environnement virtuel
poetry shell

# Démarrer PostgreSQL via Docker
docker-compose up -d db

# Appliquer les migrations
alembic upgrade head

# Lancer l'API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

### Variables d'environnement principales

| Variable | Description | Défaut |
|----------|-------------|--------|
| `ENV` | Environnement (dev/staging/prod) | `dev` |
| `DATABASE_URL` | URL PostgreSQL | - |
| `JWT_SECRET` | Secret pour signer les JWT | - |
| `JWT_ALGORITHM` | Algorithme JWT | `HS256` |
| `ACCESS_TOKEN_LIFETIME` | Durée token d'accès (sec) | `900` |
| `REFRESH_TOKEN_LIFETIME` | Durée refresh token (sec) | `604800` |
| `ENCRYPTION_KEY` | Clé de chiffrement AES | - |
| `REDIS_URL` | URL Redis | - |
| `WG_NETWORK` | Réseau WireGuard | `10.10.0.0/24` |
| `LOG_LEVEL` | Niveau de log | `INFO` |

## Utilisation de l'API

### Endpoints disponibles

#### Base
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET | Page d'accueil |
| `/health` | GET | Health check |
| `/api/v1/info` | GET | Informations API + client |
| `/docs` | GET | Documentation Swagger (dev uniquement) |

#### Auth (`/api/v1/auth`)
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/login` | POST | Connexion utilisateur |
| `/logout` | POST | Déconnexion |
| `/refresh` | POST | Rafraîchir les tokens |
| `/me` | GET | Utilisateur courant |
| `/change-password` | POST | Changer mot de passe |
| `/verify-token` | POST | Vérifier validité token |

#### Users (`/api/v1/users`)
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET/POST | Liste / Créer utilisateur |
| `/{id}` | GET/PUT/DELETE | CRUD utilisateur |
| `/{id}/activate` | POST | Activer compte |
| `/{id}/deactivate` | POST | Désactiver compte |

#### Sessions (`/api/v1/sessions`)
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/` | GET/DELETE | Liste / Terminer toutes |
| `/{id}` | GET/DELETE | Détail / Terminer session |

#### MFA (`/api/v1/mfa`)
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/setup` | POST | Configurer MFA (QR code) |
| `/enable` | POST | Activer MFA |
| `/disable` | POST | Désactiver MFA |
| `/status` | GET | Status MFA |
| `/verify` | POST | Vérifier code TOTP |
| `/recovery/verify` | POST | Utiliser code récupération |
| `/recovery/regenerate` | POST | Régénérer codes |

### Exemple de requête

```bash
curl http://localhost:8000/health
```

Réponse:
```json
{
  "status": "healthy",
  "environment": "dev",
  "wireguard_network": "10.10.0.0/24"
}
```

## Tests

```bash
# Exécuter tous les tests
pytest

# Tests unitaires uniquement
pytest tests/unit/

# Tests avec couverture
pytest --cov=app --cov-report=html

# Tests spécifiques
pytest tests/unit/test_security.py -v
```

## Architecture de sécurité

### Authentification

1. **JWT Tokens**
   - Access token: 15 minutes
   - Refresh token: 7 jours
   - Algorithme: HS256

2. **Mots de passe**
   - Hachage: bcrypt (cost factor 12)
   - Règles: 8+ caractères, majuscule, minuscule, chiffre, spécial

3. **MFA**
   - TOTP (Google Authenticator, Authy)
   - Recovery codes

### Isolation réseau

L'API est accessible uniquement via le tunnel WireGuard:
- Réseau VPN: `10.10.0.0/24`
- Serveur API: `10.10.0.1`
- Clients authentifiés: `10.10.0.2-254`

## Conformité

- **RGPD**: Audit trail, droit d'accès, droit à l'oubli
- **SOC2**: Logging complet, contrôle d'accès
- **ISO 27001**: Traçabilité, MFA, RBAC

## Contribuer

1. Créer une branche feature
2. Écrire des tests pour les nouvelles fonctionnalités
3. S'assurer que tous les tests passent
4. Respecter les conventions de code (black, ruff)
5. Créer une Pull Request

## Roadmap

### Phases complétées

- [x] **Phase 1: Foundation** - Authentification JWT, utilisateurs, tenants
- [x] **Phase 2: Sessions & Security** - Sessions, refresh tokens, audit logging, rate limiting
- [x] **Phase 3: MFA** - TOTP (pyotp), recovery codes, 7 endpoints MFA

### En cours / Planifié

- [ ] **Phase 4: RBAC** - Rôles, permissions, hiérarchie
- [ ] **Phase 5: API Keys & Features** - Auth M2M, feature flags
- [ ] **Phase 6: WireGuard API** - Gestion dynamique des peers
- [ ] SSO (OIDC/SAML)
- [ ] Dashboard admin

## État des tests

```
Tests unitaires:    428 passed
Tests intégration:   39 passed
Total:              467 passed
```

## License

Proprietary - MassaCorp Team

---

**Version**: 0.1.0
**Auteurs**: MassaCorp Team
