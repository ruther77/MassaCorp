"""
Repositories pour la gestion MFA.

Ce module fournit les repositories pour:
- MFASecretRepository: CRUD pour les secrets TOTP
- MFARecoveryCodeRepository: CRUD pour les codes de recuperation

Ces repositories gerent l'acces aux donnees MFA avec isolation multi-tenant.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.mfa import MFASecret, MFARecoveryCode
from app.repositories.base import BaseRepository


class MFASecretRepository(BaseRepository[MFASecret]):
    """
    Repository pour les secrets MFA (TOTP).

    Gere le stockage et la recuperation des secrets TOTP
    pour l'authentification a deux facteurs.
    """

    model = MFASecret

    def get_by_user_id(self, user_id: int) -> Optional[MFASecret]:
        """
        Recupere le secret MFA d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            MFASecret ou None si pas trouve
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .first()
        )

    def get_by_user_and_tenant(
        self,
        user_id: int,
        tenant_id: int
    ) -> Optional[MFASecret]:
        """
        Recupere le secret MFA avec verification du tenant.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            MFASecret ou None si pas trouve
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.tenant_id == tenant_id)
            .first()
        )

    def create_or_update(
        self,
        user_id: int,
        tenant_id: int,
        secret: str
    ) -> MFASecret:
        """
        Cree ou met a jour un secret MFA.

        Si un secret existe deja, il est mis a jour.
        Sinon, un nouveau secret est cree.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            secret: Secret TOTP en base32

        Returns:
            MFASecret cree ou mis a jour
        """
        existing = self.get_by_user_id(user_id)

        if existing:
            existing.secret = secret
            existing.enabled = False  # Reset enabled on secret change
            self.session.flush()
            return existing

        new_secret = MFASecret(
            user_id=user_id,
            tenant_id=tenant_id,
            secret=secret,
            enabled=False
        )
        self.session.add(new_secret)
        self.session.flush()
        return new_secret

    def enable_mfa(self, user_id: int) -> bool:
        """
        Active le MFA pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si active avec succes, False si pas de secret
        """
        secret = self.get_by_user_id(user_id)
        if secret is None:
            return False

        secret.enabled = True
        return True

    def disable_mfa(self, user_id: int) -> bool:
        """
        Desactive le MFA pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si desactive avec succes, False si pas de secret
        """
        secret = self.get_by_user_id(user_id)
        if secret is None:
            return False

        secret.enabled = False
        return True

    def delete_by_user_id(self, user_id: int) -> bool:
        """
        Supprime le secret MFA d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si supprime, False si pas trouve
        """
        secret = self.get_by_user_id(user_id)
        if secret is None:
            return False

        self.session.delete(secret)
        return True

    def is_mfa_enabled(self, user_id: int) -> bool:
        """
        Verifie si le MFA est active pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si MFA active, False sinon
        """
        secret = self.get_by_user_id(user_id)
        if secret is None:
            return False
        return secret.enabled

    def update_last_used(self, user_id: int) -> None:
        """
        Met a jour le timestamp de derniere utilisation.

        Args:
            user_id: ID de l'utilisateur
        """
        secret = self.get_by_user_id(user_id)
        if secret:
            secret.last_used_at = datetime.now(timezone.utc)

    def update_last_totp_window(self, user_id: int, window: int) -> None:
        """
        Met a jour le dernier window TOTP utilise (anti-replay).

        Args:
            user_id: ID de l'utilisateur
            window: Numero du window TOTP (timestamp // 30)
        """
        secret = self.get_by_user_id(user_id)
        if secret:
            secret.last_totp_window = window


class MFARecoveryCodeRepository(BaseRepository[MFARecoveryCode]):
    """
    Repository pour les codes de recuperation MFA.

    Gere le stockage et la verification des codes de recuperation
    a usage unique.
    """

    model = MFARecoveryCode

    def create_codes_for_user(
        self,
        user_id: int,
        tenant_id: int,
        code_hashes: List[str]
    ) -> List[MFARecoveryCode]:
        """
        Cree plusieurs codes de recuperation pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            code_hashes: Liste des hashes de codes

        Returns:
            Liste des codes crees
        """
        codes = []
        for code_hash in code_hashes:
            code = MFARecoveryCode(
                user_id=user_id,
                tenant_id=tenant_id,
                code_hash=code_hash
            )
            self.session.add(code)
            codes.append(code)

        self.session.flush()
        return codes

    def get_valid_codes_for_user(self, user_id: int) -> List[MFARecoveryCode]:
        """
        Recupere tous les codes valides (non utilises) d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des codes valides
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.used_at.is_(None))
            .all()
        )

    def get_code_by_hash(
        self,
        user_id: int,
        code_hash: str
    ) -> Optional[MFARecoveryCode]:
        """
        Trouve un code par son hash.

        Args:
            user_id: ID de l'utilisateur
            code_hash: Hash du code a trouver

        Returns:
            MFARecoveryCode ou None
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.code_hash == code_hash)
            .first()
        )

    def mark_code_as_used(self, code_id: int) -> bool:
        """
        Marque un code comme utilise.

        Args:
            code_id: ID du code

        Returns:
            True si marque avec succes, False si pas trouve
        """
        code = (
            self.session.query(self.model)
            .filter(self.model.id == code_id)
            .first()
        )

        if code is None:
            return False

        code.used_at = datetime.now(timezone.utc)
        return True

    def delete_all_for_user(self, user_id: int) -> int:
        """
        Supprime tous les codes d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de codes supprimes
        """
        deleted = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .delete(synchronize_session=False)
        )
        return deleted

    def count_valid_codes(self, user_id: int) -> int:
        """
        Compte les codes valides d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de codes valides
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.used_at.is_(None))
            .count()
        )

    def get_all_for_user(self, user_id: int) -> List[MFARecoveryCode]:
        """
        Recupere tous les codes d'un utilisateur (utilises et non utilises).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste de tous les codes
        """
        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .all()
        )
