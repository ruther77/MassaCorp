"""
Service pour la gestion des entites financieres.
"""
import logging
from typing import List, Optional, Dict, Any

from app.models.finance.entity import FinanceEntity, FinanceEntityMember
from app.repositories.finance.entity import (
    FinanceEntityRepository,
    FinanceEntityMemberRepository,
)
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class EntityNotFoundError(AppException):
    """Entite non trouvee."""
    status_code = 404
    error_code = "ENTITY_NOT_FOUND"

    def __init__(self, entity_id: int):
        super().__init__(message=f"Entite {entity_id} non trouvee")
        self.entity_id = entity_id


class EntityCodeExistsError(AppException):
    """Code d'entite deja utilise."""
    status_code = 409
    error_code = "ENTITY_CODE_EXISTS"

    def __init__(self, code: str):
        super().__init__(message=f"Le code '{code}' existe deja")
        self.code = code


class FinanceEntityService:
    """
    Service de gestion des entites financieres.
    """

    def __init__(
        self,
        entity_repository: FinanceEntityRepository,
        member_repository: FinanceEntityMemberRepository,
    ):
        self.entity_repository = entity_repository
        self.member_repository = member_repository

    def create_entity(
        self,
        name: str,
        code: str,
        currency: str = "EUR",
        siret: Optional[str] = None,
        address: Optional[str] = None,
    ) -> FinanceEntity:
        """
        Cree une nouvelle entite financiere.

        Args:
            name: Nom de l'entite
            code: Code unique de l'entite
            currency: Devise (defaut EUR)
            siret: Numero SIRET optionnel
            address: Adresse optionnelle

        Returns:
            L'entite creee

        Raises:
            EntityCodeExistsError: Si le code existe deja
        """
        # Verifier unicite du code
        existing = self.entity_repository.get_by_code(code)
        if existing:
            raise EntityCodeExistsError(code)

        entity = self.entity_repository.create({
            "name": name,
            "code": code.upper(),
            "currency": currency,
            "siret": siret,
            "address": address,
            "is_active": True,
        })

        logger.info(f"Entite creee: {entity.id} - {entity.code}")
        return entity

    def get_entity(self, entity_id: int) -> FinanceEntity:
        """
        Recupere une entite par ID.

        Raises:
            EntityNotFoundError: Si l'entite n'existe pas
        """
        entity = self.entity_repository.get(entity_id)
        if not entity:
            raise EntityNotFoundError(entity_id)
        return entity

    def get_active_entities(self) -> List[FinanceEntity]:
        """Recupere toutes les entites actives."""
        return self.entity_repository.get_active()

    def update_entity(
        self,
        entity_id: int,
        data: Dict[str, Any]
    ) -> FinanceEntity:
        """
        Met a jour une entite.

        Raises:
            EntityNotFoundError: Si l'entite n'existe pas
            EntityCodeExistsError: Si le nouveau code existe deja
        """
        entity = self.get_entity(entity_id)

        # Verifier unicite du code si modifie
        if "code" in data and data["code"] != entity.code:
            existing = self.entity_repository.get_by_code(data["code"])
            if existing:
                raise EntityCodeExistsError(data["code"])
            data["code"] = data["code"].upper()

        updated = self.entity_repository.update(entity_id, data)
        logger.info(f"Entite mise a jour: {entity_id}")
        return updated

    def deactivate_entity(self, entity_id: int) -> FinanceEntity:
        """Desactive une entite."""
        entity = self.get_entity(entity_id)
        entity.is_active = False
        self.entity_repository.session.flush()
        logger.info(f"Entite desactivee: {entity_id}")
        return entity

    def add_member(
        self,
        entity_id: int,
        user_id: int,
        role: str = "viewer",
        is_default: bool = False,
    ) -> FinanceEntityMember:
        """
        Ajoute un membre a une entite.

        Args:
            entity_id: ID de l'entite
            user_id: ID de l'utilisateur
            role: Role du membre (viewer, editor, admin)
            is_default: Si c'est l'entite par defaut de l'utilisateur
        """
        # Verifier que l'entite existe
        self.get_entity(entity_id)

        # Verifier si deja membre
        existing = self.member_repository.get_by_entity_and_user(entity_id, user_id)
        if existing:
            existing.role = role
            self.member_repository.session.flush()
            return existing

        # Si is_default, retirer le defaut des autres
        if is_default:
            self.member_repository.set_default(entity_id, user_id)

        member = self.member_repository.create({
            "entity_id": entity_id,
            "user_id": user_id,
            "role": role,
            "is_default": is_default,
        })

        logger.info(f"Membre ajoute: user={user_id} -> entity={entity_id}")
        return member

    def remove_member(self, entity_id: int, user_id: int) -> bool:
        """Retire un membre d'une entite."""
        member = self.member_repository.get_by_entity_and_user(entity_id, user_id)
        if member:
            self.member_repository.delete(member.id)
            logger.info(f"Membre retire: user={user_id} <- entity={entity_id}")
            return True
        return False

    def get_user_entities(self, user_id: int) -> List[FinanceEntity]:
        """Recupere les entites d'un utilisateur."""
        members = self.member_repository.get_by_user(user_id)
        return [m.entity for m in members if m.entity.is_active]

    def get_default_entity(self, user_id: int) -> Optional[FinanceEntity]:
        """Recupere l'entite par defaut d'un utilisateur."""
        member = self.member_repository.get_default_for_user(user_id)
        if member and member.entity.is_active:
            return member.entity
        return None
