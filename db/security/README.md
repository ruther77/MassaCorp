# Security Module

## Vue d'ensemble
Module de securite centré sur la protection contre les attaques par bruteforce
et le rate-limiting des tentatives de connexion.

## Tables

### `login_attempts`
Journal des tentatives de connexion pour detection d'attaques.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `identifier` | TEXT | Email ou username tente |
| `ip` | TEXT | Adresse IP source |
| `attempted_at` | TIMESTAMPTZ | Timestamp de la tentative |
| `success` | BOOLEAN | Reussite ou echec |

## Index

```sql
-- Recherche par identifiant (email/username)
login_attempts_identifier_idx ON login_attempts (identifier)

-- Recherche par IP (detection d'attaque distribuee)
login_attempts_ip_idx ON login_attempts (ip)

-- Recherche temporelle (fenetres de rate-limit)
login_attempts_attempted_at_idx ON login_attempts (attempted_at)
```

## Politiques anti-bruteforce

### Par identifiant (compte)
```sql
-- Compter les echecs recents pour un compte
SELECT COUNT(*) as failed_count
FROM login_attempts
WHERE identifier = :email
  AND success = false
  AND attempted_at > NOW() - INTERVAL '15 minutes';
```

| Echecs | Action |
|--------|--------|
| 3 | CAPTCHA requis |
| 5 | Delai de 30 secondes |
| 10 | Compte verrouille 15 minutes |
| 20 | Compte verrouille 1 heure |
| 50 | Compte verrouille + alerte admin |

### Par IP
```sql
-- Compter les echecs depuis une IP
SELECT COUNT(*) as failed_count
FROM login_attempts
WHERE ip = :ip
  AND success = false
  AND attempted_at > NOW() - INTERVAL '1 hour';
```

| Echecs | Action |
|--------|--------|
| 20 | CAPTCHA pour cette IP |
| 50 | Rate-limit 1 req/10s |
| 100 | IP bloquee 1 heure |
| 500 | IP bloquee 24h + alerte |

## Implementation recommandee

### Middleware de protection
```python
from datetime import datetime, timedelta

async def check_login_rate_limit(identifier: str, ip: str) -> dict:
    """
    Retourne:
    - allowed: bool
    - require_captcha: bool
    - wait_seconds: int
    - reason: str
    """

    # Echecs par identifiant (15 min)
    identifier_failures = await db.fetch_val("""
        SELECT COUNT(*) FROM login_attempts
        WHERE identifier = $1 AND success = false
        AND attempted_at > NOW() - INTERVAL '15 minutes'
    """, identifier)

    # Echecs par IP (1 heure)
    ip_failures = await db.fetch_val("""
        SELECT COUNT(*) FROM login_attempts
        WHERE ip = $1 AND success = false
        AND attempted_at > NOW() - INTERVAL '1 hour'
    """, ip)

    # Logique de decision
    if identifier_failures >= 50 or ip_failures >= 500:
        return {
            "allowed": False,
            "require_captcha": False,
            "wait_seconds": 3600,
            "reason": "too_many_attempts"
        }

    if identifier_failures >= 10:
        return {
            "allowed": False,
            "require_captcha": True,
            "wait_seconds": 900,
            "reason": "account_locked"
        }

    if identifier_failures >= 5 or ip_failures >= 20:
        return {
            "allowed": True,
            "require_captcha": True,
            "wait_seconds": 30,
            "reason": "suspicious_activity"
        }

    return {
        "allowed": True,
        "require_captcha": False,
        "wait_seconds": 0,
        "reason": None
    }
```

### Enregistrement des tentatives
```python
async def log_login_attempt(identifier: str, ip: str, success: bool):
    await db.execute("""
        INSERT INTO login_attempts (identifier, ip, success)
        VALUES ($1, $2, $3)
    """, identifier, ip, success)
```

## Requetes de monitoring

### Top 10 IPs suspectes (derniere heure)
```sql
SELECT ip,
       COUNT(*) as total_attempts,
       COUNT(*) FILTER (WHERE success = false) as failures,
       COUNT(DISTINCT identifier) as unique_accounts
FROM login_attempts
WHERE attempted_at > NOW() - INTERVAL '1 hour'
GROUP BY ip
HAVING COUNT(*) FILTER (WHERE success = false) > 10
ORDER BY failures DESC
LIMIT 10;
```

### Comptes les plus attaques
```sql
SELECT identifier,
       COUNT(*) as total_attempts,
       COUNT(*) FILTER (WHERE success = false) as failures,
       MAX(attempted_at) as last_attempt
FROM login_attempts
WHERE attempted_at > NOW() - INTERVAL '24 hours'
GROUP BY identifier
HAVING COUNT(*) FILTER (WHERE success = false) > 5
ORDER BY failures DESC;
```

### Taux de succes par heure (graphique)
```sql
SELECT
    DATE_TRUNC('hour', attempted_at) as hour,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE success = true) as success,
    ROUND(100.0 * COUNT(*) FILTER (WHERE success = true) / COUNT(*), 2) as success_rate
FROM login_attempts
WHERE attempted_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', attempted_at)
ORDER BY hour;
```

## Rate Limiting MFA

Les endpoints MFA ont des limites strictes pour prevenir le brute-force:

```python
# app/middleware/rate_limit.py
self.endpoint_limits = {
    # Auth endpoints
    "/api/v1/auth/login": 5,
    "/api/v1/auth/refresh": 30,
    "/api/v1/auth/logout": 30,
    # MFA endpoints - limites strictes
    "/api/v1/mfa/verify": 5,           # TOTP 6 digits = 1M combinaisons
    "/api/v1/mfa/enable": 5,
    "/api/v1/mfa/disable": 5,
    "/api/v1/mfa/recovery/verify": 3,  # Plus strict (codes precieux)
    "/api/v1/mfa/recovery/regenerate": 3,
}
```

