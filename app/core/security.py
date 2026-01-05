"""
Module de securite pour MassaCorp API
Gestion du hashing, JWT, et validation des mots de passe

Securite production:
- bcrypt avec cost factor 12
- JWT HS256 avec secrets forts
- Validation stricte des mots de passe
- SHA256 pour le hachage des refresh tokens
"""
import hashlib
import hmac
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

# ============================================
# Configuration
# ============================================

settings = get_settings()

# Algorithme JWT
JWT_ALGORITHM = settings.JWT_ALGORITHM

# Cost factor bcrypt (12 minimum pour production)
BCRYPT_COST = 12

# DUMMY_HASH pour timing-safe login (evite timing attacks sur user enumeration)
# Ce hash est pre-calcule avec bcrypt cost 12 pour "dummy_password_never_used"
# Utilise quand l'utilisateur n'existe pas pour garder un timing constant
DUMMY_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VSJHQJI0N0.o.a"

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
# Password Hashing
# ============================================

def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec bcrypt.

    Args:
        password: Mot de passe en clair

    Returns:
        Hash bcrypt du mot de passe

    Raises:
        PasswordValidationError: Si le mot de passe est vide ou None
    """
    if password is None:
        raise PasswordValidationError("Le mot de passe ne peut pas etre None")

    if not password or len(password) == 0:
        raise PasswordValidationError("Le mot de passe ne peut pas etre vide")

    # Encoder en bytes pour bcrypt
    password_bytes = password.encode("utf-8")

    # Generer le salt et hasher
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifie un mot de passe contre son hash.
    Resistant aux timing attacks grace a bcrypt.checkpw.

    Args:
        plain_password: Mot de passe en clair
        hashed_password: Hash bcrypt a verifier

    Returns:
        True si le mot de passe correspond, False sinon
    """
    if not plain_password or not hashed_password:
        return False

    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        # Hash invalide ou autre erreur - log pour debug
        logger.debug(f"Erreur verification mot de passe: {e}")
        return False


# ============================================
# Password Validation
# ============================================

def validate_password_strength(
    password: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
    check_common: bool = True,
    check_hibp: bool = False,  # Desactive par defaut (appel API externe)
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
