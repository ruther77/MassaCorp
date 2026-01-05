"""
Repository pour les comptes OAuth
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import OAuthAccount
from app.repositories.base import BaseRepository


class OAuthRepository(BaseRepository[OAuthAccount]):
    """Repository pour la gestion des comptes OAuth"""

    model = OAuthAccount

    def get_by_provider_user(
        self,
        provider: str,
        provider_user_id: str,
        tenant_id: int
    ) -> Optional[OAuthAccount]:
        """
        Recupere un compte OAuth par provider et ID utilisateur provider.

        Args:
            provider: Nom du provider (google, facebook, github)
            provider_user_id: ID de l'utilisateur chez le provider
            tenant_id: ID du tenant

        Returns:
            OAuthAccount trouve ou None
        """
        return (
            self.session.query(OAuthAccount)
            .filter(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
                OAuthAccount.tenant_id == tenant_id
            )
            .first()
        )

    def get_by_user(self, user_id: int) -> List[OAuthAccount]:
        """
        Recupere tous les comptes OAuth d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des comptes OAuth
        """
        return (
            self.session.query(OAuthAccount)
            .filter(OAuthAccount.user_id == user_id)
            .all()
        )

    def get_by_user_and_provider(
        self,
        user_id: int,
        provider: str
    ) -> Optional[OAuthAccount]:
        """
        Recupere un compte OAuth d'un utilisateur pour un provider specifique.

        Args:
            user_id: ID de l'utilisateur
            provider: Nom du provider

        Returns:
            OAuthAccount trouve ou None
        """
        return (
            self.session.query(OAuthAccount)
            .filter(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider
            )
            .first()
        )

    def get_by_email_and_provider(
        self,
        email: str,
        provider: str,
        tenant_id: int
    ) -> Optional[OAuthAccount]:
        """
        Recupere un compte OAuth par email et provider.

        Args:
            email: Email du compte OAuth
            provider: Nom du provider
            tenant_id: ID du tenant

        Returns:
            OAuthAccount trouve ou None
        """
        return (
            self.session.query(OAuthAccount)
            .filter(
                OAuthAccount.email == email.lower(),
                OAuthAccount.provider == provider,
                OAuthAccount.tenant_id == tenant_id
            )
            .first()
        )

    def count_by_user(self, user_id: int) -> int:
        """
        Compte le nombre de comptes OAuth d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de comptes OAuth
        """
        return (
            self.session.query(OAuthAccount)
            .filter(OAuthAccount.user_id == user_id)
            .count()
        )

    def unlink_from_user(self, user_id: int, provider: str) -> bool:
        """
        Delie un compte OAuth d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            provider: Nom du provider

        Returns:
            True si supprime, False si non trouve
        """
        account = self.get_by_user_and_provider(user_id, provider)
        if account:
            self.session.delete(account)
            self.session.flush()
            return True
        return False
