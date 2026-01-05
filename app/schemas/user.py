"""
Schemas Pydantic pour les utilisateurs
CRUD, profil, admin
"""
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import BaseSchema, TimestampSchema


class UserBase(BaseSchema):
    """Champs communs pour User"""
    email: EmailStr = Field(..., description="Adresse email")
    first_name: Optional[str] = Field(None, max_length=100, description="Prenom")
    last_name: Optional[str] = Field(None, max_length=100, description="Nom")
    phone: Optional[str] = Field(None, max_length=20, description="Telephone")

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.strip()
        return v


class UserCreate(UserBase):
    """Schema pour creation d'utilisateur"""
    password: str = Field(..., min_length=8, description="Mot de passe")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        from app.core.security import validate_password_strength
        validate_password_strength(v)
        return v


class UserCreateByAdmin(UserCreate):
    """Schema pour creation par admin (champs supplementaires)"""
    is_active: bool = Field(default=True, description="Compte actif")
    is_verified: bool = Field(default=False, description="Email verifie")
    is_superuser: bool = Field(default=False, description="Superuser")


class UserUpdate(BaseSchema):
    """Schema pour mise a jour d'utilisateur"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.strip()
        return v


class UserUpdateByAdmin(UserUpdate):
    """Schema pour mise a jour par admin"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.lower().strip()
        return v


class UserRead(TimestampSchema):
    """Schema de lecture utilisateur (public)"""
    id: int
    tenant_id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False


class UserReadFull(UserRead):
    """Schema de lecture utilisateur (admin)"""
    is_superuser: bool = False
    phone: Optional[str] = None
    last_login_at: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    has_password: bool = True
    has_mfa: bool = False


class UserInDB(UserRead):
    """Schema utilisateur avec hash (interne)"""
    password_hash: Optional[str] = None


class UserProfile(BaseSchema):
    """Profil utilisateur pour /me"""
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_verified: bool = False
    has_mfa: bool = False
    tenant_id: int
    tenant_name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class UserList(BaseSchema):
    """Liste d'utilisateurs avec count"""
    users: list[UserRead] = []
    total: int = 0


class TenantBase(BaseSchema):
    """Champs communs pour Tenant"""
    name: str = Field(..., min_length=1, max_length=100, description="Nom du tenant")
    slug: str = Field(..., min_length=1, max_length=50, description="Slug unique")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re
        v = v.lower().strip()
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", v):
            raise ValueError("Slug invalide: uniquement lettres minuscules, chiffres et tirets")
        return v


class TenantCreate(TenantBase):
    """Schema creation tenant"""
    settings: Optional[dict] = Field(default_factory=dict)


class TenantRead(TimestampSchema):
    """Schema lecture tenant"""
    id: int
    name: str
    slug: str
    is_active: bool = True
    settings: Optional[dict] = None
    user_count: Optional[int] = None
