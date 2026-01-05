-- ============================================================================
-- ETL WORKFLOW COMPLET - MASSACORP
-- Import Factures METRO → Staging → ODS → DWH
-- ============================================================================

-- ============================================================================
-- SECTION 1: CRÉATION DES SCHÉMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS ods;
CREATE SCHEMA IF NOT EXISTS etl;

COMMENT ON SCHEMA staging IS 'Zone de staging - données brutes avant validation';
COMMENT ON SCHEMA ods IS 'Operational Data Store - données validées pour usage tactique';
COMMENT ON SCHEMA etl IS 'Fonctions et procédures ETL';

-- ============================================================================
-- SECTION 2: TABLES STAGING
-- ============================================================================

-- ----------------------------------------------------------------------------
-- staging.stg_facture_entete : En-têtes des factures importées
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.stg_facture_ligne CASCADE;
DROP TABLE IF EXISTS staging.stg_facture_entete CASCADE;

CREATE TABLE staging.stg_facture_entete (
    id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL DEFAULT gen_random_uuid(),
    source_file VARCHAR(500),

    -- Identification facture
    numero_facture VARCHAR(100),
    numero_interne VARCHAR(50),
    date_facture DATE,
    date_impression TIMESTAMP,

    -- Fournisseur
    fournisseur_nom VARCHAR(200),
    fournisseur_siret VARCHAR(20),
    fournisseur_tva_intra VARCHAR(20),
    fournisseur_adresse TEXT,
    magasin_code VARCHAR(10),
    magasin_nom VARCHAR(100),
    magasin_adresse TEXT,

    -- Client
    client_nom VARCHAR(200),
    client_numero VARCHAR(50),
    client_adresse TEXT,

    -- Totaux
    nombre_colis INT,
    total_ht NUMERIC(14,2),
    total_tva NUMERIC(12,2),
    total_ttc NUMERIC(14,2),

    -- Paiement
    mode_paiement VARCHAR(50),
    date_echeance DATE,

    -- Métadonnées
    extraction_status VARCHAR(20) DEFAULT 'BRUT',
    validation_errors JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stg_entete_batch ON staging.stg_facture_entete(batch_id);
CREATE INDEX idx_stg_entete_numero ON staging.stg_facture_entete(numero_interne);
CREATE INDEX idx_stg_entete_status ON staging.stg_facture_entete(extraction_status);

-- ----------------------------------------------------------------------------
-- staging.stg_facture_ligne : Lignes de factures extraites
-- ----------------------------------------------------------------------------
CREATE TABLE staging.stg_facture_ligne (
    id SERIAL PRIMARY KEY,
    entete_id INT REFERENCES staging.stg_facture_entete(id) ON DELETE CASCADE,
    batch_id UUID NOT NULL,

    -- Ligne article
    ligne_numero INT,
    ean VARCHAR(20),
    article_numero VARCHAR(20),
    designation TEXT,
    categorie_source VARCHAR(100),

    -- Caractéristiques produit
    regie CHAR(1),
    vol_alcool NUMERIC(5,2),
    vap NUMERIC(10,4),
    poids_volume NUMERIC(12,4),
    unite VARCHAR(10),

    -- Prix et quantités
    prix_unitaire NUMERIC(12,4),
    prix_au_litre NUMERIC(12,4),
    colisage INT,
    quantite INT,
    montant_ligne NUMERIC(14,2),

    -- TVA
    code_tva CHAR(1),
    taux_tva NUMERIC(5,2),

    -- Flags
    est_promo BOOLEAN DEFAULT FALSE,
    cotis_secu NUMERIC(10,2),

    -- Traçabilité
    numero_lot VARCHAR(50),
    date_peremption DATE,

    -- Métadonnées
    raw_line TEXT,
    extraction_status VARCHAR(20) DEFAULT 'BRUT',
    validation_errors JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stg_ligne_batch ON staging.stg_facture_ligne(batch_id);
CREATE INDEX idx_stg_ligne_entete ON staging.stg_facture_ligne(entete_id);
CREATE INDEX idx_stg_ligne_ean ON staging.stg_facture_ligne(ean);
CREATE INDEX idx_stg_ligne_status ON staging.stg_facture_ligne(extraction_status);

-- ----------------------------------------------------------------------------
-- staging.mapping_regie_categorie : Correspondance régie METRO → catégorie DWH
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.mapping_regie_categorie CASCADE;

CREATE TABLE staging.mapping_regie_categorie (
    regie CHAR(1) PRIMARY KEY,
    nom_regie VARCHAR(50),
    categorie_dwh_code VARCHAR(20),
    famille VARCHAR(50),
    sous_famille VARCHAR(50)
);

INSERT INTO staging.mapping_regie_categorie VALUES
    ('S', 'Spiritueux', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
    ('B', 'Bière', 'ALC_BIERE', 'Boissons', 'Bière'),
    ('M', 'Champagne/Mousseux', 'ALC_CHAMPAGNE', 'Boissons', 'Vin effervescent'),
    ('T', 'Vin tranquille', 'ALC_VIN', 'Boissons', 'Vin'),
    ('A', 'Consigne/Divers', 'DIV_CONSIGNE', 'Divers', 'Consigne'),
    ('C', 'Service/Livraison', 'DIV_SERVICE', 'Divers', 'Service'),
    ('E', 'Epicerie', 'EPIC_GENERAL', 'Epicerie', 'Général'),
    ('F', 'Frais', 'FRAIS_GENERAL', 'Frais', 'Général'),
    ('G', 'Surgelés', 'SURG_GENERAL', 'Surgelés', 'Général'),
    ('H', 'Hygiène/Droguerie', 'HYG_GENERAL', 'Non-alimentaire', 'Hygiène');

-- ----------------------------------------------------------------------------
-- staging.mapping_tva : Correspondance code TVA → taux
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.mapping_tva CASCADE;

CREATE TABLE staging.mapping_tva (
    code_tva CHAR(1) PRIMARY KEY,
    taux_tva NUMERIC(5,2),
    description VARCHAR(100)
);

INSERT INTO staging.mapping_tva VALUES
    ('A', 0.00, 'Exonéré/Consigne'),
    ('B', 5.50, 'Taux réduit alimentaire'),
    ('C', 10.00, 'Taux intermédiaire'),
    ('D', 20.00, 'Taux normal');

-- ============================================================================
-- SECTION 3: TABLES ODS
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ods.ods_facture_entete : En-têtes factures validées
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS ods.ods_facture_ligne CASCADE;
DROP TABLE IF EXISTS ods.ods_facture_entete CASCADE;

CREATE TABLE ods.ods_facture_entete (
    facture_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    numero_facture VARCHAR(100) NOT NULL,
    numero_interne VARCHAR(50) NOT NULL UNIQUE,
    date_facture DATE NOT NULL,

    -- Fournisseur (FK vers DWH si existe)
    fournisseur_sk INT,
    fournisseur_nom VARCHAR(200),
    fournisseur_siret VARCHAR(20),
    magasin_nom VARCHAR(100),

    -- Client
    client_nom VARCHAR(200),
    client_numero VARCHAR(50),

    -- Totaux
    nombre_lignes INT DEFAULT 0,
    nombre_colis INT,
    total_ht NUMERIC(14,2),
    total_tva NUMERIC(12,2),
    total_ttc NUMERIC(14,2),

    -- Statut workflow
    statut VARCHAR(20) DEFAULT 'VALIDE',
    date_echeance DATE,
    date_paiement DATE,

    -- Audit
    source_batch_id UUID,
    source_file VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ods_facture_date ON ods.ods_facture_entete(date_facture);
CREATE INDEX idx_ods_facture_fournisseur ON ods.ods_facture_entete(fournisseur_sk);
CREATE INDEX idx_ods_facture_statut ON ods.ods_facture_entete(statut);

-- ----------------------------------------------------------------------------
-- ods.ods_facture_ligne : Lignes factures validées
-- ----------------------------------------------------------------------------
CREATE TABLE ods.ods_facture_ligne (
    id SERIAL PRIMARY KEY,
    facture_id UUID REFERENCES ods.ods_facture_entete(facture_id) ON DELETE CASCADE,
    ligne_numero INT NOT NULL,

    -- Produit
    ean VARCHAR(20),
    article_numero VARCHAR(20),
    designation TEXT NOT NULL,
    produit_sk INT,

    -- Catégorie
    categorie_id INT,
    categorie_source VARCHAR(100),
    regie CHAR(1),

    -- Quantités
    quantite INT NOT NULL,
    colisage INT,
    poids_volume NUMERIC(12,4),
    unite VARCHAR(10),

    -- Prix
    prix_unitaire NUMERIC(12,4) NOT NULL,
    prix_au_litre NUMERIC(12,4),
    montant_ht NUMERIC(14,2) NOT NULL,

    -- TVA
    code_tva CHAR(1),
    taux_tva NUMERIC(5,2),
    montant_tva NUMERIC(12,2),
    montant_ttc NUMERIC(14,2),

    -- Alcool
    est_alcool BOOLEAN DEFAULT FALSE,
    vol_alcool NUMERIC(5,2),
    vap_total NUMERIC(12,4),
    cotis_secu NUMERIC(10,2),

    -- Promo
    est_promo BOOLEAN DEFAULT FALSE,

    -- Audit
    source_ligne_id INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(facture_id, ligne_numero)
);

CREATE INDEX idx_ods_ligne_facture ON ods.ods_facture_ligne(facture_id);
CREATE INDEX idx_ods_ligne_ean ON ods.ods_facture_ligne(ean);
CREATE INDEX idx_ods_ligne_categorie ON ods.ods_facture_ligne(categorie_id);

-- ============================================================================
-- SECTION 4: TABLE AUDIT ETL
-- ============================================================================

DROP TABLE IF EXISTS etl.audit_execution CASCADE;

CREATE TABLE etl.audit_execution (
    execution_id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'RUNNING',

    -- Compteurs
    lignes_extraites INT DEFAULT 0,
    lignes_validees INT DEFAULT 0,
    lignes_erreur INT DEFAULT 0,
    lignes_ods INT DEFAULT 0,
    lignes_dwh INT DEFAULT 0,

    -- Détails
    source_files TEXT[],
    error_message TEXT,
    error_details JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- SECTION 5: FONCTIONS ETL
-- ============================================================================

-- ----------------------------------------------------------------------------
-- etl.valider_facture_entete : Validation des en-têtes
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.valider_facture_entete(p_batch_id UUID)
RETURNS TABLE(entete_id INT, status VARCHAR, nb_errors INT) AS $$
DECLARE
    r RECORD;
    v_errors JSONB;
BEGIN
    FOR r IN SELECT * FROM staging.stg_facture_entete WHERE batch_id = p_batch_id LOOP
        v_errors := '[]'::JSONB;

        -- V1: Numéro facture obligatoire
        IF r.numero_facture IS NULL OR TRIM(r.numero_facture) = '' THEN
            v_errors := v_errors || '["V1: Numéro facture manquant"]'::JSONB;
        END IF;

        -- V2: Date facture valide
        IF r.date_facture IS NULL THEN
            v_errors := v_errors || '["V2: Date facture manquante"]'::JSONB;
        ELSIF r.date_facture > CURRENT_DATE THEN
            v_errors := v_errors || '["V2: Date facture dans le futur"]'::JSONB;
        END IF;

        -- V3: Fournisseur identifié
        IF r.fournisseur_nom IS NULL AND r.fournisseur_siret IS NULL THEN
            v_errors := v_errors || '["V3: Fournisseur non identifié"]'::JSONB;
        END IF;

        -- V4: Total cohérent
        IF r.total_ht IS NOT NULL AND r.total_ttc IS NOT NULL THEN
            IF r.total_ttc < r.total_ht THEN
                v_errors := v_errors || '["V4: Total TTC < Total HT"]'::JSONB;
            END IF;
        END IF;

        -- V5: Doublon
        IF EXISTS (
            SELECT 1 FROM ods.ods_facture_entete
            WHERE numero_interne = r.numero_interne
        ) THEN
            v_errors := v_errors || '["V5: Facture déjà importée"]'::JSONB;
        END IF;

        -- Mise à jour statut
        UPDATE staging.stg_facture_entete
        SET
            extraction_status = CASE
                WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'
                ELSE 'ERREUR'
            END,
            validation_errors = v_errors,
            updated_at = NOW()
        WHERE id = r.id;

        RETURN QUERY SELECT r.id,
            CASE WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'::VARCHAR ELSE 'ERREUR'::VARCHAR END,
            jsonb_array_length(v_errors)::INT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- etl.valider_facture_lignes : Validation des lignes
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.valider_facture_lignes(p_batch_id UUID)
RETURNS TABLE(ligne_id INT, status VARCHAR, nb_errors INT) AS $$
DECLARE
    r RECORD;
    v_errors JSONB;
BEGIN
    FOR r IN SELECT * FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id LOOP
        v_errors := '[]'::JSONB;

        -- V1: Désignation obligatoire
        IF r.designation IS NULL OR TRIM(r.designation) = '' THEN
            v_errors := v_errors || '["V1: Désignation manquante"]'::JSONB;
        END IF;

        -- V2: Quantité valide
        IF r.quantite IS NULL OR r.quantite <= 0 THEN
            v_errors := v_errors || '["V2: Quantité invalide"]'::JSONB;
        END IF;

        -- V3: Prix valide
        IF r.prix_unitaire IS NULL OR r.prix_unitaire < 0 THEN
            v_errors := v_errors || '["V3: Prix unitaire invalide"]'::JSONB;
        END IF;

        -- V4: Montant cohérent (tolérance 1%)
        IF r.prix_unitaire IS NOT NULL AND r.quantite IS NOT NULL AND r.montant_ligne IS NOT NULL THEN
            IF ABS(r.prix_unitaire * r.quantite - r.montant_ligne) > (r.montant_ligne * 0.01 + 0.02) THEN
                v_errors := v_errors || jsonb_build_array(
                    format('V4: Montant incohérent: %.2f × %s ≠ %.2f',
                           r.prix_unitaire, r.quantite, r.montant_ligne)
                );
            END IF;
        END IF;

        -- V5: Code TVA valide
        IF r.code_tva IS NOT NULL AND r.code_tva NOT IN ('A', 'B', 'C', 'D') THEN
            v_errors := v_errors || '["V5: Code TVA inconnu"]'::JSONB;
        END IF;

        -- V6: EAN format (si présent)
        IF r.ean IS NOT NULL AND LENGTH(r.ean) > 0 AND r.ean !~ '^[0-9]{8,14}$' THEN
            v_errors := v_errors || '["V6: Format EAN invalide"]'::JSONB;
        END IF;

        -- Mise à jour statut
        UPDATE staging.stg_facture_ligne
        SET
            extraction_status = CASE
                WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'
                ELSE 'ERREUR'
            END,
            validation_errors = v_errors
        WHERE id = r.id;

        RETURN QUERY SELECT r.id,
            CASE WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'::VARCHAR ELSE 'ERREUR'::VARCHAR END,
            jsonb_array_length(v_errors)::INT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- etl.enrichir_colonnes_manquantes : Compléter les colonnes via lookups
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.enrichir_colonnes_manquantes(p_batch_id UUID)
RETURNS TABLE(colonne TEXT, nb_enrichis BIGINT) AS $$
BEGIN
    -- Enrichir taux_tva via code_tva
    UPDATE staging.stg_facture_ligne l
    SET taux_tva = m.taux_tva
    FROM staging.mapping_tva m
    WHERE l.batch_id = p_batch_id
      AND l.taux_tva IS NULL
      AND l.code_tva IS NOT NULL
      AND m.code_tva = l.code_tva;

    RETURN QUERY SELECT 'taux_tva'::TEXT, COUNT(*)
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND taux_tva IS NOT NULL;

    -- Calculer prix_au_litre si manquant
    UPDATE staging.stg_facture_ligne
    SET prix_au_litre = CASE
        WHEN poids_volume > 0 THEN ROUND(prix_unitaire / poids_volume, 3)
        ELSE NULL
    END
    WHERE batch_id = p_batch_id
      AND prix_au_litre IS NULL
      AND poids_volume IS NOT NULL
      AND poids_volume > 0;

    RETURN QUERY SELECT 'prix_au_litre'::TEXT, COUNT(*)
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND prix_au_litre IS NOT NULL;

    -- Déterminer régie selon catégorie source
    UPDATE staging.stg_facture_ligne
    SET regie = CASE
        WHEN UPPER(categorie_source) LIKE '%SPIRITUEUX%' THEN 'S'
        WHEN UPPER(categorie_source) LIKE '%BRASSERIE%' THEN 'B'
        WHEN UPPER(categorie_source) LIKE '%BIERE%' THEN 'B'
        WHEN UPPER(categorie_source) LIKE '%CHAMPAGNE%' THEN 'M'
        WHEN UPPER(categorie_source) LIKE '%CAVE%' THEN 'T'
        WHEN UPPER(categorie_source) LIKE '%VIN%' THEN 'T'
        WHEN UPPER(categorie_source) LIKE '%EPICERIE%' THEN 'E'
        WHEN UPPER(categorie_source) LIKE '%SURGELE%' THEN 'G'
        WHEN UPPER(categorie_source) LIKE '%DROGUERIE%' THEN 'H'
        WHEN UPPER(categorie_source) LIKE '%HYGIENE%' THEN 'H'
        WHEN UPPER(categorie_source) LIKE '%DIVERS%' THEN 'A'
        ELSE NULL
    END
    WHERE batch_id = p_batch_id
      AND regie IS NULL
      AND categorie_source IS NOT NULL;

    RETURN QUERY SELECT 'regie'::TEXT, COUNT(*)
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND regie IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- etl.transformer_vers_ods : Staging → ODS
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.transformer_vers_ods(p_batch_id UUID)
RETURNS INT AS $$
DECLARE
    v_entete RECORD;
    v_facture_id UUID;
    v_count INT := 0;
    v_ligne_count INT;
BEGIN
    -- Traiter chaque en-tête validé
    FOR v_entete IN
        SELECT * FROM staging.stg_facture_entete
        WHERE batch_id = p_batch_id AND extraction_status = 'VALIDE'
    LOOP
        -- Générer ID facture
        v_facture_id := gen_random_uuid();

        -- Insérer en-tête ODS
        INSERT INTO ods.ods_facture_entete (
            facture_id,
            numero_facture,
            numero_interne,
            date_facture,
            fournisseur_nom,
            fournisseur_siret,
            magasin_nom,
            client_nom,
            client_numero,
            nombre_colis,
            total_ht,
            total_tva,
            total_ttc,
            date_echeance,
            source_batch_id,
            source_file
        ) VALUES (
            v_facture_id,
            v_entete.numero_facture,
            v_entete.numero_interne,
            v_entete.date_facture,
            v_entete.fournisseur_nom,
            v_entete.fournisseur_siret,
            v_entete.magasin_nom,
            v_entete.client_nom,
            v_entete.client_numero,
            v_entete.nombre_colis,
            v_entete.total_ht,
            v_entete.total_tva,
            v_entete.total_ttc,
            v_entete.date_echeance,
            p_batch_id,
            v_entete.source_file
        );

        -- Insérer lignes ODS
        INSERT INTO ods.ods_facture_ligne (
            facture_id,
            ligne_numero,
            ean,
            article_numero,
            designation,
            categorie_source,
            regie,
            quantite,
            colisage,
            poids_volume,
            unite,
            prix_unitaire,
            prix_au_litre,
            montant_ht,
            code_tva,
            taux_tva,
            montant_tva,
            montant_ttc,
            est_alcool,
            vol_alcool,
            vap_total,
            cotis_secu,
            est_promo,
            source_ligne_id
        )
        SELECT
            v_facture_id,
            l.ligne_numero,
            l.ean,
            l.article_numero,
            l.designation,
            l.categorie_source,
            l.regie,
            l.quantite,
            l.colisage,
            l.poids_volume,
            l.unite,
            l.prix_unitaire,
            l.prix_au_litre,
            l.montant_ligne,
            l.code_tva,
            COALESCE(l.taux_tva, m.taux_tva, 20.00),
            -- Calcul TVA
            ROUND(l.montant_ligne * COALESCE(l.taux_tva, m.taux_tva, 20.00) / 100, 2),
            -- Calcul TTC
            ROUND(l.montant_ligne * (1 + COALESCE(l.taux_tva, m.taux_tva, 20.00) / 100), 2),
            -- Est alcool
            l.regie IN ('S', 'B', 'M', 'T'),
            l.vol_alcool,
            -- VAP total
            CASE
                WHEN l.regie IN ('S', 'B', 'M', 'T') AND l.vol_alcool IS NOT NULL AND l.poids_volume IS NOT NULL
                THEN l.quantite * l.poids_volume * l.vol_alcool / 100
                ELSE 0
            END,
            l.cotis_secu,
            l.est_promo,
            l.id
        FROM staging.stg_facture_ligne l
        LEFT JOIN staging.mapping_tva m ON m.code_tva = l.code_tva
        WHERE l.entete_id = v_entete.id
          AND l.extraction_status = 'VALIDE';

        GET DIAGNOSTICS v_ligne_count = ROW_COUNT;

        -- Mettre à jour nombre de lignes
        UPDATE ods.ods_facture_entete
        SET nombre_lignes = v_ligne_count
        WHERE facture_id = v_facture_id;

        v_count := v_count + v_ligne_count;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- etl.charger_vers_dwh : ODS → DWH (fait_achats)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl.charger_vers_dwh(p_batch_id UUID)
RETURNS INT AS $$
DECLARE
    v_count INT := 0;
BEGIN
    -- Vérifier que la table fait_achats existe dans dwh
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'dwh' AND table_name = 'fait_achats'
    ) THEN
        -- Créer la table fait_achats si elle n'existe pas
        CREATE TABLE IF NOT EXISTS dwh.fait_achats (
            achat_id SERIAL PRIMARY KEY,
            date_id INT NOT NULL,
            fournisseur_sk INT,
            produit_sk INT,
            categorie_id INT,

            quantite INT NOT NULL,
            montant_ht NUMERIC(14,2),
            montant_tva NUMERIC(12,2),
            montant_ttc NUMERIC(14,2),

            facture_numero VARCHAR(100),
            ligne_numero INT,
            source VARCHAR(50),

            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_fait_achats_date ON dwh.fait_achats(date_id);
        CREATE INDEX IF NOT EXISTS idx_fait_achats_fournisseur ON dwh.fait_achats(fournisseur_sk);
    END IF;

    -- Charger depuis ODS
    INSERT INTO dwh.fait_achats (
        date_id,
        fournisseur_sk,
        produit_sk,
        quantite,
        montant_ht,
        montant_tva,
        montant_ttc,
        facture_numero,
        ligne_numero,
        source
    )
    SELECT
        TO_CHAR(e.date_facture, 'YYYYMMDD')::INT,
        e.fournisseur_sk,
        l.produit_sk,
        l.quantite,
        l.montant_ht,
        l.montant_tva,
        l.montant_ttc,
        e.numero_interne,
        l.ligne_numero,
        'METRO'
    FROM ods.ods_facture_ligne l
    JOIN ods.ods_facture_entete e ON e.facture_id = l.facture_id
    WHERE e.source_batch_id = p_batch_id
      AND NOT EXISTS (
          SELECT 1 FROM dwh.fait_achats fa
          WHERE fa.facture_numero = e.numero_interne
            AND fa.ligne_numero = l.ligne_numero
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 6: PIPELINE ETL PRINCIPAL
-- ============================================================================

CREATE OR REPLACE FUNCTION etl.run_pipeline_factures(
    p_batch_id UUID DEFAULT NULL,
    p_dry_run BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    etape TEXT,
    statut VARCHAR,
    details TEXT
) AS $$
DECLARE
    v_batch_id UUID;
    v_execution_id INT;
    v_count INT;
    v_errors INT;
BEGIN
    -- Utiliser batch_id fourni ou le premier non traité
    IF p_batch_id IS NOT NULL THEN
        v_batch_id := p_batch_id;
    ELSE
        SELECT batch_id INTO v_batch_id
        FROM staging.stg_facture_entete
        WHERE extraction_status = 'BRUT'
        LIMIT 1;
    END IF;

    IF v_batch_id IS NULL THEN
        RETURN QUERY SELECT
            'INIT'::TEXT,
            'SKIP'::VARCHAR,
            'Aucun batch à traiter'::TEXT;
        RETURN;
    END IF;

    -- Enregistrer exécution
    INSERT INTO etl.audit_execution (batch_id, pipeline_name)
    VALUES (v_batch_id, 'FACTURES_METRO')
    RETURNING execution_id INTO v_execution_id;

    -- ÉTAPE 1: Validation en-têtes
    etape := '1_VALIDATION_ENTETES';
    PERFORM etl.valider_facture_entete(v_batch_id);

    SELECT COUNT(*), SUM(CASE WHEN extraction_status = 'ERREUR' THEN 1 ELSE 0 END)
    INTO v_count, v_errors
    FROM staging.stg_facture_entete WHERE batch_id = v_batch_id;

    RETURN QUERY SELECT etape, 'OK'::VARCHAR,
        format('%s en-têtes validés, %s erreurs', v_count - v_errors, v_errors);

    -- ÉTAPE 2: Validation lignes
    etape := '2_VALIDATION_LIGNES';
    PERFORM etl.valider_facture_lignes(v_batch_id);

    SELECT COUNT(*), SUM(CASE WHEN extraction_status = 'ERREUR' THEN 1 ELSE 0 END)
    INTO v_count, v_errors
    FROM staging.stg_facture_ligne WHERE batch_id = v_batch_id;

    RETURN QUERY SELECT etape, 'OK'::VARCHAR,
        format('%s lignes validées, %s erreurs', v_count - v_errors, v_errors);

    -- ÉTAPE 3: Enrichissement
    etape := '3_ENRICHISSEMENT';
    PERFORM etl.enrichir_colonnes_manquantes(v_batch_id);

    RETURN QUERY SELECT etape, 'OK'::VARCHAR, 'Colonnes enrichies';

    IF p_dry_run THEN
        RETURN QUERY SELECT 'DRY_RUN'::TEXT, 'SKIP'::VARCHAR, 'Mode test - pas de chargement';
        RETURN;
    END IF;

    -- ÉTAPE 4: Transformation ODS
    etape := '4_TRANSFORM_ODS';
    SELECT etl.transformer_vers_ods(v_batch_id) INTO v_count;

    UPDATE etl.audit_execution SET lignes_ods = v_count WHERE execution_id = v_execution_id;

    RETURN QUERY SELECT etape, 'OK'::VARCHAR,
        format('%s lignes chargées dans ODS', v_count);

    -- ÉTAPE 5: Chargement DWH
    etape := '5_LOAD_DWH';
    SELECT etl.charger_vers_dwh(v_batch_id) INTO v_count;

    UPDATE etl.audit_execution
    SET lignes_dwh = v_count, status = 'SUCCESS', finished_at = NOW()
    WHERE execution_id = v_execution_id;

    RETURN QUERY SELECT etape, 'OK'::VARCHAR,
        format('%s lignes chargées dans DWH', v_count);

    RETURN QUERY SELECT 'TERMINE'::TEXT, 'SUCCESS'::VARCHAR,
        format('Batch %s traité avec succès', v_batch_id);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 7: FONCTION D'IMPORT MANUELLE (pour test)
-- ============================================================================

CREATE OR REPLACE FUNCTION etl.importer_facture_metro(
    p_numero_facture VARCHAR,
    p_numero_interne VARCHAR,
    p_date_facture DATE,
    p_fournisseur VARCHAR DEFAULT 'METRO France',
    p_magasin VARCHAR DEFAULT 'METRO LA CHAPELLE',
    p_client VARCHAR DEFAULT 'NOUTAM',
    p_client_numero VARCHAR DEFAULT '135 00712188',
    p_total_ht NUMERIC DEFAULT 0,
    p_total_tva NUMERIC DEFAULT 0,
    p_total_ttc NUMERIC DEFAULT 0,
    p_source_file VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_batch_id UUID := gen_random_uuid();
    v_entete_id INT;
BEGIN
    INSERT INTO staging.stg_facture_entete (
        batch_id, source_file,
        numero_facture, numero_interne, date_facture,
        fournisseur_nom, fournisseur_siret, magasin_nom,
        client_nom, client_numero,
        total_ht, total_tva, total_ttc
    ) VALUES (
        v_batch_id, p_source_file,
        p_numero_facture, p_numero_interne, p_date_facture,
        p_fournisseur, '399315613', p_magasin,
        p_client, p_client_numero,
        p_total_ht, p_total_tva, p_total_ttc
    ) RETURNING id INTO v_entete_id;

    RETURN v_batch_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION etl.ajouter_ligne_facture(
    p_batch_id UUID,
    p_ligne_numero INT,
    p_ean VARCHAR,
    p_article_numero VARCHAR,
    p_designation VARCHAR,
    p_categorie VARCHAR,
    p_regie CHAR DEFAULT NULL,
    p_vol_alcool NUMERIC DEFAULT NULL,
    p_poids_volume NUMERIC DEFAULT NULL,
    p_prix_unitaire NUMERIC DEFAULT 0,
    p_colisage INT DEFAULT 1,
    p_quantite INT DEFAULT 1,
    p_montant NUMERIC DEFAULT 0,
    p_code_tva CHAR DEFAULT 'D',
    p_est_promo BOOLEAN DEFAULT FALSE,
    p_cotis_secu NUMERIC DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_entete_id INT;
    v_ligne_id INT;
BEGIN
    SELECT id INTO v_entete_id
    FROM staging.stg_facture_entete
    WHERE batch_id = p_batch_id
    LIMIT 1;

    IF v_entete_id IS NULL THEN
        RAISE EXCEPTION 'Batch % non trouvé', p_batch_id;
    END IF;

    INSERT INTO staging.stg_facture_ligne (
        entete_id, batch_id, ligne_numero,
        ean, article_numero, designation, categorie_source,
        regie, vol_alcool, poids_volume,
        prix_unitaire, colisage, quantite, montant_ligne,
        code_tva, est_promo, cotis_secu
    ) VALUES (
        v_entete_id, p_batch_id, p_ligne_numero,
        p_ean, p_article_numero, p_designation, p_categorie,
        p_regie, p_vol_alcool, p_poids_volume,
        p_prix_unitaire, p_colisage, p_quantite, p_montant,
        p_code_tva, p_est_promo, p_cotis_secu
    ) RETURNING id INTO v_ligne_id;

    RETURN v_ligne_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECTION 8: VUES DE MONITORING
-- ============================================================================

CREATE OR REPLACE VIEW etl.v_batch_status AS
SELECT
    e.batch_id,
    e.source_file,
    e.numero_interne,
    e.date_facture,
    e.extraction_status AS status_entete,
    e.total_ttc,
    COUNT(l.id) AS nb_lignes,
    SUM(CASE WHEN l.extraction_status = 'VALIDE' THEN 1 ELSE 0 END) AS lignes_valides,
    SUM(CASE WHEN l.extraction_status = 'ERREUR' THEN 1 ELSE 0 END) AS lignes_erreur,
    e.created_at
FROM staging.stg_facture_entete e
LEFT JOIN staging.stg_facture_ligne l ON l.entete_id = e.id
GROUP BY e.id;

CREATE OR REPLACE VIEW etl.v_erreurs_validation AS
SELECT
    'ENTETE' AS type,
    e.batch_id,
    e.numero_interne,
    e.validation_errors
FROM staging.stg_facture_entete e
WHERE e.extraction_status = 'ERREUR'
UNION ALL
SELECT
    'LIGNE' AS type,
    l.batch_id,
    e.numero_interne || ' L' || l.ligne_numero,
    l.validation_errors
FROM staging.stg_facture_ligne l
JOIN staging.stg_facture_entete e ON e.id = l.entete_id
WHERE l.extraction_status = 'ERREUR';

CREATE OR REPLACE VIEW ods.v_factures_recentes AS
SELECT
    e.facture_id,
    e.numero_interne,
    e.date_facture,
    e.fournisseur_nom,
    e.magasin_nom,
    e.client_nom,
    e.nombre_lignes,
    e.total_ht,
    e.total_ttc,
    e.statut,
    e.created_at
FROM ods.ods_facture_entete e
ORDER BY e.date_facture DESC, e.created_at DESC
LIMIT 50;

-- ============================================================================
-- FIN DU SCRIPT
-- ============================================================================

SELECT 'ETL Workflow créé avec succès' AS message;
