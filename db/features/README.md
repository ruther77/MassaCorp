# Features Module (Feature Flags)

## Vue d'ensemble
Systeme de feature flags multi-niveaux permettant un controle granulaire de l'activation
des fonctionnalites. Supporte le deploiement progressif, les tests A/B, et la gestion
fine des acces par tenant/role/utilisateur.

## Architecture hierarchique

```
                    +-------------------+
                    |     features      |  <- Catalogue des features
                    +-------------------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
    +------------------+  +------------------+  +------------------+
    | feature_flags_   |  | feature_flags_   |  | feature_flags_   |
    |     global       |  |     tenant       |  |      role        |
    +------------------+  +------------------+  +------------------+
                                    |
                                    v
                         +------------------+
                         | feature_flags_   |
                         |      user        |
                         +------------------+
```

**Ordre de priorite (du plus specifique au plus general):**
1. `feature_flags_user` - Override par utilisateur
2. `feature_flags_role` - Override par role
3. `feature_flags_tenant` - Override par tenant
4. `feature_flags_global` - Valeur par defaut globale

## Tables

### `features`
Catalogue central des fonctionnalites.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `key` | TEXT | Cle unique (ex: `export_excel`, `new_dashboard`) |
| `description` | TEXT | Description de la fonctionnalite |
| `created_at` | TIMESTAMPTZ | Date de creation |

### `feature_flags_global`
Activation globale par defaut.

| Colonne | Type | Description |
|---------|------|-------------|
| `feature_id` | BIGINT (PK) | Reference vers `features.id` |
| `enabled` | BOOLEAN | Active/inactive par defaut |

### `feature_flags_tenant`
Override par tenant.

| Colonne | Type | Description |
|---------|------|-------------|
| `feature_id` | BIGINT | Reference vers `features.id` |
| `tenant_id` | BIGINT | Tenant concerne |
| `enabled` | BOOLEAN | Active/inactive pour ce tenant |

**PK:** `(feature_id, tenant_id)`

### `feature_flags_role`
Override par role.

| Colonne | Type | Description |
|---------|------|-------------|
| `feature_id` | BIGINT | Reference vers `features.id` |
| `role_id` | BIGINT | Role concerne |
| `enabled` | BOOLEAN | Active/inactive pour ce role |

**PK:** `(feature_id, role_id)`

### `feature_flags_user`
Override par utilisateur (le plus prioritaire).

| Colonne | Type | Description |
|---------|------|-------------|
| `feature_id` | BIGINT | Reference vers `features.id` |
| `user_id` | BIGINT | Utilisateur concerne |
| `enabled` | BOOLEAN | Active/inactive pour cet utilisateur |

**PK:** `(feature_id, user_id)`

## Index

```sql
-- Lookup rapide par tenant
feature_flags_tenant_idx ON feature_flags_tenant (tenant_id)

-- Lookup rapide par role
feature_flags_role_idx ON feature_flags_role (role_id)

-- Lookup rapide par utilisateur
feature_flags_user_idx ON feature_flags_user (user_id)
```

## Algorithme de resolution

```python
def is_feature_enabled(feature_key, user_id, tenant_id, role_ids):
    feature = get_feature_by_key(feature_key)

    # 1. Check user override (highest priority)
    user_flag = get_user_flag(feature.id, user_id)
    if user_flag is not None:
        return user_flag.enabled

    # 2. Check role overrides (any role enables = enabled)
    for role_id in role_ids:
        role_flag = get_role_flag(feature.id, role_id)
        if role_flag is not None and role_flag.enabled:
            return True

    # 3. Check tenant override
    tenant_flag = get_tenant_flag(feature.id, tenant_id)
    if tenant_flag is not None:
        return tenant_flag.enabled

    # 4. Fallback to global
    global_flag = get_global_flag(feature.id)
    return global_flag.enabled if global_flag else False
```

## Cas d'usage

### Deploiement progressif (Canary)
```sql
-- 1. Feature desactivee globalement
INSERT INTO feature_flags_global (feature_id, enabled) VALUES (1, false);

-- 2. Activer pour un tenant beta
INSERT INTO feature_flags_tenant (feature_id, tenant_id, enabled) VALUES (1, 42, true);

-- 3. Puis etendre a tous
UPDATE feature_flags_global SET enabled = true WHERE feature_id = 1;
```

### Feature premium (par role)
```sql
-- Feature reservee aux admins et premium
INSERT INTO feature_flags_global (feature_id, enabled) VALUES (2, false);
INSERT INTO feature_flags_role (feature_id, role_id, enabled) VALUES (2, 1, true); -- admin
INSERT INTO feature_flags_role (feature_id, role_id, enabled) VALUES (2, 5, true); -- premium
```

### Beta testeur individuel
```sql
-- Activer pour un utilisateur specifique
INSERT INTO feature_flags_user (feature_id, user_id, enabled) VALUES (3, 123, true);
```

## Relations avec autres modules

- **rbac/** : Les roles references dans `feature_flags_role`
- **audit/** : Logger les changements de feature flags

## Bonnes pratiques

1. **Nommage coherent** : `module_feature_name` (ex: `billing_stripe_v2`)
2. **Documentation** : Toujours renseigner `description`
3. **Cleanup** : Supprimer les flags obsoletes apres deploiement complet
4. **Monitoring** : Tracker l'usage des features pour mesurer l'adoption
