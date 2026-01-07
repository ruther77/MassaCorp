# ARCHITECTURE REFONTE EPICERIE & RESTAURANT
## Document de Conception Technique

**Date:** 2026-01-07
**Version:** 1.0
**Auteur:** MassaCorp Dev Team

---

## TABLE DES MATIERES

1. [ETAT ACTUEL DES MODELES](#1-etat-actuel-des-modeles)
2. [PROBLEMES IDENTIFIES](#2-problemes-identifies)
3. [COMPREHENSION METIER RESTAURANT](#3-comprehension-metier-restaurant)
4. [ARCHITECTURE CIBLE](#4-architecture-cible)
5. [NOUVEAUX MODELES PROPOSES](#5-nouveaux-modeles-proposes)
6. [ROADMAP DETAILLEE](#6-roadmap-detaillee)

---

## 1. ETAT ACTUEL DES MODELES

### 1.1 Schema DWH - Fournisseurs

#### METRO (dwh.metro_*)
```
metro_facture
├── id, tenant_id, numero (unique), date_facture
├── magasin, client_nom, client_numero
├── total_ht, total_tva, total_ttc
└── fichier_source, importee_le

metro_ligne
├── id, tenant_id, facture_id (FK CASCADE)
├── ean, article_numero, designation
├── colisage, quantite_colis, quantite_unitaire
├── prix_colis, prix_unitaire, montant_ht
├── volume_unitaire, poids_unitaire, unite
├── taux_tva, code_tva, montant_tva
├── regie, vol_alcool, categorie_id
└── Index: (tenant_id, ean)

metro_produit_agregat (1531 produits actuellement)
├── id, tenant_id, ean (unique/tenant)
├── article_numero, designation, colisage_moyen, unite
├── quantite_colis_totale, quantite_unitaire_totale
├── montant_total_ht, montant_total_tva, montant_total
├── nb_achats, prix_unitaire_moyen/min/max, prix_colis_moyen
├── categorie_id, famille, categorie, sous_categorie
├── regie, vol_alcool
├── premier_achat, dernier_achat, calcule_le
└── Index: (tenant_id, ean) unique
```

#### TAIYAT (dwh.taiyat_*)
```
taiyat_facture
├── id, tenant_id, numero (unique), date_facture, echeance
├── client_nom (NOUTAM/INCONTOURNABLE), client_code
├── total_ht, total_tva, total_ttc
└── fichier_source, importee_le

taiyat_ligne
├── id, tenant_id, facture_id (FK CASCADE)
├── ean (peut etre manuel), designation, designation_clean
├── provenance (pays origine)
├── colis, pieces, unite
├── prix_unitaire_ht, prix_unitaire_ttc
├── montant_ht, montant_ttc
├── code_tva (1=5.5%, 2=20%), taux_tva
├── est_remise, categorie_id
└── Index: (tenant_id, designation_clean)

taiyat_produit_agregat
├── id, tenant_id, ean
├── designation_brute, designation_clean (unique/tenant)
├── provenance, dim_produit_id (FK)
├── quantite_colis_totale, quantite_pieces_totale, nb_achats
├── montant_total_ht/tva/total
├── prix_moyen_ht/min/max, taux_tva
├── categorie_id, famille, categorie, sous_categorie
├── premier_achat, dernier_achat, calcule_le
└── Index: (tenant_id, designation_clean) unique
```

#### EUROCIEL (dwh.eurociel_*)
```
eurociel_facture
├── id, tenant_id, numero (unique)
├── type_document (FA=Facture, AV=Avoir)
├── date_facture, client_nom, client_code, client_adresse, client_telephone
├── total_ht, total_tva, total_ttc
├── poids_total, quantite_totale
└── fichier_source, page_source, importee_le

eurociel_ligne
├── id, tenant_id, facture_id (FK CASCADE)
├── numero_ligne, ean, designation, designation_clean
├── quantite, poids (kg), prix_unitaire (HT)
├── montant_ht, code_tva, taux_tva, montant_tva, montant_ttc
├── est_promo, categorie_id
└── Index: (tenant_id, designation_clean)

eurociel_produit_agregat
├── id, tenant_id, ean
├── designation_brute, designation_clean (unique/tenant)
├── dim_produit_id (FK)
├── quantite_totale, poids_total, nb_achats
├── montant_total_ht/tva/total
├── prix_moyen/min/max, taux_tva
├── categorie_id, famille, categorie, sous_categorie
├── premier_achat, dernier_achat, calcule_le
└── Index: (tenant_id, designation_clean) unique

eurociel_catalogue_produit
├── id, tenant_id, reference (unique/tenant)
├── designation, designation_clean
├── categorie (POISSONS, VOLAILLES, LEGUMES, etc.)
├── sous_categorie, taille (500/800, 1000+, etc.)
├── conditionnement (10KG, 12X1KG), poids_kg
├── origine, page_source, actif
└── produit_agregat_id (FK SET NULL)
```

#### OTHER (dwh.other_*)
```
other_produit_agregat
├── id, tenant_id
├── designation, designation_clean
├── famille, categorie, sous_categorie
├── colisage, unite, contenance
├── prix_unitaire (centimes), prix_colis (centimes)
├── fournisseur_nom, fournisseur_type
├── notes, actif
└── Index: (tenant_id, designation_clean)
```

#### DIM_PRODUIT (Table Maitre Unifiee - dwh.dim_produit)
```
dim_produit
├── id, ean (unique), article_numero
├── designation_brute, designation_clean, nom_court
├── marque, type_produit
├── famille, categorie, sous_categorie
├── contenance_cl, contenance_label, degre_alcool
├── colisage_standard, regie, taux_tva
├── prix_achat_unitaire, prix_achat_colis, date_dernier_prix
├── nb_achats, quantite_totale_achetee, montant_total_achats
├── source (METRO/TAIYAT/EUROCIEL/OTHER)
├── actif, created_at, updated_at
└── Index: ean, marque, (famille, categorie)
```

### 1.2 Schema Restaurant

#### restaurant_ingredients
```
restaurant_ingredients
├── id, tenant_id
├── name (Text)
├── unit (ENUM: U, KG, L, G, CL, ML)
├── category (ENUM: VIANDE, POISSON, LEGUME, FRUIT,
│             PRODUIT_LAITIER, EPICERIE, BOISSON, CONDIMENT, AUTRE)
├── default_supplier_id (FK finance_vendors, SET NULL)
├── prix_unitaire (BigInt, centimes)
├── seuil_alerte (Numeric 10,3)
├── is_active, notes, created_at, updated_at
├── Relations:
│   ├── 1->N: plat_ingredients
│   ├── 1->1: stock
│   ├── 1->N: epicerie_links
│   └── N->1: default_supplier
└── Index: (tenant_id, name), (tenant_id, category)
```

#### restaurant_plats
```
restaurant_plats
├── id, tenant_id
├── name, description
├── category (ENUM: ENTREE, PLAT, DESSERT, BOISSON, MENU,
│             ACCOMPAGNEMENT, VIANDES, POISSONS, BOUILLONS,
│             GRILLADES, PLATS_EN_SAUCE, LEGUMES, TRADITIONNELS, SOFT, AUTRE)
├── prix_vente (BigInt, centimes)
├── is_active, is_menu, image_url, notes
├── created_at, updated_at
├── Relations:
│   ├── 1->N: ingredients (plat_ingredients)
│   └── 1->N: consumptions
├── Methodes calculees:
│   ├── cout_total = sum(ingredient_costs)
│   ├── marge_brute = prix_vente - cout_total
│   └── food_cost_ratio = cout_total / prix_vente * 100
└── Index: (tenant_id, name), (tenant_id, category)
```

#### restaurant_plat_ingredients
```
restaurant_plat_ingredients
├── id
├── plat_id (FK CASCADE)
├── ingredient_id (FK CASCADE)
├── quantite (Numeric 10,3)
├── notes, created_at, updated_at
├── Unique: (plat_id, ingredient_id)
└── Methodes: cout_ligne = quantite * ingredient.prix_unitaire
```

#### restaurant_epicerie_links (TABLE DE LIAISON CRITIQUE)
```
restaurant_epicerie_links
├── id, tenant_id
├── ingredient_id (FK CASCADE) → restaurant_ingredients
├── produit_id (BigInt) → ID dans dim_produit OU table agregat fournisseur
├── fournisseur (String 50) → METRO, TAIYAT, EUROCIEL, OTHER
├── ratio (Numeric 10,4) → facteur conversion
├── is_primary (Bool)
├── created_at, updated_at
├── Index: (ingredient_id), (produit_id), (tenant_id)
└── Probleme: Lien direct vers produit specifique, pas de notion generique
```

#### restaurant_stock / restaurant_stock_movements
```
restaurant_stock
├── id, tenant_id
├── ingredient_id (FK CASCADE, unique)
├── quantity (Numeric 10,3)
├── last_inventory_date, created_at, updated_at
└── Methodes: is_low, is_empty, needs_inventory

restaurant_stock_movements
├── id, stock_id (FK CASCADE)
├── type (ENUM: ENTREE, SORTIE, AJUSTEMENT, PERTE, TRANSFERT)
├── quantity (Numeric 10,3)
├── date_mouvement, reference, notes
├── created_at, updated_at
└── Index: (stock_id), (date_mouvement), (type)
```

#### restaurant_consumptions
```
restaurant_consumptions
├── id, tenant_id
├── plat_id (FK CASCADE)
├── type (ENUM: VENTE, PERTE, REPAS_STAFF, OFFERT)
├── quantite (BigInt, nb portions)
├── prix_vente (BigInt, centimes)
├── cout (BigInt, cout unitaire au moment)
├── date, notes, created_at, updated_at
└── Index: (tenant_id, date), (plat_id)
```

### 1.3 Schema Epicerie/Approvisionnement

#### supply_orders / supply_order_lines
```
supply_orders
├── id, tenant_id
├── vendor_id (FK finance_vendors, RESTRICT)
├── reference, date_commande
├── date_livraison_prevue, date_livraison_reelle
├── statut (ENUM: en_attente, confirmee, expediee, livree, annulee)
├── montant_ht, montant_tva (centimes)
├── notes, created_by (FK users)
├── created_at, updated_at
└── Relations: vendor, lines, created_by

supply_order_lines
├── id, order_id (FK CASCADE)
├── produit_id (FK dim_produit, SET NULL)
├── designation, quantity (Numeric 10,3)
├── prix_unitaire (centimes)
├── received_quantity (Numeric 10,3)
├── notes, created_at, updated_at
└── Index: (order_id), (produit_id)
```

---

## 2. PROBLEMES IDENTIFIES

### 2.1 Absence de Catalogue Unifie
- Chaque fournisseur a sa propre table agregat avec structure differente
- `metro_produit_agregat` identifie par EAN
- `taiyat_produit_agregat` identifie par designation_clean
- `eurociel_produit_agregat` identifie par designation_clean
- `dim_produit` existe mais n'est pas systematiquement utilise

### 2.2 Liens Directs Ingredient-Produit
```
restaurant_epicerie_links
├── ingredient_id → restaurant_ingredients.id
└── produit_id → ID specifique d'un fournisseur (METRO ID, TAIYAT ID, etc.)
```
**Probleme:** Un ingredient est lie a UN produit specifique d'UN fournisseur.
- Si METRO n'a plus le produit → le lien est casse
- Pas de notion de "produit equivalent chez TAIYAT"
- Pas de priorite fournisseur

### 2.3 Pas de Notion d'Article Generique
- "Poulet entier" devrait etre un CONCEPT, pas un ID METRO
- Un "Poulet entier" peut etre fourni par METRO, EUROCIEL, ou TAI YAT
- Actuellement: on lie directement l'ingredient au produit METRO

### 2.4 Ratios Incoherents
Exemple constate:
```
Ingredient: "Chips de manioc"
├── Link 1: produit_id=45 (METRO), ratio=0.25 ???
└── Signification: 1 unite ingredient = 0.25 unite produit ?
```
Le ratio n'a pas de definition claire et semantique.

### 2.5 Prix Non Normalises
- METRO: prix_unitaire (par piece), prix_colis
- TAIYAT: prix_unitaire_ht, pas toujours de poids
- EUROCIEL: prix_unitaire (parfois au kg, parfois a l'unite)
- Pas de prix standardise au kg pour comparaison

### 2.6 Gestion Restaurant Trop Simpliste
Le modele actuel `restaurant_plat_ingredients` suppose:
- 1 plat = N ingredients avec quantites fixes
- Realite: menus, options, portions variables, calibres

---

## 3. COMPREHENSION METIER RESTAURANT

### 3.1 Structure des Ventes

#### Menus (Plat + Side)
La majorite des ventes sont des **MENUS** composes de:
- 1 Plat principal (sauce, bouillon, etc.)
- 1 Side/Accompagnement (au choix du client)

#### Les Sides (= Supplements)
| Side | Portion Standard | Notes |
|------|------------------|-------|
| Riz | 400g | + petite sauce tomate (portion sauce tomate) |
| Baton de manioc | 1 piece | |
| Plantain frit | 1 banane | Calibre standard, decoupe et frit |
| Foufou | Portion genereuse | Semoule traditionnelle |
| Ngari | Portion genereuse | Semoule |
| Semoule de ble | Portion genereuse | |

**Important:** Quand le client choisit RIZ, on ajoute automatiquement une petite portion de sauce tomate maison (la meme que le plat "Sauce Tomate" mais en portion reduite).

### 3.2 Preparation des Plats en Sauce

#### Processus de Production
```
1. Cuisine grosse marmite (ex: Mafe, Sauce Arachide, etc.)
   │
2. Portionnement sous vide
   │ → "Boule de Mafe" = portion standard
   │
3. Stockage frigo/congelateur
   │
4. A la commande: Rechauffage + eau + assaisonnements
   │
5. Ajout de la viande choisie (SEPAREE)
```

#### Portions Viande/Poisson
| Option | Portion |
|--------|---------|
| Viande (boeuf, poulet, etc.) | 250-300g |
| Demi-poisson (frit) | Calibre 300/500 (PM) |
| Poisson PM | Calibre 300/500 |
| Poisson GM | Calibre 800 |
| Poisson XL | Calibre 1000+ |
| Crevettes | 200g |
| Royal | Mix: viande + poisson + crevettes |

### 3.3 Calibres Poisson
| Taille | Poids |
|--------|-------|
| PM (Petit/Moyen) | 300-500g |
| GM (Gros/Moyen) | ~800g |
| XL | 1000g+ |
| Demi-poisson | = PM (300/500) coupe en 2 |

### 3.4 Modele de Cout Reel

Pour calculer le vrai cout d'un menu vendu, il faut:
```
Cout Menu = Cout_Base_Sauce
          + Cout_Viande_Option
          + Cout_Side
          + (Sauce_Tomate si Side=Riz)
```

Exemple: "Menu Mafe Viande + Riz"
```
├── Portion Mafe (base sauce) : X centimes
├── Portion Viande (300g boeuf) : Y centimes
├── Riz (400g) : Z centimes
└── Sauce Tomate (portion petite) : W centimes
= Total: X + Y + Z + W
```

### 3.5 Donnees Sumup (Futur)
Dans `/Sumup/`, il y a les exports de ventes avec en commentaire les options choisies.
Objectif futur: parser ces commentaires pour analyse intelligente des ventes.

---

## 4. ARCHITECTURE CIBLE

### 4.1 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COUCHE FOURNISSEURS (DWH)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ METRO        │ │ TAIYAT       │ │ EUROCIEL     │ │ OTHER        │       │
│  │ _facture     │ │ _facture     │ │ _facture     │ │ _produit_    │       │
│  │ _ligne       │ │ _ligne       │ │ _ligne       │ │  agregat     │       │
│  │ _agregat     │ │ _agregat     │ │ _agregat     │ │              │       │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘       │
│         │                │                │                │                │
│         └────────────────┼────────────────┼────────────────┘                │
│                          ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    epicerie_produits (NOUVEAU)                       │   │
│  │  Catalogue unifie de tous les produits fournisseurs                 │   │
│  │  - Deduplication par EAN                                            │   │
│  │  - Prix normalises (€/kg, €/unite)                                  │   │
│  │  - Tracabilite source                                               │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COUCHE REFERENTIEL METIER                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    epicerie_articles (NOUVEAU)                       │   │
│  │  Referentiel generique des articles                                 │   │
│  │  Ex: "Poulet entier", "Lait de coco", "Riz basmati"                │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
│                                │                                            │
│  ┌─────────────────────────────┼───────────────────────────────────────┐   │
│  │      epicerie_article_produits (NOUVEAU - Table de liaison)         │   │
│  │  Mapping N articles → N produits fournisseurs                       │   │
│  │  - Priorite par fournisseur                                         │   │
│  │  - Facteur de conversion                                            │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COUCHE RESTAURANT OPERATIONS                           │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────────────────────────────────┐   │
│  │ restaurant_     │     │ restaurant_ingredients (MODIFIE)            │   │
│  │ preparations    │     │ + article_id (FK epicerie_articles)         │   │
│  │ (NOUVEAU)       │     │ = Ingredient lie a un article generique     │   │
│  │ Sauces, bases   │     └─────────────────────────────────────────────┘   │
│  │ en marmite      │                          │                             │
│  └────────┬────────┘                          │                             │
│           │                                   ▼                             │
│           │         ┌─────────────────────────────────────────────────┐    │
│           │         │ restaurant_plat_ingredients (MODIFIE)           │    │
│           │         │ + type_quantite (FIXE, VARIABLE, CALIBRE)       │    │
│           └────────►│ + quantite_min, quantite_max                    │    │
│                     └─────────────────────────────────────────────────┘    │
│                                          │                                  │
│                                          ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    restaurant_plats (MODIFIE)                        │   │
│  │  + type_plat (SIMPLE, BASE_SAUCE, SIDE, SUPPLEMENT)                 │   │
│  │  + est_composable (bool) - peut etre combine en menu                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                          │                                  │
│                                          ▼                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    restaurant_menus (NOUVEAU)                        │   │
│  │  Definition des menus = plat_base + side + options                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                          │                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 restaurant_options_viande (NOUVEAU)                  │   │
│  │  Calibres et portions viande/poisson                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Flux de Donnees

#### Flux d'Import Fournisseur
```
PDF Facture METRO/TAIYAT/EUROCIEL
        │
        ▼
    ETL Extract
        │
        ▼
metro_ligne / taiyat_ligne / eurociel_ligne
        │
        ▼
Agregation (job nightly)
        │
        ▼
metro_produit_agregat / taiyat_produit_agregat / eurociel_produit_agregat
        │
        ▼
Sync vers epicerie_produits (NOUVEAU)
        │
        ▼
Matching automatique vers epicerie_articles
        │
        ▼
Mise a jour prix restaurant_ingredients
```

#### Flux de Calcul Cout Menu
```
Commande: "Menu Mafe Viande + Riz"
        │
        ▼
Decomposition:
├── restaurant_preparations.id = "Mafe" (portion base)
├── restaurant_options_viande.id = "Viande 300g"
├── restaurant_plats.id = "Riz" (side)
└── restaurant_plats.id = "Sauce Tomate Portion" (auto si riz)
        │
        ▼
Calcul cout unitaire de chaque composant
        │
        ▼
restaurant_consumptions avec detail complet
```

---

## 5. NOUVEAUX MODELES PROPOSES

### 5.1 epicerie_produits (Catalogue Unifie)

```sql
CREATE TABLE epicerie_produits (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),

    -- Identification
    ean VARCHAR(20),                    -- Code barre si disponible
    reference_interne VARCHAR(50),      -- Notre reference interne

    -- Designation
    designation_brute TEXT,             -- Designation originale fournisseur
    designation_clean VARCHAR(255),     -- Designation nettoyee/normalisee
    nom_court VARCHAR(80),              -- Nom affichable

    -- Classification
    famille VARCHAR(50),
    categorie VARCHAR(50),
    sous_categorie VARCHAR(50),

    -- Conditionnement
    unite_vente VARCHAR(10),            -- U, KG, L
    colisage INTEGER,                   -- Unites par colis
    poids_unitaire_kg NUMERIC(10,4),    -- Poids d'une unite en kg
    volume_unitaire_l NUMERIC(10,4),    -- Volume d'une unite en L

    -- Prix normalises (en centimes)
    prix_unitaire INTEGER,              -- Prix d'une unite
    prix_kg INTEGER,                    -- Prix au kg (calcule ou direct)
    prix_colis INTEGER,                 -- Prix d'un colis
    date_dernier_prix DATE,

    -- Tracabilite source
    fournisseur_source VARCHAR(20),     -- METRO, TAIYAT, EUROCIEL, OTHER
    fournisseur_produit_id BIGINT,      -- ID dans la table agregat source

    -- Statistiques
    nb_achats INTEGER DEFAULT 0,
    quantite_totale_achetee NUMERIC(12,3) DEFAULT 0,
    montant_total_achats INTEGER DEFAULT 0,
    premier_achat DATE,
    dernier_achat DATE,

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Index
    UNIQUE(tenant_id, ean) WHERE ean IS NOT NULL,
    UNIQUE(tenant_id, fournisseur_source, fournisseur_produit_id)
);

CREATE INDEX idx_epicerie_produits_tenant ON epicerie_produits(tenant_id);
CREATE INDEX idx_epicerie_produits_famille ON epicerie_produits(tenant_id, famille);
CREATE INDEX idx_epicerie_produits_designation ON epicerie_produits(tenant_id, designation_clean);
```

### 5.2 epicerie_articles (Referentiel Generique)

```sql
CREATE TABLE epicerie_articles (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),

    -- Identification
    code VARCHAR(20),                   -- Code interne (ex: "POULET-ENTIER")
    nom VARCHAR(100) NOT NULL,          -- Nom affichable
    description TEXT,

    -- Unite standard
    unite_standard VARCHAR(10),         -- KG, L, U - unite de reference

    -- Classification
    categorie VARCHAR(50),              -- VIANDE, POISSON, LEGUME, etc.
    sous_categorie VARCHAR(50),

    -- Prix de reference (en centimes, calcule depuis produits lies)
    prix_reference INTEGER,             -- Meilleur prix actuel
    prix_moyen INTEGER,                 -- Prix moyen pondere
    fournisseur_prefere_id BIGINT,      -- FK epicerie_produits

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, code)
);

CREATE INDEX idx_epicerie_articles_tenant ON epicerie_articles(tenant_id);
CREATE INDEX idx_epicerie_articles_categorie ON epicerie_articles(tenant_id, categorie);
```

### 5.3 epicerie_article_produits (Mapping Article → Produits)

```sql
CREATE TABLE epicerie_article_produits (
    id BIGSERIAL PRIMARY KEY,

    article_id BIGINT NOT NULL REFERENCES epicerie_articles(id) ON DELETE CASCADE,
    produit_id BIGINT NOT NULL REFERENCES epicerie_produits(id) ON DELETE CASCADE,

    -- Priorite et conversion
    priorite INTEGER DEFAULT 1,         -- 1 = prioritaire, 2, 3... = alternatives
    facteur_conversion NUMERIC(10,4),   -- 1 article = X produits

    -- Notes
    notes TEXT,

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(article_id, produit_id)
);

CREATE INDEX idx_article_produits_article ON epicerie_article_produits(article_id);
CREATE INDEX idx_article_produits_produit ON epicerie_article_produits(produit_id);
```

### 5.4 restaurant_ingredients (MODIFIE)

```sql
-- Ajouts a la table existante
ALTER TABLE restaurant_ingredients ADD COLUMN article_id BIGINT REFERENCES epicerie_articles(id) ON DELETE SET NULL;
ALTER TABLE restaurant_ingredients ADD COLUMN mode_calcul_prix VARCHAR(20) DEFAULT 'ARTICLE';
-- mode_calcul_prix: 'ARTICLE' (depuis article lie), 'MANUEL' (prix_unitaire fixe)

CREATE INDEX idx_restaurant_ingredients_article ON restaurant_ingredients(article_id);
```

### 5.5 restaurant_preparations (NOUVEAU)

```sql
CREATE TABLE restaurant_preparations (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),

    -- Identification
    nom VARCHAR(100) NOT NULL,          -- "Mafe", "Sauce Arachide", etc.
    description TEXT,

    -- Type
    type_preparation VARCHAR(30),       -- SAUCE, BOUILLON, MARINADE, BASE

    -- Production en batch
    quantite_batch NUMERIC(10,3),       -- Quantite produite par batch (en unite_batch)
    unite_batch VARCHAR(10),            -- KG, L, PORTIONS
    nb_portions_batch INTEGER,          -- Nombre de portions par batch

    -- Portion standard
    poids_portion_g INTEGER,            -- Grammes par portion
    cout_portion INTEGER,               -- Cout en centimes (calcule)

    -- Stockage
    duree_conservation_jours INTEGER,
    mode_conservation VARCHAR(20),      -- FRIGO, CONGELATEUR, SOUS_VIDE

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Composition d'une preparation (ingredients de base)
CREATE TABLE restaurant_preparation_ingredients (
    id BIGSERIAL PRIMARY KEY,
    preparation_id BIGINT NOT NULL REFERENCES restaurant_preparations(id) ON DELETE CASCADE,
    ingredient_id BIGINT NOT NULL REFERENCES restaurant_ingredients(id) ON DELETE CASCADE,
    quantite_batch NUMERIC(10,3),       -- Quantite pour 1 batch
    notes TEXT,

    UNIQUE(preparation_id, ingredient_id)
);
```

### 5.6 restaurant_plats (MODIFIE)

```sql
-- Ajouts a la table existante
ALTER TABLE restaurant_plats ADD COLUMN type_plat VARCHAR(30) DEFAULT 'SIMPLE';
-- type_plat: 'SIMPLE', 'BASE_SAUCE', 'SIDE', 'SUPPLEMENT', 'OPTION_VIANDE'

ALTER TABLE restaurant_plats ADD COLUMN est_composable BOOLEAN DEFAULT false;
-- true si peut etre utilise dans un menu

ALTER TABLE restaurant_plats ADD COLUMN preparation_id BIGINT REFERENCES restaurant_preparations(id) ON DELETE SET NULL;
-- Lien vers la preparation de base (pour les plats en sauce)

ALTER TABLE restaurant_plats ADD COLUMN ajout_sauce_tomate BOOLEAN DEFAULT false;
-- true si ce side necessite l'ajout auto de sauce tomate (ex: Riz)
```

### 5.7 restaurant_plat_ingredients (MODIFIE)

```sql
-- Ajouts a la table existante
ALTER TABLE restaurant_plat_ingredients ADD COLUMN type_quantite VARCHAR(20) DEFAULT 'FIXE';
-- type_quantite: 'FIXE', 'VARIABLE', 'CALIBRE'

ALTER TABLE restaurant_plat_ingredients ADD COLUMN quantite_min NUMERIC(10,3);
ALTER TABLE restaurant_plat_ingredients ADD COLUMN quantite_max NUMERIC(10,3);
-- Pour type_quantite = VARIABLE

ALTER TABLE restaurant_plat_ingredients ADD COLUMN calibre VARCHAR(20);
-- Pour type_quantite = CALIBRE (ex: 'PM', 'GM', 'XL', 'DEMI')
```

### 5.8 restaurant_options_viande (NOUVEAU)

```sql
CREATE TABLE restaurant_options_viande (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),

    -- Identification
    nom VARCHAR(50) NOT NULL,           -- "Viande", "Poisson PM", "Crevettes", "Royal"
    code VARCHAR(20),                   -- "VIANDE_300", "POISSON_PM", etc.

    -- Type
    type_option VARCHAR(20),            -- VIANDE, POISSON, CREVETTE, MIX

    -- Calibre (pour poisson)
    calibre VARCHAR(20),                -- PM, GM, XL, DEMI
    poids_min_g INTEGER,                -- Poids min (ex: 300)
    poids_max_g INTEGER,                -- Poids max (ex: 500)

    -- Quantite/Portion
    quantite_standard_g INTEGER,        -- Grammes par portion (ex: 300 pour viande)

    -- Composition (pour Royal = mix)
    composition JSONB,                  -- {"viande_g": 100, "poisson_g": 100, "crevette_g": 100}

    -- Ingredient lie (pour calcul cout)
    ingredient_id BIGINT REFERENCES restaurant_ingredients(id) ON DELETE SET NULL,

    -- Prix supplement (si different du prix standard)
    supplement_prix INTEGER DEFAULT 0,  -- Centimes en plus du prix menu

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, code)
);
```

### 5.9 restaurant_menus (NOUVEAU)

```sql
CREATE TABLE restaurant_menus (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id),

    -- Identification
    nom VARCHAR(100) NOT NULL,          -- "Menu Standard", "Menu Royal", etc.
    description TEXT,

    -- Prix
    prix_base INTEGER NOT NULL,         -- Prix de base du menu (centimes)

    -- Composition obligatoire
    plat_base_id BIGINT REFERENCES restaurant_plats(id),          -- Le plat principal (sauce)
    inclut_viande BOOLEAN DEFAULT true,
    inclut_side BOOLEAN DEFAULT true,

    -- Meta
    actif BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Options disponibles pour un menu
CREATE TABLE restaurant_menu_options (
    id BIGSERIAL PRIMARY KEY,
    menu_id BIGINT NOT NULL REFERENCES restaurant_menus(id) ON DELETE CASCADE,

    type_option VARCHAR(20),            -- 'VIANDE', 'SIDE'

    -- Lien vers l'option
    option_viande_id BIGINT REFERENCES restaurant_options_viande(id),
    plat_side_id BIGINT REFERENCES restaurant_plats(id),

    -- Supplement prix
    supplement INTEGER DEFAULT 0,       -- Centimes

    -- Defaut
    est_defaut BOOLEAN DEFAULT false
);
```

### 5.10 restaurant_consumptions (MODIFIE)

```sql
-- Ajouts pour tracer les ventes de menus avec detail
ALTER TABLE restaurant_consumptions ADD COLUMN menu_id BIGINT REFERENCES restaurant_menus(id) ON DELETE SET NULL;
ALTER TABLE restaurant_consumptions ADD COLUMN option_viande_id BIGINT REFERENCES restaurant_options_viande(id) ON DELETE SET NULL;
ALTER TABLE restaurant_consumptions ADD COLUMN side_id BIGINT REFERENCES restaurant_plats(id) ON DELETE SET NULL;
ALTER TABLE restaurant_consumptions ADD COLUMN detail_cout JSONB;
-- detail_cout: {"base": 150, "viande": 450, "side": 50, "sauce_tomate": 20}

-- Pour tracer d'ou vient la vente
ALTER TABLE restaurant_consumptions ADD COLUMN source VARCHAR(20);
-- source: 'CAISSE', 'SUMUP', 'MANUEL'
ALTER TABLE restaurant_consumptions ADD COLUMN reference_externe VARCHAR(100);
-- reference_externe: ID Sumup, numero ticket, etc.
```

---

## 6. ROADMAP DETAILLEE

### Phase 0: Preparation (Pre-requis)

#### 0.1 Audit des donnees existantes
- [ ] Exporter la liste complete de `restaurant_epicerie_links` actuels
- [ ] Identifier les liens incoherents (ratios absurdes, produits inactifs)
- [ ] Lister tous les `restaurant_ingredients` et leur usage dans les plats
- [ ] Documenter les plats actuels et leur vraie composition metier

#### 0.2 Backup et environnement de test
- [ ] Creer dump complet de la base
- [ ] Monter environnement de staging isole
- [ ] Preparer scripts de rollback

---

### Phase 1: Catalogue Unifie (epicerie_produits)

#### 1.1 Creation de la table
- [ ] Ecrire migration Alembic pour `epicerie_produits`
- [ ] Creer modele SQLAlchemy `EpicerieProduit`
- [ ] Creer repository `EpicerieProduitRepository`
- [ ] Creer schemas Pydantic (Create, Update, Read)

#### 1.2 Script de population initiale
- [ ] Script pour importer depuis `metro_produit_agregat`
- [ ] Script pour importer depuis `taiyat_produit_agregat`
- [ ] Script pour importer depuis `eurociel_produit_agregat`
- [ ] Script pour importer depuis `other_produit_agregat`
- [ ] Logique de deduplication par EAN
- [ ] Calcul des prix normalises (prix_kg)

#### 1.3 API Endpoints
- [ ] GET /api/v1/epicerie/produits (liste paginee, filtres)
- [ ] GET /api/v1/epicerie/produits/{id}
- [ ] GET /api/v1/epicerie/produits/search?q= (recherche)
- [ ] POST /api/v1/epicerie/produits (creation manuelle)
- [ ] PATCH /api/v1/epicerie/produits/{id}

#### 1.4 Sync automatique
- [ ] Job de sync post-agregation (apres import factures)
- [ ] Detection des nouveaux produits
- [ ] Mise a jour des prix existants

---

### Phase 2: Referentiel Articles (epicerie_articles)

#### 2.1 Creation des tables
- [ ] Migration Alembic pour `epicerie_articles`
- [ ] Migration Alembic pour `epicerie_article_produits`
- [ ] Modeles SQLAlchemy
- [ ] Repositories
- [ ] Schemas Pydantic

#### 2.2 Population du referentiel
- [ ] Creer les articles generiques de base:
  - Viandes: Poulet entier, Filet de boeuf, Boeuf bourguignon, etc.
  - Poissons: Thiof, Dorade, Bar, etc.
  - Legumes: Tomate, Oignon, Ail, etc.
  - Epicerie: Riz, Huile, Lait de coco, etc.
- [ ] Interface admin pour gestion du referentiel
- [ ] Import/Export CSV du referentiel

#### 2.3 Mapping Article → Produits
- [ ] Interface de liaison article/produit
- [ ] Suggestion automatique basee sur designation
- [ ] Gestion des priorites fournisseur

#### 2.4 API Endpoints
- [ ] CRUD complet /api/v1/epicerie/articles
- [ ] GET /api/v1/epicerie/articles/{id}/produits (produits lies)
- [ ] POST /api/v1/epicerie/articles/{id}/produits (lier un produit)
- [ ] DELETE /api/v1/epicerie/articles/{id}/produits/{produit_id}

---

### Phase 3: Migration restaurant_ingredients

#### 3.1 Modification du modele
- [ ] Migration Alembic: ajouter `article_id`, `mode_calcul_prix`
- [ ] Mettre a jour modele SQLAlchemy
- [ ] Mettre a jour schemas

#### 3.2 Migration des donnees
- [ ] Script d'analyse: pour chaque ingredient, trouver l'article correspondant
- [ ] Script de migration:
  - Lire `restaurant_epicerie_links`
  - Identifier le produit lie
  - Trouver/creer l'article generique
  - Mettre a jour `ingredient.article_id`
- [ ] Validation manuelle des mappings

#### 3.3 Deprecation restaurant_epicerie_links
- [ ] Garder la table en read-only temporairement
- [ ] Adapter les services pour utiliser la nouvelle structure
- [ ] Supprimer la table apres validation complete

---

### Phase 4: Gestion des Preparations (Sauces)

#### 4.1 Creation des tables
- [ ] Migration Alembic pour `restaurant_preparations`
- [ ] Migration Alembic pour `restaurant_preparation_ingredients`
- [ ] Modeles SQLAlchemy
- [ ] Repositories
- [ ] Schemas Pydantic

#### 4.2 Population des preparations
- [ ] Creer les preparations de base:
  - Mafe
  - Sauce Arachide
  - Sauce Tomate
  - Bouillon (Thieboudienne, etc.)
  - Yassa
  - etc.
- [ ] Definir les ingredients de chaque preparation (recette batch)
- [ ] Calculer le cout portion

#### 4.3 API Endpoints
- [ ] CRUD /api/v1/restaurant/preparations
- [ ] GET /api/v1/restaurant/preparations/{id}/ingredients
- [ ] POST /api/v1/restaurant/preparations/{id}/calculer-cout

---

### Phase 5: Refonte restaurant_plats

#### 5.1 Modification du modele
- [ ] Migration Alembic: ajouter colonnes (type_plat, est_composable, preparation_id, ajout_sauce_tomate)
- [ ] Mettre a jour modele SQLAlchemy
- [ ] Mettre a jour schemas

#### 5.2 Categorisation des plats existants
- [ ] Script pour categoriser automatiquement:
  - Plats en sauce → type_plat = 'BASE_SAUCE', lier a preparation
  - Accompagnements → type_plat = 'SIDE'
  - Supplements → type_plat = 'SUPPLEMENT'
- [ ] Identifier les plats composables
- [ ] Marquer le Riz avec `ajout_sauce_tomate = true`

#### 5.3 Modification restaurant_plat_ingredients
- [ ] Migration: ajouter type_quantite, quantite_min/max, calibre
- [ ] Adapter pour les quantites variables

---

### Phase 6: Options Viande/Poisson

#### 6.1 Creation de la table
- [ ] Migration Alembic pour `restaurant_options_viande`
- [ ] Modele SQLAlchemy
- [ ] Repository
- [ ] Schemas

#### 6.2 Population des options
- [ ] Creer les options de base:
  | Nom | Type | Calibre | Quantite |
  |-----|------|---------|----------|
  | Viande | VIANDE | - | 300g |
  | Poisson PM | POISSON | PM | 300-500g |
  | Poisson GM | POISSON | GM | ~800g |
  | Poisson XL | POISSON | XL | 1000g+ |
  | Demi-poisson | POISSON | DEMI | 150-250g |
  | Crevettes | CREVETTE | - | 200g |
  | Royal | MIX | - | composition |

#### 6.3 Liaison avec ingredients
- [ ] Lier chaque option a l'ingredient correspondant
- [ ] Configurer les supplements de prix

---

### Phase 7: Systeme de Menus

#### 7.1 Creation des tables
- [ ] Migration pour `restaurant_menus`
- [ ] Migration pour `restaurant_menu_options`
- [ ] Modeles, Repos, Schemas

#### 7.2 Configuration des menus
- [ ] Creer menu "Standard" (plat + viande/poisson + side)
- [ ] Definir les options disponibles pour chaque menu
- [ ] Configurer les supplements

#### 7.3 Calcul du cout menu
- [ ] Service de calcul: `calculer_cout_menu(menu_id, option_viande_id, side_id)`
- [ ] Prise en compte de la sauce tomate auto

---

### Phase 8: Modification restaurant_consumptions

#### 8.1 Modification du modele
- [ ] Migration: ajouter menu_id, option_viande_id, side_id, detail_cout, source, reference_externe
- [ ] Adapter modele et schemas

#### 8.2 Nouveau flux d'enregistrement
- [ ] Endpoint POST /api/v1/restaurant/consumptions/menu
  - Recoit: menu_id, option_viande_id, side_id, quantite
  - Calcule et stocke le detail des couts
- [ ] Endpoint legacy pour plats simples (backward compatible)

---

### Phase 9: Integration Sumup (Futur)

#### 9.1 Parser les exports Sumup
- [ ] Analyser le format des exports Sumup
- [ ] Identifier les patterns de commentaires (options)
- [ ] Script d'import

#### 9.2 Matching intelligent
- [ ] Matcher les ventes Sumup avec menus/plats
- [ ] Extraire les options des commentaires
- [ ] Creer les consumptions automatiquement

---

### Phase 10: Frontend & UI

#### 10.1 Page Catalogue Produits
- [ ] Liste des produits unifies avec filtres
- [ ] Fiche produit avec historique prix
- [ ] Comparaison fournisseurs

#### 10.2 Page Referentiel Articles
- [ ] CRUD articles
- [ ] Interface de mapping article/produits
- [ ] Gestion priorites

#### 10.3 Page Preparations
- [ ] Liste des preparations (sauces, bases)
- [ ] Edition recette batch
- [ ] Calcul cout portion

#### 10.4 Page Menus
- [ ] Configuration des menus
- [ ] Options disponibles
- [ ] Simulation cout

#### 10.5 Page Ventes Restaurant
- [ ] Saisie vente menu avec options
- [ ] Dashboard couts/marges

---

## ANNEXES

### A. Mapping Categories

| Categorie Fournisseur | Categorie Article | Exemple |
|----------------------|-------------------|---------|
| VOLAILLES | VIANDE | Poulet, Pintade |
| BOUCHERIE | VIANDE | Boeuf, Agneau |
| POISSONNERIE | POISSON | Thiof, Dorade |
| EPICERIE SALEE | EPICERIE | Riz, Huile |
| EPICERIE SUCREE | EPICERIE | Sucre, Confiture |
| FRUITS ET LEGUMES | LEGUME/FRUIT | Tomate, Oignon |
| BOISSONS | BOISSON | Sodas, Jus |

### B. Unites de Conversion

| Unite Source | Unite Standard | Facteur |
|--------------|----------------|---------|
| G | KG | 0.001 |
| ML | L | 0.001 |
| CL | L | 0.01 |
| U | U | 1 |

### C. Calibres Poisson EUROCIEL

| Code | Taille | Poids |
|------|--------|-------|
| 300/500 | PM | 300-500g |
| 500/800 | M | 500-800g |
| 800/1000 | GM | 800-1000g |
| 1000+ | XL | >1000g |

---

**FIN DU DOCUMENT**
