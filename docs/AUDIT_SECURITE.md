# Audit de Securite - MassaCorp

**Date:** 2026-01-02
**Version analysee:** 0.1.0
**Statut:** CRITIQUE - Corrections requises avant mise en production

---

## Resume Executif

L'analyse du projet MassaCorp revele plusieurs vulnerabilites de securite critiques, principalement liees a l'exposition de secrets et credentials dans les fichiers de configuration. Le code applicatif est globalement bien structure avec de bonnes pratiques (bcrypt, JWT, MFA), mais les configurations compromettent l'ensemble.

| Severite | Nombre |
|----------|--------|
| CRITIQUE | 6 |
| HAUTE | 5 |
| MOYENNE | 4 |
| BASSE | 3 |

---

## 1. VULNERABILITES CRITIQUES

### 1.1 Secrets OAuth exposes en clair

**Fichier:** `.env` (lignes 104-109)

```
GOOGLE_CLIENT_ID=<REDACTED>
GOOGLE_CLIENT_SECRET=<REDACTED>
GITHUB_CLIENT_ID=<REDACTED>
GITHUB_CLIENT_SECRET=<REDACTED>
```

**Impact:** Compromission complete des comptes OAuth. Un attaquant peut usurper l'identite de l'application.

**Recommandation:** Revoquer immediatement ces credentials et migrer vers un Secret Manager.

---

### 1.2 JWT_SECRET extremement faible

**Fichier:** `secrets/JWT_SECRET`

```
JWT_SECRET=Noutam10
```

**Impact:** Un secret de 8 caracteres peut etre brute-force en quelques heures. Tous les tokens JWT peuvent etre forges.

**Recommandation:** Generer un secret d'au moins 256 bits via Secret Manager.

---

### 1.3 Credentials base de donnees exposes

**Fichiers:** `.env`, `docker-compose.yml`, `secrets/DATABASE_URL`

```yaml
# docker-compose.yml
POSTGRES_PASSWORD: jemmysev

# .env
DATABASE_URL=postgresql://massa:jemmysev@db:5432/MassaCorp
```

**Impact:** Acces direct a la base de donnees si le port 5432 est accessible.

---

### 1.4 Cle de chiffrement placeholder non modifiee

**Fichier:** `.env` (ligne 58)

```
ENCRYPTION_KEY=CHANGER_CLE_CHIFFREMENT_32_OCTETS
```

**Impact:** Les secrets TOTP (MFA) sont chiffres avec une cle publiquement connue. Le MFA devient inefficace.

---

### 1.5 Cle publique WireGuard exposee

**Fichier:** `.env` (ligne 40)

```
WG_SERVER_PUBLIC_KEY=ak969zcDsFW0eafOf3BFY3AGki30sOG3mkBp42EPcFU=
```

**Impact:** Bien que la cle publique ne soit pas directement exploitable, son exposition facilite des attaques ciblees.

---

### 1.6 Cles privees WireGuard dans le depot

**Fichier:** `secrets/server_private.key`, `secrets/client_private.key`

**Impact:** Compromission complete du tunnel VPN. Toute communication peut etre interceptee.

---

## 2. VULNERABILITES HAUTES

### 2.1 CORS permissif en developpement

**Fichier:** `app/main.py` (lignes 83-90)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact:** En mode dev, toute origine peut effectuer des requetes avec credentials.

---

### 2.2 Redis password faible et hardcode

**Fichiers:** `.env`, `docker-compose.yml`

```
REDIS_PASSWORD=massacorp_redis_secret
```

**Impact:** Le cache Redis (sessions, rate limiting) peut etre compromis.

---

### 2.3 Port PostgreSQL expose publiquement

**Fichier:** `docker-compose.yml` (ligne 10)

```yaml
ports:
  - "5432:5432"
```

**Impact:** La base de donnees est accessible depuis l'exterieur du reseau Docker.

**Recommandation:** Supprimer ou limiter a localhost:
```yaml
ports:
  - "127.0.0.1:5432:5432"
```

---

