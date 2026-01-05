-- =============================================================================
-- ETL METRO - Chargement vers DWH
-- =============================================================================
-- Historisation des données ODS vers le Data Warehouse
-- Conforme à l'architecture SID CIF (Corporate Information Factory)
-- =============================================================================

-- Schema DWH (si non existant)
CREATE SCHEMA IF NOT EXISTS dwh;

-- -----------------------------------------------------------------------------
-- Table: dwh.dim_temps
-- Description: Dimension temps (SCD Type 0 - invariant)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_temps (
    date_id INT PRIMARY KEY,                    -- YYYYMMDD
    date_complete DATE NOT NULL UNIQUE,
    annee INT NOT NULL,
    trimestre INT NOT NULL,
    mois INT NOT NULL,
    semaine INT NOT NULL,
    jour INT NOT NULL,
    jour_annee INT NOT NULL,
    nom_jour VARCHAR(10) NOT NULL,
    nom_mois VARCHAR(10) NOT NULL,
    annee_mois VARCHAR(7) NOT NULL,             -- YYYY-MM
    est_weekend BOOLEAN NOT NULL,
    est_ferie BOOLEAN DEFAULT FALSE
);

-- Génération dimension temps (10 ans)
INSERT INTO dwh.dim_temps (
    date_id, date_complete, annee, trimestre, mois, semaine, jour,
    jour_annee, nom_jour, nom_mois, annee_mois, est_weekend
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT,
    d,
    EXTRACT(YEAR FROM d)::INT,
    EXTRACT(QUARTER FROM d)::INT,
    EXTRACT(MONTH FROM d)::INT,
    EXTRACT(WEEK FROM d)::INT,
    EXTRACT(DAY FROM d)::INT,
    EXTRACT(DOY FROM d)::INT,
    TO_CHAR(d, 'Day'),
    TO_CHAR(d, 'Month'),
    TO_CHAR(d, 'YYYY-MM'),
    EXTRACT(DOW FROM d) IN (0, 6)
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL) d
ON CONFLICT (date_id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- Table: dwh.dim_fournisseur
-- Description: Dimension fournisseur (SCD Type 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_fournisseur (
    fournisseur_sk SERIAL PRIMARY KEY,          -- Surrogate key
    fournisseur_id INT NOT NULL,                -- Business key
    tenant_id INT DEFAULT 1,

    nom VARCHAR(200) NOT NULL,
    siret VARCHAR(20),
    tva_intra VARCHAR(20),
    adresse TEXT,
    code_postal VARCHAR(10),
    ville VARCHAR(100),
    pays VARCHAR(50) DEFAULT 'France',

    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_actuel BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_fournisseur_actuel
    ON dwh.dim_fournisseur(fournisseur_id) WHERE est_actuel = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_fournisseur_siret
    ON dwh.dim_fournisseur(siret);

-- Insertion METRO par défaut
INSERT INTO dwh.dim_fournisseur (fournisseur_id, nom, siret, ville)
VALUES (1, 'METRO France', '399315613', 'Nanterre')
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- Table: dwh.dim_categorie_produit
-- Description: Dimension catégorie (SCD Type 1)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_categorie_produit (
    categorie_id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    famille VARCHAR(50),
    sous_famille VARCHAR(50),
    est_alcool BOOLEAN DEFAULT FALSE,
    taux_tva_defaut NUMERIC(5,2) DEFAULT 20.00
);

-- Insertion catégories depuis mapping
INSERT INTO dwh.dim_categorie_produit (code, nom, famille, sous_famille, est_alcool, taux_tva_defaut)
SELECT
    categorie_dwh_code,
    nom_regie,
    famille,
    sous_famille,
    regie IN ('S', 'B', 'M', 'T'),
    taux_tva_defaut
FROM staging.mapping_regie_categorie
ON CONFLICT (code) DO NOTHING;

-- Catégorie inconnue
INSERT INTO dwh.dim_categorie_produit (categorie_id, code, nom, famille)
VALUES (-1, 'INCONNU', 'Catégorie inconnue', 'Non classé')
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- Table: dwh.dim_produit
-- Description: Dimension produit (SCD Type 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_produit (
    produit_sk SERIAL PRIMARY KEY,              -- Surrogate key
    produit_id INT,                             -- Business key
    tenant_id INT DEFAULT 1,

    ean VARCHAR(20),
    article_fournisseur VARCHAR(20),
    nom VARCHAR(200) NOT NULL,
    categorie_id INT REFERENCES dwh.dim_categorie_produit(categorie_id),

    -- Caractéristiques
    regie CHAR(1),
    vol_alcool NUMERIC(5,2),
    volume NUMERIC(12,4),
    unite VARCHAR(10),

    -- Prix (historisés)
    prix_achat NUMERIC(10,2),
    prix_vente NUMERIC(10,2),
    tva_pct NUMERIC(5,2),

    -- Calculs
    marge_unitaire NUMERIC(10,2) GENERATED ALWAYS AS (prix_vente - prix_achat) STORED,
    marge_pct NUMERIC(8,2) GENERATED ALWAYS AS (
        CASE WHEN prix_vente > 0
             THEN ROUND((prix_vente - prix_achat) / prix_vente * 100, 2)
             ELSE 0
        END
    ) STORED,

    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_actuel BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_produit_ean
    ON dwh.dim_produit(ean) WHERE est_actuel = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_produit_actuel
    ON dwh.dim_produit(produit_id) WHERE est_actuel = TRUE;

-- Produit inconnu
INSERT INTO dwh.dim_produit (produit_sk, produit_id, nom, categorie_id)
VALUES (-1, -1, 'PRODUIT INCONNU', -1)
ON CONFLICT DO NOTHING;


-- -----------------------------------------------------------------------------
-- Table: dwh.fait_achats
-- Description: Table de faits des achats fournisseurs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fait_achats (
    achat_id BIGSERIAL PRIMARY KEY,
    tenant_id INT DEFAULT 1,

    -- Dimensions (FK)
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    fournisseur_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),
    produit_sk INT REFERENCES dwh.dim_produit(produit_sk),
    categorie_id INT REFERENCES dwh.dim_categorie_produit(categorie_id),

    -- Identification facture
    facture_numero VARCHAR(100) NOT NULL,
    ligne_numero INT NOT NULL,

    -- Mesures
    quantite INT NOT NULL,
    montant_ht NUMERIC(14,2) NOT NULL,
    montant_tva NUMERIC(14,2),
    montant_ttc NUMERIC(14,2),
    prix_unitaire NUMERIC(12,4),

    -- Alcool
    volume_alcool_pur NUMERIC(12,4),

    -- Source
    source VARCHAR(20) DEFAULT 'METRO',
    source_batch_id UUID,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Contrainte unicité
    CONSTRAINT uk_fait_achats_ligne UNIQUE (facture_numero, ligne_numero, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_fait_achats_date ON dwh.fait_achats(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_achats_fournisseur ON dwh.fait_achats(fournisseur_sk);
CREATE INDEX IF NOT EXISTS idx_fait_achats_categorie ON dwh.fait_achats(categorie_id);
CREATE INDEX IF NOT EXISTS idx_fait_achats_source ON dwh.fait_achats(source);


-- -----------------------------------------------------------------------------
-- Procédure: dwh.charger_faits_achats
-- Description: Chargement ODS → DWH
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE dwh.charger_faits_achats(
    p_date_debut DATE DEFAULT NULL,
    p_date_fin DATE DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
    v_count INT;
    v_date_debut DATE := COALESCE(p_date_debut, CURRENT_DATE - INTERVAL '1 month');
    v_date_fin DATE := COALESCE(p_date_fin, CURRENT_DATE);
BEGIN
    RAISE NOTICE 'Chargement fait_achats: % → %', v_date_debut, v_date_fin;

    INSERT INTO dwh.fait_achats (
        date_id,
        fournisseur_sk,
        produit_sk,
        categorie_id,
        facture_numero,
        ligne_numero,
        quantite,
        montant_ht,
        montant_tva,
        montant_ttc,
        prix_unitaire,
        volume_alcool_pur,
        source,
        source_batch_id
    )
    SELECT
        TO_CHAR(f.date_facture, 'YYYYMMDD')::INT,
        COALESCE(
            (SELECT fournisseur_sk FROM dwh.dim_fournisseur
             WHERE siret = f.fournisseur_siret AND est_actuel LIMIT 1),
            1  -- METRO par défaut
        ),
        COALESCE(
            (SELECT produit_sk FROM dwh.dim_produit
             WHERE ean = l.produit_ean AND est_actuel LIMIT 1),
            -1  -- Produit inconnu
        ),
        COALESCE(
            (SELECT categorie_id FROM dwh.dim_categorie_produit
             WHERE code = l.categorie_code LIMIT 1),
            -1  -- Catégorie inconnue
        ),
        f.numero_facture,
        l.ligne_numero,
        l.quantite,
        l.montant_ligne_ht,
        l.montant_tva,
        l.montant_ttc,
        l.prix_unitaire_ht,
        l.volume_alcool_pur,
        'METRO',
        l.source_batch_id
    FROM ods.ods_facture_ligne l
    JOIN ods.ods_facture_entete f ON f.facture_id = l.facture_id
    WHERE f.date_facture BETWEEN v_date_debut AND v_date_fin
      AND f.statut = 'VALIDE'
    ON CONFLICT (facture_numero, ligne_numero, tenant_id) DO UPDATE SET
        montant_ht = EXCLUDED.montant_ht,
        montant_tva = EXCLUDED.montant_tva,
        montant_ttc = EXCLUDED.montant_ttc;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Chargé % lignes dans fait_achats', v_count;
END;
$$;


-- -----------------------------------------------------------------------------
-- Fonction: dwh.scd2_update_produit
-- Description: Mise à jour SCD Type 2 pour les produits
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dwh.scd2_update_produit(
    p_ean VARCHAR,
    p_nouveau_prix_achat NUMERIC,
    p_nouveau_prix_vente NUMERIC
)
RETURNS INT AS $$
DECLARE
    v_current_sk INT;
    v_new_sk INT;
    r RECORD;
BEGIN
    -- Trouver la version actuelle
    SELECT * INTO r
    FROM dwh.dim_produit
    WHERE ean = p_ean AND est_actuel = TRUE;

    IF r IS NULL THEN
        RAISE EXCEPTION 'Produit EAN % non trouvé', p_ean;
    END IF;

    -- Vérifier si le prix a changé
    IF r.prix_achat = p_nouveau_prix_achat AND r.prix_vente = p_nouveau_prix_vente THEN
        RETURN r.produit_sk;  -- Pas de changement
    END IF;

    -- Fermer la version actuelle
    UPDATE dwh.dim_produit
    SET
        date_fin = CURRENT_DATE - 1,
        est_actuel = FALSE
    WHERE produit_sk = r.produit_sk;

    -- Créer nouvelle version
    INSERT INTO dwh.dim_produit (
        produit_id, tenant_id, ean, article_fournisseur, nom, categorie_id,
        regie, vol_alcool, volume, unite,
        prix_achat, prix_vente, tva_pct,
        date_debut, date_fin, est_actuel
    )
    VALUES (
        r.produit_id, r.tenant_id, r.ean, r.article_fournisseur, r.nom, r.categorie_id,
        r.regie, r.vol_alcool, r.volume, r.unite,
        p_nouveau_prix_achat, p_nouveau_prix_vente, r.tva_pct,
        CURRENT_DATE, NULL, TRUE
    )
    RETURNING produit_sk INTO v_new_sk;

    RETURN v_new_sk;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: dwh.creer_produit_depuis_ods
-- Description: Création automatique de produits depuis ODS
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dwh.creer_produit_depuis_ods(p_batch_id UUID DEFAULT NULL)
RETURNS INT AS $$
DECLARE
    v_count INT := 0;
BEGIN
    INSERT INTO dwh.dim_produit (
        ean, article_fournisseur, nom, categorie_id,
        regie, vol_alcool, volume, unite,
        prix_achat, tva_pct
    )
    SELECT DISTINCT ON (l.produit_ean)
        l.produit_ean,
        l.article_numero,
        l.designation,
        COALESCE(
            (SELECT categorie_id FROM dwh.dim_categorie_produit WHERE code = l.categorie_code),
            -1
        ),
        l.regie,
        l.vol_alcool,
        l.poids_volume,
        l.unite,
        l.prix_unitaire_ht,
        l.taux_tva
    FROM ods.ods_facture_ligne l
    WHERE l.produit_ean IS NOT NULL
      AND (p_batch_id IS NULL OR l.source_batch_id = p_batch_id)
      AND NOT EXISTS (
          SELECT 1 FROM dwh.dim_produit p
          WHERE p.ean = l.produit_ean AND p.est_actuel
      )
    ORDER BY l.produit_ean, l.created_at DESC;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Data Mart: dwh.v_analyse_achats_fournisseur
-- Description: Analyse des achats par fournisseur/catégorie
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dwh.v_analyse_achats_fournisseur AS
SELECT
    t.annee,
    t.trimestre,
    t.mois,
    t.annee_mois,
    f.nom AS fournisseur,
    c.famille,
    c.nom AS categorie,
    c.est_alcool,

    -- Mesures
    COUNT(DISTINCT fa.facture_numero) AS nb_factures,
    SUM(fa.quantite) AS volume_total,
    SUM(fa.montant_ht) AS achats_ht,
    SUM(fa.montant_tva) AS achats_tva,
    SUM(fa.montant_ttc) AS achats_ttc,
    AVG(fa.prix_unitaire) AS prix_moyen,

    -- Spécifique alcool
    SUM(fa.volume_alcool_pur) AS vap_total,

    -- Évolution (mois précédent)
    LAG(SUM(fa.montant_ht)) OVER (
        PARTITION BY f.fournisseur_sk, c.categorie_id
        ORDER BY t.annee, t.mois
    ) AS achats_ht_mois_precedent,

    -- Part du total mensuel
    SUM(fa.montant_ht) * 100.0 / NULLIF(SUM(SUM(fa.montant_ht)) OVER (
        PARTITION BY t.annee, t.mois
    ), 0) AS pct_achats_mois

FROM dwh.fait_achats fa
JOIN dwh.dim_temps t ON fa.date_id = t.date_id
JOIN dwh.dim_fournisseur f ON fa.fournisseur_sk = f.fournisseur_sk
LEFT JOIN dwh.dim_categorie_produit c ON fa.categorie_id = c.categorie_id
GROUP BY
    t.annee, t.trimestre, t.mois, t.annee_mois,
    f.nom, f.fournisseur_sk,
    c.famille, c.nom, c.categorie_id, c.est_alcool
ORDER BY t.annee DESC, t.mois DESC, achats_ht DESC;


-- -----------------------------------------------------------------------------
-- Data Mart: dwh.v_evolution_prix_produit
-- Description: Évolution des prix d'achat (historique SCD2)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dwh.v_evolution_prix_produit AS
SELECT
    p.ean,
    p.nom,
    c.nom AS categorie,
    p.prix_achat,
    p.prix_vente,
    p.marge_unitaire,
    p.marge_pct,
    p.date_debut,
    p.date_fin,
    p.est_actuel,
    LAG(p.prix_achat) OVER (PARTITION BY p.ean ORDER BY p.date_debut) AS prix_achat_precedent,
    CASE
        WHEN LAG(p.prix_achat) OVER (PARTITION BY p.ean ORDER BY p.date_debut) > 0
        THEN ROUND((p.prix_achat - LAG(p.prix_achat) OVER (PARTITION BY p.ean ORDER BY p.date_debut))
                   / LAG(p.prix_achat) OVER (PARTITION BY p.ean ORDER BY p.date_debut) * 100, 2)
        ELSE NULL
    END AS variation_pct
FROM dwh.dim_produit p
LEFT JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
WHERE p.ean IS NOT NULL
ORDER BY p.ean, p.date_debut DESC;


COMMENT ON TABLE dwh.fait_achats IS 'Table de faits achats fournisseurs - données historisées DWH';
COMMENT ON PROCEDURE dwh.charger_faits_achats IS 'Chargement ODS → DWH avec détection doublons';
COMMENT ON FUNCTION dwh.scd2_update_produit IS 'Mise à jour SCD Type 2 pour dimension produit';
