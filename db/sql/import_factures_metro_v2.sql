-- ============================================================================
-- IMPORT FACTURES METRO V2
-- Import par position séquentielle - Aucun produit oublié
-- Normalisation: FOURNISSEUR-XXXX (ex: METRO-299013)
-- ============================================================================

-- Nettoyage préalable
TRUNCATE staging.stg_facture_ligne CASCADE;
TRUNCATE staging.stg_facture_entete CASCADE;
TRUNCATE ods.ods_facture_ligne CASCADE;
TRUNCATE ods.ods_facture_entete CASCADE;
TRUNCATE dwh.fait_achats CASCADE;
TRUNCATE etl.audit_execution CASCADE;

-- ============================================================================
-- MODIFICATION: Ajouter colonne numero_lot pour traçabilité
-- ============================================================================
ALTER TABLE staging.stg_facture_ligne ADD COLUMN IF NOT EXISTS numero_lot VARCHAR(50);
ALTER TABLE staging.stg_facture_ligne ADD COLUMN IF NOT EXISTS dlc DATE;
ALTER TABLE ods.ods_facture_ligne ADD COLUMN IF NOT EXISTS numero_lot VARCHAR(50);
ALTER TABLE ods.ods_facture_ligne ADD COLUMN IF NOT EXISTS dlc DATE;

-- ============================================================================
-- FACTURE 1: METRO-299013
-- Source: 135_11_299013_20240607174327_invoice_cus_copy_main.pdf
-- Total PDF: HT 1369.00€ | TVA 269.80€ | TTC 1638.80€
-- Nombre de lignes PDF: 3
-- ============================================================================

DO $$
DECLARE
    v_batch_1 UUID;
    v_batch_2 UUID;
