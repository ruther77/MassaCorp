"""
Repository pour les Users
Gestion des utilisateurs avec isolation multi-tenant

IMPORTANT SECURITE:
- Pour les operations POST-authentification, utiliser TenantAwareUserRepository
- UserRepository (sans tenant) ne doit etre utilise QUE pour l'authentification
  (get_by_email_and_tenant) ou par des superusers.
"""
import logging
import warnings
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.base import BaseRepository, TenantAwareBaseRepository

logger = logging.getLogger(__name__)


class TenantAwareUserRepository(TenantAwareBaseRepository[User]):
    """
    Repository User avec isolation multi-tenant OBLIGATOIRE.

    Toutes les operations sont automatiquement filtrees par tenant_id.
    Utiliser ce repository pour TOUTES les operations post-authentification.

    Usage:
        repo = TenantAwareUserRepository(session, tenant_id=current_user.tenant_id)
        user = repo.get(42)  # Ne retourne QUE si user.tenant_id == tenant_id
    """

    model = User

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Recupere un utilisateur par email DANS le tenant courant.

        Args:
            email: Email de l'utilisateur

        Returns:
            L'utilisateur trouve ou None
        """
        return (
            self._tenant_query()
            .filter(func.lower(self.model.email) == email.lower())
            .first()
        )

    def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Recupere tous les utilisateurs actifs du tenant.

        Args:
            skip: Nombre d'utilisateurs a sauter
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs actifs du tenant
        """
        return (
            self._tenant_query()
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def verify_user(self, user_id: int) -> Optional[User]:
        """
        Marque un utilisateur comme verifie (dans ce tenant).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur verifie ou None
        """
        user = self.get(user_id)  # Utilise _tenant_query
        if user is None:
            return None

        user.is_verified = True
        self.session.flush()
        return user

    def update_last_login(self, user_id: int) -> Optional[User]:
        """
        Met a jour la date de derniere connexion (dans ce tenant).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur mis a jour ou None
        """
        user = self.get(user_id)
        if user is None:
            return None

        user.last_login_at = datetime.now(timezone.utc)
        self.session.flush()
        return user

    def update_password(
        self,
        user_id: int,
        password_hash: str
    ) -> Optional[User]:
        """
        Met a jour le mot de passe d'un utilisateur (dans ce tenant).

        Args:
            user_id: ID de l'utilisateur
            password_hash: Nouveau hash du mot de passe

        Returns:
            L'utilisateur mis a jour ou None
        """
        user = self.get(user_id)
        if user is None:
            return None

        user.password_hash = password_hash
        user.password_changed_at = datetime.now(timezone.utc)
        self.session.flush()
        return user

    def deactivate(self, user_id: int) -> Optional[User]:
        """Desactive un utilisateur du tenant."""
        return self.update(user_id, {"is_active": False})

    def activate(self, user_id: int) -> Optional[User]:
        """Active un utilisateur du tenant."""
        return self.update(user_id, {"is_active": True})

    def search_by_name(
        self,
        query: str,
        limit: int = 20
    ) -> List[User]:
        """
        Recherche des utilisateurs par nom DANS le tenant courant.

        Args:
            query: Terme de recherche
            limit: Nombre maximum de resultats

        Returns:
            Liste des utilisateurs correspondants
        """
        search_pattern = f"%{query.lower()}%"
        return (
            self._tenant_query()
            .filter(
                func.lower(
                    func.coalesce(self.model.first_name, "") + " " +
                    func.coalesce(self.model.last_name, "")
                ).like(search_pattern)
            )
            .limit(limit)
            .all()
        )

    def email_exists(self, email: str) -> bool:
        """
        Verifie si un email existe DANS ce tenant.

        Args:
            email: Email a verifier

        Returns:
            True si existe dans ce tenant, False sinon
        """
        return self.get_by_email(email) is not None


class UserRepository(BaseRepository[User]):
    """
    Repository pour les operations sur les Users

    Fournit des methodes specifiques pour la gestion
    des utilisateurs avec support multi-tenant
    """

    model = User

    def __init__(self, session: Session):
        """Initialise le repository avec une session DB"""
        super().__init__(session)

    def get_by_email(self, email: str) -> Optional[User]:
        """
        SUPPRIME - Cette methode violait l'isolation multi-tenant.

        Args:
            email: Email de l'utilisateur

        Raises:
            RuntimeError: Toujours - methode supprimee pour securite

        .. deprecated::
            SUPPRIME pour raisons de securite. Cette methode cherchait dans
            TOUS les tenants, violant l'isolation multi-tenant SaaS.
            Utilisez OBLIGATOIREMENT get_by_email_and_tenant().
        """
        # SECURITE: Lever une erreur au lieu de continuer silencieusement
        # Cette methode permettait des fuites de donnees cross-tenant
        logger.error(
            f"SECURITE: Tentative d'appel a get_by_email() sans tenant_id pour {email}. "
            "Cette methode est SUPPRIMEE. Utilisez get_by_email_and_tenant()."
        )
        raise RuntimeError(
            "get_by_email() est SUPPRIME pour raisons de securite multi-tenant. "
            "Utilisez get_by_email_and_tenant(email, tenant_id) a la place."
        )

    def get_by_email_and_tenant(
        self,
        email: str,
        tenant_id: int
    ) -> Optional[User]:
        """
        Recupere un utilisateur par email et tenant

        Args:
            email: Email de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            L'utilisateur trouve ou None
        """
        return (
            self.session.query(self.model)
            .filter(
                func.lower(self.model.email) == email.lower(),
                self.model.tenant_id == tenant_id
            )
            .first()
        )

    def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Recupere tous les utilisateurs actifs

        Args:
            skip: Nombre d'utilisateurs a sauter
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs actifs
        """
        return (
            self.session.query(self.model)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_tenant(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Recupere tous les utilisateurs d'un tenant

        Args:
            tenant_id: ID du tenant
            skip: Nombre d'utilisateurs a sauter
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs du tenant
        """
        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def verify_user(self, user_id: int) -> Optional[User]:
        """
        Marque un utilisateur comme verifie

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur verifie ou None
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.is_verified = True
        self.session.flush()
        return user

    def update_last_login(self, user_id: int) -> Optional[User]:
        """
        Met a jour la date de derniere connexion

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur mis a jour ou None
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.last_login_at = datetime.now(timezone.utc)
        self.session.flush()
        return user

    def update_password(
        self,
        user_id: int,
        password_hash: str
    ) -> Optional[User]:
        """
        Met a jour le mot de passe d'un utilisateur

        Args:
            user_id: ID de l'utilisateur
            password_hash: Nouveau hash du mot de passe

        Returns:
            L'utilisateur mis a jour ou None
        """
        user = self.get_by_id(user_id)
        if user is None:
            return None

        user.password_hash = password_hash
        user.password_changed_at = datetime.now(timezone.utc)
        self.session.flush()
        return user

    def count_by_tenant(self, tenant_id: int) -> int:
        """
        Compte le nombre d'utilisateurs d'un tenant

        Args:
            tenant_id: ID du tenant

        Returns:
            Nombre d'utilisateurs
        """
        return (
            self.session.query(func.count(self.model.id))
            .filter(self.model.tenant_id == tenant_id)
            .scalar() or 0
        )

    def email_exists_in_tenant(
        self,
        email: str,
        tenant_id: int
    ) -> bool:
        """
        Verifie si un email existe dans un tenant

        Args:
            email: Email a verifier
            tenant_id: ID du tenant

        Returns:
            True si existe, False sinon
        """
        return self.get_by_email_and_tenant(email, tenant_id) is not None

    def get_superusers(self) -> List[User]:
        """
        Recupere tous les superusers

        Returns:
            Liste des superusers
        """
        return (
            self.session.query(self.model)
            .filter(self.model.is_superuser == True)
            .all()
        )

    def deactivate(self, user_id: int) -> Optional[User]:
        """
        Desactive un utilisateur

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur desactive ou None
        """
        return self.update(user_id, {"is_active": False})

    def activate(self, user_id: int) -> Optional[User]:
        """
        Active un utilisateur

        Args:
            user_id: ID de l'utilisateur

        Returns:
            L'utilisateur active ou None
        """
        return self.update(user_id, {"is_active": True})

    def search_by_name(
        self,
        query: str,
        tenant_id: Optional[int] = None,
        limit: int = 20
    ) -> List[User]:
        """
        Recherche des utilisateurs par nom

        Args:
            query: Terme de recherche
            tenant_id: ID du tenant (optionnel)
            limit: Nombre maximum de resultats

        Returns:
            Liste des utilisateurs correspondants
        """
        search_pattern = f"%{query.lower()}%"
        base_query = self.session.query(self.model).filter(
            func.lower(
                func.coalesce(self.model.first_name, "") + " " +
                func.coalesce(self.model.last_name, "")
            ).like(search_pattern)
        )

        if tenant_id is not None:
            base_query = base_query.filter(self.model.tenant_id == tenant_id)

        return base_query.limit(limit).all()
