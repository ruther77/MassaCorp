# Application FastAPI - MassaCorp

Point d'entrée principal de l'API REST sécurisée MassaCorp.

## Structure du dossier

```
app/
├── __init__.py              # Package Python
├── main.py                  # Point d'entrée FastAPI
├── README.md                # Ce fichier
│
├── api/                     # Endpoints REST
│   ├── README.md            # Documentation API
│   └── v1/
│       ├── router.py        # Router principal v1
│       └── endpoints/       # Endpoints par domaine
│           ├── auth.py      # Authentification
│           ├── users.py     # Gestion utilisateurs
│           ├── sessions.py  # Gestion sessions
│           └── mfa.py       # MFA TOTP (Phase 3)
│
├── core/                    # Configuration et utilitaires
│   ├── config.py            # Configuration (env vars)
│   ├── database.py          # Connexion SQLAlchemy
│   ├── security.py          # JWT, hashing, validation
│   ├── crypto.py            # Chiffrement AES-256-GCM (secrets TOTP) - Phase 3
│   └── dependencies.py      # Injection de dépendances FastAPI
│
├── models/                  # Modèles SQLAlchemy
│   ├── base.py              # Base model + mixins
│   ├── tenant.py            # Modèle Tenant
│   ├── user.py              # Modèle User
│   ├── session.py           # Modèle Session (Phase 2)
│   ├── audit.py             # Modèle AuditLog (Phase 2)
│   └── mfa.py               # MFASecret, MFARecoveryCode (Phase 3)
│
├── repositories/            # Couche d'accès aux données
│   ├── base.py              # Repository générique CRUD
│   ├── tenant.py            # Repository Tenant
│   ├── user.py              # Repository User
│   ├── session.py           # Repository Session (Phase 2)
│   ├── login_attempt.py     # Repository LoginAttempt (Phase 2)
│   ├── audit.py             # Repository Audit (Phase 2)
│   ├── refresh_token.py     # Repository RefreshToken (Phase 2)
│   ├── revoked_token.py     # Repository RevokedToken (Phase 2)
│   └── mfa.py               # MFASecretRepository, MFARecoveryCodeRepository (Phase 3)
│
├── services/                # Couche métier (Phase 2)
│   ├── README.md            # Documentation services
│   ├── exceptions.py        # Exceptions métier
│   ├── auth.py              # Service authentification
│   ├── user.py              # Service utilisateurs
│   ├── tenant.py            # Service tenants
│   ├── session.py           # Service sessions
│   ├── token.py             # Service tokens
│   ├── audit.py             # Service audit
│   └── mfa.py               # MFAService - TOTP, recovery codes (Phase 3)
│
├── schemas/                 # Schémas Pydantic
│   ├── base.py              # Schémas de base + helpers
│   ├── auth.py              # Schémas authentification
│   ├── user.py              # Schémas utilisateur/tenant
│   ├── session.py           # Schémas sessions (Phase 2)
│   └── mfa.py               # Schémas MFA (Phase 3)
│
└── scripts/                 # Scripts utilitaires
    ├── README.md            # Documentation scripts
    └── seed.py              # Initialisation données
```

