-- db/sql/01_autovacuum.sql
-- Configuration autovacuum optimisee pour MassaCorp
-- Execute apres l'init du schema

BEGIN;

-- =====================================================
-- AUTOVACUUM CONFIGURATION PAR TABLE
-- =====================================================

-- Tables a haute frequence d'ecriture: autovacuum plus agressif

-- login_attempts: beaucoup d'insertions, nettoyage frequent
ALTER TABLE login_attempts SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 50
);

-- audit_log: insertions constantes
ALTER TABLE audit_log SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 100
);

-- sessions: creations/revocations frequentes
ALTER TABLE sessions SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_threshold = 50
);

-- refresh_tokens: rotation constante
ALTER TABLE refresh_tokens SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_threshold = 50
);

-- revoked_tokens: insertions avec TTL
ALTER TABLE revoked_tokens SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_threshold = 100
);

-- api_key_usage: beaucoup d'insertions
ALTER TABLE api_key_usage SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 100
);


-- =====================================================
-- INDEX MAINTENANCE FUNCTION
-- =====================================================

-- Fonction pour reindexer les tables critiques
CREATE OR REPLACE FUNCTION maintenance_reindex_critical()
RETURNS void AS $$
BEGIN
    -- Reindex concurrently les index les plus utilises
    REINDEX INDEX CONCURRENTLY sessions_active_idx;
    REINDEX INDEX CONCURRENTLY refresh_tokens_active_session_idx;
    REINDEX INDEX CONCURRENTLY revoked_tokens_expires_at_idx;
END;
$$ LANGUAGE plpgsql;


-- =====================================================
-- CLEANUP FUNCTIONS
-- =====================================================

-- Nettoyage des tokens expires
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS integer AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM revoked_tokens
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    DELETE FROM refresh_tokens
    WHERE expires_at < NOW() AND used_at IS NOT NULL;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- Nettoyage des login_attempts anciens (RGPD: 90 jours)
CREATE OR REPLACE FUNCTION cleanup_old_login_attempts(days_old integer DEFAULT 90)
RETURNS integer AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM login_attempts
    WHERE attempted_at < NOW() - (days_old || ' days')::interval;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- Nettoyage des audit_log anciens (configurable, defaut 1 an)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(days_old integer DEFAULT 365)
RETURNS integer AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM audit_log
    WHERE created_at < NOW() - (days_old || ' days')::interval;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;


-- =====================================================
-- STATISTICS VIEWS
-- =====================================================

-- Vue pour monitorer les tables qui ont besoin de vacuum
CREATE OR REPLACE VIEW v_vacuum_stats AS
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY n_dead_tup DESC;


-- Vue pour monitorer l'utilisation des index
CREATE OR REPLACE VIEW v_index_usage AS
SELECT
    schemaname,
    relname,
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;


-- Vue pour detecter les index inutilises (candidates a suppression)
CREATE OR REPLACE VIEW v_unused_indexes AS
SELECT
    schemaname,
    relname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
  AND indexrelname NOT LIKE '%_unique%';


COMMIT;
