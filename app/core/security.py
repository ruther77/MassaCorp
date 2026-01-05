"""
Module de securite pour MassaCorp API
Gestion du hashing, JWT, et validation des mots de passe

Securite production:
- Argon2id pour les nouveaux hashes (recommande OWASP)
- bcrypt pour compatibilite avec anciens hashes (migration progressive)
- JWT HS256 avec secrets forts
- Validation stricte des mots de passe
- SHA256 pour le hachage des refresh tokens

Migration bcrypt -> Argon2id:
- verify_password() accepte les deux formats
- hash_password() utilise Argon2id par defaut
- needs_rehash() detecte les anciens hashes bcrypt
- Les utilisateurs sont re-hashes automatiquement au login
"""
import hashlib
import hmac
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)

import bcrypt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt

from app.core.config import get_settings

# ============================================
# Configuration
# ============================================

settings = get_settings()

# Algorithme JWT
JWT_ALGORITHM = settings.JWT_ALGORITHM

# Cost factor bcrypt (12 minimum pour production) - pour compatibilite
BCRYPT_COST = 12

# Configuration Argon2id (OWASP recommandations 2024)
# - Type: Argon2id (resistant aux side-channel et GPU attacks)
# - Time cost: 3 iterations
# - Memory cost: 64 MiB (65536 KiB)
# - Parallelism: 4 threads
# - Hash length: 32 bytes
ARGON2_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    type=Type.ID  # Argon2id
)

# DUMMY_HASH pour timing-safe login (evite timing attacks sur user enumeration)
# Ce hash est en Argon2id pour les nouvelles installations
# Format: $argon2id$v=19$m=65536,t=3,p=4$...
DUMMY_HASH_ARGON2 = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$K0VGpKvqJxWyZEfJxkBQEWjKQtRtGi5K1NxD7sGWxPk"
# Hash bcrypt legacy pour compatibilite
DUMMY_HASH_BCRYPT = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VSJHQJI0N0.o.a"
# Alias pour compatibilite
DUMMY_HASH = DUMMY_HASH_ARGON2

# Durees d'expiration des tokens (en minutes pour compatibilite)
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_LIFETIME // 60
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_LIFETIME // 60


# ============================================
# Exceptions Personnalisees
# ============================================

class SecurityError(Exception):
    """Exception de base pour les erreurs de securite"""
    pass


class PasswordValidationError(SecurityError):
    """Erreur de validation de mot de passe"""
    pass


class TokenExpiredError(SecurityError):
    """Token JWT expire"""
    pass


class InvalidTokenError(SecurityError):
    """Token JWT invalide"""
    pass


# ============================================
# Password Hashing (Argon2id + bcrypt legacy)
# ============================================

def is_argon2_hash(hashed_password: str) -> bool:
    """
    Detecte si un hash est au format Argon2.

    Args:
        hashed_password: Hash a analyser

    Returns:
        True si c'est un hash Argon2 (argon2i, argon2d, ou argon2id)
    """
    return hashed_password.startswith("$argon2")


def is_bcrypt_hash(hashed_password: str) -> bool:
    """
    Detecte si un hash est au format bcrypt.

    Args:
        hashed_password: Hash a analyser

    Returns:
        True si c'est un hash bcrypt ($2a$, $2b$, $2y$)
    """
    return hashed_password.startswith("$2")


def hash_password(password: str, use_argon2: bool = True) -> str:
    """
    Hash un mot de passe avec Argon2id (par defaut) ou bcrypt.

    Argon2id est recommande par OWASP comme algorithme de reference
    pour le hashing de mots de passe (resistant GPU et side-channel).

    Args:
        password: Mot de passe en clair
        use_argon2: Si True, utilise Argon2id (defaut). Si False, bcrypt.

    Returns:
        Hash du mot de passe (format $argon2id$... ou $2b$...)

    Raises:
        PasswordValidationError: Si le mot de passe est vide ou None
    """
    if password is None:
        raise PasswordValidationError("Le mot de passe ne peut pas etre None")

    if not password or len(password) == 0:
        raise PasswordValidationError("Le mot de passe ne peut pas etre vide")

    if use_argon2:
        # Argon2id (recommande)
        return ARGON2_HASHER.hash(password)
    else:
        # bcrypt (legacy)
        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=BCRYPT_COST)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode("utf-8")