## Architecture en couches

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                 │
│                     (FastAPI Application)                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                         api/v1/                                  │
│                    (Routers/Endpoints)                           │
│              auth.py | users.py | sessions.py                    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                       core/dependencies.py                       │
│                    (Injection de dépendances)                    │
│         get_auth_service | get_current_user | get_db            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                          services/                               │
│                      (Logique métier)                            │
│    AuthService | UserService | SessionService | AuditService    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                        repositories/                             │
│                   (Accès aux données)                            │
│   UserRepository | SessionRepository | RefreshTokenRepository   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                          models/                                 │
│                    (Modèles SQLAlchemy)                          │
│          User | Tenant | Session | AuditLog | ...               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│                           core/                                  │
│             config | database | security                         │
└─────────────────────────────────────────────────────────────────┘
```

## Documentation par module

| Module | Documentation | Description |
|--------|---------------|-------------|
| `api/` | [api/README.md](api/README.md) | Endpoints REST, exemples, codes HTTP |
| `services/` | [services/README.md](services/README.md) | Logique métier, exceptions |
| `scripts/` | [scripts/README.md](scripts/README.md) | Scripts d'administration |

## Composants principaux

### main.py

Point d'entrée de l'application FastAPI.

**Endpoints de base:**

| Route | Méthode | Description |
|-------|---------|-------------|
| `/` | GET | Page d'accueil |
| `/health` | GET | Health check |
| `/api/v1/info` | GET | Infos API + client IP |
| `/api/v1/auth/*` | - | Authentification |
| `/api/v1/users/*` | - | Gestion utilisateurs |
| `/api/v1/sessions/*` | - | Gestion sessions |
| `/api/v1/mfa/*` | - | MFA TOTP (Phase 3) |

### core/dependencies.py

Injection de dépendances FastAPI centralisée.

**Dépendances disponibles:**

```python
from app.core.dependencies import (
    # Database
    get_db,

    # Repositories
    get_user_repository,
    get_tenant_repository,
    get_session_repository,
    get_audit_repository,

    # Services
    get_auth_service,
    get_user_service,
    get_session_service,
    get_audit_service,
    get_token_service,

    # Authentication
    get_current_user,           # Requiert auth, lève 401
    get_current_superuser,      # Requiert admin, lève 403
    get_optional_current_user,  # Retourne None si pas auth
    get_current_tenant_id,      # Extrait tenant_id du user
)
```

**Exemple d'utilisation:**

```python
from fastapi import Depends
from app.core.dependencies import get_current_user, get_auth_service
from app.models import User
from app.services import AuthService

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    auth_service.logout(user_id=current_user.id, ...)
```

### core/security.py

Module de sécurité pour authentification.

**Fonctions principales:**

| Fonction | Description |
|----------|-------------|
| `hash_password(password)` | Hash bcrypt (cost 12) |
| `verify_password(plain, hashed)` | Vérification bcrypt |
| `validate_password_strength(password)` | Validation règles |
| `create_access_token(subject, tenant_id, ...)` | Génère JWT access |
| `create_refresh_token(subject, tenant_id)` | Génère JWT refresh |
| `decode_token(token)` | Décode et valide JWT |
| `get_token_payload(token)` | Extrait payload sans validation |
| `hash_token(token)` | Hash SHA-256 pour tokens révoqués |

**Règles mots de passe:**
- 8-128 caractères
- 1 majuscule, 1 minuscule, 1 chiffre, 1 spécial

### core/crypto.py (Phase 3)

Module de cryptographie pour données sensibles.

**Fonctions principales:**

| Fonction | Description |
|----------|-------------|
| `encrypt_totp_secret(secret)` | Chiffre un secret TOTP avec AES-256-GCM |
| `decrypt_totp_secret(encrypted)` | Déchiffre un secret TOTP |
| `is_encrypted_secret(secret)` | Détecte si un secret est chiffré |

**Algorithme AES-256-GCM:**
- IV de 12 bytes (généré aléatoirement)
- Tag d'authentification de 16 bytes
- Clé dérivée via SHA-256 depuis `ENCRYPTION_KEY`
- Format de sortie: `base64(IV + ciphertext + tag)`

**Exemple:**
```python
from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret

# Chiffrer avant stockage
encrypted = encrypt_totp_secret("JBSWY3DPEHPK3PXP")
# "aGVsbG8gd29ybGQhIQ..." (base64, ~80 chars)

# Déchiffrer pour vérification TOTP
secret = decrypt_totp_secret(encrypted)
# "JBSWY3DPEHPK3PXP"
```

### services/

Couche métier avec logique applicative.

| Service | Responsabilités |
|---------|-----------------|
| `AuthService` | Login, logout, tokens, brute-force |
| `UserService` | CRUD utilisateurs, changement MDP |
| `TenantService` | CRUD tenants |
| `SessionService` | Sessions, login attempts, lockout |
| `TokenService` | Refresh tokens, révocation, replay |
| `AuditService` | Logging des actions |
| `MFAService` | TOTP (pyotp), recovery codes, setup/enable/disable |

Voir [services/README.md](services/README.md) pour la documentation complète.

### models/

Modèles SQLAlchemy Phase 1 + Phase 2 + Phase 3.

| Modèle | Table | Description |
|--------|-------|-------------|
| `Tenant` | tenants | Organisations |
| `User` | users | Utilisateurs |
| `Session` | sessions | Sessions utilisateur |
| `LoginAttempt` | login_attempts | Tentatives de connexion |
| `AuditLog` | audit_log | Journal d'audit |
| `RefreshToken` | refresh_tokens | Tokens de refresh |
| `RevokedToken` | revoked_tokens | Tokens révoqués |
| `MFASecret` | mfa_secrets | Secrets TOTP (Phase 3) |
| `MFARecoveryCode` | mfa_recovery_codes | Codes de récupération (Phase 3) |

### repositories/

Pattern Repository avec CRUD générique.

**Méthodes de base (BaseRepository):**

```python
repo.get_by_id(id)           # Récupérer par ID
repo.get_all(skip, limit)    # Liste paginée
repo.create(data)            # Créer
repo.update(id, data)        # Mettre à jour
repo.delete(id)              # Supprimer
repo.count()                 # Compter
repo.exists(id)              # Vérifier existence
```

**Repositories spécialisés:**

| Repository | Méthodes spécifiques |
|------------|---------------------|
| `UserRepository` | `get_by_email_and_tenant()`, `update_password()` |
| `TenantRepository` | `get_by_slug()` |
| `SessionRepository` | `get_active_sessions()`, `terminate_session()` |
| `LoginAttemptRepository` | `count_recent_failures()` |
| `MFASecretRepository` | `get_by_user_id()`, `enable_mfa()`, `disable_mfa()` |
| `MFARecoveryCodeRepository` | `create_codes_for_user()`, `mark_code_as_used()` |

### schemas/

Schémas Pydantic pour validation.

**Helpers de réponse:**

```python
from app.schemas import success_response, error_response, paginated_response

# Réponse de succès
return success_response(message="OK", data={"id": 1})

# Réponse paginée
return paginated_response(items=users, total=100, skip=0, limit=20)
```

## Flux d'une requête authentifiée

```
1. Client envoie requête avec Bearer token
2. Middleware CORS vérifie l'origine
3. Router dirige vers l'endpoint
4. get_current_user() décode le token JWT
5. Endpoint appelle le Service
6. Service valide et exécute la logique métier
7. Service appelle le Repository
8. Repository exécute les requêtes SQL
9. Réponse remonte: Model → Schema → JSON
10. Commit automatique via get_db()
11. Client reçoit la réponse
```

## Ajouter une nouvelle fonctionnalité

### 1. Créer le modèle

```python
# models/product.py
from app.models.base import Base, TimestampMixin

class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger, ForeignKey("tenants.id"))
    name = mapped_column(Text, nullable=False)
```

### 2. Créer le repository

```python
# repositories/product.py
from app.repositories.base import BaseRepository
from app.models.product import Product

class ProductRepository(BaseRepository[Product]):
    model = Product

    def get_by_tenant(self, tenant_id: int):
        return self.session.query(Product).filter(
            Product.tenant_id == tenant_id
        ).all()
```

### 3. Créer le service

```python
# services/product.py
from app.repositories.product import ProductRepository

class ProductService:
    def __init__(self, product_repository: ProductRepository):
        self.product_repository = product_repository

    def list_products(self, tenant_id: int):
        return self.product_repository.get_by_tenant(tenant_id)
```

### 4. Créer les schémas

```python
# schemas/product.py
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str

class ProductRead(BaseModel):
    id: int
    name: str
    tenant_id: int

    class Config:
        from_attributes = True
```

### 5. Ajouter la dépendance

```python
# core/dependencies.py
def get_product_service(
    product_repo = Depends(get_product_repository)
) -> ProductService:
    return ProductService(product_repository=product_repo)
```

### 6. Créer l'endpoint

```python
# api/v1/endpoints/products.py
router = APIRouter(prefix="/products", tags=["Products"])

@router.get("")
def list_products(
    current_user: User = Depends(get_current_user),
    product_service = Depends(get_product_service)
):
    return product_service.list_products(current_user.tenant_id)
```

### 7. Enregistrer le router

```python
# api/v1/router.py
from app.api.v1.endpoints import products
api_router.include_router(products.router)
```

### 8. Créer la migration

```bash
alembic revision --autogenerate -m "add_products_table"
alembic upgrade head
```
