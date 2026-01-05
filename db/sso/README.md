# SSO Module (Single Sign-On)

## Vue d'ensemble
Module de federation d'identite supportant OIDC (OpenID Connect) et SAML.
Permet aux utilisateurs de se connecter via des providers externes (Google, Microsoft, Okta, etc.).

## Tables

### `identity_providers`
Configuration des providers SSO par tenant.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `tenant_id` | BIGINT | Tenant proprietaire |
| `provider_type` | TEXT | `'oidc'` ou `'saml'` |
| `provider_name` | TEXT | Nom (google, microsoft, okta, custom) |
| `enabled` | BOOLEAN | Provider actif |
| **OIDC** | | |
| `client_id` | TEXT | Client ID OIDC |
| `client_secret` | TEXT | Client Secret (chiffre) |
| `issuer_url` | TEXT | URL de l'issuer |
| **SAML** | | |
| `saml_entity_id` | TEXT | Entity ID SAML |
| `saml_metadata` | XML | Metadata XML du provider |
| `created_at` | TIMESTAMPTZ | Date de creation |
| `updated_at` | TIMESTAMPTZ | Derniere modification |

**Contrainte:** `UNIQUE (tenant_id, provider_name)`

### `user_identities`
Lien entre utilisateurs locaux et identites externes.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `user_id` | BIGINT | Utilisateur local |
| `tenant_id` | BIGINT | Tenant |
| `provider_name` | TEXT | Provider utilise |
| `external_subject` | TEXT | Subject ID externe (sub OIDC / NameID SAML) |
| `email` | TEXT | Email du provider |
| `created_at` | TIMESTAMPTZ | Date de liaison |

**Contrainte:** `UNIQUE (tenant_id, provider_name, external_subject)`

### `sso_sessions`
Sessions SSO pour tracabilite.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant session SSO |
| `user_id` | BIGINT | Utilisateur |
| `tenant_id` | BIGINT | Tenant |
| `provider_name` | TEXT | Provider utilise |
| `external_session_id` | TEXT | Session ID du provider |
| `created_at` | TIMESTAMPTZ | Debut de session |
| `revoked_at` | TIMESTAMPTZ | Revocation (NULL = active) |

## Index

```sql
-- Providers par tenant
identity_providers_tenant_idx ON identity_providers (tenant_id)
identity_providers_enabled_idx ON identity_providers (enabled)

-- Identites par utilisateur
user_identities_user_idx ON user_identities (user_id)
user_identities_tenant_idx ON user_identities (tenant_id)

-- Sessions SSO
sso_sessions_user_idx ON sso_sessions (user_id)
sso_sessions_tenant_idx ON sso_sessions (tenant_id)
sso_sessions_active_idx ON sso_sessions (id) WHERE revoked_at IS NULL
```

## Flux OIDC

### 1. Initiation
```
User -> GET /auth/sso/google
        |
        v
   Recuperer config depuis identity_providers
        |
        v
   Generer state + nonce (anti-CSRF)
        |
        v
   Redirect -> https://accounts.google.com/o/oauth2/auth
               ?client_id=...
               &redirect_uri=...
               &scope=openid email profile
               &state=...
               &nonce=...
```

### 2. Callback
```
Google -> GET /auth/sso/callback?code=...&state=...
          |
          v
   Valider state (anti-CSRF)
          |
          v
   Echanger code contre tokens (POST /token)
          |
          v
   Valider id_token (signature, iss, aud, exp, nonce)
          |
          v
   Extraire subject (sub) et email
          |
          v
   Chercher dans user_identities
          |
          +-- Existe --> Recuperer user_id --> Login
          |
          +-- N'existe pas --> Creer user OU lier a existant par email
          |
          v
   Creer sso_session
          |
          v
   Creer session locale (auth/sessions)
```

## Flux SAML

