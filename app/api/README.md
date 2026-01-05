# API REST - MassaCorp

Endpoints REST de l'API MassaCorp organisés par version et domaine fonctionnel.

## Structure

```
api/
├── README.md            # Ce fichier
├── __init__.py
└── v1/                  # Version 1 de l'API
    ├── __init__.py
    ├── router.py        # Router principal (combine les endpoints)
    └── endpoints/       # Endpoints par domaine
        ├── __init__.py
        ├── auth.py      # Authentification
        ├── users.py     # Gestion utilisateurs
        ├── sessions.py  # Gestion sessions
        └── mfa.py       # MFA TOTP (Phase 3)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          main.py                                 │
│                     app.include_router()                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       api/v1/router.py                           │
│                         api_router                               │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│   │  auth   │ │  users  │ │sessions │ │   mfa   │              │
│   │ /auth/* │ │ /users/*│ │/sess/*  │ │ /mfa/*  │              │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Endpoints disponibles

### Authentification (`/api/v1/auth`)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/login` | Non | Connexion utilisateur (étape 1) |
| POST | `/login/mfa` | Non | Vérification TOTP (étape 2, Issue #1) |
| POST | `/logout` | Oui | Déconnexion |
| POST | `/refresh` | Non | Rafraîchir les tokens (+ validation session) |
| GET | `/me` | Oui | Statut d'authentification (mfa_enabled réel) |
| POST | `/change-password` | Oui | Changer le mot de passe |
| POST | `/verify-token` | Oui | Vérifier un token |

> **Headers requis (Issue #8):** Toutes les requêtes doivent inclure `X-Tenant-ID: <id>`

### Utilisateurs (`/api/v1/users`)

| Méthode | Endpoint | Auth | Admin | Description |
|---------|----------|------|-------|-------------|
| GET | `/me` | Oui | Non | Mon profil |
| PUT | `/me` | Oui | Non | Modifier mon profil |
| GET | `/` | Oui | Oui | Lister les utilisateurs |
| POST | `/` | Oui | Oui | Créer un utilisateur |
| GET | `/{id}` | Oui | Oui | Détails utilisateur |
| PUT | `/{id}` | Oui | Oui | Modifier utilisateur |
| DELETE | `/{id}` | Oui | Oui | Supprimer utilisateur |
| POST | `/{id}/verify` | Oui | Oui | Vérifier un utilisateur |
| POST | `/{id}/activate` | Oui | Oui | Activer un utilisateur |
| POST | `/{id}/deactivate` | Oui | Oui | Désactiver un utilisateur |

> **Note (Phase 5):** Les endpoints `DELETE /{id}`, `POST /{id}/activate` et `POST /{id}/deactivate`
> génèrent maintenant des logs d'audit automatiques via `audit_service.log_action()`.

### Sessions (`/api/v1/sessions`)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| GET | `/` | Oui | Lister mes sessions |
| GET | `/{id}` | Oui | Détails d'une session |
| DELETE | `/{id}` | Oui | Terminer une session |
| DELETE | `/` | Oui | Terminer toutes les sessions |

### MFA (`/api/v1/mfa`) - Phase 3

| Méthode | Endpoint | Auth | Rate Limit | Description |
|---------|----------|------|------------|-------------|
| GET | `/status` | Oui | 60/min | Statut MFA de l'utilisateur |
| POST | `/setup` | Oui | 5/min | Configure MFA (génère secret + QR) |
| POST | `/enable` | Oui | 5/min | Active MFA après vérification TOTP |
| POST | `/verify` | Oui | **5/min** | Vérifie un code TOTP |
| POST | `/disable` | Oui | 5/min | Désactive MFA |
| POST | `/recovery/verify` | Oui | **3/min** | Utilise un code de récupération |
| POST | `/recovery/regenerate` | Oui | 3/min | Régénère les codes de récupération |

**Sécurité renforcée:**
- Rate limiting strict (5 req/min verify, 3 req/min recovery)
- Secrets TOTP chiffrés en AES-256-GCM
- Recovery codes hachés avec bcrypt (cost=10)
- Protection timing attacks (bcrypt.checkpw)

## Documentation détaillée

### POST /auth/login

Authentifie un utilisateur. Si MFA est activé, retourne un token de session MFA.

**Headers requis:**
```
X-Tenant-ID: 1
```

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ss123!"
}
```

**Response sans MFA (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "session_id": "uuid-session-id"
}
```

**Response avec MFA activé (200) - Issue #1:**
```json
{
  "mfa_required": true,
  "mfa_session_token": "eyJhbGciOiJIUzI1NiIs...",
  "message": "MFA verification required"
}
```

> Appeler ensuite `POST /auth/login/mfa` avec le `mfa_session_token`.

**Erreurs:**
- `400 Bad Request`: Header X-Tenant-ID manquant
- `401 Unauthorized`: Identifiants invalides
- `423 Locked`: Compte verrouillé (brute-force)

### POST /auth/login/mfa (Issue #1)

Complète l'authentification MFA après un login réussi.

**Headers requis:**
```
X-Tenant-ID: 1
```

> **Note (Phase 4.4):** Le header X-Tenant-ID est maintenant requis pour cohérence avec /login.

**Request:**
```json
{
  "mfa_session_token": "eyJhbGciOiJIUzI1NiIs...",
  "totp_code": "123456"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900,
  "session_id": "uuid-session-id"
}
```

**Erreurs:**
- `400 Bad Request`: Header X-Tenant-ID manquant
- `401 Unauthorized`: Token MFA expiré ou invalide
- `401 Unauthorized`: Code TOTP invalide

### POST /auth/logout

Déconnecte l'utilisateur et révoque le token.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request (optionnel):**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "session_id": "uuid-session-id",
  "all_sessions": false
}
```

> **Note:** Tous les champs sont optionnels. Le body peut être vide `{}` ou omis.
> - `refresh_token`: Révoque un token de refresh spécifique
> - `session_id`: Termine une session spécifique (UUID)
> - `all_sessions`: Termine toutes les sessions de l'utilisateur

**Response (200):**
```json
{
  "success": true,
  "message": "Deconnexion reussie"
}
```

### POST /auth/refresh

Rafraîchit les tokens avec rotation sécurisée.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Erreurs:**
- `401 Unauthorized`: Token invalide/expiré
- `401 Unauthorized`: Token compromis (replay détecté)

### GET /users/me

Retourne le profil de l'utilisateur connecté.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",
  "phone": "+33612345678",
  "is_verified": true,
  "has_mfa": false,
  "tenant_id": 1,
  "tenant_name": "Epicerie",
  "created_at": "2024-01-01T12:00:00Z",
  "last_login_at": "2024-01-15T10:30:00Z"
}
```

