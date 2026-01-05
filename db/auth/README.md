# Auth Module

## Vue d'ensemble
Module d'authentification gerant les sessions utilisateur et les tokens JWT.
Implemente un systeme de refresh tokens avec rotation automatique et detection de replay.

## Tables

### `sessions`
Sessions utilisateur actives.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique de session |
| `user_id` | BIGINT | Utilisateur proprietaire |
| `tenant_id` | BIGINT | Tenant (multi-tenant) |
| `created_at` | TIMESTAMPTZ | Debut de session |
| `last_seen_at` | TIMESTAMPTZ | Derniere activite |
| `ip` | TEXT | IP de connexion |
| `user_agent` | TEXT | Navigateur/client |
| `revoked_at` | TIMESTAMPTZ | Date de revocation (NULL = active) |

### `refresh_tokens`
Tokens de rafraichissement lies aux sessions.

| Colonne | Type | Description |
|---------|------|-------------|
| `jti` | TEXT (PK) | JWT ID unique |
| `session_id` | UUID | Session parente |
| `token_hash` | TEXT | Hash du token |
| `expires_at` | TIMESTAMPTZ | Expiration |
| `created_at` | TIMESTAMPTZ | Creation |
| `used_at` | TIMESTAMPTZ | Utilisation (rotation) |
| `replaced_by_jti` | TEXT | Nouveau token apres rotation |

### `revoked_tokens`
Blacklist des tokens revoques (logout, compromission).

| Colonne | Type | Description |
|---------|------|-------------|
| `jti` | TEXT (PK) | JWT ID revoque |
| `expires_at` | TIMESTAMPTZ | Expiration originale |
| `revoked_at` | TIMESTAMPTZ | Date de revocation |

## Index de performance

```sql
-- Sessions
sessions_user_id_idx ON sessions (user_id)
sessions_tenant_id_idx ON sessions (tenant_id)
sessions_revoked_at_idx ON sessions (revoked_at)
sessions_active_idx ON sessions (id) WHERE revoked_at IS NULL
sessions_tenant_active_idx ON sessions (tenant_id, user_id) WHERE revoked_at IS NULL

-- Refresh tokens
refresh_tokens_session_id_idx ON refresh_tokens (session_id)
refresh_tokens_expires_at_idx ON refresh_tokens (expires_at)
refresh_tokens_used_at_idx ON refresh_tokens (used_at)
refresh_tokens_used_not_null_idx ON refresh_tokens (jti) WHERE used_at IS NOT NULL
refresh_tokens_active_session_idx ON refresh_tokens (session_id) WHERE used_at IS NULL AND expires_at > NOW()

-- Revoked tokens
revoked_tokens_expires_at_idx ON revoked_tokens (expires_at)
revoked_tokens_active_idx ON revoked_tokens (jti) WHERE expires_at > NOW()
```

## Flux d'authentification

### Headers requis

| Header | Obligatoire | Description |
|--------|-------------|-------------|
| `X-Tenant-ID` | **Oui** | ID du tenant (depuis v2.0) |
| `Authorization` | Selon endpoint | Bearer token pour routes protégées |

> **Note (Issue #8):** Le header `X-Tenant-ID` est désormais obligatoire.
> Une requête sans ce header retournera `400 Bad Request`.

### 1. Login (sans MFA)
```
Client -> POST /auth/login {email, password}
         + Header: X-Tenant-ID: 1
         |
         v
   Verifier credentials
         |
         v
   Verifier MFA actif? -> Non
         |
         v
   Creer session dans `sessions`
         |
         v
   Generer access_token (JWT, 15min) + refresh_token (7 jours)
         |
         v
   Stocker refresh_token hash dans `refresh_tokens`
         |
         v
   Retourner {access_token, refresh_token}
```

### 1b. Login avec MFA (2 étapes - Issue #1)
```
=== Étape 1: Credentials ===

Client -> POST /auth/login {email, password}
         + Header: X-Tenant-ID: 1
         |
         v
   Verifier credentials
         |
         v
   Verifier MFA actif? -> Oui
         |
         v
   Generer mfa_session_token (JWT, 5min, type="mfa_session")
         |
         v
   Retourner {mfa_required: true, mfa_session_token: "..."}

=== Étape 2: Vérification TOTP ===

Client -> POST /auth/login/mfa {mfa_session_token, totp_code}
         |
         v
   Valider mfa_session_token (type, expiration)
         |
         v
   Verifier code TOTP avec secret dechiffre
         |
         v
   Creer session dans `sessions`
         |
         v
   Generer access_token + refresh_token
         |
         v
   Retourner {access_token, refresh_token}
```

**Token MFA Session:**
- Durée de vie: 5 minutes (non configurable)
- Type JWT: `mfa_session`
- Ne donne **pas** accès à l'API (contrairement à access_token)
- Usage unique implicite (nouvelle tentative = nouveau token)

### 2. Refresh (Rotation automatique avec validation session - Issue #5)
```
Client -> POST /auth/refresh {refresh_token}
         |
         v
   Hasher et chercher dans `refresh_tokens`
         |
         v
   Verifier: used_at IS NULL ET expires_at > NOW()
         |
         v
   === Validation session (Issue #5) ===
   Recuperer session_id du token
         |
         v
   Verifier session active (revoked_at IS NULL)
         |
         v
   Si session revoquee -> Retourner 401, log audit
         |
         v
   === Fin validation session ===
         |
         v
   Marquer ancien token comme utilise (used_at = NOW())
         |
         v
   Creer nouveau refresh_token, lier via replaced_by_jti
         |
         v
   Retourner {new_access_token, new_refresh_token}
```

> **Note (Issue #5):** Le refresh vérifie maintenant que la session
> associée au token est toujours active. Un token valide mais avec
> session révoquée sera rejeté.

### 3. Detection de replay
Si un refresh_token deja utilise est presente:
1. C'est une tentative de replay (token vole)
2. Revoquer TOUTE la session
3. Forcer re-authentification

### 4. Logout
```sql
-- Revoquer la session
UPDATE sessions SET revoked_at = NOW() WHERE id = :session_id;

-- Blacklister l'access_token actuel
INSERT INTO revoked_tokens (jti, expires_at) VALUES (:jti, :exp);
```

## Securite

### Durees de vie recommandees
- **Access token** : 15 minutes (stateless, pas en DB)
- **Refresh token** : 7 jours (avec rotation)
- **Session** : 30 jours d'inactivite max

### Verifications a chaque requete
1. Signature JWT valide
2. `exp` non depasse
3. `jti` pas dans `revoked_tokens`
4. Session associee non revoquee

## Relations avec autres modules

- **audit/** : Tous les evenements auth sont logues
- **security/** : Correle avec `login_attempts` pour anti-bruteforce
- **mfa/** : Integration MFA dans le flow login
- **sso/** : Sessions SSO paralleles possibles

## Requetes utiles

### Sessions actives d'un utilisateur
```sql
SELECT * FROM sessions
WHERE user_id = :user_id AND revoked_at IS NULL
ORDER BY last_seen_at DESC;
```

### Deconnecter toutes les sessions sauf l'actuelle
```sql
UPDATE sessions
SET revoked_at = NOW()
WHERE user_id = :user_id
  AND id != :current_session_id
  AND revoked_at IS NULL;
```
