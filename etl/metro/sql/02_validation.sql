-- =============================================================================
-- ETL METRO - Validation & Nettoyage
-- =============================================================================
-- Fonctions de validation et nettoyage des données staging
-- Conforme à l'architecture SID CIF (Corporate Information Factory)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Fonction: staging.valider_facture_lignes
-- Description: Valide toutes les lignes d'un batch
-- Règles: V1-V10 (voir documentation)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.valider_facture_lignes(p_batch_id UUID)
RETURNS TABLE(
    ligne_id INT,
    status VARCHAR,
    nb_erreurs INT,
    errors JSONB
) AS $$
DECLARE
    r RECORD;
    v_errors JSONB;
    v_montant_calcule NUMERIC;
BEGIN
    FOR r IN
        SELECT * FROM staging.stg_facture_ligne
        WHERE batch_id = p_batch_id
    LOOP
        v_errors := '[]'::JSONB;

        -- V1: Numéro facture obligatoire
        IF r.numero_facture IS NULL OR TRIM(r.numero_facture) = '' THEN
            v_errors := v_errors || '["V1: Numéro facture manquant"]'::JSONB;
        END IF;

        -- V2: Date facture valide (pas dans le futur, pas trop ancienne)
        IF r.date_facture IS NULL THEN
            v_errors := v_errors || '["V2: Date facture manquante"]'::JSONB;
        ELSIF r.date_facture > CURRENT_DATE THEN
            v_errors := v_errors || '["V2: Date facture dans le futur"]'::JSONB;
        ELSIF r.date_facture < CURRENT_DATE - INTERVAL '5 years' THEN
            v_errors := v_errors || '["V2: Date facture trop ancienne (> 5 ans)"]'::JSONB;
        END IF;

        -- V3: Montant ligne cohérent (prix × qté ≈ montant)
        IF r.prix_unitaire IS NOT NULL AND r.quantite IS NOT NULL AND r.montant_ligne IS NOT NULL THEN
            v_montant_calcule := r.prix_unitaire * r.quantite;
            IF ABS(v_montant_calcule - r.montant_ligne) > 0.10 THEN
                v_errors := v_errors || jsonb_build_array(
                    format('V3: Montant incohérent: %.2f × %s = %.2f ≠ %.2f',
                           r.prix_unitaire, r.quantite, v_montant_calcule, r.montant_ligne)
                );
            END IF;
        END IF;

        -- V4: EAN format valide (8 ou 13 chiffres)
        IF r.ean IS NOT NULL AND r.ean !~ '^[0-9]{8}$|^[0-9]{13}$' THEN
            v_errors := v_errors || jsonb_build_array(
                format('V4: Format EAN invalide: %s', r.ean)
            );
        END IF;

        -- V5: TVA cohérente avec régie
        IF r.regie = 'S' AND r.code_tva IS NOT NULL AND r.code_tva != 'D' THEN
            v_errors := v_errors || '["V5: Spiritueux devrait avoir TVA=D (20%)"]'::JSONB;
        END IF;

        -- V6: Volume alcool obligatoire pour produits alcoolisés
        IF r.regie IN ('S', 'B', 'M', 'T') AND r.vol_alcool IS NULL THEN
            v_errors := v_errors || '["V6: Degré alcool manquant pour produit alcoolisé"]'::JSONB;
        END IF;

        -- V7: Quantité positive
        IF r.quantite IS NOT NULL AND r.quantite <= 0 THEN
            v_errors := v_errors || '["V7: Quantité doit être positive"]'::JSONB;
        END IF;

        -- V8: Prix unitaire positif
        IF r.prix_unitaire IS NOT NULL AND r.prix_unitaire < 0 THEN
            v_errors := v_errors || '["V8: Prix unitaire négatif"]'::JSONB;
        END IF;

        -- V9: Désignation non vide
        IF r.designation IS NULL OR TRIM(r.designation) = '' THEN
            v_errors := v_errors || '["V9: Désignation produit manquante"]'::JSONB;
        END IF;

        -- V10: Taux TVA valide
        IF r.taux_tva IS NOT NULL AND r.taux_tva NOT IN (0, 5.5, 10, 20) THEN
            v_errors := v_errors || jsonb_build_array(
                format('V10: Taux TVA non standard: %.2f%%', r.taux_tva)
            );
        END IF;

        -- Mise à jour du statut
        UPDATE staging.stg_facture_ligne
        SET
            extraction_status = CASE
                WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'
                ELSE 'ERREUR'
            END,
            validation_errors = v_errors,
            updated_at = NOW()
        WHERE id = r.id;

        RETURN QUERY SELECT
            r.id,
            CASE WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'::VARCHAR ELSE 'ERREUR'::VARCHAR END,
            jsonb_array_length(v_errors)::INT,
            v_errors;
    END LOOP;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: staging.nettoyer_facture_lignes
