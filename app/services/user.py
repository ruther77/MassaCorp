"""
Service Utilisateur pour MassaCorp
Logique metier pour la gestion des utilisateurs
"""
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from app.core.security import hash_password, verify_password
from app.models import User, Tenant
from app.repositories.user import UserRepository
from app.repositories.tenant import TenantRepository
from app.services.exceptions import (
    EmailAlreadyExistsError,
    UserNotFoundError,
    TenantNotFoundError,
    PasswordMismatchError,
)

if TYPE_CHECKING:
    from app.services.session import SessionService
    from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class UserService:
    """
    Service pour la gestion des utilisateurs

    Contient la logique metier pour:
    - Creation/modification/suppression utilisateurs
    - Changement de mot de passe
    - Verification email
    """

    def __init__(
        self,
        user_repository: UserRepository,
        tenant_repository: TenantRepository = None,
        session_service: Optional["SessionService"] = None,
        audit_service: Optional["AuditService"] = None
    ):
        """
        Initialise le service avec les repositories

        Args:
            user_repository: Repository pour les users
            tenant_repository: Repository pour les tenants (optionnel)
            session_service: Service de sessions pour revocation (optionnel)
            audit_service: Service d'audit pour logging securite (optionnel)
        """
        self.user_repository = user_repository
        self.tenant_repository = tenant_repository
        self.session_service = session_service
        self.audit_service = audit_service

    def create_user(
        self,
        email: str,
        password: str,
        tenant_id: int,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        is_active: bool = True,
        is_verified: bool = False,
        is_superuser: bool = False,
    ) -> User:
        """
        Cree un nouvel utilisateur

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair
            tenant_id: ID du tenant
            first_name: Prenom (optionnel)
            last_name: Nom (optionnel)
            phone: Telephone (optionnel)
            is_active: Compte actif (defaut True)
            is_verified: Email verifie (defaut False)
            is_superuser: Superuser (defaut False)

        Returns:
            User cree

        Raises:
            TenantNotFoundError: Si le tenant n'existe pas
            EmailAlreadyExistsError: Si l'email existe deja dans le tenant
        """
        # Normaliser l'email
        email = email.lower().strip()

        # Verifier que le tenant existe
        if self.tenant_repository:
            tenant = self.tenant_repository.get_by_id(tenant_id)
            if tenant is None:
                raise TenantNotFoundError(tenant_id=tenant_id)

        # Verifier que l'email n'existe pas deja
        if self.user_repository.email_exists_in_tenant(email, tenant_id):
            raise EmailAlreadyExistsError(email)

        # Hasher le mot de passe
        password_hash = hash_password(password)

        # Creer l'utilisateur
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "tenant_id": tenant_id,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "is_active": is_active,
            "is_verified": is_verified,
            "is_superuser": is_superuser,
        }

        return self.user_repository.create(user_data)

    def get_user(self, user_id: int) -> Optional[User]:
        """
        Recupere un utilisateur par ID

        Args:
            user_id: ID de l'utilisateur

        Returns:
            User trouve ou None
        """
        return self.user_repository.get_by_id(user_id)

    def get_user_by_email(
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
            User trouve ou None
        """
        return self.user_repository.get_by_email_and_tenant(
            email=email.lower().strip(),
            tenant_id=tenant_id
        )

    def update_user(
        self,
        user_id: int,
        data: Dict[str, Any]
    ) -> Optional[User]:
        """
        Met a jour un utilisateur

        Args:
            user_id: ID de l'utilisateur
            data: Donnees a mettre a jour

        Returns:
            User mis a jour ou None

        Raises:
            UserNotFoundError: Si l'utilisateur n'existe pas
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)

        # Filtrer les champs non modifiables
        allowed_fields = {
            "first_name", "last_name", "phone",
            "is_active", "is_verified", "is_superuser"
        }
        filtered_data = {k: v for k, v in data.items() if k in allowed_fields}

        return self.user_repository.update(user_id, filtered_data)

    def delete_user(self, user_id: int) -> bool:
        """
        Supprime un utilisateur

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si supprime, False sinon

        Raises:
            UserNotFoundError: Si l'utilisateur n'existe pas
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)

        return self.user_repository.delete(user_id)

    def list_users(
        self,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """
        Liste les utilisateurs d'un tenant avec pagination

        Args:
            tenant_id: ID du tenant
            skip: Nombre a sauter
            limit: Nombre maximum

        Returns:
            Liste des utilisateurs
        """
        return self.user_repository.get_by_tenant(
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )

    def count_users(self, tenant_id: int) -> int:
        """
        Compte les utilisateurs d'un tenant

        Args:
            tenant_id: ID du tenant

        Returns:
            Nombre d'utilisateurs
        """
        return self.user_repository.count_by_tenant(tenant_id)

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_session_id: Optional[str] = None
    ) -> User:
        """
        Change le mot de passe d'un utilisateur

        Args:
            user_id: ID de l'utilisateur
            current_password: Mot de passe actuel
            new_password: Nouveau mot de passe
            current_session_id: Session a garder active (optionnel)

        Returns:
            User avec mot de passe mis a jour

        Raises:
            UserNotFoundError: Si l'utilisateur n'existe pas
            PasswordMismatchError: Si le mot de passe actuel est incorrect

        Note:
            Toutes les sessions sont revoquees apres changement de mot de passe
            (sauf current_session_id si specifie).
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)

        # Verifier le mot de passe actuel
        if not verify_password(current_password, user.password_hash):
            raise PasswordMismatchError()

        # Hasher et sauvegarder le nouveau mot de passe
        new_hash = hash_password(new_password)
        updated_user = self.user_repository.update_password(user_id, new_hash)

        # Revoquer toutes les sessions (securite CRITIQUE)
        sessions_revoked = False
        revocation_error = None
        if self.session_service:
            try:
                self.session_service.terminate_all_sessions(
                    user_id=user_id,
                    except_session_id=current_session_id
                )
                sessions_revoked = True
                logger.info(
                    f"Sessions revoquees apres changement de mot de passe "
                    f"pour user_id={user_id}"
                )
            except Exception as e:
                # SECURITE: Log ERROR car les anciennes sessions restent actives!
                revocation_error = str(e)
                logger.error(
                    f"SECURITE: Echec revocation sessions pour user_id={user_id}: {e}. "
                    "Les anciennes sessions peuvent rester actives!"
                )

        # Audit logging du changement de mot de passe
        if self.audit_service:
            try:
                self.audit_service.log_action(
                    action="user.password_change",
                    user_id=user_id,
                    tenant_id=user.tenant_id,
                    success=True,
                    details={
                        "sessions_revoked": sessions_revoked,
                        "revocation_error": revocation_error  # Tracer l'echec!
                    }
                )
            except Exception as e:
                logger.warning(f"Erreur audit password_change: {e}")

        return updated_user

    def verify_user(self, user_id: int) -> Optional[User]:
        """
        Marque un utilisateur comme verifie

        Args:
            user_id: ID de l'utilisateur

        Returns:
            User verifie ou None
        """
        return self.user_repository.verify_user(user_id)

    def deactivate_user(self, user_id: int) -> Optional[User]:
        """
        Desactive un utilisateur

        Args:
            user_id: ID de l'utilisateur

        Returns:
            User desactive ou None
        """
        return self.user_repository.deactivate(user_id)

    def activate_user(self, user_id: int) -> Optional[User]:
        """
        Active un utilisateur

        Args:
            user_id: ID de l'utilisateur

        Returns:
            User active ou None
        """
        return self.user_repository.activate(user_id)

    def force_mfa_required(
        self,
        user_id: int,
        reason: str = "security_policy"
    ) -> Optional[User]:
        """
        Force un utilisateur a activer MFA.

        Utilise apres une compromission suspecte ou selon la politique
        de securite. L'utilisateur devra configurer MFA avant de pouvoir
        continuer a utiliser le systeme.

        Args:
            user_id: ID de l'utilisateur
            reason: Raison de la demande (pour audit)

        Returns:
            User modifie ou None si non trouve
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return None

        user.mfa_required = True

        # Log l'action si audit service disponible
        if self.audit_service:
            self.audit_service.log_action(
                action="mfa_force_required",
                user_id=user_id,
                tenant_id=user.tenant_id,
                resource="user",
                resource_id=user_id,
                details={"reason": reason}
            )

        return user

    def clear_mfa_required(self, user_id: int) -> Optional[User]:
        """
        Supprime l'exigence MFA pour un utilisateur.

        Appele automatiquement quand l'utilisateur active MFA avec succes.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            User modifie ou None si non trouve
        """
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            return None

        user.mfa_required = False
        return user
