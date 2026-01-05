# Audit Module

## Vue d'ensemble
Module de journalisation centralise pour la tracabilite complete des actions systeme.
Indispensable pour la conformite (RGPD, SOC2, ISO 27001) et l'investigation de securite.

## Tables

### `audit_log`
Table centrale d'audit immutable.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique sequentiel |
| `event_type` | TEXT | Type d'evenement (voir liste ci-dessous) |
| `user_id` | BIGINT | Utilisateur concerne (NULL si systeme) |
| `tenant_id` | BIGINT | Tenant concerne |
| `session_id` | UUID | Session associee |
| `ip` | TEXT | Adresse IP source |
| `user_agent` | TEXT | User-Agent du client |
| `success` | BOOLEAN | Succes ou echec de l'action |
| `metadata` | JSONB | Donnees contextuelles flexibles |
| `created_at` | TIMESTAMPTZ | Timestamp de l'evenement |

## Types d'evenements (`event_type`)

### Authentification
- `auth.login` - Connexion utilisateur
- `auth.logout` - Deconnexion
- `auth.login_failed` - Echec de connexion
- `auth.password_changed` - Changement de mot de passe
- `auth.password_reset` - Reinitialisation mot de passe
- `auth.mfa_enabled` - Activation MFA
- `auth.mfa_disabled` - Desactivation MFA

### Sessions
- `session.created` - Nouvelle session
- `session.revoked` - Session revoquee
- `session.expired` - Session expiree

### API Keys
- `apikey.created` - Creation cle API
- `apikey.revoked` - Revocation cle API
- `apikey.rotated` - Rotation cle API

### RBAC
- `role.assigned` - Role assigne a un utilisateur
- `role.removed` - Role retire
- `permission.changed` - Modification permissions

### SSO
- `sso.login` - Connexion via SSO
- `sso.provider_added` - Nouveau provider SSO
- `sso.provider_removed` - Provider SSO retire

### Donnees
- `data.export` - Export de donnees
- `data.delete` - Suppression de donnees
- `data.access` - Acces sensible

## Index de performance

```sql
-- Recherche par type d'evenement
audit_log_event_type_idx ON audit_log (event_type)

-- Historique utilisateur
audit_log_user_idx ON audit_log (user_id)

-- Historique tenant
audit_log_tenant_idx ON audit_log (tenant_id)

-- Recherche temporelle (dashboards, rapports)
audit_log_created_at_idx ON audit_log (created_at)
```

## Structure `metadata` (JSONB)

Exemples de contenu selon le type d'evenement:

```json
// auth.login
{
  "method": "password",
  "mfa_used": true,
  "device_fingerprint": "abc123"
}

// apikey.created
{
  "key_name": "n8n-prod",
  "scopes": ["read:inventory", "write:orders"],
  "expires_in_days": 90
}

// data.export
{
  "format": "csv",
  "tables": ["users", "orders"],
  "row_count": 15420
}
```

## Requetes utiles

### Echecs de connexion recents (securite)
```sql
SELECT * FROM audit_log
WHERE event_type = 'auth.login_failed'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

### Activite d'un utilisateur
```sql
SELECT * FROM audit_log
WHERE user_id = :user_id
ORDER BY created_at DESC
LIMIT 100;
```

### Rapport de conformite (30 derniers jours)
```sql
SELECT event_type, COUNT(*),
       COUNT(*) FILTER (WHERE success = true) as success_count
FROM audit_log
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY event_type
ORDER BY COUNT(*) DESC;
```

## Retention et archivage

- **Retention active** : 12 mois (configurable)
- **Archivage** : Export vers stockage froid avant suppression
- **Cleanup** : Voir `maintenance/cleanup.sql`

## Relations avec autres modules

- **auth/** : Sessions et tokens references
- **security/** : Correle avec `login_attempts`
- **api_keys/** : Traçabilite des actions via cles API

## Conformite

- **RGPD** : Permet le droit d'acces (Article 15)
- **SOC2** : Audit trail complet
- **ISO 27001** : Journalisation des evenements de securite