-- Description: Applique les règles de nettoyage (N1-N6)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.nettoyer_facture_lignes(p_batch_id UUID)
RETURNS TABLE(
    regle VARCHAR,
    nb_modifies INT
) AS $$
DECLARE
    v_count INT;
BEGIN
    -- N1: Trim espaces sur les chaînes
    UPDATE staging.stg_facture_ligne
    SET
        designation = TRIM(designation),
        fournisseur_nom = TRIM(fournisseur_nom),
        client_nom = TRIM(client_nom),
        magasin_nom = TRIM(magasin_nom),
        categorie_source = TRIM(categorie_source)
    WHERE batch_id = p_batch_id;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N1: Trim espaces'::VARCHAR, v_count;

    -- N2: Majuscules pour catégorie source
    UPDATE staging.stg_facture_ligne
    SET categorie_source = UPPER(categorie_source)
    WHERE batch_id = p_batch_id
      AND categorie_source IS NOT NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N2: Majuscules catégorie'::VARCHAR, v_count;

    -- N3: Normalisation fournisseur
    UPDATE staging.stg_facture_ligne
    SET fournisseur_nom = 'METRO France'
    WHERE batch_id = p_batch_id
      AND UPPER(fournisseur_nom) LIKE '%METRO%';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N3: Normalisation fournisseur'::VARCHAR, v_count;

    -- N4: Déduction régie depuis catégorie si manquante
    UPDATE staging.stg_facture_ligne s
    SET regie = CASE UPPER(categorie_source)
        WHEN 'SPIRITUEUX' THEN 'S'
        WHEN 'BRASSERIE' THEN 'B'
        WHEN 'BIERE' THEN 'B'
        WHEN 'CAVE' THEN 'T'
        WHEN 'CHAMPAGNE' THEN 'M'
        WHEN 'CHAMPAGNES' THEN 'M'
        WHEN 'EPICERIE SECHE' THEN 'E'
        WHEN 'SURGELES' THEN 'F'
        WHEN 'DROGUERIE' THEN 'D'
        ELSE NULL
    END
    WHERE batch_id = p_batch_id
      AND regie IS NULL
      AND categorie_source IS NOT NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N4: Déduction régie'::VARCHAR, v_count;

    -- N5: Enrichissement taux TVA depuis code
    UPDATE staging.stg_facture_ligne s
    SET taux_tva = m.taux
    FROM staging.mapping_code_tva m
    WHERE s.batch_id = p_batch_id
      AND s.taux_tva IS NULL
      AND s.code_tva IS NOT NULL
      AND m.code_tva = s.code_tva;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N5: Enrichissement TVA'::VARCHAR, v_count;

    -- N6: Calcul montant ligne si manquant
    UPDATE staging.stg_facture_ligne
    SET montant_ligne = prix_unitaire * quantite
    WHERE batch_id = p_batch_id
      AND montant_ligne IS NULL
      AND prix_unitaire IS NOT NULL
      AND quantite IS NOT NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'N6: Calcul montant'::VARCHAR, v_count;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: staging.enrichir_colonnes_manquantes
-- Description: Enrichit les colonnes via lookup
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.enrichir_colonnes_manquantes(p_batch_id UUID)
RETURNS TABLE(colonne TEXT, nb_enrichis INT) AS $$
DECLARE
    v_count INT;
