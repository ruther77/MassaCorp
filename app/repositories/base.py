"""
Base Repository generique pour MassaCorp API
Fournit les operations CRUD de base pour tous les models

Ce module contient:
- BaseRepository: Operations CRUD sans isolation tenant (pour Tenant, etc.)
- TenantAwareBaseRepository: Operations CRUD avec isolation tenant OBLIGATOIRE

SECURITE CRITIQUE:
Pour TOUS les models avec tenant_id, utiliser TenantAwareBaseRepository.
BaseRepository ne doit etre utilise QUE pour les entites globales (Tenant).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session, Query

from app.models.base import Base

logger = logging.getLogger(__name__)

# Type generique pour le model
ModelType = TypeVar("ModelType", bound=Base)

# Constantes de pagination
MAX_PAGE_SIZE = 100  # Limite absolue par requete
DEFAULT_PAGE_SIZE = 20  # Taille par defaut


@dataclass
class PaginatedResult(Generic[ModelType]):
    """
    Resultat pagine avec metadonnees.

    Attributes:
        items: Liste des elements de la page courante
        total: Nombre total d'elements
        page: Numero de page (1-indexed)
        page_size: Taille de la page
        total_pages: Nombre total de pages
        has_next: True si une page suivante existe
        has_prev: True si une page precedente existe
    """
    items: List[ModelType]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calcule le nombre total de pages."""
        return (self.total + self.page_size - 1) // self.page_size if self.total > 0 else 0

    @property
    def has_next(self) -> bool:
        """True si une page suivante existe."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """True si une page precedente existe."""
        return self.page > 1


class RepositoryException(Exception):
    """Exception de base pour les repositories"""
    pass


class PaginationError(RepositoryException):
    """Erreur de pagination (page invalide, taille trop grande)"""
    pass


class TenantIsolationError(RepositoryException):
    """Erreur de violation d'isolation multi-tenant"""
    pass


