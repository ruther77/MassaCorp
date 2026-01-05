# Modèle Dimensionnel SID - NOUTAM SAS & L'Incontournable

## 1. Analyse du Modèle Transactionnel Existant

### 1.1 Structure Actuelle

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODÈLE OLTP ACTUEL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  tenants (1:Epicerie, 2:Restaurant)                            │
│       │                                                         │
│       ├── produits (2000+ articles)                            │
│       │       ├── produits_barcodes                            │
│       │       └── mouvements_stock                             │
│       │                                                         │
│       ├── restaurant_plats                                      │
│       │       └── restaurant_plat_ingredients                   │
│       │               └── restaurant_ingredients                │
│       │                                                         │
│       ├── restaurant_sales                                      │
│       ├── restaurant_depenses                                   │
│       └── restaurant_bank_statements                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Limites pour l'Analyse Décisionnelle

| Problème | Impact |
|----------|--------|
| Pas d'historisation temporelle structurée | Impossible d'analyser les tendances |
| Catégories non normalisées | Analyses par catégorie incohérentes |
| Pas de liaison stock épicerie ↔ consommation restaurant | Pas de vision flux inter-entités |
| Pas de dimension temps exploitable | Pas d'analyse par période/saison |

---

## 2. Modèle Dimensionnel Proposé (Schéma en Étoile)

### 2.1 Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA WAREHOUSE                                   │
│                    Schéma en Étoile Multi-Contexte                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌──────────────┐                              ┌──────────────┐       │
│    │  dim_temps   │                              │ dim_produit  │       │
│    │  (Date)      │◄─────────────────────────────│  (Produit)   │       │
│    └──────────────┘         ┌──────────────┐     └──────────────┘       │
│           │                 │              │            │               │
│           │    ┌────────────┤  FAITS_STOCK │◄───────────┤               │
│           └───►│            │  (Épicerie)  │            │               │
│                │            └──────────────┘            │               │
│    ┌──────────────┐                              ┌──────────────┐       │
│    │dim_fournisseur│                             │dim_categorie │       │
│    └──────────────┘◄────────────┬────────────────└──────────────┘       │
│           │                     │                       │               │
│           │         ┌───────────┴───────────┐           │               │
│           └────────►│     FAITS_ACHATS      │◄──────────┘               │
│                     │  (Approvisionnement)  │                           │
│                     └───────────────────────┘                           │
│                                                                         │
│    ┌──────────────┐     ┌───────────────────┐    ┌──────────────┐       │
│    │  dim_plat    │◄────┤   FAITS_VENTES    │───►│ dim_canal    │       │
│    │ (Restaurant) │     │   (Restaurant)     │    │  (Source)    │       │
│    └──────────────┘     └───────────────────┘    └──────────────┘       │
│           │                      │                      │               │
│           │             ┌────────┴────────┐             │               │
│           │             │  FAITS_MARGES   │             │               │
│           └────────────►│  (Restaurant)   │◄────────────┘               │
│                         └─────────────────┘                             │
│                                                                         │
│    ┌──────────────┐     ┌───────────────────┐    ┌──────────────┐       │
│    │dim_cost_center│◄───┤  FAITS_DEPENSES   │───►│dim_categorie │       │
│    └──────────────┘     │    (Global)       │    │   _depense   │       │
│                         └───────────────────┘    └──────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tables de Dimensions

### 3.1 dim_temps (Dimension Temporelle - SCD Type 0)

**Grain** : 1 ligne = 1 jour

| Colonne | Type | Description |
|---------|------|-------------|
| `date_id` | INT PK | Clé technique (YYYYMMDD) |
| `date_complete` | DATE | Date réelle |
| `jour` | INT | Jour du mois (1-31) |
| `jour_semaine` | INT | Lundi=1 ... Dimanche=7 |
| `nom_jour` | TEXT | Lundi, Mardi... |
| `semaine_iso` | INT | N° semaine ISO |
| `mois` | INT | Mois (1-12) |
| `nom_mois` | TEXT | Janvier, Février... |
| `trimestre` | INT | T1, T2, T3, T4 |
| `annee` | INT | Année |
| `annee_mois` | TEXT | 2025-01 |
| `est_weekend` | BOOLEAN | Samedi/Dimanche |
| `est_ferie` | BOOLEAN | Jour férié FR |
| `saison` | TEXT | Printemps, Été... |

### 3.2 dim_produit (Dimension Produit - SCD Type 2)

