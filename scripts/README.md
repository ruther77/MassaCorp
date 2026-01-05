# Scripts Utilitaires - MassaCorp

Scripts shell pour l'administration et la maintenance de MassaCorp.

## Structure

```
scripts/
└── db_init.sh      # Initialisation de la base de données
```

## Scripts disponibles

### db_init.sh

Initialise la base de données avec le schéma complet.

**Usage:**
```bash
# Avec DATABASE_URL définie
export DATABASE_URL="postgresql://user:pass@host:5432/db"
./scripts/db_init.sh

# Ou via Docker
docker exec -it massacorp_db ./scripts/db_init.sh
```

**Prérequis:**
- Variable `DATABASE_URL` obligatoire
- `psql` installé et accessible
- Accès à `db/sql/00_init.sql`

## Scripts dans app/scripts/

Les scripts Python pour l'application sont dans `app/scripts/`:

| Script | Description |
|--------|-------------|
| `seed.py` | Initialise les données de base (admin, tenants) |

**Usage seed.py:**
```bash
# Via Docker
docker exec massacorp_api python -m app.scripts.seed

# En local
python -m app.scripts.seed
```
