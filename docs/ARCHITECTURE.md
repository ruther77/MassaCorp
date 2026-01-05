# Architecture MassaCorp

Document d'architecture technique pour la plateforme SaaS MassaCorp.

## Vue d'ensemble

MassaCorp est une API REST sécurisée multi-tenant avec isolation réseau complète via WireGuard.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ARCHITECTURE GLOBALE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INTERNET                                                                  │
│      │                                                                      │
│      │ UDP:51820                                                            │
│      ▼                                                                      │
│   ┌──────────────────┐                                                      │
│   │    WireGuard     │ ◄── Seul point d'entrée                             │
│   │    10.10.0.1     │                                                      │
│   └────────┬─────────┘                                                      │
│            │                                                                │
│   ═════════╪═════════════════════════════════════════════════════════       │
│   ║  RÉSEAU PRIVÉ 10.10.0.0/24                                     ║       │
│   ║        │                                                        ║       │
│   ║   ┌────┴────┬─────────────┬─────────────┐                      ║       │
│   ║   │         │             │             │                      ║       │
│   ║   ▼         ▼             ▼             ▼                      ║       │
│   ║ ┌─────┐  ┌─────┐      ┌─────┐       ┌─────┐                   ║       │
│   ║ │ API │  │ DB  │      │Redis│       │Sync │                   ║       │
│   ║ │.0.2 │  │.0.3 │      │.0.5 │       │.0.4 │                   ║       │
│   ║ └─────┘  └─────┘      └─────┘       └─────┘                   ║       │
│   ╚════════════════════════════════════════════════════════════════╝       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Principes architecturaux

### 1. Zero-Trust Security

- Aucun service exposé directement sur Internet
- Authentification obligatoire via WireGuard
- Validation à chaque couche

### 2. Multi-Tenancy

- Isolation complète des données par tenant
- Chaque table sensible contient `tenant_id`
- Aucun accès croisé possible

### 3. Defense in Depth

- VPN (WireGuard) → API (JWT) → DB (isolation)
- Chiffrement des données sensibles (AES-256)
- Audit complet des actions

### 4. Separation of Concerns

- Couches distinctes (API → Services → Repository → DB)
- Responsabilité unique par module
- Testabilité à chaque niveau

## Stack technique

