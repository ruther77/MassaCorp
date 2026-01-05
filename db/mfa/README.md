# MFA Module (Multi-Factor Authentication)

## Vue d'ensemble
Module d'authentification multi-facteurs basé sur TOTP (Time-based One-Time Password).
Compatible avec Google Authenticator, Authy, 1Password, et autres applications TOTP.

## Tables

### `mfa_secrets`
Secrets TOTP par utilisateur.

| Colonne | Type | Description |
|---------|------|-------------|
| `user_id` | BIGINT (PK) | Utilisateur (un secret par user) |
| `tenant_id` | BIGINT | Tenant pour isolation |
| `secret` | TEXT | Secret TOTP (base32, chiffre en DB) |
| `enabled` | BOOLEAN | MFA actif pour cet utilisateur |
| `created_at` | TIMESTAMPTZ | Date de configuration |
| `last_used_at` | TIMESTAMPTZ | Derniere utilisation MFA |

### `mfa_recovery_codes`
Codes de secours pour recuperation d'acces.

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `user_id` | BIGINT | Utilisateur proprietaire |
| `tenant_id` | BIGINT | Tenant pour isolation |
| `code_hash` | TEXT | Hash du code (jamais en clair) |
| `used_at` | TIMESTAMPTZ | Date d'utilisation (NULL = disponible) |
| `created_at` | TIMESTAMPTZ | Date de generation |

## Index

```sql
-- Lookup par tenant
mfa_secrets_tenant_idx ON mfa_secrets (tenant_id)

-- Lookup codes par utilisateur
mfa_recovery_codes_user_idx ON mfa_recovery_codes (user_id)

-- Codes utilises (pour cleanup)
mfa_recovery_codes_used_at_idx ON mfa_recovery_codes (used_at)
```

## Flux MFA

### 1. Activation MFA

```
User -> POST /mfa/setup
        |
        v
   Generer secret TOTP (160 bits)
        |
        v
   Chiffrer et stocker dans mfa_secrets (enabled = false)
        |
        v
   Retourner QR code (otpauth://totp/...)
        |
        v
User -> Scanne avec app TOTP
        |
        v
User -> POST /mfa/verify {code: "123456"}
        |
        v
   Valider TOTP avec le secret
        |
        v
   UPDATE mfa_secrets SET enabled = true
        |
        v
   Generer 10 recovery codes, hasher et stocker
        |
        v
   Retourner les recovery codes (UNE SEULE FOIS)
```

### 2. Login avec MFA (Issue #1 - Flow 2 étapes)

```
=== Étape 1: Authentification credentials ===

User -> POST /auth/login {email, password}
        + Header: X-Tenant-ID: 1
        |
        v
   Credentials valides
        |
        v
   Verifier si mfa_secrets.enabled = true (via MFAService.is_mfa_enabled)
        |
        v
   Generer mfa_session_token (JWT type="mfa_session", expire=5min)
        |
        v
   Retourner {mfa_required: true, mfa_session_token: "...", message: "MFA verification required"}

=== Étape 2: Vérification TOTP ===

User -> POST /auth/login/mfa {mfa_session_token, totp_code: "123456"}
        |
        v
   Valider mfa_session_token (signature, expiration, type="mfa_session")
        |
        v
   Extraire user_id du token
        |
        v
   Verifier TOTP via MFAService.verify_totp(user_id, code)
        |
        v
   UPDATE mfa_secrets SET last_used_at = NOW()
        |
        v
   Creer session dans `sessions`
        |
        v
   Generer access_token + refresh_token
        |
        v
   Retourner {access_token, refresh_token, token_type, expires_in, session_id}
```

**Sécurité du mfa_session_token:**

| Propriété | Valeur | Justification |
|-----------|--------|---------------|
| Type | `mfa_session` | Distingué de `access` et `refresh` |
| Durée | 5 minutes | Limite fenêtre d'attaque |
| Accès API | **Non** | Ne peut pas être utilisé comme access_token |
| Contenu | user_id, tenant_id | Minimum nécessaire pour étape 2 |

### 3. Utilisation recovery code

