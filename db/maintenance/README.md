# Maintenance Module

## Vue d'ensemble
Module de maintenance et nettoyage automatise de la base de donnees.
Assure la performance et la conformite en supprimant les donnees obsoletes.

## Scripts

### `cleanup.sql`
Script de purge des donnees expirees/obsoletes.

```sql
-- Tentatives de connexion > 30 jours
DELETE FROM login_attempts
WHERE attempted_at < NOW() - INTERVAL '30 days';

-- Logs d'audit > 12 mois
DELETE FROM audit_log
WHERE created_at < NOW() - INTERVAL '12 months';

-- Sessions SSO revoquees > 90 jours
DELETE FROM sso_sessions
WHERE revoked_at IS NOT NULL
  AND revoked_at < NOW() - INTERVAL '90 days';

-- Cles API expirees
DELETE FROM api_keys
WHERE expires_at IS NOT NULL
  AND expires_at < NOW();
```

## Politiques de retention

| Table | Retention | Justification |
|-------|-----------|---------------|
| `login_attempts` | 30 jours | Suffisant pour detecter les attaques |
| `audit_log` | 12 mois | Conformite RGPD/SOC2 |
| `sso_sessions` (revoquees) | 90 jours | Historique de securite |
| `api_keys` (expirees) | Immediate | Securite |
| `refresh_tokens` (expires) | 7 jours | Cleanup tokens obsoletes |
| `revoked_tokens` | Jusqu'a expiration | Necesaire pour blacklist |

## Sous-dossier `cleanup_fichiers/`

Contient des fichiers temporaires a nettoyer (assets, exports, etc.).

**Types de fichiers presents:**
- Images (`.jpeg`, `.png`)
- CSS temporaires
- Fichiers d'export

**Action recommandee:**
Executer un cleanup periodique de ce dossier ou le supprimer si non necessaire.

## Planification recommandee

### Cron job quotidien (03:00 UTC)
```bash
#!/bin/bash
# /etc/cron.d/massadb-cleanup

0 3 * * * postgres psql -d massadb -f /path/to/db/maintenance/cleanup.sql >> /var/log/massadb-cleanup.log 2>&1
```

### Avec pg_cron (recommande)
```sql
-- Installer pg_cron
CREATE EXTENSION pg_cron;

-- Planifier le cleanup quotidien
SELECT cron.schedule('daily-cleanup', '0 3 * * *', $$
    DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '30 days';
    DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '12 months';
    DELETE FROM sso_sessions WHERE revoked_at IS NOT NULL AND revoked_at < NOW() - INTERVAL '90 days';
    DELETE FROM api_keys WHERE expires_at IS NOT NULL AND expires_at < NOW();
$$);
```

## Vacuum et maintenance PostgreSQL

### Apres cleanup massif
```sql
-- Recuperer l'espace disque
VACUUM FULL login_attempts;
VACUUM FULL audit_log;
VACUUM FULL sso_sessions;
VACUUM FULL api_keys;

-- Mettre a jour les statistiques
ANALYZE;
```

### Configuration autovacuum recommandee
```sql
-- Pour les tables a forte rotation
ALTER TABLE login_attempts SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE audit_log SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);
```

## Monitoring

### Taille des tables
```sql
SELECT
    relname as table_name,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as data_size,
    pg_size_pretty(pg_indexes_size(relid)) as index_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### Estimation du cleanup
```sql
SELECT
    'login_attempts' as table_name,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE attempted_at < NOW() - INTERVAL '30 days') as to_delete
FROM login_attempts
UNION ALL
SELECT
    'audit_log',
    COUNT(*),
    COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '12 months')
FROM audit_log;
```

## Relations avec autres modules

- **audit/** : Gestion de la retention des logs
- **security/** : Cleanup des tentatives de connexion
- **sso/** : Cleanup des sessions SSO
- **api_keys/** : Suppression des cles expirees

## Alertes recommandees

1. **Taille DB** : Alerte si > 80% de l'espace disque
2. **Croissance anormale** : Alerte si `audit_log` croit > 10% par jour
3. **Echec cleanup** : Alerte si le cron echoue
