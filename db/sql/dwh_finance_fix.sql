-- ============================================================================
-- CORRECTIONS DWH FINANCE
-- Fixes pour les erreurs PostgreSQL
-- ============================================================================

-- Fix 1: Créer fait_budget sans COALESCE dans UNIQUE
DROP TABLE IF EXISTS dwh.fait_budget CASCADE;

CREATE TABLE IF NOT EXISTS dwh.fait_budget (
    budget_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    exercice_id INT NOT NULL REFERENCES dwh.dim_exercice_comptable(exercice_id),
    cost_center_id INT NOT NULL REFERENCES dwh.dim_cost_center(cost_center_id),
    categorie_depense_id INT REFERENCES dwh.dim_categorie_depense(categorie_depense_id),
    mois INT NOT NULL CHECK (mois BETWEEN 1 AND 12),
    annee INT NOT NULL,
    budget_initial NUMERIC(14,2) NOT NULL,
    date_validation_budget DATE,
    budget_revise NUMERIC(14,2),
    motif_revision TEXT,
    date_revision TIMESTAMPTZ,
    realise NUMERIC(14,2) DEFAULT 0,
    date_dernier_calcul TIMESTAMPTZ,
    ecart_initial NUMERIC(14,2),
    ecart_revise NUMERIC(14,2),
    taux_consommation_pct NUMERIC(7,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.fait_budget IS 'Suivi budgétaire - GRAIN: centre de coût/mois';

CREATE INDEX IF NOT EXISTS idx_fait_budget_periode ON dwh.fait_budget(annee, mois);
CREATE INDEX IF NOT EXISTS idx_fait_budget_cc ON dwh.fait_budget(cost_center_id);
CREATE UNIQUE INDEX idx_fait_budget_unique ON dwh.fait_budget(tenant_id, exercice_id, cost_center_id, categorie_depense_id, mois)
    WHERE categorie_depense_id IS NOT NULL;
CREATE UNIQUE INDEX idx_fait_budget_unique_null ON dwh.fait_budget(tenant_id, exercice_id, cost_center_id, mois)
    WHERE categorie_depense_id IS NULL;

-- Trigger pour calculer les écarts
CREATE OR REPLACE FUNCTION dwh.trigger_budget_calculs()
RETURNS TRIGGER AS $$
BEGIN
    NEW.ecart_initial := COALESCE(NEW.budget_initial, 0) - COALESCE(NEW.realise, 0);
    NEW.ecart_revise := COALESCE(NEW.budget_revise, NEW.budget_initial, 0) - COALESCE(NEW.realise, 0);
    IF COALESCE(NEW.budget_initial, 0) > 0 THEN
        NEW.taux_consommation_pct := (COALESCE(NEW.realise, 0) / NEW.budget_initial * 100);
    ELSE
        NEW.taux_consommation_pct := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_budget_calculs
    BEFORE INSERT OR UPDATE ON dwh.fait_budget
    FOR EACH ROW
    EXECUTE FUNCTION dwh.trigger_budget_calculs();


-- Fix 2: Créer fait_echeances sans subquery dans generated column
DROP TABLE IF EXISTS dwh.fait_echeances CASCADE;

CREATE TABLE IF NOT EXISTS dwh.fait_echeances (
    echeance_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    facture_sk BIGINT REFERENCES dwh.fait_factures(facture_sk),
    date_echeance_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('ENTRANT', 'SORTANT')),
    montant_initial NUMERIC(14,2) NOT NULL,
    montant_restant NUMERIC(14,2) NOT NULL,
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),
    statut VARCHAR(20) DEFAULT 'A_VENIR' CHECK (statut IN ('A_VENIR', 'ECHUE', 'PAYEE', 'ANNULEE')),
    jours_retard INT DEFAULT 0,
    tiers_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.fait_echeances IS 'Échéancier prévisionnel - GRAIN: une échéance';

CREATE INDEX IF NOT EXISTS idx_fait_echeances_date ON dwh.fait_echeances(date_echeance_id);
CREATE INDEX IF NOT EXISTS idx_fait_echeances_statut ON dwh.fait_echeances(statut) WHERE statut IN ('A_VENIR', 'ECHUE');

-- Trigger pour calculer jours_retard
CREATE OR REPLACE FUNCTION dwh.trigger_echeance_jours_retard()
RETURNS TRIGGER AS $$
DECLARE
    v_date_echeance DATE;
BEGIN
    IF NEW.statut IN ('A_VENIR', 'ECHUE') THEN
        SELECT date_complete INTO v_date_echeance
        FROM dwh.dim_temps WHERE date_id = NEW.date_echeance_id;

        NEW.jours_retard := GREATEST(0, CURRENT_DATE - v_date_echeance);

        IF v_date_echeance < CURRENT_DATE AND NEW.statut = 'A_VENIR' THEN
            NEW.statut := 'ECHUE';
        END IF;
    ELSE
        NEW.jours_retard := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_echeance_jours_retard
    BEFORE INSERT OR UPDATE ON dwh.fait_echeances
    FOR EACH ROW
    EXECUTE FUNCTION dwh.trigger_echeance_jours_retard();


-- Fix 3: Recréer l'index sans subquery
DROP INDEX IF EXISTS dwh.idx_fait_factures_a_traiter;

CREATE INDEX idx_fait_factures_a_traiter ON dwh.fait_factures(tenant_id, statut_id);


-- Fix 4: RLS policies pour les tables corrigées
ALTER TABLE dwh.fait_budget ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_echeances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_fait_budget ON dwh.fait_budget;
DROP POLICY IF EXISTS tenant_isolation_fait_echeances ON dwh.fait_echeances;

CREATE POLICY tenant_isolation_fait_budget ON dwh.fait_budget
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_echeances ON dwh.fait_echeances
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));


-- Fix 5: Vérifier que le schéma ETL existe et recréer les fonctions
CREATE SCHEMA IF NOT EXISTS etl;

-- Continuer l'exécution du reste du script...
SELECT 'Corrections appliquées avec succès' AS status;
