# RBAC Module (Role-Based Access Control)

## Vue d'ensemble
Systeme complet de controle d'acces base sur les roles.
Supporte la multi-tenancy, l'heritage de roles, et l'assignation de roles aux API keys.

## Architecture

```
+-------------+     +------------------+     +-------------+
|    users    |---->|   user_roles     |<----|    roles    |
+-------------+     +------------------+     +-------------+
                                                    |
                                                    v
+-------------+     +------------------+     +-------------+
|  api_keys   |---->|  api_key_roles   |     | role_perms  |
+-------------+     +------------------+     +-------------+
                                                    |
                                                    v
                                            +-------------+
                                            | permissions |
                                            +-------------+

                    +------------------+
                    | role_hierarchy   |  <- Heritage de roles
                    +------------------+
```

## Tables

### `roles`
Definition des roles par tenant.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `tenant_id` | BIGINT | Tenant proprietaire |
| `name` | TEXT | Nom du role (ex: admin, manager, viewer) |
| `description` | TEXT | Description du role |
| `created_at` | TIMESTAMPTZ | Date de creation |

**Contrainte:** `UNIQUE (tenant_id, name)`

### `permissions`
Permissions atomiques globales.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `name` | TEXT | Nom unique (ex: `read:inventory`) |
| `description` | TEXT | Description |

**Contrainte:** `UNIQUE (name)`

### `role_permissions`
Mapping roles vers permissions.

| Colonne | Type | Description |
|---------|------|-------------|
| `role_id` | BIGINT | Reference vers `roles.id` |
| `permission_id` | BIGINT | Reference vers `permissions.id` |

**PK:** `(role_id, permission_id)`

### `user_roles`
Assignation des roles aux utilisateurs.

| Colonne | Type | Description |
|---------|------|-------------|
| `user_id` | BIGINT | Utilisateur |
| `role_id` | BIGINT | Role assigne |
| `tenant_id` | BIGINT | Tenant (pour isolation) |
| `assigned_at` | TIMESTAMPTZ | Date d'assignation |

**PK:** `(user_id, role_id)`

### `api_key_roles`
Assignation des roles aux API keys.

| Colonne | Type | Description |
|---------|------|-------------|
| `api_key_id` | BIGINT | Cle API |
| `role_id` | BIGINT | Role assigne |
| `tenant_id` | BIGINT | Tenant |

**PK:** `(api_key_id, role_id)`

### `role_hierarchy`
Heritage de roles (optionnel, avance).

| Colonne | Type | Description |
|---------|------|-------------|
| `parent_role_id` | BIGINT | Role parent |
| `child_role_id` | BIGINT | Role enfant (herite du parent) |

**PK:** `(parent_role_id, child_role_id)`

## Index

```sql
-- Roles par tenant
roles_tenant_idx ON roles (tenant_id)

-- Permissions par role
role_permissions_role_idx ON role_permissions (role_id)
role_permissions_permission_idx ON role_permissions (permission_id)

-- Roles par utilisateur
user_roles_user_idx ON user_roles (user_id)
user_roles_tenant_idx ON user_roles (tenant_id)

-- Roles par API key
api_key_roles_key_idx ON api_key_roles (api_key_id)
api_key_roles_tenant_idx ON api_key_roles (tenant_id)
```

## Convention de nommage des permissions

```
<action>:<resource>[:<scope>]

Exemples:
- read:inventory
- write:orders
- delete:users
- admin:billing
- manage:tenant:settings
```

## Roles predifinis recommandes

| Role | Description | Permissions typiques |
|------|-------------|---------------------|
| `super_admin` | Acces total | `*` |
| `admin` | Admin tenant | `manage:*` |
| `manager` | Gestionnaire | `read:*`, `write:*` |
| `editor` | Editeur | `read:*`, `write:own` |
| `viewer` | Lecture seule | `read:*` |
| `api_readonly` | API lecture | `read:*` (pour API keys) |

## Algorithme de verification

```python
def has_permission(user_id: int, tenant_id: int, permission: str) -> bool:
    # 1. Recuperer les roles de l'utilisateur
    user_roles = get_user_roles(user_id, tenant_id)

    # 2. Inclure les roles herites
    all_roles = set(user_roles)
    for role in user_roles:
        all_roles.update(get_inherited_roles(role))

    # 3. Recuperer toutes les permissions
    permissions = set()
    for role_id in all_roles:
        permissions.update(get_role_permissions(role_id))

    # 4. Verifier la permission (avec wildcard)
    return permission in permissions or '*' in permissions
```

## Heritage de roles (role_hierarchy)

```
super_admin
    |
    v
  admin --------+
    |           |
    v           v
 manager     billing_admin
    |
    v
  editor
    |
    v
  viewer
```

```sql
-- Configurer l'heritage
INSERT INTO role_hierarchy (parent_role_id, child_role_id) VALUES
    (1, 2),  -- super_admin -> admin
    (2, 3),  -- admin -> manager
    (3, 4),  -- manager -> editor
    (4, 5);  -- editor -> viewer
```

## Requetes utiles

### Toutes les permissions d'un utilisateur
```sql
WITH user_role_ids AS (
    SELECT role_id FROM user_roles WHERE user_id = :user_id AND tenant_id = :tenant_id
),
all_permissions AS (
    SELECT DISTINCT p.name
    FROM role_permissions rp
    JOIN permissions p ON p.id = rp.permission_id
    WHERE rp.role_id IN (SELECT role_id FROM user_role_ids)
)
SELECT * FROM all_permissions;
```

### Utilisateurs ayant un role specifique
```sql
SELECT u.* FROM users u
JOIN user_roles ur ON ur.user_id = u.id
JOIN roles r ON r.id = ur.role_id
WHERE r.name = 'admin' AND ur.tenant_id = :tenant_id;
```

### Ajouter un role a un utilisateur
```sql
INSERT INTO user_roles (user_id, role_id, tenant_id)
SELECT :user_id, id, tenant_id
FROM roles
WHERE name = :role_name AND tenant_id = :tenant_id
ON CONFLICT (user_id, role_id) DO NOTHING;
```

## Relations avec autres modules

- **api_keys/** : Les API keys peuvent avoir des roles via `api_key_roles`
- **features/** : Feature flags peuvent etre controles par role
- **audit/** : Changements de roles logues dans `audit_log`
- **auth/** : Permissions verifiees a chaque requete

## Securite

1. **Principe du moindre privilege** : Assigner le minimum de permissions
2. **Separation des roles** : Ne pas melanger admin et user dans le meme role
3. **Audit** : Logger tous les changements de roles
4. **Review periodique** : Auditer les assignations de roles regulierement
