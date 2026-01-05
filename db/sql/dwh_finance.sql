-- ============================================================================
-- MASSACORP - SCHEMA DWH FINANCE COMPLET
-- Architecture SID (Corporate Information Factory)
-- ============================================================================
--
-- ARCHITECTURE:
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │                        ACQUISITION & STOCKAGE                           │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │  Sources externes    →  STAGING (stg_*)  →  ODS (ods_*)  →  DWH (dwh.*) │
-- │  - Factures PDF          Données brutes     Données        Données      │
-- │  - Relevés bancaires     non validées       validées       historisées  │
-- │  - Imports manuels                          courantes      stratégiques │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │                        RESTITUTION & DIFFUSION                          │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │  DWH  →  Data Marts (vues métier)  →  BI Tools                         │
-- │          - v_tresorerie_analyse                                         │
-- │          - v_factures_analyse                                           │
-- │          - v_budget_vs_reel                                             │
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- CONVENTIONS:
-- - Préfixe stg_  : Staging (données brutes, temporaires)
-- - Préfixe ods_  : Operational Data Store (données courantes validées)
-- - Schéma dwh.   : Data Warehouse (données historisées)
-- - Suffixe _sk   : Surrogate Key (clé technique)
-- - Suffixe _id   : Business Key (clé métier)
--
-- SCD (Slowly Changing Dimensions):
-- - Type 1: Écrasement (dim_mode_paiement, dim_devise)
-- - Type 2: Historisation complète (dim_compte_bancaire, dim_fournisseur)
-- - Type 3: Attribut précédent (non utilisé ici)
--
-- ============================================================================

-- ============================================================================
-- SECTION 1: CRÉATION DES SCHÉMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS ods;
-- dwh existe déjà

COMMENT ON SCHEMA staging IS 'Zone de staging - données brutes avant validation';
COMMENT ON SCHEMA ods IS 'Operational Data Store - données validées pour usage tactique';

