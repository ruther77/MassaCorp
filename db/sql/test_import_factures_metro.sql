-- ============================================================================
-- TEST IMPORT FACTURES METRO
-- Import des factures 011-299013 et 011-299014 du 07-06-2024
-- ============================================================================

-- ============================================================================
-- FACTURE 1 : 011-299013 (Heineken + Livraison + Palette)
-- Total HT: 1369.00€ | TVA: 269.80€ | TTC: 1638.80€
-- ============================================================================

DO $$
DECLARE
    v_batch_1 UUID;
    v_batch_2 UUID;
BEGIN
    RAISE NOTICE '=== IMPORT FACTURES METRO ===';

    -- -------------------------------------------------------------------------
    -- FACTURE 011-299013
    -- -------------------------------------------------------------------------
    RAISE NOTICE 'Import facture 011-299013...';

    v_batch_1 := etl.importer_facture_metro(
        p_numero_facture := '0/0(135)0011/021322',
        p_numero_interne := '011-299013',
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

    -- Ligne 1: HEINEKEN 5D 65CL VP
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1,
        p_ligne_numero := 1,
        p_ean := '3119783018823',
        p_article_numero := '2032837',
        p_designation := 'HEINEKEN 5D 65CL VP',
        p_categorie := 'BRASSERIE',
        p_regie := 'B',
        p_vol_alcool := 5.0,
        p_poids_volume := 0.650,
        p_prix_unitaire := 1.404,
        p_colisage := 12,
        p_quantite := 80,
        p_montant := 1348.00,
        p_code_tva := 'D',
        p_est_promo := TRUE,
        p_cotis_secu := NULL
    );

    -- Ligne 2: LIVRAISON AC STANDARD
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1,
        p_ligne_numero := 2,
        p_ean := '21154263',
        p_article_numero := '1154269',
        p_designation := 'LIVRAISON AC STANDARD / ZONE HALLES',
        p_categorie := 'Articles divers',
        p_regie := 'C',
        p_vol_alcool := NULL,
        p_poids_volume := NULL,
        p_prix_unitaire := 1.00,
        p_colisage := 1,
        p_quantite := 1,
        p_montant := 1.00,
        p_code_tva := 'C',
        p_est_promo := TRUE,
        p_cotis_secu := NULL
    );

    -- Ligne 3: PALETTE EUROPE
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_1,
        p_ligne_numero := 3,
        p_ean := '20297794',
        p_article_numero := '0297796',
        p_designation := 'PALETTE EUROPE',
        p_categorie := 'Articles divers',
        p_regie := 'A',
        p_vol_alcool := NULL,
        p_poids_volume := NULL,
        p_prix_unitaire := 20.00,
        p_colisage := 1,
        p_quantite := 1,
        p_montant := 20.00,
        p_code_tva := 'A',
        p_est_promo := FALSE,
        p_cotis_secu := NULL
    );

    RAISE NOTICE 'Facture 011-299013 importée (batch: %)', v_batch_1;

    -- -------------------------------------------------------------------------
    -- FACTURE 011-299014
    -- -------------------------------------------------------------------------
    RAISE NOTICE 'Import facture 011-299014...';

    v_batch_2 := etl.importer_facture_metro(
        p_numero_facture := '0/0(135)0011/021323',
        p_numero_interne := '011-299014',
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

    -- ===== SPIRITUEUX =====

    -- Jack Daniel's 40D 35CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 1,
        p_ean := '5099873089057', p_article_numero := '0248567',
        p_designation := 'WH JACK DANIEL''S 40D 35CL',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 40.0, p_poids_volume := 0.350,
        p_prix_unitaire := 9.340, p_colisage := 1, p_quantite := 2,
        p_montant := 18.68, p_code_tva := 'D', p_est_promo := TRUE, p_cotis_secu := 1.68
    );

    -- Glenfiddich 15A 40D 70CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 2,
        p_ean := '5010327325125', p_article_numero := '0799775',
        p_designation := 'WH GLENFIDDICH 15A 40D 70CL',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 40.0, p_poids_volume := 0.700,
        p_prix_unitaire := 41.940, p_colisage := 1, p_quantite := 15,
        p_montant := 629.10, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := 25.20
    );

    -- Vodka Poliakov 37.5D 35CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 3,
        p_ean := '3147699102671', p_article_numero := '0446583',
        p_designation := 'VODKA POLIAKOV 37.5D 35CL',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 37.5, p_poids_volume := 0.350,
        p_prix_unitaire := 5.480, p_colisage := 1, p_quantite := 2,
        p_montant := 10.96, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := 1.58
    );

    -- Vodka Poliakov 37.5D 20CL X6
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 4,
        p_ean := '3147697510607', p_article_numero := '1925387',
        p_designation := 'VODKA POLIAKOV 37,5D 20CL X6',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 37.5, p_poids_volume := 0.200,
        p_prix_unitaire := 2.835, p_colisage := 6, p_quantite := 3,
        p_montant := 51.03, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := 8.10
    );

    -- Jack Daniel's Honey 35D 35CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 5,
        p_ean := '5099873060704', p_article_numero := '2117539',
        p_designation := 'JACK DANIEL''S HONEY 35D 35CL',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 35.0, p_poids_volume := 0.350,
        p_prix_unitaire := 10.730, p_colisage := 1, p_quantite := 2,
        p_montant := 21.46, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := 1.46
    );

    -- Jack Daniel's Fire 35D 35CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 6,
        p_ean := '5099873008270', p_article_numero := '2670578',
        p_designation := 'JACK DANIEL''S FIRE 35D 35CL',
        p_categorie := 'SPIRITUEUX', p_regie := 'S',
        p_vol_alcool := 35.0, p_poids_volume := 0.350,
        p_prix_unitaire := 10.880, p_colisage := 1, p_quantite := 2,
        p_montant := 21.76, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := 1.46
    );

    -- ===== CAVE (VINS) =====

    -- Médoc 75CL CH ARCINS CB
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 7,
        p_ean := '3211200184743', p_article_numero := '2128882',
        p_designation := 'MEDOC 75CL MIL CH ARCINS CB',
        p_categorie := 'CAVE', p_regie := 'T',
        p_vol_alcool := NULL, p_poids_volume := 0.750,
        p_prix_unitaire := 10.390, p_colisage := 6, p_quantite := 5,
        p_montant := 311.70, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Pays OC Cabernet Sauvignon 25CL Mazet
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 8,
        p_ean := '3175529657725', p_article_numero := '2158459',
        p_designation := 'PAYS OC CABERN SAUV 25CL MAZET',
        p_categorie := 'CAVE', p_regie := 'T',
        p_vol_alcool := NULL, p_poids_volume := 0.250,
        p_prix_unitaire := 1.470, p_colisage := 12, p_quantite := 1,
        p_montant := 17.64, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- IGP MED RGE C. DAUPHINS 25CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 9,
        p_ean := '03179077103147', p_article_numero := '2258655',
        p_designation := 'IGP MED RGE C. DAUPHINS 25CL',
        p_categorie := 'CAVE', p_regie := 'T',
        p_vol_alcool := NULL, p_poids_volume := 0.250,
        p_prix_unitaire := 1.160, p_colisage := 12, p_quantite := 4,
        p_montant := 55.68, p_code_tva := 'D', p_est_promo := TRUE, p_cotis_secu := NULL
    );

    -- ===== CHAMPAGNE =====

    -- Veuve Clicquot Brut 75CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 10,
        p_ean := '3049614222252', p_article_numero := '1933340',
        p_designation := 'CH V. CLICQUOT BRUT 75CL',
        p_categorie := 'CHAMPAGNES', p_regie := 'M',
        p_vol_alcool := NULL, p_poids_volume := 0.750,
        p_prix_unitaire := 36.990, p_colisage := 6, p_quantite := 1,
        p_montant := 221.94, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ===== BRASSERIE =====

    -- Leffe Blonde 6.6 33CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 11,
        p_ean := '5410228203582', p_article_numero := '2025492',
        p_designation := 'LEFFE BLONDE 6.6 BLE 33CL',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 6.6, p_poids_volume := 0.330,
        p_prix_unitaire := 0.950, p_colisage := 12, p_quantite := 5,
        p_montant := 57.00, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Leffe Blonde 75CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 12,
        p_ean := '5410228223580', p_article_numero := '2125177',
        p_designation := 'LEFFE BLONDE 75CL 6.6D VP',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 6.6, p_poids_volume := 0.750,
        p_prix_unitaire := 2.540, p_colisage := 6, p_quantite := 3,
        p_montant := 45.72, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Super Bock 5.2 25CLX24
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 13,
        p_ean := '5601164900349', p_article_numero := '1752823',
        p_designation := 'SUPER BOCK 5.2 25CLX24 VRAC',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.2, p_poids_volume := 0.250,
        p_prix_unitaire := 0.522, p_colisage := 24, p_quantite := 2,
        p_montant := 25.06, p_code_tva := 'D', p_est_promo := TRUE, p_cotis_secu := NULL
    );

    -- Heineken 5D 6X25CL (x3)
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 14,
        p_ean := '03119783018243', p_article_numero := '2023968',
        p_designation := 'HEINEKEN 5D 6X25CL VP',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.0, p_poids_volume := 0.250,
        p_prix_unitaire := 0.643, p_colisage := 24, p_quantite := 3,
        p_montant := 46.26, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- 1664 Boite 5.5D 50CL (x2)
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 15,
        p_ean := '03080213000759', p_article_numero := '2025435',
        p_designation := '1664 BOITE 5.5D 50CL',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.5, p_poids_volume := 0.500,
        p_prix_unitaire := 1.040, p_colisage := 24, p_quantite := 2,
        p_montant := 49.92, p_code_tva := 'D', p_est_promo := TRUE, p_cotis_secu := NULL
    );

    -- 1664 5.5D 75CL VP
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 16,
        p_ean := '3080210003425', p_article_numero := '2032902',
        p_designation := '1664 5.5D 75CL VP',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.5, p_poids_volume := 0.750,
        p_prix_unitaire := 1.692, p_colisage := 6, p_quantite := 3,
        p_montant := 30.45, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- 1664 BLDE 5.5D 18X25CL VP
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 17,
        p_ean := '3080216061306', p_article_numero := '3053485',
        p_designation := '1664 BLDE 5.5D 18X25CL VP',
        p_categorie := 'BRASSERIE', p_regie := 'B',
        p_vol_alcool := 5.5, p_poids_volume := 0.250,
        p_prix_unitaire := 0.551, p_colisage := 18, p_quantite := 3,
        p_montant := 29.73, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ===== BOISSONS NON ALCOOLISEES =====

    -- Powerade Ice Storm 50CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 18,
        p_ean := '5449000085276', p_article_numero := '2032290',
        p_designation := 'POWERADE ICE STORM 50CL PET',
        p_categorie := 'BRASSERIE', p_regie := NULL,
        p_vol_alcool := NULL, p_poids_volume := 0.500,
        p_prix_unitaire := 1.040, p_colisage := 12, p_quantite := 1,
        p_montant := 12.48, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Coca Cola PET 50CL
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 19,
        p_ean := '5449000017673', p_article_numero := '2033348',
        p_designation := 'COCA COLA PET 50CL',
        p_categorie := 'BRASSERIE', p_regie := NULL,
        p_vol_alcool := NULL, p_poids_volume := 0.500,
        p_prix_unitaire := 0.895, p_colisage := 24, p_quantite := 2,
        p_montant := 42.98, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ===== EPICERIE SECHE =====

    -- ARO Tomate Concassée 1/2
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 20,
        p_ean := '03439495112115', p_article_numero := '1920776',
        p_designation := 'ARO TOMATE CONCASSEE 1/2',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := NULL,
        p_prix_unitaire := 0.757, p_colisage := 6, p_quantite := 1,
        p_montant := 4.54, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ARO Tomate Concassée 4/4
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 21,
        p_ean := '03439495010985', p_article_numero := '2420347',
        p_designation := 'ARO TOMATE CONCASSEE 4/4',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := NULL,
        p_prix_unitaire := 1.370, p_colisage := 6, p_quantite := 1,
        p_montant := 8.22, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Huile Tournesol 25L
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 22,
        p_ean := '3075711382018', p_article_numero := '0111633',
        p_designation := 'MAUREL HLE TOURNESOL 25L',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 25.000,
        p_prix_unitaire := 1.622, p_colisage := 25, p_quantite := 1,
        p_montant := 40.55, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Vinaigre Blanc 8° 1L ARO
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 23,
        p_ean := '13439495113492', p_article_numero := '3046554',
        p_designation := 'VINAIGRE BLANC 8° - 1 L ARO',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 1.000,
        p_prix_unitaire := 0.451, p_colisage := 12, p_quantite := 1,
        p_montant := 5.41, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Sel fin ARO 750G
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 24,
        p_ean := '03439495112917', p_article_numero := '2422111',
        p_designation := 'ARO SEL FIN BV 750G',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 0.750,
        p_prix_unitaire := 0.501, p_colisage := 15, p_quantite := 1,
        p_montant := 7.51, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Ail en poudre 500G
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 25,
        p_ean := '3295921144200', p_article_numero := '2582138',
        p_designation := 'AIL EN POUDRE SAC 500G',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 0.500,
        p_prix_unitaire := 4.750, p_colisage := 1, p_quantite := 1,
        p_montant := 4.75, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Mayo allégée ARO 5L
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 26,
        p_ean := '3439495111699', p_article_numero := '0468553',
        p_designation := 'ARO MAYO ALLEGEE ARO SEAU 5L',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 5.000,
        p_prix_unitaire := 9.890, p_colisage := 1, p_quantite := 1,
        p_montant := 9.89, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- Moutarde Dijon 5KG
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 27,
        p_ean := '3439495102796', p_article_numero := '2419638',
        p_designation := 'MC MOUTARDE DIJON 5KG',
        p_categorie := 'EPICERIE SECHE', p_regie := 'E',
        p_vol_alcool := NULL, p_poids_volume := 5.000,
        p_prix_unitaire := 2.040, p_colisage := 5, p_quantite := 1,
        p_montant := 10.20, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ===== SURGELES =====

    -- Epinard Branche Palet 2.5KG
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 28,
        p_ean := '4337182138082', p_article_numero := '1665405',
        p_designation := 'EPINARD BRANCHE PALET 2.5KG MC',
        p_categorie := 'SURGELES', p_regie := 'G',
        p_vol_alcool := NULL, p_poids_volume := 2.500,
        p_prix_unitaire := 5.033, p_colisage := 4, p_quantite := 2,
        p_montant := 40.26, p_code_tva := 'B', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    -- ===== DROGUERIE =====

    -- Liquide vaisselle citron 20L
    PERFORM etl.ajouter_ligne_facture(
        p_batch_id := v_batch_2, p_ligne_numero := 29,
        p_ean := '3439496810997', p_article_numero := '2445781',
        p_designation := 'ARO LIQ VAISS MAIN CIT 20L',
        p_categorie := 'DROGUERIE', p_regie := 'H',
        p_vol_alcool := NULL, p_poids_volume := 20.000,
        p_prix_unitaire := 23.660, p_colisage := 1, p_quantite := 1,
        p_montant := 23.66, p_code_tva := 'D', p_est_promo := FALSE, p_cotis_secu := NULL
    );

    RAISE NOTICE 'Facture 011-299014 importée (batch: %)', v_batch_2;

    RAISE NOTICE '=== IMPORT TERMINE ===';
