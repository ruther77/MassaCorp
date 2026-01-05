-- =============================================================================
-- Migration des produits existants vers dim_produit
-- =============================================================================
-- Ce script migre les produits de metro_produit_agregat vers dim_produit
-- avec normalisation des désignations
-- =============================================================================

-- Ajouter des marques de vins pour meilleure reconnaissance
INSERT INTO dwh.dim_marque (code, nom, nom_court, categorie_defaut) VALUES
('TOUR_PRIGNAC', 'Tour de Prignac', 'Tour Prignac', 'Vins'),
('MONDESIR', 'Mondesir', 'Mondesir', 'Vins'),
('BARON_ROTHSCHILD', 'Baron de Rothschild', 'B. Rothschild', 'Vins'),
('MOUTON_CADET', 'Mouton Cadet', 'Mouton Cadet', 'Vins')
ON CONFLICT (code) DO NOTHING;

-- Fonction temporaire pour la migration
CREATE OR REPLACE FUNCTION dwh.migrer_produits_metro()
RETURNS TABLE (
    nb_produits_migres INTEGER,
    nb_alias_crees INTEGER
) AS $$
DECLARE
    v_nb_produits INTEGER := 0;
    v_nb_alias INTEGER := 0;
    v_rec RECORD;
    v_produit_id BIGINT;
    v_norm RECORD;
    v_famille VARCHAR(50);
    v_categorie VARCHAR(50);
BEGIN
    -- Parcourir tous les produits agrégés
    FOR v_rec IN
        SELECT DISTINCT ON (ean)
            ean,
            designation,
            article_numero,
            colisage_moyen,
            prix_unitaire_moyen,
            taux_tva,
            regie,
            famille,
            categorie,
            montant_total_ht,
            quantite_unitaire_totale,
            nb_achats,
            dernier_achat
        FROM dwh.metro_produit_agregat
        WHERE ean IS NOT NULL AND ean != ''
        ORDER BY ean, nb_achats DESC
    LOOP
        -- Vérifier si le produit existe déjà
        SELECT id INTO v_produit_id FROM dwh.dim_produit WHERE ean = v_rec.ean;

        -- Normaliser la désignation
        SELECT * INTO v_norm FROM dwh.normaliser_designation(v_rec.designation);

        -- Déterminer famille/catégorie depuis régie ou existant
        IF v_rec.regie = 'S' THEN
            v_famille := 'BOISSONS'; v_categorie := 'Spiritueux';
        ELSIF v_rec.regie = 'B' THEN
            v_famille := 'BOISSONS'; v_categorie := 'Bières';
        ELSIF v_rec.regie = 'T' THEN
            v_famille := 'BOISSONS'; v_categorie := 'Vins';
        ELSIF v_rec.regie = 'M' THEN
            v_famille := 'BOISSONS'; v_categorie := 'Champagnes';
        ELSIF v_norm.type_produit IS NOT NULL THEN
            v_famille := 'BOISSONS';
            v_categorie := v_norm.type_produit;
        ELSE
            v_famille := COALESCE(v_rec.famille, 'EPICERIE');
            v_categorie := COALESCE(v_rec.categorie, 'Divers');
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
                nb_achats, quantite_totale_achetee, montant_total_achats,
                source
            ) VALUES (
                v_rec.ean, v_rec.article_numero,
                v_rec.designation,
                COALESCE(v_norm.designation_clean, v_rec.designation),
                COALESCE(v_norm.nom_court, LEFT(v_rec.designation, 80)),
                v_norm.marque, v_norm.type_produit,
                v_famille, v_categorie,
                v_norm.contenance_cl, v_norm.contenance_label, v_norm.degre_alcool,
                COALESCE(v_rec.colisage_moyen, 1),
                v_rec.regie,
                COALESCE(v_rec.taux_tva, 20),
                v_rec.prix_unitaire_moyen,
                v_rec.prix_unitaire_moyen * COALESCE(v_rec.colisage_moyen, 1),
                v_rec.dernier_achat,
                v_rec.nb_achats,
                v_rec.quantite_unitaire_totale,
                v_rec.montant_total_ht,
                'METRO'
            )
            RETURNING id INTO v_produit_id;

            v_nb_produits := v_nb_produits + 1;
        END IF;

        -- Ajouter tous les alias (désignations différentes pour le même EAN)
        INSERT INTO dwh.dim_produit_alias (produit_id, designation_alias, source)
        SELECT DISTINCT v_produit_id, l.designation, 'METRO'
        FROM dwh.metro_ligne l
        WHERE l.ean = v_rec.ean
          AND l.designation IS NOT NULL
          AND l.designation != ''
        ON CONFLICT (produit_id, designation_alias) DO NOTHING;

        GET DIAGNOSTICS v_nb_alias = ROW_COUNT;

    END LOOP;

    RETURN QUERY SELECT v_nb_produits, v_nb_alias;
END;
$$ LANGUAGE plpgsql;

-- Exécuter la migration
SELECT * FROM dwh.migrer_produits_metro();

-- Afficher les statistiques
SELECT
    'dim_produit' as table_name,
    COUNT(*) as nb_rows,
    COUNT(DISTINCT marque) as nb_marques,
    COUNT(*) FILTER (WHERE marque IS NOT NULL) as avec_marque,
    COUNT(*) FILTER (WHERE marque IS NULL) as sans_marque
FROM dwh.dim_produit;

-- Top des produits normalisés
SELECT
    nom_court,
    marque,
    type_produit,
    contenance_label,
    degre_alcool,
    prix_achat_unitaire,
    nb_achats
FROM dwh.dim_produit
WHERE marque IS NOT NULL
ORDER BY nb_achats DESC
LIMIT 20;

-- Produits non reconnus (à améliorer)
SELECT
    designation_brute,
    nom_court,
    famille,
    categorie,
    nb_achats
FROM dwh.dim_produit
WHERE marque IS NULL
ORDER BY nb_achats DESC
LIMIT 20;