BEGIN
    RAISE NOTICE '══════════════════════════════════════════════════════════════';
    RAISE NOTICE 'IMPORT FACTURES METRO - VERSION 2 (Par position)';
    RAISE NOTICE '══════════════════════════════════════════════════════════════';

    -- =========================================================================
    -- FACTURE METRO-299013
    -- =========================================================================
    RAISE NOTICE '';
    RAISE NOTICE '┌─ FACTURE METRO-299013 ────────────────────────────────────────┐';

    v_batch_1 := etl.importer_facture_metro(
        p_numero_facture := '0/0(135)0011/021322',
        p_numero_interne := 'METRO-299013',  -- Format normalisé
        p_date_facture := '2024-06-07',
        p_fournisseur := 'METRO France',
        p_magasin := 'METRO LA CHAPELLE',
        p_client := 'NOUTAM',
        p_client_numero := '135 00712188',
        p_total_ht := 1369.00,
        p_total_tva := 269.80,
        p_total_ttc := 1638.80,
        p_source_file := '135_11_299013_20240607174327_invoice_cus_copy_main.pdf'
    );

    -- Position 1: HEINEKEN 5D 65CL VP (BRASSERIE)
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1, p_ligne_numero := 1,
        p_ean := '3119783018823', p_article_numero := '2032837',
        p_designation := 'HEINEKEN 5D 65CL VP',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.0, p_poids_volume := 0.650,
        p_prix_unitaire := 1.404, p_colisage := 12, p_quantite := 80,
        p_montant := 1348.00, p_code_tva := 'D', p_est_promo := TRUE
    );

    -- Position 2: LIVRAISON AC STANDARD (Articles divers)
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1, p_ligne_numero := 2,
        p_ean := '21154263', p_article_numero := '1154269',
        p_designation := 'LIVRAISON AC STANDARD / ZONE HALLES',
        p_categorie := 'Articles divers', p_regie := 'C',
        p_vol_alcool := NULL, p_poids_volume := NULL,
        p_prix_unitaire := 1.00, p_colisage := 1, p_quantite := 1,
        p_montant := 1.00, p_code_tva := 'C', p_est_promo := TRUE
    );

    -- Position 3: PALETTE EUROPE (Articles divers - consigne)
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1, p_ligne_numero := 3,
        p_ean := '20297794', p_article_numero := '0297796',
        p_designation := 'PALETTE EUROPE',
        p_categorie := 'Articles divers', p_regie := 'A',
        p_vol_alcool := NULL, p_poids_volume := NULL,
        p_prix_unitaire := 20.00, p_colisage := 1, p_quantite := 1,
        p_montant := 20.00, p_code_tva := 'A', p_est_promo := FALSE
    );

    RAISE NOTICE '  → 3 lignes importées pour METRO-299013';
    RAISE NOTICE '  → Batch: %', v_batch_1;

    -- =========================================================================
    -- FACTURE METRO-299014
    -- =========================================================================
    RAISE NOTICE '';
    RAISE NOTICE '┌─ FACTURE METRO-299014 ────────────────────────────────────────┐';
    RAISE NOTICE '  Import de TOUTES les lignes par position séquentielle...';

    v_batch_2 := etl.importer_facture_metro(
        p_numero_facture := '0/0(135)0011/021323',
        p_numero_interne := 'METRO-299014',  -- Format normalisé
        p_date_facture := '2024-06-07',
        p_fournisseur := 'METRO France',
        p_magasin := 'METRO LA CHAPELLE',
        p_client := 'NOUTAM',
        p_client_numero := '135 00712188',
        p_total_ht := 1973.29,
        p_total_tva := 352.05,
        p_total_ttc := 2325.34,
        p_source_file := '135_11_299014_20240607174636_invoice_cus_copy_main.pdf'
    );

    -- =========================================================================
    -- PAGE 1 - SPIRITUEUX (Total PDF: 792.47€ dont 39.48€ cotis SS)
    -- =========================================================================

    -- Pos 1: WH JACK DANIEL'S 40D 35CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 1,
        '5099873089057', '0248567', 'WH JACK DANIEL''S 40D 35CL',
        'SPIRITUEUX', 'S', 40.0, 0.350, 9.340, 1, 2, 18.68, 'D', TRUE, 1.68);

    -- Pos 2: WH GLENFIDDICH 15A 40D 70CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 2,
        '5010327325125', '0799775', 'WH GLENFIDDICH 15A 40D 70CL',
        'SPIRITUEUX', 'S', 40.0, 0.700, 41.940, 1, 15, 629.10, 'D', FALSE, 25.20);

    -- Pos 3: VODKA POLIAKOV 37.5D 35CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 3,
        '3147699102671', '0446583', 'VODKA POLIAKOV 37.5D 35CL',
        'SPIRITUEUX', 'S', 37.5, 0.350, 5.480, 1, 2, 10.96, 'D', FALSE, 1.58);

    -- Pos 4: VODKA POLIAKOV 37,5D 20CL X6
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 4,
        '3147697510607', '1925387', 'VODKA POLIAKOV 37,5D 20CL X6',
        'SPIRITUEUX', 'S', 37.5, 0.200, 2.835, 6, 3, 51.03, 'D', FALSE, 8.10);

    -- Pos 5: JACK DANIEL'S HONEY 35D 35CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 5,
        '5099873060704', '2117539', 'JACK DANIEL''S HONEY 35D 35CL',
        'SPIRITUEUX', 'S', 35.0, 0.350, 10.730, 1, 2, 21.46, 'D', FALSE, 1.46);

    -- Pos 6: JACK DANIEL'S FIRE 35D 35CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 6,
        '5099873008270', '2670578', 'JACK DANIEL''S FIRE 35D 35CL',
        'SPIRITUEUX', 'S', 35.0, 0.350, 10.880, 1, 2, 21.76, 'D', FALSE, 1.46);

    -- =========================================================================
    -- PAGE 1 - CAVE (Total PDF: 385.02€ - remise 24.95€)
    -- =========================================================================

    -- Pos 7: MEDOC 75CL MIL CH ARCINS CB (avec remise -24.95€)
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 7,
        '3211200184743', '2128882', 'MEDOC 75CL MIL CH ARCINS CB',
        'CAVE', 'T', NULL, 0.750, 10.390, 6, 5, 311.70, 'D', FALSE, NULL);

    -- Pos 8: PAYS OC CABERN SAUV 25CL MAZET
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 8,
        '3175529657725', '2158459', 'PAYS OC CABERN SAUV 25CL MAZET',
        'CAVE', 'T', NULL, 0.250, 1.470, 12, 1, 17.64, 'D', FALSE, NULL);

    -- Pos 9: IGP MED RGE C. DAUPHINS 25CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 9,
        '03179077103147', '2258655', 'IGP MED RGE C. DAUPHINS 25CL',
        'CAVE', 'T', NULL, 0.250, 1.160, 12, 4, 55.68, 'D', TRUE, NULL);

    -- =========================================================================
    -- PAGE 1 - CHAMPAGNES (Total PDF: 221.94€)
    -- =========================================================================

    -- Pos 10: CH V. CLICQUOT BRUT 75CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 10,
        '3049614222252', '1933340', 'CH V. CLICQUOT BRUT 75CL',
        'CHAMPAGNES', 'M', NULL, 0.750, 36.990, 6, 1, 221.94, 'D', FALSE, NULL);

    -- =========================================================================
    -- PAGE 2 - BRASSERIE ALCOOL (Bières)
    -- =========================================================================

    -- Pos 11: LEFFE BLONDE 6.6 BLE 33CL (avec remise -2.85€)
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 11,
        '5410228203582', '2025492', 'LEFFE BLONDE 6.6 BLE 33CL',
        'BRASSERIE', 'B', 6.6, 0.330, 0.950, 12, 5, 57.00, 'D', FALSE, NULL);

    -- Pos 12: LEFFE BLONDE 75CL 6.6D VP
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 12,
        '5410228223580', '2125177', 'LEFFE BLONDE 75CL 6.6D VP',
        'BRASSERIE', 'B', 6.6, 0.750, 2.540, 6, 3, 45.72, 'D', FALSE, NULL);

    -- Pos 13: SUPER BOCK 5.2 25CLX24 VRAC
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 13,
        '5601164900349', '1752823', 'SUPER BOCK 5.2 25CLX24 VRAC',
        'BRASSERIE', 'B', 5.2, 0.250, 0.522, 24, 2, 25.06, 'D', TRUE, NULL);

    -- Pos 14-16: HEINEKEN 5D 6X25CL VP (3 lignes avec traçabilité lot A40513505)
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 14,
        '03119783018243', '2023968', 'HEINEKEN 5D 6X25CL VP',
        'BRASSERIE', 'B', 5.0, 0.250, 0.643, 24, 1, 15.42, 'D', FALSE, NULL);
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 15,
        '03119783018243', '2023968', 'HEINEKEN 5D 6X25CL VP',
        'BRASSERIE', 'B', 5.0, 0.250, 0.643, 24, 1, 15.42, 'D', FALSE, NULL);
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 16,
        '03119783018243', '2023968', 'HEINEKEN 5D 6X25CL VP',
        'BRASSERIE', 'B', 5.0, 0.250, 0.643, 24, 1, 15.42, 'D', FALSE, NULL);

    -- Pos 17-18: 1664 BOITE 5.5D 50CL (2 lignes avec traçabilité lot FR01Q40119)
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 17,
        '03080213000759', '2025435', '1664 BOITE 5.5D 50CL',
        'BRASSERIE', 'B', 5.5, 0.500, 1.040, 24, 1, 24.96, 'D', TRUE, NULL);
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 18,
        '03080213000759', '2025435', '1664 BOITE 5.5D 50CL',
        'BRASSERIE', 'B', 5.5, 0.500, 1.040, 24, 1, 24.96, 'D', TRUE, NULL);

    -- Pos 19: 1664 5.5D 75CL VP
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 19,
        '3080210003425', '2032902', '1664 5.5D 75CL VP',
        'BRASSERIE', 'B', 5.5, 0.750, 1.692, 6, 3, 30.45, 'D', FALSE, NULL);

    -- Pos 20: 1664 BLDE 5.5D 18X25CL VP
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 20,
        '3080216061306', '3053485', '1664 BLDE 5.5D 18X25CL VP',
        'BRASSERIE', 'B', 5.5, 0.250, 0.551, 18, 3, 29.73, 'D', FALSE, NULL);

    -- =========================================================================
    -- PAGE 3 - BRASSERIE SOFT (Boissons non alcoolisées) - TVA 5.5%
    -- =========================================================================

    -- Pos 21: POWERADE ICE STORM 50CL PET
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 21,
        '5449000085276', '2032290', 'POWERADE ICE STORM 50CL PET',
        'BRASSERIE', NULL, NULL, 0.500, 1.040, 12, 1, 12.48, 'B', FALSE, NULL);

    -- Pos 22: HAWAI TROPICAL BOITE 33CL *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 22,
        '5449000224606', '2022549', 'HAWAI TROPICAL BOITE 33CL',
        'BRASSERIE', NULL, NULL, 0.330, 0.660, 24, 1, 15.84, 'B', FALSE, NULL);

    -- Pos 23: ORANGINA SLIM BOITE JAUN 33CL *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 23,
        '3124488184322', '2028181', 'ORANGINA SLIM BOITE JAUN 33CL',
        'BRASSERIE', NULL, NULL, 0.330, 0.515, 24, 1, 12.36, 'B', FALSE, NULL);

    -- Pos 24: COCA COLA PET 50CL
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 24,
        '5449000017673', '2033348', 'COCA COLA PET 50CL',
        'BRASSERIE', NULL, NULL, 0.500, 0.895, 24, 2, 42.96, 'B', FALSE, NULL);

    -- Pos 25: FANTA ORGE SLIM 33CL X24 PROMO *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 25,
        '5000112618303', '2516144', 'FANTA ORGE SLIM 33CL X24 PROMO',
        'BRASSERIE', NULL, NULL, 0.330, 0.450, 24, 1, 10.80, 'B', TRUE, NULL);

    -- Pos 26: ORANGINA 50CL PET (avec traçabilité lot 24050) *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 26,
        '03124488194659', '2786697', 'ORANGINA 50CL PET',
        'BRASSERIE', NULL, NULL, 0.500, 0.917, 12, 1, 11.00, 'B', FALSE, NULL);

    -- Pos 27: SCHWEPPES IT PET 4X50CL *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 27,
        '3124488151492', '2815256', 'SCHWEPPES IT PET 4X50CL',
        'BRASSERIE', NULL, NULL, 2.000, 0.996, 24, 2, 47.80, 'B', FALSE, NULL);

    -- Pos 28: ROCHE DES ECRINS PET 50CL *** MANQUANT V1 ***
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 28,
        '3439497020357', '2021418', 'ROCHE DES ECRINS PET 50CL',
        'BRASSERIE', NULL, NULL, 0.500, 0.193, 24, 2, 9.26, 'B', FALSE, NULL);

    -- =========================================================================
    -- PAGE 3 - EPICERIE SECHE (Total PDF: 91.07€)
    -- =========================================================================

    -- Pos 29: ARO TOMATE CONCASSEE 1/2
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 29,
        '03439495112115', '1920776', 'ARO TOMATE CONCASSEE 1/2',
        'EPICERIE SECHE', 'E', NULL, NULL, 0.757, 6, 1, 4.54, 'B', FALSE, NULL);

    -- Pos 30: ARO TOMATE CONCASSEE 4/4
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 30,
        '03439495010985', '2420347', 'ARO TOMATE CONCASSEE 4/4',
        'EPICERIE SECHE', 'E', NULL, NULL, 1.370, 6, 1, 8.22, 'B', FALSE, NULL);

    -- Pos 31: MAUREL HLE TOURNESOL 25L
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 31,
        '3075711382018', '0111633', 'MAUREL HLE TOURNESOL 25L',
        'EPICERIE SECHE', 'E', NULL, 25.000, 1.622, 25, 1, 40.55, 'B', FALSE, NULL);

    -- Pos 32: VINAIGRE BLANC 8° - 1 L ARO
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 32,
        '13439495113492', '3046554', 'VINAIGRE BLANC 8° - 1 L ARO',
        'EPICERIE SECHE', 'E', NULL, 1.000, 0.451, 12, 1, 5.41, 'B', FALSE, NULL);

    -- Pos 33: ARO SEL FIN BV 750G
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 33,
        '03439495112917', '2422111', 'ARO SEL FIN BV 750G',
        'EPICERIE SECHE', 'E', NULL, 0.750, 0.501, 15, 1, 7.51, 'B', FALSE, NULL);

    -- Pos 34: AIL EN POUDRE SAC 500G
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 34,
        '3295921144200', '2582138', 'AIL EN POUDRE SAC 500G',
        'EPICERIE SECHE', 'E', NULL, 0.500, 4.750, 1, 1, 4.75, 'B', FALSE, NULL);

    -- Pos 35: ARO MAYO ALLEGEE ARO SEAU 5L
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 35,
        '3439495111699', '0468553', 'ARO MAYO ALLEGEE ARO SEAU 5L',
        'EPICERIE SECHE', 'E', NULL, 5.000, 9.890, 1, 1, 9.89, 'B', FALSE, NULL);

    -- Pos 36: MC MOUTARDE DIJON 5KG
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 36,
        '3439495102796', '2419638', 'MC MOUTARDE DIJON 5KG',
        'EPICERIE SECHE', 'E', NULL, 5.000, 2.040, 5, 1, 10.20, 'B', FALSE, NULL);

    -- =========================================================================
    -- PAGE 3 - SURGELES (Total PDF: 40.26€)
    -- =========================================================================

    -- Pos 37: EPINARD BRANCHE PALET 2.5KG MC
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 37,
        '4337182138082', '1665405', 'EPINARD BRANCHE PALET 2.5KG MC',
        'SURGELES', 'G', NULL, 2.500, 5.033, 4, 2, 40.26, 'B', FALSE, NULL);

    -- =========================================================================
    -- PAGE 3 - DROGUERIE (Total PDF: 23.66€)
    -- =========================================================================

    -- Pos 38: ARO LIQ VAISS MAIN CIT 20L
    PERFORM etl.ajouter_ligne_facture(v_batch_2, 38,
        '3439496810997', '2445781', 'ARO LIQ VAISS MAIN CIT 20L',
        'DROGUERIE', 'H', NULL, 20.000, 23.660, 1, 1, 23.66, 'D', FALSE, NULL);

    RAISE NOTICE '  → 38 lignes importées pour METRO-299014';
    RAISE NOTICE '  → Batch: %', v_batch_2;
    RAISE NOTICE '';
    RAISE NOTICE '══════════════════════════════════════════════════════════════';
    RAISE NOTICE 'IMPORT TERMINÉ - 41 lignes totales (3 + 38)';
    RAISE NOTICE '══════════════════════════════════════════════════════════════';
END;
$$;

-- ============================================================================
-- VÉRIFICATION IMPORT STAGING
-- ============================================================================

SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";
SELECT '                    VÉRIFICATION DONNÉES STAGING                              ' AS " ";
SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";

SELECT * FROM etl.v_batch_status ORDER BY numero_interne;

-- ============================================================================
-- EXÉCUTION PIPELINE ETL
-- ============================================================================

SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";
SELECT '                    EXÉCUTION PIPELINE ETL                                     ' AS " ";
SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";

-- Pipeline facture 1
SELECT '┌─ Pipeline METRO-299013 ─────────────────────────────────────────────────────┐' AS " ";
SELECT * FROM etl.run_pipeline_factures();

-- Pipeline facture 2
SELECT '┌─ Pipeline METRO-299014 ─────────────────────────────────────────────────────┐' AS " ";
SELECT * FROM etl.run_pipeline_factures();

-- ============================================================================
-- RÉCONCILIATION
-- ============================================================================

SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";
SELECT '                         RÉCONCILIATION                                        ' AS " ";
SELECT '═══════════════════════════════════════════════════════════════════════════════' AS " ";

-- Totaux par facture
SELECT
    e.numero_interne AS "Facture",
    e.nombre_lignes AS "Lignes",
    e.total_ht AS "PDF HT",
    ROUND(SUM(l.montant_ht)::NUMERIC, 2) AS "Calc HT",
    e.total_ht - ROUND(SUM(l.montant_ht)::NUMERIC, 2) AS "Écart HT",
    ROUND(SUM(l.cotis_secu)::NUMERIC, 2) AS "Cotis SS"
