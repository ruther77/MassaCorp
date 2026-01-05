"""
Schemas Pydantic de base pour MassaCorp API
Responses standards, pagination, erreurs
"""
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# Type generique pour les reponses paginates
T = TypeVar("T")


class BaseSchema(BaseModel):
    """Schema de base avec configuration commune"""

    model_config = ConfigDict(
        from_attributes=True,  # Permet la conversion depuis ORM
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",  # Rejeter les champs inconnus (securite)
    )


class TimestampSchema(BaseSchema):
    """Schema avec timestamps"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResponseBase(BaseSchema):
    """Response de base pour toutes les reponses API"""
    success: bool = True
    message: Optional[str] = None


class ErrorDetail(BaseSchema):
    """Detail d'une erreur"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseSchema):
    """Response d'erreur standard"""
    success: bool = False
    message: str
    errors: List[ErrorDetail] = []
    code: Optional[str] = None


class DataResponse(ResponseBase, Generic[T]):
    """Response avec donnees"""
    data: Optional[T] = None


class PaginationMeta(BaseSchema):
    """Metadonnees de pagination"""
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    total_items: int = Field(ge=0, default=0)
    total_pages: int = Field(ge=0, default=0)
    has_next: bool = False
    has_prev: bool = False


class PaginatedResponse(ResponseBase, Generic[T]):
    """Response paginee"""
    data: List[T] = []
    pagination: PaginationMeta


class HealthResponse(BaseSchema):
    """Response du health check"""
    status: str = "healthy"
    environment: str
    version: str = "0.1.0"
    database: Optional[str] = None
    redis: Optional[str] = None


# Helpers pour creer des responses
def success_response(data: Any = None, message: str = "Success") -> dict:
    """Cree une response de succes"""
    return {
        "success": True,
        "message": message,
        "data": data
    }


def error_response(
    message: str,
    errors: Optional[List[dict]] = None,
    code: Optional[str] = None
) -> dict:
    """Cree une response d'erreur"""
    return {
        "success": False,
        "message": message,
        "errors": errors or [],
        "code": code
    }


def paginated_response(
    items: List[Any],
    page: int,
    page_size: int,
    total_items: int
) -> dict:
    """Cree une response paginee"""
    total_pages = (total_items + page_size - 1) // page_size if page_size > 0 else 0

    return {
        "success": True,
        "data": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }
