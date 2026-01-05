"""
Factory pour créer des objets User de test.
"""
import factory
from factory import Faker, Sequence, SubFactory, LazyAttribute

from app.models.user import User
from app.core.security import hash_password
from tests.factories.tenant import TenantFactory


# Mot de passe par défaut pour les tests (non compromis dans HIBP)
DEFAULT_TEST_PASSWORD = "MassaCorp2024$xK7vQ!"


class UserFactory(factory.Factory):
    """
    Factory pour créer des User de test.

    Usage:
        user = UserFactory.create()
        user = UserFactory.create(tenant=existing_tenant)
        user = UserFactory.create(is_superuser=True)

    Notes:
        - Le mot de passe par défaut est: MassaCorp2024$xK7vQ!
        - Le password_hash est auto-généré avec bcrypt
    """

    class Meta:
        model = User
        exclude = ("tenant",)  # Exclude tenant from model kwargs

    id = Sequence(lambda n: n + 1000)  # Start at 1000 to avoid conflicts
    tenant_id = LazyAttribute(lambda o: o.tenant.id if o.tenant else 1)
    email = Sequence(lambda n: f"user{n}@test.massacorp.dev")
    password_hash = factory.LazyFunction(lambda: hash_password(DEFAULT_TEST_PASSWORD))
    is_active = True
    is_verified = True
    is_superuser = False
    mfa_required = False
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    phone = None
    last_login_at = None
    password_changed_at = None

    # Relation optionnelle vers Tenant (excluded from model)
    tenant = SubFactory(TenantFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB et le tenant.
        """
        db_session = kwargs.pop("db_session", None)
        tenant = kwargs.pop("tenant", None)

        if tenant:
            kwargs["tenant_id"] = tenant.id

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
    def create_with_password(cls, password: str, **kwargs):
        """
        Crée un utilisateur avec un mot de passe spécifique.

        Args:
            password: Mot de passe en clair
            **kwargs: Autres paramètres pour l'utilisateur
        """
        kwargs["password_hash"] = hash_password(password)
        return cls.create(**kwargs)


class UserDictFactory(factory.DictFactory):
    """
    Factory pour créer des dictionnaires User (pour API tests).
    """

    email = Sequence(lambda n: f"user{n}@test.massacorp.dev")
    password = DEFAULT_TEST_PASSWORD
    first_name = Faker("first_name")
    last_name = Faker("last_name")


class AdminUserFactory(UserFactory):
    """
    Factory pour créer des utilisateurs admin de test.
    """

    is_superuser = True
    email = Sequence(lambda n: f"admin{n}@test.massacorp.dev")


class UnverifiedUserFactory(UserFactory):
    """
    Factory pour créer des utilisateurs non vérifiés.
    """

    is_verified = False
    email = Sequence(lambda n: f"unverified{n}@test.massacorp.dev")


class InactiveUserFactory(UserFactory):
    """
    Factory pour créer des utilisateurs désactivés.
    """

    is_active = False
    email = Sequence(lambda n: f"inactive{n}@test.massacorp.dev")
