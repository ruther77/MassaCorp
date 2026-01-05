-- =============================================================================
-- ETL METRO - Schema Staging
-- =============================================================================
-- Création des tables staging pour l'import des factures METRO
-- Conforme à l'architecture SID CIF (Corporate Information Factory)
-- =============================================================================

-- Schema staging (si non existant)
CREATE SCHEMA IF NOT EXISTS staging;

-- -----------------------------------------------------------------------------
-- Table: staging.stg_facture_ligne
-- Description: Lignes de factures extraites des PDFs METRO (données brutes)
-- Rétention: 7-30 jours
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.stg_facture_ligne (
    id SERIAL PRIMARY KEY,

    -- Identification batch
    batch_id UUID NOT NULL,
    source_file VARCHAR(500),

    -- En-tête facture (extraction PDF)
    numero_facture VARCHAR(100),               -- Ex: 0/0(135)0011/021323
    numero_interne VARCHAR(50),                -- Ex: 011-299014
    date_facture DATE,
    date_impression TIMESTAMP,

    -- Fournisseur
    fournisseur_nom VARCHAR(200) DEFAULT 'METRO France',
    fournisseur_siret VARCHAR(20),
    fournisseur_tva_intra VARCHAR(20),
    fournisseur_adresse TEXT,
    magasin_nom VARCHAR(100),                  -- Ex: METRO LA CHAPELLE
    magasin_adresse TEXT,

    -- Client
    client_nom VARCHAR(200),                   -- Ex: NOUTAM
    client_numero VARCHAR(50),                 -- Ex: 135 00712188
    client_adresse TEXT,

    -- Ligne article
    ligne_numero INT,
    ean VARCHAR(20),                           -- Code EAN produit (13 chiffres)
    article_numero VARCHAR(20),                -- Numéro article METRO
    designation TEXT,                          -- Nom du produit
    categorie_source VARCHAR(100),             -- Ex: SPIRITUEUX, BRASSERIE

    -- Caractéristiques produit
    regie CHAR(1),                             -- S=Spiritueux, B=Bière, T=Vin, M=Champagne
    vol_alcool NUMERIC(5,2),                   -- % alcool
    vap NUMERIC(10,4),                         -- Volume Alcool Pur
    poids_volume NUMERIC(12,4),                -- Poids ou Volume unitaire
    unite VARCHAR(10),                         -- L, KG, unité

    -- Prix et quantités
    prix_unitaire NUMERIC(12,4),
    colisage INT,                              -- Nb par colis
    quantite INT,
    montant_ligne NUMERIC(14,2),

    -- TVA
    code_tva CHAR(1),                          -- A=0%, B=5.5%, C=10%, D=20%
    taux_tva NUMERIC(5,2),

    -- Flags
    est_promo BOOLEAN DEFAULT FALSE,
    cotis_secu NUMERIC(10,2),                  -- Cotisation sécurité sociale

    -- Métadonnées extraction
    raw_line TEXT,                             -- Ligne brute du PDF
    extraction_date TIMESTAMPTZ DEFAULT NOW(),
    extraction_status VARCHAR(20) DEFAULT 'BRUT',
    validation_errors JSONB DEFAULT '[]'::JSONB,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_stg_facture_batch
    ON staging.stg_facture_ligne(batch_id);
CREATE INDEX IF NOT EXISTS idx_stg_facture_status
    ON staging.stg_facture_ligne(extraction_status);
CREATE INDEX IF NOT EXISTS idx_stg_facture_date
    ON staging.stg_facture_ligne(date_facture);
CREATE INDEX IF NOT EXISTS idx_stg_facture_numero
    ON staging.stg_facture_ligne(numero_facture);


-- -----------------------------------------------------------------------------
-- Table: staging.stg_facture_entete
-- Description: En-têtes de factures (agrégation pour contrôle)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.stg_facture_entete (
    id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL,
    source_file VARCHAR(500),

    numero_facture VARCHAR(100),
    numero_interne VARCHAR(50),
    date_facture DATE,

    fournisseur_nom VARCHAR(200),
    fournisseur_siret VARCHAR(20),
    magasin_nom VARCHAR(100),

    client_nom VARCHAR(200),
    client_numero VARCHAR(50),

    -- Totaux extraits
    total_ht_extrait NUMERIC(14,2),
    total_tva_extrait NUMERIC(14,2),
    total_ttc_extrait NUMERIC(14,2),

    -- Totaux calculés (depuis lignes)
    total_ht_calcule NUMERIC(14,2),
    total_tva_calcule NUMERIC(14,2),
    total_ttc_calcule NUMERIC(14,2),

    -- Écarts
    ecart_ht NUMERIC(14,2),
    ecart_tva NUMERIC(14,2),
    ecart_ttc NUMERIC(14,2),

    nb_lignes INT,
    extraction_status VARCHAR(20) DEFAULT 'BRUT',
    validation_errors JSONB DEFAULT '[]'::JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_entete_batch
    ON staging.stg_facture_entete(batch_id);


-- -----------------------------------------------------------------------------
-- Table: staging.mapping_regie_categorie
-- Description: Correspondance régie METRO → catégorie DWH
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.mapping_regie_categorie (
    regie CHAR(1) PRIMARY KEY,
    nom_regie VARCHAR(50) NOT NULL,
    categorie_dwh_code VARCHAR(20) NOT NULL,
    famille VARCHAR(50),
    sous_famille VARCHAR(50),
    taux_tva_defaut NUMERIC(5,2)
);

-- Insertion des mappings
INSERT INTO staging.mapping_regie_categorie
    (regie, nom_regie, categorie_dwh_code, famille, sous_famille, taux_tva_defaut)
VALUES
    ('S', 'Spiritueux', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort', 20.00),
    ('B', 'Bière', 'ALC_BIERE', 'Boissons', 'Bière', 20.00),
    ('M', 'Champagne/Mousseux', 'ALC_CHAMPAGNE', 'Boissons', 'Vin effervescent', 20.00),
    ('T', 'Vin tranquille', 'ALC_VIN', 'Boissons', 'Vin', 20.00),
    ('A', 'Consigne/Divers', 'DIV_CONSIGNE', 'Divers', 'Consigne', 20.00),
    ('C', 'Service/Livraison', 'DIV_SERVICE', 'Divers', 'Service', 20.00),
    ('E', 'Épicerie', 'ALI_EPICERIE', 'Alimentation', 'Épicerie', 5.50),
    ('F', 'Frais/Surgelés', 'ALI_FRAIS', 'Alimentation', 'Frais', 5.50),
    ('D', 'Droguerie', 'NON_ALI_DROGUERIE', 'Non alimentaire', 'Droguerie', 20.00)
ON CONFLICT (regie) DO UPDATE SET
    nom_regie = EXCLUDED.nom_regie,
    categorie_dwh_code = EXCLUDED.categorie_dwh_code;


-- -----------------------------------------------------------------------------
-- Table: staging.mapping_code_tva
-- Description: Correspondance code TVA METRO → taux
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.mapping_code_tva (
    code_tva CHAR(1) PRIMARY KEY,
    taux NUMERIC(5,2) NOT NULL,
    description VARCHAR(100)
);

INSERT INTO staging.mapping_code_tva (code_tva, taux, description)
VALUES
    ('A', 0.00, 'Exonéré TVA'),
    ('B', 5.50, 'Taux réduit 5.5%'),
    ('C', 10.00, 'Taux intermédiaire 10%'),
    ('D', 20.00, 'Taux normal 20%')
ON CONFLICT (code_tva) DO NOTHING;


-- -----------------------------------------------------------------------------
-- Vue: staging.v_colonnes_manquantes
-- Description: Monitoring des colonnes manquantes par batch
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.v_colonnes_manquantes AS
SELECT
    batch_id,
    COUNT(*) AS total_lignes,
    SUM(CASE WHEN numero_facture IS NULL THEN 1 ELSE 0 END) AS facture_manquant,
    SUM(CASE WHEN date_facture IS NULL THEN 1 ELSE 0 END) AS date_manquante,
    SUM(CASE WHEN ean IS NULL THEN 1 ELSE 0 END) AS ean_manquant,
    SUM(CASE WHEN designation IS NULL THEN 1 ELSE 0 END) AS designation_manquante,
    SUM(CASE WHEN categorie_source IS NULL THEN 1 ELSE 0 END) AS categorie_manquante,
    SUM(CASE WHEN regie IS NULL THEN 1 ELSE 0 END) AS regie_manquante,
    SUM(CASE WHEN prix_unitaire IS NULL THEN 1 ELSE 0 END) AS prix_manquant,
    SUM(CASE WHEN quantite IS NULL THEN 1 ELSE 0 END) AS quantite_manquante,
    SUM(CASE WHEN montant_ligne IS NULL THEN 1 ELSE 0 END) AS montant_manquant,
    SUM(CASE WHEN taux_tva IS NULL THEN 1 ELSE 0 END) AS tva_manquante,
    ROUND(100.0 * SUM(CASE WHEN extraction_status = 'VALIDE' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_valide
FROM staging.stg_facture_ligne
GROUP BY batch_id;


-- -----------------------------------------------------------------------------
-- Vue: staging.v_batch_summary
-- Description: Résumé par batch d'import
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.v_batch_summary AS
SELECT
    batch_id,
    MIN(extraction_date) AS date_extraction,
    COUNT(DISTINCT source_file) AS nb_fichiers,
    COUNT(DISTINCT numero_facture) AS nb_factures,
    COUNT(*) AS nb_lignes,
    SUM(CASE WHEN extraction_status = 'BRUT' THEN 1 ELSE 0 END) AS lignes_brut,
    SUM(CASE WHEN extraction_status = 'VALIDE' THEN 1 ELSE 0 END) AS lignes_valides,
    SUM(CASE WHEN extraction_status = 'ERREUR' THEN 1 ELSE 0 END) AS lignes_erreur,
    SUM(montant_ligne) AS montant_total
FROM staging.stg_facture_ligne
GROUP BY batch_id
ORDER BY MIN(extraction_date) DESC;


COMMENT ON TABLE staging.stg_facture_ligne IS 'Lignes de factures METRO extraites des PDFs - données brutes staging';
COMMENT ON TABLE staging.stg_facture_entete IS 'En-têtes de factures METRO pour contrôle de cohérence';
COMMENT ON TABLE staging.mapping_regie_categorie IS 'Mapping code régie METRO vers catégorie DWH';
