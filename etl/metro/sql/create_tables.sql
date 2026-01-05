-- =============================================================================
-- METRO DWH Tables - MassaCorp
-- =============================================================================
-- Tables pour stocker les données factures fournisseur METRO
-- avec support multi-tenant et catégorisation unifiée
-- =============================================================================

-- Création du schéma si nécessaire
CREATE SCHEMA IF NOT EXISTS dwh;

-- =============================================================================
-- Table: metro_facture
-- Entêtes de factures METRO
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.metro_facture (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,

    -- Identification facture
    numero VARCHAR(50) NOT NULL,
    date_facture DATE NOT NULL,
    magasin VARCHAR(100) NOT NULL,

    -- Totaux
    total_ht NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_tva NUMERIC(12, 2) NOT NULL DEFAULT 0,
    total_ttc NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Métadonnées
    fichier_source VARCHAR(255),
    importee_le TIMESTAMPTZ DEFAULT NOW(),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Contraintes
    CONSTRAINT uq_metro_facture_numero UNIQUE (tenant_id, numero)
);

-- Index
CREATE INDEX IF NOT EXISTS ix_metro_facture_tenant ON dwh.metro_facture(tenant_id);
CREATE INDEX IF NOT EXISTS ix_metro_facture_numero ON dwh.metro_facture(tenant_id, numero);
CREATE INDEX IF NOT EXISTS ix_metro_facture_date ON dwh.metro_facture(tenant_id, date_facture);

-- =============================================================================
-- Table: metro_ligne
-- Lignes de factures METRO (détail des produits)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.metro_ligne (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    facture_id BIGINT NOT NULL REFERENCES dwh.metro_facture(id) ON DELETE CASCADE,

    -- Identification produit
    ean VARCHAR(20) NOT NULL,
    article_numero VARCHAR(20),
    designation VARCHAR(255) NOT NULL,

    -- Colisage et quantités
    colisage INTEGER NOT NULL DEFAULT 1,
    quantite_colis NUMERIC(10, 3) NOT NULL,
    quantite_unitaire NUMERIC(10, 3) NOT NULL,

    -- Prix
    prix_colis NUMERIC(10, 4) NOT NULL,
    prix_unitaire NUMERIC(10, 4) NOT NULL,
    montant_ht NUMERIC(12, 2) NOT NULL,

    -- Volume/Poids
    volume_unitaire NUMERIC(10, 4),
    poids_unitaire NUMERIC(10, 4),
    unite VARCHAR(10) NOT NULL DEFAULT 'U',

    -- TVA
    taux_tva NUMERIC(5, 2) NOT NULL DEFAULT 20,
    code_tva VARCHAR(5),
    montant_tva NUMERIC(12, 2) NOT NULL DEFAULT 0,

    -- Classification source METRO
    regie VARCHAR(5),
    vol_alcool NUMERIC(5, 2),

    -- Lien catégorie unifiée
    categorie_id BIGINT
);

-- Index
CREATE INDEX IF NOT EXISTS ix_metro_ligne_tenant ON dwh.metro_ligne(tenant_id);
CREATE INDEX IF NOT EXISTS ix_metro_ligne_facture ON dwh.metro_ligne(facture_id);
CREATE INDEX IF NOT EXISTS ix_metro_ligne_ean ON dwh.metro_ligne(tenant_id, ean);