-- ============================================================================
-- SECTION 2: DIMENSIONS DWH - FINANCE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- dim_devise : Devises (SCD Type 1 - référentiel stable)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Référentiel des devises pour transactions multi-devises.
-- Permet la conversion et l'analyse par devise.
-- GRAIN: Une ligne par devise
-- HISTORISATION: SCD Type 1 (écrasement - devise = référentiel ISO stable)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_devise (
    devise_id SERIAL PRIMARY KEY,
    code_iso VARCHAR(3) NOT NULL UNIQUE,      -- EUR, USD, GBP
    nom VARCHAR(100) NOT NULL,                 -- Euro, Dollar US
    symbole VARCHAR(5),                        -- €, $, £
    decimales INT DEFAULT 2,                   -- Précision décimale
    est_devise_base BOOLEAN DEFAULT FALSE,     -- TRUE pour EUR (devise comptable)
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.dim_devise IS 'Dimension devises - SCD Type 1 - Référentiel ISO 4217';
COMMENT ON COLUMN dwh.dim_devise.est_devise_base IS 'TRUE pour la devise de comptabilité (EUR)';

-- Données de référence
INSERT INTO dwh.dim_devise (code_iso, nom, symbole, est_devise_base) VALUES
    ('EUR', 'Euro', '€', TRUE),
    ('USD', 'Dollar américain', '$', FALSE),
    ('GBP', 'Livre sterling', '£', FALSE),
    ('CHF', 'Franc suisse', 'CHF', FALSE)
ON CONFLICT (code_iso) DO NOTHING;

-- ----------------------------------------------------------------------------
-- dim_mode_paiement : Modes de paiement (SCD Type 1)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Classification des moyens de paiement pour analyse
-- des flux de trésorerie et rapprochement bancaire.
-- GRAIN: Une ligne par mode de paiement
-- HISTORISATION: SCD Type 1 (écrasement - nomenclature interne)
-- HIÉRARCHIE: type_paiement > mode (ex: Électronique > Carte bancaire)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_mode_paiement (
    mode_paiement_id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,          -- CB, VIR, CHQ, ESP, PRLV
    nom VARCHAR(100) NOT NULL,                 -- Carte bancaire, Virement
    type_paiement VARCHAR(50) NOT NULL,        -- Électronique, Papier, Espèces
    delai_encaissement_jours INT DEFAULT 0,    -- J+0, J+1, J+2 selon mode
    frais_pct NUMERIC(5,4) DEFAULT 0,          -- Commission (CB ~1.5%)
    frais_fixes NUMERIC(10,2) DEFAULT 0,       -- Frais fixes par transaction
    est_entrant BOOLEAN DEFAULT TRUE,          -- Peut recevoir paiements
    est_sortant BOOLEAN DEFAULT TRUE,          -- Peut émettre paiements
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.dim_mode_paiement IS 'Dimension modes de paiement - SCD Type 1';
COMMENT ON COLUMN dwh.dim_mode_paiement.delai_encaissement_jours IS 'Délai entre paiement et crédit effectif';

INSERT INTO dwh.dim_mode_paiement (code, nom, type_paiement, delai_encaissement_jours, frais_pct) VALUES
    ('ESP', 'Espèces', 'Espèces', 0, 0),
    ('CB', 'Carte bancaire', 'Électronique', 1, 0.015),
    ('VIR', 'Virement bancaire', 'Électronique', 1, 0),
    ('VIR_INST', 'Virement instantané', 'Électronique', 0, 0.001),
    ('CHQ', 'Chèque', 'Papier', 3, 0),
    ('PRLV', 'Prélèvement automatique', 'Électronique', 2, 0),
    ('TIP', 'Titre interbancaire de paiement', 'Papier', 3, 0),
    ('LCR', 'Lettre de change relevé', 'Papier', 0, 0),
    ('AVOIR', 'Avoir/Compensation', 'Interne', 0, 0)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- dim_type_document : Types de documents financiers (SCD Type 1)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Classification des documents pour le workflow de traitement
-- et l'archivage légal (durée conservation différente selon type).
-- GRAIN: Une ligne par type de document
-- HISTORISATION: SCD Type 1
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_type_document (
    type_document_id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('ENTRANT', 'SORTANT', 'INTERNE')),
    -- Règles légales
    duree_conservation_annees INT DEFAULT 10,  -- Obligation légale
    require_validation BOOLEAN DEFAULT TRUE,   -- Nécessite approbation
    -- Catégorisation
    famille VARCHAR(50) NOT NULL,              -- ACHAT, VENTE, BANQUE, FISCAL
    impact_tresorerie VARCHAR(10) CHECK (impact_tresorerie IN ('DEBIT', 'CREDIT', 'NEUTRE')),
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.dim_type_document IS 'Dimension types documents - SCD Type 1 - Règles légales et workflow';

INSERT INTO dwh.dim_type_document (code, nom, sens, famille, impact_tresorerie, duree_conservation_annees) VALUES
    -- Documents achats
    ('FACT_FOUR', 'Facture fournisseur', 'ENTRANT', 'ACHAT', 'DEBIT', 10),
    ('AVOIR_FOUR', 'Avoir fournisseur', 'ENTRANT', 'ACHAT', 'CREDIT', 10),
    ('BC', 'Bon de commande', 'SORTANT', 'ACHAT', 'NEUTRE', 5),
    ('BL', 'Bon de livraison', 'ENTRANT', 'ACHAT', 'NEUTRE', 5),
    -- Documents ventes
    ('FACT_CLI', 'Facture client', 'SORTANT', 'VENTE', 'CREDIT', 10),
    ('AVOIR_CLI', 'Avoir client', 'SORTANT', 'VENTE', 'DEBIT', 10),
    ('DEVIS', 'Devis', 'SORTANT', 'VENTE', 'NEUTRE', 3),
    -- Documents bancaires
    ('RELEVE', 'Relevé bancaire', 'ENTRANT', 'BANQUE', 'NEUTRE', 10),
    ('AVIS_DEBIT', 'Avis de débit', 'ENTRANT', 'BANQUE', 'DEBIT', 10),
    ('AVIS_CREDIT', 'Avis de crédit', 'ENTRANT', 'BANQUE', 'CREDIT', 10),
    ('RIB', 'Relevé d''identité bancaire', 'INTERNE', 'BANQUE', 'NEUTRE', 0),
    -- Documents fiscaux
    ('DEB', 'Déclaration d''échange de biens', 'SORTANT', 'FISCAL', 'NEUTRE', 10),
    ('TVA', 'Déclaration TVA', 'SORTANT', 'FISCAL', 'NEUTRE', 10)
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- dim_statut_document : Statuts workflow documents (SCD Type 1)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Workflow de traitement des documents financiers.
-- Permet le suivi et l'audit des validations.
-- GRAIN: Une ligne par statut possible
-- HISTORISATION: SCD Type 1
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_statut_document (
    statut_document_id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    -- Workflow
    ordre INT NOT NULL,                        -- Ordre dans le workflow
    est_initial BOOLEAN DEFAULT FALSE,         -- Premier statut possible
    est_final BOOLEAN DEFAULT FALSE,           -- Statut terminal
    est_bloquant BOOLEAN DEFAULT FALSE,        -- Bloque les actions suivantes
    -- Actions
    permet_modification BOOLEAN DEFAULT TRUE,
    permet_paiement BOOLEAN DEFAULT FALSE,
    -- Alertes
    delai_alerte_jours INT,                    -- Alerte si reste X jours dans ce statut
    couleur VARCHAR(7) DEFAULT '#808080',      -- Code couleur UI
    actif BOOLEAN DEFAULT TRUE
);

COMMENT ON TABLE dwh.dim_statut_document IS 'Dimension statuts workflow - SCD Type 1';

INSERT INTO dwh.dim_statut_document (code, nom, ordre, est_initial, est_final, permet_modification, permet_paiement, couleur) VALUES
    ('BROUILLON', 'Brouillon', 10, TRUE, FALSE, TRUE, FALSE, '#9CA3AF'),
    ('EN_ATTENTE', 'En attente validation', 20, FALSE, FALSE, FALSE, FALSE, '#F59E0B'),
    ('A_COMPLETER', 'À compléter', 25, FALSE, FALSE, TRUE, FALSE, '#EF4444'),
    ('VALIDE', 'Validé', 30, FALSE, FALSE, FALSE, TRUE, '#10B981'),
    ('A_PAYER', 'À payer', 40, FALSE, FALSE, FALSE, TRUE, '#3B82F6'),
    ('PAYE_PARTIEL', 'Partiellement payé', 50, FALSE, FALSE, FALSE, TRUE, '#8B5CF6'),
    ('PAYE', 'Payé', 60, FALSE, TRUE, FALSE, FALSE, '#059669'),
    ('RAPPROCHE', 'Rapproché', 70, FALSE, TRUE, FALSE, FALSE, '#047857'),
    ('ANNULE', 'Annulé', 99, FALSE, TRUE, FALSE, FALSE, '#DC2626'),
    ('LITIGE', 'En litige', 80, FALSE, FALSE, FALSE, FALSE, '#B91C1C')
ON CONFLICT (code) DO NOTHING;

-- ----------------------------------------------------------------------------
-- dim_compte_bancaire : Comptes bancaires (SCD Type 2)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Comptes bancaires de l'entreprise pour gestion trésorerie.
-- Historisation complète car les conditions peuvent évoluer.
-- GRAIN: Une ligne par version de compte
-- HISTORISATION: SCD Type 2 (date_debut/date_fin, est_actuel)
-- RELATIONS: Plusieurs comptes par tenant, un compte = une devise
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_compte_bancaire (
    compte_sk SERIAL PRIMARY KEY,              -- Surrogate key (technique)
    compte_id INT NOT NULL,                    -- Business key (métier)
    tenant_id INT NOT NULL,
    -- Identification
    code_interne VARCHAR(20) NOT NULL,         -- Code court interne (BNP1, SG1)
    libelle VARCHAR(200) NOT NULL,             -- Nom complet
    banque VARCHAR(100) NOT NULL,              -- Nom établissement
    -- Coordonnées bancaires
    iban VARCHAR(34),                          -- IBAN complet
    bic VARCHAR(11),                           -- Code SWIFT/BIC
    rib_banque VARCHAR(5),                     -- Code banque RIB
    rib_guichet VARCHAR(5),                    -- Code guichet RIB
    rib_compte VARCHAR(11),                    -- Numéro compte RIB
    rib_cle VARCHAR(2),                        -- Clé RIB
    -- Configuration
    devise_id INT REFERENCES dwh.dim_devise(devise_id),
    type_compte VARCHAR(30) NOT NULL,          -- COURANT, EPARGNE, TITRE, DEVISES
    est_compte_principal BOOLEAN DEFAULT FALSE,
    -- Conditions
    plafond_decouvert NUMERIC(14,2),
    taux_decouvert_pct NUMERIC(5,4),
    frais_tenue_compte NUMERIC(10,2),
    -- SCD Type 2
    date_debut DATE NOT NULL DEFAULT CURRENT_DATE,
    date_fin DATE DEFAULT '9999-12-31',
    est_actuel BOOLEAN DEFAULT TRUE,
    -- Métadonnées
    source VARCHAR(50),                        -- Source de l'import
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.dim_compte_bancaire IS 'Dimension comptes bancaires - SCD Type 2 - Historisation conditions';
COMMENT ON COLUMN dwh.dim_compte_bancaire.compte_sk IS 'Surrogate key technique - utilisée dans les faits';
COMMENT ON COLUMN dwh.dim_compte_bancaire.compte_id IS 'Business key métier - stable dans le temps';

CREATE INDEX IF NOT EXISTS idx_dim_compte_actuel ON dwh.dim_compte_bancaire(tenant_id, est_actuel) WHERE est_actuel = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_compte_iban ON dwh.dim_compte_bancaire(iban) WHERE iban IS NOT NULL;

-- ----------------------------------------------------------------------------
-- dim_exercice_comptable : Périodes comptables (SCD Type 1)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Exercices comptables pour agrégation et clôture.
-- GRAIN: Une ligne par exercice
-- HISTORISATION: SCD Type 1
-- HIÉRARCHIE: Exercice > Trimestre > Mois
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.dim_exercice_comptable (
    exercice_id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,
    code VARCHAR(20) NOT NULL,                 -- 2024, 2024-S1
    libelle VARCHAR(100),
    date_debut DATE NOT NULL,
    date_fin DATE NOT NULL,
    -- Statut
    statut VARCHAR(20) DEFAULT 'OUVERT' CHECK (statut IN ('OUVERT', 'CLOTURE_PROVISOIRE', 'CLOTURE')),
    date_cloture DATE,
    cloture_par INT,                           -- user_id
    -- Paramètres
    devise_id INT REFERENCES dwh.dim_devise(devise_id),
    -- Contrôle
    UNIQUE(tenant_id, code),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.dim_exercice_comptable IS 'Dimension exercices comptables - SCD Type 1';

-- ----------------------------------------------------------------------------
-- dim_tiers : Extension fournisseurs pour multi-rôle (SCD Type 2)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Entités externes (fournisseurs, clients, banques).
-- Extension de dim_fournisseur pour usage finance.
-- GRAIN: Une ligne par version de tiers
-- HISTORISATION: SCD Type 2
-- ÉVOLUTION FUTURE: Fusion possible avec dim_fournisseur
-- ----------------------------------------------------------------------------

-- Utilisation de dim_fournisseur existant - ajout colonnes si nécessaires
ALTER TABLE dwh.dim_fournisseur
ADD COLUMN IF NOT EXISTS type_tiers VARCHAR(20) DEFAULT 'FOURNISSEUR',
ADD COLUMN IF NOT EXISTS iban VARCHAR(34),
ADD COLUMN IF NOT EXISTS bic VARCHAR(11),
ADD COLUMN IF NOT EXISTS delai_paiement_jours INT DEFAULT 30,
ADD COLUMN IF NOT EXISTS mode_paiement_defaut_id INT,
ADD COLUMN IF NOT EXISTS compte_comptable VARCHAR(20),
ADD COLUMN IF NOT EXISTS plafond_encours NUMERIC(14,2),
ADD COLUMN IF NOT EXISTS score_risque INT CHECK (score_risque BETWEEN 1 AND 5);

COMMENT ON COLUMN dwh.dim_fournisseur.type_tiers IS 'FOURNISSEUR, CLIENT, BANQUE, AUTRE';
COMMENT ON COLUMN dwh.dim_fournisseur.score_risque IS 'Score risque crédit 1(faible) à 5(élevé)';


-- ============================================================================
-- SECTION 3: TABLES DE FAITS DWH - FINANCE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- fait_factures : Factures fournisseurs et clients
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Fait central de la gestion financière. Chaque facture
-- représente une obligation de paiement (fournisseur) ou créance (client).
--
-- GRAIN: Une ligne par LIGNE de facture (permet analyse par produit/service)
-- Alternative: Une ligne par facture si agrégation suffisante
--
-- HISTORISATION: Insert-only avec statut. Pas de modification du fait,
-- les changements sont tracés via fait_historique_statut.
--
-- RELATIONS MULTIPLES:
-- - dim_temps (date_facture, date_echeance, date_comptable)
-- - dim_fournisseur (émetteur ou destinataire selon sens)
-- - dim_compte_bancaire (compte de règlement prévu)
-- - dim_cost_center (imputation analytique)
--
-- DONNÉES MANQUANTES:
-- - Catégorie inconnue → categorie_depense_id = NULL + flag a_categoriser
-- - Montant illisible → montant_ht = NULL + statut = 'A_COMPLETER'
-- - Fournisseur nouveau → fournisseur_sk vers 'INCONNU' + a_identifier = TRUE
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_factures (
    facture_sk BIGSERIAL PRIMARY KEY,
    -- Clés métier
    facture_id VARCHAR(50) NOT NULL,           -- Numéro facture fournisseur
    facture_interne_id SERIAL,                 -- Numéro interne séquentiel
    tenant_id INT NOT NULL,

    -- Dimensions temporelles (relations multiples)
    date_facture_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    date_echeance_id INT REFERENCES dwh.dim_temps(date_id),
    date_reception_id INT REFERENCES dwh.dim_temps(date_id),
    date_comptable_id INT REFERENCES dwh.dim_temps(date_id),

    -- Dimensions entités
    type_document_id INT NOT NULL REFERENCES dwh.dim_type_document(type_document_id),
    fournisseur_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),
    compte_bancaire_sk INT REFERENCES dwh.dim_compte_bancaire(compte_sk),
    cost_center_id INT REFERENCES dwh.dim_cost_center(cost_center_id),
    categorie_depense_id INT REFERENCES dwh.dim_categorie_depense(categorie_depense_id),
    exercice_id INT REFERENCES dwh.dim_exercice_comptable(exercice_id),
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),

    -- Statut workflow
    statut_id INT NOT NULL REFERENCES dwh.dim_statut_document(statut_document_id),

    -- Mesures financières
    montant_ht NUMERIC(14,2),                  -- Hors taxes
    montant_tva NUMERIC(14,2),                 -- TVA
    montant_ttc NUMERIC(14,2) NOT NULL,        -- TTC (obligatoire)
    taux_tva_pct NUMERIC(5,2),                 -- Taux TVA appliqué

    -- Si multi-devises
    montant_devise NUMERIC(14,2),              -- Montant en devise origine
    taux_change NUMERIC(12,6),                 -- Taux de conversion

    -- Paiement
    montant_paye NUMERIC(14,2) DEFAULT 0,
    reste_a_payer NUMERIC(14,2) GENERATED ALWAYS AS (montant_ttc - COALESCE(montant_paye, 0)) STORED,
    mode_paiement_id INT REFERENCES dwh.dim_mode_paiement(mode_paiement_id),

    -- Gestion des données manquantes
    a_categoriser BOOLEAN DEFAULT FALSE,       -- Catégorie à identifier
    a_identifier_tiers BOOLEAN DEFAULT FALSE,  -- Fournisseur à identifier
    donnees_incompletes BOOLEAN DEFAULT FALSE, -- Données partiellement extraites
    note_extraction TEXT,                      -- Notes sur problèmes extraction
    score_confiance INT CHECK (score_confiance BETWEEN 0 AND 100), -- Confiance OCR

    -- Traçabilité
    ref_commande VARCHAR(50),                  -- Référence BC si existe
    ref_livraison VARCHAR(50),                 -- Référence BL si existe
    commentaire TEXT,

    -- Document source
    document_source_path TEXT,                 -- Chemin fichier PDF
    document_hash VARCHAR(64),                 -- SHA256 pour dédup

    -- Métadonnées
    source VARCHAR(50),                        -- METRO, TAIYAT, EUROCIEL, MANUEL
    lot_import_id UUID,                        -- ID du lot d'import
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INT,
    validated_by INT,
    validated_at TIMESTAMPTZ,

    -- Contraintes
    UNIQUE(tenant_id, source, facture_id)
);

COMMENT ON TABLE dwh.fait_factures IS 'Table de faits factures - GRAIN: une ligne par facture';
COMMENT ON COLUMN dwh.fait_factures.score_confiance IS 'Score confiance extraction OCR 0-100';
COMMENT ON COLUMN dwh.fait_factures.a_categoriser IS 'TRUE si catégorie à déterminer manuellement';

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_fait_factures_date ON dwh.fait_factures(date_facture_id);
CREATE INDEX IF NOT EXISTS idx_fait_factures_fournisseur ON dwh.fait_factures(fournisseur_sk);
CREATE INDEX IF NOT EXISTS idx_fait_factures_statut ON dwh.fait_factures(statut_id);
CREATE INDEX IF NOT EXISTS idx_fait_factures_a_traiter ON dwh.fait_factures(tenant_id, statut_id)
    WHERE statut_id IN (SELECT statut_document_id FROM dwh.dim_statut_document WHERE code IN ('EN_ATTENTE', 'A_COMPLETER'));
CREATE INDEX IF NOT EXISTS idx_fait_factures_echeance ON dwh.fait_factures(date_echeance_id, reste_a_payer)
    WHERE reste_a_payer > 0;
CREATE INDEX IF NOT EXISTS idx_fait_factures_hash ON dwh.fait_factures(document_hash);

-- ----------------------------------------------------------------------------
-- fait_lignes_factures : Détail lignes factures (si grain ligne nécessaire)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Détail des lignes pour analyse fine par produit/service.
-- Optionnel si analyse par facture suffisante.
--
-- GRAIN: Une ligne par ligne de facture
-- RELATIONS: N lignes pour 1 fait_factures
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_lignes_factures (
    ligne_sk BIGSERIAL PRIMARY KEY,
    facture_sk BIGINT NOT NULL REFERENCES dwh.fait_factures(facture_sk),
    tenant_id INT NOT NULL,

    -- Position
    numero_ligne INT NOT NULL,

    -- Description
    reference_article VARCHAR(50),             -- Code article fournisseur
    designation TEXT NOT NULL,

    -- Quantités
    quantite NUMERIC(12,3),
    unite VARCHAR(20),                         -- KG, L, PCE, etc.

    -- Prix
    prix_unitaire_ht NUMERIC(14,4),
    remise_pct NUMERIC(5,2) DEFAULT 0,
    montant_ligne_ht NUMERIC(14,2),
    taux_tva_pct NUMERIC(5,2),
    montant_tva NUMERIC(14,2),
    montant_ligne_ttc NUMERIC(14,2),

    -- Classification
    categorie_depense_id INT REFERENCES dwh.dim_categorie_depense(categorie_depense_id),
    produit_sk INT REFERENCES dwh.dim_produit(produit_sk), -- Lien catalogue si identifié

    -- Qualité données
    confiance_extraction INT CHECK (confiance_extraction BETWEEN 0 AND 100),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(facture_sk, numero_ligne)
);

COMMENT ON TABLE dwh.fait_lignes_factures IS 'Détail lignes factures - GRAIN: une ligne par ligne facture';

CREATE INDEX IF NOT EXISTS idx_fait_lignes_facture ON dwh.fait_lignes_factures(facture_sk);

-- ----------------------------------------------------------------------------
-- fait_paiements : Paiements émis et reçus
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Flux de trésorerie réels. Chaque paiement impacte la trésorerie
-- et doit être rapproché avec les factures et relevés bancaires.
--
-- GRAIN: Une ligne par paiement unitaire
--
-- HISTORISATION: Insert-only. Modifications via fait_historique_statut.
--
-- RELATIONS:
-- - 1 paiement peut solder plusieurs factures (relation N-N via fait_affectation_paiement)
-- - 1 facture peut avoir plusieurs paiements partiels
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_paiements (
    paiement_sk BIGSERIAL PRIMARY KEY,
    paiement_id VARCHAR(50),                   -- Référence unique
    tenant_id INT NOT NULL,

    -- Dimensions temporelles
    date_paiement_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    date_valeur_id INT REFERENCES dwh.dim_temps(date_id),        -- Date valeur bancaire
    date_comptable_id INT REFERENCES dwh.dim_temps(date_id),

    -- Sens du flux
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('ENTRANT', 'SORTANT')),

    -- Dimensions entités
    compte_bancaire_sk INT NOT NULL REFERENCES dwh.dim_compte_bancaire(compte_sk),
    mode_paiement_id INT NOT NULL REFERENCES dwh.dim_mode_paiement(mode_paiement_id),
    tiers_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk), -- Fournisseur ou client
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),
    exercice_id INT REFERENCES dwh.dim_exercice_comptable(exercice_id),

    -- Statut
    statut VARCHAR(20) DEFAULT 'VALIDE' CHECK (statut IN ('BROUILLON', 'VALIDE', 'RAPPROCHE', 'ANNULE')),

    -- Montants
    montant NUMERIC(14,2) NOT NULL,
    montant_devise NUMERIC(14,2),
    taux_change NUMERIC(12,6),
    frais_bancaires NUMERIC(10,2) DEFAULT 0,

    -- Informations paiement
    reference_bancaire VARCHAR(50),            -- Référence retournée par banque
    libelle VARCHAR(500),                      -- Libellé mouvement
    motif TEXT,                                -- Motif détaillé

    -- Rapprochement
    est_rapproche BOOLEAN DEFAULT FALSE,
    mouvement_bancaire_id BIGINT,              -- Lien relevé bancaire
    date_rapprochement TIMESTAMPTZ,

    -- Métadonnées
    source VARCHAR(50),
    lot_import_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INT
);

