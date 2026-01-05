"""
Configuration du logging structure pour MassaCorp.

Fournit un logging JSON structure avec:
- Sanitization des donnees sensibles
- Request ID et Tenant ID dans tous les logs
- Timestamps ISO 8601 UTC
- Niveaux de log coherents

Usage:
    from app.core.logging import get_logger, sanitize_dict

    logger = get_logger(__name__)
    logger.info("User action", user_id=123, tenant_id=1)
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Set
from contextvars import ContextVar

# Context variables pour request_id et tenant_id
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[int] = ContextVar("tenant_id", default=0)
user_id_var: ContextVar[int] = ContextVar("user_id", default=0)


# =============================================================================
# Sanitization des donnees sensibles
# =============================================================================

SENSITIVE_FIELDS: Set[str] = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
    "cookie",
    "session_id",
    "credit_card",
    "card_number",
    "cvv",
    "ssn",
    "social_security",
    "private_key",
    "encryption_key",
    # Note: "email" removed - emails are NOT redacted but can be masked using mask_email()
    # for GDPR compliance if needed in specific contexts
}

REDACTED = "[REDACTED]"


def sanitize_value(key: str, value: Any) -> Any:
    """
    Sanitize une valeur si la cle est sensible.

    Args:
        key: Nom du champ
        value: Valeur a verifier

    Returns:
        Valeur originale ou "[REDACTED]"
    """
    key_lower = key.lower()

    # Verifier si le champ est sensible
    if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
        if isinstance(value, str) and len(value) > 8:
            # Garder les 4 premiers caracteres pour debug
            return f"{value[:4]}...{REDACTED}"
        return REDACTED

    return value


def mask_email(email: str) -> str:
    """
    Masque un email pour les logs.
    """
    if not email or "@" not in email:
        return email or ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = f"{local[:1]}*"
    else:
        masked_local = f"{local[:1]}{'*' * (len(local) - 2)}{local[-1:]}"
    return f"{masked_local}@{domain}"


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize un dictionnaire en masquant les champs sensibles.

    Args:
        data: Dictionnaire a sanitizer

    Returns:
        Dictionnaire avec les valeurs sensibles masquees
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = sanitize_value(key, value)

    return result


# =============================================================================
# JSON Formatter pour structured logging
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    Formatter qui produit des logs JSON structures.

    Inclut automatiquement:
    - timestamp ISO 8601 UTC
    - level
    - logger name
    - message
    - request_id (si disponible)
    - tenant_id (si disponible)
    - user_id (si disponible)
    - extra fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """Formate le log record en JSON."""
        # Base log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Ajouter request_id si disponible
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Ajouter tenant_id si disponible
        tenant_id = tenant_id_var.get()
        if tenant_id:
            log_entry["tenant_id"] = tenant_id

        # Ajouter user_id si disponible
        user_id = user_id_var.get()
        if user_id:
            log_entry["user_id"] = user_id

        # Ajouter les extra fields (sanitized)
        if hasattr(record, "__dict__"):
            extra_fields = {}
            skip_fields = {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "asctime"
            }

            for key, value in record.__dict__.items():
                if key not in skip_fields and not key.startswith("_"):
                    extra_fields[key] = value

            if extra_fields:
                log_entry["extra"] = sanitize_dict(extra_fields)

        # Ajouter exception info si presente
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """
    Formatter lisible pour la console en developpement.

    Format: [LEVEL] logger - message (request_id=xxx)
    """

    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Formate le log record pour la console."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        # Build message
        parts = [
            f"{color}[{record.levelname}]{reset}",
            record.name,
            "-",
            record.getMessage(),
        ]

        # Ajouter request_id si disponible
        request_id = request_id_var.get()
        if request_id:
            parts.append(f"(request_id={request_id[:8]}...)")

        return " ".join(parts)


# =============================================================================
# Configuration du logging
# =============================================================================

def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    include_console: bool = True
) -> None:
    """
    Configure le logging pour l'application.

    Args:
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Si True, utilise le format JSON
        include_console: Si True, ajoute un handler console
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Supprimer les handlers existants
    root_logger.handlers.clear()

    # Handler principal
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(handler)

    # Reduire le bruit des librairies tierces
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger configure.

    Args:
        name: Nom du logger (typiquement __name__)

    Returns:
        Logger configure
    """
    return logging.getLogger(name)


# =============================================================================
# Context managers pour request context
# =============================================================================

def set_request_context(
    request_id: str = None,
    tenant_id: int = None,
    user_id: int = None
) -> None:
    """
    Set le contexte de la requete pour les logs.

    Args:
        request_id: ID de la requete
        tenant_id: ID du tenant
        user_id: ID de l'utilisateur
    """
    if request_id:
        request_id_var.set(request_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context() -> None:
    """Clear le contexte de la requete."""
    request_id_var.set("")
    tenant_id_var.set(0)
    user_id_var.set(0)
