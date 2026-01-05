# Documentation SID - Corporate Information Factory (CIF)
## NOUTAM SAS & L'Incontournable - MassaCorp

---

## 1. Architecture Globale du SID

### 1.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          CORPORATE INFORMATION FACTORY                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                     ACQUISITION & STOCKAGE                                 │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                           │  │
│  │  SOURCES              STAGING            ODS                DWH           │  │
│  │  EXTERNES             (stg_*)            (ods_*)            (dwh.*)       │  │
│  │  ┌─────────┐         ┌─────────┐        ┌─────────┐        ┌─────────┐   │  │
│  │  │Factures │──────►  │ Données │──────► │ Données │──────► │ Données │   │  │
│  │  │PDF METRO│  Extract│ Brutes  │ Clean  │Validées │ Trans. │Historis.│   │  │
│  │  ├─────────┤         │ non     │ +      │Courantes│ +      │Stratég. │   │  │
│  │  │Relevés  │         │validées │ Valid. │Tactiques│ Histor.│Décision.│   │  │
│  │  │Bancaires│         └─────────┘        └─────────┘        └─────────┘   │  │
│  │  ├─────────┤              │                  │                  │        │  │
│  │  │Imports  │              │                  │                  │        │  │
│  │  │Manuels  │              ▼                  ▼                  ▼        │  │
│  │  └─────────┘         NETTOYAGE          DÉCISIONS          DÉCISIONS     │  │
│  │                      QUALITÉ            TACTIQUES          STRATÉGIQUES  │  │
│  │                      COHÉRENCE          (J à J+7)          (Historique)  │  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                     RESTITUTION & DIFFUSION                               │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                           │  │
│  │      DWH                    DATA MARTS              OUTILS BI             │  │
│  │  ┌─────────┐              ┌─────────────┐         ┌─────────────┐        │  │
│  │  │ Données │────────────► │v_tresorerie │────────►│  Tableaux   │        │  │
│  │  │historis.│              │  _analyse   │         │  de bord    │        │  │
│  │  └─────────┘              ├─────────────┤         ├─────────────┤        │  │
│  │                           │v_factures   │         │  Graphiques │        │  │
│  │      ODS                  │  _analyse   │         ├─────────────┤        │  │
│  │  ┌─────────┐              ├─────────────┤         │  Analyse    │        │  │
│  │  │ Données │────────────► │v_budget_vs  │         │  Multi-dim. │        │  │
│  │  │courantes│   OPER MARTS │   _reel     │         └─────────────┘        │  │
│  │  └─────────┘              └─────────────┘                                │  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Composants du SID

| Composant | Schéma | Rôle | Rétention |
|-----------|--------|------|-----------|
| **Staging** | `staging` | Données brutes avant validation | 7-30 jours |
| **ODS** | `ods` | Données courantes validées (tactique) | 1-3 mois |
| **DWH** | `dwh` | Données historisées (stratégique) | 10+ ans |
| **Data Marts** | Vues `v_*` | Agrégations métier sur DWH | N/A |
| **Oper Marts** | Vues `ods.v_*` | Agrégations métier sur ODS | N/A |

---

## 2. Processus ETL - Extraction, Transformation, Chargement

### 2.1 Vue d'ensemble du flux ETL

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  EXTRACTION  │───►│  NETTOYAGE   │───►│TRANSFORMATION│───►│HISTORISATION │
│              │    │  (Qualité)   │    │  (Format)    │    │  (SCD)       │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
   Sources PDF        Validation         Règles métier      Versioning
   API externes       Cohérence          Calculs dérivés    Type 1/2/3
   Fichiers CSV       Déduplication      Enrichissement     Audit trail
