"""
Factories pour créer des objets Session et RefreshToken de test.
"""
import uuid
from datetime import datetime, timedelta, timezone

import factory
from factory import Faker, Sequence, SubFactory, LazyAttribute, LazyFunction

from app.models.session import Session, RefreshToken
from app.core.security import hash_token
from tests.factories.user import UserFactory


class SessionFactory(factory.Factory):
    """
    Factory pour créer des Session de test.

    Usage:
        session = SessionFactory.create()
        session = SessionFactory.create(user=existing_user)
    """

    class Meta:
        model = Session
        exclude = ("user",)  # Exclude user from model kwargs

    id = LazyFunction(uuid.uuid4)
    user_id = LazyAttribute(lambda o: o.user.id if o.user else 1)
    tenant_id = LazyAttribute(lambda o: o.user.tenant_id if o.user else 1)
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = LazyFunction(lambda: datetime.now(timezone.utc))
    last_seen_at = LazyFunction(lambda: datetime.now(timezone.utc))
    ip = Faker("ipv4")
    user_agent = Faker("user_agent")
    revoked_at = None
    absolute_expiry = LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=30)
    )

    # Relation optionnelle vers User (excluded from model)
    user = SubFactory(UserFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB et le user.
        """
        db_session = kwargs.pop("db_session", None)
        user = kwargs.pop("user", None)

        if user:
            kwargs["user_id"] = user.id
            kwargs["tenant_id"] = user.tenant_id

        obj = super()._create(model_class, *args, **kwargs)

        if db_session:
            db_session.add(obj)
            db_session.flush()

        return obj

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        """
        Override _build to exclude user from model kwargs.
        """
        kwargs.pop("user", None)
        return super()._build(model_class, *args, **kwargs)

    @classmethod
    def create_revoked(cls, **kwargs):
        """
        Crée une session révoquée.
        """
        kwargs["revoked_at"] = datetime.now(timezone.utc)
        return cls.create(**kwargs)

    @classmethod
    def create_expired(cls, **kwargs):
        """
        Crée une session expirée.
        """
        kwargs["absolute_expiry"] = datetime.now(timezone.utc) - timedelta(days=1)
        return cls.create(**kwargs)


class RefreshTokenFactory(factory.Factory):
    """
    Factory pour créer des RefreshToken de test.

    Usage:
        token = RefreshTokenFactory.create()
        token = RefreshTokenFactory.create(session=existing_session)
    """

    class Meta:
        model = RefreshToken
        exclude = ("session",)  # Exclude session from model kwargs

    jti = LazyFunction(lambda: str(uuid.uuid4()))
    session_id = LazyAttribute(lambda o: o.session.id if o.session else None)
    token_hash = LazyFunction(lambda: hash_token(str(uuid.uuid4())))
    expires_at = LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )
    created_at = LazyFunction(lambda: datetime.now(timezone.utc))
    used_at = None
    replaced_by_jti = None

    # Relation optionnelle vers Session (excluded from model)
    session = SubFactory(SessionFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB.
        """
        db_session = kwargs.pop("db_session", None)
        session = kwargs.pop("session", None)

        if session:
            kwargs["session_id"] = session.id

        obj = super()._create(model_class, *args, **kwargs)

        if db_session:
            db_session.add(obj)
            db_session.flush()

        return obj

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        """
        Override _build to exclude session from model kwargs.
        """
        kwargs.pop("session", None)
        return super()._build(model_class, *args, **kwargs)

    @classmethod
    def create_used(cls, **kwargs):
        """
        Crée un refresh token déjà utilisé.
        """
        kwargs["used_at"] = datetime.now(timezone.utc)
        return cls.create(**kwargs)

    @classmethod
    def create_expired(cls, **kwargs):
        """
        Crée un refresh token expiré.
        """
        kwargs["expires_at"] = datetime.now(timezone.utc) - timedelta(days=1)
        return cls.create(**kwargs)