END;
$$;

-- ============================================================================
-- AFFICHAGE STATUS IMPORT
-- ============================================================================

SELECT '=== STATUT DES FACTURES IMPORTÉES ===' AS info;

SELECT * FROM etl.v_batch_status;

-- ============================================================================
-- EXÉCUTION DU PIPELINE ETL
-- ============================================================================

SELECT '=== EXÉCUTION PIPELINE ETL ===' AS info;

SELECT * FROM etl.run_pipeline_factures();

-- ============================================================================
-- VÉRIFICATION ODS
-- ============================================================================

SELECT '=== FACTURES DANS ODS ===' AS info;

SELECT * FROM ods.v_factures_recentes;

SELECT '=== DÉTAIL LIGNES FACTURE 011-299014 ===' AS info;

SELECT
    l.ligne_numero,
    l.designation,
    l.categorie_source,
    l.quantite,
    l.prix_unitaire,
    l.montant_ht,
    l.taux_tva,
    l.montant_ttc,
    l.est_alcool,
    l.vol_alcool
FROM ods.ods_facture_ligne l
JOIN ods.ods_facture_entete e ON e.facture_id = l.facture_id
WHERE e.numero_interne = '011-299014'
ORDER BY l.ligne_numero;

-- ============================================================================
-- STATISTIQUES
-- ============================================================================

SELECT '=== STATISTIQUES PAR CATEGORIE ===' AS info;

SELECT
    l.categorie_source,
    COUNT(*) AS nb_lignes,
    SUM(l.quantite) AS quantite_totale,
    ROUND(SUM(l.montant_ht)::NUMERIC, 2) AS total_ht,
    ROUND(SUM(l.montant_ttc)::NUMERIC, 2) AS total_ttc,
    SUM(CASE WHEN l.est_alcool THEN 1 ELSE 0 END) AS nb_alcools,
    ROUND(SUM(l.vap_total)::NUMERIC, 4) AS vap_total
FROM ods.ods_facture_ligne l
GROUP BY l.categorie_source
ORDER BY total_ht DESC;