def hash_password_bcrypt(password: str) -> str:
    """
    Hash un mot de passe avec bcrypt (legacy).

    Utiliser uniquement pour des cas specifiques ou la compatibilite
    avec des systemes externes est requise.

    Args:
        password: Mot de passe en clair

    Returns:
        Hash bcrypt du mot de passe
    """
    return hash_password(password, use_argon2=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifie un mot de passe contre son hash.

    Supporte les deux formats:
    - Argon2id ($argon2id$...) - nouveau standard
    - bcrypt ($2b$...) - legacy, migration progressive

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash a verifier (Argon2id ou bcrypt)

    Returns:
        True si le mot de passe correspond, False sinon
    """
    if not plain_password or not hashed_password:
        return False

    try:
        if is_argon2_hash(hashed_password):
            # Verification Argon2
            try:
                ARGON2_HASHER.verify(hashed_password, plain_password)
                return True
            except VerificationError:
                return False
            except InvalidHashError:
                logger.warning("Hash Argon2 invalide detecte")
                return False

        elif is_bcrypt_hash(hashed_password):
            # Verification bcrypt (legacy)
            password_bytes = plain_password.encode("utf-8")
            hashed_bytes = hashed_password.encode("utf-8")
            return bcrypt.checkpw(password_bytes, hashed_bytes)

        else:
            # Format de hash inconnu
            logger.warning(f"Format de hash inconnu: {hashed_password[:20]}...")
            return False

    except Exception as e:
        logger.debug(f"Erreur verification mot de passe: {e}")
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Verifie si un hash doit etre mis a jour vers Argon2id.

    Cas necessitant un re-hash:
    - Hash bcrypt (migration vers Argon2id)
    - Hash Argon2 avec parametres obsoletes

    Args:
        hashed_password: Hash actuel

    Returns:
        True si le hash doit etre mis a jour
    """
    if not hashed_password:
        return False

    # Les hashes bcrypt doivent migrer vers Argon2id
    if is_bcrypt_hash(hashed_password):
        return True

    # Verifier si les parametres Argon2 sont a jour
    if is_argon2_hash(hashed_password):
        try:
            return ARGON2_HASHER.check_needs_rehash(hashed_password)
        except InvalidHashError:
            return True

    return False


def verify_and_rehash(
    plain_password: str,
    hashed_password: str
) -> Tuple[bool, Optional[str]]:
    """
    Verifie un mot de passe et retourne un nouveau hash si necessaire.

    Utilise pour la migration progressive:
    1. Verifie le mot de passe
    2. Si valide et hash obsolete, genere un nouveau hash Argon2id

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash actuel

    Returns:
        Tuple (is_valid, new_hash):
        - is_valid: True si le mot de passe est correct
        - new_hash: Nouveau hash Argon2id si re-hash necessaire, None sinon
    """
    is_valid = verify_password(plain_password, hashed_password)

    if not is_valid:
        return (False, None)

    # Verifier si re-hash necessaire
    if needs_rehash(hashed_password):
        new_hash = hash_password(plain_password)
        logger.info("Password rehash effectue (migration vers Argon2id)")
        return (True, new_hash)

    return (True, None)


# ============================================
# Password Validation
# ============================================

def validate_password_strength(
    password: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
    check_common: bool = True,
    check_hibp: bool = None,  # None = use settings.PASSWORD_CHECK_HIBP
    hibp_fail_open: bool = True
) -> bool:
    """
    Valide la force d'un mot de passe.

    Regles de base:
    - Minimum 8 caracteres
    - Maximum 128 caracteres
    - Au moins une majuscule
    - Au moins une minuscule
    - Au moins un chiffre
    - Au moins un caractere special

    Regles avancees (optionnelles):
    - Pas dans liste de mots de passe communs
    - Pas d'email/username dans le mot de passe
    - Pas compromis (HIBP - HaveIBeenPwned)

    Args:
        password: Mot de passe a valider
        email: Email de l'utilisateur (pour verifier absence dans password)
        username: Nom d'utilisateur (pour verifier absence dans password)
        check_common: Verifier contre liste de mots de passe communs
        check_hibp: Verifier contre HIBP (appel API externe)
        hibp_fail_open: Si True, accepte le password en cas d'erreur HIBP

    Returns:
        True si le mot de passe est valide

    Raises:
        PasswordValidationError: Si le mot de passe ne respecte pas les regles
    """
    if not password:
        raise PasswordValidationError("Le mot de passe ne peut pas etre vide")

    # Longueur minimum
    if len(password) < 8:
        raise PasswordValidationError(
            "Le mot de passe doit contenir au moins 8 caracteres"
        )

    # Longueur maximum
    if len(password) > 128:
        raise PasswordValidationError(
            "Le mot de passe ne peut pas depasser 128 caracteres"
        )

    # Au moins une majuscule
    if not re.search(r"[A-Z]", password):
        raise PasswordValidationError(
            "Le mot de passe doit contenir au moins une majuscule (uppercase)"
        )

    # Au moins une minuscule
    if not re.search(r"[a-z]", password):
        raise PasswordValidationError(
            "Le mot de passe doit contenir au moins une minuscule (lowercase)"
        )

    # Au moins un chiffre
    if not re.search(r"\d", password):
        raise PasswordValidationError(
            "Le mot de passe doit contenir au moins un chiffre (digit)"
        )

    # Au moins un caractere special
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\/'`~;]", password):
        raise PasswordValidationError(
            "Le mot de passe doit contenir au moins un caractere special"
        )

    # Resolve check_hibp from settings if None
    if check_hibp is None:
        check_hibp = settings.PASSWORD_CHECK_HIBP

    # Validations avancees (politique de mot de passe)
    if check_common or email or username or check_hibp:
        from app.core.password_policy import (
            CommonPasswordError,
            CompromisedPasswordError,
            PasswordContainsUserInfoError,
            validate_password_policy,
        )

        try:
            validate_password_policy(
                password=password,
                email=email,
                username=username,
                check_hibp=check_hibp,
                hibp_fail_open=hibp_fail_open
            )
        except CommonPasswordError as e:
            raise PasswordValidationError(e.message)
        except PasswordContainsUserInfoError as e:
            raise PasswordValidationError(e.message)
        except CompromisedPasswordError as e:
            raise PasswordValidationError(e.message)

    return True


# ============================================
# JWT Token Creation
# ============================================

def create_access_token(
    subject: Union[int, str],
    tenant_id: int,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> str:
    """
    Cree un token JWT d'acces.

    Args:
        subject: ID de l'utilisateur (sera dans 'sub')
        tenant_id: ID du tenant
        email: Email de l'utilisateur (optionnel)
        expires_delta: Duree de validite (defaut: ACCESS_TOKEN_LIFETIME)
        extra_claims: Claims supplementaires
        session_id: ID de la session (pour identifier la session courante)

    Returns:
        Token JWT signe
    """
    if expires_delta is None:
        expires_delta = timedelta(seconds=settings.ACCESS_TOKEN_LIFETIME)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(subject),  # JWT requiert string pour sub
        "tenant_id": tenant_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if email:
        payload["email"] = email

    if session_id:
        payload["session_id"] = session_id

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    subject: Union[int, str],
    tenant_id: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cree un token JWT de refresh.
    Inclut un JTI unique pour permettre la revocation.

    Args:
        subject: ID de l'utilisateur
        tenant_id: ID du tenant
        expires_delta: Duree de validite (defaut: REFRESH_TOKEN_LIFETIME)

    Returns:
        Token JWT de refresh signe
    """
    if expires_delta is None:
        expires_delta = timedelta(seconds=settings.REFRESH_TOKEN_LIFETIME)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(subject),  # JWT requiert string pour sub
        "tenant_id": tenant_id,
        "type": "refresh",
        "jti": str(uuid.uuid4()),  # Unique token identifier
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


# ============================================
# JWT Token Verification
# ============================================

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode et valide un token JWT.

    Args:
        token: Token JWT a decoder

    Returns:
        Payload du token

    Raises:
        InvalidTokenError: Si le token est invalide
        TokenExpiredError: Si le token est expire
    """
    if not token or not isinstance(token, str):
        raise InvalidTokenError("Token invalide ou vide")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Le token a expire")

    except JWTError as e:
        raise InvalidTokenError(f"Token invalide: {str(e)}")


def verify_token_type(token: str, expected_type: str) -> bool:
    """
    Verifie le type d'un token JWT.

    Args:
        token: Token JWT
        expected_type: Type attendu ('access' ou 'refresh')

    Returns:
        True si le type correspond

    Raises:
        InvalidTokenError: Si le type ne correspond pas
    """
    payload = decode_token(token)

    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(
            f"Type de token invalide: attendu '{expected_type}', obtenu '{token_type}'"
        )

    return True


def get_token_payload(token: str) -> Optional[Dict[str, Any]]:
    """
    Recupere le payload d'un token sans lever d'exception.
    Utile pour le logging et le debug.

    Args:
        token: Token JWT

    Returns:
        Payload du token ou None si invalide
    """
    try:
        return decode_token(token)
    except (InvalidTokenError, TokenExpiredError):
        return None


# ============================================
# Utility Functions
# ============================================

def generate_token_jti() -> str:
    """Genere un identifiant unique pour un token (JTI)"""
    return str(uuid.uuid4())


def get_password_hash(password: str) -> str:
    """Alias pour hash_password (compatibilite)"""
    return hash_password(password)


# ============================================
# Token Hashing (SHA256)
# ============================================

def hash_token(token: str) -> str:
    """
    Hash un token avec SHA256.

    Utilise pour stocker les refresh tokens de maniere securisee.
    Le hash est irreversible - on ne peut pas retrouver le token original.

    Args:
        token: Token brut a hasher

    Returns:
        Hash SHA256 en hexadecimal (64 caracteres)

    Raises:
        ValueError: Si le token est None ou vide
    """
    if token is None:
        raise ValueError("Le token ne peut pas etre None")

    if not token or len(token) == 0:
        raise ValueError("Le token ne peut pas etre vide")

    # SHA256 produit 32 bytes = 64 caracteres hexadecimaux
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """
    Verifie qu'un token correspond a son hash.

    Args:
        token: Token brut a verifier
        token_hash: Hash SHA256 stocke

    Returns:
        True si le token correspond au hash, False sinon
    """
    # Rejeter explicitement les placeholders
    if token_hash == "placeholder_hash":
        return False

    if not token or not token_hash:
        return False

    try:
        computed_hash = hash_token(token)
        # Comparaison en temps constant pour eviter timing attacks
        return hmac.compare_digest(computed_hash, token_hash)
    except ValueError:
        return False