class BaseRepository(Generic[ModelType]):
    """
    Repository generique avec operations CRUD

    Usage:
        class UserRepository(BaseRepository[User]):
            pass
    """

    # Type du model - doit etre defini dans les sous-classes
    model: Type[ModelType]

    def __init__(self, session: Session):
        """
        Initialise le repository avec une session DB

        Args:
            session: Session SQLAlchemy active
        """
        self.session = session

    def get(self, id: int) -> Optional[ModelType]:
        """
        Recupere un objet par son ID

        Args:
            id: ID de l'objet

        Returns:
            L'objet trouve ou None
        """
        return self.session.query(self.model).filter(self.model.id == id).first()

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """
        Alias pour get() - recupere un objet par son ID

        Args:
            id: ID de l'objet

        Returns:
            L'objet trouve ou None
        """
        return self.get(id)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Recupere tous les objets avec pagination

        Args:
            skip: Nombre d'objets a sauter (offset)
            limit: Nombre maximum d'objets a retourner

        Returns:
            Liste des objets
        """
        return (
            self.session.query(self.model)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Cree un nouvel objet

        Args:
            data: Dictionnaire avec les donnees de l'objet

        Returns:
            L'objet cree
        """
        obj = self.model(**data)
        self.session.add(obj)
        self.session.flush()  # Pour obtenir l'ID
        return obj

    def update(
        self,
        id: int,
        data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """
        Met a jour un objet existant

        Args:
            id: ID de l'objet a mettre a jour
            data: Dictionnaire avec les nouvelles donnees

        Returns:
            L'objet mis a jour ou None si non trouve
        """
        obj = self.get_by_id(id)
        if obj is None:
            return None

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        self.session.flush()
        return obj

    def delete(self, id: int) -> bool:
        """
        Supprime un objet par son ID

        Args:
            id: ID de l'objet a supprimer

        Returns:
            True si supprime, False si non trouve
        """
        obj = self.get_by_id(id)
        if obj is None:
            return False

        self.session.delete(obj)
        self.session.flush()
        return True

    def count(self) -> int:
        """
        Compte le nombre total d'objets

        Returns:
            Nombre d'objets
        """
        return self.session.query(func.count(self.model.id)).scalar() or 0

    def exists(self, id: int) -> bool:
        """
        Verifie si un objet existe

        Args:
            id: ID de l'objet

        Returns:
            True si existe, False sinon
        """
        return self.get_by_id(id) is not None

    def paginate(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        query: Optional[Query] = None
    ) -> PaginatedResult[ModelType]:
        """
        Recupere une page de resultats avec metadonnees.

        Methode OBLIGATOIRE pour les listes - evite les requetes non bornees.

        Args:
            page: Numero de page (1-indexed, defaut 1)
            page_size: Nombre d'elements par page (defaut 20, max 100)
            query: Query SQLAlchemy optionnelle (defaut: tous les objets)

        Returns:
            PaginatedResult avec items, total, et metadonnees

        Raises:
            PaginationError: Si page < 1 ou page_size > MAX_PAGE_SIZE
        """
        # Validation des parametres
        if page < 1:
            raise PaginationError(f"Page doit etre >= 1, recu: {page}")

        if page_size > MAX_PAGE_SIZE:
            raise PaginationError(
                f"page_size maximum est {MAX_PAGE_SIZE}, recu: {page_size}"
            )

        if page_size < 1:
            raise PaginationError(f"page_size doit etre >= 1, recu: {page_size}")

        # Query par defaut si non fournie
        if query is None:
            query = self.session.query(self.model)

        # Compter le total
        total = query.count()

        # Calculer l'offset
        offset = (page - 1) * page_size

        # Recuperer les items
        items = query.offset(offset).limit(page_size).all()

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

    def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedResult[ModelType]:
        """
        Alias pour paginate() - recupere tous les objets de facon paginee.

        Args:
            page: Numero de page (1-indexed)
            page_size: Nombre d'elements par page

        Returns:
            PaginatedResult avec les items et metadonnees
        """
        return self.paginate(page=page, page_size=page_size)


class TenantAwareBaseRepository(Generic[ModelType]):
    """
    Repository avec isolation multi-tenant OBLIGATOIRE.

    TOUTES les operations sont automatiquement filtrees par tenant_id.
    Impossible d'acceder aux donnees d'un autre tenant.

    SECURITE CRITIQUE:
    - Le tenant_id est requis a l'initialisation
    - AUCUNE operation ne peut contourner le filtrage tenant
    - Toute tentative d'acces cross-tenant leve une erreur

    Usage:
        class UserRepository(TenantAwareBaseRepository[User]):
            model = User

        repo = UserRepository(session, tenant_id=1)
        user = repo.get(42)  # Retourne seulement si user.tenant_id == 1
    """

    # Type du model - doit etre defini dans les sous-classes
    model: Type[ModelType]

    def __init__(self, session: Session, tenant_id: int):
        """
        Initialise le repository avec session et tenant_id OBLIGATOIRE.

        Args:
            session: Session SQLAlchemy active
            tenant_id: ID du tenant pour TOUTES les operations

        Raises:
            TenantIsolationError: Si le model n'a pas d'attribut tenant_id
        """
        self.session = session
        self._tenant_id = tenant_id

        # Verification a l'initialisation que le model supporte le multi-tenant
        if not hasattr(self.model, 'tenant_id'):
            raise TenantIsolationError(
                f"Le model {self.model.__name__} n'a pas d'attribut tenant_id. "
                "Utilisez BaseRepository pour les entites globales (Tenant)."
            )

        logger.debug(
            f"TenantAwareBaseRepository initialise pour {self.model.__name__} "
            f"avec tenant_id={tenant_id}"
        )

    @property
    def tenant_id(self) -> int:
        """Retourne le tenant_id (lecture seule)."""
        return self._tenant_id

    def _tenant_query(self) -> Query:
        """
        Retourne une Query pre-filtree par tenant_id.

        METHODE PRIVEE - toutes les operations DOIVENT l'utiliser.
        """
        return self.session.query(self.model).filter(
            self.model.tenant_id == self._tenant_id
        )

    def get(self, id: int) -> Optional[ModelType]:
        """
        Recupere un objet par ID avec isolation tenant.

        Args:
            id: ID de l'objet

        Returns:
            L'objet trouve ou None (si non trouve OU autre tenant)
        """
        return self._tenant_query().filter(self.model.id == id).first()

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Alias pour get() - recupere un objet par ID avec isolation tenant."""
        return self.get(id)

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Recupere tous les objets du tenant avec pagination.

        Args:
            skip: Nombre d'objets a sauter (offset)
            limit: Nombre maximum d'objets a retourner

        Returns:
            Liste des objets du tenant courant uniquement
        """
        return (
            self._tenant_query()
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> ModelType:
        """
        Cree un nouvel objet avec tenant_id force.

        Le tenant_id est TOUJOURS celui du repository, meme si
        un tenant_id different est passe dans data.

        Args:
            data: Dictionnaire avec les donnees de l'objet

        Returns:
            L'objet cree avec le tenant_id du repository
        """
        # SECURITE: Forcer le tenant_id meme si passe dans data
        data_with_tenant = {**data, "tenant_id": self._tenant_id}

        obj = self.model(**data_with_tenant)
        self.session.add(obj)
        self.session.flush()
        return obj

    def update(
        self,
        id: int,
        data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """
        Met a jour un objet existant avec verification tenant.

        SECURITE: Le tenant_id ne peut JAMAIS etre modifie.

        Args:
            id: ID de l'objet a mettre a jour
            data: Dictionnaire avec les nouvelles donnees

        Returns:
            L'objet mis a jour ou None si non trouve (ou autre tenant)
        """
        obj = self.get(id)  # Utilise _tenant_query() automatiquement
        if obj is None:
            return None

        # SECURITE: Empecher toute modification du tenant_id
        if "tenant_id" in data:
            logger.warning(
                f"Tentative de modification de tenant_id ignoree pour "
                f"{self.model.__name__} id={id}"
            )
            data = {k: v for k, v in data.items() if k != "tenant_id"}

        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

        self.session.flush()
        return obj

    def delete(self, id: int) -> bool:
        """
        Supprime un objet avec verification tenant.

        Args:
            id: ID de l'objet a supprimer

        Returns:
            True si supprime, False si non trouve (ou autre tenant)
        """
        obj = self.get(id)  # Utilise _tenant_query() automatiquement
        if obj is None:
            return False

        self.session.delete(obj)
        self.session.flush()
        return True

    def count(self) -> int:
        """
        Compte le nombre d'objets du tenant courant.

        Returns:
            Nombre d'objets appartenant au tenant
        """
        return self._tenant_query().count()

    def exists(self, id: int) -> bool:
        """
        Verifie si un objet existe dans le tenant courant.

        Args:
            id: ID de l'objet

        Returns:
            True si existe dans ce tenant, False sinon
        """
        return self.get(id) is not None

    def paginate(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        query: Optional[Query] = None
    ) -> PaginatedResult[ModelType]:
        """
        Recupere une page de resultats avec isolation tenant.

        Args:
            page: Numero de page (1-indexed, defaut 1)
            page_size: Nombre d'elements par page (defaut 20, max 100)
            query: Query personnalisee (doit deja inclure le filtrage tenant!)

        Returns:
            PaginatedResult avec items du tenant courant uniquement

        Raises:
            PaginationError: Si page < 1 ou page_size > MAX_PAGE_SIZE
        """
        # Validation des parametres
        if page < 1:
            raise PaginationError(f"Page doit etre >= 1, recu: {page}")

        if page_size > MAX_PAGE_SIZE:
            raise PaginationError(
                f"page_size maximum est {MAX_PAGE_SIZE}, recu: {page_size}"
            )

        if page_size < 1:
            raise PaginationError(f"page_size doit etre >= 1, recu: {page_size}")

        # SECURITE: Query par defaut avec filtrage tenant
        if query is None:
            query = self._tenant_query()

        # Compter le total
        total = query.count()

        # Calculer l'offset
        offset = (page - 1) * page_size

        # Recuperer les items
        items = query.offset(offset).limit(page_size).all()

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

    def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedResult[ModelType]:
        """
        Alias pour paginate() - recupere objets du tenant de facon paginee.

        Args:
            page: Numero de page (1-indexed)
            page_size: Nombre d'elements par page

        Returns:
            PaginatedResult avec les items du tenant courant
        """
        return self.paginate(page=page, page_size=page_size)

    def filter_by(self, **kwargs) -> List[ModelType]:
        """
        Filtre les objets du tenant par attributs.

        Args:
            **kwargs: Attributs a filtrer (ex: is_active=True)

        Returns:
            Liste des objets correspondants dans le tenant courant
        """
        query = self._tenant_query()
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.all()

    def first_by(self, **kwargs) -> Optional[ModelType]:
        """
        Retourne le premier objet du tenant correspondant aux criteres.

        Args:
            **kwargs: Attributs a filtrer

        Returns:
            Premier objet correspondant ou None
        """
        query = self._tenant_query()
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.first()