```
User -> POST /auth/mfa {mfa_token, recovery_code: "ABCD-1234"}
        |
        v
   Hasher le code fourni
        |
        v
   Chercher dans mfa_recovery_codes WHERE code_hash = hash AND used_at IS NULL
        |
        v
   Si trouve: UPDATE mfa_recovery_codes SET used_at = NOW()
        |
        v
   Continuer login + ALERTER que des codes ont ete utilises
```

## Securite

### Chiffrement des secrets TOTP (AES-256-GCM)

Les secrets TOTP sont chiffres avant stockage en base de donnees avec AES-256-GCM.
Cela garantit la confidentialite meme en cas de fuite de la base.

```python
# app/core/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

def encrypt_totp_secret(secret: str) -> str:
    """Chiffre un secret TOTP avec AES-256-GCM"""
    key = _get_encryption_key()  # 32 bytes depuis config
    aesgcm = AESGCM(key)
    iv = os.urandom(12)  # IV unique par chiffrement
    ciphertext = aesgcm.encrypt(iv, secret.encode(), None)
    return base64.b64encode(iv + ciphertext).decode()

def decrypt_totp_secret(encrypted: str) -> str:
    """Dechiffre un secret TOTP"""
    key = _get_encryption_key()
    encrypted = base64.b64decode(encrypted)
    iv, ciphertext = encrypted[:12], encrypted[12:]
    return AESGCM(key).decrypt(iv, ciphertext, None).decode()
```

### Hachage des recovery codes (bcrypt)

Les recovery codes sont haches avec **bcrypt** (pas SHA-256) pour resister aux attaques brute-force.
bcrypt est intentionnellement lent (~100ms par verification).

```python
# app/services/mfa.py
import bcrypt

def _hash_recovery_code(code: str) -> str:
    """Hash un recovery code avec bcrypt (cost=10)"""
    normalized = code.upper().replace("-", "")
    return bcrypt.hashpw(normalized.encode(), bcrypt.gensalt(rounds=10)).decode()

def _verify_code_hash(code: str, code_hash: str) -> bool:
    """Verification en temps constant avec bcrypt.checkpw"""
    normalized = code.upper().replace("-", "")
    return bcrypt.checkpw(normalized.encode(), code_hash.encode())
```

### Rate limiting MFA

Les endpoints MFA sont proteges contre le brute-force:

| Endpoint | Limite | Raison |
|----------|--------|--------|
| `/mfa/verify` | 5 req/min | TOTP 6 digits = 1M combinaisons |
| `/mfa/enable` | 5 req/min | Protection setup |
| `/mfa/recovery/verify` | 3 req/min | Recovery codes plus precieux |

### Validation TOTP
```python
import pyotp

def verify_totp(secret: str, code: str) -> bool:
    # Dechiffrer le secret d'abord
    decrypted = decrypt_totp_secret(secret)
    totp = pyotp.TOTP(decrypted)
    # Accepter +/- 1 intervalle (30 secondes de tolerance)
    return totp.verify(code, valid_window=1)
```

## Requetes utiles

### Utilisateurs avec MFA actif
```sql
SELECT user_id, created_at, last_used_at
FROM mfa_secrets
WHERE enabled = true
  AND tenant_id = :tenant_id;
```

### Recovery codes restants
```sql
SELECT COUNT(*) as remaining
FROM mfa_recovery_codes
WHERE user_id = :user_id
  AND used_at IS NULL;
```

### Desactivation MFA (admin)
```sql
BEGIN;
UPDATE mfa_secrets SET enabled = false WHERE user_id = :user_id;
DELETE FROM mfa_recovery_codes WHERE user_id = :user_id;
COMMIT;
```

## Relations avec autres modules

- **auth/** : Integration dans le flux de login
- **audit/** : Logger activation/desactivation/utilisation MFA
- **security/** : MFA requis apres X echecs de connexion

## Bonnes pratiques

1. **Chiffrement obligatoire** : Ne jamais stocker le secret TOTP en clair
2. **10 recovery codes** : Standard industriel
3. **Usage unique** : Recovery codes utilisables une seule fois
4. **Alerte** : Notifier l'utilisateur quand un recovery code est utilise
5. **Regeneration** : Permettre de regenerer les recovery codes
6. **Backup** : L'utilisateur doit conserver ses recovery codes en lieu sur