**Grain** : 1 ligne = 1 version produit

| Colonne | Type | Description |
|---------|------|-------------|
| `produit_sk` | SERIAL PK | Clé surrogate |
| `produit_id` | INT | Clé naturelle (produits.id) |
| `tenant_id` | INT | 1=Épicerie, 2=Restaurant |
| `nom` | TEXT | Nom du produit |
| `categorie_id` | INT FK | Lien dim_categorie |
| `prix_achat` | NUMERIC | Prix d'achat HT |
| `prix_vente` | NUMERIC | Prix de vente TTC |
| `tva_pct` | NUMERIC | Taux TVA |
| `marge_unitaire` | NUMERIC | Calculé |
| `marge_pct` | NUMERIC | Calculé |
| `date_debut` | DATE | Début validité |
| `date_fin` | DATE | Fin validité (NULL=actif) |
| `est_actuel` | BOOLEAN | Version courante |

### 3.3 dim_categorie (Dimension Catégorie - SCD Type 1)

**Grain** : 1 ligne = 1 catégorie

| Colonne | Type | Description |
|---------|------|-------------|
| `categorie_id` | SERIAL PK | Clé technique |
| `tenant_id` | INT | Tenant |
| `code` | TEXT | Code court |
| `nom` | TEXT | Nom affiché |
| `famille` | TEXT | Regroupement niveau 1 |
| `sous_famille` | TEXT | Regroupement niveau 2 |
| `tva_defaut` | NUMERIC | TVA par défaut |

**Mapping catégories existantes :**
```
Épicerie:
  - Epicerie sucree → Famille: Alimentaire, Sous-famille: Sucré
  - Epicerie salee  → Famille: Alimentaire, Sous-famille: Salé
  - Boissons        → Famille: Boissons, Sous-famille: Soft/Alcool
  - Alcool          → Famille: Boissons, Sous-famille: Alcool
  - Hygiene         → Famille: Non-alimentaire, Sous-famille: Hygiène
  - Afrique         → Famille: Alimentaire, Sous-famille: Monde
  
Restaurant:
  - Entrées, Plats, Desserts, Boissons...
```

### 3.4 dim_fournisseur (Dimension Fournisseur - SCD Type 2)

| Colonne | Type | Description |
|---------|------|-------------|
| `fournisseur_sk` | SERIAL PK | Clé surrogate |
| `fournisseur_id` | INT | Clé naturelle |
| `tenant_id` | INT | Tenant |
| `nom` | TEXT | Nom fournisseur |
| `type` | TEXT | Grossiste/Direct/Marché |
| `siret` | TEXT | SIRET |
| `delai_paiement` | INT | Jours |
| `est_actuel` | BOOLEAN | Version courante |

### 3.5 dim_plat (Dimension Plat Restaurant - SCD Type 2)

| Colonne | Type | Description |
|---------|------|-------------|
| `plat_sk` | SERIAL PK | Clé surrogate |
| `plat_id` | INT | Clé naturelle |
| `tenant_id` | INT | Tenant |
| `nom` | TEXT | Nom du plat |
| `categorie` | TEXT | Entrée/Plat/Dessert |
| `prix_vente_ttc` | NUMERIC | Prix carte |
| `cout_matiere` | NUMERIC | Coût ingrédients |
| `marge_brute` | NUMERIC | Calculé |
| `ratio_cout` | NUMERIC | % food cost |
| `nb_ingredients` | INT | Complexité |
| `est_actuel` | BOOLEAN | Version courante |

### 3.6 dim_cost_center (Centres de Coûts - SCD Type 1)

| Colonne | Type | Description |
|---------|------|-------------|
| `cost_center_id` | SERIAL PK | Clé technique |
| `tenant_id` | INT | Tenant |
| `nom` | TEXT | Nom du centre |
| `type` | TEXT | Fixe/Variable |
| `budget_mensuel` | NUMERIC | Budget prévu |

---

## 4. Tables de Faits

### 4.1 fait_mouvements_stock (Épicerie)

**Grain** : 1 ligne = 1 mouvement de stock
**Contexte** : Analyse des flux de stock épicerie