-- =============================================================================
-- Table: metro_produit_agregat
-- Vue matérialisée des produits agrégés par EAN
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.metro_produit_agregat (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,

    -- Identification
    ean VARCHAR(20) NOT NULL,
    article_numero VARCHAR(20),
    designation VARCHAR(255) NOT NULL,

    -- Colisage
    colisage_moyen INTEGER NOT NULL DEFAULT 1,
    unite VARCHAR(10) NOT NULL DEFAULT 'U',
    volume_unitaire NUMERIC(10, 4),

    -- Agrégats quantités
    quantite_colis_totale NUMERIC(12, 3) NOT NULL DEFAULT 0,
    quantite_unitaire_totale NUMERIC(12, 3) NOT NULL DEFAULT 0,

    -- Montants
    montant_total_ht NUMERIC(14, 2) NOT NULL DEFAULT 0,
    montant_total_tva NUMERIC(14, 2) NOT NULL DEFAULT 0,
    montant_total NUMERIC(14, 2) NOT NULL DEFAULT 0,
    nb_achats BIGINT NOT NULL DEFAULT 0,

    -- Prix unitaires réels (par unité, pas par colis)
    prix_unitaire_moyen NUMERIC(10, 4) NOT NULL DEFAULT 0,
    prix_unitaire_min NUMERIC(10, 4) NOT NULL DEFAULT 0,
    prix_unitaire_max NUMERIC(10, 4) NOT NULL DEFAULT 0,
    prix_colis_moyen NUMERIC(10, 4) NOT NULL DEFAULT 0,

    -- TVA
    taux_tva NUMERIC(5, 2) NOT NULL DEFAULT 20,

    -- Classification unifiée
    categorie_id BIGINT,
    famille VARCHAR(50) NOT NULL DEFAULT 'DIVERS',
    categorie VARCHAR(50) NOT NULL DEFAULT 'Divers',
    sous_categorie VARCHAR(50),

    -- Classification source METRO
    regie VARCHAR(5),
    vol_alcool NUMERIC(5, 2),

    -- Dates
    premier_achat DATE,
    dernier_achat DATE,

    -- Métadonnées
    calcule_le TIMESTAMPTZ DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT uq_metro_produit_ean UNIQUE (tenant_id, ean)
);

-- Index
CREATE INDEX IF NOT EXISTS ix_metro_produit_tenant ON dwh.metro_produit_agregat(tenant_id);
CREATE INDEX IF NOT EXISTS ix_metro_produit_ean ON dwh.metro_produit_agregat(tenant_id, ean);
CREATE INDEX IF NOT EXISTS ix_metro_produit_categorie ON dwh.metro_produit_agregat(tenant_id, categorie_id);
CREATE INDEX IF NOT EXISTS ix_metro_produit_famille ON dwh.metro_produit_agregat(tenant_id, famille);
CREATE INDEX IF NOT EXISTS ix_metro_produit_montant ON dwh.metro_produit_agregat(tenant_id, montant_total DESC);

-- =============================================================================
-- Trigger: updated_at automatique
-- =============================================================================
CREATE OR REPLACE FUNCTION dwh.update_metro_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_metro_facture_updated ON dwh.metro_facture;
CREATE TRIGGER tr_metro_facture_updated
    BEFORE UPDATE ON dwh.metro_facture
    FOR EACH ROW
    EXECUTE FUNCTION dwh.update_metro_updated_at();

