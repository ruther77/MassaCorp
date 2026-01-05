# API Keys Module

## Vue d'ensemble
Module de gestion des cles API pour l'authentification machine-to-machine (M2M).
Permet aux services externes (n8n, integrations tierces) d'acceder aux ressources de facon securisee.

## Tables

### `api_keys`
Table principale stockant les cles API.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `tenant_id` | BIGINT | Tenant proprietaire (multi-tenant) |
| `name` | TEXT | Nom lisible (ex: "n8n-prod", "zapier-integration") |
| `key_hash` | TEXT | Hash SHA-256 de la cle (jamais stockee en clair) |
| `scopes` | TEXT[] | Permissions accordees (ex: `{'read:inventory','write:orders'}`) |
| `expires_at` | TIMESTAMPTZ | Date d'expiration (NULL = jamais) |
| `revoked_at` | TIMESTAMPTZ | Date de revocation (NULL = active) |
| `created_at` | TIMESTAMPTZ | Date de creation |
| `last_used_at` | TIMESTAMPTZ | Derniere utilisation |

**Contraintes:**
- `UNIQUE (tenant_id, name)` - Nom unique par tenant

### `api_key_usage`
Table d'audit et rate-limiting pour tracer l'utilisation des cles.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `api_key_id` | BIGINT | Reference vers `api_keys.id` |
| `tenant_id` | BIGINT | Tenant pour partitionnement |
| `ip` | TEXT | Adresse IP de la requete |
| `endpoint` | TEXT | Endpoint appele (ex: `/api/v1/orders`) |
| `method` | TEXT | Methode HTTP (GET, POST, etc.) |
| `used_at` | TIMESTAMPTZ | Timestamp de l'appel |

## Index de performance

```sql
-- Lookup rapide par hash (authentification)
api_keys_key_hash_idx ON api_keys (key_hash)

-- Cles actives par tenant (listing)
api_keys_active_tenant_idx ON api_keys (tenant_id) WHERE revoked_at IS NULL

-- Detection des cles expirees (cleanup)
api_keys_expires_at_idx ON api_keys (expires_at)

-- Monitoring d'activite
api_keys_last_used_at_idx ON api_keys (last_used_at)

-- Usage par cle (rate-limiting)
api_key_usage_key_idx ON api_key_usage (api_key_id)
api_key_usage_tenant_idx ON api_key_usage (tenant_id)
api_key_usage_used_at_idx ON api_key_usage (used_at)
```

## Flux de securite

### Creation d'une cle
1. Generer une cle aleatoire (256 bits minimum)
2. Hasher avec SHA-256/Argon2
3. Stocker uniquement le hash
4. Retourner la cle en clair UNE SEULE FOIS

### Authentification
1. Recevoir la cle dans le header `Authorization: Bearer <key>`
2. Hasher la cle recue
3. Lookup dans `api_keys` par `key_hash`
4. Verifier: `revoked_at IS NULL` ET (`expires_at IS NULL` OU `expires_at > NOW()`)
5. Verifier les scopes vs l'action demandee
6. Logger dans `api_key_usage`

### Revocation
```sql
UPDATE api_keys SET revoked_at = NOW() WHERE id = :api_key_id;
```

## Relations avec autres modules

- **rbac/** : `api_key_roles` permet d'assigner des roles aux cles API
- **audit/** : Les actions sont tracees dans `audit_log`
- **maintenance/** : Cleanup automatique des cles expirees

## Bonnes pratiques

1. **Rotation reguliere** : Expiration tous les 90 jours recommandee
2. **Scopes minimaux** : Principe du moindre privilege
3. **Monitoring** : Alerter sur usage anormal via `api_key_usage`
4. **Jamais en clair** : Ne jamais logger/stocker la cle brute
