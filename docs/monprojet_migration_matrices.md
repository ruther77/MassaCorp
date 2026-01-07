# Matrice de Migration Fonctionnelle - monprojet → MassaCorp (Épicerie / Finances / Restaurant)

**Date**: 2026-01-05  
**Version**: 1.0  
**Scope**: Frontend (tables + modals/drawers), mapping DWH, endpoints cibles  
**Cible UX**: newCMS amélioré (niveau entreprise), modals/drawers comme monprojet

---

## Table des matières

1. [Résumé exécutif](#1-resume-executif)
2. [Décisions de cadrage](#2-decisions-de-cadrage)
3. [Matrices Épicerie (Opérations)](#3-matrices-epicerie-operations)
4. [Matrices Finances](#4-matrices-finances)
5. [Matrices Restaurant](#5-matrices-restaurant)
6. [Écarts techniques & DWH](#6-ecarts-techniques--dwh)
7. [Prochaines étapes](#7-prochaines-etapes)

---

## 1. Résumé exécutif

- Les **factures basculent entièrement dans Finances** (pas dans Opérations).
- Le **style visuel cible** est newCMS, mais **structuré entreprise** (grille, hiérarchie, états, KPIs).
- Les données **DWH sont la source canonique** (catalogue + finance).
- Les **détails se font en modals/drawers** (comme monprojet).
- Responsive requis: **tables desktop + cartes/swipe mobile**.

---

## 2. Décisions de cadrage

| Décision | Valeur |
| --- | --- |
| Factures | Déplacées vers Finances |
| UI cible | newCMS amélioré (entreprise) |
| Source canonique | DWH (catalog/finance) |
| Détails | Modals + drawers |
| Responsive | Tables + cartes mobile |

---

## 3. Matrices Épicerie (Opérations)

### 3.1 Tables

#### EP-01 – Catalogue (SmartTable + cartes)
| Champ | Détail |
| --- | --- |
| UI source | CatalogSmartDemo |
| Fichier source | `monprojet/frontend/src/features/catalog/CatalogSmartDemo.jsx` |
| Colonnes | produit (nom,id), catégorie, prix achat, prix vente, stock, marge, actions |
| API source | GET `/catalog/products` ; PATCH `/catalog/products/:id` ; DELETE `/catalog/products/:id` |
| Route cible | `/operations/catalog` |
| Modèle DWH | `ProduitListItem` |
| Hook cible | `catalogApi.getProducts` / `useProducts` |
| Mapping DWH | id→produit_id, nom→nom, catégorie→categorie_nom, prix_achat, prix_vente, stock_actuel, marge_pct |
| Écart | UI MassaCorp catalogue utilise `/metro/*` |
| Notes | Remplacer `/metro/*` par DWH ; conserver cards mobile + drawer |

#### EP-02 – Stock produits
| Champ | Détail |
| --- | --- |
| UI source | StockPage |
| Fichier source | `monprojet/frontend/src/features/stock/StockPage.jsx` |
| Colonnes | produit, stock+unité, niveau, rotation, actions |
| API source | GET `/catalog/products` ; GET `/stock/movements/recent` |
| Route cible | `/operations/stock` |
| Modèle DWH | `ProduitListItem` + `ProduitDetail` |
| Hook cible | `catalogApi.getProducts` ; `catalogApi.getProductDetail` |
| Mapping DWH | stock_actuel, seuil_alerte, unité (dim), rotation (conso_moy_30j) |
| Écart | champ unité non standard DWH |
| Notes | Niveau calculé en DWH ou côté UI |

#### EP-03 – Mouvements stock (journal)
| Champ | Détail |
| --- | --- |
| UI source | StockMovementsPage |
| Fichier source | `monprojet/frontend/src/features/stock/StockMovementsPage.jsx` |
| Colonnes | date, produit, type, quantité, source |
| API source | GET `/stock/movements/recent` |
| Route cible | `/operations/stock/movements` |
| Modèle DWH | `MouvementStock` |
| Hook cible | nouveau endpoint DWH |
| Mapping DWH | date, type_mouvement, quantite, source |
| Écart | endpoint DWH manquant |
| Notes | besoin pagination |

#### EP-04 – Alertes prix/stock
| Champ | Détail |
| --- | --- |
| UI source | PricesPage |
| Fichier source | `monprojet/frontend/src/features/prices/PricesPage.jsx` |
| Colonnes | produit, prix achat, marge %, rupture |
| API source | GET `/prices/history` |
| Route cible | `/operations/prix` |
| Modèle DWH | vue price_history |
| Hook cible | nouveau endpoint DWH |
| Mapping DWH | produit_nom, code, prix_achat, marge_pct, stock_alert |
| Écart | endpoint DWH manquant |

#### EP-05 – Historique des prix
| Champ | Détail |
| --- | --- |
| UI source | PricesPage |
| Fichier source | `monprojet/frontend/src/features/prices/PricesPage.jsx` |
| Colonnes | date, produit, code, fournisseur, prix, delta, marge, quantité, montant, contexte |
| API source | GET `/prices/history` |
| Route cible | `/operations/prix` |
| Modèle DWH | fact_invoice_line + dims |
| Hook cible | nouveau endpoint DWH |
| Écart | endpoint DWH manquant |
| Notes | delta_prix/delta_pct calculés côté API |

#### EP-06 – Plan d’approvisionnement (principal)
| Champ | Détail |
| --- | --- |
| UI source | SupplyPage |
| Fichier source | `monprojet/frontend/src/features/supply/SupplyPage.jsx` |
| Colonnes | produit, catégorie, ventes/j, stock, couverture, priorité, qté, valeur, fournisseur |
| API source | GET `/supply/plan` |
| Route cible | `/operations/approvisionnement` |
| Modèle DWH | vue supply_plan |
| Hook cible | nouveau endpoint DWH |
| Écart | endpoint DWH manquant |
| Notes | nécessite forecast ventes |

#### EP-07 – Plan d’approvisionnement (fournisseurs)
| Champ | Détail |
| --- | --- |
| UI source | SupplyPage |
| Fichier source | `monprojet/frontend/src/features/supply/SupplyPage.jsx` |
| Colonnes | fournisseur, références, quantité, valeur, marge, actions |
| API source | GET `/supply/plan` (supplier_breakdown) |
| Route cible | `/operations/approvisionnement` |
| Modèle DWH | vue supply_plan |
| Hook cible | même endpoint EP-06 |
| Écart | endpoint DWH manquant |

### 3.2 Modals / Drawers

#### EP-M01 – Ajouter produit
| Champ | Détail |
| --- | --- |
| UI source | AddProductModal |
| Fichier source | `monprojet/frontend/src/components/modals/AddProductModal.jsx` |
| Champs | nom, catégorie, prix achat, prix vente, stock, seuil, unité, codes, fournisseur |
| API source | POST `/catalog/products` |
| Modèle DWH | dimension produit + faits stock |
| Écart | écriture DWH à valider (gouvernance) |
| Notes | audit trail obligatoire |

#### EP-M02 – Éditer produit
| Champ | Détail |
| --- | --- |
| UI source | EditProductModal |
| Fichier source | `monprojet/frontend/src/components/modals/EditProductModal.jsx` |
| Champs | mêmes que EP-M01 |
| API source | PATCH `/catalog/products/:id` |
| Écart | écriture DWH à valider |

#### EP-M03 – Ajustement stock
| Champ | Détail |
| --- | --- |
| UI source | StockAdjustmentModal |
| Fichier source | `monprojet/frontend/src/components/modals/StockAdjustmentModal.jsx` |
| Champs | mode, quantité, raison, note |
| API source | POST `/stock/adjustments` |
| Écart | endpoint DWH manquant |
| Notes | raison et note doivent être persistées |

#### EP-M04 – Détail produit (drawer)
| Champ | Détail |
| --- | --- |
| UI source | ProductDetailDrawer |
| Fichier source | `monprojet/frontend/src/components/modals/ProductDetailDrawer.jsx` |
| Champs | KPIs stock/marge, prix, mouvements, dernier achat |
| API source | GET `/catalog/products/:id/detail` |
| DWH cible | `ProduitDetail` |
| Notes | aligner avec `frontend/src/components/catalog/ProductDetailDrawer.tsx` |

#### EP-M05 – Créer commande fournisseur
| Champ | Détail |
| --- | --- |
| UI source | CreateOrderModal |
| Fichier source | `monprojet/frontend/src/components/modals/CreateOrderModal.jsx` |
| Champs | fournisseur, items, quantités, livraison, notes |
| API source | client-side (CSV/PDF) |
| Écart | persistance PO à décider |

#### EP-M06 – Import factures (déplacé)
| Champ | Détail |
| --- | --- |
| UI source | InvoiceImportModal |
| Fichier source | `monprojet/frontend/src/components/modals/InvoiceImportModal.jsx` |
| Destination | Finances (FIN-M06) |
| Notes | conserver UX dropzone |

---

## 4. Matrices Finances

### 4.1 Tables

#### FIN-01 – Transactions
| Champ | Détail |
| --- | --- |
| UI source | FinanceTransactionsPage |
| Fichier source | `monprojet/frontend/src/features/finance/FinanceTransactionsPage.jsx` |
| Colonnes | date, libellé, montant, catégorie, compte, statut |
| API source | GET `/finance/transactions/search` |
| Route cible | `/finances/transactions` |
| Modèle DWH | `BankMovement` |
| Hook cible | `bankMovementsApi.getAll` + categorize |
| Mapping DWH | date_operation, libelle, montant, compte_bancaire, categorie_depense, est_rapproche |
| Écart | champs IA (confidence/prediction) absents |

#### FIN-02 – Rapprochement (transactions)
| Champ | Détail |
| --- | --- |
| UI source | BankReconciliationPage |
| Fichier source | `monprojet/frontend/src/features/finance/BankReconciliationPage.jsx` |
| Colonnes | date, libellé, montant, match_status, actions |
| Route cible | `/finances/rapprochement` |
| Modèle DWH | BankMovement + liens paiement/facture |
| Écart | endpoints reconciliation manquants |

#### FIN-03 – Rapprochement (factures)
| Champ | Détail |
| --- | --- |
| UI source | BankReconciliationPage |
| Fichier source | `monprojet/frontend/src/features/finance/BankReconciliationPage.jsx` |
| Colonnes | date, fournisseur, numéro, montant, match_status |
| Route cible | `/finances/rapprochement` |
| Modèle DWH | Invoice |
| Écart | match_status non exposé |

#### FIN-04 – Règles de catégorisation
| Champ | Détail |
| --- | --- |
| UI source | FinanceRulesPage |
| Fichier source | `monprojet/frontend/src/features/finance/FinanceRulesPage.jsx` |
| Colonnes | nom, entity_id, catégorie, mots-clés, match_count, statut |
| Route cible | `/finances/regles` |
| Modèle DWH | finance_rule |
| Écart | endpoints rules manquants |

#### FIN-05 – Test de règle (table)
| Champ | Détail |
| --- | --- |
| UI source | TestRuleModal |
| Fichier source | `monprojet/frontend/src/features/finance/FinanceRulesPage.jsx` |
| Colonnes | date, libellé, montant, catégorie |
| Modèle DWH | BankMovement |
| Écart | recherche full-text à prévoir |

#### FIN-06 – Anomalies
| Champ | Détail |
| --- | --- |
| UI source | FinanceAnomaliesPage |
| Fichier source | `monprojet/frontend/src/features/finance/FinanceAnomaliesPage.jsx` |
| Colonnes | type, montant, confidence, statut |
| Modèle DWH | finance_anomaly |
| Écart | endpoints anomalies manquants |

#### FIN-07 – Overview (dernières transactions)
| Champ | Détail |
| --- | --- |
| UI source | FinanceOverview |
| Fichier source | `monprojet/frontend/src/features/finance/FinanceOverview.jsx` |
| Colonnes | date, libellé, catégorie, compte, montant |
| Route cible | `/finances` |
| Modèle DWH | BankMovement |

#### FIN-08 – Liste factures (migrée)
| Champ | Détail |
| --- | --- |
| UI source | InvoicesListPage |
| Fichier source | `monprojet/frontend/src/features/invoices/InvoicesListPage.jsx` |
| Route cible | `/finances/factures` |
| Modèle DWH | Invoice |
| Notes | aligner UI MassaCorp avec newCMS |

#### FIN-09 – Détail facture (lignes)
| Champ | Détail |
| --- | --- |
| UI source | InvoiceDetailPage |
| Fichier source | `MassaCorp/frontend/src/pages/finance/InvoiceDetailPage.tsx` |
| Colonnes | designation, quantite, prix, tva, montant |
| Modèle DWH | InvoiceLine |
| Notes | prévoir drawer détail rapide |

### 4.2 Modals / Drawers

#### FIN-M01 – Détail transaction (modal/drawer)
| Champ | Détail |
| --- | --- |
| UI source | FinanceTransactionsPage |
| Champs | libellé, date, montant, catégorie, compte, statut, IA |
| Écart | champs IA à stocker |

#### FIN-M02 – Catégorisation transaction (modal)
| Champ | Détail |
| --- | --- |
| UI source | FinanceTransactionsPage |
| Champs | catégorie |
| API cible | `bankMovementsApi.categorize` |

#### FIN-M03 – Rapprochement manuel (modal global)
| Champ | Détail |
| --- | --- |
| UI source | BankReconciliationPage |
| Champs | transaction + facture + différence |
| Écart | endpoints reconciliation manquants |

#### FIN-M04 – Création/édition règle
| Champ | Détail |
| --- | --- |
| UI source | FinanceRulesPage |
| Champs | nom, catégorie, mots-clés, actif |
| Écart | endpoints rules manquants |

#### FIN-M05 – Test règle
| Champ | Détail |
| --- | --- |
| UI source | TestRuleModal |
| Champs | résultats matching |
| Écart | recherche full-text |

#### FIN-M06 – Import factures (nouvelle entrée)
| Champ | Détail |
| --- | --- |
| UI source | InvoiceImportModal |
| Champs | fichiers, options import |
| Route cible | `/finances/factures/import` |
| Écart | endpoint import à confirmer |

#### FIN-M07 – Drawer détail facture (nouveau)
| Champ | Détail |
| --- | --- |
| UI source | à créer |
| Champs | résumé facture + lignes |
| Notes | demandé “détails modals pour les deux entités” |

---

## 5. Matrices Restaurant

### 5.1 Tables

#### REST-01 – Ingrédients
| Champ | Détail |
| --- | --- |
| UI source | IngredientsPage |
| Fichier source | `monprojet/frontend/src/features/restaurant/IngredientsPage.jsx` |
| Colonnes | ingrédient, prix unitaire, stock, tendance, historique, actions |
| API source | GET `/restaurant/ingredients` |
| Route cible | `/restaurant/ingredients` |
| Écart | domaine restaurant absent dans MassaCorp |

#### REST-02 – Stock ingrédients
| Champ | Détail |
| --- | --- |
| UI source | RestaurantStockMovementsPage |
| Fichier source | `monprojet/frontend/src/features/restaurant/RestaurantStockMovementsPage.jsx` |
| Colonnes | ingrédient, stock, niveau, statut, catégorie |
| API source | GET `/restaurant/stock/summary` |
| Route cible | `/restaurant/stock` |
| Écart | domaine restaurant absent |

#### REST-03 – Consommations
| Champ | Détail |
| --- | --- |
| UI source | RestaurantConsumptionPage |
| Fichier source | `monprojet/frontend/src/features/restaurant/RestaurantConsumptionPage.jsx` |
| Colonnes | produit épicerie, plat, prix achat, stock, consommé, coût |
| API source | GET `/restaurant/consumptions` |
| Route cible | `/restaurant/consumptions` |
| Écart | domaine restaurant absent |

#### REST-04 – Liens Épicerie ↔ Ingrédients
| Champ | Détail |
| --- | --- |
| UI source | IngredientEpicerieLinkPage |
| Fichier source | `monprojet/frontend/src/features/restaurant/IngredientEpicerieLinkPage.jsx` |
| Colonnes | ingrédient, produit épicerie, ratio, catégorie, prix achat |
| API source | GET `/restaurant/ingredients` + `/restaurant/epicerie/products/search` |
| Route cible | `/restaurant/link-epicerie` |
| Écart | domaine restaurant absent |

### 5.2 Modals / Drawers

#### REST-M01 – Détail plat (modal)
| Champ | Détail |
| --- | --- |
| UI source | PlatDetailModal |
| Fichier source | `monprojet/frontend/src/features/restaurant/components/PlatDetailModal.jsx` |
| Champs | fiche technique, ingrédients, coût, historique prix |
| Écart | endpoints restaurant manquants |

#### REST-M02 – Détail plat (drawer)
| Champ | Détail |
| --- | --- |
| UI source | PlatDetailDrawer |
| Écart | endpoints restaurant manquants |

#### REST-M03 – Ajouter plat
| Champ | Détail |
| --- | --- |
| UI source | AddPlatModal |
| Écart | endpoints restaurant manquants |

#### REST-M04 – Historique prix plat
| Champ | Détail |
| --- | --- |
| UI source | modal historique (PlatsCatalogPage) |
| Écart | endpoints restaurant manquants |

#### REST-M05 – Simulateur de prix
| Champ | Détail |
| --- | --- |
| UI source | PriceSimulatorPanel |
| Écart | endpoints restaurant manquants |

#### REST-M06 – Détail ingrédient (modal)
| Champ | Détail |
| --- | --- |
| UI source | IngredientsPage |
| Écart | endpoints restaurant manquants |

#### REST-M07 – Détail ingrédient (drawer)
| Champ | Détail |
| --- | --- |
| UI source | IngredientDetailDrawer |
| Fichier source | `monprojet/frontend/src/features/restaurant/components/IngredientDetailDrawer.jsx` |
| Écart | endpoints restaurant manquants |

#### REST-M08 – Ajouter ingrédient
| Champ | Détail |
| --- | --- |
| UI source | AddIngredientModal |
| Écart | endpoints restaurant manquants |

#### REST-M09 – Quick stock update
| Champ | Détail |
| --- | --- |
| UI source | IngredientsPage quick stock modal |
| Écart | endpoints restaurant manquants |

---

## 6. Écarts techniques & DWH

| Écart | Impact | Priorité |
| --- | --- | --- |
| Catalogue MassaCorp basé `/metro/*` | perte de précision DWH | Haute |
| Endpoints DWH prix (history/alerts) manquants | blocage EP-04/05 | Haute |
| Endpoints DWH supply plan manquants | blocage EP-06/07 | Haute |
| Écriture DWH (création/édition produit) | modals EP-M01/M02 | Haute |
| Reconciliation finance DWH absente | blocage FIN-02/03/FIN-M03 | Haute |
| Règles/anomalies finance absentes | blocage FIN-04/06/FIN-M04/M05 | Haute |
| Champs IA catégorisation absents | FIN-01/FIN-M01 | Moyenne |
| Domaine Restaurant absent (API + modèle) | blocage complet Restaurant | Haute |

---

## 7. Prochaines étapes

1. Valider les endpoints DWH à créer (prix, supply, reconciliation, rules, anomalies).
2. Décider la politique d’écriture DWH (produits, ajustements, POs).
3. Activer la bascule catalogue `/metro/*` → DWH `catalogApi`.
4. Construire les pages newCMS Epicerie/Finance avec modals/drawers.
5. Démarrer le domaine Restaurant (modèles + endpoints + UI).
