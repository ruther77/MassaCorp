"""
Factory pour créer des objets APIKey de test.
"""
import secrets
from datetime import datetime, timedelta, timezone

import factory
from factory import Faker, Sequence, SubFactory, LazyAttribute, LazyFunction

from app.models.api_key import APIKey
from app.core.security import hash_token
from tests.factories.tenant import TenantFactory


def generate_api_key():
    """Génère une clé API au format prefix_secret."""
    prefix = secrets.token_hex(4)  # 8 chars
    secret = secrets.token_hex(16)  # 32 chars
    return f"mc_{prefix}_{secret}"


class APIKeyFactory(factory.Factory):
    """
    Factory pour créer des APIKey de test.

    Usage:
        api_key = APIKeyFactory.create()
        api_key = APIKeyFactory.create(tenant=existing_tenant)
    """

    class Meta:
        model = APIKey
        exclude = ("tenant",)  # Exclude tenant from model kwargs

    id = Sequence(lambda n: n + 1000)
    tenant_id = LazyAttribute(lambda o: o.tenant.id if o.tenant else 1)
    name = Faker("bs")
    key_prefix = LazyFunction(lambda: secrets.token_hex(4))
    key_hash = LazyFunction(lambda: hash_token(generate_api_key()))
    scopes = factory.LazyFunction(lambda: ["users:read"])
    revoked_at = None
    created_by_user_id = None
    expires_at = LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=365)
    )
    last_used_at = None

    # Relation optionnelle vers Tenant (excluded from model)
    tenant = SubFactory(TenantFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB et le tenant.
        """
        db_session = kwargs.pop("db_session", None)
        tenant = kwargs.pop("tenant", None)
        plain_key = kwargs.pop("plain_key", None)

        if tenant:
            kwargs["tenant_id"] = tenant.id

        # Générer une vraie clé si demandé
        if plain_key is None:
            plain_key = generate_api_key()
            kwargs["key_hash"] = hash_token(plain_key)
            kwargs["key_prefix"] = plain_key.split("_")[1] if "_" in plain_key else plain_key[:8]

        obj = super()._create(model_class, *args, **kwargs)

        if db_session:
            db_session.add(obj)
            db_session.flush()

        return obj

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        """
        Override _build to exclude tenant from model kwargs.
        """
        kwargs.pop("tenant", None)
        return super()._build(model_class, *args, **kwargs)

    @classmethod
    def create_expired(cls, **kwargs):
        """
        Crée une clé API expirée.
        """
        kwargs["expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
        return cls.create(**kwargs)

    @classmethod
    def create_revoked(cls, **kwargs):
        """
        Crée une clé API révoquée.
        """
        kwargs["revoked_at"] = datetime.now(timezone.utc)
        return cls.create(**kwargs)

    @classmethod
    def create_with_scopes(cls, scopes: list, **kwargs):
        """
        Crée une clé API avec des scopes spécifiques.
        """
        kwargs["scopes"] = scopes
        return cls.create(**kwargs)