### POST /users (Admin)

Crée un nouvel utilisateur.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "email": "new@example.com",
  "password": "SecureP@ss123!",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone": "+33698765432",
  "is_active": true,
  "is_verified": false,
  "is_superuser": false
}
```

**Response (201):**
```json
{
  "id": 2,
  "email": "new@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "tenant_id": 1,
  "is_active": true,
  "is_verified": false,
  "created_at": "2024-01-15T12:00:00Z"
}
```

**Erreurs:**
- `403 Forbidden`: Non superuser
- `409 Conflict`: Email déjà utilisé

### GET /sessions

Liste les sessions actives de l'utilisateur.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query params:**
- `include_inactive`: bool (défaut: false)

**Response (200):**
```json
{
  "sessions": [
    {
      "id": "uuid-session-1",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "device_type": "desktop",
      "browser": "Chrome",
      "os": "Windows",
      "is_active": true,
      "is_current": true,
      "last_seen_at": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-15T08:00:00Z"
    }
  ],
  "total": 1,
  "active_count": 1
}
```

### GET /sessions/{id}

Récupère les détails d'une session spécifique.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "id": "uuid-session-1",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "device_type": "desktop",
  "browser": "Chrome",
  "os": "Windows",
  "is_active": true,
  "is_current": true,
  "last_seen_at": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T08:00:00Z"
}
```