```

### 2.2 Exemple concret : Factures METRO

#### Source : Facture METRO PDF

**Facture 011-299013** (07-06-2024)
```
┌─────────────────────────────────────────────────────────────────┐
│ METRO France → NOUTAM (Client 135 00712188)                     │
├─────────────────────────────────────────────────────────────────┤
│ HEINEKEN 5D 65CL VP   │ 80 unités │ 1,404€ │ 1348,00€ HT       │
│ Livraison ZONE HALLES │  1 unité  │ 1,00€  │    1,00€ HT       │
│ PALETTE EUROPE        │  1 unité  │ 20,00€ │   20,00€ HT       │
├─────────────────────────────────────────────────────────────────┤
│ TOTAL HT: 1369,00€  │  TVA: 269,80€  │  TTC: 1638,80€          │
└─────────────────────────────────────────────────────────────────┘
```

**Facture 011-299014** (07-06-2024)
```
┌─────────────────────────────────────────────────────────────────┐
│ METRO France → NOUTAM (Client 135 00712188)                     │
├─────────────────────────────────────────────────────────────────┤
│ SPIRITUEUX (Jack Daniel's, Glenfiddich, Vodka...)  │ 792,47€   │
│ CAVE (Médoc, IGP, vins...)                         │ 385,02€   │
│ CHAMPAGNES (Veuve Clicquot)                        │ 221,94€   │
│ BRASSERIE (Leffe, Super Bock, Heineken, 1664...)   │ 446,67€   │
│ EPICERIE SECHE (tomate, huile, sel, mayo...)       │  91,07€   │
│ SURGELES (épinards)                                │  40,26€   │
│ DROGUERIE (liquide vaisselle)                      │  23,66€   │
├─────────────────────────────────────────────────────────────────┤
│ TOTAL HT: 1973,29€  │  TVA: 352,05€  │  TTC: 2325,34€          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Étape 1 : EXTRACTION

### 3.1 Sources de données

| Source | Format | Fréquence | Volume estimé |
|--------|--------|-----------|---------------|
| Factures METRO | PDF | Hebdo | ~50/mois |
| Relevés bancaires | OFX/CSV | Quotidien | ~200 lignes/mois |
| Caisse restaurant | API JSON | Temps réel | ~100/jour |
| Imports manuels | Excel/CSV | Ponctuel | Variable |

### 3.2 Structure Staging (données brutes)

```sql
-- staging.stg_facture_ligne : Lignes de factures extraites
CREATE TABLE staging.stg_facture_ligne (
    id SERIAL PRIMARY KEY,
    -- Identification
    batch_id UUID NOT NULL,                    -- Lot d'import
    source_file VARCHAR(500),                  -- Nom fichier source

    -- En-tête facture (extraction PDF)
    numero_facture VARCHAR(100),               -- Ex: 0/0(135)0011/021323
    numero_interne VARCHAR(50),                -- Ex: 011-299014
    date_facture DATE,
    date_impression TIMESTAMP,

    -- Fournisseur
    fournisseur_nom VARCHAR(200),              -- Ex: METRO France
    fournisseur_siret VARCHAR(20),
    fournisseur_tva_intra VARCHAR(20),
    fournisseur_adresse TEXT,
    magasin_nom VARCHAR(100),                  -- Ex: METRO LA CHAPELLE
    magasin_adresse TEXT,

    -- Client
    client_nom VARCHAR(200),                   -- Ex: NOUTAM
    client_numero VARCHAR(50),                 -- Ex: 135 00712188
    client_adresse TEXT,

    -- Ligne article
    ligne_numero INT,
    ean VARCHAR(20),                           -- Code EAN produit
    article_numero VARCHAR(20),                -- Numéro article METRO
    designation TEXT,                          -- Nom du produit
    categorie_source VARCHAR(100),             -- Ex: SPIRITUEUX, BRASSERIE

    -- Caractéristiques produit
    regie CHAR(1),                             -- S=Spiritueux, B=Bière, T=Vin...
    vol_alcool NUMERIC(5,2),                   -- % alcool
    vap NUMERIC(10,4),                         -- Volume Alcool Pur
    poids_volume NUMERIC(12,4),                -- Poids ou Volume unitaire
    unite VARCHAR(10),                         -- L, KG, unité

    -- Prix et quantités
    prix_unitaire NUMERIC(12,4),
    colisage INT,                              -- Nb par colis
    quantite INT,
    montant_ligne NUMERIC(14,2),

    -- TVA
    code_tva CHAR(1),                          -- A, B, C, D
    taux_tva NUMERIC(5,2),

    -- Flags
    est_promo BOOLEAN DEFAULT FALSE,
    cotis_secu NUMERIC(10,2),                  -- Cotisation sécurité sociale

    -- Métadonnées
    raw_line TEXT,                             -- Ligne brute du PDF
    extraction_date TIMESTAMPTZ DEFAULT NOW(),
    extraction_status VARCHAR(20) DEFAULT 'BRUT',
    validation_errors JSONB,

    -- Index clustering
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stg_facture_batch ON staging.stg_facture_ligne(batch_id);
CREATE INDEX idx_stg_facture_status ON staging.stg_facture_ligne(extraction_status);
```

### 3.3 Exemple de données extraites

```sql
-- Insertion des données extraites de la facture 011-299014
INSERT INTO staging.stg_facture_ligne (
    batch_id, source_file, numero_facture, numero_interne, date_facture,
    fournisseur_nom, fournisseur_siret, magasin_nom,
    client_nom, client_numero, client_adresse,
    ean, article_numero, designation, categorie_source,
    regie, vol_alcool, poids_volume, prix_unitaire, colisage, quantite, montant_ligne,
    code_tva, taux_tva, est_promo, cotis_secu
) VALUES
-- SPIRITUEUX
('a1b2c3d4-...', '135_11_299014_....pdf', '0/0(135)0011/021323', '011-299014', '2024-06-07',
 'METRO France', '399315613', 'METRO LA CHAPELLE',
 'NOUTAM', '135 00712188', '83, Rue des Poissonniers, 75018 Paris',
 '5099873089057', '0248567', 'WH JACK DANIEL''S 40D 35CL', 'SPIRITUEUX',
 'S', 40.0, 0.350, 9.340, 1, 2, 18.68, 'D', 20.00, TRUE, 1.68),

('a1b2c3d4-...', '135_11_299014_....pdf', '0/0(135)0011/021323', '011-299014', '2024-06-07',
 'METRO France', '399315613', 'METRO LA CHAPELLE',
 'NOUTAM', '135 00712188', '83, Rue des Poissonniers, 75018 Paris',
 '5010327325125', '0799775', 'WH GLENFIDDICH 15A 40D 70CL', 'SPIRITUEUX',
 'S', 40.0, 0.700, 41.940, 1, 15, 629.10, 'D', 20.00, FALSE, 25.20),

-- BRASSERIE
('a1b2c3d4-...', '135_11_299014_....pdf', '0/0(135)0011/021323', '011-299014', '2024-06-07',
 'METRO France', '399315613', 'METRO LA CHAPELLE',
 'NOUTAM', '135 00712188', '83, Rue des Poissonniers, 75018 Paris',
 '5410228203582', '2025492', 'LEFFE BLONDE 6.6 BLE 33CL', 'BRASSERIE',
 'B', 6.6, 0.330, 0.950, 12, 5, 57.00, 'D', 20.00, FALSE, NULL);
```

---

## 4. Étape 2 : NETTOYAGE (Qualité & Cohérence)

### 4.1 Règles de validation

```sql
-- Fonction de validation des lignes staging
CREATE OR REPLACE FUNCTION staging.valider_facture_lignes(p_batch_id UUID)
RETURNS TABLE(ligne_id INT, status VARCHAR, errors JSONB) AS $$
DECLARE
    r RECORD;
    v_errors JSONB;
BEGIN
    FOR r IN SELECT * FROM staging.stg_facture_ligne WHERE batch_id = p_batch_id LOOP
        v_errors := '[]'::JSONB;

        -- V1: Numéro facture obligatoire
        IF r.numero_facture IS NULL OR r.numero_facture = '' THEN
            v_errors := v_errors || '["V1: Numéro facture manquant"]'::JSONB;
        END IF;

        -- V2: Date facture valide
        IF r.date_facture IS NULL OR r.date_facture > CURRENT_DATE THEN
            v_errors := v_errors || '["V2: Date facture invalide"]'::JSONB;
        END IF;

        -- V3: Montant ligne cohérent (prix × qté ≈ montant)
        IF ABS(r.prix_unitaire * r.quantite - r.montant_ligne) > 0.02 THEN
            v_errors := v_errors || jsonb_build_array(
                format('V3: Montant incohérent: %s × %s ≠ %s',
                       r.prix_unitaire, r.quantite, r.montant_ligne)
            );
        END IF;

        -- V4: EAN format valide (13 ou 8 chiffres)
        IF r.ean IS NOT NULL AND r.ean !~ '^[0-9]{8,14}$' THEN
            v_errors := v_errors || '["V4: Format EAN invalide"]'::JSONB;
        END IF;

        -- V5: TVA cohérente avec régie
        IF r.regie = 'S' AND r.code_tva != 'D' THEN
            v_errors := v_errors || '["V5: Spiritueux devrait avoir TVA=D (20%)"]'::JSONB;
        END IF;

        -- V6: Volume alcool obligatoire pour alcools
        IF r.regie IN ('S', 'B', 'M', 'T') AND r.vol_alcool IS NULL THEN
            v_errors := v_errors || '["V6: Volume alcool manquant pour produit alcoolisé"]'::JSONB;
        END IF;

        -- Mise à jour du statut
        UPDATE staging.stg_facture_ligne
        SET
            extraction_status = CASE
                WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE'
                ELSE 'ERREUR'
            END,
            validation_errors = v_errors
        WHERE id = r.id;

        RETURN QUERY SELECT r.id,
            CASE WHEN jsonb_array_length(v_errors) = 0 THEN 'VALIDE' ELSE 'ERREUR' END::VARCHAR,
            v_errors;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### 4.2 Règles de nettoyage

| Code | Règle | Action |
|------|-------|--------|
| N1 | Trim espaces | `TRIM(designation)` |
| N2 | Majuscules uniformes | `UPPER(fournisseur_nom)` |
| N3 | Format date FR→ISO | `TO_DATE(date_str, 'DD-MM-YYYY')` |
| N4 | Virgule→Point décimal | `REPLACE(prix, ',', '.')::NUMERIC` |
| N5 | Déduplication EAN | Vérif doublons par EAN+date |
| N6 | Enrichissement catégorie | Mapping code régie → catégorie DWH |

### 4.3 Mapping des catégories

```sql
-- Table de correspondance régie METRO → catégorie DWH
CREATE TABLE staging.mapping_regie_categorie (
    regie CHAR(1) PRIMARY KEY,
    nom_regie VARCHAR(50),
    categorie_dwh_code VARCHAR(20),
    famille VARCHAR(50),
    sous_famille VARCHAR(50)
);

INSERT INTO staging.mapping_regie_categorie VALUES
    ('S', 'Spiritueux', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
    ('B', 'Bière', 'ALC_BIERE', 'Boissons', 'Bière'),
    ('M', 'Champagne/Mousseux', 'ALC_CHAMPAGNE', 'Boissons', 'Vin effervescent'),
    ('T', 'Vin tranquille', 'ALC_VIN', 'Boissons', 'Vin'),
    ('A', 'Consigne/Divers', 'DIV_CONSIGNE', 'Divers', 'Consigne'),
    ('C', 'Service/Livraison', 'DIV_SERVICE', 'Divers', 'Service');
```

---

## 5. Étape 3 : TRANSFORMATION (Format & Règles Métier)

### 5.1 Calculs dérivés

```sql
-- Transformation staging → ODS avec calculs métier
CREATE OR REPLACE FUNCTION staging.transformer_vers_ods(p_batch_id UUID)
RETURNS INT AS $$
DECLARE
    v_count INT := 0;
BEGIN
    INSERT INTO ods.ods_facture_ligne (
        -- Clés
        facture_id,
        ligne_id,

        -- Dimensions
        date_facture,
        fournisseur_sk,
        produit_ean,
        categorie_id,

        -- Mesures brutes
        quantite,
        prix_unitaire_ht,
        montant_ligne_ht,
        taux_tva,

        -- CALCULS DÉRIVÉS
        montant_tva,                           -- = montant_ht × taux_tva
        montant_ttc,                           -- = montant_ht + montant_tva
        prix_au_litre,                         -- = prix_unitaire / volume
        marge_estimee,                         -- = prix_vente_dwh - prix_achat

        -- Enrichissement
        est_alcool,
        volume_alcool_pur_total,               -- = quantité × volume × % alcool

        -- Métadonnées
        source_batch_id,
        source_ligne_id
    )
    SELECT
        -- Génération ID facture (hash numéro + date)
        MD5(s.numero_facture || s.date_facture::TEXT)::UUID,
        ROW_NUMBER() OVER (PARTITION BY s.numero_facture ORDER BY s.ligne_numero),

        -- Dimensions
        s.date_facture,
        f.fournisseur_sk,
        s.ean,
        c.categorie_id,

        -- Mesures brutes
        s.quantite,
        s.prix_unitaire,
        s.montant_ligne,
        s.taux_tva,

        -- CALCULS DÉRIVÉS
        ROUND(s.montant_ligne * s.taux_tva / 100, 2),        -- TVA
        ROUND(s.montant_ligne * (1 + s.taux_tva / 100), 2),  -- TTC
        CASE
            WHEN s.poids_volume > 0
            THEN ROUND(s.prix_unitaire / s.poids_volume, 3)
            ELSE NULL
        END,                                                   -- Prix/L
        NULL,                                                  -- Marge (calculée après)

        -- Enrichissement
        s.regie IN ('S', 'B', 'M', 'T'),                      -- Est alcool
        CASE
            WHEN s.regie IN ('S', 'B', 'M', 'T')
            THEN s.quantite * s.poids_volume * s.vol_alcool / 100
            ELSE 0
        END,                                                   -- VAP total

        -- Métadonnées
        p_batch_id,
        s.id
    FROM staging.stg_facture_ligne s
    LEFT JOIN dwh.dim_fournisseur f ON f.siret = s.fournisseur_siret AND f.est_actuel
    LEFT JOIN dwh.dim_categorie_produit c ON c.code = (
        SELECT categorie_dwh_code FROM staging.mapping_regie_categorie WHERE regie = s.regie
    )
    WHERE s.batch_id = p_batch_id
      AND s.extraction_status = 'VALIDE';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
```

### 5.2 Règles métier appliquées

| Règle | Description | Formule |
|-------|-------------|---------|
| **TVA** | Calcul TVA ligne | `montant_ht × taux_tva / 100` |
| **TTC** | Montant TTC | `montant_ht × (1 + taux_tva / 100)` |
| **Prix/L** | Prix au litre | `prix_unitaire / volume_unitaire` |
| **VAP** | Volume Alcool Pur | `qté × volume × degré / 100` |
| **Cotis. SS** | Cotisation sécu. sociale | Présente sur facture (alcools >18°) |
| **Marge** | Marge estimée | `prix_vente_catalogue - prix_achat` |

---

## 6. Étape 4 : HISTORISATION (DWH)

### 6.1 Types de SCD (Slowly Changing Dimensions)

```
┌─────────────────────────────────────────────────────────────────┐
│                  TYPES DE SCD UTILISÉS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TYPE 0 (Invariant)                                            │
│  ─────────────────                                             │
│  Tables: dim_temps                                             │
│  Comportement: Jamais modifié après création                   │
│  Exemple: 20240607 = Vendredi 7 juin 2024 (fixe)              │
│                                                                 │
│  TYPE 1 (Écrasement)                                           │
│  ──────────────────                                            │
│  Tables: dim_devise, dim_mode_paiement, dim_categorie          │
│  Comportement: Mise à jour directe, pas d'historique           │
│  Usage: Données de référence stables                           │
│                                                                 │
│  TYPE 2 (Historisation complète)                               │
│  ──────────────────────────────                                │
│  Tables: dim_produit, dim_fournisseur, dim_plat                │
│  Comportement: Nouvelle ligne à chaque changement              │
│  Colonnes: date_debut, date_fin, est_actuel                    │
│                                                                 │
│  Exemple SCD Type 2:                                           │
│  ┌──────┬─────────┬───────────┬───────────┬──────────┐        │
│  │ SK   │ Produit │ Prix      │ Début     │ Actuel   │        │
│  ├──────┼─────────┼───────────┼───────────┼──────────┤        │
│  │ 101  │ Heineken│ 1.350€    │ 2024-01-01│ FALSE    │        │
│  │ 102  │ Heineken│ 1.404€    │ 2024-06-01│ TRUE     │        │
│  └──────┴─────────┴───────────┴───────────┴──────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Procédure d'historisation SCD Type 2

```sql
-- Gestion SCD Type 2 pour les produits
CREATE OR REPLACE FUNCTION dwh.scd2_update_produit(
    p_produit_id INT,
    p_nouveau_prix_achat NUMERIC,
    p_nouveau_prix_vente NUMERIC
)
RETURNS INT AS $$
DECLARE
    v_current_sk INT;
    v_new_sk INT;
BEGIN
    -- 1. Trouver la version actuelle
    SELECT produit_sk INTO v_current_sk
    FROM dwh.dim_produit
    WHERE produit_id = p_produit_id AND est_actuel = TRUE;

    IF v_current_sk IS NULL THEN
        RAISE EXCEPTION 'Produit % non trouvé', p_produit_id;
    END IF;

    -- 2. Fermer la version actuelle
    UPDATE dwh.dim_produit
    SET
        date_fin = CURRENT_DATE - 1,
        est_actuel = FALSE
    WHERE produit_sk = v_current_sk;

    -- 3. Créer nouvelle version
    INSERT INTO dwh.dim_produit (
        produit_id, tenant_id, nom, categorie_id,
        prix_achat, prix_vente, tva_pct, seuil_alerte,
        date_debut, date_fin, est_actuel
    )
    SELECT
        produit_id, tenant_id, nom, categorie_id,
        p_nouveau_prix_achat,
        p_nouveau_prix_vente,
        tva_pct, seuil_alerte,
        CURRENT_DATE,
        NULL,
        TRUE
    FROM dwh.dim_produit
    WHERE produit_sk = v_current_sk
    RETURNING produit_sk INTO v_new_sk;

    RETURN v_new_sk;
END;
$$ LANGUAGE plpgsql;
```

### 6.3 Chargement dans les tables de faits

```sql
-- Chargement ODS → DWH (faits achats)
CREATE OR REPLACE PROCEDURE dwh.charger_faits_achats(p_date_debut DATE, p_date_fin DATE)
LANGUAGE plpgsql AS $$
DECLARE
    v_count INT;
BEGIN
    INSERT INTO dwh.fait_achats (
        date_id,
        fournisseur_sk,
        produit_sk,
        categorie_id,

        quantite,
        montant_ht,
        montant_tva,
        montant_ttc,

        facture_numero,
        ligne_numero,
        source
    )
    SELECT
        TO_CHAR(o.date_facture, 'YYYYMMDD')::INT,
        o.fournisseur_sk,
        COALESCE(p.produit_sk, -1),  -- -1 = produit inconnu
        o.categorie_id,

        o.quantite,
        o.montant_ligne_ht,
        o.montant_tva,
        o.montant_ttc,

        f.numero_facture,
        o.ligne_id,
        'METRO'
    FROM ods.ods_facture_ligne o
    JOIN ods.ods_facture_entete f ON f.facture_id = o.facture_id
    LEFT JOIN dwh.dim_produit p ON p.ean = o.produit_ean AND p.est_actuel
    WHERE o.date_facture BETWEEN p_date_debut AND p_date_fin
      AND NOT EXISTS (
          SELECT 1 FROM dwh.fait_achats fa
          WHERE fa.facture_numero = f.numero_facture
            AND fa.ligne_numero = o.ligne_id
      );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Chargé % lignes dans fait_achats', v_count;
END;
$$;
```

---

## 7. Gestion des Colonnes Manquantes

### 7.1 Problématique

Lors de l'insertion dans les tables cibles, certaines colonnes peuvent manquer dans les données sources :

```
┌────────────────────────────────────────────────────────────────────┐
│  SCÉNARIOS DE COLONNES MANQUANTES                                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1. Colonne obligatoire manquante                                 │
│     → Erreur bloquante, insertion rejetée                         │
│     → Action: Compléter manuellement ou valeur par défaut         │
│                                                                    │
│  2. Colonne optionnelle manquante                                 │
│     → NULL accepté, insertion OK                                  │
│     → Action: Aucune                                               │
│                                                                    │
│  3. Colonne dérivable manquante                                   │
│     → Peut être calculée à partir d'autres colonnes              │
│     → Action: Calcul automatique (GENERATED ou trigger)           │
│                                                                    │
│  4. Colonne enrichissable manquante                               │
│     → Peut être retrouvée via lookup (jointure)                  │
│     → Action: Enrichissement via tables de référence              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 7.2 Stratégies de gestion

#### Stratégie 1 : Valeurs par défaut

```sql
-- Définition des valeurs par défaut au niveau table
ALTER TABLE dwh.fait_achats
    ALTER COLUMN source SET DEFAULT 'INCONNU',
    ALTER COLUMN created_at SET DEFAULT NOW();

-- Ou lors de l'insertion
INSERT INTO dwh.fait_achats (date_id, montant_ht, source)
SELECT
    date_id,
    montant_ht,
    COALESCE(source, 'METRO')  -- Valeur par défaut si NULL
FROM staging.stg_facture;
```

#### Stratégie 2 : Colonnes calculées (GENERATED)

```sql
-- Colonnes auto-calculées
CREATE TABLE dwh.dim_produit (
    ...
    prix_achat NUMERIC(10,2),
    prix_vente NUMERIC(10,2),

    -- Colonnes GÉNÉRÉES automatiquement
    marge_unitaire NUMERIC(10,2) GENERATED ALWAYS AS (
        prix_vente - prix_achat
    ) STORED,

    marge_pct NUMERIC(8,2) GENERATED ALWAYS AS (
        CASE WHEN prix_vente > 0
             THEN ROUND((prix_vente - prix_achat) / prix_vente * 100, 2)
             ELSE 0
        END
    ) STORED
);

-- Avantage: Pas besoin de fournir ces colonnes à l'insertion
INSERT INTO dwh.dim_produit (nom, prix_achat, prix_vente)
VALUES ('Heineken 65CL', 1.10, 1.40);
-- marge_unitaire = 0.30, marge_pct = 21.43 (calculés automatiquement)
```

#### Stratégie 3 : Enrichissement par lookup

```sql
-- Fonction d'enrichissement des colonnes manquantes
CREATE OR REPLACE FUNCTION staging.enrichir_colonnes_manquantes(p_batch_id UUID)
RETURNS TABLE(colonne TEXT, nb_enrichis INT) AS $$
BEGIN
    -- Enrichir fournisseur_sk si manquant
    UPDATE staging.stg_facture_ligne s
    SET fournisseur_sk = f.fournisseur_sk
    FROM dwh.dim_fournisseur f
    WHERE s.batch_id = p_batch_id
      AND s.fournisseur_sk IS NULL
      AND f.siret = s.fournisseur_siret
      AND f.est_actuel = TRUE;

    RETURN QUERY SELECT 'fournisseur_sk'::TEXT, COUNT(*)::INT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND fournisseur_sk IS NOT NULL;

    -- Enrichir categorie_id via mapping régie
    UPDATE staging.stg_facture_ligne s
    SET categorie_id = c.categorie_id
    FROM staging.mapping_regie_categorie m
    JOIN dwh.dim_categorie_produit c ON c.code = m.categorie_dwh_code
    WHERE s.batch_id = p_batch_id
      AND s.categorie_id IS NULL
      AND m.regie = s.regie;

    RETURN QUERY SELECT 'categorie_id'::TEXT, COUNT(*)::INT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND categorie_id IS NOT NULL;

    -- Enrichir taux_tva via code_tva
    UPDATE staging.stg_facture_ligne
    SET taux_tva = CASE code_tva
        WHEN 'A' THEN 0.00
        WHEN 'B' THEN 5.50
        WHEN 'C' THEN 10.00
        WHEN 'D' THEN 20.00
        ELSE NULL
    END
    WHERE batch_id = p_batch_id
      AND taux_tva IS NULL
      AND code_tva IS NOT NULL;

    RETURN QUERY SELECT 'taux_tva'::TEXT, COUNT(*)::INT
    FROM staging.stg_facture_ligne
    WHERE batch_id = p_batch_id AND taux_tva IS NOT NULL;
END;
$$ LANGUAGE plpgsql;
```

#### Stratégie 4 : Clés surrogate pour valeurs inconnues

```sql
-- Créer des entrées "inconnues" dans les dimensions
INSERT INTO dwh.dim_fournisseur (fournisseur_sk, fournisseur_id, nom, est_actuel)
VALUES (-1, -1, 'FOURNISSEUR INCONNU', TRUE);

INSERT INTO dwh.dim_produit (produit_sk, produit_id, nom, est_actuel)
VALUES (-1, -1, 'PRODUIT INCONNU', TRUE);

INSERT INTO dwh.dim_categorie_produit (categorie_id, code, nom)
VALUES (-1, 'INCONNU', 'Catégorie inconnue');

-- Utilisation lors de l'insertion
INSERT INTO dwh.fait_achats (fournisseur_sk, produit_sk, ...)
SELECT
    COALESCE(f.fournisseur_sk, -1),  -- -1 si non trouvé
    COALESCE(p.produit_sk, -1),
    ...
FROM staging.stg_facture_ligne s
LEFT JOIN dwh.dim_fournisseur f ON ...
LEFT JOIN dwh.dim_produit p ON ...;
```

### 7.3 Rapport des colonnes manquantes

```sql
-- Vue de monitoring des colonnes manquantes
CREATE OR REPLACE VIEW staging.v_colonnes_manquantes AS
SELECT
    batch_id,
    COUNT(*) AS total_lignes,
    SUM(CASE WHEN fournisseur_siret IS NULL THEN 1 ELSE 0 END) AS siret_manquant,
    SUM(CASE WHEN ean IS NULL THEN 1 ELSE 0 END) AS ean_manquant,
    SUM(CASE WHEN categorie_source IS NULL THEN 1 ELSE 0 END) AS categorie_manquante,
    SUM(CASE WHEN taux_tva IS NULL THEN 1 ELSE 0 END) AS tva_manquante,
    SUM(CASE WHEN prix_unitaire IS NULL THEN 1 ELSE 0 END) AS prix_manquant,
    SUM(CASE WHEN quantite IS NULL THEN 1 ELSE 0 END) AS quantite_manquante
FROM staging.stg_facture_ligne
GROUP BY batch_id;

-- Exemple de résultat:
-- batch_id | total | siret | ean | categorie | tva | prix | quantite
-- a1b2c3d4 |   45  |   0   |  2  |     0     |  0  |   0  |    0
```

---

## 8. Data Marts & Oper Marts

### 8.1 Data Marts (vues sur DWH - décisions stratégiques)

```sql
-- Data Mart : Analyse des achats fournisseurs
CREATE OR REPLACE VIEW dwh.v_analyse_achats_fournisseur AS
SELECT
    t.annee,
    t.trimestre,
    t.mois,
    f.nom AS fournisseur,
    c.famille,
    c.nom AS categorie,

    -- Mesures
    COUNT(DISTINCT fa.facture_numero) AS nb_factures,
    SUM(fa.quantite) AS volume_total,
    SUM(fa.montant_ht) AS achats_ht,
    SUM(fa.montant_ttc) AS achats_ttc,
    AVG(fa.montant_ht / NULLIF(fa.quantite, 0)) AS prix_moyen,

    -- Évolution
    LAG(SUM(fa.montant_ht)) OVER (
        PARTITION BY f.fournisseur_sk, c.categorie_id
        ORDER BY t.annee, t.mois
    ) AS achats_ht_mois_precedent,

    -- % du total
    SUM(fa.montant_ht) * 100.0 / SUM(SUM(fa.montant_ht)) OVER (
        PARTITION BY t.annee, t.mois
    ) AS pct_achats_mois

FROM dwh.fait_achats fa
JOIN dwh.dim_temps t ON fa.date_id = t.date_id
JOIN dwh.dim_fournisseur f ON fa.fournisseur_sk = f.fournisseur_sk
LEFT JOIN dwh.dim_categorie_produit c ON fa.categorie_id = c.categorie_id
GROUP BY t.annee, t.trimestre, t.mois, f.nom, f.fournisseur_sk,
         c.famille, c.nom, c.categorie_id;

-- Data Mart : Trésorerie prévisionnelle
CREATE OR REPLACE VIEW dwh.v_tresorerie_analyse AS
SELECT
    t.date_complete,
    t.annee_mois,
    t.nom_jour,
    t.est_weekend,

    -- Entrées (ventes)
    SUM(CASE WHEN type = 'VENTE' THEN montant ELSE 0 END) AS entrees,

    -- Sorties (achats)
    SUM(CASE WHEN type = 'ACHAT' THEN montant ELSE 0 END) AS sorties,

    -- Solde journalier
    SUM(CASE WHEN type = 'VENTE' THEN montant ELSE -montant END) AS solde_jour,

    -- Cumul
    SUM(SUM(CASE WHEN type = 'VENTE' THEN montant ELSE -montant END)) OVER (
        ORDER BY t.date_complete
    ) AS solde_cumule

FROM dwh.fait_tresorerie ft
JOIN dwh.dim_temps t ON ft.date_id = t.date_id
GROUP BY t.date_complete, t.annee_mois, t.nom_jour, t.est_weekend;
```

### 8.2 Oper Marts (vues sur ODS - décisions tactiques)

```sql
-- Oper Mart : Factures en attente de validation (tactique J+0 à J+7)
CREATE OR REPLACE VIEW ods.v_factures_a_valider AS
SELECT
    f.facture_id,
    f.numero_facture,
    f.date_facture,
    f.fournisseur_nom,
    f.montant_total_ht,
    f.montant_total_ttc,
    f.statut,
    f.date_echeance,

    -- Alerte délai
    CURRENT_DATE - f.date_facture AS jours_depuis_reception,
    f.date_echeance - CURRENT_DATE AS jours_avant_echeance,

    -- Priorité
    CASE
        WHEN f.date_echeance <= CURRENT_DATE THEN 'URGENT'
        WHEN f.date_echeance <= CURRENT_DATE + 7 THEN 'PRIORITAIRE'
        ELSE 'NORMAL'
    END AS priorite,

    -- Lignes avec erreurs
    (SELECT COUNT(*) FROM ods.ods_facture_ligne l
     WHERE l.facture_id = f.facture_id AND l.has_error) AS nb_lignes_erreur

FROM ods.ods_facture_entete f
WHERE f.statut IN ('BROUILLON', 'EN_ATTENTE', 'A_COMPLETER')
ORDER BY
    CASE WHEN f.date_echeance <= CURRENT_DATE THEN 0 ELSE 1 END,
    f.date_echeance;
```

---

## 9. Pipeline ETL Complet

### 9.1 Orchestration du flux

```sql
-- Procédure ETL complète : PDF → DWH
CREATE OR REPLACE PROCEDURE etl.run_pipeline_factures(
    p_source_files TEXT[],
    p_dry_run BOOLEAN DEFAULT FALSE
)
LANGUAGE plpgsql AS $$
DECLARE
    v_batch_id UUID := gen_random_uuid();
    v_step INT := 1;
    v_count INT;
BEGIN
    RAISE NOTICE '=== PIPELINE ETL FACTURES - Batch % ===', v_batch_id;

    -- ÉTAPE 1: Extraction
    RAISE NOTICE '[%] Extraction des PDFs...', v_step;
    -- (Appel script Python d'extraction PDF ici)
    v_step := v_step + 1;

    -- ÉTAPE 2: Validation
    RAISE NOTICE '[%] Validation des données...', v_step;
    PERFORM staging.valider_facture_lignes(v_batch_id);

    SELECT COUNT(*) INTO v_count
    FROM staging.stg_facture_ligne
    WHERE batch_id = v_batch_id AND extraction_status = 'ERREUR';

    IF v_count > 0 THEN
        RAISE WARNING '  → % lignes en erreur', v_count;
    END IF;
    v_step := v_step + 1;

    -- ÉTAPE 3: Enrichissement colonnes manquantes
    RAISE NOTICE '[%] Enrichissement colonnes manquantes...', v_step;
    PERFORM staging.enrichir_colonnes_manquantes(v_batch_id);
    v_step := v_step + 1;

    -- ÉTAPE 4: Transformation → ODS
    RAISE NOTICE '[%] Transformation vers ODS...', v_step;
    SELECT staging.transformer_vers_ods(v_batch_id) INTO v_count;
    RAISE NOTICE '  → % lignes insérées dans ODS', v_count;
    v_step := v_step + 1;

    IF p_dry_run THEN
        RAISE NOTICE '[DRY RUN] Rollback...';
        ROLLBACK;
        RETURN;
    END IF;

    -- ÉTAPE 5: Chargement → DWH
    RAISE NOTICE '[%] Chargement vers DWH...', v_step;
    CALL dwh.charger_faits_achats(
        (SELECT MIN(date_facture) FROM ods.ods_facture_ligne WHERE source_batch_id = v_batch_id),
        (SELECT MAX(date_facture) FROM ods.ods_facture_ligne WHERE source_batch_id = v_batch_id)
    );
    v_step := v_step + 1;

    -- ÉTAPE 6: Nettoyage staging
    RAISE NOTICE '[%] Nettoyage staging...', v_step;
    DELETE FROM staging.stg_facture_ligne
    WHERE batch_id = v_batch_id
      AND extraction_status = 'VALIDE'
      AND created_at < NOW() - INTERVAL '7 days';

    RAISE NOTICE '=== PIPELINE TERMINÉ ===';
    COMMIT;
END;
$$;
```

### 9.2 Monitoring et audit

```sql
-- Table d'audit des exécutions ETL
CREATE TABLE etl.audit_execution (
    execution_id SERIAL PRIMARY KEY,
    batch_id UUID NOT NULL,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'RUNNING',

    -- Compteurs
    lignes_extraites INT DEFAULT 0,
    lignes_validees INT DEFAULT 0,
    lignes_erreur INT DEFAULT 0,
    lignes_chargees_ods INT DEFAULT 0,
    lignes_chargees_dwh INT DEFAULT 0,

    -- Erreurs
    error_message TEXT,
    error_details JSONB
);

-- Vue synthèse exécutions
CREATE VIEW etl.v_synthese_executions AS
SELECT
    DATE(started_at) AS date_execution,
    pipeline_name,
    COUNT(*) AS nb_executions,
    SUM(lignes_extraites) AS total_extraites,
    SUM(lignes_validees) AS total_validees,
    SUM(lignes_erreur) AS total_erreurs,
    SUM(lignes_chargees_dwh) AS total_dwh,
    ROUND(100.0 * SUM(lignes_validees) / NULLIF(SUM(lignes_extraites), 0), 1) AS taux_validation,
    AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) AS duree_moyenne_sec
FROM etl.audit_execution
WHERE status = 'SUCCESS'
GROUP BY DATE(started_at), pipeline_name;
```

---

## 10. Résumé Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE SID MASSACORP                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  SOURCES                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ Factures    │  │ Relevés     │  │ Caisse      │  │ Imports     │           │
│  │ METRO (PDF) │  │ Bancaires   │  │ Restaurant  │  │ Manuels     │           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │
│         │                │                │                │                   │
│         └────────────────┴────────────────┴────────────────┘                   │
│                                   │                                             │
│                          ┌────────▼────────┐                                   │
│                          │   EXTRACTION    │                                   │
│                          │   (PDF Parser)  │                                   │
│                          └────────┬────────┘                                   │
│                                   │                                             │
│  STAGING          ┌───────────────▼───────────────┐                            │
│                   │    staging.stg_facture_*      │  ◄── Données brutes        │
│                   │    Rétention: 7-30 jours      │                            │
│                   └───────────────┬───────────────┘                            │
│                                   │                                             │
│                          ┌────────▼────────┐                                   │
│                          │   NETTOYAGE     │  ◄── Validation + Qualité         │
│                          │   TRANSFORMATION│  ◄── Règles métier + Calculs      │
│                          └────────┬────────┘                                   │
│                                   │                                             │
│  ODS              ┌───────────────▼───────────────┐                            │
│                   │    ods.ods_facture_*          │  ◄── Décisions TACTIQUES   │
│                   │    Données courantes validées │      (J à J+7)             │
│                   │    Rétention: 1-3 mois        │                            │
│                   └───────────────┬───────────────┘                            │
│                                   │                                             │
│                          ┌────────▼────────┐                                   │
│                          │  HISTORISATION  │  ◄── SCD Type 0/1/2              │
│                          │  (SCD)          │                                   │
│                          └────────┬────────┘                                   │
│                                   │                                             │
│  DWH              ┌───────────────▼───────────────┐                            │
│                   │    dwh.dim_* / dwh.fait_*     │  ◄── Décisions STRATÉGIQUES│
│                   │    Données historisées        │      (Analyse tendances)   │
│                   │    Rétention: 10+ ans         │                            │
│                   └───────────────┬───────────────┘                            │
│                                   │                                             │
│  MARTS            ┌───────────────▼───────────────┐                            │
│                   │    dwh.v_* (Data Marts)       │  ◄── Vues pré-agrégées     │
│                   │    ods.v_* (Oper Marts)       │      Dashboards + Rapports │
│                   └───────────────────────────────┘                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

*Document généré le 2026-01-02*
*MassaCorp - NOUTAM SAS & L'Incontournable*
