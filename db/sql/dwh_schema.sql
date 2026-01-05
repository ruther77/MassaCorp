-- =============================================================================
-- DATA WAREHOUSE - NOUTAM SAS & L'Incontournable
-- Modèle Dimensionnel (Schéma en Étoile)
-- =============================================================================

-- Schéma dédié pour le DWH
CREATE SCHEMA IF NOT EXISTS dwh;
SET search_path TO dwh, public;

-- =============================================================================
-- 1. DIMENSIONS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- dim_temps : Dimension temporelle (pré-générée)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_temps (
    date_id INT PRIMARY KEY,                    -- Format YYYYMMDD
    date_complete DATE NOT NULL UNIQUE,
    jour INT NOT NULL,                          -- 1-31
    jour_semaine INT NOT NULL,                  -- 1=Lundi ... 7=Dimanche
    nom_jour TEXT NOT NULL,                     -- Lundi, Mardi...
    semaine_iso INT NOT NULL,                   -- 1-53
    mois INT NOT NULL,                          -- 1-12
    nom_mois TEXT NOT NULL,                     -- Janvier, Février...
    trimestre INT NOT NULL,                     -- 1-4
    annee INT NOT NULL,
    annee_mois TEXT NOT NULL,                   -- 2025-01
    annee_semaine TEXT NOT NULL,                -- 2025-W01
    est_weekend BOOLEAN NOT NULL DEFAULT FALSE,
    est_ferie BOOLEAN NOT NULL DEFAULT FALSE,
    nom_ferie TEXT,                             -- Nom du jour férié
    saison TEXT NOT NULL                        -- Printemps, Été, Automne, Hiver
);

CREATE INDEX IF NOT EXISTS idx_dim_temps_date ON dwh.dim_temps(date_complete);
CREATE INDEX IF NOT EXISTS idx_dim_temps_annee_mois ON dwh.dim_temps(annee, mois);

-- -----------------------------------------------------------------------------
-- dim_categorie_produit : Catégories produits (table partagée - voir dwh_categories.sql)
-- -----------------------------------------------------------------------------
-- La table dwh.dim_categorie_produit contient 91 catégories produits
-- Elle est créée et alimentée par le script dwh_categories.sql

