# Alembic - Migrations de Base de Données

Gestion des migrations de schéma PostgreSQL pour MassaCorp.

## Structure du dossier

```
alembic/
├── README.md           <- Ce fichier
├── env.py              <- Configuration d'environnement Alembic
├── script.py.mako      <- Template pour les migrations
└── versions/           <- Fichiers de migration
    ├── c3bee0e2b93b_initial_schema.py
    └── d4cf1a3e5f7c_add_tenants_users.py
```

## Configuration

### alembic.ini (racine du projet)

Fichier de configuration principal. L'URL de la base de données est lue depuis la variable d'environnement `DATABASE_URL`.

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
```

### env.py

Configure la connexion à la base de données et importe les modèles pour l'autogenerate.

```python
# Pour activer l'autogenerate, décommenter:
from app.core.database import Base
target_metadata = Base.metadata
```

## Commandes courantes

### Appliquer les migrations

```bash
# Appliquer toutes les migrations en attente
alembic upgrade head

# Appliquer jusqu'à une révision spécifique
alembic upgrade abc123

# Appliquer N migrations suivantes
alembic upgrade +1
```

### Voir l'état

```bash
# Version actuelle de la DB
alembic current

# Historique des migrations
alembic history

# Migrations en attente
alembic history --indicate-current
```

### Créer une migration

```bash
# Migration manuelle (vide)
alembic revision -m "description_de_la_migration"

# Migration auto-générée (compare modèles vs DB)
alembic revision --autogenerate -m "add_new_table"
```

### Annuler une migration

```bash
# Revenir à la migration précédente
alembic downgrade -1

# Revenir à une révision spécifique
alembic downgrade abc123

# Tout annuler (attention!)
alembic downgrade base
```

## Écrire une migration

### Structure d'un fichier de migration

```python
"""Description de la migration

Revision ID: abc123def456
Revises: previous_revision_id
Create Date: 2024-01-01 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# Identifiants de révision
revision = 'abc123def456'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Appliquer la migration"""
    op.create_table(
        'example',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Annuler la migration"""
    op.drop_table('example')
```

### Opérations courantes

#### Créer une table

```python
def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), sa.ForeignKey('tenants.id')),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email')
    )
```

#### Modifier une colonne

```python
def upgrade():
    # Ajouter une colonne
    op.add_column('users', sa.Column('phone', sa.Text()))

    # Modifier une colonne
    op.alter_column('users', 'email', nullable=False)

    # Renommer une colonne
    op.alter_column('users', 'name', new_column_name='full_name')

def downgrade():
    op.drop_column('users', 'phone')
```

#### Créer un index

```python
def upgrade():
    # Index simple
    op.create_index('ix_users_email', 'users', ['email'])

    # Index unique
    op.create_index('ix_users_tenant_email', 'users', ['tenant_id', 'email'], unique=True)

    # Index partiel (PostgreSQL)
    op.create_index(
        'ix_users_active',
        'users',
        ['email'],
        postgresql_where=sa.text('is_active = true')
    )

def downgrade():
    op.drop_index('ix_users_email')
```

#### Exécuter du SQL brut

```python
def upgrade():
    # Pour des opérations complexes
    op.execute("""
        CREATE INDEX CONCURRENTLY ix_large_table_column
        ON large_table (column)
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_large_table_column")
```

## Migrations existantes

| Révision | Phase | Description | Tables |
|----------|-------|-------------|--------|
| `c3bee0e2b93b` | 1 | Schéma initial | - |
| `d4cf1a3e5f7c` | 1 | Ajout tenants et users | `tenants`, `users` |
| `e5a72b8c9d0f` | 2 | Ajout sessions.updated_at | `sessions` |

## Bonnes pratiques

### 1. Toujours écrire le downgrade

```python
def downgrade():
    # Même si vous pensez ne jamais l'utiliser
    op.drop_table('new_table')
```

### 2. Une migration = une modification logique

```python
# Bon: une migration par fonctionnalité
"add_users_table"
"add_user_email_index"
"add_user_mfa_columns"

# Mauvais: tout dans une migration
"add_users_and_tenants_and_roles_and_permissions"
```

### 3. Tester avant de merger

```bash
# Appliquer
alembic upgrade head

# Vérifier
alembic current

# Annuler
alembic downgrade -1

# Ré-appliquer
alembic upgrade head
```

### 4. Migrations en production

```bash
# Toujours faire une sauvegarde avant
pg_dump -d MassaCorp > backup_before_migration.sql

# Appliquer
alembic upgrade head

# Vérifier les logs
```

### 5. Éviter les migrations destructives

```python
# Dangereux: perte de données
op.drop_column('users', 'important_data')

# Mieux: renommer puis supprimer plus tard
op.alter_column('users', 'important_data', new_column_name='deprecated_data')
```

## Dépannage

### La migration échoue

```bash
# Voir l'état actuel
alembic current

# Voir l'historique
alembic history -v

# Marquer comme appliquée (si déjà fait manuellement)
alembic stamp abc123
```

### Conflits de révisions

```bash
# Après un merge avec conflits
alembic merge -m "merge_branches" abc123 def456
```

### Désynchronisation

```bash
# Si la DB est en avance sur le code
alembic stamp head

# Si la DB est en retard
alembic upgrade head
```

## Environnements

### Développement

```bash
# Utiliser DATABASE_URL de .env
source .env
alembic upgrade head
```

### Docker

```bash
# Via docker-compose (automatique au démarrage)
# Voir docker-compose.yml: "alembic upgrade head && uvicorn..."

# Manuellement
docker exec massacorp_api alembic upgrade head
```

### Production

```bash
# Via variable d'environnement
DATABASE_URL=postgresql://user:pass@prod-db:5432/MassaCorp alembic upgrade head
```
