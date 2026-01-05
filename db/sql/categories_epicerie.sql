-- =============================================================================
-- CATÉGORISATION PRODUITS - NOUTAM SAS (Épicerie)
-- Structure hiérarchique : Famille > Catégorie > Sous-catégorie
-- =============================================================================

-- Supprimer et recréer pour avoir une base propre
DROP TABLE IF EXISTS dwh.dim_categorie_produit CASCADE;

-- =============================================================================
-- TABLE DES CATÉGORIES (structure hiérarchique)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dwh.dim_categorie_produit (
    categorie_id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    nom TEXT NOT NULL,
    famille VARCHAR(50) NOT NULL,
    categorie VARCHAR(50) NOT NULL,
    sous_categorie VARCHAR(50),
    -- TVA par défaut selon le type de produit
    tva_defaut NUMERIC(5,2) NOT NULL DEFAULT 20.00,
    -- Ordre d'affichage dans les rapports
    ordre_famille INT DEFAULT 99,
    ordre_categorie INT DEFAULT 99,
    -- Flag pour identifier les catégories utilisables comme ingrédients restaurant
    est_ingredient_resto BOOLEAN DEFAULT FALSE,
    priorite_ingredient INT DEFAULT 0,  -- 1=haute, 2=moyenne, 3=basse
    -- Métadonnées
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index pour les requêtes fréquentes
CREATE INDEX idx_cat_famille ON dwh.dim_categorie_produit(famille);
CREATE INDEX idx_cat_ingredient ON dwh.dim_categorie_produit(est_ingredient_resto) WHERE est_ingredient_resto = TRUE;

-- =============================================================================
-- INSERTION DES 50 CATÉGORIES
-- =============================================================================

INSERT INTO dwh.dim_categorie_produit 
    (code, nom, famille, categorie, sous_categorie, tva_defaut, ordre_famille, ordre_categorie, est_ingredient_resto, priorite_ingredient)
VALUES
-- ═══════════════════════════════════════════════════════════════════════════
-- 1. BOISSONS SANS ALCOOL (TVA 5.5% alimentaire, 20% si sucré)
-- ═══════════════════════════════════════════════════════════════════════════
('BOIS_EAU', 'Eaux', 'Boissons', 'Sans Alcool', 'Eaux', 5.50, 1, 1, TRUE, 3),
('BOIS_SODA', 'Sodas', 'Boissons', 'Sans Alcool', 'Sodas', 5.50, 1, 2, TRUE, 3),
('BOIS_JUS', 'Jus de fruits', 'Boissons', 'Sans Alcool', 'Jus', 5.50, 1, 3, TRUE, 2),
('BOIS_SIROP', 'Sirops', 'Boissons', 'Sans Alcool', 'Sirops', 5.50, 1, 4, TRUE, 2),
('BOIS_ENERG', 'Energy drinks', 'Boissons', 'Sans Alcool', 'Energy', 5.50, 1, 5, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 2. BOISSONS CHAUDES
-- ═══════════════════════════════════════════════════════════════════════════
('BOIS_CAFE', 'Cafés', 'Boissons', 'Chaudes', 'Café', 5.50, 1, 10, TRUE, 2),
('BOIS_THE', 'Thés & Infusions', 'Boissons', 'Chaudes', 'Thé', 5.50, 1, 11, TRUE, 3),
('BOIS_CHOCO', 'Chocolats chauds', 'Boissons', 'Chaudes', 'Chocolat', 5.50, 1, 12, TRUE, 3),

-- ═══════════════════════════════════════════════════════════════════════════
-- 3. ALCOOLS (TVA 20%)
-- ═══════════════════════════════════════════════════════════════════════════
('ALC_BIERE', 'Bières', 'Boissons', 'Alcools', 'Bières', 20.00, 1, 20, TRUE, 3),
('ALC_VIN_RGE', 'Vins rouges', 'Boissons', 'Alcools', 'Vins rouges', 20.00, 1, 21, TRUE, 2),
('ALC_VIN_BLC', 'Vins blancs', 'Boissons', 'Alcools', 'Vins blancs', 20.00, 1, 22, TRUE, 2),
('ALC_VIN_ROSE', 'Vins rosés', 'Boissons', 'Alcools', 'Vins rosés', 20.00, 1, 23, TRUE, 3),
('ALC_SPIRIT', 'Spiritueux', 'Boissons', 'Alcools', 'Spiritueux', 20.00, 1, 24, TRUE, 2),
('ALC_APERO', 'Apéritifs', 'Boissons', 'Alcools', 'Apéritifs', 20.00, 1, 25, TRUE, 3),
('ALC_LIQUEUR', 'Liqueurs', 'Boissons', 'Alcools', 'Liqueurs', 20.00, 1, 26, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 4. PRODUITS LAITIERS (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('LAIT_UHT', 'Laits', 'Produits Laitiers', 'Laits', NULL, 5.50, 2, 1, TRUE, 1),
('LAIT_CREME', 'Crèmes', 'Produits Laitiers', 'Crèmes', NULL, 5.50, 2, 2, TRUE, 1),
('LAIT_BEURRE', 'Beurres', 'Produits Laitiers', 'Beurres', NULL, 5.50, 2, 3, TRUE, 1),
('LAIT_FROMAGE', 'Fromages', 'Produits Laitiers', 'Fromages', NULL, 5.50, 2, 4, TRUE, 1),
('LAIT_YAOURT', 'Yaourts', 'Produits Laitiers', 'Yaourts', NULL, 5.50, 2, 5, TRUE, 2),
('LAIT_DESSERT', 'Desserts lactés', 'Produits Laitiers', 'Desserts lactés', NULL, 5.50, 2, 6, TRUE, 3),

-- ═══════════════════════════════════════════════════════════════════════════
-- 5. ÉPICERIE SALÉE - FÉCULENTS (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('EPIC_PATE', 'Pâtes', 'Épicerie Salée', 'Féculents', 'Pâtes', 5.50, 3, 1, TRUE, 1),
('EPIC_RIZ', 'Riz', 'Épicerie Salée', 'Féculents', 'Riz', 5.50, 3, 2, TRUE, 1),
('EPIC_SEMOULE', 'Semoules & Couscous', 'Épicerie Salée', 'Féculents', 'Semoules', 5.50, 3, 3, TRUE, 1),
('EPIC_LEGUM_SEC', 'Légumineuses', 'Épicerie Salée', 'Féculents', 'Légumineuses', 5.50, 3, 4, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 6. ÉPICERIE SALÉE - CONSERVES (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('CONS_LEGUME', 'Conserves légumes', 'Épicerie Salée', 'Conserves', 'Légumes', 5.50, 3, 10, TRUE, 2),
('CONS_POISSON', 'Conserves poissons', 'Épicerie Salée', 'Conserves', 'Poissons', 5.50, 3, 11, TRUE, 2),
('CONS_PLAT', 'Plats préparés conserve', 'Épicerie Salée', 'Conserves', 'Plats', 5.50, 3, 12, FALSE, 0),
('CONS_SAUCE', 'Sauces & Coulis conserve', 'Épicerie Salée', 'Conserves', 'Sauces', 5.50, 3, 13, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 7. ÉPICERIE SALÉE - CONDIMENTS (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('COND_HUILE', 'Huiles', 'Épicerie Salée', 'Condiments', 'Huiles', 5.50, 3, 20, TRUE, 1),
('COND_VINAIGRE', 'Vinaigres', 'Épicerie Salée', 'Condiments', 'Vinaigres', 5.50, 3, 21, TRUE, 1),
('COND_SAUCE', 'Sauces froides', 'Épicerie Salée', 'Condiments', 'Sauces froides', 5.50, 3, 22, TRUE, 2),
('COND_EPICE', 'Épices & Aromates', 'Épicerie Salée', 'Condiments', 'Épices', 5.50, 3, 23, TRUE, 1),
('COND_BOUILLON', 'Bouillons & Fonds', 'Épicerie Salée', 'Condiments', 'Bouillons', 5.50, 3, 24, TRUE, 1),
('COND_SEL', 'Sels', 'Épicerie Salée', 'Condiments', 'Sels', 5.50, 3, 25, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 8. ÉPICERIE SUCRÉE - PETIT DÉJEUNER (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SUCR_CEREAL', 'Céréales', 'Épicerie Sucrée', 'Petit-déjeuner', 'Céréales', 5.50, 4, 1, TRUE, 3),
('SUCR_CONF', 'Confitures & Miels', 'Épicerie Sucrée', 'Petit-déjeuner', 'Confitures', 5.50, 4, 2, TRUE, 2),
('SUCR_SUCRE', 'Sucres', 'Épicerie Sucrée', 'Petit-déjeuner', 'Sucres', 5.50, 4, 3, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 9. ÉPICERIE SUCRÉE - BISCUITS & GÂTEAUX (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SUCR_BISC', 'Biscuits', 'Épicerie Sucrée', 'Biscuits & Gâteaux', 'Biscuits', 5.50, 4, 10, TRUE, 3),
('SUCR_GATEAU', 'Gâteaux', 'Épicerie Sucrée', 'Biscuits & Gâteaux', 'Gâteaux', 5.50, 4, 11, TRUE, 3),
('SUCR_VIEN', 'Viennoiseries', 'Épicerie Sucrée', 'Biscuits & Gâteaux', 'Viennoiseries', 5.50, 4, 12, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 10. ÉPICERIE SUCRÉE - CONFISERIES (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SUCR_CHOCO', 'Chocolats', 'Épicerie Sucrée', 'Confiseries', 'Chocolats', 5.50, 4, 20, TRUE, 2),
('SUCR_BONBON', 'Bonbons', 'Épicerie Sucrée', 'Confiseries', 'Bonbons', 5.50, 4, 21, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 11. ÉPICERIE SUCRÉE - PÂTISSERIE (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SUCR_FARINE', 'Farines', 'Épicerie Sucrée', 'Pâtisserie', 'Farines', 5.50, 4, 30, TRUE, 1),
('SUCR_LEVURE', 'Levures & Agents', 'Épicerie Sucrée', 'Pâtisserie', 'Levures', 5.50, 4, 31, TRUE, 1),
('SUCR_AROME', 'Arômes & Extraits', 'Épicerie Sucrée', 'Pâtisserie', 'Arômes', 5.50, 4, 32, TRUE, 1),
('SUCR_NAPPAGE', 'Nappages & Décorations', 'Épicerie Sucrée', 'Pâtisserie', 'Nappages', 5.50, 4, 33, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 12. PRODUITS FRAIS - VIANDES (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('FRAIS_BOEUF', 'Bœuf', 'Produits Frais', 'Viandes', 'Bœuf', 5.50, 5, 1, TRUE, 1),
('FRAIS_VOLAILLE', 'Volailles', 'Produits Frais', 'Viandes', 'Volailles', 5.50, 5, 2, TRUE, 1),
('FRAIS_PORC', 'Porc', 'Produits Frais', 'Viandes', 'Porc', 5.50, 5, 3, TRUE, 1),
('FRAIS_AGNEAU', 'Agneau & Veau', 'Produits Frais', 'Viandes', 'Agneau/Veau', 5.50, 5, 4, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 13. PRODUITS FRAIS - CHARCUTERIE (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('FRAIS_JAMBON', 'Jambons', 'Produits Frais', 'Charcuterie', 'Jambons', 5.50, 5, 10, TRUE, 2),
('FRAIS_SAUCISSE', 'Saucisses', 'Produits Frais', 'Charcuterie', 'Saucisses', 5.50, 5, 11, TRUE, 2),
('FRAIS_CHARC', 'Charcuterie diverse', 'Produits Frais', 'Charcuterie', 'Divers', 5.50, 5, 12, TRUE, 2),
('FRAIS_LARDON', 'Lardons & Allumettes', 'Produits Frais', 'Charcuterie', 'Lardons', 5.50, 5, 13, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 14. PRODUITS FRAIS - POISSONS (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('FRAIS_POISSON', 'Poissons frais', 'Produits Frais', 'Poissons', 'Poissons', 5.50, 5, 20, TRUE, 1),
('FRAIS_CRUST', 'Crustacés', 'Produits Frais', 'Poissons', 'Crustacés', 5.50, 5, 21, TRUE, 1),
('FRAIS_COQUIL', 'Coquillages', 'Produits Frais', 'Poissons', 'Coquillages', 5.50, 5, 22, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 15. PRODUITS FRAIS - AUTRES (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('FRAIS_OEUF', 'Œufs', 'Produits Frais', 'Œufs', NULL, 5.50, 5, 30, TRUE, 1),
('FRAIS_TRAIT', 'Traiteur frais', 'Produits Frais', 'Traiteur', NULL, 5.50, 5, 31, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 16. SURGELÉS (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SURG_LEGUME', 'Légumes surgelés', 'Surgelés', 'Légumes', NULL, 5.50, 6, 1, TRUE, 1),
('SURG_VIANDE', 'Viandes surgelées', 'Surgelés', 'Viandes', NULL, 5.50, 6, 2, TRUE, 1),
('SURG_POISSON', 'Poissons surgelés', 'Surgelés', 'Poissons', NULL, 5.50, 6, 3, TRUE, 1),
('SURG_PATISS', 'Pâtisserie surgelée', 'Surgelés', 'Pâtisserie', NULL, 5.50, 6, 4, TRUE, 2),
('SURG_GLACE', 'Glaces & Sorbets', 'Surgelés', 'Glaces', NULL, 5.50, 6, 5, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 17. BOULANGERIE (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('BOUL_PAIN', 'Pains', 'Boulangerie', 'Pains', NULL, 5.50, 7, 1, TRUE, 1),
('BOUL_BRIOCHE', 'Brioches', 'Boulangerie', 'Brioches', NULL, 5.50, 7, 2, TRUE, 2),
('BOUL_VIEN', 'Viennoiseries fraîches', 'Boulangerie', 'Viennoiseries', NULL, 5.50, 7, 3, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 18. FRUITS & LÉGUMES (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('FL_FRUIT', 'Fruits frais', 'Fruits & Légumes', 'Fruits', NULL, 5.50, 8, 1, TRUE, 1),
('FL_LEGUME', 'Légumes frais', 'Fruits & Légumes', 'Légumes', NULL, 5.50, 8, 2, TRUE, 1),
('FL_AROMATE', 'Aromates frais', 'Fruits & Légumes', 'Aromates', NULL, 5.50, 8, 3, TRUE, 1),
('FL_SALADE', 'Salades', 'Fruits & Légumes', 'Salades', NULL, 5.50, 8, 4, TRUE, 1),

-- ═══════════════════════════════════════════════════════════════════════════
-- 19. PRODUITS DU MONDE (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('MONDE_AFRIQUE', 'Afrique', 'Produits du Monde', 'Afrique', NULL, 5.50, 9, 1, TRUE, 2),
('MONDE_ASIE', 'Asie', 'Produits du Monde', 'Asie', NULL, 5.50, 9, 2, TRUE, 2),
('MONDE_ORIENT', 'Orient & Maghreb', 'Produits du Monde', 'Orient', NULL, 5.50, 9, 3, TRUE, 2),
('MONDE_AMERIQUE', 'Amérique latine', 'Produits du Monde', 'Amérique', NULL, 5.50, 9, 4, TRUE, 2),
('MONDE_HALAL', 'Produits Halal', 'Produits du Monde', 'Halal', NULL, 5.50, 9, 5, TRUE, 2),

-- ═══════════════════════════════════════════════════════════════════════════
-- 20. SNACKING & APÉRITIF (TVA 5.5%)
-- ═══════════════════════════════════════════════════════════════════════════
('SNACK_CHIPS', 'Chips', 'Snacking', 'Chips', NULL, 5.50, 10, 1, FALSE, 0),
('SNACK_FRUIT_SEC', 'Fruits secs & Oléagineux', 'Snacking', 'Fruits secs', NULL, 5.50, 10, 2, TRUE, 2),
('SNACK_BISCUIT', 'Biscuits apéritifs', 'Snacking', 'Biscuits apéro', NULL, 5.50, 10, 3, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 21. HYGIÈNE & ENTRETIEN (TVA 20%)
-- ═══════════════════════════════════════════════════════════════════════════
('HYG_CORPS', 'Hygiène corporelle', 'Hygiène', 'Corps', NULL, 20.00, 11, 1, FALSE, 0),
('HYG_PAPIER', 'Papeterie hygiène', 'Hygiène', 'Papier', NULL, 20.00, 11, 2, FALSE, 0),
('ENTR_LESSIVE', 'Lessives', 'Entretien', 'Lessive', NULL, 20.00, 11, 10, FALSE, 0),
('ENTR_NETTOY', 'Nettoyants', 'Entretien', 'Nettoyants', NULL, 20.00, 11, 11, FALSE, 0),
('ENTR_VAISS', 'Vaisselle', 'Entretien', 'Vaisselle', NULL, 20.00, 11, 12, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 22. CONSOMMABLES PROFESSIONNELS (TVA 20%)
-- ═══════════════════════════════════════════════════════════════════════════
('PRO_EMBALL', 'Emballages', 'Consommables Pro', 'Emballages', NULL, 20.00, 12, 1, FALSE, 0),
('PRO_JETABLE', 'Jetables', 'Consommables Pro', 'Jetables', NULL, 20.00, 12, 2, FALSE, 0),
('PRO_FILM', 'Films & Papiers', 'Consommables Pro', 'Films', NULL, 20.00, 12, 3, FALSE, 0),
('PRO_PROTECT', 'Protection', 'Consommables Pro', 'Protection', NULL, 20.00, 12, 4, FALSE, 0),
('PRO_ETIQ', 'Étiquetage', 'Consommables Pro', 'Étiquettes', NULL, 20.00, 12, 5, FALSE, 0),

-- ═══════════════════════════════════════════════════════════════════════════
-- 23. CATÉGORIE PAR DÉFAUT
-- ═══════════════════════════════════════════════════════════════════════════
('AUTRE', 'Non classé', 'Divers', 'Non classé', NULL, 20.00, 99, 99, FALSE, 0)

ON CONFLICT (code) DO UPDATE SET
    nom = EXCLUDED.nom,
    famille = EXCLUDED.famille,
    categorie = EXCLUDED.categorie,
    sous_categorie = EXCLUDED.sous_categorie,
    tva_defaut = EXCLUDED.tva_defaut,
    ordre_famille = EXCLUDED.ordre_famille,
    ordre_categorie = EXCLUDED.ordre_categorie,
    est_ingredient_resto = EXCLUDED.est_ingredient_resto,
    priorite_ingredient = EXCLUDED.priorite_ingredient;

-- =============================================================================
-- VUES UTILES
-- =============================================================================

-- Vue hiérarchique des catégories
CREATE OR REPLACE VIEW dwh.v_categories_hierarchie AS
SELECT 
    categorie_id,
    code,
    nom,
    famille,
    categorie,
    sous_categorie,
    CONCAT(famille, ' > ', categorie, COALESCE(' > ' || sous_categorie, '')) AS chemin_complet,
    tva_defaut,
    est_ingredient_resto,
    priorite_ingredient
FROM dwh.dim_categorie_produit
WHERE actif = TRUE
ORDER BY ordre_famille, ordre_categorie;

-- Vue des catégories ingrédients restaurant (triées par priorité)
CREATE OR REPLACE VIEW dwh.v_categories_ingredients AS
SELECT 
    categorie_id,
    code,
    nom,
    famille,
    categorie,
    CASE priorite_ingredient 
        WHEN 1 THEN '⭐⭐⭐ Haute'
        WHEN 2 THEN '⭐⭐ Moyenne'
        WHEN 3 THEN '⭐ Basse'
        ELSE 'N/A'
    END AS priorite_label
FROM dwh.dim_categorie_produit
WHERE est_ingredient_resto = TRUE
ORDER BY priorite_ingredient, famille, categorie;

-- Stats par famille
CREATE OR REPLACE VIEW dwh.v_stats_familles AS
SELECT 
    famille,
    COUNT(*) AS nb_categories,
    COUNT(*) FILTER (WHERE est_ingredient_resto) AS nb_ingredients,
    ROUND(AVG(tva_defaut), 2) AS tva_moyenne
FROM dwh.dim_categorie_produit
WHERE actif = TRUE
GROUP BY famille
ORDER BY MIN(ordre_famille);

-- =============================================================================
-- AFFICHAGE RÉCAPITULATIF
-- =============================================================================

SELECT 
    famille,
    COUNT(*) AS nb_sous_categories,
    STRING_AGG(nom, ', ' ORDER BY ordre_categorie) AS sous_categories
FROM dwh.dim_categorie_produit
WHERE actif = TRUE
GROUP BY famille, ordre_famille
ORDER BY ordre_famille;