-- -----------------------------------------------------------------------------
-- dim_fournisseur : Fournisseurs (SCD Type 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_fournisseur (
    fournisseur_sk SERIAL PRIMARY KEY,
    fournisseur_id INT NOT NULL,
    tenant_id INT NOT NULL,
    nom TEXT NOT NULL,
    type TEXT,                                  -- Grossiste/Direct/Marché
    siret TEXT,
    iban TEXT,
    delai_paiement INT DEFAULT 30,
    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_actuel BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_dim_fournisseur_actuel ON dwh.dim_fournisseur(tenant_id, est_actuel) WHERE est_actuel = TRUE;

-- -----------------------------------------------------------------------------
-- dim_produit : Produits épicerie (SCD Type 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_produit (
    produit_sk SERIAL PRIMARY KEY,
    produit_id INT NOT NULL,
    tenant_id INT NOT NULL,
    nom TEXT NOT NULL,
    categorie_id INT REFERENCES dwh.dim_categorie_produit(categorie_id),
    -- Prix et marges
    prix_achat NUMERIC(10,2),
    prix_vente NUMERIC(10,2),
    tva_pct NUMERIC(5,2),
    marge_unitaire NUMERIC(10,2) GENERATED ALWAYS AS (
        prix_vente - prix_achat
    ) STORED,
    marge_pct NUMERIC(8,2) GENERATED ALWAYS AS (
        CASE WHEN prix_vente > 0 
             THEN ROUND((prix_vente - prix_achat) / prix_vente * 100, 2)
             ELSE 0 
        END
    ) STORED,
    -- Stock
    seuil_alerte NUMERIC(12,3) DEFAULT 0,
    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_actuel BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_dim_produit_actuel ON dwh.dim_produit(tenant_id, est_actuel) WHERE est_actuel = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_produit_categorie ON dwh.dim_produit(categorie_id);

-- -----------------------------------------------------------------------------
-- dim_plat : Plats restaurant (SCD Type 2)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_plat (
    plat_sk SERIAL PRIMARY KEY,
    plat_id INT NOT NULL,
    tenant_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    nom TEXT NOT NULL,
    categorie TEXT,
    -- Prix et coûts
    prix_vente_ttc NUMERIC(12,2),
    cout_matiere NUMERIC(12,4),
    marge_brute NUMERIC(12,2) GENERATED ALWAYS AS (
        prix_vente_ttc - cout_matiere
    ) STORED,
    ratio_cout NUMERIC(8,2) GENERATED ALWAYS AS (
        CASE WHEN prix_vente_ttc > 0 
             THEN ROUND(cout_matiere / prix_vente_ttc * 100, 2)
             ELSE 0 
        END
    ) STORED,
    nb_ingredients INT DEFAULT 0,
    actif BOOLEAN DEFAULT TRUE,
    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE,
    est_actuel BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_dim_plat_actuel ON dwh.dim_plat(tenant_id, est_actuel) WHERE est_actuel = TRUE;

-- -----------------------------------------------------------------------------
-- dim_cost_center : Centres de coûts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_cost_center (
    cost_center_id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    nom TEXT NOT NULL,
    type TEXT,                                  -- Fixe/Variable
    budget_mensuel NUMERIC(14,2),
    UNIQUE(tenant_id, nom)
);

-- -----------------------------------------------------------------------------
-- dim_categorie_depense : Catégories de dépenses
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_categorie_depense (
    categorie_depense_id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    nom TEXT NOT NULL,
    cost_center_id INT REFERENCES dwh.dim_cost_center(cost_center_id),
    UNIQUE(tenant_id, nom)
);

-- -----------------------------------------------------------------------------
-- dim_canal : Canaux de vente restaurant
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_canal (
    canal_id SERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    nom TEXT NOT NULL,
    type TEXT,                                  -- Salle/Emporter/Livraison
    commission_pct NUMERIC(5,2) DEFAULT 0,
    est_actif BOOLEAN DEFAULT TRUE
);

-- Données de base canaux
INSERT INTO dwh.dim_canal (code, nom, type, commission_pct) VALUES
    ('SALLE', 'Sur place', 'Salle', 0),
    ('EMPORTER', 'À emporter', 'Emporter', 0),
    ('UBER', 'Uber Eats', 'Livraison', 30),
    ('DELIVEROO', 'Deliveroo', 'Livraison', 25),
    ('JUSTEATS', 'Just Eat', 'Livraison', 25),
    ('DIRECT', 'Livraison directe', 'Livraison', 0)
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- 2. TABLES DE FAITS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- fait_mouvements_stock : Mouvements de stock épicerie
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fait_mouvements_stock (
    mouvement_id SERIAL PRIMARY KEY,
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    produit_sk INT NOT NULL REFERENCES dwh.dim_produit(produit_sk),
    fournisseur_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),
    -- Dimensions dégénérées
    type_mouvement TEXT NOT NULL,               -- ENTREE/SORTIE/INVENTAIRE/TRANSFERT
    source TEXT,                                -- Origine du mouvement
    -- Mesures
    quantite NUMERIC(12,3) NOT NULL,            -- Toujours positive
    sens INT NOT NULL,                          -- +1 (entrée) / -1 (sortie)
    prix_unitaire NUMERIC(10,2),
    valeur_mouvement NUMERIC(14,2),
    -- Métadonnées
    mouvement_source_id INT,                    -- ID original (mouvements_stock.id)
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fait_mvt_date ON dwh.fait_mouvements_stock(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_mvt_produit ON dwh.fait_mouvements_stock(produit_sk);
CREATE INDEX IF NOT EXISTS idx_fait_mvt_type ON dwh.fait_mouvements_stock(type_mouvement);

-- -----------------------------------------------------------------------------
-- fait_ventes_restaurant : Ventes plats restaurant
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fait_ventes_restaurant (
    vente_id SERIAL PRIMARY KEY,
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    plat_sk INT NOT NULL REFERENCES dwh.dim_plat(plat_sk),
    canal_id INT REFERENCES dwh.dim_canal(canal_id),
    -- Dimensions dégénérées
    source TEXT,                                -- Caisse/Uber/Deliveroo...
    source_ref TEXT,                            -- Référence commande
    -- Mesures
    quantite NUMERIC(12,4) NOT NULL,
    ca_ttc NUMERIC(14,2) NOT NULL,
    ca_ht NUMERIC(14,2),
    tva NUMERIC(12,2),
    cout_matiere NUMERIC(14,4),
    marge_brute NUMERIC(14,2),
    commission NUMERIC(12,2) DEFAULT 0,
    -- Métadonnées
    vente_source_id INT,                        -- ID original (restaurant_sales.id)
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fait_ventes_date ON dwh.fait_ventes_restaurant(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_ventes_plat ON dwh.fait_ventes_restaurant(plat_sk);
CREATE INDEX IF NOT EXISTS idx_fait_ventes_canal ON dwh.fait_ventes_restaurant(canal_id);

-- -----------------------------------------------------------------------------
-- fait_depenses : Dépenses globales (épicerie + restaurant)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fait_depenses (
    depense_id SERIAL PRIMARY KEY,
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    tenant_id INT NOT NULL,
    cost_center_id INT REFERENCES dwh.dim_cost_center(cost_center_id),
    categorie_depense_id INT REFERENCES dwh.dim_categorie_depense(categorie_depense_id),
    fournisseur_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),
    -- Dimensions dégénérées
    libelle TEXT NOT NULL,
    ref_externe TEXT,
    -- Mesures
    montant_ht NUMERIC(12,2),
    tva_pct NUMERIC(5,2),
    tva NUMERIC(12,2),
    montant_ttc NUMERIC(12,2),
    -- Métadonnées
    depense_source_id INT,
    source TEXT,                                -- facture/bank_statement
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fait_depenses_date ON dwh.fait_depenses(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_depenses_tenant ON dwh.fait_depenses(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fait_depenses_cc ON dwh.fait_depenses(cost_center_id);

-- -----------------------------------------------------------------------------
-- fait_stock_quotidien : Snapshot stock fin de journée
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fait_stock_quotidien (
    snapshot_id SERIAL PRIMARY KEY,
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    produit_sk INT NOT NULL REFERENCES dwh.dim_produit(produit_sk),
    -- Mesures
    stock_quantite NUMERIC(12,3) NOT NULL,
    stock_valeur NUMERIC(14,2),
    conso_moy_30j NUMERIC(12,3),                -- Consommation moyenne 30 jours
    jours_stock NUMERIC(8,1),                   -- stock / conso moyenne
    -- Alertes
    est_rupture BOOLEAN DEFAULT FALSE,
    est_surstock BOOLEAN DEFAULT FALSE,
    -- Contrainte unicité
    UNIQUE(date_id, produit_sk)
);

CREATE INDEX IF NOT EXISTS idx_fait_stock_date ON dwh.fait_stock_quotidien(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_stock_rupture ON dwh.fait_stock_quotidien(est_rupture) WHERE est_rupture = TRUE;

-- =============================================================================
-- 3. GÉNÉRATION DIMENSION TEMPS (5 ans)
-- =============================================================================

CREATE OR REPLACE FUNCTION dwh.generer_dim_temps(
    p_date_debut DATE DEFAULT '2020-01-01',
    p_date_fin DATE DEFAULT '2030-12-31'
)
RETURNS INT AS $$
DECLARE
    v_date DATE;
    v_count INT := 0;
    v_jours_feries DATE[];
    v_saison TEXT;
BEGIN
    -- Jours fériés France (à compléter selon les années)
    v_jours_feries := ARRAY[
        -- 2024
        '2024-01-01', '2024-04-01', '2024-05-01', '2024-05-08', '2024-05-09', 
        '2024-05-20', '2024-07-14', '2024-08-15', '2024-11-01', '2024-11-11', '2024-12-25',
        -- 2025
        '2025-01-01', '2025-04-21', '2025-05-01', '2025-05-08', '2025-05-29',
        '2025-06-09', '2025-07-14', '2025-08-15', '2025-11-01', '2025-11-11', '2025-12-25',
        -- 2026
        '2026-01-01', '2026-04-06', '2026-05-01', '2026-05-08', '2026-05-14',
        '2026-05-25', '2026-07-14', '2026-08-15', '2026-11-01', '2026-11-11', '2026-12-25'
    ]::DATE[];

    v_date := p_date_debut;
    
    WHILE v_date <= p_date_fin LOOP
        -- Déterminer la saison
        v_saison := CASE 
            WHEN EXTRACT(MONTH FROM v_date) IN (3,4,5) THEN 'Printemps'
            WHEN EXTRACT(MONTH FROM v_date) IN (6,7,8) THEN 'Été'
            WHEN EXTRACT(MONTH FROM v_date) IN (9,10,11) THEN 'Automne'
            ELSE 'Hiver'
        END;
        
        INSERT INTO dwh.dim_temps (
            date_id, date_complete, jour, jour_semaine, nom_jour,
            semaine_iso, mois, nom_mois, trimestre, annee,
            annee_mois, annee_semaine, est_weekend, est_ferie, saison
        ) VALUES (
            TO_CHAR(v_date, 'YYYYMMDD')::INT,
            v_date,
            EXTRACT(DAY FROM v_date)::INT,
            EXTRACT(ISODOW FROM v_date)::INT,
            TO_CHAR(v_date, 'TMDay'),
            EXTRACT(WEEK FROM v_date)::INT,
            EXTRACT(MONTH FROM v_date)::INT,
            TO_CHAR(v_date, 'TMMonth'),
            EXTRACT(QUARTER FROM v_date)::INT,
            EXTRACT(YEAR FROM v_date)::INT,
            TO_CHAR(v_date, 'YYYY-MM'),
            TO_CHAR(v_date, 'IYYY-"W"IW'),
            EXTRACT(ISODOW FROM v_date) IN (6, 7),
            v_date = ANY(v_jours_feries),
            v_saison
        )
        ON CONFLICT (date_id) DO NOTHING;
        
        v_count := v_count + 1;
        v_date := v_date + INTERVAL '1 day';
    END LOOP;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Générer 2020-2030
SELECT dwh.generer_dim_temps();

-- =============================================================================
-- 4. CATÉGORIES PRODUITS
-- =============================================================================
-- Les 91 catégories produits sont dans dwh.dim_categorie_produit
-- Voir le script dwh_categories.sql pour la définition complète

-- =============================================================================
-- 5. CENTRES DE COÛTS DWH
-- =============================================================================

INSERT INTO dwh.dim_cost_center (tenant_id, nom, type, budget_mensuel)
SELECT tenant_id, nom, 
    CASE 
        WHEN nom IN ('Loyer', 'Assurance', 'Abonnements/IT') THEN 'Fixe'
        ELSE 'Variable'
    END,
    NULL
FROM public.restaurant_cost_centers
ON CONFLICT (tenant_id, nom) DO NOTHING;

-- =============================================================================
-- 6. VUES ANALYTIQUES PRÉ-AGRÉGÉES
-- =============================================================================

-- Vue CA quotidien restaurant
CREATE OR REPLACE VIEW dwh.v_ca_quotidien_restaurant AS
SELECT 
    t.date_complete,
    t.jour_semaine,
    t.nom_jour,
    t.annee_mois,
    c.nom AS canal,
    SUM(v.quantite) AS nb_plats,
    SUM(v.ca_ttc) AS ca_ttc,
    SUM(v.ca_ht) AS ca_ht,
    SUM(v.marge_brute) AS marge_brute,
    SUM(v.commission) AS commissions,
    ROUND(AVG(v.ca_ttc / NULLIF(v.quantite, 0)), 2) AS prix_moyen
FROM dwh.fait_ventes_restaurant v
JOIN dwh.dim_temps t ON v.date_id = t.date_id
LEFT JOIN dwh.dim_canal c ON v.canal_id = c.canal_id
GROUP BY t.date_complete, t.jour_semaine, t.nom_jour, t.annee_mois, c.nom;

-- Vue valorisation stock épicerie
CREATE OR REPLACE VIEW dwh.v_valorisation_stock AS
SELECT
    t.date_complete,
    c.famille,
    c.nom AS categorie,
    SUM(s.stock_quantite) AS quantite_totale,
    SUM(s.stock_valeur) AS valeur_totale,
    SUM(CASE WHEN s.est_rupture THEN 1 ELSE 0 END) AS nb_ruptures,
    AVG(s.jours_stock) AS rotation_moyenne
FROM dwh.fait_stock_quotidien s
JOIN dwh.dim_temps t ON s.date_id = t.date_id
JOIN dwh.dim_produit p ON s.produit_sk = p.produit_sk
JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
GROUP BY t.date_complete, c.famille, c.nom;

-- Vue synthèse dépenses
CREATE OR REPLACE VIEW dwh.v_synthese_depenses AS
SELECT 
    t.annee,
    t.mois,
    t.annee_mois,
    d.tenant_id,
    cc.nom AS centre_cout,
    cc.type AS type_cout,
    SUM(d.montant_ht) AS total_ht,
    SUM(d.montant_ttc) AS total_ttc,
    cc.budget_mensuel,
    ROUND(SUM(d.montant_ht) / NULLIF(cc.budget_mensuel, 0) * 100, 1) AS execution_pct
FROM dwh.fait_depenses d
JOIN dwh.dim_temps t ON d.date_id = t.date_id
LEFT JOIN dwh.dim_cost_center cc ON d.cost_center_id = cc.cost_center_id
GROUP BY t.annee, t.mois, t.annee_mois, d.tenant_id, cc.nom, cc.type, cc.budget_mensuel;

-- Vue top produits épicerie
CREATE OR REPLACE VIEW dwh.v_top_produits_epicerie AS
SELECT
    p.nom AS produit,
    c.famille,
    c.nom AS categorie,
    SUM(CASE WHEN m.type_mouvement = 'SORTIE' THEN m.quantite ELSE 0 END) AS volume_vendu,
    SUM(CASE WHEN m.type_mouvement = 'SORTIE' THEN m.valeur_mouvement ELSE 0 END) AS ca_total,
    SUM(CASE WHEN m.type_mouvement = 'SORTIE' THEN m.quantite * p.marge_unitaire ELSE 0 END) AS marge_totale,
    p.marge_pct
FROM dwh.fait_mouvements_stock m
JOIN dwh.dim_produit p ON m.produit_sk = p.produit_sk AND p.est_actuel = TRUE
JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
GROUP BY p.produit_sk, p.nom, c.famille, c.nom, p.marge_pct;

-- Vue top plats restaurant
CREATE OR REPLACE VIEW dwh.v_top_plats_restaurant AS
SELECT 
    p.nom AS plat,
    p.categorie,
    SUM(v.quantite) AS nb_vendus,
    SUM(v.ca_ttc) AS ca_ttc,
    SUM(v.marge_brute) AS marge_brute,
    p.ratio_cout AS food_cost_pct,
    RANK() OVER (ORDER BY SUM(v.marge_brute) DESC) AS rang_marge,
    RANK() OVER (ORDER BY SUM(v.quantite) DESC) AS rang_volume
FROM dwh.fait_ventes_restaurant v
JOIN dwh.dim_plat p ON v.plat_sk = p.plat_sk AND p.est_actuel = TRUE
GROUP BY p.plat_sk, p.nom, p.categorie, p.ratio_cout;

-- =============================================================================
-- 7. PROCÉDURE ETL : Migration données existantes → DWH
-- =============================================================================

CREATE OR REPLACE PROCEDURE dwh.etl_migration_initiale()
LANGUAGE plpgsql AS $$
DECLARE
    v_count INT;
BEGIN
    RAISE NOTICE 'Début migration initiale vers DWH...';
    
    -- 1. Migration des produits
    INSERT INTO dwh.dim_produit (
        produit_id, tenant_id, nom, categorie_id,
        prix_achat, prix_vente, tva_pct, seuil_alerte,
        date_debut, est_actuel
    )
    SELECT 
        p.id,
        COALESCE(p.tenant_id, 1),
        p.nom,
        c.categorie_id,
        p.prix_achat,
        p.prix_vente,
        p.tva,
        p.seuil_alerte,
        p.created_at::DATE,
        TRUE
    FROM public.produits p
    LEFT JOIN dwh.dim_categorie_produit c ON c.code = CASE p.categorie::TEXT
            WHEN 'Epicerie sucree' THEN 'EPIC_BISCUITS'
            WHEN 'Epicerie salee' THEN 'EPIC_CONSERVES'
            WHEN 'Boissons' THEN 'BOIS_SODA'
            WHEN 'Alcool' THEN 'ALC_BIERE'
            WHEN 'Afrique' THEN 'MONDE_AFRIQUE'
            WHEN 'Hygiene' THEN 'HYG_CORPS'
            ELSE 'DIV_AUTRE'
        END
    WHERE NOT EXISTS (
        SELECT 1 FROM dwh.dim_produit dp 
        WHERE dp.produit_id = p.id AND dp.est_actuel = TRUE
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE '  - Produits migrés: %', v_count;
    
    -- 2. Migration des plats restaurant
    INSERT INTO dwh.dim_plat (
        plat_id, tenant_id, restaurant_id, nom, categorie,
        prix_vente_ttc, cout_matiere, nb_ingredients, actif,
        date_debut, est_actuel
    )
    SELECT 
        rp.id,
        rp.tenant_id,
        rp.restaurant_id,
        rp.nom,
        rp.categorie,
        rp.prix_vente_ttc,
        COALESCE(rc.cout_matiere, 0),
        (SELECT COUNT(*) FROM public.restaurant_plat_ingredients rpi WHERE rpi.plat_id = rp.id),
        rp.actif,
        CURRENT_DATE,
        TRUE
    FROM public.restaurant_plats rp
    LEFT JOIN public.restaurant_plat_costs rc ON rc.plat_id = rp.id
    WHERE NOT EXISTS (
        SELECT 1 FROM dwh.dim_plat dp 
        WHERE dp.plat_id = rp.id AND dp.est_actuel = TRUE
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE '  - Plats migrés: %', v_count;
    
    -- 3. Migration des mouvements de stock
    INSERT INTO dwh.fait_mouvements_stock (
        date_id, produit_sk, type_mouvement, source,
        quantite, sens, prix_unitaire, valeur_mouvement, mouvement_source_id
    )
    SELECT 
        TO_CHAR(m.date_mvt, 'YYYYMMDD')::INT,
        dp.produit_sk,
        m.type::TEXT,
        m.source,
        m.quantite,
        CASE WHEN m.type IN ('ENTREE', 'INVENTAIRE') THEN 1 ELSE -1 END,
        p.prix_achat,
        m.quantite * COALESCE(p.prix_achat, 0),
        m.id
    FROM public.mouvements_stock m
    JOIN public.produits p ON p.id = m.produit_id
    JOIN dwh.dim_produit dp ON dp.produit_id = m.produit_id AND dp.est_actuel = TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM dwh.fait_mouvements_stock f WHERE f.mouvement_source_id = m.id
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE '  - Mouvements stock migrés: %', v_count;
    
    -- 4. Migration des ventes restaurant
    INSERT INTO dwh.fait_ventes_restaurant (
        date_id, plat_sk, source, source_ref,
        quantite, ca_ttc, ca_ht, cout_matiere, marge_brute, vente_source_id
    )
    SELECT 
        TO_CHAR(rs.sold_at, 'YYYYMMDD')::INT,
        dp.plat_sk,
        rs.source,
        rs.source_ref,
        rs.quantity,
        rs.quantity * rp.prix_vente_ttc,
        rs.quantity * rp.prix_vente_ttc / 1.10,  -- Approximation TVA 10%
        rs.quantity * COALESCE(rc.cout_matiere, 0),
        rs.quantity * (rp.prix_vente_ttc / 1.10 - COALESCE(rc.cout_matiere, 0)),
        rs.id
    FROM public.restaurant_sales rs
    JOIN public.restaurant_plats rp ON rp.id = rs.plat_id
    JOIN dwh.dim_plat dp ON dp.plat_id = rs.plat_id AND dp.est_actuel = TRUE
    LEFT JOIN public.restaurant_plat_costs rc ON rc.plat_id = rs.plat_id
    WHERE NOT EXISTS (
        SELECT 1 FROM dwh.fait_ventes_restaurant f WHERE f.vente_source_id = rs.id
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE '  - Ventes restaurant migrées: %', v_count;
    
    -- 5. Migration des dépenses
    INSERT INTO dwh.fait_depenses (
        date_id, tenant_id, cost_center_id, libelle, ref_externe,
        montant_ht, tva_pct, montant_ttc, depense_source_id, source
    )
    SELECT 
        TO_CHAR(rd.date_operation, 'YYYYMMDD')::INT,
        rd.tenant_id,
        dcc.cost_center_id,
        rd.libelle,
        rd.ref_externe,
        rd.montant_ht,
        rd.tva_pct,
        rd.montant_ht * (1 + COALESCE(rd.tva_pct, 0) / 100),
        rd.id,
        'depense'
    FROM public.restaurant_depenses rd
    LEFT JOIN dwh.dim_cost_center dcc ON dcc.cost_center_id = rd.cost_center_id
    WHERE NOT EXISTS (
        SELECT 1 FROM dwh.fait_depenses f 
        WHERE f.depense_source_id = rd.id AND f.source = 'depense'
    );
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE '  - Dépenses migrées: %', v_count;
    
    RAISE NOTICE 'Migration initiale terminée.';
END;
$$;

-- =============================================================================
-- 8. COMMENTAIRES TABLES
-- =============================================================================

COMMENT ON SCHEMA dwh IS 'Data Warehouse - Modèle dimensionnel NOUTAM & L''Incontournable';
COMMENT ON TABLE dwh.dim_temps IS 'Dimension temporelle pré-générée (2020-2030)';
COMMENT ON TABLE dwh.dim_produit IS 'Dimension produits épicerie avec SCD Type 2';
COMMENT ON TABLE dwh.dim_plat IS 'Dimension plats restaurant avec SCD Type 2';
COMMENT ON TABLE dwh.fait_mouvements_stock IS 'Faits mouvements stock épicerie';
COMMENT ON TABLE dwh.fait_ventes_restaurant IS 'Faits ventes plats restaurant';
COMMENT ON TABLE dwh.fait_depenses IS 'Faits dépenses multi-tenant';
COMMENT ON TABLE dwh.fait_stock_quotidien IS 'Snapshot quotidien stock épicerie';

-- =============================================================================
-- FIN DU SCRIPT
-- =============================================================================
