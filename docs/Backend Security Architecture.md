# Backend Security & Architecture Checklist

> **Audience**: Équipe d'ingénieurs confirmés  
> **Stack**: FastAPI + PostgreSQL + JWT + Multi-tenant SaaS  
> **Version**: 1.0  

---

## Table des matières

1. [Sécurité - Authentification](#1-sécurité---authentification)
2. [Sécurité - Tokens JWT](#2-sécurité---tokens-jwt)
3. [Sécurité - Mots de passe](#3-sécurité---mots-de-passe)
4. [Sécurité - Anti-bruteforce & Rate Limiting](#4-sécurité---anti-bruteforce--rate-limiting)
5. [Sécurité - MFA](#5-sécurité---mfa)
6. [Sécurité - Sessions](#6-sécurité---sessions)
7. [Sécurité - API Keys](#7-sécurité---api-keys)
8. [Sécurité - Headers HTTP](#8-sécurité---headers-http)
9. [Sécurité - Input Validation](#9-sécurité---input-validation)
10. [Architecture - Structure projet](#10-architecture---structure-projet)
11. [Architecture - Middleware Stack](#11-architecture---middleware-stack)
12. [Architecture - Dependency Injection](#12-architecture---dependency-injection)
13. [Architecture - Service Layer](#13-architecture---service-layer)
14. [Architecture - Repository Pattern](#14-architecture---repository-pattern)
15. [Architecture - Exception Handling](#15-architecture---exception-handling)
16. [Multi-tenant](#16-multi-tenant)
17. [Base de données - Schema](#17-base-de-données---schema)
18. [Base de données - Performance](#18-base-de-données---performance)
19. [Base de données - Maintenance](#19-base-de-données---maintenance)
20. [Observabilité - Logging](#20-observabilité---logging)
21. [Observabilité - Metrics](#21-observabilité---metrics)
22. [Observabilité - Tracing](#22-observabilité---tracing)
23. [Performance](#23-performance)
24. [Tests](#24-tests)
25. [CI/CD](#25-cicd)
26. [Documentation](#26-documentation)
27. [Compliance & Audit](#27-compliance--audit)
28. [Operations](#28-operations)

---

## 1. Sécurité - Authentification

### 1.1 Flow Login

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Constant-time comparison** | 🔴 CRITICAL | Utiliser `secrets.compare_digest()` pour comparer hashes, jamais `==` |
| [x] | **User enumeration prevention** | 🔴 CRITICAL | Même message d'erreur que l'user existe ou non: "Invalid credentials" |
| [x] | **Timing attack prevention** | 🔴 CRITICAL | Hasher un DUMMY_HASH si user inexistant pour garder timing constant |
| [x] | **Credentials in body only** | 🔴 CRITICAL | Jamais de password dans URL, query params, ou headers custom |
| [x] | **HTTPS only** | 🔴 CRITICAL | Refuser HTTP en production, même pour /health |
| [x] | **Login response unifié** | 🟠 HIGH | Même schema LoginResponse que MFA requis ou non |
| [x] | **Lowercase email** | 🟠 HIGH | Normaliser email en lowercase avant lookup |
| [x] | **Trim whitespace** | 🟠 HIGH | Strip espaces sur email/username |

```python
# ✅ Implementation correcte
DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.V" # Precomputed

async def authenticate(email: str, password: str) -> User:
    email = email.lower().strip()
    user = await user_repo.get_by_email(email)
    
    # Timing constant: hash même si user inexistant
    hash_to_verify = user.password_hash if user else DUMMY_HASH
    password_valid = secrets.compare_digest(
        verify_password(password, hash_to_verify).encode(),
        b"valid"  # ou votre logique
    )
    # Alternative avec passlib:
    # password_valid = pwd_context.verify(password, hash_to_verify)
    
    if not user or not password_valid:
        # Log failed attempt AVANT de raise
        await audit.log("login_failed", identifier=email)
        raise InvalidCredentials()  # Message générique
    
    return user
```

### 1.2 Logout

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Blacklist access token** | 🔴 CRITICAL | Insérer JTI dans `revoked_tokens` |
| [x] | **Révoquer session** | 🔴 CRITICAL | `sessions.revoked_at = NOW()` |
| [x] | **Invalider tous refresh tokens** | 🔴 CRITICAL | Via CASCADE ou update explicite |
| [x] | **Logout all devices** | 🟠 HIGH | Endpoint pour révoquer toutes les sessions sauf courante |
| [N/A] | **Clear cookies** | 🟠 HIGH | N/A - Bearer tokens utilisés, pas de cookies |

### 1.3 Password Reset

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Token usage unique** | 🔴 CRITICAL | Marquer `used_at` après utilisation |
| [x] | **Expiration courte** | 🔴 CRITICAL | 1 heure max |
| [x] | **Invalider sessions existantes** | 🔴 CRITICAL | Forcer re-login après reset |
| [x] | **Rate limit requests** | 🔴 CRITICAL | Max 3 demandes/heure/email |
| [x] | **Token cryptographiquement sûr** | 🔴 CRITICAL | `secrets.token_urlsafe(32)` minimum |
| [x] | **Hasher le token en DB** | 🟠 HIGH | Stocker SHA-256, pas le token brut |
| [x] | **Email générique** | 🟠 HIGH | "If this email exists, you'll receive..." |
| [x] | **Log password changes** | 🟠 HIGH | AuditService.log_action("user.password_change") |

---

## 2. Sécurité - Tokens JWT

### 2.1 Génération

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Secret ≥ 256 bits** | 🔴 CRITICAL | Minimum 32 caractères aléatoires |
| [x] | **Secret unique par env** | 🔴 CRITICAL | Dev ≠ Staging ≠ Prod |
| [x] | **Validation secret au startup** | 🔴 CRITICAL | Crash si secret = valeur par défaut |
| [x] | **Algorithm explicite** | 🔴 CRITICAL | Toujours spécifier `algorithm="HS256"` ou RS256 |
| [x] | **JTI unique** | 🔴 CRITICAL | UUID v4 pour chaque token |
| [x] | **Claims minimaux** | 🟠 HIGH | sub, tenant_id, type, exp, iat, jti - pas de données sensibles |
| [ ] | **Issuer (iss)** | 🟡 MEDIUM | Identifier l'émetteur |
| [ ] | **Audience (aud)** | 🟡 MEDIUM | Identifier le destinataire |

```python
# ✅ Settings avec validation
class Settings(BaseSettings):
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    _DANGEROUS_DEFAULTS = ["changeme", "secret", "CHANGE_IN_PRODUCTION"]
    
    @validator("JWT_SECRET")
    def validate_jwt_secret(cls, v):
        if v in cls._DANGEROUS_DEFAULTS:
            raise ValueError("JWT_SECRET must be changed from default!")
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters!")
        return v
    
    def validate_production_secrets(self):
        """Call this at startup in production"""
        if self.ENV == "production":
            assert self.JWT_SECRET not in self._DANGEROUS_DEFAULTS
```

### 2.2 Validation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Vérifier signature** | 🔴 CRITICAL | Décoder avec verify=True |
| [x] | **Vérifier expiration** | 🔴 CRITICAL | Rejeter si exp < now |
| [x] | **Vérifier type** | 🔴 CRITICAL | access ≠ refresh ≠ mfa_session |
| [x] | **Check blacklist** | 🔴 CRITICAL | Lookup JTI dans `revoked_tokens` |
| [x] | **Check session active** | 🔴 CRITICAL | Si session_id présent, vérifier non révoquée |
| [x] | **Valider sub format** | 🔴 CRITICAL | Doit être int > 0 |
| [x] | **Cross-tenant validation** | 🔴 CRITICAL | token.tenant_id == user.tenant_id |
| [x] | **Rejeter algorithm none** | 🔴 CRITICAL | PyJWT le fait par défaut, mais vérifier |
| [ ] | **Clock skew tolerance** | 🟡 MEDIUM | ±30 secondes pour exp/iat |

```python
# ✅ Validation complète
def decode_and_validate_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "require": ["sub", "exp", "type", "jti"],
                "verify_exp": True,
            }
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    
    # Type check
    if payload.get("type") != expected_type:
        raise HTTPException(401, f"Expected {expected_type} token")
    
    # Sub validation
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(401, "Missing subject")
    try:
        user_id = int(sub)
        if user_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise HTTPException(401, "Invalid subject")
    
    return payload
```

### 2.3 Durées de vie

| Token Type | Durée | Justification |
|------------|-------|---------------|
| Access Token | 15 minutes | Court = moins de risque si volé |
| Refresh Token | 7 jours | UX vs sécurité |
| MFA Session | 5 minutes | Juste le temps de taper le code |
| Password Reset | 1 heure | Assez pour check email |
| Email Verification | 24 heures | Délais email possibles |
| API Key | 1 an ou permanent | Avec rotation recommandée |

### 2.4 Refresh Token Rotation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Rotation à chaque usage** | 🔴 CRITICAL | Ancien invalidé, nouveau émis |
| [x] | **Stocker hash, pas token** | 🔴 CRITICAL | SHA-256 du token en DB |
| [x] | **Tracking lineage** | 🔴 CRITICAL | `replaced_by_jti` pour tracer |
| [x] | **Replay detection** | 🔴 CRITICAL | Si token déjà used → révoquer TOUTE la session |
| [x] | **Validate session on refresh** | 🔴 CRITICAL | Session doit être active |
| [x] | **Absolute expiry** | 🟠 HIGH | Refresh max 30 jours même avec rotation - Session.absolute_expiry |

```python
# ✅ Refresh avec rotation et replay detection
async def refresh_tokens(refresh_token: str) -> TokenPair:
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    
    stored = await token_repo.get_by_hash(token_hash)
    if not stored:
        raise HTTPException(401, "Invalid refresh token")
    
    # Replay detection
    if stored.used_at is not None:
        # Token already used = stolen token replay attack!
        await session_service.revoke_session(stored.session_id)
        await audit.log("replay_attack_detected", session_id=stored.session_id)
        raise HTTPException(401, "Token reuse detected - session revoked")
    
    # Expiration check
    if stored.expires_at < datetime.utcnow():
        raise HTTPException(401, "Refresh token expired")
    
    # Session check
    session = await session_repo.get(stored.session_id)
    if not session or session.revoked_at:
        raise HTTPException(401, "Session revoked")
    
    # Mark as used
    await token_repo.mark_used(stored.jti)
    
    # Generate new pair
    new_access = create_access_token(session.user_id, session.tenant_id)
    new_refresh = create_refresh_token(session.id)
    
    # Link old to new
    await token_repo.set_replaced_by(stored.jti, new_refresh.jti)
    
    return TokenPair(access=new_access, refresh=new_refresh)
```

---

## 3. Sécurité - Mots de passe

### 3.1 Hashing

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **bcrypt ou Argon2id** | 🔴 CRITICAL | Jamais MD5, SHA1, SHA256 seul |
| [x] | **Cost factor approprié** | 🔴 CRITICAL | bcrypt cost ≥ 12, Argon2 memory ≥ 64MB |
| [x] | **Salt unique auto** | 🔴 CRITICAL | bcrypt/Argon2 le font automatiquement |
| [ ] | **Upgrade hash on login** | 🟡 MEDIUM | Si ancien algo, re-hash avec nouveau |

```python
# ✅ Configuration passlib
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Adjust based on server performance
)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def needs_rehash(hashed: str) -> bool:
    return pwd_context.needs_update(hashed)
```

### 3.2 Validation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Longueur minimum 8** | 🔴 CRITICAL | NIST recommande ≥8 |
| [x] | **Longueur maximum 128** | 🔴 CRITICAL | Prévenir DoS via bcrypt |
| [x] | **Complexité** | 🟠 HIGH | 1 maj, 1 min, 1 chiffre, 1 special |
| [x] | **Pas dans liste compromis** | 🟠 HIGH | Check contre HaveIBeenPwned ou liste locale |
| [x] | **Pas username/email** | 🟠 HIGH | Password ≠ identifiant |
| [x] | **Unicode supporté** | 🟡 MEDIUM | Permettre caractères non-ASCII |
| [x] | **No password hints** | 🟡 MEDIUM | Jamais de "indice" stocké |

```python
# ✅ Validation Pydantic
import re
from pydantic import BaseModel, validator

class PasswordMixin:
    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain special character")
        return v

class RegisterRequest(BaseModel, PasswordMixin):
    email: str
    password: str
```

---

## 4. Sécurité - Anti-bruteforce & Rate Limiting

### 4.1 Rate Limiting Global

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Middleware global** | 🔴 CRITICAL | Avant toute logique |
| [x] | **Backend Redis** | 🔴 CRITICAL | Pas in-memory en multi-instance |
| [x] | **Sliding window** | 🟠 HIGH | Plus juste que fixed window |
| [x] | **Différent par endpoint** | 🟠 HIGH | /login plus strict que /users |
| [x] | **Headers X-RateLimit-*** | 🟡 MEDIUM | Informer le client |
| [x] | **429 Too Many Requests** | 🟠 HIGH | Status code correct + Retry-After |

```python
# ✅ Rate limit middleware
from fastapi import Request, HTTPException
from redis.asyncio import Redis
import time

class RateLimitMiddleware:
    def __init__(self, redis: Redis, default_limit: int = 100, window: int = 60):
        self.redis = redis
        self.default_limit = default_limit
        self.window = window
        
        # Limites par endpoint
        self.endpoint_limits = {
            "/api/v1/auth/login": 5,
            "/api/v1/auth/refresh": 30,
            "/api/v1/mfa/verify": 5,
            "/api/v1/mfa/recovery/verify": 3,
            "/api/v1/auth/password/reset": 3,
        }
    
    async def __call__(self, request: Request, call_next):
        # Key based on IP + endpoint
        ip = request.client.host
        path = request.url.path
        key = f"ratelimit:{ip}:{path}"
        
        limit = self.endpoint_limits.get(path, self.default_limit)
        
        # Sliding window counter
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, self.window)
        results = await pipe.execute()
        
        request_count = results[2]
        
        if request_count > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + self.window)),
                }
            )
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - request_count))
        return response
```

### 4.2 Anti-bruteforce Login

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Tracking par identifier** | 🔴 CRITICAL | Email/username, fenêtre 15 min |
| [x] | **Tracking par IP** | 🔴 CRITICAL | Fenêtre 1 heure |
| [x] | **Escalade progressive** | 🔴 CRITICAL | CAPTCHA → Delay → Lock → Alert |
| [x] | **Log toutes tentatives** | 🔴 CRITICAL | Table `login_attempts` |
| [ ] | **Reset on success** | 🟠 HIGH | Ou pas - philosophie différente |
| [~] | **Notification user** | 🟠 HIGH | Email si tentatives suspectes - Infrastructure SMTP requise |
| [x] | **Alert admin** | 🟠 HIGH | Slack/PagerDuty si seuil atteint |

**Seuils recommandés:**

| Par identifier | Action |
|----------------|--------|
| 3 échecs | CAPTCHA |
| 5 échecs | Délai 30s entre tentatives |
| 10 échecs | Compte verrouillé 15 min |
| 20 échecs | Compte verrouillé 1h |
| 50 échecs | Lock + Alerte admin |

| Par IP | Action |
|--------|--------|
| 20 échecs | CAPTCHA pour cette IP |
| 50 échecs | Rate limit 1 req/10s |
| 100 échecs | IP bloquée 1h |
| 500 échecs | IP bloquée 24h + Alerte |

### 4.3 CAPTCHA

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **reCAPTCHA v3 ou hCaptcha** | 🟠 HIGH | Invisible, score-based |
| [x] | **Validation côté serveur** | 🔴 CRITICAL | Jamais faire confiance au client |
| [x] | **Timeout validation** | 🟠 HIGH | Token CAPTCHA expire vite |
| [ ] | **Fallback si service down** | 🟡 MEDIUM | Dégrader gracieusement |

---

## 5. Sécurité - MFA

### 5.1 TOTP

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Secret chiffré en DB** | 🔴 CRITICAL | AES-256-GCM, jamais plaintext |
| [x] | **QR code éphémère** | 🔴 CRITICAL | Ne pas stocker l'image |
| [x] | **Vérifier code avant enable** | 🔴 CRITICAL | Prouver que l'app est configurée |
| [x] | **Tolérance ±1 window** | 🟠 HIGH | 30s avant/après pour clock drift |
| [x] | **Anti-replay** | 🔴 CRITICAL | Un code ne peut être utilisé qu'une fois |
| [x] | **Rate limit verify** | 🔴 CRITICAL | Max 5/min (10^6 combinaisons) |

```python
# ✅ TOTP verification avec anti-replay
import pyotp
from datetime import datetime, timedelta

async def verify_totp(user_id: int, code: str) -> bool:
    mfa = await mfa_repo.get_secret(user_id)
    if not mfa or not mfa.enabled:
        return False
    
    # Decrypt secret
    secret = decrypt_aes_gcm(mfa.secret, settings.ENCRYPTION_KEY)
    
    totp = pyotp.TOTP(secret)
    
    # Check with ±1 window tolerance
    if not totp.verify(code, valid_window=1):
        return False
    
    # Anti-replay: check last used code time
    # TOTP changes every 30s, so store timestamp of last valid code
    current_window = int(datetime.utcnow().timestamp() // 30)
    if mfa.last_totp_window and mfa.last_totp_window >= current_window:
        # Same code already used in this window
        return False
    
    # Update last used
    await mfa_repo.update_last_used(user_id, current_window)
    
    return True
```

### 5.2 Recovery Codes

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **8-10 codes générés** | 🟠 HIGH | Balance sécurité/praticité |
| [x] | **Haute entropie** | 🔴 CRITICAL | 8+ chars alphanumériques |
| [x] | **Hashés en DB** | 🔴 CRITICAL | bcrypt cost 10 |
| [x] | **Usage unique** | 🔴 CRITICAL | Marquer `used_at` après utilisation |
| [x] | **Afficher une seule fois** | 🔴 CRITICAL | User doit les sauvegarder |
| [x] | **Régénération invalide anciens** | 🔴 CRITICAL | Delete all avant insert new |
| [x] | **Rate limit strict** | 🔴 CRITICAL | Max 3/min |
| [~] | **Alert on use** | 🟠 HIGH | Notifier user par email - Infrastructure SMTP requise |

### 5.3 Flow MFA 2 étapes

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **MFA Session Token séparé** | 🔴 CRITICAL | Type "mfa_session", pas d'accès API |
| [x] | **Expiration 5 minutes** | 🔴 CRITICAL | Juste le temps de taper |
| [ ] | **Ne pas révéler MFA status** | 🟠 HIGH | Même response time |
| [x] | **Forcer MFA après compromission** | 🟠 HIGH | User.mfa_required + force_mfa_required() |

---

## 6. Sécurité - Sessions

### 6.1 Gestion

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **UUID v4 pour session ID** | 🔴 CRITICAL | Non prédictible |
| [x] | **Tracking IP + User-Agent** | 🟠 HIGH | Détecter hijacking |
| [x] | **last_seen_at update** | 🟠 HIGH | Timeout inactivité |
| [x] | **Revocation immédiate** | 🔴 CRITICAL | revoked_at = NOW() |
| [x] | **Cascade sur tokens** | 🔴 CRITICAL | Refresh tokens invalidés |
| [x] | **List sessions endpoint** | 🟠 HIGH | User peut voir ses sessions |
| [x] | **Revoke other sessions** | 🟠 HIGH | Sécurité post-compromission |
| [ ] | **Max sessions par user** | 🟡 MEDIUM | Ex: 5 max, révoquer plus ancienne |

### 6.2 Validation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Check sur chaque requête** | 🔴 CRITICAL | Via access token session_id |
| [x] | **Ou check sur refresh only** | 🟠 HIGH | Moins strict, meilleure perf |
| [ ] | **IP change detection** | 🟡 MEDIUM | Alerter ou invalider |
| [ ] | **Device fingerprint** | 🟡 MEDIUM | User-Agent + autres signaux |

---

## 7. Sécurité - API Keys

### 7.1 Génération

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Préfixe identifiable** | 🟠 HIGH | Ex: `sk_live_`, `sk_test_` |
| [x] | **Haute entropie** | 🔴 CRITICAL | `secrets.token_urlsafe(32)` |
| [x] | **Afficher une seule fois** | 🔴 CRITICAL | Pas de "show key" ensuite |
| [x] | **Hasher en DB** | 🔴 CRITICAL | SHA-256 ou Argon2 |
| [x] | **Scopes limités** | 🟠 HIGH | Least privilege principle - APIKeyScopes + has_scope() |
| [x] | **Expiration optionnelle** | 🟠 HIGH | Recommander 1 an max |

### 7.2 Validation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Constant-time compare** | 🔴 CRITICAL | Via hash comparison |
| [x] | **Check revoked_at** | 🔴 CRITICAL | Key peut être révoquée |
| [x] | **Check expires_at** | 🔴 CRITICAL | Key peut expirer |
| [x] | **Tenant isolation** | 🔴 CRITICAL | Key liée à un tenant |
| [x] | **Log usage** | 🟠 HIGH | Table `api_key_usage` + APIKeyUsageRepository |
| [x] | **Update last_used_at** | 🟠 HIGH | Détecter keys inutilisées |
| [x] | **Rate limit par key** | 🟠 HIGH | check_rate_limit() + enforce_rate_limit() |

---

## 8. Sécurité - Headers HTTP

### 8.1 Response Headers

| # | Header | Valeur | Priorité |
|---|--------|--------|----------|
| [x] | `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | 🔴 CRITICAL |
| [x] | `X-Content-Type-Options` | `nosniff` | 🔴 CRITICAL |
| [x] | `X-Frame-Options` | `DENY` | 🔴 CRITICAL |
| [x] | `Content-Security-Policy` | Selon app | 🟠 HIGH |
| [x] | `X-XSS-Protection` | `1; mode=block` | 🟡 MEDIUM (deprecated) |
| [x] | `Referrer-Policy` | `strict-origin-when-cross-origin` | 🟡 MEDIUM |
| [x] | `Permissions-Policy` | Selon besoins | 🟡 MEDIUM |
| [x] | `Cache-Control` | `no-store` pour auth endpoints | 🟠 HIGH |

```python
# ✅ Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # No cache for auth endpoints
        if "/auth/" in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        
        return response
```

### 8.2 CORS

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Whitelist explicite** | 🔴 CRITICAL | Jamais `*` en prod avec credentials |
| [x] | **Origins depuis config** | 🟠 HIGH | Pas hardcodé |
| [x] | **Credentials=true si cookies** | 🟠 HIGH | Sinon cookies ignorés |
| [ ] | **Preflight cache** | 🟡 MEDIUM | `max_age=3600` |

```python
# ✅ CORS configuration
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["https://app.example.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    max_age=3600,
)
```

---

## 9. Sécurité - Input Validation

### 9.1 Pydantic Schemas

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **extra = "forbid"** | 🔴 CRITICAL | Rejeter champs inconnus |
| [x] | **Types stricts** | 🔴 CRITICAL | `StrictStr`, `StrictInt` si nécessaire |
| [x] | **Longueurs max** | 🔴 CRITICAL | `max_length` sur tous les strings |
| [x] | **Regex validation** | 🟠 HIGH | Emails, phones, etc. |
| [x] | **Enum pour valeurs fixes** | 🟠 HIGH | Pas de strings libres pour status, types |
| [x] | **Validators custom** | 🟠 HIGH | Logique métier dans validators |

```python
# ✅ Strict schema example
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.USER
    
    class Config:
        extra = "forbid"  # Reject unknown fields
        str_strip_whitespace = True  # Auto-strip
    
    @validator("name")
    def validate_name(cls, v):
        if not v.replace(" ", "").isalpha():
            raise ValueError("Name must contain only letters")
        return v
```

### 9.2 SQL Injection Prevention

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Parameterized queries only** | 🔴 CRITICAL | Jamais de f-strings avec user input |
| [x] | **ORM par défaut** | 🔴 CRITICAL | SQLAlchemy, Tortoise, etc. |
| [x] | **Audit raw SQL** | 🔴 CRITICAL | Review toute requête raw |
| [x] | **Escape identifiers** | 🔴 CRITICAL | Si dynamic column names |

```python
# ❌ JAMAIS
query = f"SELECT * FROM users WHERE email = '{email}'"

# ✅ Toujours
query = "SELECT * FROM users WHERE email = :email"
result = await db.execute(query, {"email": email})

# ✅ Avec SQLAlchemy ORM
user = await session.execute(
    select(User).where(User.email == email)
)
```

### 9.3 Path Traversal Prevention

> ℹ️ **Note**: Pas de file upload dans l'application actuellement. Items à implémenter si feature ajoutée.

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [N/A] | **Whitelist extensions** | 🔴 CRITICAL | Si file upload - pas de file upload actuellement |
| [N/A] | **Sanitize filenames** | 🔴 CRITICAL | Supprimer `../`, `..\\` - pas de file upload |
| [N/A] | **UUID pour stockage** | 🟠 HIGH | Renommer fichiers uploadés - pas de file upload |
| [N/A] | **Vérifier path final** | 🔴 CRITICAL | `os.path.realpath()` - pas de file upload |

---

## 10. Architecture - Structure projet

### 10.1 Layout recommandé

```
app/
├── __init__.py
├── main.py                    # FastAPI app factory
├── core/
│   ├── __init__.py
│   ├── config.py              # Settings (pydantic-settings)
│   ├── security.py            # JWT, hashing utilities
│   ├── dependencies.py        # FastAPI dependencies
│   ├── exceptions.py          # Custom exceptions
│   └── constants.py           # Enums, constantes
├── middleware/
│   ├── __init__.py
│   ├── request_id.py          # X-Request-ID
│   ├── tenant.py              # X-Tenant-ID extraction
│   ├── rate_limit.py          # Rate limiting
│   ├── timing.py              # Response time logging
│   └── security_headers.py    # Security headers
├── api/
│   ├── __init__.py
│   ├── deps.py                # Shared dependencies
│   └── v1/
│       ├── __init__.py
│       ├── router.py          # Aggregated router
│       ├── auth.py
│       ├── users.py
│       ├── sessions.py
│       ├── mfa.py
│       └── api_keys.py
├── services/                  # Business logic
│   ├── __init__.py
│   ├── auth_service.py
│   ├── user_service.py
│   ├── session_service.py
│   ├── mfa_service.py
│   ├── token_service.py
│   └── audit_service.py
├── repositories/              # Data access
│   ├── __init__.py
│   ├── base.py                # Base repository
│   ├── user_repo.py
│   ├── session_repo.py
│   ├── token_repo.py
│   └── audit_repo.py
├── models/                    # SQLAlchemy models
│   ├── __init__.py
│   ├── base.py
│   ├── user.py
│   ├── session.py
│   └── ...
├── schemas/                   # Pydantic schemas
│   ├── __init__.py
│   ├── auth.py
│   ├── user.py
│   └── ...
├── db/
│   ├── __init__.py
│   ├── session.py             # DB session factory
│   └── migrations/            # Alembic
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── e2e/
```

### 10.2 Checklist structure

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Séparation claire des couches** | 🔴 CRITICAL | API → Service → Repository → DB |
| [x] | **Pas de logique dans routers** | 🔴 CRITICAL | Routers = thin, délèguent aux services |
| [x] | **Services injectables** | 🟠 HIGH | Facilite les tests |
| [x] | **Config centralisée** | 🔴 CRITICAL | Un seul endroit pour settings |
| [x] | **Exceptions custom** | 🟠 HIGH | Pas de HTTPException dans services |
| [x] | **Schemas séparés** | 🟠 HIGH | Request ≠ Response ≠ DB model |

---

## 11. Architecture - Middleware Stack

### 11.1 Ordre des middlewares

L'ordre est **CRITIQUE**. Dernier ajouté = premier exécuté.

```python
# ✅ Ordre correct (lecture de bas en haut pour l'exécution)
app = FastAPI()

# 7. CORS (doit être premier pour preflight)
app.add_middleware(CORSMiddleware, ...)

# 6. Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# 5. Rate Limiting (avant auth pour protéger)
app.add_middleware(RateLimitMiddleware, ...)

# 4. Tenant Extraction
app.add_middleware(TenantMiddleware)

# 3. Request ID (pour traçabilité)
app.add_middleware(RequestIDMiddleware)

# 2. Timing (pour metrics)
app.add_middleware(TimingMiddleware)

# 1. Exception Handler (catch-all)
app.add_middleware(ExceptionMiddleware)
```

### 11.2 Checklist middlewares

| # | Middleware | Priorité | Responsabilité |
|---|------------|----------|----------------|
| [x] | **RequestIDMiddleware** | 🔴 CRITICAL | Génère/propage X-Request-ID |
| [x] | **TenantMiddleware** | 🔴 CRITICAL | X-Tenant-ID → request.state |
| [x] | **RateLimitMiddleware** | 🔴 CRITICAL | Anti-abus global |
| [x] | **SecurityHeadersMiddleware** | 🔴 CRITICAL | HSTS, X-Frame-Options, etc. |
| [x] | **TimingMiddleware** | 🟠 HIGH | Log response time |
| [x] | **ExceptionMiddleware** | 🔴 CRITICAL | Catch-all, format erreurs |
| [x] | **CORSMiddleware** | 🔴 CRITICAL | Si cross-origin |
| [x] | **GZipMiddleware** | 🟡 MEDIUM | Compression responses |

```python
# ✅ Request ID middleware
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Get from header or generate
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Add to logging context
        # structlog.contextvars.bind_contextvars(request_id=request_id)
        
        response = await call_next(request)
        
        # Echo back in response
        response.headers["X-Request-ID"] = request_id
        
        return response
```

---

## 12. Architecture - Dependency Injection

### 12.1 Dependencies standard

```python
# ✅ app/core/dependencies.py
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.core.security import decode_access_token
from app.models import User
from app.repositories import UserRepository, TokenRepository

# Type aliases pour clarté
security = HTTPBearer()

async def get_db() -> AsyncSession:
    async with get_async_session() as session:
        yield session

DB = Annotated[AsyncSession, Depends(get_db)]

async def get_tenant_id(request: Request) -> int:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(400, "X-Tenant-ID header required")
    try:
        return int(tenant_id)
    except ValueError:
        raise HTTPException(400, "Invalid X-Tenant-ID")

TenantID = Annotated[int, Depends(get_tenant_id)]

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: DB,
    tenant_id: TenantID,
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(401, "Invalid token")
    
    # Type check
    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")
    
    # Extract and validate user_id
    try:
        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Invalid token subject")
    
    # Check blacklist
    jti = payload.get("jti")
    if jti:
        token_repo = TokenRepository(db)
        if await token_repo.is_revoked(jti):
            raise HTTPException(401, "Token revoked")
    
    # Check session if present
    session_id = payload.get("session_id")
    if session_id:
        session_repo = SessionRepository(db)
        session = await session_repo.get(session_id)
        if not session or session.revoked_at:
            raise HTTPException(401, "Session expired")
    
    # Get user
    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)
    if not user:
        raise HTTPException(401, "User not found")
    
    # Cross-tenant check
    if payload.get("tenant_id") != user.tenant_id:
        raise HTTPException(401, "Tenant mismatch")
    
    # Verify request tenant matches token tenant
    if tenant_id != user.tenant_id:
        raise HTTPException(403, "Tenant access denied")
    
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]

async def get_current_user_optional(
    request: Request,
    db: DB,
) -> Optional[User]:
    """For endpoints that work with or without auth"""
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    try:
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=auth.replace("Bearer ", "")
        )
        return await get_current_user(credentials, db, ...)
    except HTTPException:
        return None

OptionalUser = Annotated[Optional[User], Depends(get_current_user_optional)]
```

### 12.2 Checklist DI

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [ ] | **Type hints avec Annotated** | 🟠 HIGH | Clarté et réutilisabilité |
| [x] | **Pas de dépendance circulaire** | 🔴 CRITICAL | Vérifié via scripts/check_imports.py |
| [x] | **Dependencies async** | 🔴 CRITICAL | Pas de sync dans async chain |
| [ ] | **Scope correct** | 🟠 HIGH | Request scope par défaut |
| [ ] | **Cache par requête** | 🟡 MEDIUM | `use_cache=True` si heavy |
| [ ] | **Error messages clairs** | 🟠 HIGH | Pas de 500 pour input invalide |

---

## 13. Architecture - Service Layer

### 13.1 Responsabilités

| Couche | Responsabilité | Exemple |
|--------|----------------|---------|
| **Router** | HTTP handling, validation, response | Parse request, call service, return JSON |
| **Service** | Business logic, orchestration | Validate rules, coordinate repos, emit events |
| **Repository** | Data access | CRUD operations, queries |

### 13.2 Pattern Service

```python
# ✅ app/services/auth_service.py
from typing import Optional
from app.repositories import UserRepository, SessionRepository, TokenRepository
from app.schemas.auth import LoginResponse, TokenPair
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.exceptions import InvalidCredentials, AccountLocked, MFARequired

class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        token_repo: TokenRepository,
        audit_service: "AuditService",
        mfa_service: "MFAService",
    ):
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.token_repo = token_repo
        self.audit = audit_service
        self.mfa = mfa_service
    
    async def login(
        self,
        email: str,
        password: str,
        ip: str,
        user_agent: str,
    ) -> LoginResponse:
        # Normalize
        email = email.lower().strip()
        
        # Get user (timing-safe)
        user = await self.user_repo.get_by_email(email)
        hash_to_check = user.password_hash if user else DUMMY_HASH
        
        password_valid = verify_password(password, hash_to_check)
        
        if not user or not password_valid:
            await self.audit.log_failed_login(email, ip)
            raise InvalidCredentials()
        
        # Check account status
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise AccountLocked(until=user.locked_until)
        
        # Check MFA
        if await self.mfa.is_enabled(user.id):
            mfa_token = self.mfa.create_session_token(user.id, user.tenant_id)
            return LoginResponse(
                mfa_required=True,
                mfa_session_token=mfa_token,
            )
        
        # Create session
        session = await self.session_repo.create(
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip=ip,
            user_agent=user_agent,
        )
        
        # Generate tokens
        access = create_access_token(user.id, user.tenant_id, session.id)
        refresh = create_refresh_token(session.id)
        
        # Store refresh token
        await self.token_repo.create_refresh_token(
            jti=refresh.jti,
            session_id=session.id,
            token_hash=refresh.hash,
            expires_at=refresh.expires_at,
        )
        
        # Audit
        await self.audit.log_successful_login(user.id, session.id, ip)
        
        return LoginResponse(
            access_token=access.token,
            refresh_token=refresh.token,
            token_type="bearer",
            expires_in=access.expires_in,
        )
```

### 13.3 Injection du service

```python
# ✅ Dependency pour injecter le service
from functools import lru_cache

def get_auth_service(db: DB) -> AuthService:
    return AuthService(
        user_repo=UserRepository(db),
        session_repo=SessionRepository(db),
        token_repo=TokenRepository(db),
        audit_service=AuditService(db),
        mfa_service=MFAService(db),
    )

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# ✅ Router utilise le service
@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    data: LoginRequest,
    auth_service: AuthServiceDep,
):
    return await auth_service.login(
        email=data.email,
        password=data.password,
        ip=request.client.host,
        user_agent=request.headers.get("User-Agent", ""),
    )
```

### 13.4 Checklist Service Layer

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Pas de HTTPException dans services** | 🔴 CRITICAL | Lever des exceptions custom |
| [x] | **Pas d'accès Request dans services** | 🔴 CRITICAL | Passer les valeurs en params |
| [x] | **Transactions explicites** | 🔴 CRITICAL | Service contrôle les boundaries |
| [x] | **Services testables** | 🟠 HIGH | Injection des dépendances |
| [x] | **Single responsibility** | 🟠 HIGH | Un service = un domaine |
| [x] | **Audit dans le service** | 🟠 HIGH | Pas dans le router |

---

## 14. Architecture - Repository Pattern

### 14.1 Base Repository

```python
# ✅ app/repositories/base.py
from typing import TypeVar, Generic, Optional, List, Type
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model
    
    async def get(self, id: int) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_ids(self, ids: List[int]) -> List[ModelType]:
        result = await self.session.execute(
            select(self.model).where(self.model.id.in_(ids))
        )
        return list(result.scalars().all())
    
    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance
    
    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        await self.session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
        )
        return await self.get(id)
    
    async def delete(self, id: int) -> bool:
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
```

### 14.2 Repository spécialisé

```python
# ✅ app/repositories/user_repo.py
from typing import Optional
from sqlalchemy import select
from app.models import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_by_tenant(
        self,
        tenant_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        result = await self.session.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def email_exists(self, email: str, tenant_id: int) -> bool:
        result = await self.session.execute(
            select(User.id)
            .where(User.email == email.lower())
            .where(User.tenant_id == tenant_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
```

### 14.3 Checklist Repository

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Pas de logique métier** | 🔴 CRITICAL | Que du CRUD et queries |
| [x] | **Pas de commit** | 🔴 CRITICAL | Service contrôle la transaction |
| [x] | **Tenant isolation** | 🔴 CRITICAL | Toujours filtrer par tenant_id |
| [x] | **Return models, pas dicts** | 🟠 HIGH | Type safety |
| [x] | **Pagination par défaut** | 🟠 HIGH | Éviter les SELECT sans LIMIT |
| [x] | **Async everywhere** | 🔴 CRITICAL | Pas de sync DB calls |

---

## 15. Architecture - Exception Handling

### 15.1 Custom Exceptions

```python
# ✅ app/core/exceptions.py
from typing import Optional, Dict, Any

class AppException(Exception):
    """Base exception for application"""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"
    
    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }

# Auth exceptions
class InvalidCredentials(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"

class TokenExpired(AppException):
    status_code = 401
    error_code = "TOKEN_EXPIRED"
    message = "Token has expired"

class TokenRevoked(AppException):
    status_code = 401
    error_code = "TOKEN_REVOKED"
    message = "Token has been revoked"

class SessionExpired(AppException):
    status_code = 401
    error_code = "SESSION_EXPIRED"
    message = "Session has expired"

class AccountLocked(AppException):
    status_code = 403
    error_code = "ACCOUNT_LOCKED"
    message = "Account is temporarily locked"
    
    def __init__(self, until: datetime):
        super().__init__(details={"locked_until": until.isoformat()})

class MFARequired(AppException):
    status_code = 403
    error_code = "MFA_REQUIRED"
    message = "Multi-factor authentication required"

class MFAInvalid(AppException):
    status_code = 401
    error_code = "MFA_INVALID"
    message = "Invalid MFA code"

# Permission exceptions
class PermissionDenied(AppException):
    status_code = 403
    error_code = "PERMISSION_DENIED"
    message = "You don't have permission to perform this action"

class TenantMismatch(AppException):
    status_code = 403
    error_code = "TENANT_MISMATCH"
    message = "Tenant access denied"

# Resource exceptions
class NotFound(AppException):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"

class AlreadyExists(AppException):
    status_code = 409
    error_code = "ALREADY_EXISTS"
    message = "Resource already exists"

# Validation exceptions
class ValidationError(AppException):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"

# Rate limiting
class RateLimitExceeded(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many requests"
```

### 15.2 Global Exception Handler

```python
# ✅ app/core/exception_handlers.py
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import AppException
import structlog

logger = structlog.get_logger()

def setup_exception_handlers(app: FastAPI):
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            "Application error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
            },
        )
    
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        
        logger.exception(
            "Unhandled exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"request_id": request_id},
            },
        )
```

### 15.3 Checklist Exceptions

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Exceptions custom typées** | 🔴 CRITICAL | Pas de `raise Exception("...")` |
| [x] | **Error codes constants** | 🔴 CRITICAL | Pour parsing côté client |
| [x] | **Messages user-friendly** | 🟠 HIGH | Pas de stack traces en prod |
| [x] | **Request ID dans les 500** | 🔴 CRITICAL | Pour debugging |
| [x] | **Log toutes les erreurs** | 🔴 CRITICAL | Structured logging |
| [x] | **Ne pas leak d'infos sensibles** | 🔴 CRITICAL | Pas de SQL, paths, etc. |
| [x] | **Validation errors détaillées** | 🟠 HIGH | Field-level feedback |

---

## 16. Multi-tenant

### 16.1 Isolation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **tenant_id sur toutes les tables** | 🔴 CRITICAL | Sauf tables globales (permissions) |
| [x] | **Validation header X-Tenant-ID** | 🔴 CRITICAL | Middleware obligatoire |
| [x] | **RLS PostgreSQL** | 🔴 CRITICAL | Defense in depth |
| [x] | **Cross-tenant check dans get_current_user** | 🔴 CRITICAL | Token.tenant == User.tenant |
| [x] | **Tenant dans tous les logs** | 🟠 HIGH | Pour audit |
| [x] | **Indexes avec tenant_id** | 🟠 HIGH | Perf queries |

### 16.2 Row Level Security

```sql
-- ✅ RLS setup
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
-- ... toutes les tables tenant-scoped

-- Policy de base
CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.current_tenant_id')::bigint);

-- Pour les admins système (bypass)
CREATE POLICY admin_bypass ON users
    USING (current_setting('app.is_system_admin', true)::boolean = true);
```

```python
# ✅ Set tenant context for RLS
async def set_tenant_context(session: AsyncSession, tenant_id: int):
    await session.execute(
        text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'")
    )
```

### 16.3 Tenant Middleware

```python
# ✅ app/middleware/tenant.py
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import HTTPException

class TenantMiddleware(BaseHTTPMiddleware):
    # Endpoints qui ne requièrent pas de tenant
    TENANT_EXEMPT = {
        "/health",
        "/ready",
        "/docs",
        "/openapi.json",
    }
    
    async def dispatch(self, request, call_next):
        if request.url.path in self.TENANT_EXEMPT:
            return await call_next(request)
        
        tenant_header = request.headers.get("X-Tenant-ID")
        
        if not tenant_header:
            return JSONResponse(
                status_code=400,
                content={"error": "MISSING_TENANT", "message": "X-Tenant-ID header required"}
            )
        
        try:
            tenant_id = int(tenant_header)
            if tenant_id <= 0:
                raise ValueError()
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": "INVALID_TENANT", "message": "Invalid X-Tenant-ID"}
            )
        
        request.state.tenant_id = tenant_id
        
        return await call_next(request)
```

---

## 17. Base de données - Schema

### 17.1 Tables obligatoires

| # | Table | Priorité | Rôle |
|---|-------|----------|------|
| [x] | **tenants** | 🔴 CRITICAL | Organisations |
| [x] | **users** | 🔴 CRITICAL | Utilisateurs |
| [x] | **sessions** | 🔴 CRITICAL | Sessions actives |
| [x] | **refresh_tokens** | 🔴 CRITICAL | Tokens de refresh |
| [x] | **revoked_tokens** | 🔴 CRITICAL | Blacklist JWT |
| [x] | **login_attempts** | 🔴 CRITICAL | Anti-bruteforce |
| [x] | **audit_log** | 🔴 CRITICAL | Traçabilité |
| [x] | **mfa_secrets** | 🟠 HIGH | TOTP secrets |
| [x] | **mfa_recovery_codes** | 🟠 HIGH | Recovery codes |
| [x] | **verification_tokens** | 🟠 HIGH | Email verify, password reset |
| [x] | **api_keys** | 🟠 HIGH | M2M auth |
| [x] | **roles** | 🟠 HIGH | RBAC |
| [x] | **permissions** | 🟠 HIGH | RBAC |
| [x] | **user_roles** | 🟠 HIGH | RBAC |

### 17.2 Conventions

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **snake_case pour colonnes** | 🟠 HIGH | Consistance |
| [x] | **Pluriel pour tables** | 🟡 MEDIUM | users, sessions, tokens |
| [x] | **id BIGSERIAL ou UUID** | 🟠 HIGH | Selon le cas d'usage |
| [x] | **created_at sur toutes les tables** | 🔴 CRITICAL | Audit |
| [x] | **updated_at où pertinent** | 🟠 HIGH | Tracking modifications |
| [x] | **Soft delete avec deleted_at** | 🟠 HIGH | Ou revoked_at selon contexte |
| [x] | **TIMESTAMPTZ pas TIMESTAMP** | 🔴 CRITICAL | Timezone-aware |
| [x] | **NOT NULL par défaut** | 🟠 HIGH | Expliciter les optionnels |
| [x] | **DEFAULT values** | 🟠 HIGH | NOW(), false, etc. |

### 17.3 Contraintes

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **PK sur toutes les tables** | 🔴 CRITICAL | Évident mais à vérifier |
| [x] | **FK avec ON DELETE** | 🔴 CRITICAL | CASCADE ou RESTRICT explicite |
| [x] | **UNIQUE constraints** | 🔴 CRITICAL | (tenant_id, email), etc. |
| [x] | **CHECK constraints** | 🟠 HIGH | Valider les enums en DB |
| [x] | **Indexes explicites** | 🔴 CRITICAL | Pas juste implicites des FK |

---

## 18. Base de données - Performance

### 18.1 Index Strategy

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Index sur FK** | 🔴 CRITICAL | PostgreSQL ne les crée pas auto |
| [x] | **Index composites** | 🟠 HIGH | (tenant_id, created_at DESC) |
| [x] | **Index partiels** | 🟠 HIGH | WHERE revoked_at IS NULL |
| [x] | **EXPLAIN ANALYZE** | 🔴 CRITICAL | `app/core/query_profiler.py` - explain_analyze() + N+1 detection |
| [ ] | **Pas d'index inutilisés** | 🟡 MEDIUM | Cleanup régulier |
| [ ] | **Index covering** | 🟡 MEDIUM | INCLUDE pour éviter heap fetch |

```sql
-- ✅ Exemples d'index optimisés

-- Sessions actives par user (query fréquente)
CREATE INDEX sessions_user_active_idx 
    ON sessions (user_id, created_at DESC)
    WHERE revoked_at IS NULL;

-- Lookup refresh token par hash
CREATE INDEX refresh_tokens_hash_idx 
    ON refresh_tokens (token_hash)
    WHERE used_at IS NULL;

-- Audit log par tenant + date (reporting)
CREATE INDEX audit_log_tenant_time_idx 
    ON audit_log (tenant_id, created_at DESC);

-- Login attempts pour rate limiting
CREATE INDEX login_attempts_identifier_recent_idx 
    ON login_attempts (identifier, attempted_at DESC);

-- API keys lookup
CREATE INDEX api_keys_hash_active_idx 
    ON api_keys (key_hash)
    WHERE revoked_at IS NULL AND (expires_at IS NULL OR expires_at > NOW());
```

### 18.2 Connection Pooling

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Pool size configuré** | 🔴 CRITICAL | Selon workers * connections |
| [x] | **Max overflow** | 🟠 HIGH | Buffer pour pics |
| [x] | **Connection timeout** | 🟠 HIGH | Fail fast |
| [x] | **Recycle connections** | 🟠 HIGH | Éviter stale connections |
| [N/A] | **PgBouncer en prod** | 🟠 HIGH | Infrastructure-specific - à configurer selon environnement |

```python
# ✅ SQLAlchemy async pool config
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,           # Base connections
    max_overflow=10,       # Extra connections on demand
    pool_timeout=30,       # Wait for available connection
    pool_recycle=1800,     # Recycle after 30 minutes
    pool_pre_ping=True,    # Verify connection before use
    echo=settings.DEBUG,   # SQL logging
)

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### 18.3 Query Optimization

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Pagination obligatoire** | 🔴 CRITICAL | PaginatedResult dans BaseRepository |
| [ ] | **Éviter SELECT *** | 🟠 HIGH | Sélectionner les colonnes nécessaires |
| [x] | **N+1 detection** | 🔴 CRITICAL | QueryProfiler avec détection N+1 |
| [ ] | **Batch operations** | 🟠 HIGH | Bulk insert/update |
| [ ] | **Read replicas** | 🟡 MEDIUM | Pour requêtes heavy read |

---

## 19. Base de données - Maintenance

### 19.1 Cleanup automatique

| # | Table | Rétention | Fréquence |
|---|-------|-----------|-----------|
| [x] | **revoked_tokens** | expires_at passé | Daily |
| [x] | **refresh_tokens** | expires_at passé | Daily |
| [x] | **login_attempts** | 30 jours | Daily |
| [ ] | **audit_log** | 12 mois (ou selon compliance) | Weekly |
| [x] | **password_reset_tokens** | expires_at passé | Daily |
| [x] | **sessions** | revoked > 90 jours | Weekly |

```sql
-- ✅ Cleanup script (à scheduler)

-- Revoked tokens expirés
DELETE FROM revoked_tokens WHERE expires_at < NOW();

-- Refresh tokens expirés
DELETE FROM refresh_tokens WHERE expires_at < NOW();

-- Login attempts vieux
DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '30 days';

-- Sessions révoquées anciennes
DELETE FROM sessions WHERE revoked_at < NOW() - INTERVAL '90 days';

-- Verification tokens expirés
DELETE FROM verification_tokens WHERE expires_at < NOW();
```

### 19.2 Vacuum & Analyze

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **autovacuum activé** | 🔴 CRITICAL | Par défaut sur PostgreSQL |
| [x] | **Tune autovacuum** | 🟠 HIGH | db/sql/01_autovacuum.sql |
| [ ] | **VACUUM ANALYZE manuel** | 🟠 HIGH | Après gros DELETE/UPDATE |
| [ ] | **pg_repack** | 🟡 MEDIUM | Pour tables bloated |

### 19.3 Backups

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **pg_dump quotidien** | 🔴 CRITICAL | Backup logique |
| [x] | **WAL archiving** | 🔴 CRITICAL | Point-in-time recovery |
| [x] | **Test restore régulier** | 🔴 CRITICAL | Un backup non testé n'existe pas |
| [x] | **Offsite storage** | 🔴 CRITICAL | S3, GCS, autre région |
| [x] | **Encryption at rest** | 🟠 HIGH | Backups chiffrés |
| [x] | **Retention policy** | 🟠 HIGH | 7 daily, 4 weekly, 12 monthly |

---

## 20. Observabilité - Logging

### 20.1 Structured Logging

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Format JSON** | 🔴 CRITICAL | Parsable par outils (ELK, Datadog) |
| [x] | **structlog ou python-json-logger** | 🟠 HIGH | Librairie éprouvée |
| [x] | **Levels cohérents** | 🟠 HIGH | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| [x] | **Request ID dans tous les logs** | 🔴 CRITICAL | Corrélation |
| [x] | **Tenant ID dans tous les logs** | 🔴 CRITICAL | Multi-tenant debug |
| [x] | **User ID (quand auth)** | 🟠 HIGH | `logging.py` - ContextVar user_id dans logs |
| [x] | **Timestamps ISO 8601** | 🟠 HIGH | Tous les modèles utilisent `.isoformat()` |

```python
# ✅ Configuration structlog
import structlog
from structlog.contextvars import merge_contextvars

structlog.configure(
    processors=[
        merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info(
    "User logged in",
    user_id=user.id,
    tenant_id=user.tenant_id,
    ip=request.client.host,
)
```

### 20.2 Que logger

| Event | Level | Champs obligatoires |
|-------|-------|---------------------|
| Request start | DEBUG | method, path, request_id |
| Request end | INFO | method, path, status, duration_ms, request_id |
| Auth success | INFO | user_id, tenant_id, ip |
| Auth failure | WARNING | identifier, ip, reason |
| Permission denied | WARNING | user_id, action, resource |
| Validation error | INFO | path, errors |
| Business error | WARNING | error_code, message |
| System error | ERROR | exception, stack_trace, request_id |
| Rate limit hit | WARNING | ip, endpoint, limit |
| MFA events | INFO | user_id, event_type |
| Session events | INFO | session_id, event_type |

### 20.3 Ce qu'il ne faut PAS logger

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Pas de mots de passe** | 🔴 CRITICAL | Jamais, même en debug |
| [x] | **Pas de tokens complets** | 🔴 CRITICAL | Max 8 premiers chars |
| [x] | **Pas de secrets** | 🔴 CRITICAL | API keys, encryption keys |
| [x] | **Pas de PII excessive** | 🟠 HIGH | Email OK, SSN jamais |
| [x] | **Pas de card numbers** | 🔴 CRITICAL | PCI compliance |
| [x] | **Pas de request body sensible** | 🟠 HIGH | Filter login payloads |

```python
# ✅ Sanitize sensitive data
SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "authorization"}

def sanitize_dict(data: dict) -> dict:
    result = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        else:
            result[key] = value
    return result
```

---

## 21. Observabilité - Metrics

### 21.1 Metrics essentielles

| # | Metric | Type | Labels |
|---|--------|------|--------|
| [x] | **http_requests_total** | Counter | method, path, status |
| [x] | **http_request_duration_seconds** | Histogram | method, path |
| [x] | **auth_login_total** | Counter | status (success/failure), tenant_id |
| [x] | **auth_mfa_verify_total** | Counter | status, tenant_id |
| [x] | **active_sessions** | Gauge | tenant_id |
| [x] | **rate_limit_hits_total** | Counter | endpoint, tenant_id |
| [x] | **db_query_duration_seconds** | Histogram | query_type |
| [ ] | **db_pool_connections** | Gauge | status (active/idle) |

### 21.2 Implementation Prometheus

```python
# ✅ Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from starlette.responses import Response

# Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

LOGIN_ATTEMPTS = Counter(
    "auth_login_total",
    "Login attempts",
    ["status", "tenant_id"]
)

ACTIVE_SESSIONS = Gauge(
    "active_sessions",
    "Currently active sessions",
    ["tenant_id"]
)

# Endpoint
@app.get("/metrics")
async def metrics():
    return Response(
        generate_latest(),
        media_type="text/plain"
    )
```

### 21.3 Checklist Metrics

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **RED metrics** | 🔴 CRITICAL | Rate, Errors, Duration |
| [x] | **USE metrics** | 🟠 HIGH | Utilization, Saturation, Errors |
| [x] | **Business metrics** | 🟠 HIGH | Logins, signups, etc. |
| [x] | **Cardinality contrôlée** | 🔴 CRITICAL | Pas de user_id dans labels |
| [N/A] | **Dashboards Grafana** | 🟠 HIGH | Infrastructure/Observability - à configurer séparément |
| [x] | **Alerting rules** | 🔴 CRITICAL | Prometheus Alertmanager |

---

## 22. Observabilité - Tracing

### 22.1 Distributed Tracing

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [N/A] | **OpenTelemetry SDK** | 🟠 HIGH | Infrastructure/Observability - à intégrer selon besoins |
| [x] | **Trace ID propagation** | 🔴 CRITICAL | X-Request-ID + logging context |
| [ ] | **Span per DB query** | 🟠 HIGH | Identifier slow queries |
| [ ] | **Span per HTTP call** | 🟠 HIGH | External services |
| [ ] | **Sampling en prod** | 🟠 HIGH | 1% ou head-based |
| [ ] | **Jaeger ou Zipkin** | 🟡 MEDIUM | Backend de traces |

```python
# ✅ OpenTelemetry setup
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Setup
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Auto-instrument
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)

# Manual span
tracer = trace.get_tracer(__name__)

async def some_complex_operation():
    with tracer.start_as_current_span("complex_operation") as span:
        span.set_attribute("user_id", user_id)
        # ... operation
```

---

## 23. Performance

### 23.1 Async Best Practices

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Async DB driver** | 🔴 CRITICAL | asyncpg pour PostgreSQL |
| [x] | **Async HTTP client** | 🔴 CRITICAL | httpx ou aiohttp |
| [x] | **Pas de sync dans async** | 🔴 CRITICAL | Bloque l'event loop |
| [ ] | **asyncio.gather pour parallel** | 🟠 HIGH | Concurrent calls |
| [ ] | **run_in_executor pour CPU-bound** | 🟠 HIGH | Offload blocking |
| [x] | **Timeouts sur external calls** | 🔴 CRITICAL | Pas d'attente infinie |

```python
# ❌ Mauvais - bloque l'event loop
import requests
response = requests.get("https://api.example.com")

# ✅ Bon
import httpx
async with httpx.AsyncClient(timeout=10.0) as client:
    response = await client.get("https://api.example.com")

# ✅ Parallel calls
results = await asyncio.gather(
    service_a.call(),
    service_b.call(),
    service_c.call(),
    return_exceptions=True,
)
```

### 23.2 Caching

> ℹ️ **Note**: Pas de cache applicatif implémenté actuellement. Redis utilisé uniquement pour rate limiting.

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [N/A] | **Redis pour cache partagé** | 🟠 HIGH | Multi-instance - pas de cache applicatif actuellement |
| [N/A] | **TTL appropriés** | 🟠 HIGH | Selon fraîcheur requise - pas de cache |
| [N/A] | **Cache invalidation strategy** | 🔴 CRITICAL | À implémenter si cache ajouté |
| [ ] | **Cache per-request** | 🟠 HIGH | get_current_user |
| [ ] | **Response caching (CDN)** | 🟡 MEDIUM | Pour static content |
| [ ] | **ETag / If-None-Match** | 🟡 MEDIUM | Client-side caching |

```python
# ✅ Cache decorator avec Redis
from functools import wraps
import json
import hashlib

def cached(ttl: int = 60, prefix: str = "cache"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            cache_key = f"{prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            # Try cache
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute
            result = await func(*args, **kwargs)
            
            # Store
            await redis.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

@cached(ttl=300, prefix="user")
async def get_user_permissions(user_id: int) -> list:
    # Heavy query
    ...
```

### 23.3 Autres optimisations

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Compression gzip** | 🟠 HIGH | GZipMiddleware (min_size=1000) |
| [ ] | **Response streaming** | 🟡 MEDIUM | Pour large responses |
| [ ] | **Lazy loading** | 🟠 HIGH | Éviter eager loading inutile |
| [ ] | **Connection reuse** | 🟠 HIGH | Keep-alive HTTP |
| [ ] | **Batch endpoints** | 🟡 MEDIUM | Réduire round-trips |
| [ ] | **Pagination cursor-based** | 🟠 HIGH | Plus efficace que offset |

---

## 24. Tests

### 24.1 Test Pyramid

| Niveau | Proportion | Focus |
|--------|------------|-------|
| **Unit tests** | 70% | Services, utils, business logic |
| **Integration tests** | 20% | Repositories + DB, external services |
| **E2E tests** | 10% | Full API flows |

### 24.2 Checklist Tests

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **pytest-asyncio** | 🔴 CRITICAL | Pour async tests |
| [x] | **Fixtures réutilisables** | 🟠 HIGH | conftest.py |
| [x] | **DB isolation** | 🔴 CRITICAL | Transaction rollback ou test DB |
| [x] | **Mocks pour external** | 🟠 HIGH | Ne pas appeler vrais services |
| [ ] | **Factory pattern** | 🟠 HIGH | factory_boy pour data |
| [ ] | **Coverage > 80%** | 🟠 HIGH | Avec exclusions raisonnables |
| [x] | **Tests security-specific** | 🔴 CRITICAL | Voir ci-dessous |

### 24.3 Tests de sécurité obligatoires

| # | Test | Description |
|---|------|-------------|
| [x] | **Token expiration** | Rejeter tokens expirés |
| [x] | **Token type mismatch** | Refresh token pas accepté comme access |
| [x] | **Revoked token** | Blacklist respectée |
| [x] | **Session revoked** | Token valide mais session révoquée |
| [x] | **Cross-tenant access** | User tenant A ne peut pas accéder tenant B |
| [x] | **Rate limiting** | 429 après N requests |
| [x] | **Bruteforce protection** | Lock après N échecs |
| [x] | **Invalid JWT signature** | Rejeter tokens modifiés |
| [x] | **SQL injection** | Parameterized queries |
| [x] | **MFA replay** | Code déjà utilisé rejeté |
| [x] | **Password validation** | Règles respectées |

```python
# ✅ Exemple tests sécurité
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token

@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    token = create_access_token(
        user_id=1,
        tenant_id=1,
        expires_delta=timedelta(seconds=-1)  # Already expired
    )
    
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "1"}
    )
    
    assert response.status_code == 401
    assert response.json()["error"] == "TOKEN_EXPIRED"

@pytest.mark.asyncio
async def test_refresh_token_not_valid_as_access(client: AsyncClient):
    refresh_token = create_refresh_token(session_id=uuid4())
    
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh_token.token}", "X-Tenant-ID": "1"}
    )
    
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_cross_tenant_access_denied(client: AsyncClient, user_tenant_1, token_tenant_2):
    # User belongs to tenant 1, token claims tenant 2
    response = await client.get(
        "/api/v1/users/me",
        headers={
            "Authorization": f"Bearer {token_tenant_2}",
            "X-Tenant-ID": "1"  # Mismatch!
        }
    )
    
    assert response.status_code in [401, 403]

@pytest.mark.asyncio
async def test_rate_limit_enforced(client: AsyncClient):
    # Exceed rate limit
    for i in range(10):
        await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "wrong"})
    
    response = await client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "wrong"})
    
    assert response.status_code == 429
```

---

## 25. CI/CD

### 25.1 Pipeline stages

| # | Stage | Priorité | Checks |
|---|-------|----------|--------|
| [x] | **Lint** | 🔴 CRITICAL | ruff, black, isort |
| [ ] | **Type check** | 🟠 HIGH | mypy --strict |
| [x] | **Unit tests** | 🔴 CRITICAL | pytest -m unit |
| [x] | **Integration tests** | 🔴 CRITICAL | pytest -m integration (avec DB) |
| [x] | **Security scan** | 🔴 CRITICAL | bandit, safety |
| [x] | **Dependency audit** | 🟠 HIGH | pip-audit |
| [x] | **Build image** | 🔴 CRITICAL | Docker build |
| [x] | **Image scan** | 🟠 HIGH | Trivy dans `.github/workflows/security.yml` |
| [x] | **Migration test** | 🔴 CRITICAL | alembic upgrade + downgrade |
| [ ] | **Deploy staging** | 🟠 HIGH | Auto-deploy - infrastructure-specific |
| [ ] | **E2E tests** | 🟠 HIGH | Sur staging |
| [ ] | **Deploy prod** | 🔴 CRITICAL | Manuel ou auto - infrastructure-specific |

### 25.2 Pre-commit hooks

```yaml
# ✅ .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: detect-private-key

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]
```

### 25.3 GitHub Actions example

```yaml
# ✅ .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: mypy app --strict

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install bandit safety pip-audit
      - run: bandit -r app
      - run: safety check
      - run: pip-audit

  migration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: alembic upgrade head
      - run: alembic downgrade base
      - run: alembic upgrade head
```

---

## 26. Documentation

### 26.1 API Documentation

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **OpenAPI spec auto** | 🔴 CRITICAL | FastAPI le fait (/openapi.json, /docs) |
| [ ] | **Descriptions sur tous les endpoints** | 🟠 HIGH | docstrings |
| [ ] | **Examples dans schemas** | 🟠 HIGH | `schema_extra` |
| [ ] | **Error responses documentées** | 🟠 HIGH | `responses={}` |
| [ ] | **Auth requirements clairs** | 🟠 HIGH | Security schemes |
| [ ] | **Changelog / versioning** | 🟠 HIGH | /v1, /v2 |

```python
# ✅ Well-documented endpoint
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="Authenticate user",
    description="""
    Authenticate a user with email and password.
    
    Returns JWT tokens for API access.
    If MFA is enabled, returns a temporary MFA session token instead.
    """,
    responses={
        200: {"description": "Login successful or MFA required"},
        401: {"description": "Invalid credentials"},
        403: {"description": "Account locked"},
        429: {"description": "Too many attempts"},
    },
)
async def login(
    request: Request,
    data: LoginRequest,
    auth_service: AuthServiceDep,
):
    """Authenticate user with email/password."""
    ...
```

### 26.2 Documentation interne

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **README principal** | 🔴 CRITICAL | Setup, architecture overview |
| [x] | **README par module** | 🟠 HIGH | Comme dans ta structure |
| [ ] | **ADRs** | 🟠 HIGH | Architecture Decision Records |
| [x] | **Runbook ops** | 🟠 HIGH | Comment debug, restart, etc. (INCIDENT_RESPONSE.md) |
| [x] | **Security policy** | 🔴 CRITICAL | Comment reporter une vulnérabilité (SECURITY.md) |
| [ ] | **Onboarding guide** | 🟡 MEDIUM | Pour nouveaux devs |

---

## 27. Compliance & Audit

### 27.1 Audit Trail

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Log tous les events auth** | 🔴 CRITICAL | Login, logout, password change |
| [x] | **Log les accès données sensibles** | 🔴 CRITICAL | Read PII |
| [x] | **Log les modifications** | 🔴 CRITICAL | Create, update, delete |
| [x] | **Immutable audit log** | 🔴 CRITICAL | Append-only, pas de DELETE |
| [x] | **Timestamps précis** | 🔴 CRITICAL | TIMESTAMPTZ |
| [x] | **IP + User-Agent** | 🟠 HIGH | Context complet |
| [ ] | **Before/After pour updates** | 🟠 HIGH | Diff visible |
| [x] | **Retention 12+ mois** | 🔴 CRITICAL | Selon compliance |

### 27.2 RGPD

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Data inventory** | 🔴 CRITICAL | Quelles données, où, pourquoi |
| [N/A] | **Consent tracking** | 🔴 CRITICAL | Non requis - bases légales: contrat, intérêt légitime, obligation légale |
| [x] | **Right to access** | 🔴 CRITICAL | Export des données user |
| [x] | **Right to deletion** | 🔴 CRITICAL | Hard delete possible |
| [x] | **Data portability** | 🟠 HIGH | Export format standard (JSON) |
| [x] | **Breach notification** | 🔴 CRITICAL | Process en place (72h) |
| [N/A] | **DPA with vendors** | 🔴 CRITICAL | Document légal - pas du code |

### 27.3 Checklist Sécurité générale

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [ ] | **Secrets rotation** | 🟠 HIGH | Process pour changer JWT secret, etc. |
| [x] | **Dependency updates** | 🔴 CRITICAL | .github/dependabot.yml |
| [x] | **Security headers** | 🔴 CRITICAL | Voir section 8 (middleware/security_headers.py) |
| [x] | **TLS 1.3** | 🔴 CRITICAL | HTTPS redirect + HSTS |
| [x] | **Vulnerability scanning** | 🔴 CRITICAL | .github/workflows/security.yml |
| [N/A] | **Pen testing** | 🟠 HIGH | Processus externe - à planifier annuellement |
| [x] | **Incident response plan** | 🔴 CRITICAL | Qui fait quoi en cas de breach (INCIDENT_RESPONSE.md) |

---

## 28. Operations

### 28.1 Health Checks

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **GET /health** | 🔴 CRITICAL | Liveness: app répond |
| [x] | **GET /ready** | 🔴 CRITICAL | Readiness: DB + Redis OK |
| [x] | **Deep health check** | 🟠 HIGH | Tous les dépendances |
| [x] | **No auth required** | 🔴 CRITICAL | Pour load balancer |

```python
# ✅ Health endpoints
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

@app.get("/ready", include_in_schema=False)
async def ready(db: DB, redis: Redis):
    errors = []
    
    # Check DB
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"database: {e}")
    
    # Check Redis
    try:
        await redis.ping()
    except Exception as e:
        errors.append(f"redis: {e}")
    
    if errors:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "errors": errors}
        )
    
    return {"status": "ok"}
```

### 28.2 Graceful Shutdown

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Signal handlers** | 🔴 CRITICAL | SIGTERM, SIGINT |
| [x] | **Drain connections** | 🔴 CRITICAL | Finir requests en cours |
| [x] | **Close DB pool** | 🔴 CRITICAL | Proprement |
| [x] | **Timeout shutdown** | 🟠 HIGH | Force après 30s |
| [N/A] | **K8s preStop hook** | 🟠 HIGH | Si Kubernetes - infrastructure-specific |

```python
# ✅ Graceful shutdown
import signal
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await init_redis()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db_pool()
    await close_redis()
    logger.info("Shutdown complete")

app = FastAPI(lifespan=lifespan)

# For Docker/K8s
def handle_sigterm(signum, frame):
    logger.info("Received SIGTERM")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
```

### 28.3 Configuration Production

| # | Item | Priorité | Détails |
|---|------|----------|---------|
| [x] | **Env vars pour secrets** | 🔴 CRITICAL | validate_secrets() au démarrage |
| [N/A] | **Secret manager** | 🟠 HIGH | Infrastructure-specific - AWS/Vault selon environnement |
| [x] | **Debug=False** | 🔴 CRITICAL | validate_production_config() bloque si DEBUG=True |
| [x] | **Proper logging level** | 🟠 HIGH | Warning si LOG_LEVEL=DEBUG en prod |
| [N/A] | **Workers selon CPU** | 🟠 HIGH | Infrastructure-specific - docker-compose/K8s config |
| [N/A] | **Memory limits** | 🟠 HIGH | Infrastructure-specific - container config |
| [N/A] | **Resource requests** | 🟠 HIGH | Infrastructure-specific - K8s config |


---

*Document généré pour review équipe. À adapter selon contexte spécifique.*
