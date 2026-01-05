-- =============================================================================
-- ETL METRO - Audit & Monitoring
-- =============================================================================
-- Tables et vues pour le suivi des exécutions ETL
-- Conforme à l'architecture SID CIF (Corporate Information Factory)
-- =============================================================================

-- Schema ETL (si non existant)
CREATE SCHEMA IF NOT EXISTS etl;

-- -----------------------------------------------------------------------------
-- Table: etl.audit_execution
-- Description: Journal des exécutions ETL
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl.audit_execution (
    execution_id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL,
    pipeline_name VARCHAR(100) NOT NULL,

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_seconds NUMERIC(10,2),

    -- Statut
    status VARCHAR(20) DEFAULT 'RUNNING',
    current_step VARCHAR(50),

    -- Compteurs
    fichiers_source INT DEFAULT 0,
    lignes_extraites INT DEFAULT 0,
    lignes_validees INT DEFAULT 0,
    lignes_erreur INT DEFAULT 0,
    lignes_transformees_ods INT DEFAULT 0,
    lignes_chargees_dwh INT DEFAULT 0,

    -- Métriques
    montant_total_ht NUMERIC(14,2),
    nb_factures INT DEFAULT 0,

    -- Erreurs
    error_message TEXT,
    error_details JSONB,

    -- Contexte
    source_directory TEXT,
    parameters JSONB,
    user_name VARCHAR(100) DEFAULT CURRENT_USER
);

CREATE INDEX IF NOT EXISTS idx_audit_batch ON etl.audit_execution(batch_id);
CREATE INDEX IF NOT EXISTS idx_audit_status ON etl.audit_execution(status);
CREATE INDEX IF NOT EXISTS idx_audit_date ON etl.audit_execution(started_at);


