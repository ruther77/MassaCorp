# Services - Couche Métier MassaCorp

Couche de services contenant la logique métier de l'application, séparée des repositories (accès données) et des endpoints (API).

## Structure

```
services/
├── __init__.py          # Exports et documentation
├── README.md            # Ce fichier
├── exceptions.py        # Exceptions métier
├── auth.py              # Authentification (login, tokens, sessions)
├── user.py              # Gestion des utilisateurs
├── tenant.py            # Gestion des tenants
├── session.py           # Gestion des sessions (Phase 2)
├── token.py             # Gestion des refresh tokens (Phase 2)
└── audit.py             # Logging d'audit (Phase 2)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENDPOINTS (API)                           │
│                    api/v1/endpoints/*.py                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         SERVICES                                 │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│   │ AuthService │ │ UserService │ │TenantService│              │
│   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│          │               │               │                      │
│   ┌──────┴───────────────┴───────────────┴──────┐              │
│   │          Services Phase 2                    │              │
│   │ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │              │
│   │ │SessionService│ │TokenService │ │AuditSvc│ │              │
│   │ └─────────────┘ └─────────────┘ └─────────┘ │              │
│   └─────────────────────────────────────────────┘              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       REPOSITORIES                               │
│                    repositories/*.py                             │
└─────────────────────────────────────────────────────────────────┘
```

## Services disponibles

### AuthService (`auth.py`)

Service d'authentification complet avec protection brute-force et audit.

**Responsabilités:**
- Authentification email/password
- Génération de tokens JWT (access + refresh)
- Rotation sécurisée des tokens
- Gestion des sessions
- Protection brute-force (lockout)
- Audit logging des événements de sécurité

**Méthodes:**

| Méthode | Description | Phase |
|---------|-------------|-------|
| `authenticate(email, password, tenant_id)` | Authentifie un utilisateur | 1 |
| `login(email, password, tenant_id, ip, user_agent)` | Connexion complète avec session | 1+2+3 |
| `complete_mfa_login(mfa_session_token, totp_code, ip, user_agent, expected_tenant_id)` | Complète login MFA 2ème étape | 3 |
| `logout(user_id, tenant_id, ...)` | Déconnexion avec révocation | 1+2 |
| `validate_token(token)` | Valide un token JWT | 1 |
| `refresh_tokens(refresh_token, ip)` | Rotation des tokens + validation session | 1+2 |
| `get_current_user(token)` | Récupère l'utilisateur du token | 1 |