COMMENT ON TABLE dwh.fait_paiements IS 'Table de faits paiements - GRAIN: un paiement unitaire';
COMMENT ON COLUMN dwh.fait_paiements.sens IS 'ENTRANT=encaissement, SORTANT=décaissement';

CREATE INDEX IF NOT EXISTS idx_fait_paiements_date ON dwh.fait_paiements(date_paiement_id);
CREATE INDEX IF NOT EXISTS idx_fait_paiements_compte ON dwh.fait_paiements(compte_bancaire_sk);
CREATE INDEX IF NOT EXISTS idx_fait_paiements_tiers ON dwh.fait_paiements(tiers_sk);
CREATE INDEX IF NOT EXISTS idx_fait_paiements_non_rapproche ON dwh.fait_paiements(tenant_id, compte_bancaire_sk)
    WHERE est_rapproche = FALSE;

-- ----------------------------------------------------------------------------
-- fait_affectation_paiement : Lien paiement-facture (table de liaison)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Permet l'affectation d'un paiement à plusieurs factures
-- et le suivi des règlements partiels.
--
-- GRAIN: Une ligne par affectation paiement-facture
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_affectation_paiement (
    affectation_sk BIGSERIAL PRIMARY KEY,
    paiement_sk BIGINT NOT NULL REFERENCES dwh.fait_paiements(paiement_sk),
    facture_sk BIGINT NOT NULL REFERENCES dwh.fait_factures(facture_sk),
    tenant_id INT NOT NULL,

    -- Montant affecté
    montant_affecte NUMERIC(14,2) NOT NULL,

    -- Dates
    date_affectation_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),

    -- Métadonnées
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INT,

    UNIQUE(paiement_sk, facture_sk)
);

COMMENT ON TABLE dwh.fait_affectation_paiement IS 'Liaison paiements-factures - GRAIN: une affectation';

-- ----------------------------------------------------------------------------
-- fait_mouvements_bancaires : Relevés bancaires
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Mouvements des relevés bancaires pour rapprochement.
-- Source de vérité pour la position de trésorerie réelle.
--
-- GRAIN: Une ligne par mouvement (ligne de relevé)
--
-- HISTORISATION: Insert-only. Données source bancaire non modifiables.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_mouvements_bancaires (
    mouvement_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Identification
    compte_bancaire_sk INT NOT NULL REFERENCES dwh.dim_compte_bancaire(compte_sk),
    reference_mouvement VARCHAR(100),          -- Référence unique bancaire

    -- Dates
    date_operation_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    date_valeur_id INT REFERENCES dwh.dim_temps(date_id),
    date_comptable_id INT REFERENCES dwh.dim_temps(date_id),

    -- Mouvement
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('DEBIT', 'CREDIT')),
    montant NUMERIC(14,2) NOT NULL,            -- Toujours positif
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),

    -- Libellé et classification
    libelle_banque VARCHAR(500),               -- Libellé brut bancaire
    libelle_normalise VARCHAR(500),            -- Libellé nettoyé
    code_operation VARCHAR(20),                -- Code opération bancaire
    mode_paiement_id INT REFERENCES dwh.dim_mode_paiement(mode_paiement_id),

    -- Rapprochement
    est_rapproche BOOLEAN DEFAULT FALSE,
    paiement_sk BIGINT REFERENCES dwh.fait_paiements(paiement_sk),
    date_rapprochement TIMESTAMPTZ,
    rapproche_par INT,

    -- Soldes (calculés lors de l'import)
    solde_avant NUMERIC(14,2),
    solde_apres NUMERIC(14,2),

    -- Import
    source_releve VARCHAR(50),                 -- BNP, SG, etc.
    fichier_source VARCHAR(500),
    ligne_fichier INT,
    lot_import_id UUID,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, compte_bancaire_sk, reference_mouvement)
);

COMMENT ON TABLE dwh.fait_mouvements_bancaires IS 'Mouvements relevés bancaires - GRAIN: une ligne de relevé';

CREATE INDEX IF NOT EXISTS idx_fait_mvt_bancaire_date ON dwh.fait_mouvements_bancaires(date_operation_id);
CREATE INDEX IF NOT EXISTS idx_fait_mvt_bancaire_compte ON dwh.fait_mouvements_bancaires(compte_bancaire_sk);
CREATE INDEX IF NOT EXISTS idx_fait_mvt_bancaire_rapprochement ON dwh.fait_mouvements_bancaires(tenant_id, compte_bancaire_sk)
    WHERE est_rapproche = FALSE;

-- ----------------------------------------------------------------------------
-- fait_tresorerie : Position trésorerie quotidienne (snapshot)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Photo quotidienne de la position de trésorerie par compte.
-- Permet analyse historique et prévisionnel.
--
-- GRAIN: Une ligne par compte par jour
--
-- HISTORISATION: Insert quotidien via ETL. Pas de modification.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_tresorerie (
    tresorerie_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Dimensions
    date_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),
    compte_bancaire_sk INT NOT NULL REFERENCES dwh.dim_compte_bancaire(compte_sk),
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),

    -- Soldes
    solde_debut_journee NUMERIC(14,2) NOT NULL,
    solde_fin_journee NUMERIC(14,2) NOT NULL,

    -- Mouvements du jour
    total_debits NUMERIC(14,2) DEFAULT 0,
    total_credits NUMERIC(14,2) DEFAULT 0,
    nb_operations INT DEFAULT 0,

    -- Indicateurs
    en_decouvert BOOLEAN GENERATED ALWAYS AS (solde_fin_journee < 0) STORED,
    variation_jour NUMERIC(14,2) GENERATED ALWAYS AS (solde_fin_journee - solde_debut_journee) STORED,

    -- Prévisionnel (calculé via ETL)
    solde_previsionnel_j7 NUMERIC(14,2),       -- Projection à 7 jours
    solde_previsionnel_j30 NUMERIC(14,2),      -- Projection à 30 jours
    encaissements_prevus_j7 NUMERIC(14,2),
    decaissements_prevus_j7 NUMERIC(14,2),

    -- Métadonnées
    source VARCHAR(20) DEFAULT 'CALCUL',       -- CALCUL, RELEVE, SAISIE
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, date_id, compte_bancaire_sk)
);

COMMENT ON TABLE dwh.fait_tresorerie IS 'Position trésorerie quotidienne - GRAIN: compte/jour';

CREATE INDEX IF NOT EXISTS idx_fait_tresorerie_date ON dwh.fait_tresorerie(date_id);
CREATE INDEX IF NOT EXISTS idx_fait_tresorerie_compte ON dwh.fait_tresorerie(compte_bancaire_sk);
CREATE INDEX IF NOT EXISTS idx_fait_tresorerie_decouvert ON dwh.fait_tresorerie(tenant_id, date_id) WHERE en_decouvert = TRUE;

-- ----------------------------------------------------------------------------
-- fait_budget : Suivi budgétaire
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Budget prévisionnel vs réalisé par centre de coût et période.
--
-- GRAIN: Une ligne par centre de coût par mois
--
-- HISTORISATION: Update du réalisé, version du budget initial conservée
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_budget (
    budget_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Dimensions
    exercice_id INT NOT NULL REFERENCES dwh.dim_exercice_comptable(exercice_id),
    cost_center_id INT NOT NULL REFERENCES dwh.dim_cost_center(cost_center_id),
    categorie_depense_id INT REFERENCES dwh.dim_categorie_depense(categorie_depense_id),
    mois INT NOT NULL CHECK (mois BETWEEN 1 AND 12),
    annee INT NOT NULL,

    -- Budget initial (figé à validation)
    budget_initial NUMERIC(14,2) NOT NULL,
    date_validation_budget DATE,

    -- Budget révisé (ajustements en cours d'année)
    budget_revise NUMERIC(14,2),
    motif_revision TEXT,
    date_revision TIMESTAMPTZ,

    -- Réalisé (mis à jour par ETL)
    realise NUMERIC(14,2) DEFAULT 0,
    date_dernier_calcul TIMESTAMPTZ,

    -- Écarts calculés
    ecart_initial NUMERIC(14,2) GENERATED ALWAYS AS (COALESCE(budget_initial, 0) - COALESCE(realise, 0)) STORED,
    ecart_revise NUMERIC(14,2) GENERATED ALWAYS AS (COALESCE(budget_revise, budget_initial, 0) - COALESCE(realise, 0)) STORED,
    taux_consommation_pct NUMERIC(7,2) GENERATED ALWAYS AS (
        CASE WHEN COALESCE(budget_initial, 0) > 0
        THEN (COALESCE(realise, 0) / budget_initial * 100)
        ELSE 0 END
    ) STORED,

    -- Métadonnées
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, exercice_id, cost_center_id, COALESCE(categorie_depense_id, 0), mois)
);

COMMENT ON TABLE dwh.fait_budget IS 'Suivi budgétaire - GRAIN: centre de coût/mois';

CREATE INDEX IF NOT EXISTS idx_fait_budget_periode ON dwh.fait_budget(annee, mois);
CREATE INDEX IF NOT EXISTS idx_fait_budget_cc ON dwh.fait_budget(cost_center_id);