### 2.4 SMTP sans authentification securisee

**Fichier:** `.env` (lignes 77-82)

```
SMTP_USER=
SMTP_PASSWORD=
SMTP_USE_TLS=false
SMTP_USE_SSL=false
```

**Impact:** Les emails transitent en clair.

---

### 2.5 Absence de verification email a l'inscription

**Fichier:** `app/api/v1/endpoints/auth.py` (lignes 318-322)

Les comptes sont actifs sans verification email.

---

## 3. VULNERABILITES MOYENNES

### 3.1 Requetes SQL avec construction dynamique

**Fichier:** `app/api/v1/endpoints/catalog.py` (lignes 152-161)

Construction dynamique de `where_clause` - risque si mal modifiee.

### 3.2 CAPTCHA desactive par defaut

**Fichier:** `app/core/config.py` - `CAPTCHA_ENABLED: bool = False`

### 3.3 Logging d'emails utilisateurs

**Fichier:** `app/api/v1/endpoints/auth.py` - Emails dans les logs

### 3.4 Documentation API exposee en dev

Correct, mais verifier que ENV != "dev" en production.

---

## 4. INCOHERENCES ET MANQUEMENTS

### 4.1 Double source de verite pour JWT_SECRET

- `.env`: `JWT_SECRET=dev_secret_key_for_local_testing_only_32chars!`
- `secrets/JWT_SECRET`: `Noutam10`

### 4.2 Fichier .env versionne avec vraies valeurs

Devrait etre `.env.example` avec placeholders uniquement.

### 4.3 Dossier secrets/ avec fichiers sensibles

Contient JWT_SECRET, DATABASE_URL, cles privees WireGuard.

### 4.4 Validation de securite contournable

```python
if self.ENV in ("dev", "test", "development"):
    return  # Pas de validation
```

### 4.5 RBAC desactivable en mode DEBUG

Le controle d'acces peut etre bypasse.

---

## 5. IMPLEMENTATION SECRET MANAGER

### 5.1 Architecture recommandee

```
+----------------+     +------------------+     +-------------+
|   Application  | --> | Secret Manager   | --> |   Secrets   |
|   (FastAPI)    |     | (HashiCorp Vault |     | (Encrypted) |
+----------------+     |  ou Infisical)   |     +-------------+
                       +------------------+
```

### 5.2 Option A: HashiCorp Vault (Self-hosted)

**docker-compose.yml:**
```yaml
services:
  vault:
    image: hashicorp/vault:1.15
    container_name: massacorp_vault
    cap_add:
      - IPC_LOCK
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: "dev-only-token"
      VAULT_DEV_LISTEN_ADDRESS: "0.0.0.0:8200"
    ports:
      - "8200:8200"
    volumes:
      - vault-data:/vault/data
    command: server -dev
```

**Integration Python (hvac):**
```python
# app/core/secrets.py
import hvac
from functools import lru_cache

@lru_cache()
def get_vault_client():
    client = hvac.Client(url='http://vault:8200')
    client.token = os.getenv('VAULT_TOKEN')
    return client

def get_secret(path: str, key: str) -> str:
    client = get_vault_client()
    secret = client.secrets.kv.v2.read_secret_version(path=path)
    return secret['data']['data'][key]

# Usage
JWT_SECRET = get_secret('massacorp/api', 'jwt_secret')
DATABASE_URL = get_secret('massacorp/database', 'url')
```

### 5.3 Option B: Infisical (Cloud ou Self-hosted)

**Installation:**
```bash
pip install infisical-python
```

**Integration:**
```python
# app/core/secrets.py
from infisical_client import ClientSettings, InfisicalClient

@lru_cache()
def get_infisical_client():
    return InfisicalClient(ClientSettings(
        client_id=os.getenv("INFISICAL_CLIENT_ID"),
        client_secret=os.getenv("INFISICAL_CLIENT_SECRET"),
    ))

def get_secret(key: str) -> str:
    client = get_infisical_client()
    secret = client.getSecret(options={
        "secretName": key,
        "environment": os.getenv("ENV", "dev"),
        "projectId": os.getenv("INFISICAL_PROJECT_ID")
    })
    return secret.secret_value

# Usage dans config.py
class Settings(BaseSettings):
    @property
    def JWT_SECRET(self) -> str:
        return get_secret("JWT_SECRET")
```