| Colonne | Type | Description |
|---------|------|-------------|
| `mouvement_id` | SERIAL PK | Identifiant |
| `date_id` | INT FK | → dim_temps |
| `produit_sk` | INT FK | → dim_produit |
| `fournisseur_sk` | INT FK | → dim_fournisseur (nullable) |
| `type_mouvement` | TEXT | ENTREE/SORTIE/INVENTAIRE |
| `quantite` | NUMERIC | Quantité (toujours +) |
| `sens` | INT | +1 (entrée) / -1 (sortie) |
| `prix_unitaire` | NUMERIC | Prix à la date |
| `valeur_mouvement` | NUMERIC | qté × prix |
| `source` | TEXT | Origine (facture, vente...) |

**Mesures agrégables :**
- `SUM(quantite * sens)` → Variation nette
- `SUM(valeur_mouvement * sens)` → Valeur flux
- `COUNT(*)` → Nombre d'opérations

### 4.2 fait_ventes_restaurant

**Grain** : 1 ligne = 1 vente plat
**Contexte** : Analyse CA et volumes restaurant

| Colonne | Type | Description |
|---------|------|-------------|
| `vente_id` | SERIAL PK | Identifiant |
| `date_id` | INT FK | → dim_temps |
| `plat_sk` | INT FK | → dim_plat |
| `canal` | TEXT | Salle/Emporter/Livraison |
| `source` | TEXT | Caisse/UberEats/Deliveroo |
| `quantite` | NUMERIC | Nb vendus |
| `ca_ttc` | NUMERIC | qté × prix TTC |
| `ca_ht` | NUMERIC | CA HT |
| `cout_matiere` | NUMERIC | qté × coût matière |
| `marge_brute` | NUMERIC | CA HT - coût |

**KPIs :**
- CA par jour/semaine/mois
- Ticket moyen
- Food cost ratio
- Top/Flop ventes

### 4.3 fait_depenses (Global)

**Grain** : 1 ligne = 1 dépense
**Contexte** : Suivi des charges

| Colonne | Type | Description |
|---------|------|-------------|
| `depense_id` | SERIAL PK | Identifiant |
| `date_id` | INT FK | → dim_temps |
| `tenant_id` | INT | 1=Épicerie, 2=Restaurant |
| `cost_center_id` | INT FK | → dim_cost_center |
| `categorie_id` | INT FK | → dim_categorie_depense |
| `fournisseur_sk` | INT FK | → dim_fournisseur |
| `libelle` | TEXT | Description |
| `montant_ht` | NUMERIC | Montant HT |
| `tva` | NUMERIC | TVA |
| `montant_ttc` | NUMERIC | Total TTC |

### 4.4 fait_stock_quotidien (Snapshot)

**Grain** : 1 ligne = 1 produit × 1 jour
**Contexte** : Photo stock fin de journée (pour rotation, ruptures)

| Colonne | Type | Description |
|---------|------|-------------|
| `snapshot_id` | SERIAL PK | Identifiant |
| `date_id` | INT FK | → dim_temps |
| `produit_sk` | INT FK | → dim_produit |
| `stock_quantite` | NUMERIC | Qté en stock |
| `stock_valeur` | NUMERIC | Valorisation |
| `jours_stock` | NUMERIC | Stock / conso moyenne |
| `est_rupture` | BOOLEAN | Stock ≤ seuil |
| `est_surstock` | BOOLEAN | Stock > 2× rotation |

---

## 5. Schéma des Relations

```
                    ┌─────────────────┐
                    │   dim_temps     │
                    │   (date_id)     │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┬─────────────────┐
        │                    │                    │                 │
        ▼                    ▼                    ▼                 ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐  ┌───────────────┐
│fait_mouvements│   │ fait_ventes   │   │fait_depenses  │  │fait_stock_quot│
│    _stock     │   │  _restaurant  │   │               │  │   idien       │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘  └───────┬───────┘
        │                   │                   │                  │
        ▼                   ▼                   ▼                  ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐  ┌───────────────┐
│  dim_produit  │   │   dim_plat    │   │dim_cost_center│  │  dim_produit  │
└───────┬───────┘   └───────────────┘   └───────────────┘  └───────────────┘
        │                                       │
        ▼                                       ▼
┌───────────────┐                       ┌───────────────┐
│dim_fournisseur│                       │dim_categorie_ │
└───────────────┘                       │    depense    │
        │                               └───────────────┘
        ▼
┌───────────────┐
│ dim_categorie │
└───────────────┘
```

---

## 6. Exemples de Requêtes Analytiques

### 6.1 Top 10 produits par marge (Épicerie)

