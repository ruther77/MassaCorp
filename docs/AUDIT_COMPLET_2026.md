# MassaCorp - Audit Technique Complet
## Version 2.0 - Niveau Entreprise

**Date**: 6 janvier 2026
**Auteur**: Equipe Architecture
**Statut**: Audit Complet

---

## Table des Matieres

1. [Resume Executif](#1-resume-executif)
2. [Architecture Globale](#2-architecture-globale)
3. [Inventaire Base de Donnees](#3-inventaire-base-de-donnees)
4. [Inventaire Frontend](#4-inventaire-frontend)
5. [Architecture DWH/ETL](#5-architecture-dwhetl)
6. [Architecture Securite](#6-architecture-securite)
7. [Inventaire API](#7-inventaire-api)
8. [Scenarios Utilisateurs](#8-scenarios-utilisateurs)
9. [Analyse des Manques](#9-analyse-des-manques)
10. [Roadmap](#10-roadmap)

---

## 1. Resume Executif

### 1.1 Vue d'Ensemble

MassaCorp est une plateforme multi-tenant de gestion d'entreprise integrant trois domaines metier:
- **Epicerie**: Gestion des achats fournisseurs (METRO), catalogue produits, POS
- **Finance**: Facturation, tresorerie, rapprochement bancaire, budget
- **Restaurant**: Ingredients, plats, stock, consommations, charges

### 1.2 Statistiques Cles

| Composant | Quantite | Statut |
|-----------|----------|--------|
| Tables Base de Donnees | 85 | Production |
| Modeles SQLAlchemy | 50 | Implementes |
| Pages Frontend | 35+ | Operationnelles |
| Endpoints API | 120+ | Documentes |
| Dimensions DWH | 14 | Actives |
| Tables de Faits | 5 | Alimentees |
| Roles RBAC | 3 systeme + N custom | Configures |

### 1.3 Stack Technique

```
Frontend:  React 18 + TypeScript + TanStack Query + Tailwind CSS
Backend:   FastAPI + SQLAlchemy 2.0 + Pydantic v2
Database:  PostgreSQL 16 + Redis 7
ETL:       Python Scripts + SQL Procedures
Auth:      JWT HS256 + Argon2id + TOTP MFA
Deploy:    Docker Compose
```

---

## 2. Architecture Globale

### 2.1 Diagramme de Composants

```
                    +------------------+
                    |   Frontend       |
                    |   React/TS       |
                    |   Port 3000      |
                    +--------+---------+
                             |
                             | HTTP/REST
                             v
+------------------+   +------------------+   +------------------+
|   PostgreSQL 16  |<--|   FastAPI        |-->|   Redis 7        |
|   Port 5432      |   |   Port 8000      |   |   Port 6379      |
|   - public.*     |   |   - Auth/RBAC    |   |   - Sessions     |
|   - dwh.*        |   |   - API REST     |   |   - Rate Limit   |
|   - staging.*    |   |   - Middleware   |   |   - Cache        |
+------------------+   +------------------+   +------------------+
         ^                     |
         |                     v
+------------------+   +------------------+
|   ETL Pipeline   |   |   MailHog        |
|   Python/SQL     |   |   Port 8025      |
|   - Metro PDF    |   |   - SMTP Test    |
+------------------+   +------------------+
```

### 2.2 Multi-Tenancy

- **Isolation**: Row-Level Security (RLS) PostgreSQL
- **Context**: `app.current_tenant_id` session variable
- **Validation**: Application + Database layer
- **Scope**: Toutes les tables metier isolees par tenant_id

---

## 3. Inventaire Base de Donnees

### 3.1 Schema Public (51 tables)

#### Core/Auth (16 tables)

| Table | Description | Cles |
|-------|-------------|------|
| `tenants` | Organisations multi-tenant | PK: id, UK: slug |
| `users` | Utilisateurs systeme | PK: id, UK: (tenant_id, email) |
| `sessions` | Sessions actives | PK: id (UUID), FK: user_id |
| `refresh_tokens` | Tokens de rafraichissement | PK: jti, FK: session_id |
| `revoked_tokens` | Tokens revoques (blacklist) | PK: jti |
| `roles` | Roles RBAC | PK: id, UK: (tenant_id, code) |
| `permissions` | Permissions granulaires | PK: id, UK: code |
| `role_permissions` | Association role-permission | UK: (role_id, permission_id) |
| `user_roles` | Association user-role | UK: (user_id, role_id) |
| `audit_log` | Journal d'audit immutable | PK: id, IDX: event_type, created_at |
| `login_attempts` | Tentatives de connexion | IDX: identifier, ip |
| `mfa_secrets` | Secrets TOTP | PK: user_id |
| `mfa_recovery_codes` | Codes de recuperation MFA | FK: user_id |
| `password_reset_tokens` | Tokens reset mot de passe | UK: token_hash |
| `api_keys` | Cles API M2M | UK: key_hash |
| `api_key_usage` | Logs d'utilisation API keys | FK: api_key_id |
| `oauth_accounts` | Comptes OAuth lies | UK: (provider, provider_user_id, tenant_id) |

#### Finance (15 tables)

| Table | Description | Relations |
|-------|-------------|-----------|
| `finance_entities` | Entites juridiques | Parent de accounts, categories |
| `finance_entity_members` | Membres par entite | FK: entity_id, user_id |
| `finance_accounts` | Comptes bancaires | FK: entity_id |
| `finance_account_balances` | Historique soldes | FK: account_id |
| `finance_categories` | Categories depenses/revenus | Self-ref hierarchie |
| `finance_cost_centers` | Centres de couts | FK: entity_id |
| `finance_vendors` | Fournisseurs | FK: entity_id |
| `finance_invoices` | Factures fournisseurs | FK: entity_id, vendor_id |
| `finance_invoice_lines` | Lignes de facture | FK: invoice_id |
| `finance_payments` | Paiements factures | FK: invoice_id, transaction_id |
| `finance_transactions` | Transactions bancaires | FK: account_id |
| `finance_transaction_lines` | Ventilation transactions | FK: transaction_id, category_id |
| `finance_bank_statements` | Releves bancaires | FK: account_id |
| `finance_bank_statement_lines` | Lignes de releve | FK: statement_id |
| `finance_reconciliations` | Rapprochements | FK: statement_line_id, transaction_id |

#### Restaurant (8 tables)

| Table | Description | Relations |
|-------|-------------|-----------|
| `restaurant_ingredients` | Ingredients cuisine | FK: default_supplier_id |
| `restaurant_plats` | Plats/Menus | - |
| `restaurant_plat_ingredients` | Composition plats | FK: plat_id, ingredient_id |
| `restaurant_stock` | Niveaux de stock | FK: ingredient_id (1:1) |
| `restaurant_stock_movements` | Mouvements de stock | FK: stock_id |
| `restaurant_consumptions` | Ventes/Pertes/Offerts | FK: plat_id |
| `restaurant_charges` | Charges fixes restaurant | - |
| `restaurant_epicerie_links` | Liens ingredient-produit Metro | FK: ingredient_id |

### 3.2 Schema DWH (34 tables)

#### Dimensions (14 tables)

| Dimension | Type SCD | Description |
|-----------|----------|-------------|
| `dim_temps` | Type 0 | Calendrier 2020-2030 pre-genere |
| `dim_produit` | Type 2 | Produits avec historique prix |
| `dim_plat` | Type 2 | Plats avec historique couts |
| `dim_fournisseur` | Type 2 | Fournisseurs avec historique |
| `dim_categorie_produit` | Type 1 | 91 categories pre-chargees |
| `dim_devise` | Type 1 | Devises (EUR, USD, GBP, CHF) |
| `dim_mode_paiement` | Type 1 | Modes de paiement |
| `dim_type_document` | Type 1 | Types de documents |
| `dim_statut_document` | Type 1 | Statuts workflow |
| `dim_cost_center` | Type 1 | Centres de couts |
| `dim_categorie_depense` | Type 1 | Categories depenses |
| `dim_canal` | Type 1 | Canaux de vente (6) |
| `dim_marque` | Type 1 | Marques produits |
| `dim_exercice_comptable` | Type 1 | Exercices fiscaux |

#### Tables de Faits (5 tables)

| Fait | Grain | Mesures Cles |
|------|-------|--------------|
| `fait_achats` | Ligne facture achat | quantite, montant_ht, montant_ttc |
| `fait_ventes_restaurant` | Transaction vente | ca_ttc, cout_matiere, marge_brute |
| `fait_mouvements_stock` | Mouvement unitaire | quantite, valeur_mouvement |
| `fait_stock_quotidien` | Produit/Jour (snapshot) | stock_quantite, stock_valeur, jours_stock |
| `fait_depenses` | Ligne depense | montant_ht, montant_ttc |

#### Tables Metro (3 tables)

| Table | Description |
|-------|-------------|
| `metro_facture` | En-tetes factures Metro importees |
| `metro_ligne` | Lignes de factures Metro |
| `metro_produit_agregat` | Agregats par produit (stats) |

---

## 4. Inventaire Frontend

### 4.1 Pages par Domaine

#### Authentification (6 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/login` | LoginPage | OK |
| `/register` | RegisterPage | OK |
| `/forgot-password` | ForgotPasswordPage | OK |
| `/reset-password` | ResetPasswordPage | OK |
| `/mfa/verify` | MFAVerifyPage | OK |
| `/oauth/:provider/callback` | OAuthCallbackPage | OK |

#### Profil (3 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/profile` | ProfilePage | OK |
| `/profile/security` | SecurityPage | OK |
| `/profile/mfa` | MFASetupPage | OK |

#### Admin (3 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/admin/users` | UsersPage | INCOMPLET - Manque modals CRUD |
| `/admin/sessions` | SessionsPage | OK |
| `/admin/audit-logs` | AuditLogsPage | OK |

#### Epicerie (4 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/epicerie` | EpicerieDashboard | OK |
| `/epicerie/catalogue` | CatalogPage | OK |
| `/epicerie/pos` | VentePOSPage | OK |
| `/epicerie/fournisseurs` | FournisseursPage | INCOMPLET - Backend non integre |

#### Finance (12 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/finance` | FinanceDashboard | OK |
| `/finance/factures` | InvoicesPage | OK |
| `/finance/factures/new` | InvoiceFormPage | OK |
| `/finance/factures/:id` | InvoiceDetailPage | OK |
| `/finance/factures/:id/edit` | InvoiceFormPage | OK |
| `/finance/tresorerie` | TreasuryPage | OK |
| `/finance/budget` | BudgetPage | OK |
| `/finance/echeances` | DueDatesPage | OK |
| `/finance/transactions` | TransactionsPage | OK |
| `/finance/comptes` | AccountsPage | OK |
| `/finance/rapprochement` | ReconciliationPage | OK |
| `/finance/regles` | RulesPage | OK |
| `/finance/imports` | ImportsPage | OK |

#### Restaurant (7 pages)
| Route | Page | Statut |
|-------|------|--------|
| `/restaurant` | RestaurantDashboard | OK |
| `/restaurant/ingredients` | IngredientsPage | OK |
| `/restaurant/plats` | PlatsPage | OK |
| `/restaurant/stock` | StockPage | OK |
| `/restaurant/ventes` | ConsumptionsPage | OK |
| `/restaurant/charges` | ChargesPage | OK |
| `/restaurant/rapprochement` | RapprochementPage | OK |

#### Analytics (1 page)
| Route | Page | Statut |
|-------|------|--------|
| `/analytics` | AnalyticsDashboard | OK |

### 4.2 Modals Existants

| Domaine | Modal | Utilisation |
|---------|-------|-------------|
| UI Core | Modal | Wrapper generique |
| UI Core | ConfirmDialog | Confirmations (delete, logout) |
| UI Core | DeleteConfirm | Suppression avec danger |
| Epicerie | PaymentModal | Paiement POS |
| Restaurant | IngredientModal | CRUD Ingredient |
| Restaurant | PlatModal | CRUD Plat |
| Restaurant | IngredientsListModal | Composition plat |
| Restaurant | LinkEpicerieModal | Rapprochement |
| Finance | InvoiceFormModal | Creation facture inline |

### 4.3 Modals Manquants (Critiques)

| Domaine | Modal Requis | Priorite |
|---------|--------------|----------|
| Admin | UserCreateModal | HAUTE |
| Admin | UserEditModal | HAUTE |
| Admin | UserRolesModal | HAUTE |
| Admin | RolePermissionsModal | MOYENNE |
| Epicerie | ProductDetailModal | MOYENNE |
| Epicerie | FournisseurFormModal | HAUTE |
| Epicerie | CommandeFormModal | HAUTE |
| Finance | TransactionEditModal | MOYENNE |
| Finance | ReconciliationMatchModal | MOYENNE |
| Restaurant | StockAdjustModal | MOYENNE |
| Restaurant | ConsumptionFormModal | HAUTE |
| Global | BulkActionModal | BASSE |
| Global | ExportModal | BASSE |
| Global | ImportPreviewModal | MOYENNE |

---

## 5. Architecture DWH/ETL

### 5.1 Pipeline ETL (8 etapes)

```
1. EXTRACTION        PDF Metro -> JSON
2. NETTOYAGE         Formatage, normalisation
3. VALIDATION        Coherence, calculs
4. ENRICHISSEMENT    Classification auto
5. TRANSFORMATION    Staging -> ODS
6. GENERATION        Entetes factures
7. CHARGEMENT        ODS -> DWH (SCD)
8. AGREGATION        Produits agregats
```

### 5.2 Flux de Donnees

```
Sources                    Staging              ODS                 DWH
+----------+              +----------+        +----------+        +----------+
| PDF      |--Extract---->| stg_*    |--T/V-->| ods_*    |--Load->| dim_*    |
| Metro    |              |          |        |          |        | fait_*   |
+----------+              +----------+        +----------+        +----------+
                               |                   |                   |
                               v                   v                   v
                         7-30 jours           1-3 mois              7+ ans
                         (temporaire)        (tactique)          (strategique)
```

### 5.3 Vues Pre-Calculees

| Vue | Utilisation |
|-----|-------------|
| `v_valorisation_stock` | Valeur stock par categorie |
| `v_top_produits_epicerie` | Top 100 produits CA |
| `v_ca_quotidien_restaurant` | CA journalier par canal |
| `v_top_plats_restaurant` | Top plats marge/volume |
| `v_synthese_depenses` | Depenses par centre cout |

---

## 6. Architecture Securite

### 6.1 Authentification

| Composant | Implementation |
|-----------|----------------|
| **Password Hash** | Argon2id (OWASP 2024) + Migration BCrypt |
| **JWT Access** | HS256, 15 min expiry |
| **JWT Refresh** | SHA-256 hash, 7 jours, rotation |
| **Sessions** | UUID, device tracking, revocables |
| **MFA/TOTP** | Google Authenticator, 10 recovery codes |
| **OAuth** | Google, Facebook, GitHub |

### 6.2 Autorisation (RBAC)

```
Roles Systeme:
+-- admin     -> Full access (users.*, roles.*, audit.*, settings.*)
+-- manager   -> User management (users.read/write, roles.read/assign)
+-- viewer    -> Read-only (users.read, roles.read, reports.read)

Permissions Format: resource.action
Ressources: users, tenants, roles, audit, sessions, reports, settings
Actions: read, write, delete, manage, assign, export, revoke
```

### 6.3 Securite Applicative

| Mesure | Configuration |
|--------|---------------|
| Rate Limiting | Redis ZSET, 60 req/min default |
| Password Policy | 12+ chars, HIBP check, complexity |
| HTTPS | Force redirect, HSTS 1 an |
| Headers | CSP, X-Frame-Options DENY, nosniff |
| CORS | Origins explicites, no * en prod |
| Audit | Immutable log, IP tracking |
| Lockout | 5 echecs MFA -> 30 min blocage |

### 6.4 Isolation Multi-Tenant

```sql
-- RLS PostgreSQL
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
  USING (tenant_id = current_setting('app.current_tenant_id')::bigint);

-- Context setup per request
SET app.current_tenant_id = {tenant_id};
SET app.current_user_id = {user_id};
```

---

## 7. Inventaire API

### 7.1 Endpoints par Domaine

| Domaine | Prefix | Endpoints | Auth |
|---------|--------|-----------|------|
| Auth | `/auth` | 7 | Public/Auth |
| Users | `/users` | 10 | Auth/Admin |
| Catalog | `/catalog` | 3 | Auth |
| Finance | `/finance` | 15+ | Auth |
| Restaurant | `/restaurant` | 40+ | Auth |
| Analytics | `/analytics` | 10 | Auth |
| Metro | `/metro` | 12 | Auth |
| MFA | `/mfa` | 7 | Auth |
| API Keys | `/api-keys` | 4 | Auth |
| Sessions | `/sessions` | 4 | Auth |
| GDPR | `/gdpr` | 4 | Auth/Admin |
| Password Reset | `/password-reset` | 3 | Public |

### 7.2 Schemas de Reponse Standard

```python
# Pagination
class PaginatedResponse(BaseModel):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

# Erreur
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict]
    request_id: str
```

---

## 8. Scenarios Utilisateurs

### 8.1 Roles et Personas

#### Admin Systeme
- Gere les utilisateurs et roles
- Configure les entites finance
- Supervise l'audit et la securite
- Exporte les donnees GDPR

#### Gestionnaire Epicerie
- Importe les factures Metro
- Gere le catalogue produits
- Utilise le POS pour les ventes
- Analyse les stats achats

#### Gestionnaire Restaurant
- Gere les ingredients et plats
- Suit le stock et les alertes
- Enregistre les ventes/pertes
- Calcule le food cost

#### Comptable
- Gere les factures fournisseurs
- Fait le rapprochement bancaire
- Suit la tresorerie
- Analyse les depenses

### 8.2 Parcours Critiques

#### Connexion avec MFA
```
1. POST /auth/login (email, password)
   -> 200 {mfa_required: true, mfa_session_token}
2. POST /auth/login/mfa (mfa_session_token, totp_code)
   -> 200 {access_token, refresh_token}
3. GET /auth/me
   -> 200 {authenticated: true, user details}
```

#### Import Facture Metro
```
1. Upload PDF -> ETL Extract
2. Staging tables populated
3. POST /metro/import (json_path)
4. Validation + Enrichissement
5. Chargement DWH
6. GET /metro/products - Catalogue mis a jour
```

#### Vente Restaurant avec Stock
```
1. GET /restaurant/plats (liste)
2. POST /restaurant/consumptions/sale
   {plat_id, quantite, decrement_stock: true}
3. Stock ingredients decrementes automatiquement
4. GET /restaurant/stock/low (alertes)
```

#### Rapprochement Bancaire
```
1. POST /finance/bank-statements/import
2. GET /finance/bank-statements/{id}/lines
3. POST /finance/reconciliations
   {statement_line_id, transaction_id}
4. GET /finance/dashboard (stats updated)
```

---

## 9. Analyse des Manques

### 9.1 Fonctionnalites Manquantes (Critiques)

| Domaine | Manque | Impact | Effort |
|---------|--------|--------|--------|
| Admin | CRUD complet utilisateurs UI | Gestion impossible via UI | 2 jours |
| Admin | Gestion roles/permissions UI | Configuration limitee | 3 jours |
| Epicerie | Backend fournisseurs/commandes | Module incomplet | 5 jours |
| Epicerie | Gestion stock epicerie | Pas de suivi | 4 jours |
| Finance | Import releves bancaires | Manuel actuellement | 3 jours |
| Restaurant | Historique mouvements UI | Tracabilite limitee | 1 jour |
| Global | Notifications temps reel | Pas d'alertes push | 4 jours |
| Global | Export PDF/Excel | Reporting limite | 2 jours |

### 9.2 Incoherences Corrigees

| Probleme | Status |
|----------|--------|
| food_cost_ratio string vs number | CORRIGE |
| URL doubling /api/v1/api/v1 | CORRIGE |
| Manque epicerie_links hooks | CORRIGE |
| Pas de route rapprochement | CORRIGE |

### 9.3 Dette Technique

| Type | Description | Priorite |
|------|-------------|----------|
| Tests | Couverture tests < 50% | HAUTE |
| Types | any usage dans quelques fichiers | MOYENNE |
| Perf | Queries N+1 sur certains endpoints | MOYENNE |
| Doc | API non documentee OpenAPI complet | HAUTE |
| i18n | Hardcoded French strings | BASSE |

---

## 10. Roadmap

### Phase 1: Consolidation (2 semaines)

**Semaine 1**
- [ ] Completer CRUD utilisateurs admin (modals + API)
- [ ] Standardiser les modals (hook useModal partout)
- [ ] Ajouter tests unitaires hooks critiques
- [ ] Documenter API OpenAPI complete

**Semaine 2**
- [ ] Implementer backend fournisseurs epicerie
- [ ] Connecter FournisseursPage au backend
- [ ] Ajouter gestion stock epicerie
- [ ] Tests E2E parcours critiques

### Phase 2: Enrichissement (3 semaines)

**Semaine 3-4**
- [ ] Import releves bancaires (MT940, OFX, CSV)
- [ ] Rapprochement auto intelligent
- [ ] Notifications temps reel (WebSocket)
- [ ] Dashboard alertes configurable

**Semaine 5**
- [ ] Export PDF/Excel (factures, rapports)
- [ ] Historique mouvements stock UI
- [ ] Amelioration perf queries DWH
- [ ] Cache Redis pour analytics

### Phase 3: Entreprise (4 semaines)

**Semaines 6-7**
- [ ] Multi-entite par tenant
- [ ] Workflow approbation factures
- [ ] Budget previsionnel avance
- [ ] API versioning v2

**Semaines 8-9**
- [ ] SSO SAML/OIDC enterprise
- [ ] Audit compliance etendu
- [ ] Retention policies automatiques
- [ ] Disaster recovery plan

### Indicateurs de Succes

| Metrique | Actuel | Cible Phase 1 | Cible Phase 3 |
|----------|--------|---------------|---------------|
| Test Coverage | ~30% | 60% | 80% |
| API Response P95 | 500ms | 200ms | 100ms |
| Uptime | 95% | 99% | 99.9% |
| Security Score | B | A | A+ |
| WCAG Compliance | Partiel | AA | AAA |

---

## Annexes

### A. Fichiers Cles

```
/home/ruuuzer/Documents/MassaCorp/
+-- app/
|   +-- api/v1/endpoints/     # 14 modules API
|   +-- core/                 # Security, config, deps
|   +-- middleware/           # Rate limit, headers, tenant
|   +-- models/               # 50 SQLAlchemy models
|   +-- repositories/         # Data access layer
|   +-- services/             # Business logic
|   +-- main.py              # FastAPI app
+-- frontend/src/
|   +-- api/                  # API clients
|   +-- components/ui/        # Design system
|   +-- hooks/                # React Query hooks
|   +-- pages/                # 35+ pages
|   +-- App.tsx              # Router
+-- etl/metro/               # ETL pipeline
+-- db/sql/                  # DWH schemas
+-- alembic/versions/        # Migrations
```

### B. Variables d'Environnement Critiques

```bash
# Database
POSTGRES_DB=MassaCorp
POSTGRES_USER=massa
POSTGRES_PASSWORD=***

# Security
JWT_SECRET=***  # Min 32 chars
ENCRYPTION_KEY=***  # Min 32 chars

# Services
REDIS_URL=redis://:***@massacorp_redis:6379/0

# Production Flags
ENV=prod
DEBUG=false
FORCE_HTTPS=true
CAPTCHA_ENABLED=true
```

### C. Contacts

- **Architecture**: architecture@massacorp.dev
- **Securite**: security@massacorp.dev
- **Support**: support@massacorp.dev

---

*Document genere automatiquement - MassaCorp Architecture Team*
*Date de generation: 2026-01-06*