> **Note (Phase 5):** `is_current` indique si la session consultée est celle utilisée
> pour la requête actuelle (cohérent avec `GET /sessions`).

**Erreurs:**
- `404 Not Found`: Session inexistante ou non possédée (réponse identique pour IDOR protection)

## Authentification

### Bearer Token

Toutes les routes protégées requièrent un header Authorization:

```
Authorization: Bearer <access_token>
```

### Tokens JWT

| Type | Durée | Contenu |
|------|-------|---------|
| Access Token | 15 min | sub, tenant_id, email, type, exp |
| Refresh Token | 7 jours | sub, tenant_id, jti, type, exp |

### Refresh automatique

Quand l'access token expire:
1. Appeler `POST /auth/refresh` avec le refresh token
2. Recevoir une nouvelle paire de tokens
3. L'ancien refresh token est invalidé (rotation)

## Codes HTTP

| Code | Signification |
|------|---------------|
| 200 | Succès |
| 201 | Créé |
| 204 | Supprimé (pas de contenu) |
| 400 | Requête invalide |
| 401 | Non authentifié |
| 403 | Non autorisé (permissions) |
| 404 | Ressource non trouvée |
| 409 | Conflit (email existe) |
| 422 | Validation échouée |
| 423 | Verrouillé (brute-force) |
| 500 | Erreur serveur |

## Format des réponses

### Succès standard

```json
{
  "success": true,
  "message": "Operation reussie",
  "data": { ... }
}
```

### Erreur

```json
{
  "detail": "Description de l'erreur"
}
```

### Liste paginée

```json
{
  "items": [ ... ],
  "total": 100,
  "skip": 0,
  "limit": 20
}
```

## Sécurité

### Protection brute-force

- Maximum 5 tentatives de login
- Verrouillage de 30 minutes après 5 échecs
- Compteur réinitialisé après succès

### Rate limiting MFA (Phase 3.1)

| Endpoint | Limite | Justification |
|----------|--------|---------------|
| `/mfa/verify` | 5/min | TOTP 6 digits = 10^6 combinaisons |
| `/mfa/enable` | 5/min | Protection configuration |
| `/mfa/recovery/verify` | 3/min | Codes de récupération précieux |
| `/mfa/recovery/regenerate` | 3/min | Opération sensible |

**Calcul brute-force TOTP:**
- 10^6 combinaisons / 5 req/min = 200000 min = ~139 jours

### Stockage sécurisé MFA

| Donnée | Méthode | Détails |
|--------|---------|---------|
| Secret TOTP | AES-256-GCM | Chiffré avant stockage, IV unique |
| Recovery codes | bcrypt (cost=10) | ~100ms par vérification |

### Rotation des tokens

- Le refresh token est à usage unique
- Détection des attaques de replay
- Révocation automatique en cas de compromission

### Isolation multi-tenant

- Chaque utilisateur ne voit que les données de son tenant
- `tenant_id` extrait du token JWT
- Vérification à chaque requête

## Ajouter un nouvel endpoint

1. Créer le fichier dans `api/v1/endpoints/`
2. Définir le router avec préfixe et tags
3. Implémenter les endpoints
4. Enregistrer dans `api/v1/router.py`

```python
# api/v1/endpoints/products.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])

@router.get("")
def list_products(current_user = Depends(get_current_user)):
    ...
```

```python
# api/v1/router.py
from app.api.v1.endpoints import products
api_router.include_router(products.router)
```

## Documentation OpenAPI

En mode développement, la documentation est accessible:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