### 1. SP-Initiated
```
User -> GET /auth/sso/okta
        |
        v
   Generer AuthnRequest SAML
        |
        v
   Redirect -> IdP avec SAMLRequest
```

### 2. Assertion
```
IdP -> POST /auth/sso/saml/acs (Assertion Consumer Service)
       |
       v
   Valider signature XML
       |
       v
   Extraire NameID + attributs
       |
       v
   Meme logique que OIDC (user_identities)
```

## Configuration providers

### Google (OIDC)
```sql
INSERT INTO identity_providers (
    tenant_id, provider_type, provider_name, enabled,
    client_id, client_secret, issuer_url
) VALUES (
    1, 'oidc', 'google', true,
    'xxx.apps.googleusercontent.com',
    encrypt('client_secret_here'),
    'https://accounts.google.com'
);
```

### Microsoft Azure AD (OIDC)
```sql
INSERT INTO identity_providers (
    tenant_id, provider_type, provider_name, enabled,
    client_id, client_secret, issuer_url
) VALUES (
    1, 'oidc', 'microsoft', true,
    'azure-client-id',
    encrypt('azure-secret'),
    'https://login.microsoftonline.com/{tenant}/v2.0'
);
```

### Okta (SAML)
```sql
INSERT INTO identity_providers (
    tenant_id, provider_type, provider_name, enabled,
    saml_entity_id, saml_metadata
) VALUES (
    1, 'saml', 'okta', true,
    'http://www.okta.com/exk...',
    '<md:EntityDescriptor>...</md:EntityDescriptor>'
);
```

## Requetes utiles

### Providers actifs d'un tenant
```sql
SELECT provider_name, provider_type, enabled
FROM identity_providers
WHERE tenant_id = :tenant_id AND enabled = true;
```

### Utilisateur avec identites liees
```sql
SELECT u.*, array_agg(ui.provider_name) as linked_providers
FROM users u
LEFT JOIN user_identities ui ON ui.user_id = u.id
WHERE u.id = :user_id
GROUP BY u.id;
```

### Sessions SSO actives
```sql
SELECT ss.*, ip.provider_name
FROM sso_sessions ss
JOIN identity_providers ip ON ip.provider_name = ss.provider_name
WHERE ss.user_id = :user_id AND ss.revoked_at IS NULL;
```

## Securite

### Stockage des secrets
- `client_secret` doit etre chiffre (AES-256-GCM)
- Utiliser un KMS pour la cle de chiffrement

### Validations OIDC obligatoires
1. Signature du id_token (RS256/ES256)
2. `iss` == issuer configure
3. `aud` == client_id
4. `exp` > NOW()
5. `nonce` == nonce envoye

### Validations SAML obligatoires
1. Signature XML valide
2. Certificat du IdP valide
3. `Issuer` == EntityID configure
4. `Audience` == notre SP EntityID
5. `NotBefore` < NOW() < `NotOnOrAfter`

## Relations avec autres modules

- **auth/** : Sessions SSO creent des sessions locales
- **audit/** : Login SSO logue dans `audit_log`
- **mfa/** : MFA peut etre requis apres SSO (step-up auth)

## JIT Provisioning (Just-In-Time)

Creer automatiquement les utilisateurs lors du premier login SSO:

```python
async def jit_provision(tenant_id: int, provider: str, claims: dict):
    # Chercher par external_subject
    identity = await get_identity(tenant_id, provider, claims['sub'])

    if identity:
        return identity.user_id

    # Chercher par email
    user = await get_user_by_email(tenant_id, claims['email'])

    if not user:
        # Creer l'utilisateur
        user = await create_user(
            tenant_id=tenant_id,
            email=claims['email'],
            name=claims.get('name'),
            email_verified=claims.get('email_verified', False)
        )

    # Lier l'identite
    await create_identity(
        user_id=user.id,
        tenant_id=tenant_id,
        provider_name=provider,
        external_subject=claims['sub'],
        email=claims['email']
    )

    return user.id
```
