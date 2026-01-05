# SQL Module

## Vue d'ensemble
Point d'entree centralise pour l'initialisation de la base de donnees.
Contient le script d'orchestration qui charge tous les modules dans le bon ordre.

## Fichiers

### `00_init.sql`
Script maitre d'initialisation. Utilise `\i` pour inclure les scripts des autres modules
dans l'ordre correct (respect des dependances FK).

### `00_init_flat.sql`
Version "aplatie" contenant toutes les definitions SQL en un seul fichier.
Utile pour les environnements ou `\i` n'est pas supporte (certains ORM, migrations).

## Ordre d'initialisation

L'ordre est critique pour respecter les contraintes de cles etrangeres:

```sql
-- 1. Auth (base, pas de FK externes)
\i db/sql/auth/revoked_tokens.sql
\i db/sql/auth/sessions.sql
\i db/sql/auth/refresh_tokens.sql    -- FK: sessions

-- 2. Audit & Security (pas de FK)
\i db/sql/audit/audit_log.sql
\i db/sql/security/login_attempts.sql

-- 3. MFA (pas de FK externes)
\i db/sql/mfa/mfa_secrets.sql
\i db/sql/mfa/mfa_recovery_codes.sql

-- 4. SSO (pas de FK)
\i db/sql/sso/identity_providers.sql
\i db/sql/sso/user_identities.sql
\i db/sql/sso/sso_sessions.sql

-- 5. API Keys (base pour RBAC)
\i db/sql/api_keys/api_keys.sql
\i db/sql/api_keys/api_key_usage.sql  -- FK: api_keys

-- 6. RBAC (FK: api_keys)
\i db/sql/rbac/roles.sql
\i db/sql/rbac/permissions.sql
\i db/sql/rbac/role_permissions.sql   -- FK: roles, permissions
\i db/sql/rbac/user_roles.sql         -- FK: roles
\i db/sql/rbac/api_key_roles.sql      -- FK: api_keys, roles
\i db/sql/rbac/role_hierarchy.sql     -- FK: roles

-- 7. Features (FK: features table first)
\i db/sql/features/features.sql
\i db/sql/features/feature_flags_global.sql   -- FK: features
\i db/sql/features/feature_flags_tenant.sql   -- FK: features
\i db/sql/features/feature_flags_role.sql     -- FK: features
\i db/sql/features/feature_flags_user.sql     -- FK: features
```

## Usage

### Initialisation complete
```bash
psql -d massadb -f db/sql/00_init.sql
```

### Avec fichier aplati
```bash
psql -d massadb -f db/sql/00_init_flat.sql
```

### Via Docker
```bash
docker exec -i postgres psql -U postgres -d massadb < db/sql/00_init_flat.sql
```

## Generation du fichier aplati

Pour regenerer `00_init_flat.sql` apres modifications:

```bash
#!/bin/bash
# generate_flat.sh

cat > db/sql/00_init_flat.sql << 'HEADER'
-- ================================================
-- MassaCorp Database Schema (Flat Version)
-- Generated: $(date)
-- ================================================

HEADER

for module in auth audit security mfa sso api_keys rbac features; do
    echo "-- ========== Module: $module ==========" >> db/sql/00_init_flat.sql
    for file in db/$module/*.sql; do
        echo "-- Source: $file" >> db/sql/00_init_flat.sql
        cat "$file" >> db/sql/00_init_flat.sql
        echo "" >> db/sql/00_init_flat.sql
    done
done
```

## Migrations (Alembic)

Le projet utilise Alembic pour les migrations incrementales.
Voir le dossier `alembic/` pour:
- `alembic.ini` - Configuration
- `alembic/versions/` - Fichiers de migration

### Workflow migrations
```bash
# Creer une nouvelle migration
alembic revision --autogenerate -m "Add new column"

# Appliquer les migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Relations avec autres modules

Ce module est le point d'entree qui orchestre tous les autres:
- **auth/** : Authentification et sessions
- **audit/** : Logs d'audit
- **security/** : Protection bruteforce
- **mfa/** : Authentification multi-facteurs
- **sso/** : Single Sign-On
- **api_keys/** : Gestion des cles API
- **rbac/** : Controle d'acces base sur les roles
- **features/** : Feature flags

## Environnements

| Environnement | Methode |
|---------------|---------|
| Development | `00_init.sql` direct |
| CI/CD | `00_init_flat.sql` |
| Production | Alembic migrations |
| Docker | `00_init_flat.sql` dans entrypoint |
