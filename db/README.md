# MassaCorp Database Architecture

## Vue d'ensemble

Schema de base de donnees PostgreSQL complet pour une application SaaS multi-tenant
avec authentification avancee, RBAC, SSO, et feature flags.

```
db/
├── README.md              <- Ce fichier
├── api_keys/              <- Gestion des cles API (M2M)
│   ├── README.md
│   ├── api_keys.sql
│   └── api_key_usage.sql
├── audit/                 <- Journalisation centralisee
│   ├── README.md
│   └── audit_log.sql
├── auth/                  <- Authentification (sessions, tokens)
│   ├── README.md
│   ├── sessions.sql
│   ├── refresh_tokens.sql
│   └── revoked_tokens.sql
├── features/              <- Feature flags multi-niveaux
│   ├── README.md
│   ├── features.sql
│   ├── feature_flags_global.sql
│   ├── feature_flags_tenant.sql
│   ├── feature_flags_role.sql
│   └── feature_flags_user.sql
├── maintenance/           <- Scripts de maintenance
│   ├── README.md
│   ├── cleanup.sql
│   └── cleanup_fichiers/
├── mfa/                   <- Authentification multi-facteurs
│   ├── README.md
│   ├── mfa_secrets.sql
│   └── mfa_recovery_codes.sql
├── rbac/                  <- Role-Based Access Control
│   ├── README.md
│   ├── roles.sql
│   ├── permissions.sql
│   ├── role_permissions.sql
│   ├── user_roles.sql
│   ├── api_key_roles.sql
│   └── role_hierarchy.sql
├── security/              <- Protection anti-bruteforce
│   ├── README.md
│   └── login_attempts.sql
├── sql/                   <- Scripts d'initialisation
│   ├── README.md
│   ├── 00_init.sql
│   └── 00_init_flat.sql
├── sso/                   <- Single Sign-On (OIDC/SAML)
│   ├── README.md
│   ├── identity_providers.sql
│   ├── user_identities.sql
│   └── sso_sessions.sql
└── wireguard/             <- Gestion VPN WireGuard
    ├── README.md
    └── wg_peers.sql
```

## Modules

| Module | Description | Tables |
|--------|-------------|--------|
| **api_keys** | Authentification machine-to-machine | `api_keys`, `api_key_usage` |
| **audit** | Tracabilite complete des actions | `audit_log` |
| **auth** | Sessions et tokens JWT | `sessions`, `refresh_tokens`, `revoked_tokens` |
| **features** | Feature flags granulaires | `features`, `feature_flags_*` |
| **maintenance** | Nettoyage automatise | Scripts de purge |
| **mfa** | TOTP + recovery codes | `mfa_secrets`, `mfa_recovery_codes` |
| **rbac** | Controle d'acces base sur roles | `roles`, `permissions`, `*_roles` |
| **security** | Protection bruteforce | `login_attempts` |
| **sql** | Initialisation DB | Scripts d'init |
| **sso** | Federation OIDC/SAML | `identity_providers`, `user_identities`, `sso_sessions` |
| **wireguard** | VPN et isolation reseau | `wg_peers`, `wg_server_config`, `wg_ip_pool`, `wg_access_rules` |

## Diagramme des relations

```
                                    ┌─────────────┐
                                    │   tenants   │ (externe)
                                    └─────────────┘
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              │                            │                            │
              ▼                            ▼                            ▼
       ┌─────────────┐              ┌─────────────┐              ┌─────────────┐
       │    users    │ (externe)    │   api_keys  │              │    roles    │
       └─────────────┘              └─────────────┘              └─────────────┘
              │                            │                            │
    ┌─────────┼─────────┐                  │                   ┌────────┼────────┐
    │         │         │                  │                   │        │        │
    ▼         ▼         ▼                  ▼                   ▼        ▼        ▼
┌────────┐ ┌────────┐ ┌──────────┐  ┌─────────────┐     ┌─────────┐ ┌────────┐ ┌──────────┐
│sessions│ │mfa_    │ │user_     │  │api_key_usage│     │role_    │ │user_   │ │api_key_  │
│        │ │secrets │ │identities│  └─────────────┘     │perms    │ │roles   │ │roles     │
└────────┘ └────────┘ └──────────┘                      └─────────┘ └────────┘ └──────────┘
    │                       │                                 │
    ▼                       │                                 ▼
┌────────────┐              │                           ┌───────────┐
│refresh_    │              │                           │permissions│
│tokens      │              │                           └───────────┘
└────────────┘              │
                            ▼
                     ┌─────────────────┐
                     │identity_providers│
                     └─────────────────┘
```

## Quick Start

### 1. Initialisation complete
```bash
# Via psql
psql -d massadb -f db/sql/00_init_flat.sql

# Via Docker
docker exec -i postgres psql -U postgres -d massadb < db/sql/00_init_flat.sql
```

### 2. Migrations incrementales
```bash
# Avec Alembic
alembic upgrade head
```

### 3. Verifier l'installation
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

## Architecture multi-tenant

Toutes les tables principales incluent un `tenant_id` pour l'isolation des donnees:

```sql
-- Exemple de requete tenant-safe
SELECT * FROM api_keys
WHERE tenant_id = :current_tenant_id
  AND revoked_at IS NULL;
```

**Row-Level Security (optionnel):**
```sql
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON api_keys
    USING (tenant_id = current_setting('app.current_tenant')::bigint);
```

## Securite

### Donnees sensibles chiffrees
- `api_keys.key_hash` - Hash SHA-256/Argon2
- `mfa_secrets.secret` - Chiffre AES-256-GCM
- `identity_providers.client_secret` - Chiffre AES-256-GCM
- `mfa_recovery_codes.code_hash` - Hash SHA-256

### Jamais stockes en clair
- Mots de passe
- Cles API
- Secrets TOTP
- Recovery codes
- Client secrets SSO

## Performance

### Index partiels (filtres frequents)
```sql
-- Sessions actives uniquement
CREATE INDEX sessions_active_idx ON sessions (id) WHERE revoked_at IS NULL;

-- Tokens non expires
CREATE INDEX revoked_tokens_active_idx ON revoked_tokens (jti) WHERE expires_at > NOW();
```

### Partitionnement (pour tables volumineuses)
```sql
-- Exemple: audit_log par mois
CREATE TABLE audit_log (
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_log_2024_01 PARTITION OF audit_log
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## Conformite

| Standard | Support |
|----------|---------|
| **RGPD** | Audit trail, droit d'acces, droit a l'oubli |
| **SOC2** | Logging complet, controle d'acces |
| **ISO 27001** | Tracabilite, MFA, RBAC |
| **HIPAA** | Audit, chiffrement, acces minimum |

## Maintenance

### Taches quotidiennes (03:00 UTC)
- Cleanup `login_attempts` > 30 jours
- Cleanup `audit_log` > 12 mois
- Cleanup sessions SSO revoquees > 90 jours
- Cleanup API keys expirees

### Taches hebdomadaires
- VACUUM ANALYZE sur tables volumineuses
- Verification des index inutilises
- Rapport de croissance des tables

## Documentation detaillee

Chaque module possede son propre README avec:
- Description des tables et colonnes
- Index et leur justification
- Requetes utiles
- Flux de donnees
- Bonnes pratiques

Consulter les fichiers `README.md` dans chaque sous-dossier.

## Roadmap

- [x] Integration WireGuard (Docker-managed) - FAIT
- [ ] Partitionnement automatique audit_log
- [ ] Compression des anciennes donnees
- [ ] Replication read-replicas
- [ ] Backup incremental automatise