-- =============================================================================
-- Fonction: Recalculer les agrégats produits
-- =============================================================================
CREATE OR REPLACE FUNCTION dwh.recalculer_metro_agregats(p_tenant_id BIGINT)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    -- Supprimer les anciens agrégats
    DELETE FROM dwh.metro_produit_agregat WHERE tenant_id = p_tenant_id;

    -- Insérer les nouveaux agrégats
    INSERT INTO dwh.metro_produit_agregat (
        tenant_id, ean, article_numero, designation,
        colisage_moyen, unite, volume_unitaire,
        quantite_colis_totale, quantite_unitaire_totale,
        montant_total_ht, montant_total_tva, montant_total,
        nb_achats,
        prix_unitaire_moyen, prix_unitaire_min, prix_unitaire_max, prix_colis_moyen,
        taux_tva,
        categorie_id, famille, categorie, sous_categorie,
        regie, vol_alcool,
        premier_achat, dernier_achat, calcule_le
    )
    SELECT
        l.tenant_id,
        l.ean,
        MAX(l.article_numero) as article_numero,
        MAX(l.designation) as designation,
        -- Colisage moyen (mode statistique)
        COALESCE(CAST(AVG(l.colisage) AS INTEGER), 1) as colisage_moyen,
        MAX(l.unite) as unite,
        MAX(l.volume_unitaire) as volume_unitaire,
        -- Quantités
        SUM(l.quantite_colis) as quantite_colis_totale,
        SUM(l.quantite_unitaire) as quantite_unitaire_totale,
        -- Montants
        SUM(l.montant_ht) as montant_total_ht,
        SUM(l.montant_tva) as montant_total_tva,
        SUM(l.montant_ht + l.montant_tva) as montant_total,
        COUNT(*) as nb_achats,
        -- Prix unitaires réels
        AVG(l.prix_unitaire) as prix_unitaire_moyen,
        MIN(l.prix_unitaire) as prix_unitaire_min,
        MAX(l.prix_unitaire) as prix_unitaire_max,
        AVG(l.prix_colis) as prix_colis_moyen,
        -- TVA (taux le plus fréquent)
        MODE() WITHIN GROUP (ORDER BY l.taux_tva) as taux_tva,
        -- Classification unifiée (à mapper via dim_categorie_produit)
        MAX(l.categorie_id) as categorie_id,
        CASE
            WHEN MAX(l.regie) IN ('S', 'B', 'T', 'M') THEN 'BOISSONS'
            ELSE 'EPICERIE'
        END as famille,
        CASE
            WHEN MAX(l.regie) = 'S' THEN 'Spiritueux'
            WHEN MAX(l.regie) = 'B' THEN 'Bières'
            WHEN MAX(l.regie) = 'T' THEN 'Vins'
            WHEN MAX(l.regie) = 'M' THEN 'Alcools'
            ELSE 'Epicerie'
        END as categorie,
        NULL as sous_categorie,
        -- Classification METRO
        MAX(l.regie) as regie,
        MAX(l.vol_alcool) as vol_alcool,
        -- Dates
        MIN(f.date_facture) as premier_achat,
        MAX(f.date_facture) as dernier_achat,
        NOW() as calcule_le
    FROM dwh.metro_ligne l
    JOIN dwh.metro_facture f ON l.facture_id = f.id
    WHERE l.tenant_id = p_tenant_id
      AND l.ean IS NOT NULL
      AND l.ean != ''
    GROUP BY l.tenant_id, l.ean;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Vue: Résumé global METRO
-- =============================================================================
CREATE OR REPLACE VIEW dwh.v_metro_summary AS
SELECT
    f.tenant_id,
    COUNT(DISTINCT f.id) as nb_factures,
    COUNT(DISTINCT l.ean) as nb_produits,
    COUNT(l.id) as nb_lignes,
    SUM(f.total_ht) / NULLIF(COUNT(DISTINCT f.id), 0) * COUNT(DISTINCT f.id) as total_ht,
    SUM(f.total_tva) / NULLIF(COUNT(DISTINCT f.id), 0) * COUNT(DISTINCT f.id) as total_tva,
    SUM(f.total_ttc) / NULLIF(COUNT(DISTINCT f.id), 0) * COUNT(DISTINCT f.id) as total_ttc,
    MIN(f.date_facture) as date_premiere_facture,
    MAX(f.date_facture) as date_derniere_facture
FROM dwh.metro_facture f
LEFT JOIN dwh.metro_ligne l ON f.id = l.facture_id
GROUP BY f.tenant_id;

-- Commentaires
COMMENT ON TABLE dwh.metro_facture IS 'Entêtes de factures fournisseur METRO';
COMMENT ON TABLE dwh.metro_ligne IS 'Lignes de factures METRO avec détail des produits';
COMMENT ON TABLE dwh.metro_produit_agregat IS 'Produits METRO agrégés par EAN pour le catalogue';
COMMENT ON FUNCTION dwh.recalculer_metro_agregats IS 'Recalcule les agrégats produits pour un tenant';
