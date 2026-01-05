# Tests - MassaCorp API

Suite de tests automatisés pour valider le bon fonctionnement de l'API MassaCorp.

## Structure du dossier

```
tests/
├── __init__.py                    # Package Python
├── conftest.py                    # Configuration pytest + fixtures globales
├── README.md                      # Ce fichier
│
├── unit/                          # Tests unitaires (sans DB)
│   ├── __init__.py
│   ├── test_security.py           # Tests sécurité (JWT, hashing)
│   ├── test_security_tokens.py    # Tests tokens avancés
│   ├── test_repositories.py       # Tests repositories Phase 1
│   ├── test_repositories_phase2.py # Tests repositories Phase 2
│   ├── test_repositories_mfa.py   # Tests repositories MFA (Phase 3)
│   ├── test_services.py           # Tests services Phase 1
│   ├── test_services_phase2.py    # Tests services Phase 2
│   ├── test_services_mfa.py       # Tests MFAService (Phase 3)
│   ├── test_mfa_security.py       # Tests sécurité MFA (Phase 3.1) - bcrypt, AES-256, timing
│   ├── test_models_mfa.py         # Tests modèles MFA (Phase 3)
│   ├── test_session_idor.py       # Tests sécurité IDOR sessions
│   ├── test_session_token_linking.py # Tests liaison session/token
│   │
│   │ === Tests TDD Corrections (Phase 4) ===
│   ├── test_mfa_integration.py    # Tests MFA dans auth flow (Issue #1)
│   ├── test_auth_fixes.py         # Tests /auth/me, tenant, deprecation (Issues #2,3,8,9)
│   ├── test_session_validation.py # Tests validation session (Issues #6,7,10,11)
│   ├── test_token_fixes.py        # Tests token rotation (Issues #4,5,12)
│   ├── test_critical_fixes.py     # Tests securite critique (secrets, IDOR)
│   ├── test_remaining_fixes.py    # Tests Phase 4.4 (startup, revoke, max_length)
│   │
│   │ === Tests TDD Corrections (Phase 5) ===
│   └── test_phase5_fixes.py       # Tests Phase 5 (17 issues: audit, tenant, logs, types)
│
├── integration/                   # Tests d'intégration (avec DB + API)
│   ├── __init__.py
│   ├── test_auth.py               # Tests endpoints auth
│   ├── test_sessions.py           # Tests endpoints sessions
│   └── test_mfa.py                # Tests endpoints MFA (Phase 3)
│
├── e2e/                           # Tests end-to-end (API complète)
│   └── __init__.py
│
└── factories/                     # Factories pour génération de données
    └── __init__.py
```

## Types de tests

### Tests unitaires (`unit/`)

Tests isolés sans dépendances externes (DB, Redis, etc.).

**Caractéristiques:**
- Rapides (< 100ms par test)
- Isolation complète
- Mocking des dépendances

**Exemples:**
- Validation de mots de passe
- Hashing bcrypt
- Création/vérification JWT
- Logique métier pure

**Fichiers de tests unitaires:**