```
┌─────────────────────────────────────────────────────────────────┐
│                          STACK TECHNIQUE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Frontend (futur)                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  React / Vue / Next.js (à définir)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  API Layer                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  FastAPI 0.115+ (Python 3.12)                           │   │
│  │  ├── Pydantic 2.x (validation)                          │   │
│  │  ├── python-jose (JWT)                                  │   │
│  │  └── bcrypt (hashing)                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  Data Layer                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SQLAlchemy 2.0 (ORM)                                   │   │
│  │  Alembic (migrations)                                   │   │
│  │  PostgreSQL 16 (stockage)                               │   │
│  │  Redis 7 (cache/sessions)                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  Infrastructure                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Docker + Docker Compose                                │   │
│  │  WireGuard (VPN)                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture applicative

### Couches de l'application

```
┌─────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE EN COUCHES                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                     API LAYER                            │   │
│   │   main.py + api/v1/endpoints/*.py                        │   │
│   │   - Endpoints REST (auth, users, sessions)              │   │
│   │   - Validation entrée (Pydantic)                        │   │
│   │   - Authentification (JWT via dependencies.py)          │   │
│   │   - Sérialisation sortie                                │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   SERVICES LAYER (Phase 2)               │   │
│   │   services/*.py                                          │   │
│   │   - Logique métier (AuthService, UserService...)        │   │
│   │   - Gestion des sessions et tokens                      │   │
│   │   - Protection brute-force                              │   │
│   │   - Audit logging                                       │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   SCHEMAS LAYER                          │   │
│   │   schemas/*.py                                           │   │
│   │   - Validation des données                              │   │
│   │   - Transformation entrée/sortie                        │   │
│   │   - Documentation OpenAPI                               │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                 REPOSITORY LAYER                         │   │
│   │   repositories/*.py                                      │   │
│   │   - Accès aux données (CRUD)                            │   │
│   │   - Queries SQL                                         │   │
│   │   - Isolation multi-tenant                              │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   MODEL LAYER                            │   │
│   │   models/*.py                                            │   │
│   │   - Entités SQLAlchemy                                  │   │
│   │   - Relations                                           │   │
│   │   - Contraintes DB                                      │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                   CORE LAYER                             │   │
│   │   core/*.py                                              │   │
│   │   - Configuration                                       │   │
│   │   - Sécurité (JWT, hashing)                            │   │
│   │   - Database connection                                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Flux d'une requête

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUX D'UNE REQUÊTE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. CLIENT                                                     │
│      │                                                          │
│      │ HTTPS via WireGuard                                      │
│      ▼                                                          │
│   2. FASTAPI MIDDLEWARE                                         │
│      ├── CORS                                                   │
│      ├── Request logging                                        │
│      └── Exception handling                                     │
│      │                                                          │
│      ▼                                                          │
│   3. ROUTER (api/v1/users.py)                                   │
│      ├── Path parsing                                           │
│      └── Dependency injection                                   │
│      │                                                          │
│      ▼                                                          │
│   4. AUTHENTICATION                                             │
│      ├── Extract JWT from header                                │
│      ├── Validate signature                                     │
│      ├── Check expiration                                       │
│      └── Extract user_id + tenant_id                           │
│      │                                                          │
│      ▼                                                          │
│   5. VALIDATION (Pydantic Schema)                               │
│      ├── Parse request body                                     │
│      ├── Validate types                                         │
│      └── Apply constraints                                      │
│      │                                                          │
│      ▼                                                          │
│   6. REPOSITORY                                                 │
│      ├── Build query with tenant_id                            │
│      ├── Execute SQL                                            │
│      └── Return model                                           │
│      │                                                          │
│      ▼                                                          │
│   7. RESPONSE                                                   │
│      ├── Serialize to schema                                    │
│      ├── Add headers                                            │
│      └── Return JSON                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture de sécurité

### Authentification

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUX D'AUTHENTIFICATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LOGIN                                                         │
│   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐        │
│   │ Client │───▶│  API   │───▶│ Verify │───▶│ Create │        │
│   │email/pw│    │/login  │    │bcrypt  │    │JWT     │        │
│   └────────┘    └────────┘    └────────┘    └───┬────┘        │
│                                                  │              │
│                                                  ▼              │
│   ┌────────────────────────────────────────────────────┐       │
│   │  { access_token, refresh_token, expires_in }       │       │
│   └────────────────────────────────────────────────────┘       │
│                                                                 │
│   REQUÊTE AUTHENTIFIÉE                                          │
│   ┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐        │
│   │ Client │───▶│  API   │───▶│Validate│───▶│Extract │        │
│   │Bearer  │    │/users  │    │JWT     │    │user_id │        │
│   └────────┘    └────────┘    └────────┘    └───┬────┘        │
│                                                  │              │
│                                                  ▼              │
│   ┌────────────────────────────────────────────────────┐       │
│   │  { sub: 42, tenant_id: 7, exp: 1234567890 }        │       │
│   └────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tokens JWT

| Type | Durée | Contenu | Usage |
|------|-------|---------|-------|
| Access Token | 15 min | sub, tenant_id, email, type, exp | Requêtes API |
| Refresh Token | 7 jours | sub, tenant_id, jti, type, exp | Renouvellement |
| MFA Session | 5 min | sub, tenant_id, type="mfa_session", exp | Flow MFA 2 étapes (Issue #1) |

> **Note:** Le MFA Session Token ne donne pas accès à l'API. Il sert uniquement à
> compléter l'authentification MFA via `POST /auth/login/mfa`.

### Validation des mots de passe

- Minimum 8 caractères
- Au moins 1 majuscule
- Au moins 1 minuscule
- Au moins 1 chiffre
- Au moins 1 caractère spécial
- Maximum 128 caractères

### Stockage sécurisé

| Donnée | Méthode |
|--------|---------|
| Mots de passe | bcrypt (cost 12) |
| Tokens revoqués | SHA-256 |
| Secrets MFA | AES-256-GCM (chiffré) |
| Recovery codes MFA | bcrypt (cost 10) |
| API Keys | SHA-256 |

## Architecture Base de Données

### Schéma principal

```
┌─────────────────────────────────────────────────────────────────┐
│                      MODÈLE DE DONNÉES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐                                               │
│   │   tenants   │ 1                                             │
│   ├─────────────┤───────────┐                                   │
│   │ id          │           │                                   │
│   │ name        │           │                                   │
│   │ slug        │           │                                   │
│   │ is_active   │           │                                   │
│   │ settings    │           │                                   │
│   └─────────────┘           │ *                                 │
│                       ┌─────────────┐                           │
│                       │    users    │                           │
│                       ├─────────────┤                           │
│                       │ id          │                           │
│                       │ tenant_id   │                           │
│                       │ email       │                           │
│                       │ password_   │                           │
│                       │    hash     │                           │
│                       │ is_active   │                           │
│                       │ is_verified │                           │
│                       │ first_name  │                           │
│                       │ last_name   │                           │
│                       └─────────────┘                           │
│                             │                                   │
│                             │ 1                                 │
│              ┌──────────────┼──────────────┐                    │
│              │ *            │ *            │ *                  │
│        ┌───────────┐  ┌───────────┐  ┌───────────┐             │
│        │ sessions  │  │ mfa_      │  │ user_     │             │
│        │           │  │ secrets   │  │ roles     │             │
│        └───────────┘  └───────────┘  └───────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Modules de la base de données

| Module | Tables | Description |
|--------|--------|-------------|
| `auth` | sessions, refresh_tokens, revoked_tokens | Authentification |
| `rbac` | roles, permissions, user_roles | Contrôle d'accès |
| `mfa` | mfa_secrets, mfa_recovery_codes | Multi-facteurs |
| `sso` | identity_providers, user_identities | Single Sign-On |
| `api_keys` | api_keys, api_key_usage | Auth M2M |
| `audit` | audit_log | Traçabilité |
| `features` | features, feature_flags_* | Feature flags |
| `security` | login_attempts | Anti-bruteforce |
| `wireguard` | wg_peers, wg_ip_pool | VPN |

## Architecture réseau

### Allocation IP

| Adresse | Service |
|---------|---------|
| 10.10.0.1 | WireGuard (gateway) |
| 10.10.0.2 | API FastAPI |
| 10.10.0.3 | PostgreSQL |
| 10.10.0.4 | WG Sync service |
| 10.10.0.5 | Redis |
| 10.10.0.6-253 | Clients VPN |
| 10.10.0.254 | Docker gateway |

### Ports

| Port | Protocole | Service | Exposé |
|------|-----------|---------|--------|
| 51820 | UDP | WireGuard | Oui |
| 8000 | TCP | API | Non (interne) |
| 5432 | TCP | PostgreSQL | Non (interne) |
| 6379 | TCP | Redis | Non (interne) |

## Scalabilité

### Actuel (Single Node)

```
┌─────────────────────────────────────────┐
│              SINGLE NODE                 │
│  ┌─────────────────────────────────┐    │
│  │  Docker Host                    │    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐       │    │
│  │  │ WG  │ │ API │ │ DB  │       │    │
│  │  └─────┘ └─────┘ └─────┘       │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Futur (Multi Node)

```
┌─────────────────────────────────────────────────────────────────┐
│                        MULTI NODE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Load Balancer                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                     HAProxy/Nginx                        │   │
│   └───────────────────────────┬─────────────────────────────┘   │
│                               │                                 │
│           ┌───────────────────┼───────────────────┐            │
│           │                   │                   │            │
│           ▼                   ▼                   ▼            │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │   API 1     │     │   API 2     │     │   API 3     │      │
│   └─────────────┘     └─────────────┘     └─────────────┘      │
│           │                   │                   │            │
│           └───────────────────┼───────────────────┘            │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    Redis Cluster                         │   │
│   │              (Sessions + Cache)                          │   │
│   └─────────────────────────────────────────────────────────┘   │
│                               │                                 │
│                               ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              PostgreSQL (Primary + Replicas)             │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Monitoring (futur)

```
┌─────────────────────────────────────────────────────────────────┐
│                       OBSERVABILITÉ                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │  Prometheus │───▶│   Grafana   │◀───│   Loki      │        │
│   │  (Metrics)  │    │ (Dashboard) │    │  (Logs)     │        │
│   └─────────────┘    └─────────────┘    └─────────────┘        │
│         ▲                                      ▲                │
│         │                                      │                │
│   ┌─────┴───────────────────────────────────────┴─────┐        │
│   │                    Services                        │        │
│   │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐     │        │
│   │  │ WG  │  │ API │  │ DB  │  │Redis│  │Sync │     │        │
│   │  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘     │        │
│   └────────────────────────────────────────────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Conformité

| Standard | Mesures |
|----------|---------|
| **RGPD** | Audit trail, pseudonymisation, droit à l'oubli |
| **SOC2** | Logging, contrôles d'accès, chiffrement |
| **ISO 27001** | RBAC, MFA, traçabilité |

## État d'avancement

### Phase 1 - Fondations (Terminé)

- [x] Architecture multi-tenant
- [x] Authentification JWT (access + refresh tokens)
- [x] Intégration WireGuard
- [x] Modèles User/Tenant
- [x] Repositories CRUD génériques
- [x] Schémas Pydantic
- [x] Tests unitaires security/repositories

### Phase 2 - Sécurité avancée (Terminé)

- [x] Couche Services (AuthService, UserService, etc.)
- [x] Endpoints auth (/login, /logout, /refresh, /me)
- [x] Endpoints users (CRUD + profil)
- [x] Endpoints sessions (liste, termination)
- [x] Gestion des sessions en DB
- [x] Protection brute-force (lockout)
- [x] Rotation des refresh tokens
- [x] Détection attaques replay
- [x] Audit logging complet
- [x] Tests unitaires services Phase 2
- [x] Tests intégration auth/sessions
- [x] Script de seed (tenants + admin)
- [x] Injection de dépendances centralisée

### Phase 3 - MFA & Rate Limiting (Terminé)

- [x] MFA TOTP (Google Authenticator, Authy compatible)
- [x] Chiffrement secrets TOTP (AES-256-GCM)
- [x] Recovery codes avec bcrypt (résistant brute-force)
- [x] Rate limiting endpoints MFA (5 req/min verify, 3 req/min recovery)
- [x] Protection timing attacks (bcrypt.checkpw constant-time)
- [x] Tests unitaires sécurité MFA (16 tests)

### Phase 4 - Corrections TDD (Terminé)

12 issues de sécurité/cohérence corrigées avec approche TDD strict (RED → GREEN → REFACTOR):

**Critiques (Issues #1-3):**
- [x] MFA 2 étapes dans login (`mfa_session_token`)
- [x] `/auth/me` retourne `mfa_enabled` réel
- [x] `get_by_email()` deprecation warning + log

**Hautes (Issues #4-7):**
- [x] Token rotation unique (pas de double stockage)
- [x] Validation session au refresh
- [x] `is_session_valid(session_id)` fonctionne
- [x] `except_session_id` pour logout partiel

**Moyennes (Issues #8-12):**
- [x] Header `X-Tenant-ID` obligatoire
- [x] `has_mfa` réel dans profil utilisateur
- [x] `include_inactive` fonctionne pour sessions
- [x] Audit log CRITICAL en cas d'échec
- [x] `get_user_tokens()` appelle le repository

**Tests:** 46 nouveaux tests TDD, total 518 tests passent.

### Phase 4.4 - Corrections Restantes (Terminé)

10 issues supplémentaires corrigées avec approche TDD:

**Sécurité startup:**
- [x] `validate_secrets()` appelée au démarrage (bloque en production si secrets par défaut)
- [x] Warning log si `mfa_service=None` dans AuthService

**Cohérence API:**
- [x] Header `X-Tenant-ID` requis sur `/auth/login/mfa`
- [x] Exceptions consolidées (suppression doublons `session.py`)

**Sécurité sessions:**
- [x] `change_password()` révoque toutes les sessions (sauf courante)
- [x] `cleanup_expired_sessions()` accepte `tenant_id` pour isolation

**Validation schemas:**
- [x] `LoginRequest.password` avec `max_length=128` (protection DoS bcrypt)
- [x] `MFAVerifyRequest.code` avec `max_length=9` (accepte recovery codes)

**Tests:** 17 nouveaux tests TDD, total 595 tests passent.

### Phase 5 - Corrections Finales (Terminé)

17 issues de qualité code et sécurité corrigées avec approche TDD:

**Critiques:**
- [x] Session creation logging (warning si session=None au login)
- [x] Audit user operations (delete/activate/deactivate avec audit_service)
- [x] TokenRevokedError unique (import depuis exceptions.py)

**Hautes (Tenant Isolation):**
- [x] tenant_id validation dans `get_user_sessions()` (warning si None)
- [x] `export_audit_logs()` docstring WARNING caller must verify
- [x] `SessionRepository.get_by_id_and_tenant()` ajouté

**Moyennes:**
- [x] Bulk update flush (`invalidate_all_sessions` avec synchronize_session='fetch')

**Basses (Code Quality):**
- [x] Log language standardisé EN (logs français → anglais)
- [x] Type hints spécifiques (`Session`/`LoginAttempt` au lieu de `Any`)

**Fichiers modifiés:**
- `app/api/v1/endpoints/users.py` - Audit logging
- `app/services/token.py` - Import exception
- `app/services/session.py` - Type hints + validation
- `app/services/audit.py` - Docstring warning
- `app/repositories/session.py` - get_by_id_and_tenant + flush
- `app/services/auth.py` - Logs EN

**Tests:** 20 nouveaux tests TDD, total 635 tests passent (596 unit + 39 integration).

> **Note:** Les tests d'integration passent tous grace a la desactivation du rate limiting
> en environnement de test (`ENV=test`). Voir `tests/README.md` pour details.

### Évolutions prévues (Phase 6+)

- [ ] SSO (OIDC/SAML)
- [ ] Feature flags
- [ ] Webhooks
- [ ] Dashboard admin
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Backup automatisé
- [ ] CI/CD (GitHub Actions)
- [ ] Tests e2e complets
