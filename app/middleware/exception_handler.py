"""
Exception Handler pour MassaCorp API.

Gere de maniere uniforme toutes les exceptions applicatives
et les convertit en responses JSON standardisees.
"""
import logging
from typing import Union

from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def create_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict = None,
    request_id: str = None
) -> JSONResponse:
    """
    Cree une response d'erreur standardisee.

    Args:
        status_code: Code HTTP
        error_code: Code d'erreur applicatif
        message: Message d'erreur
        details: Details supplementaires
        request_id: ID de la requete pour tracabilite

    Returns:
        JSONResponse formatee
    """
    content = {
        "error": error_code,
        "message": message,
    }

    if details:
        content["details"] = details

    if request_id:
        content["request_id"] = request_id

    return JSONResponse(
        status_code=status_code,
        content=content
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handler pour les exceptions applicatives custom.

    Convertit AppException en response JSON standardisee.
    """
    request_id = getattr(request.state, "request_id", None)

    # Log selon la severite
    if exc.status_code >= 500:
        logger.error(
            f"AppException: {exc.error_code} - {exc.message}",
            extra={"request_id": request_id, "details": exc.details}
        )
    else:
        logger.info(
            f"AppException: {exc.error_code} - {exc.message}",
            extra={"request_id": request_id}
        )

    return create_error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details if exc.details else None,
        request_id=request_id
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handler pour les HTTPException standard de FastAPI/Starlette.
    """
    request_id = getattr(request.state, "request_id", None)

    # Mapper les codes HTTP courants vers des error_code
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
    }

    error_code = error_codes.get(exc.status_code, "HTTP_ERROR")

    return create_error_response(
        status_code=exc.status_code,
        error_code=error_code,
        message=str(exc.detail),
        request_id=request_id
    )


async def validation_exception_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handler pour les erreurs de validation Pydantic.
    """
    request_id = getattr(request.state, "request_id", None)

    # Extraire les erreurs de validation
    errors = exc.errors() if hasattr(exc, "errors") else []

    # Formater les erreurs
    formatted_errors = []
    for error in errors:
        loc = ".".join(str(l) for l in error.get("loc", []))
        formatted_errors.append({
            "field": loc,
            "message": error.get("msg", "Validation error"),
            "type": error.get("type", "unknown")
        })

    return create_error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": formatted_errors},
        request_id=request_id
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler catch-all pour les exceptions non gerees.

    SECURITE: Ne jamais exposer les details de l'exception en production.

    Categorise les exceptions pour un meilleur debugging:
    - Erreurs DB/reseau: log ERROR (recuperables)
    - Bugs code: log CRITICAL (a corriger immediatement)
    """
    request_id = getattr(request.state, "request_id", None)
    exc_type = type(exc).__name__
    exc_module = type(exc).__module__

    # Categoriser l'exception pour un meilleur logging
    # Erreurs infrastructure (DB, Redis, reseau) - recuperables
    infra_exceptions = (
        "OperationalError", "InterfaceError", "DatabaseError",
        "ConnectionError", "TimeoutError", "RedisError",
        "ConnectionRefusedError", "BrokenPipeError"
    )

    if exc_type in infra_exceptions or "sqlalchemy" in exc_module.lower():
        # Erreur infrastructure - log ERROR (pas CRITICAL)
        logger.error(
            f"Infrastructure error: {exc_type}: {exc}",
            extra={"request_id": request_id, "category": "infrastructure"}
        )
        error_code = "SERVICE_UNAVAILABLE"
        status_code = 503
    else:
        # Bug inattendu - log CRITICAL pour investigation immediate
        logger.critical(
            f"BUG INATTENDU: {exc_type}: {exc} - A CORRIGER IMMEDIATEMENT",
            extra={"request_id": request_id, "category": "bug"},
            exc_info=True  # Stack trace complete
        )
        error_code = "INTERNAL_ERROR"
        status_code = 500

    return create_error_response(
        status_code=status_code,
        error_code=error_code,
        message="An unexpected error occurred",
        request_id=request_id
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Enregistre tous les exception handlers sur l'application.

    Args:
        app: L'instance FastAPI
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