```sql
SELECT 
    p.nom,
    c.famille,
    SUM(f.quantite) as volume,
    SUM(f.valeur_mouvement) as ca,
    SUM(f.quantite * p.marge_unitaire) as marge_totale
FROM fait_mouvements_stock f
JOIN dim_produit p ON f.produit_sk = p.produit_sk
JOIN dim_categorie c ON p.categorie_id = c.categorie_id
JOIN dim_temps t ON f.date_id = t.date_id
WHERE f.type_mouvement = 'SORTIE'
  AND t.annee = 2025
  AND p.est_actuel = TRUE
GROUP BY p.nom, c.famille
ORDER BY marge_totale DESC
LIMIT 10;
```

### 6.2 CA Restaurant par mois et canal

```sql
SELECT 
    t.annee_mois,
    v.canal,
    SUM(v.ca_ttc) as ca_total,
    SUM(v.marge_brute) as marge,
    ROUND(SUM(v.cout_matiere) / NULLIF(SUM(v.ca_ht), 0) * 100, 1) as food_cost_pct
FROM fait_ventes_restaurant v
JOIN dim_temps t ON v.date_id = t.date_id
GROUP BY t.annee_mois, v.canal
ORDER BY t.annee_mois, ca_total DESC;
```

### 6.3 Évolution stock par catégorie

```sql
SELECT 
    t.nom_mois,
    c.famille,
    AVG(s.stock_valeur) as valeur_moyenne,
    SUM(CASE WHEN s.est_rupture THEN 1 ELSE 0 END) as nb_ruptures,
    AVG(s.jours_stock) as rotation_moyenne
FROM fait_stock_quotidien s
JOIN dim_temps t ON s.date_id = t.date_id
JOIN dim_produit p ON s.produit_sk = p.produit_sk
JOIN dim_categorie c ON p.categorie_id = c.categorie_id
WHERE t.annee = 2025
GROUP BY t.mois, t.nom_mois, c.famille
ORDER BY t.mois, c.famille;
```

### 6.4 Analyse des dépenses par centre de coût

```sql
SELECT 
    cc.nom as centre_cout,
    t.trimestre,
    SUM(d.montant_ht) as total_ht,
    cc.budget_mensuel * 3 as budget_trim,
    ROUND((SUM(d.montant_ht) / (cc.budget_mensuel * 3)) * 100, 1) as execution_pct
FROM fait_depenses d
JOIN dim_cost_center cc ON d.cost_center_id = cc.cost_center_id
JOIN dim_temps t ON d.date_id = t.date_id
WHERE t.annee = 2025
GROUP BY cc.nom, cc.budget_mensuel, t.trimestre
ORDER BY t.trimestre, total_ht DESC;
```

---

## 7. Processus ETL Recommandé

### 7.1 Fréquence de Chargement

| Table | Fréquence | Source |
|-------|-----------|--------|
| dim_temps | Annuel (pré-généré 5 ans) | Script |
| dim_produit | À chaque modif prix | Trigger sur produits |
| dim_plat | À chaque modif prix | Trigger sur restaurant_plats |
| fait_mouvements_stock | Temps réel | Trigger sur mouvements_stock |
| fait_ventes_restaurant | Temps réel | Trigger sur restaurant_sales |
| fait_stock_quotidien | Quotidien 23h | Job planifié |
| fait_depenses | Import batch | Intégration bancaire |

### 7.2 Règles d'Historisation (SCD)

**Type 0 (dim_temps)** : Jamais modifié après création

**Type 1 (dim_categorie, dim_cost_center)** : Écrasement simple, pas d'historique

**Type 2 (dim_produit, dim_plat, dim_fournisseur)** :
- Nouvelle ligne à chaque changement de prix
- `date_fin` = veille du changement pour ancienne ligne
- `est_actuel` = FALSE pour ancienne ligne
- Préserve les faits historiques avec le bon prix

---

## 8. Prochaines Étapes

1. **Valider les catégories** : Nettoyer et normaliser les catégories produits
2. **Créer les tables dimensionnelles** : Exécuter le script SQL
3. **Migrer les données historiques** : Script ETL initial
4. **Mettre en place les triggers** : Alimentation temps réel
5. **Créer les vues BI** : Vues pré-agrégées pour tableaux de bord
6. **Connecter l'outil de visualisation** : React dashboard ou Metabase

---

*Document généré pour NOUTAM SAS & L'Incontournable*
*Architecture SID Multi-Tenant*