### Justification des limites MFA

| Endpoint | Limite | Calcul |
|----------|--------|--------|
| `/mfa/verify` | 5/min | TOTP = 6 digits = 10^6 combinaisons. A 5/min, brute-force prendrait ~139 jours |
| `/mfa/recovery/verify` | 3/min | Recovery codes = 8 chars = 32^8 combinaisons. Plus precieux, limite plus stricte |

### Detection attaque MFA

```sql
-- Tentatives MFA excessives (derniere heure)
SELECT user_id, ip, COUNT(*) as attempts
FROM audit_log
WHERE action IN ('mfa_verify_failed', 'recovery_code_failed')
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY user_id, ip
HAVING COUNT(*) > 10
ORDER BY attempts DESC;
```

## Integration avec autres modules

- **auth/** : Appele avant chaque tentative de login
- **audit/** : Correlation avec `audit_log` pour investigation
- **mfa/** : MFA obligatoire apres echecs multiples, rate limiting specifique
- **maintenance/** : Cleanup automatique > 30 jours

## Alertes recommandees

### Temps reel
- IP avec > 100 echecs/heure
- Compte avec > 20 echecs/15 minutes
- Spike de tentatives (> 5x la normale)

### Quotidiennes
- Top 10 IPs bloquees
- Comptes frequemment attaques
- Anomalies par rapport a la baseline

## Bonnes pratiques

1. **Ne pas reveler l'existence du compte** : Message generique "Invalid credentials"
2. **Timing constant** : Meme temps de reponse que le compte existe ou non
3. **Logs structures** : Format JSON pour SIEM
4. **Geo-blocking optionnel** : Bloquer les pays non attendus
5. **CAPTCHA progressif** : Augmenter la difficulte avec les echecs

## Securite JWT et Validation (Phase 4.1)

### Validation des secrets au demarrage

```python
# app/core/config.py
class Settings(BaseSettings):
    _DANGEROUS_DEFAULTS = [
        "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES",
        "CHANGER_CLE_CHIFFREMENT_32_OCTETS",
    ]

    def validate_secrets(self) -> None:
        """DOIT etre appele au demarrage en production"""
        if self.ENV == "production":
            if self.JWT_SECRET in self._DANGEROUS_DEFAULTS:
                raise ValueError("JWT_SECRET non configure!")
            if self.ENCRYPTION_KEY in self._DANGEROUS_DEFAULTS:
                raise ValueError("ENCRYPTION_KEY non configure!")
```

### Protection IDOR Cross-Tenant

```python
# app/core/dependencies.py
def get_current_user(...) -> User:
    # ...
    # Validation cross-tenant: le tenant du token DOIT correspondre
    token_tenant_id = payload.get("tenant_id")
    if token_tenant_id is not None and token_tenant_id != user.tenant_id:
        raise HTTPException(401, "Token invalide: tenant mismatch")
```

### Validation securisee du payload JWT

```python
def _validate_and_extract_user_id(payload: dict) -> int:
    """Valide et extrait le user_id de maniere securisee"""
    sub = payload.get("sub")

    if sub is None:
        raise HTTPException(401, "Token invalide: subject manquant")

    try:
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(401, "Token invalide: subject malformed")

    if user_id <= 0:
        raise HTTPException(401, "Token invalide: subject invalide")

    return user_id
```

### Identification de la session courante

```python
# app/core/dependencies.py
def get_current_session_id(credentials) -> Optional[UUID]:
    """Extrait le session_id du token pour identifier la session courante"""
    payload = decode_token(credentials.credentials)
    session_id_str = payload.get("session_id")
    return UUID(session_id_str) if session_id_str else None
```

### Checklist securite JWT

| Verification | Implementation |
|--------------|----------------|
| sub non None | `_validate_and_extract_user_id()` |
| sub numerique valide | `try: int(sub)` |
| sub > 0 | `if user_id <= 0: raise` |
| tenant match | `token.tenant_id == user.tenant_id` |
| payload non None | `if payload is None: return None` |
| type token correct | `payload.get("type") == "access"` |

## Response Login Unifiee (Phase 4.3)

Le endpoint `/auth/login` retourne maintenant un schema unifie `LoginResponse`
quel que soit le resultat (MFA requis ou login complet).

### Schema LoginResponse

```python
class LoginResponse(BaseSchema):
    success: bool = True
    # Tokens (None si MFA requis)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    # MFA (False si login complet)
    mfa_required: bool = False
    mfa_session_token: Optional[str] = None
    message: Optional[str] = None
```

### Exemples de reponses

**Login sans MFA:**
```json
{
  "success": true,
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "mfa_required": false,
  "mfa_session_token": null,
  "message": null
}
```

**Login avec MFA requis:**
```json
{
  "success": true,
  "access_token": null,
  "refresh_token": null,
  "token_type": null,
  "expires_in": null,
  "mfa_required": true,
  "mfa_session_token": "eyJ...",
  "message": "MFA verification required"
}
```

### Avantages

- **Coherence**: Le client peut toujours parser le meme schema
- **Predictibilite**: Pas besoin de detecter le type de reponse
- **Simplicite**: Un seul type TypeScript/interface cote client

## Logging des erreurs (Phase 4.3)

Les erreurs de session sont maintenant loggees en niveau ERROR:

```python
# app/api/v1/endpoints/sessions.py
except Exception as e:
    logger.error(f"Echec termination session {session_id}...")
```

Ceci permet une meilleure detection des problemes en production.