BEGIN
    -- Enrichir code TVA par défaut selon régie
    UPDATE staging.stg_facture_ligne s
    SET
        code_tva = COALESCE(code_tva, 'D'),
        taux_tva = COALESCE(taux_tva, m.taux_tva_defaut)
    FROM staging.mapping_regie_categorie m
    WHERE s.batch_id = p_batch_id
      AND s.regie = m.regie
      AND (s.code_tva IS NULL OR s.taux_tva IS NULL);

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'taux_tva (via régie)'::TEXT, v_count;

    -- Enrichir SIRET fournisseur
    UPDATE staging.stg_facture_ligne
    SET fournisseur_siret = '399315613'
    WHERE batch_id = p_batch_id
      AND fournisseur_siret IS NULL
      AND fournisseur_nom = 'METRO France';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'fournisseur_siret'::TEXT, v_count;

    -- Enrichir volume depuis désignation (pattern XXcl)
    UPDATE staging.stg_facture_ligne
    SET
        poids_volume = (REGEXP_MATCH(UPPER(designation), '(\d+)CL'))[1]::NUMERIC / 100,
        unite = 'L'
    WHERE batch_id = p_batch_id
      AND poids_volume IS NULL
      AND designation ~ '\d+CL';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'poids_volume (via designation)'::TEXT, v_count;

    -- Enrichir degré alcool depuis désignation (pattern XXD)
    UPDATE staging.stg_facture_ligne
    SET vol_alcool = (REGEXP_MATCH(UPPER(designation), '(\d+[,.]?\d*)D'))[1]::NUMERIC
    WHERE batch_id = p_batch_id
      AND vol_alcool IS NULL
      AND designation ~ '\d+D';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN QUERY SELECT 'vol_alcool (via designation)'::TEXT, v_count;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: staging.generer_entetes_factures
-- Description: Agrège les lignes en en-têtes de factures
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.generer_entetes_factures(p_batch_id UUID)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    -- Supprimer les anciennes entrées du batch
    DELETE FROM staging.stg_facture_entete WHERE batch_id = p_batch_id;

    -- Générer les en-têtes depuis les lignes
    INSERT INTO staging.stg_facture_entete (
        batch_id,
        source_file,
        numero_facture,
        numero_interne,
        date_facture,
        fournisseur_nom,
        fournisseur_siret,
        magasin_nom,
        client_nom,
        client_numero,
        total_ht_calcule,
        total_tva_calcule,
        total_ttc_calcule,
        nb_lignes,
        extraction_status
    )
    SELECT
        batch_id,
        MIN(source_file),
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
        COUNT(*),
        CASE
            WHEN COUNT(*) FILTER (WHERE extraction_status = 'ERREUR') > 0 THEN 'ERREUR'
            WHEN COUNT(*) FILTER (WHERE extraction_status = 'BRUT') > 0 THEN 'BRUT'
            ELSE 'VALIDE'
        END
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id
      AND numero_facture IS NOT NULL
    GROUP BY batch_id, numero_facture;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- -----------------------------------------------------------------------------
-- Fonction: staging.rapport_validation
-- Description: Génère un rapport de validation du batch
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.rapport_validation(p_batch_id UUID)
RETURNS TABLE(
    metrique VARCHAR,
    valeur TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'Batch ID'::VARCHAR, p_batch_id::TEXT;

    RETURN QUERY
    SELECT 'Date extraction'::VARCHAR,
           MIN(extraction_date)::TEXT
    FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id;

    RETURN QUERY
    SELECT 'Nb fichiers'::VARCHAR,
           COUNT(DISTINCT source_file)::TEXT
    FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id;

    RETURN QUERY
    SELECT 'Nb factures'::VARCHAR,
           COUNT(DISTINCT numero_facture)::TEXT
    FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id;

    RETURN QUERY
    SELECT 'Nb lignes total'::VARCHAR,
           COUNT(*)::TEXT
    FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id;

    RETURN QUERY
    SELECT 'Lignes VALIDE'::VARCHAR,
           COUNT(*)::TEXT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND extraction_status = 'VALIDE';

    RETURN QUERY
    SELECT 'Lignes ERREUR'::VARCHAR,
           COUNT(*)::TEXT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND extraction_status = 'ERREUR';

    RETURN QUERY
    SELECT 'Taux validation'::VARCHAR,
           ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'VALIDE') / NULLIF(COUNT(*), 0), 1)::TEXT || '%'
    FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id;

    RETURN QUERY
    SELECT 'Montant HT total'::VARCHAR,
           TO_CHAR(SUM(montant_ligne), 'FM999G999G999D00 €')
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND extraction_status = 'VALIDE';

    -- Top 5 erreurs
    RETURN QUERY
    SELECT 'Top erreurs'::VARCHAR,
           jsonb_array_elements_text(validation_errors)::TEXT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id
      AND extraction_status = 'ERREUR'
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;


COMMENT ON FUNCTION staging.valider_facture_lignes IS 'Valide les lignes staging selon règles V1-V10';
COMMENT ON FUNCTION staging.nettoyer_facture_lignes IS 'Applique nettoyage N1-N6 sur lignes staging';
COMMENT ON FUNCTION staging.enrichir_colonnes_manquantes IS 'Enrichit colonnes via lookup et déduction';