-- ----------------------------------------------------------------------------
-- fait_echeances : Échéancier paiements
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Vue prévisionnelle des flux de trésorerie basée sur les
-- factures à payer/encaisser et leurs échéances.
--
-- GRAIN: Une ligne par échéance
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_echeances (
    echeance_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Source
    facture_sk BIGINT REFERENCES dwh.fait_factures(facture_sk),

    -- Dates
    date_echeance_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),

    -- Sens
    sens VARCHAR(10) NOT NULL CHECK (sens IN ('ENTRANT', 'SORTANT')),

    -- Montants
    montant_initial NUMERIC(14,2) NOT NULL,    -- Montant à l'origine
    montant_restant NUMERIC(14,2) NOT NULL,    -- Reste à payer
    devise_id INT NOT NULL REFERENCES dwh.dim_devise(devise_id),

    -- Statut
    statut VARCHAR(20) DEFAULT 'A_VENIR' CHECK (statut IN ('A_VENIR', 'ECHUE', 'PAYEE', 'ANNULEE')),
    jours_retard INT GENERATED ALWAYS AS (
        CASE WHEN statut IN ('A_VENIR', 'ECHUE')
        THEN GREATEST(0, CURRENT_DATE - (SELECT date_complete FROM dwh.dim_temps WHERE date_id = date_echeance_id))
        ELSE 0 END
    ) STORED,

    -- Tiers
    tiers_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),

    -- Métadonnées
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.fait_echeances IS 'Échéancier prévisionnel - GRAIN: une échéance';

CREATE INDEX IF NOT EXISTS idx_fait_echeances_date ON dwh.fait_echeances(date_echeance_id);
CREATE INDEX IF NOT EXISTS idx_fait_echeances_statut ON dwh.fait_echeances(statut) WHERE statut IN ('A_VENIR', 'ECHUE');

