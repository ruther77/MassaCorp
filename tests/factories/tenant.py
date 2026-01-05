"""
Factory pour créer des objets Tenant de test.
"""
import factory
from factory import Faker, Sequence, LazyAttribute

from app.models.tenant import Tenant


class TenantFactory(factory.Factory):
    """
    Factory pour créer des Tenant de test.

    Usage:
        tenant = TenantFactory.create()
        tenant = TenantFactory.create(name="Custom Corp")
    """

    class Meta:
        model = Tenant

    id = Sequence(lambda n: n + 1000)  # Start at 1000 to avoid conflicts
    name = Faker("company")
    slug = Sequence(lambda n: f"tenant-{n}")
    is_active = True
    settings = factory.LazyFunction(dict)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override _create pour gérer la session DB si fournie.
        """
        db_session = kwargs.pop("db_session", None)
        obj = super()._create(model_class, *args, **kwargs)
        if db_session:
            db_session.add(obj)
            db_session.flush()
        return obj


class TenantDictFactory(factory.DictFactory):
    """
    Factory pour créer des dictionnaires Tenant (pour API tests).
    """

    name = Faker("company")
    slug = Sequence(lambda n: f"tenant-{n}")
    is_active = True
