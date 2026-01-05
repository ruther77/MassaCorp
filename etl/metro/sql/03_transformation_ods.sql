-- =============================================================================
-- ETL METRO - Transformation vers ODS
-- =============================================================================
-- Transformation des données staging validées vers ODS
-- Conforme à l'architecture SID CIF (Corporate Information Factory)
-- =============================================================================

-- Schema ODS (si non existant)
CREATE SCHEMA IF NOT EXISTS ods;

-- -----------------------------------------------------------------------------
-- Table: ods.ods_facture_entete
-- Description: En-têtes de factures validées (données tactiques)
-- Rétention: 1-3 mois
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ods.ods_facture_entete (
    facture_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INT DEFAULT 1,

    -- Identification
    numero_facture VARCHAR(100) NOT NULL,
    numero_interne VARCHAR(50),
    date_facture DATE NOT NULL,
    date_echeance DATE,

    -- Fournisseur
    fournisseur_nom VARCHAR(200) NOT NULL,
    fournisseur_siret VARCHAR(20),
    fournisseur_tva_intra VARCHAR(20),
    magasin_nom VARCHAR(100),
    magasin_code VARCHAR(10),

    -- Client
    client_nom VARCHAR(200),
    client_numero VARCHAR(50),
    client_adresse TEXT,

    -- Totaux
    montant_total_ht NUMERIC(14,2) NOT NULL,
    montant_total_tva NUMERIC(14,2),
    montant_total_ttc NUMERIC(14,2),

    -- Statut
    statut VARCHAR(20) DEFAULT 'VALIDE',
    date_validation TIMESTAMPTZ,
    date_paiement DATE,
    mode_paiement VARCHAR(50),

    -- Traçabilité
    source_batch_id UUID NOT NULL,
    source VARCHAR(20) DEFAULT 'METRO',

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uk_ods_facture_numero UNIQUE (numero_facture, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_ods_facture_date ON ods.ods_facture_entete(date_facture);
CREATE INDEX IF NOT EXISTS idx_ods_facture_fournisseur ON ods.ods_facture_entete(fournisseur_siret);
CREATE INDEX IF NOT EXISTS idx_ods_facture_statut ON ods.ods_facture_entete(statut);


-- -----------------------------------------------------------------------------
-- Table: ods.ods_facture_ligne
-- Description: Lignes de factures validées avec calculs métier
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ods.ods_facture_ligne (
    ligne_id SERIAL PRIMARY KEY,
    facture_id UUID NOT NULL REFERENCES ods.ods_facture_entete(facture_id),
    tenant_id INT DEFAULT 1,

    -- Position
    ligne_numero INT NOT NULL,

    -- Produit
    produit_ean VARCHAR(20),
    article_numero VARCHAR(20),
    designation TEXT NOT NULL,
    categorie_code VARCHAR(20),
    categorie_nom VARCHAR(100),

    -- Caractéristiques
    regie CHAR(1),
    est_alcool BOOLEAN DEFAULT FALSE,
    vol_alcool NUMERIC(5,2),
    poids_volume NUMERIC(12,4),
    unite VARCHAR(10),

    -- Prix et quantités (brut)
    quantite INT NOT NULL,
    prix_unitaire_ht NUMERIC(12,4) NOT NULL,
    montant_ligne_ht NUMERIC(14,2) NOT NULL,

    -- TVA
    code_tva CHAR(1),
    taux_tva NUMERIC(5,2) NOT NULL,
    montant_tva NUMERIC(14,2),
    montant_ttc NUMERIC(14,2),

    -- CALCULS DÉRIVÉS
    prix_au_litre NUMERIC(12,4),               -- Prix HT / volume
    volume_alcool_pur NUMERIC(12,4),           -- qté × volume × degré / 100
    cotis_secu NUMERIC(10,2),

    -- Promo
    est_promo BOOLEAN DEFAULT FALSE,
    remise_pct NUMERIC(5,2),
    remise_montant NUMERIC(10,2),

    -- Traçabilité
    source_batch_id UUID NOT NULL,
    source_ligne_id INT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ods_ligne_facture ON ods.ods_facture_ligne(facture_id);
CREATE INDEX IF NOT EXISTS idx_ods_ligne_ean ON ods.ods_facture_ligne(produit_ean);
CREATE INDEX IF NOT EXISTS idx_ods_ligne_categorie ON ods.ods_facture_ligne(categorie_code);


-- -----------------------------------------------------------------------------
-- Fonction: staging.transformer_vers_ods
-- Description: Transformation Staging → ODS avec calculs métier
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.transformer_vers_ods(p_batch_id UUID)
RETURNS TABLE(
    nb_entetes INT,
    nb_lignes INT,
    montant_total_ht NUMERIC
) AS $$
DECLARE
    v_nb_entetes INT := 0;
    v_nb_lignes INT := 0;
    v_montant_ht NUMERIC := 0;
BEGIN
    -- 1. Insertion des en-têtes de factures
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
        montant_total_ht,
        montant_total_tva,
        montant_total_ttc,
        statut,
        date_validation,
        source_batch_id,
        source
    )
    SELECT
        MD5(numero_facture || MIN(date_facture)::TEXT)::UUID,
        numero_facture,
        MIN(numero_interne),
        MIN(date_facture),
        MIN(fournisseur_nom),
        MIN(fournisseur_siret),
        MIN(magasin_nom),
        MIN(client_nom),
        MIN(client_numero),
        SUM(montant_ligne),
        SUM(montant_ligne * COALESCE(taux_tva, 20) / 100),
        SUM(montant_ligne * (1 + COALESCE(taux_tva, 20) / 100)),
        'VALIDE',
        NOW(),
        p_batch_id,
        'METRO'
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id
      AND extraction_status = 'VALIDE'
      AND numero_facture IS NOT NULL
    GROUP BY numero_facture
    ON CONFLICT (numero_facture, tenant_id) DO UPDATE SET
        montant_total_ht = EXCLUDED.montant_total_ht,
        montant_total_tva = EXCLUDED.montant_total_tva,
        montant_total_ttc = EXCLUDED.montant_total_ttc,
        updated_at = NOW();

    GET DIAGNOSTICS v_nb_entetes = ROW_COUNT;

    -- 2. Insertion des lignes avec calculs dérivés
    INSERT INTO ods.ods_facture_ligne (
        facture_id,
        ligne_numero,
        produit_ean,
        article_numero,
        designation,
        categorie_code,
        categorie_nom,
        regie,
        est_alcool,
        vol_alcool,
        poids_volume,
        unite,
        quantite,
        prix_unitaire_ht,
        montant_ligne_ht,
        code_tva,
        taux_tva,
        montant_tva,
        montant_ttc,
        prix_au_litre,
        volume_alcool_pur,
        cotis_secu,
        est_promo,
        source_batch_id,
        source_ligne_id
    )
    SELECT
        -- Facture ID (hash)
        MD5(s.numero_facture || s.date_facture::TEXT)::UUID,

        -- Position
        s.ligne_numero,

        -- Produit
        s.ean,
        s.article_numero,
        COALESCE(s.designation, 'Article inconnu'),
        COALESCE(m.categorie_dwh_code, 'INCONNU'),
        COALESCE(m.nom_regie, s.categorie_source),

        -- Caractéristiques
        s.regie,
        s.regie IN ('S', 'B', 'M', 'T'),
        s.vol_alcool,
        s.poids_volume,
        s.unite,

        -- Mesures brutes
        COALESCE(s.quantite, 1),
        COALESCE(s.prix_unitaire, 0),
        COALESCE(s.montant_ligne, 0),

        -- TVA
        COALESCE(s.code_tva, 'D'),
        COALESCE(s.taux_tva, 20),
        ROUND(COALESCE(s.montant_ligne, 0) * COALESCE(s.taux_tva, 20) / 100, 2),
        ROUND(COALESCE(s.montant_ligne, 0) * (1 + COALESCE(s.taux_tva, 20) / 100), 2),

        -- CALCULS DÉRIVÉS
        -- Prix au litre
        CASE
            WHEN s.poids_volume > 0 AND s.unite = 'L'
            THEN ROUND(s.prix_unitaire / s.poids_volume, 4)
            ELSE NULL
        END,

        -- Volume Alcool Pur (VAP)
        CASE
            WHEN s.regie IN ('S', 'B', 'M', 'T') AND s.poids_volume > 0 AND s.vol_alcool > 0
            THEN ROUND(COALESCE(s.quantite, 1) * s.poids_volume * s.vol_alcool / 100, 4)
            ELSE 0
        END,

        -- Cotisation sécurité sociale
        s.cotis_secu,

        -- Promo
        s.est_promo,

        -- Traçabilité
        p_batch_id,
        s.id

    FROM staging.stg_facture_ligne s
    LEFT JOIN staging.mapping_regie_categorie m ON m.regie = s.regie
    WHERE s.batch_id = p_batch_id
      AND s.extraction_status = 'VALIDE'
      AND s.numero_facture IS NOT NULL;

    GET DIAGNOSTICS v_nb_lignes = ROW_COUNT;

    -- 3. Calcul montant total
    SELECT SUM(montant_ligne_ht) INTO v_montant_ht
    FROM ods.ods_facture_ligne
    WHERE source_batch_id = p_batch_id;

    RETURN QUERY SELECT v_nb_entetes, v_nb_lignes, COALESCE(v_montant_ht, 0);
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Vue: ods.v_factures_a_valider
-- Description: Factures en attente de traitement (Oper Mart tactique)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW ods.v_factures_a_valider AS
SELECT
    f.facture_id,
    f.numero_facture,
    f.numero_interne,
    f.date_facture,
    f.fournisseur_nom,
    f.magasin_nom,
    f.client_nom,
    f.montant_total_ht,
    f.montant_total_ttc,
    f.statut,
    f.date_echeance,

    -- Alertes
    CURRENT_DATE - f.date_facture AS jours_depuis_facture,
    CASE
        WHEN f.date_echeance IS NOT NULL
        THEN f.date_echeance - CURRENT_DATE
        ELSE NULL
    END AS jours_avant_echeance,

    -- Priorité
    CASE
        WHEN f.date_echeance IS NOT NULL AND f.date_echeance <= CURRENT_DATE THEN 'URGENT'
        WHEN f.date_echeance IS NOT NULL AND f.date_echeance <= CURRENT_DATE + 7 THEN 'PRIORITAIRE'
        ELSE 'NORMAL'
    END AS priorite,

    -- Stats lignes
    (SELECT COUNT(*) FROM ods.ods_facture_ligne l WHERE l.facture_id = f.facture_id) AS nb_lignes,
    (SELECT COUNT(DISTINCT categorie_code) FROM ods.ods_facture_ligne l WHERE l.facture_id = f.facture_id) AS nb_categories

FROM ods.ods_facture_entete f
WHERE f.statut IN ('VALIDE', 'EN_ATTENTE', 'A_COMPLETER')
ORDER BY
    CASE WHEN f.date_echeance IS NOT NULL AND f.date_echeance <= CURRENT_DATE THEN 0 ELSE 1 END,
    f.date_echeance NULLS LAST,
    f.date_facture DESC;


-- -----------------------------------------------------------------------------
-- Vue: ods.v_achats_par_categorie
-- Description: Agrégation des achats par catégorie (Oper Mart)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW ods.v_achats_par_categorie AS
SELECT
    DATE_TRUNC('month', f.date_facture)::DATE AS mois,
    l.categorie_code,
    l.categorie_nom,
    l.est_alcool,
    f.fournisseur_nom,

    COUNT(DISTINCT f.facture_id) AS nb_factures,
    COUNT(*) AS nb_lignes,
    SUM(l.quantite) AS quantite_totale,
    SUM(l.montant_ligne_ht) AS montant_ht,
    SUM(l.montant_tva) AS montant_tva,
    SUM(l.montant_ttc) AS montant_ttc,
    AVG(l.prix_unitaire_ht) AS prix_moyen,

    -- Spécifique alcool
    SUM(l.volume_alcool_pur) AS vap_total

FROM ods.ods_facture_ligne l
JOIN ods.ods_facture_entete f ON f.facture_id = l.facture_id
GROUP BY
    DATE_TRUNC('month', f.date_facture),
    l.categorie_code,
    l.categorie_nom,
    l.est_alcool,
    f.fournisseur_nom
ORDER BY mois DESC, montant_ht DESC;


-- -----------------------------------------------------------------------------
-- Vue: ods.v_top_produits
-- Description: Top produits par volume d'achat
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW ods.v_top_produits AS
SELECT
    l.produit_ean,
    l.designation,
    l.categorie_nom,
    l.regie,
    COUNT(DISTINCT l.facture_id) AS nb_factures,
    SUM(l.quantite) AS quantite_totale,
    SUM(l.montant_ligne_ht) AS montant_total_ht,
    AVG(l.prix_unitaire_ht) AS prix_moyen,
    MIN(l.prix_unitaire_ht) AS prix_min,
    MAX(l.prix_unitaire_ht) AS prix_max,
    MIN(f.date_facture) AS premiere_facture,
    MAX(f.date_facture) AS derniere_facture
FROM ods.ods_facture_ligne l
JOIN ods.ods_facture_entete f ON f.facture_id = l.facture_id
WHERE l.produit_ean IS NOT NULL
GROUP BY l.produit_ean, l.designation, l.categorie_nom, l.regie
ORDER BY montant_total_ht DESC;


COMMENT ON TABLE ods.ods_facture_entete IS 'En-têtes factures METRO validées - données tactiques ODS';
COMMENT ON TABLE ods.ods_facture_ligne IS 'Lignes factures METRO avec calculs métier - ODS';
COMMENT ON FUNCTION staging.transformer_vers_ods IS 'Transformation Staging → ODS avec calculs dérivés';