-- ----------------------------------------------------------------------------
-- fait_historique_statut : Audit trail des changements de statut
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Traçabilité complète des changements de statut pour audit
-- et analyse des délais de traitement.
--
-- GRAIN: Une ligne par changement de statut
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dwh.fait_historique_statut (
    historique_sk BIGSERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Entité concernée
    entite_type VARCHAR(20) NOT NULL,          -- FACTURE, PAIEMENT, etc.
    entite_sk BIGINT NOT NULL,                 -- SK de l'entité

    -- Changement
    statut_precedent_id INT REFERENCES dwh.dim_statut_document(statut_document_id),
    statut_nouveau_id INT NOT NULL REFERENCES dwh.dim_statut_document(statut_document_id),
    date_changement_id INT NOT NULL REFERENCES dwh.dim_temps(date_id),

    -- Contexte
    motif TEXT,
    commentaire TEXT,

    -- Utilisateur
    user_id INT,
    user_email VARCHAR(255),

    -- Métadonnées
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE dwh.fait_historique_statut IS 'Audit trail statuts - GRAIN: un changement';

CREATE INDEX IF NOT EXISTS idx_fait_historique_entite ON dwh.fait_historique_statut(entite_type, entite_sk);
CREATE INDEX IF NOT EXISTS idx_fait_historique_date ON dwh.fait_historique_statut(date_changement_id);


-- ============================================================================
-- SECTION 4: COUCHE ODS - OPERATIONAL DATA STORE
-- ============================================================================
-- SENS MÉTIER: Données validées pour usage opérationnel/tactique.
-- Mise à jour fréquente (plusieurs fois/jour), rétention courte (3 mois).
-- Source pour les data marts opérationnels et décisions tactiques.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ods.factures_en_cours : Factures en traitement (non closes)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Vue opérationnelle des factures actives pour équipe comptable.
-- Exclut les factures payées/rapprochées de plus de 30 jours.
-- REFRESH: Temps réel via triggers ou toutes les heures.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ods.factures_en_cours (
    facture_sk BIGINT PRIMARY KEY,
    facture_id VARCHAR(50) NOT NULL,
    tenant_id INT NOT NULL,

    -- Données dénormalisées pour performance
    fournisseur_nom VARCHAR(200),
    fournisseur_code VARCHAR(50),

    -- Dates clés
    date_facture DATE NOT NULL,
    date_echeance DATE,
    jours_avant_echeance INT,
    est_echue BOOLEAN,

    -- Montants
    montant_ttc NUMERIC(14,2) NOT NULL,
    montant_paye NUMERIC(14,2) DEFAULT 0,
    reste_a_payer NUMERIC(14,2),
    devise VARCHAR(3),

    -- Statut
    statut_code VARCHAR(20) NOT NULL,
    statut_nom VARCHAR(100),
    statut_couleur VARCHAR(7),

    -- Classification
    cost_center_nom VARCHAR(100),
    categorie_nom VARCHAR(100),

    -- Alertes
    priorite INT DEFAULT 5,                    -- 1=urgente, 5=normale
    alerte_texte VARCHAR(200),

    -- Actions requises
    require_validation BOOLEAN DEFAULT FALSE,
    require_categorisation BOOLEAN DEFAULT FALSE,
    require_completion BOOLEAN DEFAULT FALSE,

    -- Métadonnées
    source VARCHAR(50),
    last_sync TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ods.factures_en_cours IS 'ODS - Factures actives pour gestion opérationnelle';

CREATE INDEX IF NOT EXISTS idx_ods_factures_tenant ON ods.factures_en_cours(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ods_factures_statut ON ods.factures_en_cours(statut_code);
CREATE INDEX IF NOT EXISTS idx_ods_factures_echeance ON ods.factures_en_cours(date_echeance) WHERE reste_a_payer > 0;
CREATE INDEX IF NOT EXISTS idx_ods_factures_priorite ON ods.factures_en_cours(tenant_id, priorite);

-- ----------------------------------------------------------------------------
-- ods.tresorerie_temps_reel : Position trésorerie courante
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Position de trésorerie en quasi temps réel pour pilotage.
-- REFRESH: Toutes les 15 minutes ou à chaque mouvement.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ods.tresorerie_temps_reel (
    compte_sk INT PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Identification compte
    code_compte VARCHAR(20) NOT NULL,
    libelle_compte VARCHAR(200) NOT NULL,
    banque VARCHAR(100),
    iban VARCHAR(34),
    devise VARCHAR(3) NOT NULL,

    -- Soldes
    solde_comptable NUMERIC(14,2) NOT NULL,    -- Solde après toutes écritures
    solde_valeur NUMERIC(14,2),                -- Solde en date de valeur
    solde_disponible NUMERIC(14,2),            -- Solde utilisable (- engagements)

    -- Plafonds
    plafond_decouvert NUMERIC(14,2),
    marge_disponible NUMERIC(14,2),            -- Avant découvert max

    -- Mouvements du jour
    debits_jour NUMERIC(14,2) DEFAULT 0,
    credits_jour NUMERIC(14,2) DEFAULT 0,
    nb_operations_jour INT DEFAULT 0,

    -- Prévisionnel court terme
    decaissements_prevus_j7 NUMERIC(14,2) DEFAULT 0,
    encaissements_prevus_j7 NUMERIC(14,2) DEFAULT 0,
    solde_previsionnel_j7 NUMERIC(14,2),

    -- Alertes
    est_en_alerte BOOLEAN DEFAULT FALSE,
    type_alerte VARCHAR(50),                   -- DECOUVERT, SEUIL_BAS, etc.

    -- Sync
    dernier_releve DATE,
    derniere_maj TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ods.tresorerie_temps_reel IS 'ODS - Position trésorerie temps réel';

CREATE INDEX IF NOT EXISTS idx_ods_treso_tenant ON ods.tresorerie_temps_reel(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ods_treso_alerte ON ods.tresorerie_temps_reel(est_en_alerte) WHERE est_en_alerte = TRUE;

-- ----------------------------------------------------------------------------
-- ods.echeancier_7j : Échéances à 7 jours
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Vue opérationnelle des échéances court terme.
-- REFRESH: Quotidien ou à chaque nouveau paiement/facture.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ods.echeancier_7j (
    echeance_sk BIGINT PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Source
    type_source VARCHAR(20),                   -- FACTURE, ABONNEMENT, SALAIRE
    source_ref VARCHAR(100),

    -- Date et montant
    date_echeance DATE NOT NULL,
    jours_restants INT,
    sens VARCHAR(10) NOT NULL,                 -- ENTRANT, SORTANT
    montant NUMERIC(14,2) NOT NULL,
    devise VARCHAR(3) NOT NULL,

    -- Tiers
    tiers_nom VARCHAR(200),
    tiers_code VARCHAR(50),

    -- Compte cible
    compte_code VARCHAR(20),
    compte_libelle VARCHAR(200),

    -- Classification
    categorie VARCHAR(100),

    -- Statut
    est_confirme BOOLEAN DEFAULT TRUE,         -- FALSE si prévisionnel
    peut_reporter BOOLEAN DEFAULT FALSE,

    last_sync TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ods.echeancier_7j IS 'ODS - Échéancier court terme (7 jours)';

CREATE INDEX IF NOT EXISTS idx_ods_echeancier_date ON ods.echeancier_7j(date_echeance);
CREATE INDEX IF NOT EXISTS idx_ods_echeancier_tenant ON ods.echeancier_7j(tenant_id);


-- ============================================================================
-- SECTION 5: COUCHE STAGING - IMPORT DONNÉES BRUTES
-- ============================================================================
-- SENS MÉTIER: Zone temporaire pour import de données externes non validées.
-- Données brutes conservées pour audit et retraitement.
-- Rétention: 90 jours après traitement.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- staging.import_lots : Métadonnées lots d'import
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.import_lots (
    lot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INT NOT NULL,

    -- Identification
    type_import VARCHAR(50) NOT NULL,          -- FACTURE_PDF, RELEVE_CSV, MANUEL
    source VARCHAR(50) NOT NULL,               -- METRO, TAIYAT, EUROCIEL, BNP, SG

    -- Fichiers
    fichier_origine VARCHAR(500),
    fichier_hash VARCHAR(64),                  -- SHA256 pour dédup
    taille_octets BIGINT,

    -- Traitement
    statut VARCHAR(20) DEFAULT 'EN_COURS' CHECK (statut IN ('EN_COURS', 'TERMINE', 'ERREUR', 'PARTIEL')),
    date_debut TIMESTAMPTZ DEFAULT NOW(),
    date_fin TIMESTAMPTZ,

    -- Résultats
    nb_lignes_source INT,
    nb_lignes_importees INT DEFAULT 0,
    nb_lignes_erreur INT DEFAULT 0,
    nb_lignes_doublon INT DEFAULT 0,

    -- Erreurs
    message_erreur TEXT,

    -- Utilisateur
    importe_par INT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.import_lots IS 'Métadonnées lots d''import - traçabilité complète';

CREATE INDEX IF NOT EXISTS idx_staging_lots_tenant ON staging.import_lots(tenant_id);
CREATE INDEX IF NOT EXISTS idx_staging_lots_statut ON staging.import_lots(statut);

-- ----------------------------------------------------------------------------
-- staging.factures_brutes : Factures extraites (avant validation)
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Données extraites des PDF factures avant nettoyage/validation.
-- Conserve les données brutes même si parsing incomplet.
--
-- TRAITEMENT DONNÉES MANQUANTES:
-- - Champs NULL = non extrait ou illisible
-- - score_confiance par champ (0-100)
-- - Passage en révision manuelle si score < 70
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.factures_brutes (
    stg_facture_id BIGSERIAL PRIMARY KEY,
    lot_id UUID NOT NULL REFERENCES staging.import_lots(lot_id),
    tenant_id INT NOT NULL,

    -- Fichier source
    fichier_source VARCHAR(500) NOT NULL,
    page_numero INT,
    document_hash VARCHAR(64),

    -- Extraction brute - En-tête
    numero_facture_brut VARCHAR(100),          -- Tel qu'extrait
    date_facture_brut VARCHAR(50),             -- Tel qu'extrait
    date_echeance_brut VARCHAR(50),

    -- Extraction brute - Fournisseur
    fournisseur_nom_brut VARCHAR(300),
    fournisseur_adresse_brut TEXT,
    fournisseur_siret_brut VARCHAR(20),
    fournisseur_tva_brut VARCHAR(20),

    -- Extraction brute - Montants
    montant_ht_brut VARCHAR(50),
    montant_tva_brut VARCHAR(50),
    montant_ttc_brut VARCHAR(50),
    devise_brut VARCHAR(10),

    -- Extraction brute - Lignes (JSON array)
    lignes_brutes JSONB,                       -- [{designation, qte, pu, montant}, ...]

    -- Scores confiance extraction (0-100)
    score_numero INT,
    score_date INT,
    score_fournisseur INT,
    score_montants INT,
    score_global INT,

    -- Données normalisées (après parsing)
    numero_facture VARCHAR(50),
    date_facture DATE,
    date_echeance DATE,
    fournisseur_id_match INT,                  -- ID fournisseur si identifié
    montant_ht NUMERIC(14,2),
    montant_tva NUMERIC(14,2),
    montant_ttc NUMERIC(14,2),
    devise VARCHAR(3) DEFAULT 'EUR',

    -- Statut traitement
    statut VARCHAR(20) DEFAULT 'EXTRAIT' CHECK (statut IN (
        'EXTRAIT',                             -- Extraction terminée
        'VALIDE',                              -- Validation OK
        'A_COMPLETER',                         -- Données manquantes
        'A_VERIFIER',                          -- Score faible
        'DOUBLON',                             -- Déjà importé
        'REJETE',                              -- Rejeté manuellement
        'INTEGRE'                              -- Intégré dans DWH
    )),

    -- Erreurs et notes
    erreurs JSONB,                             -- [{champ, erreur, suggestion}, ...]
    notes TEXT,

    -- Traitement manuel
    verifie_par INT,
    verifie_at TIMESTAMPTZ,
    corrections_manuelles JSONB,               -- Historique corrections

    -- Intégration DWH
    facture_sk_integre BIGINT,                 -- FK vers dwh.fait_factures si intégré
    date_integration TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.factures_brutes IS 'Staging factures - données brutes extraction PDF';
COMMENT ON COLUMN staging.factures_brutes.score_global IS 'Score confiance global extraction 0-100';

CREATE INDEX IF NOT EXISTS idx_stg_factures_lot ON staging.factures_brutes(lot_id);
CREATE INDEX IF NOT EXISTS idx_stg_factures_statut ON staging.factures_brutes(statut);
CREATE INDEX IF NOT EXISTS idx_stg_factures_hash ON staging.factures_brutes(document_hash);
CREATE INDEX IF NOT EXISTS idx_stg_factures_a_traiter ON staging.factures_brutes(tenant_id)
    WHERE statut IN ('A_COMPLETER', 'A_VERIFIER');

-- ----------------------------------------------------------------------------
-- staging.factures_lignes_brutes : Lignes factures extraites
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.factures_lignes_brutes (
    stg_ligne_id BIGSERIAL PRIMARY KEY,
    stg_facture_id BIGINT NOT NULL REFERENCES staging.factures_brutes(stg_facture_id),
    tenant_id INT NOT NULL,

    -- Position
    numero_ligne INT NOT NULL,

    -- Extraction brute
    designation_brut TEXT,
    reference_brut VARCHAR(100),
    quantite_brut VARCHAR(50),
    unite_brut VARCHAR(20),
    prix_unitaire_brut VARCHAR(50),
    remise_brut VARCHAR(50),
    montant_brut VARCHAR(50),
    tva_brut VARCHAR(20),

    -- Données normalisées
    designation TEXT,
    reference VARCHAR(50),
    quantite NUMERIC(12,3),
    unite VARCHAR(20),
    prix_unitaire NUMERIC(14,4),
    remise_pct NUMERIC(5,2),
    montant_ht NUMERIC(14,2),
    taux_tva NUMERIC(5,2),

    -- Score confiance
    score_confiance INT,

    -- Classification auto
    categorie_suggeree_id INT,
    produit_suggere_sk INT,
    score_classification INT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.factures_lignes_brutes IS 'Staging lignes factures - extraction détaillée';

CREATE INDEX IF NOT EXISTS idx_stg_lignes_facture ON staging.factures_lignes_brutes(stg_facture_id);

-- ----------------------------------------------------------------------------
-- staging.releves_bruts : Relevés bancaires importés
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Mouvements extraits des relevés bancaires (CSV, PDF).
-- Sources: BNP, SG, CA, etc. avec formats différents.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.releves_bruts (
    stg_releve_id BIGSERIAL PRIMARY KEY,
    lot_id UUID NOT NULL REFERENCES staging.import_lots(lot_id),
    tenant_id INT NOT NULL,

    -- Fichier source
    fichier_source VARCHAR(500) NOT NULL,
    ligne_fichier INT,

    -- Identification compte
    compte_iban_brut VARCHAR(50),
    compte_id_match INT,                       -- ID compte si identifié

    -- Extraction brute
    date_operation_brut VARCHAR(50),
    date_valeur_brut VARCHAR(50),
    libelle_brut VARCHAR(500),
    reference_brut VARCHAR(100),
    debit_brut VARCHAR(50),
    credit_brut VARCHAR(50),
    solde_brut VARCHAR(50),

    -- Données normalisées
    date_operation DATE,
    date_valeur DATE,
    libelle VARCHAR(500),
    reference VARCHAR(100),
    sens VARCHAR(10),                          -- DEBIT, CREDIT
    montant NUMERIC(14,2),
    solde_apres NUMERIC(14,2),
    devise VARCHAR(3) DEFAULT 'EUR',

    -- Classification auto
    mode_paiement_suggere_id INT,
    tiers_suggere_id INT,
    categorie_suggeree_id INT,

    -- Statut
    statut VARCHAR(20) DEFAULT 'EXTRAIT' CHECK (statut IN (
        'EXTRAIT', 'VALIDE', 'DOUBLON', 'REJETE', 'INTEGRE'
    )),

    -- Intégration
    mouvement_sk_integre BIGINT,               -- FK vers dwh.fait_mouvements_bancaires

    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.releves_bruts IS 'Staging relevés bancaires - import multi-format';

CREATE INDEX IF NOT EXISTS idx_stg_releves_lot ON staging.releves_bruts(lot_id);
CREATE INDEX IF NOT EXISTS idx_stg_releves_compte ON staging.releves_bruts(compte_id_match);
CREATE INDEX IF NOT EXISTS idx_stg_releves_statut ON staging.releves_bruts(statut);

-- ----------------------------------------------------------------------------
-- staging.erreurs_import : Journal des erreurs d'import
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Centralisation des erreurs pour analyse et amélioration
-- des processus d'extraction.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.erreurs_import (
    erreur_id BIGSERIAL PRIMARY KEY,
    lot_id UUID REFERENCES staging.import_lots(lot_id),
    tenant_id INT NOT NULL,

    -- Contexte
    type_erreur VARCHAR(50) NOT NULL,          -- PARSING, VALIDATION, DOUBLON, FORMAT
    severite VARCHAR(10) NOT NULL,             -- ERROR, WARNING, INFO

    -- Localisation
    fichier_source VARCHAR(500),
    ligne_numero INT,
    champ VARCHAR(100),

    -- Détails
    valeur_brute TEXT,
    message_erreur TEXT NOT NULL,
    suggestion TEXT,

    -- Résolution
    est_resolu BOOLEAN DEFAULT FALSE,
    resolu_par INT,
    resolu_at TIMESTAMPTZ,
    action_resolution TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.erreurs_import IS 'Journal erreurs import - analyse qualité données';

CREATE INDEX IF NOT EXISTS idx_stg_erreurs_lot ON staging.erreurs_import(lot_id);
CREATE INDEX IF NOT EXISTS idx_stg_erreurs_type ON staging.erreurs_import(type_erreur);
CREATE INDEX IF NOT EXISTS idx_stg_erreurs_non_resolu ON staging.erreurs_import(tenant_id) WHERE est_resolu = FALSE;

-- ----------------------------------------------------------------------------
-- staging.patterns_fournisseurs : Patterns extraction par fournisseur
-- ----------------------------------------------------------------------------
-- SENS MÉTIER: Configuration des règles d'extraction spécifiques à chaque
-- fournisseur (METRO, TAIYAT, EUROCIEL). Permet adaptation aux formats PDF.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.patterns_fournisseurs (
    pattern_id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Identification fournisseur
    fournisseur_code VARCHAR(50) NOT NULL,     -- METRO, TAIYAT, EUROCIEL
    fournisseur_nom VARCHAR(200),
    fournisseur_sk INT REFERENCES dwh.dim_fournisseur(fournisseur_sk),

    -- Patterns d'identification (pour détecter quel format)
    pattern_detection TEXT[],                  -- Textes identifiant ce fournisseur

    -- Configuration extraction (JSON flexible)
    config_extraction JSONB NOT NULL,          -- {
                                               --   numero: {regex: "...", position: "..."},
                                               --   date: {format: "DD/MM/YYYY", zone: "..."},
                                               --   montants: {decimal: ",", zone: "..."},
                                               --   lignes: {debut: "...", fin: "...", colonnes: [...]}
                                               -- }

    -- Mapping champs
    mapping_champs JSONB,                      -- Correspondance champs extraits -> standard

    -- Statistiques
    nb_factures_traitees INT DEFAULT 0,
    score_succes_moyen NUMERIC(5,2),
    derniere_utilisation TIMESTAMPTZ,

    -- Métadonnées
    version INT DEFAULT 1,
    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by INT,

    UNIQUE(tenant_id, fournisseur_code, version)
);

COMMENT ON TABLE staging.patterns_fournisseurs IS 'Configuration extraction par fournisseur';

-- Exemples de configuration (à adapter selon formats réels)
INSERT INTO staging.patterns_fournisseurs (tenant_id, fournisseur_code, fournisseur_nom, pattern_detection, config_extraction)
VALUES
(1, 'METRO', 'METRO Cash & Carry',
 ARRAY['METRO', 'metro.fr', 'METRO CASH'],
 '{
   "format": "PDF",
   "numero_facture": {"zone": "header", "regex": "N°\\s*(\\d{10,})"},
   "date_facture": {"zone": "header", "format": "DD/MM/YYYY", "regex": "Date\\s*:\\s*(\\d{2}/\\d{2}/\\d{4})"},
   "montant_ttc": {"zone": "footer", "regex": "TOTAL TTC\\s*([\\d\\s]+[,.]\\d{2})"},
   "lignes": {"start_marker": "Désignation", "end_marker": "TOTAL", "colonnes": ["ref", "designation", "qte", "pu", "montant"]}
 }'::jsonb),
(1, 'TAIYAT', 'TAIYAT Distribution',
 ARRAY['TAIYAT', 'taiyat.com'],
 '{
   "format": "PDF",
   "numero_facture": {"zone": "header", "regex": "FACTURE\\s+N°\\s*(FA\\d+)"},
   "date_facture": {"zone": "header", "format": "DD-MM-YYYY"},
   "montant_ttc": {"zone": "footer", "regex": "Net à payer\\s*([\\d\\s]+[,.]\\d{2})"},
   "lignes": {"format": "table", "colonnes": ["designation", "qte", "prix", "total"]}
 }'::jsonb),
(1, 'EUROCIEL', 'EUROCIEL',
 ARRAY['EUROCIEL', 'eurociel.fr'],
 '{
   "format": "PDF",
   "numero_facture": {"regex": "(EC\\d{8})"},
   "date_facture": {"format": "YYYY-MM-DD"},
   "montant_ttc": {"position": "bottom-right"},
   "particularites": ["multi-pages", "tableaux-complexes"]
 }'::jsonb)
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- staging.patterns_releves : Patterns extraction relevés bancaires
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.patterns_releves (
    pattern_id SERIAL PRIMARY KEY,
    tenant_id INT NOT NULL,

    -- Identification banque
    banque_code VARCHAR(20) NOT NULL,          -- BNP, SG, CA, BP
    banque_nom VARCHAR(100),

    -- Patterns
    pattern_detection TEXT[],

    -- Configuration
    format_fichier VARCHAR(20),                -- CSV, PDF, OFX, QIF
    config_extraction JSONB NOT NULL,

    -- Mapping colonnes CSV
    mapping_colonnes JSONB,                    -- {0: "date_op", 1: "libelle", 2: "debit", ...}

    -- Parsing
    separateur VARCHAR(5) DEFAULT ';',
    encodage VARCHAR(20) DEFAULT 'UTF-8',
    lignes_entete INT DEFAULT 1,
    format_date VARCHAR(20) DEFAULT 'DD/MM/YYYY',
    format_montant VARCHAR(20) DEFAULT 'FR',   -- FR: 1 234,56 | EN: 1,234.56

    actif BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE staging.patterns_releves IS 'Configuration extraction relevés par banque';


-- ============================================================================
-- SECTION 6: PROCÉDURES ETL
-- ============================================================================
-- Processus ETL: Extraction → Nettoyage → Transformation → Chargement
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ETL: Validation et normalisation des factures staging → DWH
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION etl.valider_factures_staging(
    p_tenant_id INT,
    p_lot_id UUID DEFAULT NULL
)
RETURNS TABLE(
    factures_validees INT,
    factures_erreurs INT,
    factures_doublons INT
) AS $$
DECLARE
    v_validees INT := 0;
    v_erreurs INT := 0;
    v_doublons INT := 0;
    v_facture RECORD;
    v_date_id INT;
    v_date_ech_id INT;
    v_statut_id INT;
    v_devise_id INT;
    v_facture_sk BIGINT;
BEGIN
    -- Récupérer les IDs de référence
    SELECT statut_document_id INTO v_statut_id
    FROM dwh.dim_statut_document WHERE code = 'EN_ATTENTE';

    SELECT devise_id INTO v_devise_id
    FROM dwh.dim_devise WHERE code_iso = 'EUR';

    -- Parcourir les factures à valider
    FOR v_facture IN
        SELECT *
        FROM staging.factures_brutes
        WHERE tenant_id = p_tenant_id
          AND statut = 'EXTRAIT'
          AND (p_lot_id IS NULL OR lot_id = p_lot_id)
          AND score_global >= 70  -- Seuil confiance minimum
        ORDER BY created_at
    LOOP
        BEGIN
            -- Vérifier doublon
            IF EXISTS (
                SELECT 1 FROM dwh.fait_factures
                WHERE tenant_id = p_tenant_id
                  AND facture_id = v_facture.numero_facture
                  AND fournisseur_sk = v_facture.fournisseur_id_match
            ) THEN
                UPDATE staging.factures_brutes
                SET statut = 'DOUBLON', updated_at = NOW()
                WHERE stg_facture_id = v_facture.stg_facture_id;
                v_doublons := v_doublons + 1;
                CONTINUE;
            END IF;

            -- Vérifier données minimales
            IF v_facture.numero_facture IS NULL
               OR v_facture.date_facture IS NULL
               OR v_facture.montant_ttc IS NULL THEN
                UPDATE staging.factures_brutes
                SET statut = 'A_COMPLETER',
                    erreurs = jsonb_build_array(
                        jsonb_build_object('champ', 'validation', 'erreur', 'Données minimales manquantes')
                    ),
                    updated_at = NOW()
                WHERE stg_facture_id = v_facture.stg_facture_id;
                v_erreurs := v_erreurs + 1;
                CONTINUE;
            END IF;

            -- Obtenir date_id
            SELECT date_id INTO v_date_id
            FROM dwh.dim_temps WHERE date_complete = v_facture.date_facture;

            IF v_date_id IS NULL THEN
                RAISE EXCEPTION 'Date non trouvée dans dim_temps: %', v_facture.date_facture;
            END IF;

            -- Obtenir date échéance si présente
            IF v_facture.date_echeance IS NOT NULL THEN
                SELECT date_id INTO v_date_ech_id
                FROM dwh.dim_temps WHERE date_complete = v_facture.date_echeance;
            END IF;

            -- Insérer dans fait_factures
            INSERT INTO dwh.fait_factures (
                facture_id,
                tenant_id,
                date_facture_id,
                date_echeance_id,
                type_document_id,
                fournisseur_sk,
                devise_id,
                statut_id,
                montant_ht,
                montant_tva,
                montant_ttc,
                a_categoriser,
                a_identifier_tiers,
                donnees_incompletes,
                score_confiance,
                document_source_path,
                document_hash,
                source,
                lot_import_id
            ) VALUES (
                v_facture.numero_facture,
                p_tenant_id,
                v_date_id,
                v_date_ech_id,
                (SELECT type_document_id FROM dwh.dim_type_document WHERE code = 'FACT_FOUR'),
                v_facture.fournisseur_id_match,
                v_devise_id,
                v_statut_id,
                v_facture.montant_ht,
                v_facture.montant_tva,
                v_facture.montant_ttc,
                v_facture.fournisseur_id_match IS NULL,  -- a_categoriser si pas de fournisseur
                v_facture.fournisseur_id_match IS NULL,  -- a_identifier si pas de fournisseur
                v_facture.score_global < 90,             -- incomplet si score < 90
                v_facture.score_global,
                v_facture.fichier_source,
                v_facture.document_hash,
                COALESCE((SELECT fournisseur_code FROM staging.patterns_fournisseurs
                          WHERE fournisseur_sk = v_facture.fournisseur_id_match LIMIT 1), 'INCONNU'),
                v_facture.lot_id
            )
            RETURNING facture_sk INTO v_facture_sk;

            -- Mettre à jour staging
            UPDATE staging.factures_brutes
            SET statut = 'INTEGRE',
                facture_sk_integre = v_facture_sk,
                date_integration = NOW(),
                updated_at = NOW()
            WHERE stg_facture_id = v_facture.stg_facture_id;

            v_validees := v_validees + 1;

        EXCEPTION WHEN OTHERS THEN
            -- Enregistrer l'erreur
            INSERT INTO staging.erreurs_import (lot_id, tenant_id, type_erreur, severite, message_erreur, fichier_source)
            VALUES (v_facture.lot_id, p_tenant_id, 'ETL', 'ERROR', SQLERRM, v_facture.fichier_source);

            UPDATE staging.factures_brutes
            SET statut = 'A_VERIFIER',
                erreurs = jsonb_build_array(jsonb_build_object('erreur', SQLERRM)),
                updated_at = NOW()
            WHERE stg_facture_id = v_facture.stg_facture_id;

            v_erreurs := v_erreurs + 1;
        END;
    END LOOP;

    -- Mettre à jour le lot
    IF p_lot_id IS NOT NULL THEN
        UPDATE staging.import_lots
        SET nb_lignes_importees = v_validees,
            nb_lignes_erreur = v_erreurs,
            nb_lignes_doublon = v_doublons,
            statut = CASE
                WHEN v_erreurs = 0 THEN 'TERMINE'
                WHEN v_validees > 0 THEN 'PARTIEL'
                ELSE 'ERREUR'
            END,
            date_fin = NOW()
        WHERE lot_id = p_lot_id;
    END IF;

    RETURN QUERY SELECT v_validees, v_erreurs, v_doublons;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION etl.valider_factures_staging IS 'ETL: Valide et intègre les factures staging vers DWH';

-- ----------------------------------------------------------------------------
-- ETL: Calcul position trésorerie quotidienne
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION etl.calculer_tresorerie_quotidienne(
    p_tenant_id INT,
    p_date DATE DEFAULT CURRENT_DATE
)
RETURNS INT AS $$
DECLARE
    v_compte RECORD;
    v_date_id INT;
    v_solde_debut NUMERIC(14,2);
    v_total_debits NUMERIC(14,2);
    v_total_credits NUMERIC(14,2);
    v_nb_ops INT;
    v_inserted INT := 0;
BEGIN
    -- Obtenir date_id
    SELECT date_id INTO v_date_id
    FROM dwh.dim_temps WHERE date_complete = p_date;

    IF v_date_id IS NULL THEN
        RAISE EXCEPTION 'Date % non trouvée dans dim_temps', p_date;
    END IF;

    -- Pour chaque compte bancaire actif
    FOR v_compte IN
        SELECT compte_sk, compte_id, devise_id
        FROM dwh.dim_compte_bancaire
        WHERE tenant_id = p_tenant_id AND est_actuel = TRUE
    LOOP
        -- Calculer solde début (= solde fin veille ou 0)
        SELECT COALESCE(solde_fin_journee, 0) INTO v_solde_debut
        FROM dwh.fait_tresorerie
        WHERE tenant_id = p_tenant_id
          AND compte_bancaire_sk = v_compte.compte_sk
          AND date_id = (SELECT date_id FROM dwh.dim_temps WHERE date_complete = p_date - 1);

        IF v_solde_debut IS NULL THEN
            v_solde_debut := 0;
        END IF;

        -- Calculer mouvements du jour
        SELECT
            COALESCE(SUM(CASE WHEN sens = 'DEBIT' THEN montant ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN sens = 'CREDIT' THEN montant ELSE 0 END), 0),
            COUNT(*)
        INTO v_total_debits, v_total_credits, v_nb_ops
        FROM dwh.fait_mouvements_bancaires
        WHERE tenant_id = p_tenant_id
          AND compte_bancaire_sk = v_compte.compte_sk
          AND date_operation_id = v_date_id;

        -- Insérer ou mettre à jour
        INSERT INTO dwh.fait_tresorerie (
            tenant_id, date_id, compte_bancaire_sk, devise_id,
            solde_debut_journee, solde_fin_journee,
            total_debits, total_credits, nb_operations,
            source
        ) VALUES (
            p_tenant_id, v_date_id, v_compte.compte_sk, v_compte.devise_id,
            v_solde_debut,
            v_solde_debut - v_total_debits + v_total_credits,
            v_total_debits, v_total_credits, v_nb_ops,
            'CALCUL'
        )
        ON CONFLICT (tenant_id, date_id, compte_bancaire_sk)
        DO UPDATE SET
            solde_fin_journee = EXCLUDED.solde_fin_journee,
            total_debits = EXCLUDED.total_debits,
            total_credits = EXCLUDED.total_credits,
            nb_operations = EXCLUDED.nb_operations,
            created_at = NOW();

        v_inserted := v_inserted + 1;
    END LOOP;

    RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION etl.calculer_tresorerie_quotidienne IS 'ETL: Calcul position trésorerie journalière par compte';

-- ----------------------------------------------------------------------------
-- ETL: Mise à jour ODS factures en cours
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION etl.refresh_ods_factures_en_cours(p_tenant_id INT)
RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    -- Vider et recharger (truncate + insert pour performances)
    DELETE FROM ods.factures_en_cours WHERE tenant_id = p_tenant_id;

    INSERT INTO ods.factures_en_cours (
        facture_sk, facture_id, tenant_id,
        fournisseur_nom, fournisseur_code,
        date_facture, date_echeance, jours_avant_echeance, est_echue,
        montant_ttc, montant_paye, reste_a_payer, devise,
        statut_code, statut_nom, statut_couleur,
        cost_center_nom, categorie_nom,
        priorite, alerte_texte,
        require_validation, require_categorisation, require_completion,
        source
    )
    SELECT
        f.facture_sk,
        f.facture_id,
        f.tenant_id,
        COALESCE(four.nom, 'Non identifié'),
        four.code,
        dt.date_complete AS date_facture,
        de.date_complete AS date_echeance,
        CASE WHEN de.date_complete IS NOT NULL
             THEN de.date_complete - CURRENT_DATE
             ELSE NULL END AS jours_avant_echeance,
        CASE WHEN de.date_complete IS NOT NULL
             THEN de.date_complete < CURRENT_DATE
             ELSE FALSE END AS est_echue,
        f.montant_ttc,
        f.montant_paye,
        f.reste_a_payer,
        dev.code_iso,
        s.code AS statut_code,
        s.nom AS statut_nom,
        s.couleur AS statut_couleur,
        cc.nom AS cost_center_nom,
        cd.nom AS categorie_nom,
        CASE
            WHEN de.date_complete < CURRENT_DATE AND f.reste_a_payer > 0 THEN 1  -- Échue impayée
            WHEN de.date_complete <= CURRENT_DATE + 3 AND f.reste_a_payer > 0 THEN 2  -- Échéance < 3j
            WHEN f.a_identifier_tiers OR f.a_categoriser THEN 3  -- Actions requises
            WHEN f.donnees_incompletes THEN 4  -- Données incomplètes
            ELSE 5  -- Normal
        END AS priorite,
        CASE
            WHEN de.date_complete < CURRENT_DATE AND f.reste_a_payer > 0 THEN 'ÉCHUE IMPAYÉE'
            WHEN de.date_complete <= CURRENT_DATE + 3 AND f.reste_a_payer > 0 THEN 'ÉCHÉANCE PROCHE'
            WHEN f.a_identifier_tiers THEN 'FOURNISSEUR À IDENTIFIER'
            WHEN f.a_categoriser THEN 'À CATÉGORISER'
            WHEN f.donnees_incompletes THEN 'DONNÉES INCOMPLÈTES'
            ELSE NULL
        END AS alerte_texte,
        s.code = 'EN_ATTENTE' AS require_validation,
        f.a_categoriser AS require_categorisation,
        f.donnees_incompletes AS require_completion,
        f.source
    FROM dwh.fait_factures f
    JOIN dwh.dim_temps dt ON f.date_facture_id = dt.date_id
    LEFT JOIN dwh.dim_temps de ON f.date_echeance_id = de.date_id
    JOIN dwh.dim_statut_document s ON f.statut_id = s.statut_document_id
    JOIN dwh.dim_devise dev ON f.devise_id = dev.devise_id
    LEFT JOIN dwh.dim_fournisseur four ON f.fournisseur_sk = four.fournisseur_sk
    LEFT JOIN dwh.dim_cost_center cc ON f.cost_center_id = cc.cost_center_id
    LEFT JOIN dwh.dim_categorie_depense cd ON f.categorie_depense_id = cd.categorie_depense_id
    WHERE f.tenant_id = p_tenant_id
      AND s.est_final = FALSE  -- Exclure statuts terminaux
    ;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION etl.refresh_ods_factures_en_cours IS 'ETL: Rafraîchit ODS factures en cours';

-- ----------------------------------------------------------------------------
-- ETL: Mise à jour budget réalisé
-- ----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION etl.calculer_budget_realise(
    p_tenant_id INT,
    p_annee INT,
    p_mois INT
)
RETURNS INT AS $$
DECLARE
    v_updated INT := 0;
BEGIN
    -- Mettre à jour le réalisé basé sur fait_depenses
    UPDATE dwh.fait_budget b
    SET realise = sub.total_realise,
        date_dernier_calcul = NOW(),
        updated_at = NOW()
    FROM (
        SELECT
            d.cost_center_id,
            d.categorie_depense_id,
            SUM(COALESCE(d.montant_ttc, 0)) AS total_realise
        FROM dwh.fait_depenses d
        JOIN dwh.dim_temps t ON d.date_id = t.date_id
        WHERE d.tenant_id = p_tenant_id
          AND t.annee = p_annee
          AND t.mois = p_mois
        GROUP BY d.cost_center_id, d.categorie_depense_id
    ) sub
    WHERE b.tenant_id = p_tenant_id
      AND b.annee = p_annee
      AND b.mois = p_mois
      AND b.cost_center_id = sub.cost_center_id
      AND COALESCE(b.categorie_depense_id, 0) = COALESCE(sub.categorie_depense_id, 0);

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION etl.calculer_budget_realise IS 'ETL: Calcule le réalisé vs budget';

-- Créer le schéma ETL si pas existant
CREATE SCHEMA IF NOT EXISTS etl;
COMMENT ON SCHEMA etl IS 'Procédures ETL - Extraction, Transformation, Chargement';


-- ============================================================================
-- SECTION 7: SÉCURITÉ - ROW LEVEL SECURITY (RLS)
-- ============================================================================
-- Isolation tenant complète sur toutes les tables finance
-- ============================================================================

-- Activer RLS sur toutes les tables DWH Finance
ALTER TABLE dwh.dim_compte_bancaire ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.dim_exercice_comptable ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_factures ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_lignes_factures ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_paiements ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_affectation_paiement ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_mouvements_bancaires ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_tresorerie ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_budget ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_echeances ENABLE ROW LEVEL SECURITY;
ALTER TABLE dwh.fait_historique_statut ENABLE ROW LEVEL SECURITY;

-- Activer RLS sur tables ODS
ALTER TABLE ods.factures_en_cours ENABLE ROW LEVEL SECURITY;
ALTER TABLE ods.tresorerie_temps_reel ENABLE ROW LEVEL SECURITY;
ALTER TABLE ods.echeancier_7j ENABLE ROW LEVEL SECURITY;

-- Activer RLS sur tables Staging
ALTER TABLE staging.import_lots ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.factures_brutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.factures_lignes_brutes ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.releves_bruts ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.erreurs_import ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.patterns_fournisseurs ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging.patterns_releves ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- Politiques RLS - Pattern: tenant_id = current_setting('app.current_tenant_id')
-- ----------------------------------------------------------------------------

-- DWH Tables
CREATE POLICY tenant_isolation_dim_compte ON dwh.dim_compte_bancaire
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_dim_exercice ON dwh.dim_exercice_comptable
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_factures ON dwh.fait_factures
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_lignes ON dwh.fait_lignes_factures
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_paiements ON dwh.fait_paiements
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_affectation ON dwh.fait_affectation_paiement
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_mvt_bancaire ON dwh.fait_mouvements_bancaires
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_tresorerie ON dwh.fait_tresorerie
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_budget ON dwh.fait_budget
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_echeances ON dwh.fait_echeances
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_fait_historique ON dwh.fait_historique_statut
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

-- ODS Tables
CREATE POLICY tenant_isolation_ods_factures ON ods.factures_en_cours
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_ods_treso ON ods.tresorerie_temps_reel
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_ods_echeancier ON ods.echeancier_7j
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

-- Staging Tables
CREATE POLICY tenant_isolation_stg_lots ON staging.import_lots
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_factures ON staging.factures_brutes
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_lignes ON staging.factures_lignes_brutes
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_releves ON staging.releves_bruts
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_erreurs ON staging.erreurs_import
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_patterns_four ON staging.patterns_fournisseurs
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));

CREATE POLICY tenant_isolation_stg_patterns_rel ON staging.patterns_releves
    USING (tenant_id = COALESCE(NULLIF(current_setting('app.current_tenant_id', TRUE), '')::INT, tenant_id));


-- ============================================================================
-- SECTION 8: DATA MARTS - VUES ANALYTIQUES
-- ============================================================================
-- Vues orientées métier pour BI et reporting
-- Architecture: Étoile avec faits dénormalisés
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Data Mart: Analyse Trésorerie
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW dwh.v_tresorerie_analyse AS
SELECT
    t.tresorerie_sk,
    t.tenant_id,
    -- Temps
    dt.date_complete,
    dt.jour_semaine,
    dt.nom_jour,
    dt.semaine_iso,
    dt.mois,
    dt.nom_mois,
    dt.trimestre,
    dt.annee,
    dt.est_jour_ouvre,
    -- Compte
    c.code_interne AS compte_code,
    c.libelle AS compte_libelle,
    c.banque,
    c.iban,
    c.type_compte,
    c.est_compte_principal,
    dev.code_iso AS devise,
    -- Mesures
    t.solde_debut_journee,
    t.solde_fin_journee,
    t.variation_jour,
    t.total_debits,
    t.total_credits,
    t.nb_operations,
    t.en_decouvert,
    -- Limites
    c.plafond_decouvert,
    CASE
        WHEN c.plafond_decouvert IS NOT NULL
        THEN t.solde_fin_journee + c.plafond_decouvert
        ELSE t.solde_fin_journee
    END AS marge_disponible,
    -- Prévisionnel
    t.solde_previsionnel_j7,
    t.solde_previsionnel_j30
FROM dwh.fait_tresorerie t
JOIN dwh.dim_temps dt ON t.date_id = dt.date_id
JOIN dwh.dim_compte_bancaire c ON t.compte_bancaire_sk = c.compte_sk
JOIN dwh.dim_devise dev ON t.devise_id = dev.devise_id
WHERE c.est_actuel = TRUE;

COMMENT ON VIEW dwh.v_tresorerie_analyse IS 'Data Mart: Analyse trésorerie - vue multi-dimensions';

-- ----------------------------------------------------------------------------
-- Data Mart: Analyse Factures Fournisseurs
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW dwh.v_factures_analyse AS
SELECT
    f.facture_sk,
    f.facture_id,
    f.tenant_id,
    -- Temps facture
    dt.date_complete AS date_facture,
    dt.mois AS mois_facture,
    dt.trimestre AS trimestre_facture,
    dt.annee AS annee_facture,
    -- Temps échéance
    de.date_complete AS date_echeance,
    CASE
        WHEN de.date_complete IS NOT NULL
        THEN de.date_complete - CURRENT_DATE
        ELSE NULL
    END AS jours_avant_echeance,
    CASE
        WHEN de.date_complete IS NOT NULL AND de.date_complete < CURRENT_DATE
        THEN CURRENT_DATE - de.date_complete
        ELSE 0
    END AS jours_retard,
    -- Fournisseur
    four.nom AS fournisseur_nom,
    four.code AS fournisseur_code,
    four.type_tiers,
    -- Type document
    td.nom AS type_document,
    td.sens,
    -- Statut
    s.code AS statut_code,
    s.nom AS statut_nom,
    s.est_final AS est_clos,
    -- Montants
    f.montant_ht,
    f.montant_tva,
    f.montant_ttc,
    f.montant_paye,
    f.reste_a_payer,
    dev.code_iso AS devise,
    -- Classification
    cc.nom AS cost_center,
    cd.nom AS categorie_depense,
    ex.code AS exercice,
    -- Qualité
    f.score_confiance,
    f.a_categoriser,
    f.a_identifier_tiers,
    f.donnees_incompletes,
    -- Source
    f.source,
    f.created_at
FROM dwh.fait_factures f
JOIN dwh.dim_temps dt ON f.date_facture_id = dt.date_id
LEFT JOIN dwh.dim_temps de ON f.date_echeance_id = de.date_id
JOIN dwh.dim_type_document td ON f.type_document_id = td.type_document_id
JOIN dwh.dim_statut_document s ON f.statut_id = s.statut_document_id
JOIN dwh.dim_devise dev ON f.devise_id = dev.devise_id
LEFT JOIN dwh.dim_fournisseur four ON f.fournisseur_sk = four.fournisseur_sk AND four.est_actuel = TRUE
LEFT JOIN dwh.dim_cost_center cc ON f.cost_center_id = cc.cost_center_id
LEFT JOIN dwh.dim_categorie_depense cd ON f.categorie_depense_id = cd.categorie_depense_id
LEFT JOIN dwh.dim_exercice_comptable ex ON f.exercice_id = ex.exercice_id;

COMMENT ON VIEW dwh.v_factures_analyse IS 'Data Mart: Analyse factures - vue multi-dimensions';

-- ----------------------------------------------------------------------------
-- Data Mart: Budget vs Réalisé
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW dwh.v_budget_vs_reel AS
SELECT
    b.budget_sk,
    b.tenant_id,
    -- Période
    b.annee,
    b.mois,
    ex.code AS exercice,
    -- Classification
    cc.nom AS cost_center,
    cc.type AS cost_center_type,
    cd.nom AS categorie_depense,
    -- Budget
    b.budget_initial,
    b.budget_revise,
    COALESCE(b.budget_revise, b.budget_initial) AS budget_actuel,
    -- Réalisé
    b.realise,
    -- Écarts
    b.ecart_initial,
    b.ecart_revise,
    b.taux_consommation_pct,
    -- Indicateurs
    CASE
        WHEN b.taux_consommation_pct > 100 THEN 'DEPASSEMENT'
        WHEN b.taux_consommation_pct > 90 THEN 'ALERTE'
        WHEN b.taux_consommation_pct > 75 THEN 'ATTENTION'
        ELSE 'OK'
    END AS statut_budget,
    -- Projection fin de mois
    CASE
        WHEN EXTRACT(DAY FROM CURRENT_DATE) > 0
        THEN b.realise / EXTRACT(DAY FROM CURRENT_DATE) * DATE_PART('day',
            (DATE_TRUNC('month', MAKE_DATE(b.annee, b.mois, 1)) + INTERVAL '1 month - 1 day')::DATE)
        ELSE b.realise
    END AS projection_fin_mois
FROM dwh.fait_budget b
JOIN dwh.dim_exercice_comptable ex ON b.exercice_id = ex.exercice_id
JOIN dwh.dim_cost_center cc ON b.cost_center_id = cc.cost_center_id
LEFT JOIN dwh.dim_categorie_depense cd ON b.categorie_depense_id = cd.categorie_depense_id;

COMMENT ON VIEW dwh.v_budget_vs_reel IS 'Data Mart: Suivi budgétaire - budget vs réalisé';

-- ----------------------------------------------------------------------------
-- Data Mart: Échéancier Consolidé
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW dwh.v_echeancier_consolide AS
SELECT
    -- Identité
    f.facture_sk AS reference_sk,
    'FACTURE' AS type_echeance,
    f.facture_id AS reference,
    f.tenant_id,
    -- Dates
    de.date_complete AS date_echeance,
    dt.date_complete AS date_origine,
    -- Tiers
    four.nom AS tiers_nom,
    four.code AS tiers_code,
    -- Montants
    CASE td.sens WHEN 'ENTRANT' THEN 'SORTANT' ELSE 'ENTRANT' END AS sens_flux,  -- Inverse: facture entrante = paiement sortant
    f.reste_a_payer AS montant,
    dev.code_iso AS devise,
    -- Classification
    cc.nom AS cost_center,
    cd.nom AS categorie,
    -- Statut
    CASE
        WHEN de.date_complete < CURRENT_DATE THEN 'ECHUE'
        WHEN de.date_complete <= CURRENT_DATE + 7 THEN 'PROCHE'
        ELSE 'A_VENIR'
    END AS statut_echeance,
    de.date_complete - CURRENT_DATE AS jours_restants
FROM dwh.fait_factures f
JOIN dwh.dim_temps dt ON f.date_facture_id = dt.date_id
JOIN dwh.dim_temps de ON f.date_echeance_id = de.date_id
JOIN dwh.dim_type_document td ON f.type_document_id = td.type_document_id
JOIN dwh.dim_statut_document s ON f.statut_id = s.statut_document_id
JOIN dwh.dim_devise dev ON f.devise_id = dev.devise_id
LEFT JOIN dwh.dim_fournisseur four ON f.fournisseur_sk = four.fournisseur_sk AND four.est_actuel = TRUE
LEFT JOIN dwh.dim_cost_center cc ON f.cost_center_id = cc.cost_center_id
LEFT JOIN dwh.dim_categorie_depense cd ON f.categorie_depense_id = cd.categorie_depense_id
WHERE f.reste_a_payer > 0
  AND s.permet_paiement = TRUE;

COMMENT ON VIEW dwh.v_echeancier_consolide IS 'Data Mart: Échéancier consolidé - prévision flux';

-- ----------------------------------------------------------------------------
-- Data Mart: KPIs Finance Dashboard
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW dwh.v_kpis_finance AS
SELECT
    tenant_id,
    -- Trésorerie globale
    (SELECT SUM(solde_fin_journee)
     FROM dwh.fait_tresorerie t
     JOIN dwh.dim_compte_bancaire c ON t.compte_bancaire_sk = c.compte_sk AND c.est_actuel = TRUE
     WHERE t.tenant_id = f.tenant_id
       AND t.date_id = (SELECT MAX(date_id) FROM dwh.fait_tresorerie WHERE tenant_id = f.tenant_id)
    ) AS solde_tresorerie_global,

    -- Factures à payer
    SUM(CASE WHEN s.code NOT IN ('PAYE', 'RAPPROCHE', 'ANNULE') THEN f.reste_a_payer ELSE 0 END) AS total_a_payer,
    COUNT(CASE WHEN s.code NOT IN ('PAYE', 'RAPPROCHE', 'ANNULE') AND f.reste_a_payer > 0 THEN 1 END) AS nb_factures_a_payer,

    -- Échéances proches (7j)
    SUM(CASE
        WHEN s.code NOT IN ('PAYE', 'RAPPROCHE', 'ANNULE')
         AND de.date_complete BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
        THEN f.reste_a_payer ELSE 0
    END) AS echeances_7j,

    -- Retards
    SUM(CASE
        WHEN s.code NOT IN ('PAYE', 'RAPPROCHE', 'ANNULE')
         AND de.date_complete < CURRENT_DATE
        THEN f.reste_a_payer ELSE 0
    END) AS total_en_retard,
    COUNT(CASE
        WHEN s.code NOT IN ('PAYE', 'RAPPROCHE', 'ANNULE')
         AND de.date_complete < CURRENT_DATE
         AND f.reste_a_payer > 0
        THEN 1
    END) AS nb_factures_en_retard,

    -- Actions requises
    COUNT(CASE WHEN f.a_categoriser THEN 1 END) AS factures_a_categoriser,
    COUNT(CASE WHEN f.a_identifier_tiers THEN 1 END) AS factures_tiers_inconnu,
    COUNT(CASE WHEN f.donnees_incompletes THEN 1 END) AS factures_incompletes

FROM dwh.fait_factures f
JOIN dwh.dim_statut_document s ON f.statut_id = s.statut_document_id
LEFT JOIN dwh.dim_temps de ON f.date_echeance_id = de.date_id
GROUP BY f.tenant_id;

COMMENT ON VIEW dwh.v_kpis_finance IS 'Data Mart: KPIs finance pour dashboard';


-- ============================================================================
-- SECTION 9: TRIGGERS ET AUTOMATISATIONS
-- ============================================================================

-- Trigger: Historisation changements statut factures
CREATE OR REPLACE FUNCTION dwh.trigger_historique_statut_facture()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.statut_id IS DISTINCT FROM NEW.statut_id THEN
        INSERT INTO dwh.fait_historique_statut (
            tenant_id, entite_type, entite_sk,
            statut_precedent_id, statut_nouveau_id,
            date_changement_id
        ) VALUES (
            NEW.tenant_id,
            'FACTURE',
            NEW.facture_sk,
            OLD.statut_id,
            NEW.statut_id,
            (SELECT date_id FROM dwh.dim_temps WHERE date_complete = CURRENT_DATE)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_facture_historique_statut
    AFTER UPDATE ON dwh.fait_factures
    FOR EACH ROW
    EXECUTE FUNCTION dwh.trigger_historique_statut_facture();

-- Trigger: Mise à jour montant payé facture après affectation paiement
CREATE OR REPLACE FUNCTION dwh.trigger_update_facture_montant_paye()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE dwh.fait_factures
        SET montant_paye = (
            SELECT COALESCE(SUM(montant_affecte), 0)
            FROM dwh.fait_affectation_paiement
            WHERE facture_sk = NEW.facture_sk
        ),
        updated_at = NOW()
        WHERE facture_sk = NEW.facture_sk;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE dwh.fait_factures
        SET montant_paye = (
            SELECT COALESCE(SUM(montant_affecte), 0)
            FROM dwh.fait_affectation_paiement
            WHERE facture_sk = OLD.facture_sk
        ),
        updated_at = NOW()
        WHERE facture_sk = OLD.facture_sk;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_affectation_update_facture
    AFTER INSERT OR UPDATE OR DELETE ON dwh.fait_affectation_paiement
    FOR EACH ROW
    EXECUTE FUNCTION dwh.trigger_update_facture_montant_paye();


-- ============================================================================
-- SECTION 10: DOCUMENTATION MODÈLE
-- ============================================================================

COMMENT ON SCHEMA dwh IS '
================================================================================
DATA WAREHOUSE FINANCE - MASSACORP
================================================================================

ARCHITECTURE SID (Corporate Information Factory):
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGING (staging.*)     │ DONNÉES BRUTES                                    │
│ - factures_brutes       │ Import PDF (METRO, TAIYAT, EUROCIEL)             │
│ - releves_bruts         │ Import relevés bancaires (BNP, SG, CA)           │
│ - patterns_*            │ Configuration extraction par source              │
├─────────────────────────────────────────────────────────────────────────────┤
│ ODS (ods.*)             │ DONNÉES OPÉRATIONNELLES                          │
│ - factures_en_cours     │ Factures actives (décision tactique)             │
│ - tresorerie_temps_reel │ Position trésorerie live                         │
│ - echeancier_7j         │ Échéances court terme                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ DWH (dwh.*)             │ DONNÉES HISTORISÉES                              │
│ DIMENSIONS:                                                                 │
│ - dim_devise            │ Devises (SCD1)                                   │
│ - dim_mode_paiement     │ Modes paiement (SCD1)                            │
│ - dim_type_document     │ Types documents (SCD1)                           │
│ - dim_statut_document   │ Statuts workflow (SCD1)                          │
│ - dim_compte_bancaire   │ Comptes bancaires (SCD2)                         │
│ - dim_exercice_comptable│ Exercices comptables (SCD1)                      │
│ - dim_fournisseur       │ Tiers (SCD2) - étendu                            │
│                                                                             │
│ FAITS:                                                                      │
│ - fait_factures         │ GRAIN: 1 ligne/facture                           │
│ - fait_lignes_factures  │ GRAIN: 1 ligne/ligne facture                     │
│ - fait_paiements        │ GRAIN: 1 ligne/paiement                          │
│ - fait_affectation      │ GRAIN: 1 ligne/affectation paiement-facture      │
│ - fait_mvt_bancaires    │ GRAIN: 1 ligne/mouvement relevé                  │
│ - fait_tresorerie       │ GRAIN: 1 ligne/compte/jour                       │
│ - fait_budget           │ GRAIN: 1 ligne/cost_center/mois                  │
│ - fait_echeances        │ GRAIN: 1 ligne/échéance                          │
│ - fait_historique_statut│ GRAIN: 1 ligne/changement statut                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ DATA MARTS (dwh.v_*)    │ VUES MÉTIER                                      │
│ - v_tresorerie_analyse  │ Analyse trésorerie multi-dim                     │
│ - v_factures_analyse    │ Analyse factures multi-dim                       │
│ - v_budget_vs_reel      │ Suivi budgétaire                                 │
│ - v_echeancier_consolide│ Prévision flux                                   │
│ - v_kpis_finance        │ KPIs dashboard                                   │
└─────────────────────────────────────────────────────────────────────────────┘

SÉCURITÉ:
- RLS (Row Level Security) sur toutes les tables
- Isolation tenant via current_setting(app.current_tenant_id)

TRAITEMENT DONNÉES MANQUANTES:
- score_confiance: 0-100 (seuil validation: 70)
- a_categoriser: catégorie non identifiée
- a_identifier_tiers: fournisseur non reconnu
- donnees_incompletes: extraction partielle
- Workflow: EXTRAIT → A_VERIFIER → VALIDE/A_COMPLETER → INTEGRE

ETL (etl.*):
- valider_factures_staging(): Staging → DWH
- calculer_tresorerie_quotidienne(): Snapshot journalier
- refresh_ods_factures_en_cours(): ODS refresh
- calculer_budget_realise(): Budget vs réalisé
================================================================================
';