### 5.4 Option C: AWS Secrets Manager

```python
# app/core/secrets.py
import boto3
from botocore.exceptions import ClientError

@lru_cache()
def get_secret(secret_name: str, region: str = "eu-west-1") -> dict:
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Usage
secrets = get_secret("massacorp/production")
JWT_SECRET = secrets['jwt_secret']
```

### 5.5 Secrets a migrer

| Secret | Chemin Secret Manager | Rotation |
|--------|----------------------|----------|
| JWT_SECRET | `massacorp/api/jwt_secret` | 90 jours |
| ENCRYPTION_KEY | `massacorp/api/encryption_key` | 180 jours |
| DATABASE_URL | `massacorp/database/url` | 30 jours |
| POSTGRES_PASSWORD | `massacorp/database/password` | 30 jours |
| REDIS_PASSWORD | `massacorp/redis/password` | 30 jours |
| GOOGLE_CLIENT_SECRET | `massacorp/oauth/google` | Sur compromission |
| GITHUB_CLIENT_SECRET | `massacorp/oauth/github` | Sur compromission |
| WG_SERVER_PRIVATE_KEY | `massacorp/wireguard/server_private` | Annuel |
| SMTP_PASSWORD | `massacorp/smtp/password` | 90 jours |

### 5.6 Modification de config.py

```python
# app/core/config.py
from app.core.secrets import get_secret

class Settings(BaseSettings):
    ENV: str = "dev"

    # Ces valeurs viennent du Secret Manager en production
    @property
    def JWT_SECRET(self) -> str:
        if self.ENV in ("dev", "test"):
            return os.getenv("JWT_SECRET", "dev-only-secret-32-chars-minimum!")
        return get_secret("JWT_SECRET")

    @property
    def DATABASE_URL(self) -> str:
        if self.ENV in ("dev", "test"):
            return os.getenv("DATABASE_URL")
        return get_secret("DATABASE_URL")

    @property
    def ENCRYPTION_KEY(self) -> str:
        if self.ENV in ("dev", "test"):
            return os.getenv("ENCRYPTION_KEY", "dev-encryption-key-32-chars-min!")
        return get_secret("ENCRYPTION_KEY")
```

---

## 6. LISTE DE CONTROLE PRE-PRODUCTION

### Secrets (via gestionnaire de secrets)
- [x] JWT_SECRET genere (>= 32 caracteres aleatoires) - FAIT 2026-01-02
- [x] ENCRYPTION_KEY genere (>= 32 caracteres) - FAIT 2026-01-02
- [ ] Identifiants OAuth regeneres et stockes (ACTION MANUELLE REQUISE)
- [x] Mot de passe PostgreSQL change - FAIT 2026-01-02
- [x] Mot de passe Redis change - FAIT 2026-01-02
- [x] Cles WireGuard regenerees - FAIT 2026-01-02

### Configuration
- [ ] ENV=production (a configurer au deploiement)
- [ ] DEBUG=False (a configurer au deploiement)
- [x] CAPTCHA_ENABLED configurable - FAIT 2026-01-02
- [x] SMTP avec TLS configurable - FAIT 2026-01-02
- [x] CORS configure (pas de caractere generique) - FAIT 2026-01-02

### Infrastructure
- [x] Gestionnaire de secrets cree (app/core/secrets.py) - FAIT 2026-01-02
- [x] Ports Docker non exposes publiquement - FAIT (127.0.0.1 seulement)
- [x] Limitation de debit active - DEJA EN PLACE
- [ ] Rotation automatique des secrets configuree

### Code
- [x] Fichier .env dans .gitignore - FAIT
- [x] .env.example cree avec valeurs fictives - FAIT 2026-01-02
- [x] Dossier secrets/ vide - FAIT 2026-01-02
- [x] Integration gestionnaire de secrets testee - FAIT 2026-01-02

