# Infrastructure Docker - MassaCorp

Configuration Docker et Docker Compose pour le déploiement de MassaCorp.

## Structure

```
Fichiers racine:
├── Dockerfile                    # Image de l'API FastAPI
├── docker-compose.yml            # Développement (DB + API)
├── docker-compose.wireguard.yml  # Production (isolation complète)
└── .env                          # Variables d'environnement

docker/
├── README.md                     # Ce fichier
└── entrypoint.sh                 # Script de démarrage du container

prod/
├── DATABASE_URL                  # Secret production
└── JWT_SECRET                    # Secret production
```

## Modes de déploiement

### 1. Développement (`docker-compose.yml`)

Mode simplifié pour le développement local.

```bash
# Démarrer
docker-compose up -d

# Logs
docker-compose logs -f api

# Arrêter
docker-compose down
```

**Services:**
| Service | Port exposé | Description |
|---------|-------------|-------------|
| `db` | 5432 | PostgreSQL 16 |
| `api` | 8000 | API FastAPI (hot reload) |

### 2. Production (`docker-compose.wireguard.yml`)

Mode sécurisé avec isolation WireGuard complète.

```bash
# Démarrer
docker-compose -f docker-compose.wireguard.yml up -d

# Logs
docker-compose -f docker-compose.wireguard.yml logs -f

# Arrêter
docker-compose -f docker-compose.wireguard.yml down
```

**Services:**
| Service | IP interne | Port exposé | Description |
|---------|------------|-------------|-------------|
| `wireguard` | 10.10.0.1 | 51820/udp | VPN (seul point d'entrée) |
| `api` | 10.10.0.2 | aucun | API FastAPI |
| `db` | 10.10.0.3 | aucun | PostgreSQL 16 |
| `wg-sync` | 10.10.0.4 | aucun | Sync peers |
| `redis` | 10.10.0.5 | aucun | Cache/sessions |

## Dockerfile

```dockerfile
FROM python:3.12-slim

# Variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système (PostgreSQL)
RUN apt-get update && apt-get install -y \
    build-essential gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python via Poetry
COPY pyproject.toml poetry.lock* /app/
RUN pip install poetry && poetry install

# Code source
COPY . /app

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
```

## Variables d'environnement

### Développement (.env)

```bash
# Application
ENV=dev
LOG_LEVEL=DEBUG
APP_NAME=MassaCorp API
APP_VERSION=0.1.0

# Base de données
POSTGRES_DB=MassaCorp
POSTGRES_USER=massa
POSTGRES_PASSWORD=jemmysev
DATABASE_URL=postgresql+psycopg2://massa:jemmysev@db:5432/MassaCorp

# Sécurité
JWT_SECRET=CHANGER_EN_PRODUCTION_MIN_32_CARACTERES
JWT_ALGORITHM=HS256
ENCRYPTION_KEY=CHANGER_CLE_CHIFFREMENT_32_OCTETS

# Redis
REDIS_PASSWORD=massacorp_redis_secret
REDIS_URL=redis://:massacorp_redis_secret@10.10.0.5:6379/0

# WireGuard
WG_NETWORK=10.10.0.0/24
WG_SERVER_URL=vpn.massacorp.com
WG_LISTEN_PORT=51820
```

### Production

Utiliser des secrets Docker ou des fichiers séparés:

```bash
# prod/DATABASE_URL
postgresql+psycopg2://user:STRONG_PASSWORD@10.10.0.3:5432/MassaCorp

# prod/JWT_SECRET
VOTRE_SECRET_TRES_LONG_ET_ALEATOIRE_MINIMUM_32_CARACTERES
```

## Commandes courantes

### Build

```bash
# Reconstruire l'image
docker-compose build

# Sans cache
docker-compose build --no-cache
```

### Exécution

```bash
# Démarrer en arrière-plan
docker-compose up -d

# Voir les logs en temps réel
docker-compose logs -f

# Logs d'un service spécifique
docker-compose logs -f api
```

### Accès aux containers

```bash
# Shell dans le container API
docker exec -it massacorp_api bash

# Shell PostgreSQL
docker exec -it massacorp_db psql -U massa -d MassaCorp

# Exécuter une commande
docker exec massacorp_api alembic upgrade head
```

### Maintenance

```bash
# Redémarrer un service
docker-compose restart api

# Arrêter et supprimer
docker-compose down

# Supprimer avec les volumes (ATTENTION: perte de données)
docker-compose down -v

# Nettoyer les images non utilisées
docker system prune -a
```

## Architecture réseau

### Développement

```
┌─────────────┐      ┌─────────────┐
│   Client    │      │   Client    │
│ :8000 HTTP  │      │ :5432 PG    │
└──────┬──────┘      └──────┬──────┘
       │                    │
       ▼                    ▼
┌─────────────┐      ┌─────────────┐
│     API     │──────│      DB     │
│ massacorp_  │      │ massacorp_  │
│    api      │      │     db      │
└─────────────┘      └─────────────┘
```

### Production (WireGuard)

```
                     INTERNET
                         │
                         │ :51820/UDP
                         ▼
                  ┌─────────────┐
                  │  WireGuard  │
                  │  10.10.0.1  │
                  └──────┬──────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌───────────┐   ┌───────────┐   ┌───────────┐
   │    API    │   │    DB     │   │   Redis   │
   │ 10.10.0.2 │   │ 10.10.0.3 │   │ 10.10.0.5 │
   └───────────┘   └───────────┘   └───────────┘

   ========= RÉSEAU ISOLÉ (10.10.0.0/24) =========
```

## Healthchecks

Tous les services ont des healthchecks configurés:

| Service | Test | Intervalle |
|---------|------|------------|
| `db` | `pg_isready` | 5s |
| `api` | HTTP /health | 30s |
| `wireguard` | `wg show` | 30s |
| `redis` | `redis-cli ping` | 10s |

## Volumes persistants

| Volume | Contenu | Chemin dans container |
|--------|---------|----------------------|
| `pgdata` | Données PostgreSQL | /var/lib/postgresql/data |
| `redisdata` | Données Redis | /data |

## Dépannage

### Container ne démarre pas

```bash
# Voir les logs
docker-compose logs api

# Vérifier l'état
docker-compose ps

# Inspecter le container
docker inspect massacorp_api
```

### Problème de connexion DB

```bash
# Vérifier que DB est prête
docker exec massacorp_db pg_isready -U massa

# Tester la connexion
docker exec massacorp_api python -c "from app.core.database import engine; print(engine.connect())"
```

### Problème de permissions

```bash
# Fixer les permissions des volumes
sudo chown -R 1000:1000 ./wireguard/config
```

### Réseau

```bash
# Lister les réseaux
docker network ls

# Inspecter le réseau
docker network inspect massacorp_wg_network

# Tester la connectivité
docker exec massacorp_api ping -c 3 10.10.0.3
```
