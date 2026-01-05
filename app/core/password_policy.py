"""
Module de politique de mot de passe avancee pour MassaCorp API.

Fonctionnalites:
- Verification contre liste de mots de passe communs (local)
- Verification contre HaveIBeenPwned (API, k-anonymity)
- Verification que le mot de passe != email/username
- Validation combinee avec les regles de force existantes
"""
import hashlib
import logging
from typing import Optional, Set

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Liste de mots de passe interdits (top 1000 les plus communs)
# Source: SecLists / rockyou / HIBP
# =============================================================================

COMMON_PASSWORDS: Set[str] = {
    # Top 100 mots de passe les plus communs
    "123456", "password", "12345678", "qwerty", "123456789",
    "12345", "1234", "111111", "1234567", "dragon",
    "123123", "baseball", "abc123", "football", "monkey",
    "letmein", "shadow", "master", "666666", "qwertyuiop",
    "123321", "mustang", "1234567890", "michael", "654321",
    "superman", "1qaz2wsx", "7777777", "121212", "000000",
    "qazwsx", "123qwe", "killer", "trustno1", "jordan",
    "jennifer", "zxcvbnm", "asdfgh", "hunter", "buster",
    "soccer", "harley", "batman", "andrew", "tigger",
    "sunshine", "iloveyou", "2000", "charlie", "robert",
    "thomas", "hockey", "ranger", "daniel", "starwars",
    "klaster", "112233", "george", "computer", "michelle",
    "jessica", "pepper", "1111", "zxcvbn", "555555",
    "11111111", "131313", "freedom", "777777", "pass",
    "maggie", "159753", "aaaaaa", "ginger", "princess",
    "joshua", "cheese", "amanda", "summer", "love",
    "ashley", "nicole", "chelsea", "biteme", "matthew",
    "access", "yankees", "987654321", "dallas", "austin",
    "thunder", "taylor", "matrix", "mobilemail", "mom",
    "monitor", "monitoring", "montana", "moon", "moscow",
    # Patterns communs
    "password1", "password123", "password1234", "passw0rd",
    "p@ssw0rd", "p@ssword", "P@ssw0rd", "P@ssword1",
    "qwerty123", "qwerty1234", "admin", "admin123",
    "administrator", "root", "toor", "test", "test123",
    "guest", "default", "welcome", "welcome1", "welcome123",
    "changeme", "changeme123", "temp", "temp123",
    "azerty", "azerty123", "azertyuiop",
    # Annees et dates communes
    "2020", "2021", "2022", "2023", "2024", "2025",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Mots francais communs
    "motdepasse", "soleil", "amour", "bonjour", "france",
    "marseille", "paris", "lyon", "toulouse", "bordeaux",
    # Mots avec caracteres speciaux simples
    "abc123!", "password!", "123456!", "qwerty!",
    # Autres patterns
    "abcd1234", "1q2w3e4r", "1q2w3e4r5t", "zaq12wsx",
    "qweasdzxc", "1qazxsw2", "1qaz@WSX",
}


# =============================================================================
# Exceptions
# =============================================================================

