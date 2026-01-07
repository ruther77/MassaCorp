# Feuille de Route Migration - monprojet vers MassaCorp

**Date**: 5 janvier 2026
**Version**: 1.0
**Scope**: Backend (Python/FastAPI), Frontend (React/TypeScript), Base de donnees PostgreSQL
**Objectif**: Integration des domaines Epicerie, Finances, Restaurant de monprojet vers MassaCorp niveau entreprise

---

## Table des matieres

1. [Resume Executif](#1-resume-executif)
2. [Phase 1: Inventaire Sources](#2-phase-1-inventaire-sources)
3. [Phase 2: Inventaire Cible MassaCorp](#3-phase-2-inventaire-cible-massacorp)
4. [Phase 3: Ecarts et Decisions](#4-phase-3-ecarts-et-decisions)
5. [Phase 4: Migration Backend](#5-phase-4-migration-backend)
6. [Phase 5: Migration Frontend](#6-phase-5-migration-frontend)
7. [Phase 6: Tests et Validation](#7-phase-6-tests-et-validation)
8. [Phase 7: Planning](#8-phase-7-planning)
9. [Annexes](#9-annexes)

---

## 1. Resume Executif

### 1.1 Contexte

| Aspect | monprojet | MassaCorp |
|--------|-----------|-----------|
| **Backend** | FastAPI + SQLAlchemy | FastAPI + SQLAlchemy |
| **Frontend** | React JSX | React TypeScript |
| **Auth** | Basic | JWT + MFA + RBAC + OAuth |
| **Multi-tenant** | Partiel | Complet avec isolation |
| **Tests** | Partiels | 1221 tests unitaires |

### 1.2 Domaines a Migrer

| Domaine | Tables Source | Composants Frontend | Priorite |
|---------|--------------|---------------------|----------|
| **Epicerie** | dim_produit, fact_invoices, stock_movements | 7 pages, 6 modals | HAUTE |
| **Finances** | finance_* (15 tables) | 8 pages, 7 modals | HAUTE |
| **Restaurant** | restaurant_* (a creer) | 10 pages, 9 modals | MOYENNE |

### 1.3 Estimation Globale

| Phase | Effort | Duree estimee |
|-------|--------|---------------|
| Backend Models + Migrations | M | - |
| Backend Services + API | L | - |
| Frontend Pages | L | - |
| Frontend Modals/Drawers | M | - |
| Tests E2E | M | - |
| **Total** | **XL** | - |

---

## 2. Phase 1: Inventaire Sources (monprojet)

### 2.1 Schema Base de Donnees - Finance

#### 2.1.1 Tables Finance Core

| Table | Colonnes Principales | Relations | Indexes |
|-------|---------------------|-----------|---------|
| `finance_entities` | id, name, code, currency, is_active | - | name, is_active |
| `finance_entity_members` | id, entity_id, user_id | FK finance_entities | - |
| `finance_categories` | id, entity_id, name, type, parent_id, code | FK self, FK entities | parent, entity_type |
| `finance_cost_centers` | id, entity_id, name, code, is_active | FK entities | entity_active |

#### 2.1.2 Tables Comptes et Transactions

| Table | Colonnes Principales | Relations | Indexes |
|-------|---------------------|-----------|---------|
| `finance_accounts` | id, entity_id, type (ENUM), label, iban, bic, currency | FK entities | entity_type, active |
| `finance_account_balances` | id, account_id, date, balance, source | FK accounts | date |
| `finance_transactions` | id, entity_id, account_id, direction (ENUM), date_operation, amount, status (ENUM) | FK entities, accounts | entity_date, account_date |
| `finance_transaction_lines` | id, transaction_id, category_id, cost_center_id, montant_ht, tva_pct, montant_ttc | FK transactions, categories, cost_centers | transaction, category, cost_center |

#### 2.1.3 Tables Fournisseurs et Factures

| Table | Colonnes Principales | Relations | Indexes |
|-------|---------------------|-----------|---------|
| `finance_vendors` | id, entity_id, name, siret, iban, contact_email, address | FK entities | entity_name |
| `finance_invoices_supplier` | id, entity_id, vendor_id, invoice_number, date_invoice, date_due, montant_ht/tva/ttc, status | FK entities, vendors | status, due |
| `finance_invoice_lines_supplier` | id, invoice_id, category_id, description, quantite, prix_unitaire, montant_ht/ttc | FK invoices, categories | invoice, category |
| `finance_payments` | id, invoice_id, transaction_id, amount, date_payment, mode | FK invoices, transactions | invoice, transaction |

#### 2.1.4 Tables Releves Bancaires et Rapprochement

| Table | Colonnes Principales | Relations | Indexes |
|-------|---------------------|-----------|---------|
| `finance_bank_statements` | id, account_id, period_start, period_end, source, file_name, hash | FK accounts | account_period |
| `finance_bank_statement_lines` | id, statement_id, date_operation, date_valeur, libelle_banque, montant, checksum | FK statements | statement, ref_banque, checksum |
| `finance_reconciliations` | id, statement_line_id, transaction_id, status, confidence | FK statement_lines, transactions | transaction, status |

### 2.2 Schema Base de Donnees - Catalogue/Epicerie

#### 2.2.1 Tables DWH Catalogue

| Table | Colonnes Principales | Usage |
|-------|---------------------|-------|
| `dim_produit` | produit_id, nom, code_ean, categorie_id, fournisseur_id | Dimension produit |
| `dim_fournisseur` | fournisseur_id, nom, siret | Dimension fournisseur |
| `dim_categorie_produit` | categorie_id, nom, parent_id, niveau | Hierarchie categories |
| `fact_invoices` | id, date_id, supplier_id, product_id, unit_cost_excl_tax, quantity | Faits achats |
| `fact_sales` | id, date_id, product_id, channel, quantity, net_amount | Faits ventes |
| `stock_movements` | id, product_id, type, quantity, date, source | Journal stock |

### 2.3 Schema Base de Donnees - Restaurant (a creer)

#### 2.3.1 Tables Restaurant Proposees

| Table | Colonnes Principales | Usage |
|-------|---------------------|-------|
| `restaurant_ingredients` | id, tenant_id, name, unit, category_id, default_supplier_id | Ingredients restaurant |
| `restaurant_plats` | id, tenant_id, name, description, prix_vente, is_active | Plats/menus |
| `restaurant_plat_ingredients` | id, plat_id, ingredient_id, quantite, unit | Composition plats |
| `restaurant_epicerie_links` | id, ingredient_id, produit_id, ratio | Lien ingredient-produit |
| `restaurant_stock` | id, ingredient_id, quantity, updated_at | Stock ingredients |
| `restaurant_consumptions` | id, plat_id, date, quantity, cost | Consommations |

### 2.4 Frontend monprojet - Pages Existantes

#### 2.4.1 Pages Epicerie

| ID | Page | Fichier Source | Route | Fonctionnalites |
|----|------|----------------|-------|-----------------|
| EP-P01 | Catalogue | `features/catalog/CatalogSmartDemo.jsx` | `/catalog` | Liste produits, search, filtres, CRUD |
| EP-P02 | Stock | `features/stock/StockPage.jsx` | `/stock` | Niveaux stock, alertes, rotation |
| EP-P03 | Mouvements Stock | `features/stock/StockMovementsPage.jsx` | `/stock/movements` | Journal mouvements |
| EP-P04 | Prix | `features/prices/PricesPage.jsx` | `/prices` | Historique, alertes marge |
| EP-P05 | Approvisionnement | `features/supply/SupplyPage.jsx` | `/supply` | Plan appro, couverture |
| EP-P06 | Operations | `features/operations/OperationsPage.jsx` | `/operations` | Vue unifiee |
| EP-P07 | Scanner | `features/scanner/ScannerPage.jsx` | `/scanner` | Scan EAN |

#### 2.4.2 Pages Finances

| ID | Page | Fichier Source | Route | Fonctionnalites |
|----|------|----------------|-------|-----------------|
| FIN-P01 | Overview | `features/finance/FinanceOverview.jsx` | `/finance` | KPIs, dernieres transactions |
| FIN-P02 | Transactions | `features/finance/FinanceTransactionsPage.jsx` | `/finance/transactions` | Liste, filtres, categorisation |
| FIN-P03 | Comptes | `features/finance/FinanceAccountsPage.jsx` | `/finance/accounts` | Comptes bancaires |
| FIN-P04 | Rapprochement | `features/finance/BankReconciliationPage.jsx` | `/finance/reconciliation` | Match transactions-factures |
| FIN-P05 | Regles | `features/finance/FinanceRulesPage.jsx` | `/finance/rules` | Regles categorisation auto |
| FIN-P06 | Anomalies | `features/finance/FinanceAnomaliesPage.jsx` | `/finance/anomalies` | Detection anomalies |
| FIN-P07 | Imports | `features/finance/FinanceImportsPage.jsx` | `/finance/imports` | Import releves bancaires |
| FIN-P08 | Factures | `features/invoices/InvoicesListPage.jsx` | `/invoices` | Liste factures fournisseurs |

#### 2.4.3 Pages Restaurant

| ID | Page | Fichier Source | Route | Fonctionnalites |
|----|------|----------------|-------|-----------------|
| REST-P01 | Dashboard | `features/restaurant/RestaurantDashboard.jsx` | `/restaurant` | KPIs, alertes |
| REST-P02 | Plats | `features/restaurant/PlatsCatalogPage.jsx` | `/restaurant/plats` | Catalogue plats |
| REST-P03 | Ingredients | `features/restaurant/IngredientsPage.jsx` | `/restaurant/ingredients` | Gestion ingredients |
| REST-P04 | Menus | `features/restaurant/RestaurantMenuPage.jsx` | `/restaurant/menus` | Composition menus |
| REST-P05 | Liens Epicerie | `features/restaurant/IngredientEpicerieLinkPage.jsx` | `/restaurant/links` | Mapping ingredient-produit |
| REST-P06 | Stock | `features/restaurant/RestaurantStockMovementsPage.jsx` | `/restaurant/stock` | Stock ingredients |
| REST-P07 | Consommations | `features/restaurant/RestaurantConsumptionPage.jsx` | `/restaurant/consumption` | Suivi conso |
| REST-P08 | Charges | `features/restaurant/RestaurantChargesPage.jsx` | `/restaurant/charges` | Charges fixes |
| REST-P09 | Couts Menus | `features/restaurant/RestaurantMenusCostsPage.jsx` | `/restaurant/costs` | Analyse food cost |
| REST-P10 | Tendances Prix | `features/restaurant/RestaurantPriceTrends.jsx` | `/restaurant/trends` | Evolution prix |

### 2.5 Frontend monprojet - Modals/Drawers

#### 2.5.1 Modals Epicerie

| ID | Modal | Usage | Champs |
|----|-------|-------|--------|
| EP-M01 | AddProductModal | Ajout produit | nom, categorie, prix_achat, prix_vente, stock, seuil, unite |
| EP-M02 | EditProductModal | Edition produit | idem EP-M01 |
| EP-M03 | StockAdjustmentModal | Ajustement stock | mode, quantite, raison, note |
| EP-M04 | ProductDetailDrawer | Detail produit | KPIs, historique prix, mouvements |
| EP-M05 | CreateOrderModal | Commande fournisseur | fournisseur, items, quantites |
| EP-M06 | ImportInvoiceModal | Import facture | fichier, options |

#### 2.5.2 Modals Finances

| ID | Modal | Usage | Champs |
|----|-------|-------|--------|
| FIN-M01 | TransactionDetailDrawer | Detail transaction | libelle, date, montant, categorie, IA |
| FIN-M02 | CategorizeModal | Categorisation | categorie select |
| FIN-M03 | ReconciliationModal | Rapprochement manuel | transaction + facture |
| FIN-M04 | RuleCreateModal | Creation regle | nom, categorie, mots-cles |
| FIN-M05 | TestRuleModal | Test regle | resultats matching |
| FIN-M06 | InvoiceImportModal | Import factures | dropzone, options |
| FIN-M07 | InvoiceDetailDrawer | Detail facture | resume + lignes |

#### 2.5.3 Modals Restaurant

| ID | Modal | Usage | Champs |
|----|-------|-------|--------|
| REST-M01 | PlatDetailModal | Detail plat | fiche technique, ingredients, cout |
| REST-M02 | PlatDetailDrawer | Drawer plat | version drawer |
| REST-M03 | AddPlatModal | Ajout plat | nom, description, prix, ingredients |
| REST-M04 | PriceHistoryModal | Historique prix plat | graphique evolution |
| REST-M05 | PriceSimulatorPanel | Simulateur prix | calcul impact |
| REST-M06 | IngredientDetailModal | Detail ingredient | prix, stock, tendance |
| REST-M07 | IngredientDetailDrawer | Drawer ingredient | version drawer |
| REST-M08 | AddIngredientModal | Ajout ingredient | nom, unite, categorie |
| REST-M09 | QuickStockModal | MAJ stock rapide | quantite input |

---

## 3. Phase 2: Inventaire Cible MassaCorp

### 3.1 Models Existants

| Model | Table | Usage | Multi-tenant |
|-------|-------|-------|--------------|
| Tenant | tenants | Isolation | ROOT |
| User | users | Authentification | Oui |
| Session | sessions | Sessions actives | Oui |
| RefreshToken | refresh_tokens | Tokens refresh | Oui |
| AuditLog | audit_logs | Audit trail | Oui |
| LoginAttempt | login_attempts | Securite | Oui |
| MFASecret | mfa_secrets | TOTP MFA | Oui |
| MFARecoveryCode | mfa_recovery_codes | Recovery codes | Oui |
| APIKey | api_keys | API keys externes | Oui |
| Role | roles | RBAC | Oui |
| Permission | permissions | RBAC | Non |
| OAuthAccount | oauth_accounts | SSO | Oui |
| MetroFacture | dwh.metro_facture | Factures METRO | Oui |
| MetroLigne | dwh.metro_ligne | Lignes factures | Oui |

### 3.2 Services Existants

| Service | Fichier | Responsabilites |
|---------|---------|-----------------|
| AuthService | `services/auth.py` | Login, logout, refresh |
| UserService | `services/user.py` | CRUD users |
| SessionService | `services/session.py` | Gestion sessions |
| TokenService | `services/token.py` | Tokens JWT |
| MFAService | `services/mfa.py` | TOTP, recovery |
| AuditService | `services/audit.py` | Logging audit |
| RBACService | `services/rbac.py` | Permissions |
| GDPRService | `services/gdpr.py` | Export/delete |
| OAuthService | `services/oauth.py` | SSO providers |

### 3.3 Frontend Existant

| Page | Route | Fonctionnalites |
|------|-------|-----------------|
| Dashboard | `/` | KPIs analytics |
| Catalog | `/catalog` | Liste produits (METRO) |
| Finance | `/finance` | Dashboard finance |
| Profile | `/profile` | Profil utilisateur |
| Admin | `/admin` | Administration |

### 3.4 Infrastructure Securite

| Composant | Implementation | Status |
|-----------|---------------|--------|
| JWT | HS256, session_id embedded | OK |
| MFA | TOTP pyotp, anti-replay | OK |
| Rate Limiting | Redis sliding window | OK |
| RBAC | Permission-based | OK |
| Tenant Isolation | Repository pattern | OK |
| Audit Trail | AuditService | OK |
| Password Hashing | Argon2id (migre) | OK |
| HSTS | Preload enabled | OK |
| CSP | Strict policy | OK |

---

## 4. Phase 3: Ecarts et Decisions

### 4.1 Ecarts Critiques

| ID | Ecart | Impact | Decision |
|----|-------|--------|----------|
| GAP-01 | Tables finance_* absentes dans MassaCorp | Blocker Finances | Creer migrations |
| GAP-02 | Tables restaurant_* inexistantes | Blocker Restaurant | Creer migrations |
| GAP-03 | Frontend JSX vs TypeScript | Effort conversion | Convertir en TSX |
| GAP-04 | Catalogue base sur /metro/* | Perte precision DWH | Migrer vers DWH |
| GAP-05 | Pas de composants UI newCMS | Style inconsistant | Utiliser design system |
| GAP-06 | Pas de tests E2E domaines metier | Regression possible | Creer tests E2E |

### 4.2 Decisions Architecturales

| ID | Decision | Justification |
|----|----------|---------------|
| DEC-01 | Factures dans Finances (pas Operations) | Coherence metier |
| DEC-02 | Source canonique = DWH | Single source of truth |
| DEC-03 | Modals/Drawers pour details | UX consistante |
| DEC-04 | Tables desktop + Cards mobile | Responsive enterprise |
| DEC-05 | Multi-tenant sur tous domaines | Isolation obligatoire |
| DEC-06 | Audit trail sur toutes ecritures | Conformite |

---

## 5. Phase 4: Migration Backend

### 5.1 Migrations Base de Donnees

#### 5.1.1 [CRITIQUE] Migration Finance Core

**Fichier**: `alembic/versions/20260105_finance_domain.py`

```
Tables a creer:
- finance_entities
- finance_entity_members
- finance_categories
- finance_cost_centers
- finance_accounts
- finance_account_balances
- finance_transactions
- finance_transaction_lines
```

| Champ | Verification | Critere |
|-------|-------------|---------|
| tenant_id | Obligatoire sur toutes tables | Multi-tenant |
| created_at/updated_at | TimestampMixin | Audit |
| indexes | Performance | Requetes frequentes |
| foreign keys | Integrite | CASCADE/SET NULL |

**Effort**: M

#### 5.1.2 [CRITIQUE] Migration Finance Factures

**Fichier**: `alembic/versions/20260105_finance_invoices.py`

```
Tables a creer:
- finance_vendors
- finance_invoices_supplier
- finance_invoice_lines_supplier
- finance_payments
```

**Effort**: M

#### 5.1.3 [CRITIQUE] Migration Finance Banking

**Fichier**: `alembic/versions/20260105_finance_banking.py`

```
Tables a creer:
- finance_bank_statements
- finance_bank_statement_lines
- finance_reconciliations
```

**Effort**: M

#### 5.1.4 [HAUTE] Migration Restaurant

**Fichier**: `alembic/versions/20260105_restaurant_domain.py`

```
Tables a creer:
- restaurant_ingredients
- restaurant_plats
- restaurant_plat_ingredients
- restaurant_epicerie_links
- restaurant_stock
- restaurant_consumptions
- restaurant_charges
```

**Effort**: M

### 5.2 Models SQLAlchemy

#### 5.2.1 Models Finance

| Model | Fichier | Base Classes |
|-------|---------|--------------|
| FinanceEntity | `models/finance/entity.py` | Base, TimestampMixin |
| FinanceCategory | `models/finance/category.py` | Base, TimestampMixin, TenantMixin |
| FinanceCostCenter | `models/finance/cost_center.py` | Base, TimestampMixin, TenantMixin |
| FinanceAccount | `models/finance/account.py` | Base, TimestampMixin, TenantMixin |
| FinanceTransaction | `models/finance/transaction.py` | Base, TimestampMixin, TenantMixin |
| FinanceVendor | `models/finance/vendor.py` | Base, TimestampMixin, TenantMixin |
| FinanceInvoice | `models/finance/invoice.py` | Base, TimestampMixin, TenantMixin |
| FinanceBankStatement | `models/finance/bank_statement.py` | Base, TimestampMixin |

**Effort**: M

#### 5.2.2 Models Restaurant

| Model | Fichier | Base Classes |
|-------|---------|--------------|
| RestaurantIngredient | `models/restaurant/ingredient.py` | Base, TimestampMixin, TenantMixin |
| RestaurantPlat | `models/restaurant/plat.py` | Base, TimestampMixin, TenantMixin |
| RestaurantPlatIngredient | `models/restaurant/plat_ingredient.py` | Base |
| RestaurantEpicerieLink | `models/restaurant/epicerie_link.py` | Base, TenantMixin |
| RestaurantStock | `models/restaurant/stock.py` | Base, TimestampMixin, TenantMixin |
| RestaurantConsumption | `models/restaurant/consumption.py` | Base, TimestampMixin, TenantMixin |

**Effort**: M

### 5.3 Repositories

#### 5.3.1 Repositories Finance

| Repository | Methodes Specifiques |
|------------|---------------------|
| FinanceEntityRepository | get_with_members, get_by_code |
| FinanceCategoryRepository | get_tree, get_by_type |
| FinanceAccountRepository | get_with_balances, get_by_iban |
| FinanceTransactionRepository | search, get_by_period, get_uncategorized |
| FinanceVendorRepository | get_by_siret, search_by_name |
| FinanceInvoiceRepository | get_pending, get_by_vendor, get_overdue |
| FinanceBankStatementRepository | get_by_account, check_duplicate |
| FinanceReconciliationRepository | get_unmatched, create_match |

**Effort**: L

#### 5.3.2 Repositories Restaurant

| Repository | Methodes Specifiques |
|------------|---------------------|
| RestaurantIngredientRepository | get_with_links, get_low_stock |
| RestaurantPlatRepository | get_with_ingredients, get_active |
| RestaurantStockRepository | get_current, update_quantity |
| RestaurantConsumptionRepository | get_by_period, get_by_plat |

**Effort**: M

### 5.4 Services

#### 5.4.1 Services Finance

| Service | Fichier | Responsabilites |
|---------|---------|-----------------|
| FinanceAccountService | `services/finance/account.py` | CRUD comptes, soldes |
| FinanceTransactionService | `services/finance/transaction.py` | CRUD transactions, categorisation |
| FinanceInvoiceService | `services/finance/invoice.py` | CRUD factures, statuts |
| FinanceBankImportService | `services/finance/bank_import.py` | Import releves, parsing |
| FinanceReconciliationService | `services/finance/reconciliation.py` | Rapprochement auto/manuel |
| FinanceRuleService | `services/finance/rules.py` | Regles categorisation |
| FinanceAnalyticsService | `services/finance/analytics.py` | KPIs, anomalies |

**Effort**: L

#### 5.4.2 Services Restaurant

| Service | Fichier | Responsabilites |
|---------|---------|-----------------|
| RestaurantIngredientService | `services/restaurant/ingredient.py` | CRUD ingredients |
| RestaurantPlatService | `services/restaurant/plat.py` | CRUD plats, composition |
| RestaurantStockService | `services/restaurant/stock.py` | Gestion stock |
| RestaurantCostService | `services/restaurant/cost.py` | Calcul food cost |
| RestaurantConsumptionService | `services/restaurant/consumption.py` | Suivi conso |

**Effort**: M

### 5.5 Endpoints API

#### 5.5.1 Endpoints Finance

| Endpoint | Methode | Route | Service |
|----------|---------|-------|---------|
| list_accounts | GET | `/api/v1/finance/accounts` | FinanceAccountService |
| get_account | GET | `/api/v1/finance/accounts/{id}` | FinanceAccountService |
| create_account | POST | `/api/v1/finance/accounts` | FinanceAccountService |
| list_transactions | GET | `/api/v1/finance/transactions` | FinanceTransactionService |
| get_transaction | GET | `/api/v1/finance/transactions/{id}` | FinanceTransactionService |
| categorize_transaction | PATCH | `/api/v1/finance/transactions/{id}/categorize` | FinanceTransactionService |
| list_invoices | GET | `/api/v1/finance/invoices` | FinanceInvoiceService |
| get_invoice | GET | `/api/v1/finance/invoices/{id}` | FinanceInvoiceService |
| import_bank_statement | POST | `/api/v1/finance/bank-statements/import` | FinanceBankImportService |
| get_reconciliation_candidates | GET | `/api/v1/finance/reconciliation/candidates` | FinanceReconciliationService |
| create_reconciliation | POST | `/api/v1/finance/reconciliation` | FinanceReconciliationService |
| list_rules | GET | `/api/v1/finance/rules` | FinanceRuleService |
| test_rule | POST | `/api/v1/finance/rules/test` | FinanceRuleService |

**Effort**: L

#### 5.5.2 Endpoints Restaurant

| Endpoint | Methode | Route | Service |
|----------|---------|-------|---------|
| list_ingredients | GET | `/api/v1/restaurant/ingredients` | RestaurantIngredientService |
| get_ingredient | GET | `/api/v1/restaurant/ingredients/{id}` | RestaurantIngredientService |
| create_ingredient | POST | `/api/v1/restaurant/ingredients` | RestaurantIngredientService |
| list_plats | GET | `/api/v1/restaurant/plats` | RestaurantPlatService |
| get_plat | GET | `/api/v1/restaurant/plats/{id}` | RestaurantPlatService |
| create_plat | POST | `/api/v1/restaurant/plats` | RestaurantPlatService |
| get_plat_cost | GET | `/api/v1/restaurant/plats/{id}/cost` | RestaurantCostService |
| get_stock_summary | GET | `/api/v1/restaurant/stock/summary` | RestaurantStockService |
| update_stock | PATCH | `/api/v1/restaurant/stock/{ingredient_id}` | RestaurantStockService |
| list_consumptions | GET | `/api/v1/restaurant/consumptions` | RestaurantConsumptionService |

**Effort**: M

---

## 6. Phase 5: Migration Frontend

### 6.1 Conversion JSX vers TSX

#### 6.1.1 Regles de Conversion

| Aspect | JSX (monprojet) | TSX (MassaCorp) |
|--------|-----------------|-----------------|
| Types props | PropTypes / aucun | Interface TypeScript |
| Types state | Implicite | Types explicites |
| API calls | fetch/axios | hooks typés (useQuery) |
| Styles | CSS / inline | Tailwind + CSS modules |

#### 6.1.2 Pages a Convertir

| Priorite | Page | Fichier Source | Fichier Cible |
|----------|------|----------------|---------------|
| P1 | FinanceOverview | `monprojet/.../FinanceOverview.jsx` | `MassaCorp/.../FinanceOverviewPage.tsx` |
| P1 | FinanceTransactions | `monprojet/.../FinanceTransactionsPage.jsx` | `MassaCorp/.../FinanceTransactionsPage.tsx` |
| P1 | FinanceAccounts | `monprojet/.../FinanceAccountsPage.jsx` | `MassaCorp/.../FinanceAccountsPage.tsx` |
| P1 | InvoicesList | `monprojet/.../InvoicesListPage.jsx` | `MassaCorp/.../FinanceInvoicesPage.tsx` |
| P2 | BankReconciliation | `monprojet/.../BankReconciliationPage.jsx` | `MassaCorp/.../FinanceReconciliationPage.tsx` |
| P2 | FinanceRules | `monprojet/.../FinanceRulesPage.jsx` | `MassaCorp/.../FinanceRulesPage.tsx` |
| P2 | FinanceImports | `monprojet/.../FinanceImportsPage.jsx` | `MassaCorp/.../FinanceImportsPage.tsx` |
| P3 | RestaurantDashboard | `monprojet/.../RestaurantDashboard.jsx` | `MassaCorp/.../RestaurantDashboardPage.tsx` |
| P3 | Ingredients | `monprojet/.../IngredientsPage.jsx` | `MassaCorp/.../RestaurantIngredientsPage.tsx` |
| P3 | Plats | `monprojet/.../PlatsCatalogPage.jsx` | `MassaCorp/.../RestaurantPlatsPage.tsx` |

**Effort**: L

### 6.2 Composants UI

#### 6.2.1 Composants a Creer/Adapter

| Composant | Type | Usage |
|-----------|------|-------|
| SmartTable | Table | Liste avec filtres, tri, pagination |
| DataCard | Card | Version mobile des tables |
| DetailDrawer | Drawer | Details en side panel |
| FormModal | Modal | Formulaires CRUD |
| ConfirmDialog | Dialog | Confirmations |
| KPICard | Card | Indicateurs |
| ChartContainer | Chart | Graphiques |
| FilterBar | Form | Filtres avances |

**Effort**: M

#### 6.2.2 Integration Design System

| Aspect | Source | Cible |
|--------|--------|-------|
| Couleurs | Variables CSS | Tailwind theme |
| Typography | Custom | Tailwind typography |
| Spacing | Mixed | Tailwind spacing |
| Icons | Lucide | Lucide (conserve) |
| Charts | Recharts | Recharts (conserve) |

### 6.3 Hooks et API

#### 6.3.1 Hooks a Creer

| Hook | Usage | Fichier |
|------|-------|---------|
| useFinanceAccounts | CRUD comptes | `hooks/finance/useFinanceAccounts.ts` |
| useFinanceTransactions | CRUD transactions | `hooks/finance/useFinanceTransactions.ts` |
| useFinanceInvoices | CRUD factures | `hooks/finance/useFinanceInvoices.ts` |
| useFinanceReconciliation | Rapprochement | `hooks/finance/useFinanceReconciliation.ts` |
| useFinanceRules | Regles | `hooks/finance/useFinanceRules.ts` |
| useRestaurantIngredients | CRUD ingredients | `hooks/restaurant/useRestaurantIngredients.ts` |
| useRestaurantPlats | CRUD plats | `hooks/restaurant/useRestaurantPlats.ts` |
| useRestaurantStock | Stock | `hooks/restaurant/useRestaurantStock.ts` |
| useRestaurantCosts | Food cost | `hooks/restaurant/useRestaurantCosts.ts` |

**Effort**: M

#### 6.3.2 Services API

| Service | Base URL | Fichier |
|---------|----------|---------|
| financeApi | `/api/v1/finance` | `api/financeApi.ts` |
| restaurantApi | `/api/v1/restaurant` | `api/restaurantApi.ts` |

---

## 7. Phase 6: Tests et Validation

### 7.1 Tests Backend

#### 7.1.1 Tests Unitaires Services

| Service | Fichier Test | Cas de Test |
|---------|--------------|-------------|
| FinanceAccountService | `test_finance_account_service.py` | CRUD, soldes, validation |
| FinanceTransactionService | `test_finance_transaction_service.py` | CRUD, categorisation, filtres |
| FinanceReconciliationService | `test_finance_reconciliation_service.py` | Matching, confidence |
| RestaurantPlatService | `test_restaurant_plat_service.py` | CRUD, composition, cout |

**Effort**: M

#### 7.1.2 Tests Integration Repositories

| Repository | Fichier Test | Cas de Test |
|------------|--------------|-------------|
| FinanceTransactionRepository | `test_finance_transaction_repo.py` | Tenant isolation, search |
| FinanceInvoiceRepository | `test_finance_invoice_repo.py` | CRUD, statuts |
| RestaurantIngredientRepository | `test_restaurant_ingredient_repo.py` | Links, stock |

**Effort**: M

#### 7.1.3 Tests E2E API

| Endpoint | Fichier Test | Scenarios |
|----------|--------------|-----------|
| /finance/transactions | `test_finance_transactions_e2e.py` | List, create, categorize, filter |
| /finance/invoices | `test_finance_invoices_e2e.py` | List, get, import |
| /finance/reconciliation | `test_finance_reconciliation_e2e.py` | Candidates, match |
| /restaurant/plats | `test_restaurant_plats_e2e.py` | CRUD, cost |

**Effort**: M

### 7.2 Tests Frontend

#### 7.2.1 Tests Composants

| Composant | Framework | Cas de Test |
|-----------|-----------|-------------|
| SmartTable | Vitest + RTL | Render, sort, filter, paginate |
| DetailDrawer | Vitest + RTL | Open, close, content |
| FormModal | Vitest + RTL | Validation, submit |

**Effort**: S

#### 7.2.2 Tests E2E Playwright

| Flow | Fichier Test | Scenarios |
|------|--------------|-----------|
| Finance Transactions | `finance-transactions.spec.ts` | List, filter, categorize |
| Finance Reconciliation | `finance-reconciliation.spec.ts` | View, match |
| Restaurant Plats | `restaurant-plats.spec.ts` | Create, view cost |

**Effort**: M

---

## 8. Phase 7: Planning

### 8.1 Phases de Livraison

| Phase | Contenu | Dependances |
|-------|---------|-------------|
| **Phase A** | Finance Core (models, repos, services, API) | Aucune |
| **Phase B** | Finance UI (pages, modals) | Phase A |
| **Phase C** | Restaurant Core (models, repos, services, API) | Aucune |
| **Phase D** | Restaurant UI (pages, modals) | Phase C |
| **Phase E** | Integration Epicerie-Restaurant | Phase B, D |
| **Phase F** | Tests E2E complets | Phase E |

### 8.2 Criteres de Completion par Phase

#### Phase A - Finance Core

- [ ] Migrations executees sans erreur
- [ ] Models avec tenant isolation
- [ ] Repositories avec tests >80% coverage
- [ ] Services avec validation metier
- [ ] Endpoints documentes OpenAPI
- [ ] Tests unitaires passing

#### Phase B - Finance UI

- [ ] Pages converties en TSX
- [ ] Modals/Drawers fonctionnels
- [ ] Responsive (desktop + mobile)
- [ ] Integration API complete
- [ ] Tests composants passing

#### Phase C - Restaurant Core

- [ ] Migrations executees sans erreur
- [ ] Models avec tenant isolation
- [ ] Services food cost fonctionnels
- [ ] Endpoints documentes OpenAPI
- [ ] Tests unitaires passing

#### Phase D - Restaurant UI

- [ ] Pages converties en TSX
- [ ] Modals/Drawers fonctionnels
- [ ] Responsive
- [ ] Tests composants passing

#### Phase E - Integration

- [ ] Liens Epicerie-Restaurant fonctionnels
- [ ] Stock synchronise
- [ ] Couts calcules correctement

#### Phase F - Tests E2E

- [ ] Scenarios Finance couverts
- [ ] Scenarios Restaurant couverts
- [ ] Scenarios Integration couverts
- [ ] CI/CD pipeline vert

---

## 9. Annexes

### 9.1 Mapping Fichiers Source -> Cible

```
monprojet/                              MassaCorp/
├── backend/                            ├── app/
│   ├── services/finance/               │   ├── services/finance/
│   │   ├── imports.py                  │   │   ├── bank_import.py
│   │   ├── reconciliation.py           │   │   ├── reconciliation.py
│   │   └── metrics.py                  │   │   └── analytics.py
│   └── services/restaurant/            │   └── services/restaurant/
│       └── *.py                        │       └── *.py (nouveau)
├── core/                               ├── app/
│   ├── bank_import/models.py           │   ├── models/finance/
│   └── finance/*.py                    │   └── schemas/finance/
├── migrations/versions/                ├── alembic/versions/
│   └── 20241203_finance_treasury.py    │   └── 20260105_finance_*.py
└── frontend/src/features/              └── frontend/src/pages/
    ├── finance/                            ├── finance/
    │   ├── FinanceOverview.jsx             │   ├── FinanceOverviewPage.tsx
    │   ├── FinanceTransactionsPage.jsx     │   ├── FinanceTransactionsPage.tsx
    │   └── ...                             │   └── ...
    └── restaurant/                         └── restaurant/
        ├── IngredientsPage.jsx                 ├── RestaurantIngredientsPage.tsx
        └── ...                                 └── ...
```

### 9.2 ENUMs a Creer

```sql
-- Finance
CREATE TYPE finance_account_type AS ENUM ('BANQUE', 'CAISSE', 'CB', 'AUTRE', 'PLATFORM');
CREATE TYPE finance_tx_direction AS ENUM ('IN', 'OUT', 'TRANSFER');
CREATE TYPE finance_tx_status AS ENUM ('DRAFT', 'CONFIRMED', 'CANCELLED');
CREATE TYPE finance_invoice_status AS ENUM ('EN_ATTENTE', 'PAYEE', 'PARTIELLE', 'ANNULEE');
CREATE TYPE finance_reconciliation_status AS ENUM ('AUTO', 'MANUAL', 'REJECTED');

-- Restaurant
CREATE TYPE restaurant_unit AS ENUM ('U', 'KG', 'L', 'G', 'CL', 'ML');
CREATE TYPE restaurant_stock_movement AS ENUM ('ENTREE', 'SORTIE', 'AJUSTEMENT', 'PERTE');
```

### 9.3 Checklist Pre-Migration

- [ ] Backup base de donnees production
- [ ] Variables d'environnement configurees
- [ ] Redis disponible
- [ ] Tests existants MassaCorp passent
- [ ] Branch git creee pour migration
- [ ] Documentation API a jour

### 9.4 Risques et Mitigations

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Conflits migration | Moyenne | Haut | Test sur env staging |
| Regression securite | Faible | Critique | Audit post-migration |
| Performance degradee | Moyenne | Moyen | Benchmarks avant/apres |
| UX inconsistante | Haute | Moyen | Design review |

---

**Document genere le 5 janvier 2026**
**Version 1.0**
