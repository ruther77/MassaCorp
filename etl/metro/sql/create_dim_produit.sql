-- =============================================================================
-- RÉFÉRENTIEL PRODUIT - MassaCorp
-- =============================================================================
-- Table maître des produits avec normalisation des désignations
-- Gère les différents conditionnements (unité, colis, pack)
-- =============================================================================

-- =============================================================================
-- Table: dim_marque
-- Référentiel des marques connues pour normalisation
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.dim_marque (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    nom VARCHAR(100) NOT NULL,
    nom_court VARCHAR(50),
    fournisseur VARCHAR(100),
    categorie_defaut VARCHAR(50),
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Marques courantes
INSERT INTO dwh.dim_marque (code, nom, nom_court, categorie_defaut) VALUES
-- Spiritueux
('GLENFIDDICH', 'Glenfiddich', 'Glenfiddich', 'Spiritueux'),
('JDANIELS', 'Jack Daniel''s', 'Jack Daniel''s', 'Spiritueux'),
('JWALKER', 'Johnnie Walker', 'J. Walker', 'Spiritueux'),
('CHIVAS', 'Chivas Regal', 'Chivas', 'Spiritueux'),
('BALLANTINES', 'Ballantine''s', 'Ballantine''s', 'Spiritueux'),
('JAMESON', 'Jameson', 'Jameson', 'Spiritueux'),
('ABSOLUT', 'Absolut', 'Absolut', 'Spiritueux'),
('SMIRNOFF', 'Smirnoff', 'Smirnoff', 'Spiritueux'),
('GREY_GOOSE', 'Grey Goose', 'Grey Goose', 'Spiritueux'),
('BACARDI', 'Bacardi', 'Bacardi', 'Spiritueux'),
('HAVANA', 'Havana Club', 'Havana', 'Spiritueux'),
('RICARD', 'Ricard', 'Ricard', 'Spiritueux'),
('PASTIS51', 'Pastis 51', 'Pastis 51', 'Spiritueux'),
('HENNESSY', 'Hennessy', 'Hennessy', 'Spiritueux'),
('MARTELL', 'Martell', 'Martell', 'Spiritueux'),
('COURVOISIER', 'Courvoisier', 'Courvoisier', 'Spiritueux'),
-- Champagnes
('VEUVE_CLICQUOT', 'Veuve Clicquot', 'V. Clicquot', 'Champagnes'),
('MOET', 'Moët & Chandon', 'Moët', 'Champagnes'),
('RUINART', 'Ruinart', 'Ruinart', 'Champagnes'),
('DOM_PERIGNON', 'Dom Pérignon', 'Dom Pérignon', 'Champagnes'),
('TAITTINGER', 'Taittinger', 'Taittinger', 'Champagnes'),
('MUMM', 'G.H. Mumm', 'Mumm', 'Champagnes'),
-- Bières
('HEINEKEN', 'Heineken', 'Heineken', 'Bières'),
('KRONENBOURG', 'Kronenbourg', 'Kronen.', 'Bières'),
('1664', '1664', '1664', 'Bières'),
('LEFFE', 'Leffe', 'Leffe', 'Bières'),
('STELLA', 'Stella Artois', 'Stella', 'Bières'),
('CORONA', 'Corona', 'Corona', 'Bières'),
('DESPERADOS', 'Desperados', 'Desperados', 'Bières'),
('GRIMBERGEN', 'Grimbergen', 'Grimbergen', 'Bières'),
('PELFORTH', 'Pelforth', 'Pelforth', 'Bières'),
('GUINNESS', 'Guinness', 'Guinness', 'Bières'),
('AFFLIGEM', 'Affligem', 'Affligem', 'Bières'),
-- Soft drinks
('COCA', 'Coca-Cola', 'Coca', 'Soft drinks'),
('PEPSI', 'Pepsi', 'Pepsi', 'Soft drinks'),
('ORANGINA', 'Orangina', 'Orangina', 'Soft drinks'),
('SCHWEPPES', 'Schweppes', 'Schweppes', 'Soft drinks'),
('PERRIER', 'Perrier', 'Perrier', 'Soft drinks'),
('EVIAN', 'Evian', 'Evian', 'Soft drinks'),
('VITTEL', 'Vittel', 'Vittel', 'Soft drinks'),
('REDBULL', 'Red Bull', 'Red Bull', 'Soft drinks')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- Table: dim_produit
-- Référentiel maître des produits
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.dim_produit (
    id BIGSERIAL PRIMARY KEY,

    -- Identification
    ean VARCHAR(20) NOT NULL,
    ean_colis VARCHAR(20),           -- EAN du colis si différent
    article_numero VARCHAR(20),

    -- Désignation
    designation_brute VARCHAR(500),   -- Désignation originale du PDF
    designation_clean VARCHAR(255),   -- Désignation nettoyée
    nom_court VARCHAR(100),           -- Nom court pour affichage

    -- Classification
    marque_id INTEGER REFERENCES dwh.dim_marque(id),
    marque VARCHAR(100),
    type_produit VARCHAR(50),         -- Whisky, Bière, Vin, etc.

    -- Catégorisation unifiée
    famille VARCHAR(50) NOT NULL DEFAULT 'DIVERS',
    categorie VARCHAR(50) NOT NULL DEFAULT 'Divers',
    sous_categorie VARCHAR(50),

    -- Caractéristiques
    contenance_cl NUMERIC(8,2),       -- En centilitres
    contenance_label VARCHAR(20),     -- "75CL", "1L", etc.
    degre_alcool NUMERIC(4,1),

    -- Conditionnement
    type_conditionnement VARCHAR(20) DEFAULT 'UNITE',  -- UNITE, COLIS, PACK
    colisage_standard INTEGER DEFAULT 1,
    poids_unitaire_kg NUMERIC(8,3),

    -- TVA
    taux_tva NUMERIC(5,2) DEFAULT 20,
    code_tva VARCHAR(5),

    -- Classification METRO
    regie VARCHAR(5),

    -- Prix de référence (dernier connu)
    prix_achat_unitaire NUMERIC(10,4),
    prix_achat_colis NUMERIC(10,4),
    prix_vente_conseille NUMERIC(10,4),
    date_dernier_prix DATE,

    -- Statistiques
    nb_achats INTEGER DEFAULT 0,
    quantite_totale_achetee NUMERIC(12,2) DEFAULT 0,
    montant_total_achats NUMERIC(14,2) DEFAULT 0,

    -- Métadonnées
    source VARCHAR(20) DEFAULT 'METRO',
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Contraintes
    CONSTRAINT uq_dim_produit_ean UNIQUE (ean)
);

-- Index
CREATE INDEX IF NOT EXISTS ix_dim_produit_ean ON dwh.dim_produit(ean);
CREATE INDEX IF NOT EXISTS ix_dim_produit_marque ON dwh.dim_produit(marque);
CREATE INDEX IF NOT EXISTS ix_dim_produit_famille ON dwh.dim_produit(famille);
CREATE INDEX IF NOT EXISTS ix_dim_produit_categorie ON dwh.dim_produit(categorie);
CREATE INDEX IF NOT EXISTS ix_dim_produit_nom ON dwh.dim_produit(nom_court);

-- =============================================================================
-- Table: dim_produit_alias
-- Alias pour les désignations différentes d'un même produit
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.dim_produit_alias (
    id BIGSERIAL PRIMARY KEY,
    produit_id BIGINT NOT NULL REFERENCES dwh.dim_produit(id) ON DELETE CASCADE,
    designation_alias VARCHAR(500) NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_produit_alias UNIQUE (produit_id, designation_alias)
);

CREATE INDEX IF NOT EXISTS ix_produit_alias_designation ON dwh.dim_produit_alias(designation_alias);

-- =============================================================================
-- Table: dim_produit_prix_historique
-- Historique des prix d'achat
-- =============================================================================
CREATE TABLE IF NOT EXISTS dwh.dim_produit_prix_historique (
    id BIGSERIAL PRIMARY KEY,
    produit_id BIGINT NOT NULL REFERENCES dwh.dim_produit(id) ON DELETE CASCADE,
    date_prix DATE NOT NULL,
    prix_unitaire NUMERIC(10,4) NOT NULL,
    prix_colis NUMERIC(10,4),
    colisage INTEGER,
    source VARCHAR(50),
    facture_numero VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_produit_prix_hist ON dwh.dim_produit_prix_historique(produit_id, date_prix DESC);

-- =============================================================================
-- Fonction: Normaliser une désignation
-- =============================================================================
CREATE OR REPLACE FUNCTION dwh.normaliser_designation(p_designation TEXT)
RETURNS TABLE (
    designation_clean VARCHAR(255),
    nom_court VARCHAR(100),
    marque VARCHAR(100),
    type_produit VARCHAR(50),
    contenance_cl NUMERIC(8,2),
    contenance_label VARCHAR(20),
    degre_alcool NUMERIC(4,1)
) AS $$
DECLARE
    v_clean TEXT;
    v_marque VARCHAR(100);
    v_type VARCHAR(50);
    v_contenance NUMERIC(8,2);
    v_contenance_label VARCHAR(20);
    v_degre NUMERIC(4,1);
    v_nom_court VARCHAR(100);
BEGIN
    IF p_designation IS NULL OR p_designation = '' THEN
        RETURN QUERY SELECT
            NULL::VARCHAR(255), NULL::VARCHAR(100), NULL::VARCHAR(100),
            NULL::VARCHAR(50), NULL::NUMERIC(8,2), NULL::VARCHAR(20), NULL::NUMERIC(4,1);
        RETURN;
    END IF;

    -- Nettoyer la désignation
    v_clean := UPPER(TRIM(p_designation));

    -- Supprimer les codes parasites au début (ex: "12012 203290*2")
    v_clean := REGEXP_REPLACE(v_clean, '^\d+\s+\d+\*\d+\s*', '');
    v_clean := REGEXP_REPLACE(v_clean, '^\d{4,}\s+', '');

    -- Supprimer les suffixes parasites (codes techniques)
    v_clean := REGEXP_REPLACE(v_clean, '\s+[A-Z]\s+\d+[,.]?\d*\s+\d+[,.]?\d*\s+\d+[,.]?\d*$', '');
    v_clean := REGEXP_REPLACE(v_clean, '\s+[STBM]\s+\d+[pP,.]?\d*\s+\d+[,.]?\d*\s+\d+[,.]?\d*$', '');
    v_clean := REGEXP_REPLACE(v_clean, '\s+[a-z]\s*$', '');
    v_clean := REGEXP_REPLACE(v_clean, '\s+\*+\s*$', '');
    v_clean := REGEXP_REPLACE(v_clean, '\s+//\s*$', '');

    -- Extraire la contenance
    IF v_clean ~ '(\d+(?:[,\.]\d+)?)\s*CL' THEN
        v_contenance_label := (REGEXP_MATCH(v_clean, '(\d+(?:[,\.]\d+)?)\s*CL'))[1] || 'CL';
        v_contenance := REPLACE((REGEXP_MATCH(v_clean, '(\d+(?:[,\.]\d+)?)\s*CL'))[1], ',', '.')::NUMERIC;
    ELSIF v_clean ~ '(\d+(?:[,\.]\d+)?)\s*L\b' THEN
        v_contenance_label := (REGEXP_MATCH(v_clean, '(\d+(?:[,\.]\d+)?)\s*L\b'))[1] || 'L';
        v_contenance := REPLACE((REGEXP_MATCH(v_clean, '(\d+(?:[,\.]\d+)?)\s*L\b'))[1], ',', '.')::NUMERIC * 100;
    ELSIF v_clean ~ '(\d+)\s*ML' THEN
        v_contenance_label := (REGEXP_MATCH(v_clean, '(\d+)\s*ML'))[1] || 'ML';
        v_contenance := (REGEXP_MATCH(v_clean, '(\d+)\s*ML'))[1]::NUMERIC / 10;
    END IF;

    -- Extraire le degré d'alcool
    IF v_clean ~ '(\d+(?:[,\.]\d+)?)\s*[°D]' THEN
        v_degre := REPLACE((REGEXP_MATCH(v_clean, '(\d+(?:[,\.]\d+)?)\s*[°D]'))[1], ',', '.')::NUMERIC;
        -- Vérifier que c'est un degré raisonnable (pas un volume)
        IF v_degre > 80 THEN v_degre := NULL; END IF;
    END IF;

    -- Détecter la marque
    v_marque := NULL;

    -- Whisky
    IF v_clean ~ 'GLENFIDDICH' THEN v_marque := 'Glenfiddich'; v_type := 'Whisky';
    ELSIF v_clean ~ 'J\.?\s*DANIEL|JACK\s*DANIEL' THEN v_marque := 'Jack Daniel''s'; v_type := 'Whisky';
    ELSIF v_clean ~ 'J\.?\s*WALKER|JOHNNIE\s*WALKER' THEN v_marque := 'Johnnie Walker'; v_type := 'Whisky';
    ELSIF v_clean ~ 'CHIVAS' THEN v_marque := 'Chivas'; v_type := 'Whisky';
    ELSIF v_clean ~ 'BALLANTINE' THEN v_marque := 'Ballantine''s'; v_type := 'Whisky';
    ELSIF v_clean ~ 'JAMESON' THEN v_marque := 'Jameson'; v_type := 'Whisky';
    ELSIF v_clean ~ 'LAGAVULIN' THEN v_marque := 'Lagavulin'; v_type := 'Whisky';
    ELSIF v_clean ~ 'TALISKER' THEN v_marque := 'Talisker'; v_type := 'Whisky';

    -- Vodka
    ELSIF v_clean ~ 'ABSOLUT' THEN v_marque := 'Absolut'; v_type := 'Vodka';
    ELSIF v_clean ~ 'SMIRNOFF' THEN v_marque := 'Smirnoff'; v_type := 'Vodka';
    ELSIF v_clean ~ 'GREY\s*GOOSE' THEN v_marque := 'Grey Goose'; v_type := 'Vodka';
    ELSIF v_clean ~ 'POLIAKOV' THEN v_marque := 'Poliakov'; v_type := 'Vodka';
    ELSIF v_clean ~ 'CIROC' THEN v_marque := 'Cîroc'; v_type := 'Vodka';

    -- Rhum
    ELSIF v_clean ~ 'BACARDI|BACA\s' THEN v_marque := 'Bacardi'; v_type := 'Rhum';
    ELSIF v_clean ~ 'HAVANA' THEN v_marque := 'Havana Club'; v_type := 'Rhum';
    ELSIF v_clean ~ 'CAPTAIN\s*MORGAN' THEN v_marque := 'Captain Morgan'; v_type := 'Rhum';

    -- Cognac
    ELSIF v_clean ~ 'HENNESSY' THEN v_marque := 'Hennessy'; v_type := 'Cognac';
    ELSIF v_clean ~ 'MARTELL' THEN v_marque := 'Martell'; v_type := 'Cognac';
    ELSIF v_clean ~ 'COURVOISIER' THEN v_marque := 'Courvoisier'; v_type := 'Cognac';
    ELSIF v_clean ~ 'MEUKOV' THEN v_marque := 'Meukov'; v_type := 'Cognac';

    -- Anisés
    ELSIF v_clean ~ 'RICARD' THEN v_marque := 'Ricard'; v_type := 'Pastis';
    ELSIF v_clean ~ 'PASTIS\s*51|51\s' THEN v_marque := 'Pastis 51'; v_type := 'Pastis';

    -- Champagnes
    ELSIF v_clean ~ 'VEUVE|V\.?\s*CLICQUOT|CLIQUOT' THEN v_marque := 'Veuve Clicquot'; v_type := 'Champagne';
    ELSIF v_clean ~ 'MOET|MOËT' THEN v_marque := 'Moët & Chandon'; v_type := 'Champagne';
    ELSIF v_clean ~ 'RUINART' THEN v_marque := 'Ruinart'; v_type := 'Champagne';
    ELSIF v_clean ~ 'DOM\s*PERIGNON|PERIGNON' THEN v_marque := 'Dom Pérignon'; v_type := 'Champagne';
    ELSIF v_clean ~ 'TAITTINGER' THEN v_marque := 'Taittinger'; v_type := 'Champagne';
    ELSIF v_clean ~ 'MUMM' THEN v_marque := 'Mumm'; v_type := 'Champagne';

    -- Bières
    ELSIF v_clean ~ 'HEINEKEN' THEN v_marque := 'Heineken'; v_type := 'Bière';
    ELSIF v_clean ~ 'KRONENBOURG' THEN v_marque := 'Kronenbourg'; v_type := 'Bière';
    ELSIF v_clean ~ '1664' THEN v_marque := '1664'; v_type := 'Bière';
    ELSIF v_clean ~ 'LEFFE' THEN v_marque := 'Leffe'; v_type := 'Bière';
    ELSIF v_clean ~ 'STELLA' THEN v_marque := 'Stella Artois'; v_type := 'Bière';
    ELSIF v_clean ~ 'CORONA' THEN v_marque := 'Corona'; v_type := 'Bière';
    ELSIF v_clean ~ 'DESPERADOS' THEN v_marque := 'Desperados'; v_type := 'Bière';
    ELSIF v_clean ~ 'GRIMBERGEN' THEN v_marque := 'Grimbergen'; v_type := 'Bière';
    ELSIF v_clean ~ 'PELFORTH' THEN v_marque := 'Pelforth'; v_type := 'Bière';
    ELSIF v_clean ~ 'GUINNESS' THEN v_marque := 'Guinness'; v_type := 'Bière';
    ELSIF v_clean ~ 'AFFLIGEM' THEN v_marque := 'Affligem'; v_type := 'Bière';

    -- Soft drinks
    ELSIF v_clean ~ 'COCA' THEN v_marque := 'Coca-Cola'; v_type := 'Soft';
    ELSIF v_clean ~ 'PEPSI' THEN v_marque := 'Pepsi'; v_type := 'Soft';
    ELSIF v_clean ~ 'ORANGINA' THEN v_marque := 'Orangina'; v_type := 'Soft';
    ELSIF v_clean ~ 'SCHWEPPES' THEN v_marque := 'Schweppes'; v_type := 'Soft';
    ELSIF v_clean ~ 'PERRIER' THEN v_marque := 'Perrier'; v_type := 'Eau';
    ELSIF v_clean ~ 'EVIAN' THEN v_marque := 'Evian'; v_type := 'Eau';
    ELSIF v_clean ~ 'RED\s*BULL' THEN v_marque := 'Red Bull'; v_type := 'Energy';
    END IF;

    -- Construire le nom court
    IF v_marque IS NOT NULL THEN
        v_nom_court := v_marque;
        IF v_type IS NOT NULL AND v_type NOT IN ('Bière', 'Soft', 'Eau') THEN
            v_nom_court := v_nom_court;
        END IF;
        IF v_contenance_label IS NOT NULL THEN
            v_nom_court := v_nom_court || ' ' || v_contenance_label;
        END IF;
        IF v_degre IS NOT NULL AND v_degre > 0 THEN
            v_nom_court := v_nom_court || ' ' || v_degre || '°';
        END IF;
    ELSE
        -- Pas de marque reconnue, utiliser la désignation nettoyée tronquée
        v_nom_court := LEFT(v_clean, 80);
    END IF;

    -- Nettoyer encore la désignation
    v_clean := REGEXP_REPLACE(v_clean, '\s+', ' ', 'g');
    v_clean := TRIM(v_clean);

    RETURN QUERY SELECT
        LEFT(v_clean, 255)::VARCHAR(255),
        LEFT(v_nom_court, 100)::VARCHAR(100),
        v_marque::VARCHAR(100),
        v_type::VARCHAR(50),
        v_contenance,
        v_contenance_label::VARCHAR(20),
        v_degre;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Fonction: Trouver ou créer un produit
-- =============================================================================
CREATE OR REPLACE FUNCTION dwh.upsert_produit(
    p_ean VARCHAR(20),
    p_designation VARCHAR(500),
    p_article_numero VARCHAR(20) DEFAULT NULL,
    p_prix_unitaire NUMERIC DEFAULT NULL,
    p_colisage INTEGER DEFAULT 1,
    p_regie VARCHAR(5) DEFAULT NULL,
    p_taux_tva NUMERIC DEFAULT 20,
    p_date_prix DATE DEFAULT CURRENT_DATE
)
RETURNS BIGINT AS $$
DECLARE
    v_produit_id BIGINT;
    v_norm RECORD;
    v_famille VARCHAR(50);
    v_categorie VARCHAR(50);
BEGIN
    -- Vérifier si le produit existe
    SELECT id INTO v_produit_id FROM dwh.dim_produit WHERE ean = p_ean;

    -- Normaliser la désignation
    SELECT * INTO v_norm FROM dwh.normaliser_designation(p_designation);

    -- Déterminer famille/catégorie
    IF p_regie = 'S' THEN
        v_famille := 'BOISSONS'; v_categorie := 'Spiritueux';
    ELSIF p_regie = 'B' THEN
        v_famille := 'BOISSONS'; v_categorie := 'Bières';
    ELSIF p_regie = 'T' THEN
        v_famille := 'BOISSONS'; v_categorie := 'Vins';
    ELSIF p_regie = 'M' THEN
        v_famille := 'BOISSONS'; v_categorie := 'Champagnes';
    ELSIF v_norm.type_produit IS NOT NULL THEN
        v_famille := 'BOISSONS';
        v_categorie := v_norm.type_produit;
    ELSE
        v_famille := 'EPICERIE';
        v_categorie := 'Divers';
    END IF;

    IF v_produit_id IS NULL THEN
        -- Créer le produit
        INSERT INTO dwh.dim_produit (
            ean, article_numero,
            designation_brute, designation_clean, nom_court,
            marque, type_produit,
            famille, categorie,
            contenance_cl, contenance_label, degre_alcool,
            colisage_standard, regie, taux_tva,
            prix_achat_unitaire, prix_achat_colis, date_dernier_prix,
            nb_achats, source
        ) VALUES (
            p_ean, p_article_numero,
            p_designation, v_norm.designation_clean, v_norm.nom_court,
            v_norm.marque, v_norm.type_produit,
            v_famille, v_categorie,
            v_norm.contenance_cl, v_norm.contenance_label, v_norm.degre_alcool,
            COALESCE(p_colisage, 1), p_regie, p_taux_tva,
            p_prix_unitaire, p_prix_unitaire * COALESCE(p_colisage, 1), p_date_prix,
            1, 'METRO'
        )
        RETURNING id INTO v_produit_id;

    ELSE
        -- Mettre à jour le produit existant
        UPDATE dwh.dim_produit SET
            article_numero = COALESCE(p_article_numero, article_numero),
            prix_achat_unitaire = COALESCE(p_prix_unitaire, prix_achat_unitaire),
            prix_achat_colis = COALESCE(p_prix_unitaire * COALESCE(p_colisage, colisage_standard), prix_achat_colis),
            date_dernier_prix = CASE WHEN p_prix_unitaire IS NOT NULL THEN p_date_prix ELSE date_dernier_prix END,
            nb_achats = nb_achats + 1,
            updated_at = NOW()
        WHERE id = v_produit_id;

        -- Ajouter l'alias si différent
        IF p_designation IS NOT NULL AND p_designation != '' THEN
            INSERT INTO dwh.dim_produit_alias (produit_id, designation_alias, source)
            VALUES (v_produit_id, p_designation, 'METRO')
            ON CONFLICT (produit_id, designation_alias) DO NOTHING;
        END IF;
    END IF;

    -- Historique des prix
    IF p_prix_unitaire IS NOT NULL THEN
        INSERT INTO dwh.dim_produit_prix_historique (
            produit_id, date_prix, prix_unitaire, prix_colis, colisage, source
        ) VALUES (
            v_produit_id, p_date_prix, p_prix_unitaire,
            p_prix_unitaire * COALESCE(p_colisage, 1), p_colisage, 'METRO'
        );
    END IF;

    RETURN v_produit_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Trigger: updated_at automatique
-- =============================================================================
CREATE OR REPLACE FUNCTION dwh.update_dim_produit_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_dim_produit_updated ON dwh.dim_produit;
CREATE TRIGGER tr_dim_produit_updated
    BEFORE UPDATE ON dwh.dim_produit
    FOR EACH ROW
    EXECUTE FUNCTION dwh.update_dim_produit_timestamp();

-- Commentaires
COMMENT ON TABLE dwh.dim_produit IS 'Référentiel maître des produits avec normalisation';
COMMENT ON TABLE dwh.dim_marque IS 'Référentiel des marques pour normalisation automatique';
COMMENT ON TABLE dwh.dim_produit_alias IS 'Alias des désignations pour un même produit (EAN)';
COMMENT ON TABLE dwh.dim_produit_prix_historique IS 'Historique des prix d''achat';
COMMENT ON FUNCTION dwh.normaliser_designation IS 'Normalise une désignation produit et extrait marque, contenance, degré';
COMMENT ON FUNCTION dwh.upsert_produit IS 'Trouve ou crée un produit dans le référentiel';
