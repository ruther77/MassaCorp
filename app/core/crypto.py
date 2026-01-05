"""
Module de cryptographie pour MassaCorp.

Ce module fournit des fonctions de chiffrement/dechiffrement securisees
pour les donnees sensibles comme les secrets TOTP.

Algorithme: AES-256-GCM (Galois/Counter Mode)
- Chiffrement authentifie (confidentialite + integrite)
- IV unique par chiffrement (12 bytes)
- Tag d'authentification (16 bytes)

Format de sortie: base64(IV + ciphertext + tag)
"""
import base64
import hashlib
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _get_encryption_key() -> bytes:
    """
    Derive une cle AES-256 a partir de la cle de configuration.

    Utilise SHA-256 pour garantir une cle de 32 bytes
    meme si la cle configuree est de taille differente.

    Returns:
        Cle de 32 bytes pour AES-256
    """
    settings = get_settings()
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    # Deriver une cle de 32 bytes avec SHA-256
    return hashlib.sha256(key).digest()


def encrypt_totp_secret(secret: str) -> str:
    """
    Chiffre un secret TOTP avec AES-256-GCM.

    Le resultat inclut l'IV et le tag d'authentification
    pour permettre le dechiffrement et la verification d'integrite.

    Args:
        secret: Secret TOTP en base32 (typiquement 32 caracteres)

    Returns:
        Secret chiffre en base64 (format: IV + ciphertext + tag)

    Raises:
        ValueError: Si le secret est vide ou None
    """
    if not secret:
        raise ValueError("Le secret ne peut pas etre vide")

    key = _get_encryption_key()
    aesgcm = AESGCM(key)

    # Generer un IV unique de 12 bytes (recommande pour GCM)
    iv = os.urandom(12)

    # Chiffrer le secret
    plaintext = secret.encode("utf-8")
    ciphertext = aesgcm.encrypt(iv, plaintext, None)

    # Combiner IV + ciphertext (le tag est inclus dans ciphertext par AESGCM)
    encrypted = iv + ciphertext

    # Encoder en base64 pour stockage
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """
    Dechiffre un secret TOTP chiffre avec AES-256-GCM.

    Verifie l'integrite du secret grace au tag GCM.

    Args:
        encrypted_secret: Secret chiffre en base64

    Returns:
        Secret TOTP en clair (base32)

    Raises:
        ValueError: Si le secret est invalide ou corrompu
    """
    if not encrypted_secret:
        raise ValueError("Le secret chiffre ne peut pas etre vide")

    try:
        key = _get_encryption_key()
        aesgcm = AESGCM(key)

        # Decoder le base64
        encrypted = base64.b64decode(encrypted_secret)

        # Extraire l'IV (12 premiers bytes)
        iv = encrypted[:12]
        ciphertext = encrypted[12:]

        # Dechiffrer (verifie aussi l'integrite via le tag)
        plaintext = aesgcm.decrypt(iv, ciphertext, None)

        return plaintext.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Impossible de dechiffrer le secret: {e}")


def is_encrypted_secret(secret: str) -> bool:
    """
    Detecte si un secret est chiffre ou en clair.

    Un secret chiffre est en base64 et plus long qu'un secret TOTP standard.

    Args:
        secret: Secret a verifier

    Returns:
        True si le secret semble chiffre
    """
    if not secret:
        return False

    # Un secret TOTP base32 standard fait 32 chars et ne contient que A-Z, 2-7
    # Un secret chiffre est en base64 et fait ~50+ chars (12 IV + 32 secret + 16 tag)
    if len(secret) <= 40:
        # Probablement un secret base32 non chiffre
        return False

    try:
        # Essayer de decoder en base64
        decoded = base64.b64decode(secret)
        # Minimum: 12 (IV) + 1 (data) + 16 (tag) = 29 bytes
        return len(decoded) >= 29
    except Exception:
        return False