> **Note (Issue #1):** `login()` retourne maintenant `{mfa_required: true, mfa_session_token: "..."}`
> si MFA est activé. Appeler ensuite `complete_mfa_login()` pour obtenir les tokens.
>
> **Note (Issue #5):** `refresh_tokens()` valide maintenant que la session associée est active.
>
> **Note (Securite):** `complete_mfa_login()` accepte `expected_tenant_id` pour valider que le
> tenant_id dans le token MFA correspond au header X-Tenant-ID (protection cross-tenant).
>
> **Warning (Phase 4.4):** Si `mfa_service=None`, un warning est loggé et la vérification MFA
> est désactivée. Toujours injecter `MFAService` en production pour éviter de bypasser le MFA.

**Exemple d'utilisation:**

```python
from app.services import AuthService
from app.repositories.user import UserRepository

auth_service = AuthService(
    user_repository=UserRepository(db),
    session_service=session_service,  # Phase 2
    token_service=token_service,      # Phase 2
    audit_service=audit_service,      # Phase 2
    mfa_service=mfa_service           # Phase 3 (Issue #1)
)

# Login sans MFA
result = auth_service.login(
    email="user@example.com",
    password="SecureP@ss123!",
    tenant_id=1,
    ip_address="192.168.1.1"
)
# Résultat sans MFA:
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 900,
    "session_id": "uuid-session-id"
}

# Login avec MFA activé (Issue #1)
result = auth_service.login(...)
# Résultat avec MFA:
{
    "mfa_required": True,
    "mfa_session_token": "eyJhbGci...",
    "message": "MFA verification required"
}

# Compléter le login MFA
tokens = auth_service.complete_mfa_login(
    mfa_session_token=result["mfa_session_token"],
    totp_code="123456",
    ip_address="192.168.1.1"
)
# Résultat:
{
    "access_token": "eyJhbGci...",
    "refresh_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 900,
    "session_id": "uuid-session-id"
}
```

**Configuration brute-force:**
- `MAX_LOGIN_ATTEMPTS`: 5 échecs avant lockout
- `LOCKOUT_MINUTES`: 30 minutes de verrouillage

### UserService (`user.py`)

Gestion CRUD des utilisateurs avec validation métier.

**Responsabilités:**
- Création d'utilisateurs avec validation
- Mise à jour du profil
- Changement de mot de passe
- Vérification email
- Activation/désactivation

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `create_user(email, password, tenant_id, ...)` | Crée un utilisateur |
| `get_user(user_id)` | Récupère par ID |
| `get_user_by_email(email, tenant_id)` | Récupère par email |
| `update_user(user_id, data)` | Met à jour le profil |
| `delete_user(user_id)` | Supprime un utilisateur |
| `list_users(tenant_id, skip, limit)` | Liste paginée |
| `change_password(user_id, current, new, current_session_id)` | Change le mot de passe + révoque sessions |
| `verify_user(user_id)` | Marque comme vérifié |
| `activate_user(user_id)` / `deactivate_user(user_id)` | Active/désactive |

**Exemple:**

```python
from app.services import UserService

user_service = UserService(
    user_repository=UserRepository(db),
    tenant_repository=TenantRepository(db),
    session_service=session_service  # Phase 4.4 - révocation sessions
)

# Créer un utilisateur
user = user_service.create_user(
    email="new@example.com",
    password="SecureP@ss123!",
    tenant_id=1,
    first_name="John",
    last_name="Doe"
)

# Changer le mot de passe (révoque toutes les sessions sauf la courante)
user_service.change_password(
    user_id=user.id,
    current_password="SecureP@ss123!",
    new_password="NewSecureP@ss456!",
    current_session_id="uuid-session-courante"  # Optionnel
)
```

> **Note (Phase 4.4):** `change_password()` révoque maintenant toutes les sessions
> de l'utilisateur (sauf `current_session_id` si spécifié) pour des raisons de sécurité.
> Utilise `session_service.terminate_all_sessions()` en interne.

### TenantService (`tenant.py`)

Gestion des tenants (organisations).

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `create_tenant(name, slug, settings)` | Crée un tenant |
| `get_tenant(tenant_id)` | Récupère par ID |
| `get_tenant_by_slug(slug)` | Récupère par slug |
| `update_tenant(tenant_id, data)` | Met à jour |
| `deactivate_tenant(tenant_id)` | Désactive |

### SessionService (`session.py`) - Phase 2

Gestion des sessions utilisateur et protection brute-force.

**Responsabilités:**
- Création/termination de sessions
- Suivi des sessions actives
- Protection brute-force (login attempts)
- Détection de comptes verrouillés

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `create_session(user_id, tenant_id, ip, user_agent)` | Crée une session |
| `get_session(session_id)` | Récupère une session |
| `get_session_by_id(session_id)` | Récupère une session par UUID (Issue #5) |
| `terminate_session(session_id, user_id)` | Termine une session |
| `terminate_all_sessions(user_id, except_session_id)` | Termine toutes sauf une (Issue #7) |
| `get_user_sessions(user_id, include_inactive)` | Liste les sessions (Issue #10) |
| `cleanup_expired_sessions(older_than_days, tenant_id)` | Nettoie les sessions expirées (Phase 4.4) |
| `record_login_attempt(email, tenant_id, success, ip)` | Enregistre une tentative |
| `is_account_locked(email, tenant_id, ...)` | Vérifie le lockout |
| `detect_suspicious_activity(user_id, current_ip, current_user_agent)` | Détecte activité suspecte |

> **Note (Issue #7):** `terminate_all_sessions()` accepte maintenant `except_session_id` (UUID).
>
> **Note (Phase 5):** `detect_suspicious_activity()` retourne maintenant un dict complet:
> ```python
> {
>     "multiple_ips": bool,      # Plus d'une IP active
>     "ip_count": int,           # Nombre d'IPs distinctes
>     "multiple_agents": bool,   # Plus d'un User-Agent
>     "agent_count": int,        # Nombre d'agents distincts
>     "new_ip": bool,            # L'IP courante est nouvelle
>     "new_agent": bool          # Le User-Agent courant est nouveau
> }
> ```
>
> **Note (Issue #10):** `get_user_sessions()` avec `include_inactive=True` retourne aussi les sessions révoquées.
>
> **Note (Phase 4.4):** `cleanup_expired_sessions()` accepte maintenant `tenant_id` pour isolation multi-tenant.
>
> **Note (Phase 5):** `get_user_sessions()` log un warning si `tenant_id=None` (rappel isolation multi-tenant).
> Type hints spécifiques (`Session`, `LoginAttempt`) au lieu de `Any` pour meilleure autocomplétion.
> Nouvelle méthode `get_session_by_id_for_tenant(session_id, tenant_id)` pour isolation tenant stricte.

**Environnement de test:**

Le brute-force protection est **desactive en environnement de test** (`ENV=test`) pour eviter
les faux positifs lors de l'execution des tests d'integration. La methode `is_account_locked()`
retourne toujours `False` quand `ENV=test`.

```python
# app/services/session.py
_IS_TEST_ENV = os.getenv("ENV") == "test"

def is_account_locked(self, ...):
    if _IS_TEST_ENV:
        return False  # Desactive en test
    # ... logique normale
```

### TokenService (`token.py`) - Phase 2

Gestion des refresh tokens avec détection de replay.

**Responsabilités:**
- Stockage des refresh tokens en DB
- Révocation de tokens
- Détection d'attaques de replay
- Rotation des tokens

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `store_refresh_token(jti, user_id, ...)` | Stocke un token |
| `revoke_refresh_token(jti)` | Révoque un token |
| `revoke_all_user_tokens(user_id, tenant_id)` | Révoque tous les tokens |
| `is_token_revoked(jti)` | Vérifie si révoqué |
| `detect_token_replay(jti)` | Détecte les replays |
| `rotate_refresh_token(old_jti, new_jti, ...)` | Marque l'ancien token comme utilisé |
| `get_user_tokens(user_id, tenant_id, include_revoked)` | Liste les tokens actifs (Issue #12) |

> **Note (Issue #12):** `get_user_tokens()` est maintenant fonctionnel et appelle le repository.
>
> **Note (Phase 5):** `revoke_refresh_token()` est idempotent (retourne toujours `True`).
> Si le token est inconnu ou déjà révoqué, un message DEBUG est loggé pour faciliter le debug.
>
> **Note (Phase 5):** `rotate_refresh_token()` marque uniquement l'ancien token comme utilisé.
> Le stockage du nouveau token est fait séparément via `store_refresh_token()` par l'appelant.
>
> **Note (Phase 5):** `TokenRevokedError` est maintenant importé depuis `exceptions.py` (pas de duplication).

### AuditService (`audit.py`) - Phase 2

Logging des événements de sécurité pour compliance.

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `log_action(action, user_id, tenant_id, resource, ...)` | Log une action |
| `get_audit_logs(tenant_id, filters, ...)` | Récupère les logs |
| `get_user_activity(user_id, tenant_id)` | Activité d'un utilisateur |
| `cleanup_old_logs(retention_days)` | Purge les anciens logs |

> **Note (Issue #11):** En cas d'échec de l'audit, `log_action()` log maintenant un message
> **CRITICAL** et re-raise l'exception. L'audit n'échoue plus silencieusement.
>
> **Note (Phase 5):** `export_audit_logs()` docstring ajoute un WARNING que le caller doit valider
> l'accès au tenant_id avant d'appeler cette méthode.

### MFAService (`mfa.py`) - Phase 3

Service d'authentification multi-facteur avec TOTP et codes de récupération.

**Responsabilités:**
- Configuration MFA (génération secret TOTP + QR code)
- Vérification codes TOTP (compatible Google Authenticator, Authy)
- Gestion des codes de récupération (10 codes par défaut)
- Activation/désactivation MFA

**Méthodes:**

| Méthode | Description |
|---------|-------------|
| `setup_mfa(user_id, tenant_id, email)` | Configure MFA, retourne secret + QR code |
| `enable_mfa(user_id, code)` | Active MFA après vérification TOTP |
| `disable_mfa(user_id, code)` | Désactive MFA |
| `verify_totp(user_id, code)` | Vérifie un code TOTP |
| `verify_recovery_code(user_id, code)` | Vérifie et consomme un code de récupération |
| `regenerate_recovery_codes(user_id, totp_code)` | Régénère les codes |
| `get_mfa_status(user_id)` | Statut MFA complet |
| `is_mfa_enabled(user_id)` | Vérifie si MFA est activé (Issue #1) |

> **Note (Issue #1):** `is_mfa_enabled()` est utilisé par `AuthService.login()` pour décider
> si le flow MFA 2 étapes est nécessaire.

**Sécurité renforcée (Phase 3.1):**

| Mesure | Implémentation |
|--------|----------------|
| **Chiffrement secrets TOTP** | AES-256-GCM via `app/core/crypto.py` |
| **Hachage recovery codes** | bcrypt cost=10 (résistant brute-force) |
| **Protection timing attacks** | `bcrypt.checkpw()` constant-time |
| **Rate limiting** | 5 req/min verify, 3 req/min recovery |

**Exemple d'utilisation:**

```python
from app.services.mfa import MFAService

mfa_service = MFAService(
    mfa_secret_repository=mfa_secret_repo,
    mfa_recovery_code_repository=mfa_recovery_repo
)

# 1. Setup MFA (génère secret chiffré)
result = mfa_service.setup_mfa(
    user_id=1,
    tenant_id=1,
    email="user@example.com"
)
# result = {
#     "secret": "JBSWY3DPEHPK3PXP",  # Affiché à l'utilisateur
#     "provisioning_uri": "otpauth://totp/MassaCorp:user@example.com?...",
#     "qr_code_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
# }

# 2. Enable MFA (vérifie le code TOTP)
result = mfa_service.enable_mfa(user_id=1, code="123456")
# result = {
#     "enabled": True,
#     "recovery_codes": ["ABCD-1234", "EFGH-5678", ...]  # 10 codes bcrypt-hachés
# }

# 3. Verify TOTP (secret déchiffré automatiquement)
is_valid = mfa_service.verify_totp(user_id=1, code="654321")
```

**Configuration:**
- `TOTP_WINDOW`: 1 (accepte ±30 secondes)
- `RECOVERY_CODES_COUNT`: 10 codes par utilisateur
- `DEFAULT_ISSUER`: "MassaCorp" (affiché dans les apps TOTP)

## Exceptions (`exceptions.py`)

Exceptions métier typées pour une gestion d'erreur propre.

### Phase 1

| Exception | Code | Description |
|-----------|------|-------------|
| `ServiceException` | - | Base pour toutes les exceptions |
| `EmailAlreadyExistsError` | EMAIL_EXISTS | Email déjà utilisé |
| `UserNotFoundError` | USER_NOT_FOUND | Utilisateur inexistant |
| `TenantNotFoundError` | TENANT_NOT_FOUND | Tenant inexistant |
| `InvalidCredentialsError` | INVALID_CREDENTIALS | Identifiants incorrects |
| `InactiveUserError` | INACTIVE_USER | Compte désactivé |
| `InvalidTokenError` | INVALID_TOKEN | Token JWT invalide |
| `PasswordMismatchError` | PASSWORD_MISMATCH | Mauvais mot de passe actuel |
| `MFARequiredError` | MFA_REQUIRED | MFA requis |
| `MFAInvalidError` | MFA_INVALID | Code MFA invalide |

### Phase 2

| Exception | Code | Description |
|-----------|------|-------------|
| `SessionNotFoundError` | SESSION_NOT_FOUND | Session inexistante |
| `SessionExpiredError` | SESSION_EXPIRED | Session expirée |
| `AccountLockedError` | ACCOUNT_LOCKED | Compte verrouillé (brute-force) |
| `TokenRevokedError` | TOKEN_REVOKED | Token révoqué |
| `TokenReplayDetectedError` | TOKEN_REPLAY | Attaque de replay détectée |
| `MaxSessionsExceededError` | MAX_SESSIONS_EXCEEDED | Trop de sessions |
| `InvalidDateRangeError` | INVALID_DATE_RANGE | Plage de dates invalide |

### Phase 3 (MFA)

| Exception | Code | Description |
|-----------|------|-------------|
| `MFAAlreadyEnabledError` | MFA_ALREADY_ENABLED | MFA déjà activé |
| `MFANotConfiguredError` | MFA_NOT_CONFIGURED | MFA non configuré |
| `InvalidMFACodeError` | INVALID_MFA_CODE | Code TOTP/recovery invalide |

**Exemple de gestion:**

```python
from app.services.exceptions import EmailAlreadyExistsError, AccountLockedError

try:
    user = user_service.create_user(email="test@test.com", ...)
except EmailAlreadyExistsError as e:
    raise HTTPException(status_code=400, detail=e.message)
except AccountLockedError as e:
    raise HTTPException(status_code=423, detail=e.message)
```

## Injection de dépendances

Les services sont injectés via FastAPI Depends (voir `core/dependencies.py`):

```python
from app.core.dependencies import get_auth_service, get_user_service

@router.post("/login")
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return auth_service.login(...)
```

## Bonnes pratiques

### 1. Séparation des responsabilités

```python
# BON: Service utilise Repository
class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def create_user(self, ...):
        # Validation métier
        if self.user_repository.email_exists_in_tenant(email, tenant_id):
            raise EmailAlreadyExistsError(email)
        # Déléguer la persistance au repository
        return self.user_repository.create(data)

# MAUVAIS: Service accède directement à la DB
class UserService:
    def create_user(self, ...):
        db.query(User).filter(...).first()  # Non!
```

### 2. Transactions

```python
# Les services n'appellent pas commit()
# C'est le endpoint qui commit via la dépendance get_db()
def create_user(self, ...):
    user = self.user_repository.create(data)
    # Pas de session.commit() ici!
    return user
```

### 3. Logging silencieux

```python
# Les services de logging ne bloquent pas le flux principal
def _log_audit_event(self, ...):
    if not self.audit_service:
        return
    try:
        self.audit_service.log_action(...)
    except Exception:
        pass  # Silencieux pour ne pas bloquer
```

### 4. Validation en cascade

```python
def create_user(self, ...):
    # 1. Valider le tenant existe
    if self.tenant_repository:
        if not self.tenant_repository.get_by_id(tenant_id):
            raise TenantNotFoundError(tenant_id)

    # 2. Valider l'email n'existe pas
    if self.user_repository.email_exists_in_tenant(email, tenant_id):
        raise EmailAlreadyExistsError(email)

    # 3. Créer l'utilisateur
    return self.user_repository.create(data)
```

## Tests

Les services sont testés unitairement avec mocking des repositories:

```python
from unittest.mock import Mock
from app.services import UserService

def test_create_user():
    # Arrange
    mock_user_repo = Mock()
    mock_user_repo.email_exists_in_tenant.return_value = False
    mock_user_repo.create.return_value = User(id=1, email="test@test.com")

    service = UserService(user_repository=mock_user_repo)

    # Act
    user = service.create_user(email="test@test.com", ...)

    # Assert
    assert user.id == 1
    mock_user_repo.create.assert_called_once()
```