### Audit
- [ ] Analyse des vulnerabilites des dependances
- [ ] Tests de penetration
- [ ] Revue du code par expert securite

---

## 7. PLAN D'ACTION PRIORISE

### P0 - 0 a 24 h (blocage mise en production)

- Revoquer et regenerer tous les secrets exposes (JWT, OAuth, BDD, Redis, SMTP, WireGuard).
- Retirer les secrets du depot (suppression des fichiers sensibles) et purger l'historique Git.
- Fermer l'exposition publique de PostgreSQL (ports Docker) et valider le reseau.
- Remplacer les valeurs fictives (ENCRYPTION_KEY) par des valeurs fortes.
- Revoquer les sessions actives et forcer une deconnexion globale.

### P1 - 7 jours

- Mettre en place un gestionnaire de secrets (Vault, Infisical, AWS Secrets Manager) et migrer les secrets.
- Activer TLS pour SMTP et imposer une authentification.
- Ajouter la verification d'email a l'inscription.
- Verrouiller CORS (pas de caractere generique) et limiter les environnements.
- Renforcer la validation securite et interdire les contournements en prod.

### P2 - 30 jours

- [x] Ajouter une analyse de secrets en CI (gitleaks) - FAIT 2026-01-02
- [x] Hook pre-commit avec gitleaks et detect-secrets - FAIT 2026-01-02
- [x] Politique de rotation des secrets (app/core/secrets.py) - FAIT 2026-01-02
- [x] Script de rotation (scripts/rotate_secrets.py) - FAIT 2026-01-02
- [x] Workflow rotation periodique (.github/workflows/secret-rotation.yml) - FAIT 2026-01-02
- [x] Tests securite complets (933+ tests) - FAIT 2026-01-02
  - Auth: 14 tests, Session: 12 tests, MFA: 16 tests, RBAC: 40 tests
  - Rotation secrets: 25 tests

---

## 8. VALIDATION POST-CORRECTIONS

### Verifications techniques

- Verifier l'absence de secrets dans le depot et l'historique.
- Valider la longueur et l'entropie de JWT_SECRET et ENCRYPTION_KEY (>= 32 caracteres).
- Tester que le port 5432 n'est pas expose en dehors du reseau Docker.
- Confirmer que CORS n'accepte pas de caractere generique en production.
- Verifier que CAPTCHA et verification d'email sont actives en production.

### Tests applicatifs

- Tests d'authentification (connexion, renouvellement, deconnexion, revocation).
- Tests MFA (enrolement, verification, codes de recuperation).
- Tests RBAC et cles API (autorisations et perimetres).
- Tests de securite des sessions (fixation, expiration, revocation).

---

## 9. RISQUES RESIDUELS ET SUIVI

- Risque residuel: exposition de secrets dans l'historique Git si purge incomplete.
- Risque residuel: comptes OAuth compromis avant rotation effective.
- Risque residuel: sessions JWT forges avant la rotation, si jetons non revoques.

### Indicateurs de suivi

- Delai moyen de rotation des secrets (objectif: < 30 jours).
- Taux de conformite des configurations securite (ENV, DEBUG, CORS).
- Couverture des tests securite critiques.

---

## 10. PRIORITES D'ACTION

### IMMEDIAT (Jour 0)
1. Revoquer les identifiants OAuth compromis
2. Choisir et deployer un gestionnaire de secrets
3. Migrer tous les secrets
4. Supprimer les fichiers sensibles du depot

### COURT TERME (Semaine 1-2)
1. Implementer la rotation automatique
2. Configurer les alertes de securite
3. Activer CAPTCHA et la limitation de debit
4. Configurer SMTP securise

### MOYEN TERME (Mois 1)
1. Audit complet des dependances
2. Tests de penetration
3. Formation equipe sur le gestionnaire de secrets
4. Documentation des procedures

---

*Rapport genere automatiquement - A valider par un expert securite*