-- -----------------------------------------------------------------------------
-- Table: etl.audit_step
-- Description: Détail des étapes d'exécution
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl.audit_step (
    step_id SERIAL PRIMARY KEY,
    execution_id INT REFERENCES etl.audit_execution(execution_id),
    batch_id UUID NOT NULL,

    step_number INT NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms INT,

    status VARCHAR(20) DEFAULT 'RUNNING',
    rows_affected INT DEFAULT 0,
    message TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_step_exec ON etl.audit_step(execution_id);


-- -----------------------------------------------------------------------------
-- Fonction: etl.start_pipeline
-- Description: Démarre une nouvelle exécution de pipeline
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.start_pipeline(
    p_pipeline_name VARCHAR,
    p_batch_id UUID DEFAULT NULL,
    p_source_directory TEXT DEFAULT NULL,
    p_parameters JSONB DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_execution_id INT;
    v_batch_id UUID := COALESCE(p_batch_id, gen_random_uuid());
BEGIN
    INSERT INTO etl.audit_execution (
        batch_id, pipeline_name, source_directory, parameters
    )
    VALUES (
        v_batch_id, p_pipeline_name, p_source_directory, p_parameters
    )
    RETURNING execution_id INTO v_execution_id;

    RAISE NOTICE '[ETL] Pipeline % démarré (execution_id=%)', p_pipeline_name, v_execution_id;
    RETURN v_execution_id;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: etl.log_step
-- Description: Log une étape du pipeline
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.log_step(
    p_execution_id INT,
    p_step_number INT,
    p_step_name VARCHAR,
    p_status VARCHAR DEFAULT 'SUCCESS',
    p_rows_affected INT DEFAULT 0,
    p_message TEXT DEFAULT NULL,
    p_details JSONB DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_batch_id UUID;
BEGIN
    SELECT batch_id INTO v_batch_id
    FROM etl.audit_execution WHERE execution_id = p_execution_id;

    INSERT INTO etl.audit_step (
        execution_id, batch_id, step_number, step_name,
        finished_at, status, rows_affected, message, details
    )
    VALUES (
        p_execution_id, v_batch_id, p_step_number, p_step_name,
        NOW(), p_status, p_rows_affected, p_message, p_details
    );

    -- Mise à jour step courant
    UPDATE etl.audit_execution
    SET current_step = p_step_name
    WHERE execution_id = p_execution_id;

    RAISE NOTICE '[ETL] Step %: % - % (% lignes)',
        p_step_number, p_step_name, p_status, p_rows_affected;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: etl.finish_pipeline
-- Description: Termine une exécution de pipeline
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.finish_pipeline(
    p_execution_id INT,
    p_status VARCHAR DEFAULT 'SUCCESS',
    p_error_message TEXT DEFAULT NULL,
    p_error_details JSONB DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_batch_id UUID;
    v_stats RECORD;
BEGIN
    SELECT batch_id INTO v_batch_id
    FROM etl.audit_execution WHERE execution_id = p_execution_id;

    -- Calculer les stats depuis staging
    SELECT
        COUNT(DISTINCT source_file) AS fichiers,
        COUNT(*) AS lignes,
        COUNT(*) FILTER (WHERE extraction_status = 'VALIDE') AS valides,
        COUNT(*) FILTER (WHERE extraction_status = 'ERREUR') AS erreurs,
        COUNT(DISTINCT numero_facture) AS factures,
        COALESCE(SUM(montant_ligne), 0) AS montant
    INTO v_stats
    FROM staging.stg_facture_ligne
    WHERE batch_id = v_batch_id;

    -- Mise à jour exécution
    UPDATE etl.audit_execution
    SET
        finished_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at)),
        status = p_status,
        current_step = NULL,
        fichiers_source = v_stats.fichiers,
        lignes_extraites = v_stats.lignes,
        lignes_validees = v_stats.valides,
        lignes_erreur = v_stats.erreurs,
        nb_factures = v_stats.factures,
        montant_total_ht = v_stats.montant,
        error_message = p_error_message,
        error_details = p_error_details
    WHERE execution_id = p_execution_id;

    RAISE NOTICE '[ETL] Pipeline terminé: % (% factures, %.2f€ HT)',
        p_status, v_stats.factures, v_stats.montant;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Vue: etl.v_executions_recentes
-- Description: Synthèse des exécutions récentes
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW etl.v_executions_recentes AS
SELECT
    e.execution_id,
    e.batch_id,
    e.pipeline_name,
    e.started_at,
    e.finished_at,
    e.duration_seconds,
    e.status,
    e.fichiers_source,
    e.nb_factures,
    e.lignes_extraites,
    e.lignes_validees,
    e.lignes_erreur,
    CASE
        WHEN e.lignes_extraites > 0
        THEN ROUND(100.0 * e.lignes_validees / e.lignes_extraites, 1)
        ELSE 0
    END AS taux_validation_pct,
    e.montant_total_ht,
    e.error_message,
    e.user_name
FROM etl.audit_execution e
ORDER BY e.started_at DESC
LIMIT 50;


-- -----------------------------------------------------------------------------
-- Vue: etl.v_stats_journalieres
-- Description: Statistiques journalières des pipelines
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW etl.v_stats_journalieres AS
SELECT
    DATE(started_at) AS date_execution,
    pipeline_name,
    COUNT(*) AS nb_executions,
    COUNT(*) FILTER (WHERE status = 'SUCCESS') AS nb_success,
    COUNT(*) FILTER (WHERE status = 'ERROR') AS nb_error,
    SUM(fichiers_source) AS total_fichiers,
    SUM(nb_factures) AS total_factures,
    SUM(lignes_extraites) AS total_extraites,
    SUM(lignes_validees) AS total_validees,
    SUM(lignes_erreur) AS total_erreurs,
    ROUND(AVG(duration_seconds), 1) AS duree_moyenne_sec,
    SUM(montant_total_ht) AS montant_total_ht
FROM etl.audit_execution
WHERE status != 'RUNNING'
GROUP BY DATE(started_at), pipeline_name
ORDER BY DATE(started_at) DESC;


-- -----------------------------------------------------------------------------
-- Vue: etl.v_erreurs_frequentes
-- Description: Analyse des erreurs de validation
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW etl.v_erreurs_frequentes AS
SELECT
    jsonb_array_elements_text(validation_errors) AS erreur,
    COUNT(*) AS nb_occurrences,
    MIN(extraction_date) AS premiere_occurrence,
    MAX(extraction_date) AS derniere_occurrence
FROM staging.stg_facture_ligne
WHERE extraction_status = 'ERREUR'
  AND jsonb_array_length(validation_errors) > 0
GROUP BY jsonb_array_elements_text(validation_errors)
ORDER BY nb_occurrences DESC
LIMIT 20;


-- -----------------------------------------------------------------------------
-- Vue: etl.v_qualite_donnees
-- Description: Indicateurs qualité des données staging
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW etl.v_qualite_donnees AS
SELECT
    DATE(extraction_date) AS date_extraction,
    COUNT(*) AS total_lignes,

    -- Complétude
    ROUND(100.0 * COUNT(*) FILTER (WHERE numero_facture IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_facture,
    ROUND(100.0 * COUNT(*) FILTER (WHERE date_facture IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_date,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ean IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_ean,
    ROUND(100.0 * COUNT(*) FILTER (WHERE designation IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_designation,
    ROUND(100.0 * COUNT(*) FILTER (WHERE prix_unitaire IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_prix,
    ROUND(100.0 * COUNT(*) FILTER (WHERE quantite IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_quantite,
    ROUND(100.0 * COUNT(*) FILTER (WHERE montant_ligne IS NOT NULL) / NULLIF(COUNT(*), 0), 1) AS pct_montant,

    -- Validité
    ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'VALIDE') / NULLIF(COUNT(*), 0), 1) AS pct_valide,

    -- Score qualité global (moyenne des complétudes)
    ROUND((
        COUNT(*) FILTER (WHERE numero_facture IS NOT NULL) +
        COUNT(*) FILTER (WHERE date_facture IS NOT NULL) +
        COUNT(*) FILTER (WHERE designation IS NOT NULL) +
        COUNT(*) FILTER (WHERE prix_unitaire IS NOT NULL) +
        COUNT(*) FILTER (WHERE quantite IS NOT NULL)
    ) * 100.0 / (5 * NULLIF(COUNT(*), 0)), 1) AS score_qualite

FROM staging.stg_facture_ligne
GROUP BY DATE(extraction_date)
ORDER BY DATE(extraction_date) DESC;


-- -----------------------------------------------------------------------------
-- Fonction: etl.nettoyer_staging
-- Description: Nettoyage des données staging anciennes
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.nettoyer_staging(
    p_retention_jours INT DEFAULT 30
)
RETURNS TABLE(
    table_name TEXT,
    lignes_supprimees INT
) AS $$
DECLARE
    v_count INT;
    v_date_limite TIMESTAMPTZ := NOW() - (p_retention_jours || ' days')::INTERVAL;
BEGIN
    -- Nettoyage stg_facture_ligne
    DELETE FROM staging.stg_facture_ligne
    WHERE extraction_status = 'VALIDE'
      AND created_at < v_date_limite;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'staging.stg_facture_ligne'::TEXT, v_count;

    -- Nettoyage stg_facture_entete
    DELETE FROM staging.stg_facture_entete
    WHERE extraction_status = 'VALIDE'
      AND created_at < v_date_limite;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'staging.stg_facture_entete'::TEXT, v_count;

    RAISE NOTICE '[ETL] Nettoyage staging terminé (rétention: % jours)', p_retention_jours;
END;
$$ LANGUAGE plpgsql;


COMMENT ON SCHEMA etl IS 'Schema pour orchestration et monitoring ETL';
COMMENT ON TABLE etl.audit_execution IS 'Journal des exécutions de pipelines ETL';
COMMENT ON FUNCTION etl.start_pipeline IS 'Démarre et enregistre une nouvelle exécution ETL';
COMMENT ON FUNCTION etl.finish_pipeline IS 'Termine et finalise une exécution ETL';
