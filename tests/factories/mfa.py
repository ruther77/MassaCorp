"""
Factories pour créer des objets MFA de test.
"""
import pyotp
import factory
from factory import Faker, Sequence, SubFactory, LazyAttribute, LazyFunction

from app.models.mfa import MFASecret, MFARecoveryCode
from app.core.security import hash_password
from tests.factories.user import UserFactory


class MFASecretFactory(factory.Factory):
    """
    Factory pour créer des MFASecret de test.

    Usage:
        mfa = MFASecretFactory.create()
        mfa = MFASecretFactory.create(user=existing_user, enabled=True)
    """

    class Meta:
        model = MFASecret
        exclude = ("user",)  # Exclude user from model kwargs

    user_id = LazyAttribute(lambda o: o.user.id if o.user else 1)
    tenant_id = LazyAttribute(lambda o: o.user.tenant_id if o.user else 1)
    secret = LazyFunction(pyotp.random_base32)
    enabled = False
    last_totp_window = None

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
        Override _build to also exclude user from model kwargs.
        """
        kwargs.pop("user", None)
        return super()._build(model_class, *args, **kwargs)

    @classmethod
    def create_enabled(cls, **kwargs):
        """
        Crée un MFASecret activé.
        """
        kwargs["enabled"] = True
        return cls.create(**kwargs)


class MFARecoveryCodeFactory(factory.Factory):
    """
    Factory pour créer des MFARecoveryCode de test.

    Usage:
        code = MFARecoveryCodeFactory.create()
        code = MFARecoveryCodeFactory.create(user=existing_user)
    """

    class Meta:
        model = MFARecoveryCode
        exclude = ("user",)  # Exclude user from model kwargs

    id = Sequence(lambda n: n + 1000)
    user_id = LazyAttribute(lambda o: o.user.id if o.user else 1)
    code_hash = LazyFunction(lambda: hash_password("RECOVERY-CODE-TEST"))
    used_at = None

    # Relation optionnelle vers User (excluded from model)
    user = SubFactory(UserFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB et le user.
        """
        db_session = kwargs.pop("db_session", None)
        user = kwargs.pop("user", None)
        plain_code = kwargs.pop("plain_code", None)

        if user:
            kwargs["user_id"] = user.id

        if plain_code:
            kwargs["code_hash"] = hash_password(plain_code)

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
        kwargs.pop("plain_code", None)
        return super()._build(model_class, *args, **kwargs)

    @classmethod
    def create_used(cls, **kwargs):
        """
        Crée un code de récupération déjà utilisé.
        """
        from datetime import datetime, timezone
        kwargs["used_at"] = datetime.now(timezone.utc)
        return cls.create(**kwargs)

    @classmethod
    def create_batch_for_user(cls, user, count: int = 10, db_session=None):
        """
        Crée plusieurs codes de récupération pour un utilisateur.
        Retourne une liste de tuples (code_object, plain_code).
        """
        import secrets
        codes = []
        for _ in range(count):
            plain_code = f"RCVRY-{secrets.token_hex(4).upper()}"
            code_obj = cls.create(
                user=user,
                plain_code=plain_code,
                db_session=db_session
            )
            codes.append((code_obj, plain_code))
        return codes