FROM ods.ods_facture_entete e
JOIN ods.ods_facture_ligne l ON l.facture_id = e.facture_id
GROUP BY e.numero_interne, e.nombre_lignes, e.total_ht
ORDER BY e.numero_interne;

-- Totaux par catégorie facture 299014
SELECT '┌─ Totaux par catégorie METRO-299014 ─────────────────────────────────────────┐' AS " ";

SELECT
    l.categorie_source AS "Catégorie",
    COUNT(*) AS "Lignes",
    ROUND(SUM(l.montant_ht)::NUMERIC, 2) AS "Total HT",
    ROUND(SUM(l.cotis_secu)::NUMERIC, 2) AS "Cotis SS",
    ROUND(SUM(l.montant_ht) + COALESCE(SUM(l.cotis_secu), 0), 2) AS "HT + CSS"
FROM ods.ods_facture_ligne l
JOIN ods.ods_facture_entete e ON e.facture_id = l.facture_id
WHERE e.numero_interne = 'METRO-299014'
GROUP BY l.categorie_source
ORDER BY SUM(l.montant_ht) DESC;

-- Total général
SELECT '┌─ Total général ────────────────────────────────────────────────────────────────┐' AS " ";

SELECT
    'METRO-299014' AS "Facture",
    'PDF' AS "Source",
    1973.29 AS "Total HT",
    NULL AS "Cotis SS",
    NULL AS "HT + CSS"
UNION ALL
SELECT
    'METRO-299014',
    'Import',
    ROUND(SUM(montant_ht)::NUMERIC, 2),
    ROUND(SUM(cotis_secu)::NUMERIC, 2),
    ROUND(SUM(montant_ht) + COALESCE(SUM(cotis_secu), 0), 2)
FROM ods.ods_facture_ligne l
JOIN ods.ods_facture_entete e ON e.facture_id = l.facture_id
WHERE e.numero_interne = 'METRO-299014';
