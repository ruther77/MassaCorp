# Audit Technique Complet - MassaCorp API

**Date**: 5 janvier 2026
**Auditeur**: Claude Opus 4.5
**Version du projet**: 1.0.0
**Scope**: Backend Python (FastAPI), Base de donnees PostgreSQL, Frontend React (non audite)

---

## Table des matieres

1. [Resume Executif](#1-resume-executif)
2. [Phase 1: Cartographie](#2-phase-1-cartographie)
3. [Phase 2: Audit Securite](#3-phase-2-audit-securite)
4. [Phase 3: Audit Base de Donnees](#4-phase-3-audit-base-de-donnees)
5. [Phase 4: Audit Qualite Code](#5-phase-4-audit-qualite-code)
6. [Phase 5: Matrice des Fonctionnalites](#6-phase-5-matrice-des-fonctionnalites)
7. [Phase 6: Feuille de Route](#7-phase-6-feuille-de-route)
8. [Annexes](#8-annexes)

---

## 1. Resume Executif

### Etat Global du Projet

| Aspect | Score | Commentaire |
|--------|-------|-------------|
| **Architecture** | 8/10 | Pattern Repository bien implemente, structure claire |
| **Securite Auth/JWT** | 8.5/10 | Implementation solide, bonnes pratiques |
| **Securite MFA** | 7/10 | Fonctionnel mais manque rate limiting specifique |
| **Multi-tenancy** | 5/10 | **CRITIQUE**: Isolation incomplete dans les repositories |
| **Tests** | 6.5/10 | Bonne couverture unitaire, 0 tests E2E |
| **Migrations** | 4/10 | **CRITIQUE**: Conflits entre migrations |
| **Configuration** | 7.5/10 | Validation robuste, quelques valeurs hardcodees |

### Risques Majeurs Identifies

| # | Risque | Severite | Impact |
|---|--------|----------|--------|
| 1 | **IDOR Multi-tenant** - BaseRepository.get() sans tenant_id | CRITIQUE | Acces cross-tenant aux donnees |
| 2 | **Migrations conflictuelles** - Tables supprimees puis referencees | CRITIQUE | Echec de migration en production |
| 3 | **MFA sans rate limiting** - Brute-force possible sur codes TOTP | HAUTE | Contournement MFA |
| 4 | **Pool DB hardcode** - Ignore les settings de configuration | MOYENNE | Performance sous charge |
| 5 | **Pas de CSP header** - Vulnerability XSS | HAUTE | Injection de scripts |
| 6 | **Aucun test E2E** - Regression non detectee | HAUTE | Bugs en production |

### Recommandation Globale

**Le projet est fonctionnel mais NE DOIT PAS etre deploye en production** avant correction des failles critiques d'isolation multi-tenant et de migrations. Estimation: **2-3 semaines de travail** pour atteindre un niveau production-ready.

---

## 2. Phase 1: Cartographie

### 2.1 Structure du Projet

```
MassaCorp/
├── app/                          # Application principale
│   ├── api/v1/endpoints/         # 11 routers, 73 endpoints
│   ├── core/                     # Config, security, database
│   ├── middleware/               # 8 middlewares actifs
│   ├── models/                   # 12 modeles SQLAlchemy
│   ├── repositories/             # 10+ repositories
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # 15+ services metier
│   └── main.py                   # Point d'entree
├── alembic/versions/             # 14 migrations
├── tests/                        # 34 unit, 4 integration, 0 e2e
├── etl/metro/                    # Pipeline ETL factures
└── frontend/                     # React app (non audite)
```

### 2.2 Fichiers Python Principaux

| Categorie | Fichiers | LOC estim. |
|-----------|----------|------------|
| API Endpoints | 11 | ~3000 |
| Services | 15 | ~4500 |
| Repositories | 10 | ~2500 |
| Models | 12 | ~1500 |
| Middlewares | 8 | ~800 |
| Tests | 38 | ~6000 |
| **Total** | **94** | **~18,300** |

### 2.3 Dependances Principales

| Package | Version | Usage |
|---------|---------|-------|
| FastAPI | ^0.115.0 | Framework web |
| SQLAlchemy | ^2.0.36 | ORM |
| Pydantic | ^2.10.0 | Validation |
| python-jose | ^3.3.0 | JWT |
| bcrypt (passlib) | ^1.7.4 | Hashing |
| pyotp | ^2.9.0 | TOTP/MFA |
| redis | ^5.2.0 | Cache/Rate limit |

**Dependances optionnelles non declarees mais importees:**
- `hvac` (HashiCorp Vault)
- `boto3` (AWS Secrets Manager)
- `infisical-client`

---

## 3. Phase 2: Audit Securite

### 3.1 Authentification JWT

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Algorithme | HS256 | OK (accepter RS256 pour microservices) |
| Expiration Access | 15 minutes | OK |
| Expiration Refresh | 7 jours | OK |
| Secret management | Env var + validation | OK |
| Refresh rotation | Oui + detection replay | EXCELLENT |
| Blacklist/Revocation | Double mecanisme DB | OK |

**Points forts:**
- Detection de replay attack avec revocation automatique de tous les tokens
- Expiration absolue de session (30 jours non extensible)
- DUMMY_HASH pour timing attack prevention

**Points d'attention:**
- Secret rotation n'invalide pas les anciens tokens
- Blacklist en DB (Redis recommande pour perf)

### 3.2 Sessions

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Stockage | PostgreSQL | OK |
| ID format | UUID (anti-enumeration) | EXCELLENT |
| Expiration | Absolue 30j + soft revoke | OK |
| Multi-device | Oui avec liste/terminaison | OK |
| Tracking | IP + User-Agent | OK |

### 3.3 MFA/TOTP

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Endpoints | 7/7 implementes | OK |
| Secret generation | pyotp.random_base32() 160-bit | OK |
| Secret storage | Chiffre (AES) | OK |
| Anti-replay | last_totp_window | OK |
| Recovery codes | 10 codes, bcrypt hash | OK |
| Usage unique | Oui (used_at timestamp) | OK |
| **Rate limiting** | **ABSENT** | **CRITIQUE** |
| Enforcement | Optionnel par user | ATTENTION |

**FAILLE CRITIQUE**: Aucun rate limiting sur `/mfa/verify`, `/mfa/enable`. Un attaquant peut brute-forcer les 6 chiffres.

### 3.4 Rate Limiting et Brute-Force

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Backend | Redis (fallback memoire) | OK |
| Login limit | 5 req/min | OK |
| MFA limit | 5 req/min | OK |
| Escalade brute-force | CAPTCHA -> Delay -> Lock -> Alert | EXCELLENT |
| Lockout | 15 min apres 10 echecs | OK |

**Points d'attention:**
- Fallback memoire non distribue (inefficace multi-serveur)
- IP spoofing possible via X-Forwarded-For mal configure

### 3.5 Security Headers

| Header | Present | Valeur |
|--------|---------|--------|
| HSTS | Oui | max-age=31536000; includeSubDomains |
| X-Frame-Options | Oui | DENY |
| X-Content-Type-Options | Oui | nosniff |
| Referrer-Policy | Oui | strict-origin-when-cross-origin |
| **Content-Security-Policy** | **NON** | **MANQUANT** |
| X-XSS-Protection | Oui | 1; mode=block (deprecie) |

**FAILLE**: Absence de CSP expose aux attaques XSS.

### 3.6 Hachage des Mots de Passe

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Algorithme | bcrypt | OK |
| Cost factor | 12 | OK (13-14 recommande) |
| Salt | Auto-genere | OK |
| Password policy | 8+ chars, maj/min/chiffre/special | OK |
| HIBP check | Desactive par defaut | ATTENTION |

---

## 4. Phase 3: Audit Base de Donnees

### 4.1 Modeles SQLAlchemy

| Modele | tenant_id | Indexes | Cascade |
|--------|-----------|---------|---------|
| User | Oui (NOT NULL) | tenant_id | CASCADE |
| Session | Oui (NOT NULL) | user_id, tenant_id, revoked_at | CASCADE |
| RefreshToken | Non (via Session) | session_id, expires_at | CASCADE |
| APIKey | Oui (NOT NULL) | tenant_id, expires_at | CASCADE |
| AuditLog | Oui (nullable) | event_type, user_id, created_at | SET NULL |
| MFASecret | Oui (NOT NULL) | tenant_id | CASCADE |
| Role | Oui (nullable - global) | tenant_id, code | CASCADE |
| OAuthAccount | Oui (NOT NULL) | provider, user_id | CASCADE |

### 4.2 Multi-Tenancy

**Strategie**: Colonne `tenant_id` (shared database, shared schema)

**FAILLES CRITIQUES D'ISOLATION:**

```python
# BaseRepository.get() - AUCUN filtre tenant_id!
def get(self, id: int) -> Optional[ModelType]:
    return self.session.query(self.model).filter(self.model.id == id).first()
```

| Methode vulnerable | Fichier | Impact |
|--------------------|---------|--------|
| `BaseRepository.get()` | base.py:89 | IDOR sur toutes entites |
| `BaseRepository.get_all()` | base.py:113 | Listing cross-tenant |
| `BaseRepository.update()` | base.py:131 | Modification cross-tenant |
| `BaseRepository.delete()` | base.py:145 | Suppression cross-tenant |
| `MFASecretRepository.get_by_user_id()` | mfa.py:29 | Vol MFA cross-tenant |
| `SessionRepository.is_session_valid()` | session.py:251 | Validation cross-tenant |
| `UserRepository.get_active_users()` | user.py:83 | Enumeration users |

**RLS PostgreSQL**: Configure dans migrations mais politiques inconsistantes (3 variantes differentes).

### 4.3 Migrations Alembic

**Chaine de revisions**: Correcte (14 migrations)

**CONFLITS DETECTES:**

| Probleme | Migrations concernees | Severite |
|----------|----------------------|----------|
| Colonne `scopes` supprimee mais dans modele | k1h38f4j6f7i -> 9ed31d547bd7 | CRITIQUE |
| Table `api_key_usage` supprimee mais modele existe | k1h38f4j6f7i -> 9ed31d547bd7 | CRITIQUE |
| Double creation trigger `audit_log_immutable` | h8e05d1g3c4f + i9f16e2h4d5g | CRITIQUE |
| RLS sur tables supprimees | n4k61h7m9i0l | CRITIQUE |

**Recommandation**: Creer une migration de consolidation qui reconcilie l'etat DB avec les modeles SQLAlchemy.

---

## 5. Phase 4: Audit Qualite Code

### 5.1 Pattern Repository

| Aspect | Verdict | Detail |
|--------|---------|--------|
| Structure | OK | BaseRepository generique, heritage correct |
| CRUD | OK | Methodes standard implementees |
| Transactions | OK | flush() sans commit, gere au niveau service |
| **Isolation tenant** | **ECHEC** | Methodes de base sans filtrage |

### 5.2 Injection de Dependances

```python
# Coherent - utilisation de Depends()
def get_current_user(token: str = Depends(oauth2_scheme)):
    ...

@router.get("/users")
def list_users(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    ...
```

**Verdict**: Implementation coherente et correcte.

### 5.3 Gestion d'Erreurs

| Aspect | Implementation | Verdict |
|--------|---------------|---------|
| Exceptions custom | Hierarchie complete (AppException) | EXCELLENT |
| HTTP codes | Corrects (401, 403, 404, 409, 422, 429) | OK |
| Messages | Generiques (anti-enumeration) | OK |
| Logging | CRITICAL si echec audit | OK |

### 5.4 Tests

| Type | Fichiers | Estimation | Couverture |
|------|----------|------------|------------|
| Unitaires | 34 | ~300 tests | Auth, MFA, RBAC bien couverts |
| Integration | 4 | ~50 tests | Login, MFA, Sessions |
| E2E | 0 | 0 | **AUCUN** |

**Problemes identifies:**
- Dependance au seed admin (skip si absent)
- ~15-20% tests verifient interfaces (hasattr) plutot que comportement
- Mocks excessifs reduisant la valeur
- Rate limiting desactive en test (protection non testee)

**Score global tests**: 6.5/10

### 5.5 Configuration

| Variable | Defaut | Risque |
|----------|--------|--------|
| JWT_SECRET | "CHANGER_EN_PRODUCTION..." | Detecte et bloque en prod |
| ENCRYPTION_KEY | "CHANGER_CLE_CHIFFREMENT..." | Detecte et bloque en prod |
| DATABASE_URL | user:password@localhost | Credentials faibles |
| HIBP check | Desactive | Mots de passe compromis acceptes |

**Probleme**: Pool DB hardcode (10/20) au lieu de settings (5/10).

---

## 6. Phase 5: Matrice des Fonctionnalites

### Legende
- ✅ **Complet**: Code fonctionnel et teste
- ⚠️ **Partiel**: Structure presente, logique incomplete
- ❌ **Absent**: Annonce mais non implemente
- **CRITIQUE**: Implemente avec faille critique

### Authentication & Authorization

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Login email/password | ✅ Complet | Avec timing attack protection |
| JWT Access tokens | ✅ Complet | 15min expiration |
| JWT Refresh tokens | ✅ Complet | Rotation + replay detection |
| Token revocation | ✅ Complet | Double mecanisme |
| Logout (single/all) | ✅ Complet | |
| Password change | ✅ Complet | Avec policy validation |
| Password reset | ✅ Complet | Token + email |
| Account lockout | ✅ Complet | Escalade progressive |

### MFA/2FA

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| TOTP setup | ✅ Complet | QR code + secret |
| TOTP verify | ⚠️ **CRITIQUE** | **Pas de rate limiting** |
| Recovery codes | ✅ Complet | 10 codes, usage unique |
| MFA disable | ✅ Complet | Require password |
| MFA enforce | ⚠️ Partiel | Flag par user, pas par tenant |

### Sessions

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Session list | ✅ Complet | Par user |
| Session terminate | ⚠️ **CRITIQUE** | **IDOR potentiel** |
| Session absolute expiry | ✅ Complet | 30 jours |
| Multi-device | ✅ Complet | |

### Multi-Tenancy

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Tenant isolation | ⚠️ **CRITIQUE** | **Repositories non securises** |
| RLS PostgreSQL | ⚠️ Partiel | Politiques inconsistantes |
| Cross-tenant prevention | ❌ Absent | Pas de validation systematique |

### RBAC

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Permissions | ✅ Complet | Code-based |
| Roles | ✅ Complet | Tenant + global |
| Role assignment | ✅ Complet | Avec expiration |
| Permission check | ✅ Complet | Superuser bypass |

### API Keys

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Create | ✅ Complet | Hash + prefix |
| Revoke | ✅ Complet | |
| Scopes | ⚠️ **CRITIQUE** | Conflit migration - colonne supprimee |
| Usage tracking | ⚠️ **CRITIQUE** | Table supprimee dans migration |

### OAuth/SSO

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Google OAuth | ✅ Complet | |
| GitHub OAuth | ✅ Complet | |
| Account linking | ✅ Complet | |
| Account unlinking | ✅ Complet | |

### GDPR

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Data export | ⚠️ Partiel | MFA et API keys non inclus |
| Data deletion | ⚠️ Partiel | MFA data non supprimee |
| Anonymization | ✅ Complet | |
| Data inventory | ✅ Complet | |

### Monitoring

| Fonctionnalite | Status | Detail |
|----------------|--------|--------|
| Health checks | ✅ Complet | /health, /ready, /health/deep |
| Prometheus metrics | ✅ Complet | /metrics |
| Audit logging | ✅ Complet | Actions sensibles |
| Request tracing | ✅ Complet | X-Request-ID |

---

## 7. Phase 6: Feuille de Route

### 7.1 CRITIQUE - Securite (Semaine 1)

#### [CRITIQUE] Corriger l'isolation multi-tenant dans BaseRepository

- **Fichiers concernes**: `app/repositories/base.py`, tous les repositories
- **Probleme actuel**: `get()`, `get_all()`, `update()`, `delete()` sans filtrage tenant_id
- **Action requise**:
  1. Creer `TenantAwareBaseRepository` avec tenant_id obligatoire
  2. Migrer tous les repositories vers cette nouvelle base
  3. Rendre `tenant_id` non-Optional dans toutes les signatures
  4. Ajouter tests IDOR cross-tenant
- **Critere de completion**: Aucune methode ne retourne de donnees d'un autre tenant
- **Effort estime**: L

#### [CRITIQUE] Ajouter rate limiting sur endpoints MFA

- **Fichiers concernes**: `app/api/v1/endpoints/mfa.py`, `app/middleware/rate_limit.py`
- **Probleme actuel**: Brute-force possible sur codes TOTP (6 chiffres)
- **Action requise**:
  1. Ajouter limite 5 req/min sur `/mfa/verify`
  2. Ajouter lockout apres 10 echecs consecutifs
  3. Logger les tentatives echouees
- **Critere de completion**: Tests demontrant le blocage apres N tentatives
- **Effort estime**: S

#### [CRITIQUE] Ajouter header Content-Security-Policy

- **Fichiers concernes**: `app/middleware/security_headers.py`
- **Probleme actuel**: Vulnerability XSS sans CSP
- **Action requise**:
  1. Definir politique CSP restrictive
  2. Ajouter header `Content-Security-Policy`
  3. Remplacer X-XSS-Protection deprecie
- **Critere de completion**: CSP header present sur toutes les reponses
- **Effort estime**: S

### 7.2 CRITIQUE - Database (Semaine 1-2)

#### [CRITIQUE] Reconcilier migrations avec modeles SQLAlchemy

- **Fichiers concernes**: `alembic/versions/`, `app/models/api_key.py`
- **Probleme actuel**:
  - Colonne `scopes` supprimee mais dans modele
  - Table `api_key_usage` supprimee mais modele existe
  - Double trigger audit_log_immutable
  - RLS sur tables inexistantes
- **Action requise**:
  1. Auditer l'etat reel de la DB de dev/prod
  2. Creer migration de consolidation
  3. Synchroniser modeles SQLAlchemy
  4. Unifier les politiques RLS (une seule syntaxe)
- **Critere de completion**: `alembic upgrade head` sans erreur, modeles = DB
- **Effort estime**: L

### 7.3 HAUTE - Tests (Semaine 2)

#### [HAUTE] Creer suite de tests E2E

- **Fichiers concernes**: `tests/e2e/`
- **Probleme actuel**: 0 tests E2E, workflows complets non valides
- **Action requise**:
  1. Setup Playwright ou similaire
  2. Scenarios: Registration -> Login -> MFA -> Actions -> Logout
  3. Scenarios: Password reset complet
  4. Scenarios: Multi-session cross-device
- **Critere de completion**: CI passe avec tests E2E, couverture flows critiques
- **Effort estime**: L

#### [HAUTE] Ajouter factories avec FactoryBoy

- **Fichiers concernes**: `tests/factories/`
- **Probleme actuel**: Dependance au seed admin, skip excessifs
- **Action requise**:
  1. Installer factory_boy
  2. Creer UserFactory, TenantFactory, SessionFactory
  3. Migrer tests existants
- **Critere de completion**: Tests independants du seed
- **Effort estime**: M

### 7.4 HAUTE - Configuration (Semaine 2)

#### [HAUTE] Utiliser settings pour pool DB

- **Fichiers concernes**: `app/core/database.py`
- **Probleme actuel**: `pool_size=10, max_overflow=20` hardcodes
- **Action requise**:
  1. Remplacer par `settings.DATABASE_POOL_SIZE` et `settings.DATABASE_MAX_OVERFLOW`
  2. Ajouter `pool_timeout` et `pool_recycle`
- **Critere de completion**: DB pool configurable via env vars
- **Effort estime**: S

#### [HAUTE] Activer HIBP check par defaut

- **Fichiers concernes**: `app/core/password_policy.py`
- **Probleme actuel**: `check_hibp=False` par defaut
- **Action requise**:
  1. Activer par defaut sur creation/changement password
  2. Configurable via env var `PASSWORD_CHECK_HIBP`
  3. Garder `fail_open=True` pour disponibilite
- **Critere de completion**: Mots de passe compromis rejetes
- **Effort estime**: S

### 7.5 MOYENNE - Ameliorations (Semaine 3)

#### [MOYENNE] Completer GDPR export/delete

- **Fichiers concernes**: `app/services/gdpr.py`
- **Probleme actuel**: MFA secrets, API keys non inclus
- **Action requise**:
  1. Ajouter MFA data dans export_user_data()
  2. Supprimer MFA data dans delete_user_data()
  3. Inclure API keys
- **Critere de completion**: Export contient toutes les donnees personnelles
- **Effort estime**: M

#### [MOYENNE] Ajouter validation phone/IP

- **Fichiers concernes**: `app/schemas/user.py`, `app/schemas/session.py`
- **Probleme actuel**: Pas de regex pour phone, pas de validation IP
- **Action requise**:
  1. Ajouter regex E.164 pour telephone
  2. Valider format IPv4/IPv6 pour ip_address
  3. Limiter longueur user_agent
- **Critere de completion**: Inputs invalides rejetes avec 422
- **Effort estime**: S

#### [MOYENNE] Ajouter Redis pool pour blacklist

- **Fichiers concernes**: `app/core/redis.py`
- **Probleme actuel**: Pas de connection pool Redis
- **Action requise**:
  1. Configurer `max_connections`
  2. Ajouter `health_check_interval`
  3. Utiliser pour blacklist tokens (perf)
- **Critere de completion**: Redis performant sous charge
- **Effort estime**: M

### 7.6 BASSE - Optimisations (Semaine 3+)

#### [BASSE] Passer de bcrypt a Argon2id

- **Fichiers concernes**: `app/core/security.py`
- **Probleme actuel**: bcrypt est bon, Argon2id est mieux
- **Action requise**:
  1. Ajouter argon2-cffi
  2. Migration progressive (dual verification)
  3. Re-hash au login
- **Critere de completion**: Nouveaux hash en Argon2id
- **Effort estime**: M

#### [BASSE] Ajouter preload HSTS

- **Fichiers concernes**: `app/middleware/security_headers.py`
- **Probleme actuel**: Pas de `preload` dans HSTS
- **Action requise**:
  1. Ajouter `preload` au header HSTS
  2. Soumettre a hstspreload.org
- **Critere de completion**: Domaine dans preload list
- **Effort estime**: S

---

## 8. Annexes

### A. Liste Complete des Endpoints (73 total)

#### Authentication (`/api/v1/auth`) - 8 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| POST | /login | login() |
| POST | /login/mfa | login_mfa() |
| POST | /register | register() |
| POST | /logout | logout() |
| POST | /refresh | refresh_tokens() |
| GET | /me | get_auth_status() |
| POST | /change-password | change_password() |
| POST | /verify-token | verify_token() |

#### MFA (`/api/v1/mfa`) - 7 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| POST | /setup | setup_mfa() |
| POST | /enable | enable_mfa() |
| POST | /disable | disable_mfa() |
| GET | /status | get_mfa_status() |
| POST | /verify | verify_totp() |
| POST | /recovery/verify | verify_recovery_code() |
| POST | /recovery/regenerate | regenerate_recovery_codes() |

#### Sessions (`/api/v1/sessions`) - 4 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | / | list_sessions() |
| GET | /{session_id} | get_session() |
| DELETE | /{session_id} | terminate_session() |
| DELETE | / | terminate_all_sessions() |

#### Users (`/api/v1/users`) - 10 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /me | get_my_profile() |
| PUT | /me | update_my_profile() |
| GET | / | list_users() |
| POST | / | create_user() |
| GET | /{user_id} | get_user() |
| PUT | /{user_id} | update_user() |
| DELETE | /{user_id} | delete_user() |
| POST | /{user_id}/verify | verify_user() |
| POST | /{user_id}/activate | activate_user() |
| POST | /{user_id}/deactivate | deactivate_user() |

#### API Keys (`/api/v1/api-keys`) - 4 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| POST | / | create_api_key() |
| GET | / | list_api_keys() |
| GET | /{key_id} | get_api_key() |
| DELETE | /{key_id} | revoke_api_key() |

#### OAuth (`/api/v1/oauth`) - 7 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /providers | get_providers() |
| GET | /{provider}/authorize | oauth_authorize() |
| GET | /{provider}/callback | oauth_callback() |
| POST | /complete-registration | complete_registration() |
| GET | /accounts | get_linked_accounts() |
| POST | /unlink | unlink_account() |
| GET | /{provider}/link | link_account() |

#### Password Reset (`/api/v1/password-reset`) - 3 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| POST | /request | request_password_reset() |
| POST | /confirm | confirm_password_reset() |
| GET | /validate/{token} | validate_reset_token() |

#### GDPR (`/api/v1/gdpr`) - 5 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /export | export_my_data() |
| GET | /export/{user_id} | export_user_data() |
| DELETE | /delete | delete_user_data() |
| POST | /anonymize | anonymize_user_data() |
| GET | /inventory | get_data_inventory() |

#### Catalog (`/api/v1/catalog`) - 3 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /products | list_products() |
| GET | /products/{produit_sk} | get_product_detail() |
| GET | /families | list_families() |

#### Analytics (`/api/v1/analytics`) - 10 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /categories | list_categories() |
| GET | /stock/valorisation | get_stock_valorisation() |
| GET | /stock/mouvements | get_stock_mouvements() |
| GET | /ventes/restaurant | get_ventes_restaurant() |
| GET | /ventes/top-plats | get_top_plats() |
| GET | /depenses/synthese | get_depenses_synthese() |
| GET | /produits/top | get_top_produits() |
| GET | /dashboard | get_dashboard_kpis() |
| POST | /classify-products | classify_products() |
| GET | /classify-products/preview | preview_classification() |

#### METRO (`/api/v1/metro`) - 12 endpoints
| Methode | Path | Handler |
|---------|------|---------|
| GET | /products | list_products() |
| GET | /products/{produit_id} | get_product() |
| GET | /products/ean/{ean} | get_product_by_ean() |
| GET | /factures | list_factures() |
| GET | /factures/{facture_id} | get_facture() |
| GET | /summary | get_summary() |
| GET | /dashboard | get_dashboard() |
| GET | /stats/categories | get_category_stats() |
| GET | /stats/tva | get_tva_stats() |
| GET | /categories | get_categories() |
| POST | /import | import_data() |
| POST | /recalculate | recalculate_aggregates() |

### B. Middlewares Actifs (ordre d'execution)

| # | Middleware | Fonction |
|---|------------|----------|
| 1 | TrustedHostMiddleware | Validation des hosts |
| 2 | CORSMiddleware | Cross-Origin Resource Sharing |
| 3 | SecurityHeadersMiddleware | Headers securite + HTTPS redirect |
| 4 | RateLimitMiddleware | 60 req/min global, 5 login |
| 5 | TenantMiddleware | Extraction X-Tenant-ID |
| 6 | GZipMiddleware | Compression > 1000 bytes |
| 7 | RequestIDMiddleware | X-Request-ID tracing |
| 8 | TimingMiddleware | X-Response-Time + slow request log |

### C. Modeles SQLAlchemy

| Modele | Table | Champs principaux |
|--------|-------|-------------------|
| Tenant | tenants | id, name, slug, is_active, settings |
| User | users | id, tenant_id, email, password_hash, is_active, is_verified, mfa_required |
| Session | sessions | id (UUID), user_id, tenant_id, ip, user_agent, absolute_expiry |
| RefreshToken | refresh_tokens | jti, session_id, token_hash, expires_at, used_at |
| RevokedToken | revoked_tokens | jti, expires_at, revoked_at |
| APIKey | api_keys | id, tenant_id, name, key_hash, scopes, expires_at |
| AuditLog | audit_log | id, event_type, user_id, tenant_id, ip, success, metadata |
| LoginAttempt | login_attempts | id, identifier, ip, attempted_at, success |
| MFASecret | mfa_secrets | user_id, tenant_id, secret (encrypted), enabled |
| MFARecoveryCode | mfa_recovery_codes | id, user_id, code_hash, used_at |
| OAuthAccount | oauth_accounts | id, user_id, provider, provider_user_id |
| PasswordResetToken | password_reset_tokens | id, user_id, token_hash, expires_at |
| Role | roles | id, tenant_id, code, name, is_system |
| Permission | permissions | id, code, name, resource, action |

---

**Fin du rapport d'audit**

*Document genere automatiquement. Pour toute question, contacter l'equipe technique.*
