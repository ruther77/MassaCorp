"""
Factories FactoryBoy pour les tests.

Ces factories permettent de créer des objets de test de manière
indépendante du seed de données, avec des valeurs réalistes.

Usage:
    from tests.factories import UserFactory, TenantFactory

    tenant = TenantFactory.create()
    user = UserFactory.create(tenant=tenant)

    # Ou avec session DB
    user = UserFactory.create(tenant=tenant)
"""
from tests.factories.tenant import TenantFactory
from tests.factories.user import UserFactory
from tests.factories.session import SessionFactory, RefreshTokenFactory
from tests.factories.mfa import MFASecretFactory, MFARecoveryCodeFactory
from tests.factories.api_key import APIKeyFactory

__all__ = [
    "TenantFactory",
    "UserFactory",
    "SessionFactory",
    "RefreshTokenFactory",
    "MFASecretFactory",
    "MFARecoveryCodeFactory",
    "APIKeyFactory",
]