class PasswordPolicyError(Exception):
    """Exception pour violations de politique de mot de passe."""

    def __init__(self, message: str, error_code: str = "PASSWORD_POLICY_VIOLATION"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class CommonPasswordError(PasswordPolicyError):
    """Mot de passe trop commun."""

    def __init__(self, message: str = "Ce mot de passe est trop commun"):
        super().__init__(message, "COMMON_PASSWORD")


class CompromisedPasswordError(PasswordPolicyError):
    """Mot de passe compromis (HIBP)."""

    def __init__(self, message: str = "Ce mot de passe a ete compromis dans une fuite de donnees"):
        super().__init__(message, "COMPROMISED_PASSWORD")


class PasswordContainsUserInfoError(PasswordPolicyError):
    """Mot de passe contient email ou username."""

    def __init__(self, message: str = "Le mot de passe ne peut pas contenir votre email ou nom d'utilisateur"):
        super().__init__(message, "PASSWORD_CONTAINS_USER_INFO")


# =============================================================================
# Verification locale (liste commune)
# =============================================================================

def check_common_password(password: str) -> bool:
    """
    Verifie si le mot de passe est dans la liste des mots de passe communs.

    Args:
        password: Mot de passe a verifier

    Returns:
        True si le mot de passe est commun (INTERDIT)

    Note:
        Comparaison case-insensitive pour attraper les variations.
    """
    if not password:
        return False

    # Comparaison case-insensitive
    password_lower = password.lower()

    # Verifier contre la liste
    if password_lower in COMMON_PASSWORDS:
        return True

    # Verifier aussi sans caracteres speciaux de fin
    # Ex: "password!" -> "password"
    stripped = password_lower.rstrip("!@#$%^&*()_+-=[]{}|;':\",./<>?0123456789")
    if stripped and stripped in COMMON_PASSWORDS:
        return True

    return False


def validate_not_common(password: str) -> None:
    """
    Valide que le mot de passe n'est pas commun.

    Args:
        password: Mot de passe a valider

    Raises:
        CommonPasswordError: Si le mot de passe est trop commun
    """
    if check_common_password(password):
        raise CommonPasswordError()


# =============================================================================
# Verification HIBP (Have I Been Pwned)
# =============================================================================

def get_hibp_sha1_prefix(password: str) -> tuple[str, str]:
    """
    Calcule le hash SHA-1 et le divise en prefix/suffix pour k-anonymity.

    Args:
        password: Mot de passe a hasher

    Returns:
        Tuple (prefix 5 chars, suffix restant)
    """
    sha1_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    return sha1_hash[:5], sha1_hash[5:]


async def check_hibp_async(password: str, timeout: float = 3.0) -> Optional[int]:
    """
    Verifie si le mot de passe est dans la base HIBP (asynchrone).

    Utilise k-anonymity: seul le prefix SHA-1 (5 chars) est envoye a l'API.
    L'API retourne tous les suffixes correspondants, on verifie localement.

    Args:
        password: Mot de passe a verifier
        timeout: Timeout en secondes pour l'appel API

    Returns:
        Nombre de fois que le mot de passe a ete compromis, ou None si erreur/timeout
    """
    prefix, suffix = get_hibp_sha1_prefix(password)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={
                    "User-Agent": "MassaCorp-PasswordCheck/1.0",
                    "Add-Padding": "true",  # Evite timing attacks
                }
            )

            if response.status_code != 200:
                logger.warning(f"HIBP API returned {response.status_code}")
                return None

            # Parser la reponse: chaque ligne est "SUFFIX:COUNT"
            for line in response.text.splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    hash_suffix, count = parts
                    if hash_suffix == suffix:
                        return int(count)

            # Pas trouve = pas compromis
            return 0

    except httpx.TimeoutException:
        logger.warning("HIBP API timeout")
        return None
    except Exception as e:
        logger.warning(f"HIBP API error: {e}")
        return None


def check_hibp_sync(password: str, timeout: float = 3.0) -> Optional[int]:
    """
    Verifie si le mot de passe est dans la base HIBP (synchrone).

    Args:
        password: Mot de passe a verifier
        timeout: Timeout en secondes pour l'appel API

    Returns:
        Nombre de fois que le mot de passe a ete compromis, ou None si erreur/timeout
    """
    prefix, suffix = get_hibp_sha1_prefix(password)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={
                    "User-Agent": "MassaCorp-PasswordCheck/1.0",
                    "Add-Padding": "true",
                }
            )

            if response.status_code != 200:
                logger.warning(f"HIBP API returned {response.status_code}")
                return None

            for line in response.text.splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    hash_suffix, count = parts
                    if hash_suffix == suffix:
                        return int(count)

            return 0

    except httpx.TimeoutException:
        logger.warning("HIBP API timeout")
        return None
    except Exception as e:
        logger.warning(f"HIBP API error: {e}")
        return None


def validate_not_compromised(
    password: str,
    timeout: float = 3.0,
    fail_open: bool = True
) -> None:
    """
    Valide que le mot de passe n'est pas compromis (HIBP).

    Args:
        password: Mot de passe a valider
        timeout: Timeout pour l'appel API
        fail_open: Si True, accepte le mot de passe en cas d'erreur API

    Raises:
        CompromisedPasswordError: Si le mot de passe est compromis
    """
    count = check_hibp_sync(password, timeout=timeout)

    if count is None:
        # Erreur API
        if not fail_open:
            raise CompromisedPasswordError(
                "Impossible de verifier si le mot de passe est compromis. Reessayez."
            )
        # fail_open = True: on accepte silencieusement
        logger.info("HIBP check skipped due to API error (fail_open=True)")
        return

    if count > 0:
        raise CompromisedPasswordError(
            f"Ce mot de passe a ete trouve dans {count} fuites de donnees. "
            "Choisissez un mot de passe different."
        )


# =============================================================================
# Verification email/username
# =============================================================================

def check_password_contains_user_info(
    password: str,
    email: Optional[str] = None,
    username: Optional[str] = None
) -> bool:
    """
    Verifie si le mot de passe contient l'email ou le username.

    Args:
        password: Mot de passe a verifier
        email: Email de l'utilisateur (optionnel)
        username: Nom d'utilisateur (optionnel)

    Returns:
        True si le mot de passe contient des infos utilisateur (INTERDIT)
    """
    if not password:
        return False

    password_lower = password.lower()

    # Verifier email
    if email:
        email_lower = email.lower()

        # Email complet dans le password
        if email_lower in password_lower:
            return True

        # Partie locale de l'email (avant @)
        local_part = email_lower.split("@")[0]
        if len(local_part) >= 3 and local_part in password_lower:
            return True

    # Verifier username
    if username:
        username_lower = username.lower()
        if len(username_lower) >= 3 and username_lower in password_lower:
            return True

    return False


def validate_not_user_info(
    password: str,
    email: Optional[str] = None,
    username: Optional[str] = None
) -> None:
    """
    Valide que le mot de passe ne contient pas email/username.

    Args:
        password: Mot de passe a valider
        email: Email de l'utilisateur
        username: Nom d'utilisateur

    Raises:
        PasswordContainsUserInfoError: Si le mot de passe contient des infos utilisateur
    """
    if check_password_contains_user_info(password, email, username):
        raise PasswordContainsUserInfoError()


# =============================================================================
# Validation combinee
# =============================================================================

def validate_password_policy(
    password: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
    check_hibp: bool = True,
    hibp_timeout: float = 3.0,
    hibp_fail_open: bool = True
) -> None:
    """
    Validation complete de la politique de mot de passe.

    Verifie dans l'ordre:
    1. Liste de mots de passe communs (rapide, local)
    2. Pas d'infos utilisateur dans le password
    3. HIBP (optionnel, API externe)

    Args:
        password: Mot de passe a valider
        email: Email de l'utilisateur
        username: Nom d'utilisateur
        check_hibp: Si True, verifie contre HIBP
        hibp_timeout: Timeout pour l'appel HIBP
        hibp_fail_open: Si True, accepte en cas d'erreur HIBP

    Raises:
        CommonPasswordError: Si mot de passe trop commun
        PasswordContainsUserInfoError: Si contient email/username
        CompromisedPasswordError: Si compromis (HIBP)
    """
    # 1. Verifier mots de passe communs (rapide, local)
    validate_not_common(password)

    # 2. Verifier pas d'infos utilisateur
    validate_not_user_info(password, email, username)

    # 3. Verifier HIBP (si active)
    if check_hibp:
        validate_not_compromised(
            password,
            timeout=hibp_timeout,
            fail_open=hibp_fail_open
        )