| Fichier | Phase | Couverture |
|---------|-------|------------|
| `test_security.py` | 1 | Hashing bcrypt, JWT, validation MDP |
| `test_security_tokens.py` | 2 | Tokens avancés, révocation, replay |
| `test_repositories.py` | 1 | Repositories User, Tenant |
| `test_repositories_phase2.py` | 2 | Repositories Session, Token, Audit |
| `test_repositories_mfa.py` | 3 | MFASecretRepository, MFARecoveryCodeRepository |
| `test_services.py` | 1 | Services Auth, User, Tenant |
| `test_services_phase2.py` | 2 | Services Session, Token, Audit |
| `test_services_mfa.py` | 3 | MFAService (TOTP, recovery codes) |
| `test_mfa_security.py` | 3.1 | Sécurité MFA (bcrypt, AES-256-GCM, timing attacks, rate limiting) |
| `test_models_mfa.py` | 3 | Modèles MFASecret, MFARecoveryCode |
| `test_session_idor.py` | 2 | Protection IDOR sessions |
| `test_session_token_linking.py` | 2 | Liaison session ↔ refresh token |
| `test_mfa_integration.py` | 4 | MFA dans AuthService (Issue #1) |
| `test_auth_fixes.py` | 4 | Corrections auth/me, tenant, deprecation |
| `test_session_validation.py` | 4 | Validation session, include_inactive |
| `test_token_fixes.py` | 4 | Token rotation, get_user_tokens |
| `test_consistency_fixes.py` | 4 | Corrections coherence (16 issues) |
| `test_critical_fixes.py` | 4.1 | Corrections CRITIQUES securite (5 issues) |
| `test_remaining_fixes.py` | 4.4 | Corrections restantes (10 issues) |
| `test_phase5_fixes.py` | 5 | Corrections finales (17 issues: audit, tenant, logs, types) |

### Tests d'intégration (`integration/`)

Tests avec base de données PostgreSQL et API HTTP.

**Caractéristiques:**
- Base de données réelle (données du seed)
- TestClient FastAPI pour requêtes HTTP
- Validation des endpoints complets
- Authentification testée avec l'admin du seed

**Fichiers de tests d'intégration:**

| Fichier | Phase | Couverture |
|---------|-------|------------|
| `test_auth.py` | 1-2 | Login, logout, refresh, /me, change-password |
| `test_sessions.py` | 2 | Liste, termination, /sessions/* |
| `test_mfa.py` | 3 | Setup, enable, verify, disable, recovery codes |

**Exemples:**
- Flux d'authentification complet
- Gestion des sessions via API
- Configuration et vérification MFA (TOTP)
- Codes d'erreur HTTP

### Tests end-to-end (`e2e/`)

Tests de l'API complète via HTTP.

**Caractéristiques:**
- TestClient FastAPI
- Tests des endpoints complets
- Validation des réponses JSON

**Exemples:**
- Flux d'authentification
- CRUD via API
- Gestion des erreurs HTTP

## Configuration (conftest.py)

### Environnement de test

L'environnement de test (`ENV=test`) a des comportements specifiques pour eviter les faux positifs:

| Fonctionnalite | Comportement en test | Fichier |
|----------------|---------------------|---------|
| **Rate Limiting Middleware** | Desactive | `app/main.py` |
| **Brute-force Protection** | Desactive | `app/services/session.py` |
| **Login Attempts Tracking** | Nettoyage avant chaque test | `tests/conftest.py` |

> **Note:** Le header `X-Tenant-ID` est obligatoire pour `/auth/login` et `/auth/login/mfa`.
> Tous les tests d'integration doivent l'inclure: `headers={"X-Tenant-ID": "1"}`

### Fixtures principales

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_settings` | session | Configuration de test |
| `db_engine` | session | Engine SQLAlchemy |
| `db_session` | function | Session avec rollback + nettoyage login_attempts |
| `client` | function | TestClient FastAPI |

### Fixtures de données

| Fixture | Description |
|---------|-------------|
| `sample_password` | Mot de passe valide: `SecureP@ssw0rd123!` |
| `weak_passwords` | Liste de mots de passe faibles |
| `sample_email` | Email valide: `test@massacorp.local` |
| `invalid_emails` | Liste d'emails invalides |
| `sample_user_data` | Données utilisateur complètes |
| `sample_tenant_data` | Données tenant complètes |

### Fixtures JWT

| Fixture | Description |
|---------|-------------|
| `jwt_payload_valid` | Payload JWT valide (expire dans 15min) |
| `jwt_payload_expired` | Payload JWT expiré |
| `jwt_payload_refresh` | Payload refresh token |

## Markers pytest

```python
@pytest.mark.unit          # Tests unitaires
@pytest.mark.integration   # Tests d'intégration
@pytest.mark.e2e           # Tests end-to-end
@pytest.mark.security      # Tests de sécurité
@pytest.mark.slow          # Tests lents (> 1s)
```

## Exécution des tests

### Tous les tests

```bash
# Exécuter tous les tests
pytest

# Avec output verbose
pytest -v

# Avec affichage des prints
pytest -s
```

### Par catégorie

```bash
# Tests unitaires uniquement
pytest tests/unit/

# Tests d'intégration
pytest tests/integration/

# Tests e2e
pytest tests/e2e/

# Par marker
pytest -m unit
pytest -m "unit and not slow"
pytest -m security
```

### Tests spécifiques

```bash
# Un fichier
pytest tests/unit/test_security.py

# Une classe
pytest tests/unit/test_security.py::TestPasswordHashing

# Un test
pytest tests/unit/test_security.py::TestPasswordHashing::test_hash_password_returns_string
```

### Avec couverture

```bash
# Rapport console
pytest --cov=app

# Rapport HTML
pytest --cov=app --cov-report=html
# Ouvrir htmlcov/index.html

# Avec branches
pytest --cov=app --cov-branch --cov-report=term-missing
```

## Écrire un nouveau test

### Test unitaire

```python
# tests/unit/test_example.py
import pytest

class TestExample:
    """Tests pour le module example"""

    @pytest.mark.unit
    def test_function_returns_expected(self):
        """Description claire du test"""
        from app.module import function

        result = function("input")

        assert result == "expected"

    @pytest.mark.unit
    def test_function_raises_on_invalid(self):
        """La fonction doit lever une exception pour input invalide"""
        from app.module import function, CustomError

        with pytest.raises(CustomError):
            function(None)
```

### Test d'intégration

```python
# tests/integration/test_user_repository.py
import pytest
from app.repositories.user import UserRepository
from app.models.user import User

class TestUserRepository:
    """Tests du repository User"""

    @pytest.mark.integration
    def test_create_user(self, db_session):
        """Création d'un utilisateur en DB"""
        repo = UserRepository(db_session)

        user = repo.create({
            "email": "test@test.com",
            "password_hash": "hash",
            "tenant_id": 1
        })

        assert user.id is not None
        assert user.email == "test@test.com"

    @pytest.mark.integration
    def test_get_by_email(self, db_session):
        """Récupération par email"""
        repo = UserRepository(db_session)

        # Setup
        repo.create({"email": "find@test.com", "tenant_id": 1})

        # Test
        user = repo.get_by_email("find@test.com", tenant_id=1)

        assert user is not None
        assert user.email == "find@test.com"
```

### Test e2e

```python
# tests/e2e/test_auth.py
import pytest

class TestAuthEndpoints:
    """Tests des endpoints d'authentification"""

    @pytest.mark.e2e
    def test_login_success(self, client):
        """Login avec credentials valides"""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "ValidP@ss123!"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.e2e
    def test_login_invalid_password(self, client):
        """Login avec mauvais mot de passe"""
        response = client.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "WrongPassword"
        })

        assert response.status_code == 401
```

## Bonnes pratiques

### 1. Nommage

```python
# Bon: descriptif et clair
def test_create_user_with_valid_data_returns_user():
def test_login_with_expired_token_returns_401():

# Mauvais: vague
def test_user():
def test_login():
```

### 2. Structure AAA (Arrange-Act-Assert)

```python
def test_example(self):
    # Arrange - Préparer les données
    user_data = {"email": "test@test.com"}

    # Act - Exécuter l'action
    result = create_user(user_data)

    # Assert - Vérifier le résultat
    assert result.email == "test@test.com"
```

### 3. Un test = une assertion principale

```python
# Bon: tests séparés
def test_user_creation_sets_id(self):
    user = create_user(data)
    assert user.id is not None

def test_user_creation_sets_email(self):
    user = create_user(data)
    assert user.email == data["email"]

# Acceptable: assertions liées
def test_user_creation_returns_valid_user(self):
    user = create_user(data)
    assert user.id is not None
    assert user.email == data["email"]
```

### 4. Isolation des tests

```python
# Chaque test doit être indépendant
# Ne jamais dépendre de l'ordre d'exécution
# Utiliser les fixtures pour le setup
```

### 5. Tests de sécurité

```python
@pytest.mark.security
def test_password_hash_not_reversible(self):
    """Le hash ne doit pas contenir le password"""
    hashed = hash_password("secret")
    assert "secret" not in hashed
```

## CI/CD

### GitHub Actions (exemple)

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: MassaCorp_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install poetry && poetry install
      - name: Run tests
        run: poetry run pytest --cov=app
```

## Debugging

```bash
# Afficher les prints
pytest -s

# S'arrêter au premier échec
pytest -x

# Relancer seulement les tests échoués
pytest --lf

# Mode debug avec pdb
pytest --pdb

# Verbose avec traceback complet
pytest -vvv --tb=long
```

## État actuel des tests

```
Phase 1 (Foundation):      ~150 tests
Phase 2 (Sessions):        ~180 tests
Phase 3 (MFA):             ~107 tests
Phase 3.1 (MFA Security):   16 tests (bcrypt, AES-256, timing)
Phase 4 (TDD Corrections):  46 tests (12 issues corrigées)
Phase 4.1 (Coherence):      16 tests (16 issues coherence)
Phase 4.2 (Critiques):      20 tests (5 issues securite critique)
Phase 4.3 (Mineurs):        24 tests (14 issues mineures)
Phase 4.4 (Remaining):      17 tests (10 issues restantes)
Phase 5 (Final Fixes):      20 tests (17 issues finales)
────────────────────────────────────
Tests unitaires:           596 passed
Tests intégration:          39 passed
────────────────────────────────────
Total:                     635 passed (25 skipped)
```

### Tests TDD Phase 4 (Corrections Issues)

| Fichier | Tests | Issues Couvertes |
|---------|-------|------------------|
| `test_mfa_integration.py` | 13 | #1 MFA bypassable au login |
| `test_auth_fixes.py` | 14 | #2 mfa_enabled False, #3 cross-tenant, #8 tenant header, #9 has_mfa |
| `test_session_validation.py` | 12 | #6 is_session_valid, #7 except_jti, #10 include_inactive, #11 audit |
| `test_token_fixes.py` | 7 | #4 double stockage, #5 session validation, #12 get_user_tokens |
| `test_consistency_fixes.py` | 16 | Coherence: tenant validation, token rotation, nommage, encapsulation |
| `test_critical_fixes.py` | 20 | Securite: secrets, payload validation, IDOR cross-tenant, session_id |
| `test_minor_fixes.py` | 24 | Mineurs: typage, logging ERROR, TOTP format, email case, pagination, LoginResponse unifié |
| `test_remaining_fixes.py` | 17 | Phase 4.4: validate_secrets startup, MFA warning, X-Tenant-ID login/mfa, exceptions consolidées, change_password revoke, cleanup tenant, password max_length, MFA max_length |

### Tests TDD Phase 5 (Corrections Finales)

| Fichier | Tests | Issues Couvertes |
|---------|-------|------------------|
| `test_phase5_fixes.py` | 20 | 17 issues finales |

**Issues Phase 5 corrigées:**

| Priorité | Issue | Correction |
|----------|-------|------------|
| CRITIQUE | Session creation logging | Warning si session=None au login |
| CRITIQUE | Audit user operations | delete/activate/deactivate avec audit_service |
| CRITIQUE | Duplicate TokenRevokedError | Import depuis exceptions.py |
| HAUTE | tenant_id validation sessions | Warning si tenant_id=None |
| HAUTE | export_audit tenant warning | Docstring caller must verify |
| HAUTE | SessionRepository tenant check | get_by_id_and_tenant() ajouté |
| MOYENNE | Bulk update flush | synchronize_session='fetch' + flush() |
| BASSE | Log language EN | Logs standardisés en anglais |
| BASSE | Type hints spécifiques | Session/LoginAttempt au lieu de Any |

**Approche TDD:**
1. Tests RED écrits AVANT implémentation
2. Implémentation GREEN pour faire passer les tests
3. Refactor si nécessaire

### Tests de sécurité MFA (Phase 3.1)

| Catégorie | Tests | Vérifie |
|-----------|-------|---------|
| Rate Limiting | 3 | Endpoints MFA avec limites strictes (5/min, 3/min) |
| Bcrypt Recovery | 4 | Hachage lent, salt unique, vérification |
| Timing Attacks | 2 | Comparaison constant-time (bcrypt.checkpw) |
| TOTP Encryption | 5 | AES-256-GCM, IV unique, round-trip |
| Integration | 2 | Service utilise chiffrement/hachage |

### Couverture par module

| Module | Tests | Couverture |
|--------|-------|------------|
| `core/security.py` | 45+ | JWT, hashing, validation |
| `repositories/*` | 80+ | CRUD, queries |
| `services/*` | 120+ | Logique métier |
| `api/v1/endpoints/*` | 39 | Endpoints HTTP |
| `models/*` | 30+ | Modèles SQLAlchemy |

### Exécution rapide

```bash
# Exécuter tous les tests (depuis le conteneur)
docker exec massacorp_api pytest -v

# Avec couverture
docker exec massacorp_api pytest --cov=app --cov-report=term-missing
```
