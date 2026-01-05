"""
Repository pour la gestion des refresh tokens.

Ce module gere les tokens de rafraichissement JWT, permettant aux utilisateurs
de renouveler leurs access tokens sans re-authentification.

Fonctionnalites principales:
- Stockage securise des refresh tokens (seul le hash est stocke)
- Verification de validite (non revoque, non expire)
- Revocation individuelle ou globale
- Nettoyage des tokens expires

Notes de securite:
- Le token brut n'est JAMAIS stocke, uniquement son hash
- Chaque utilisation genere un nouveau token (rotation)
- La reutilisation d'un token consomme indique une compromission
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.session import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """
    Repository pour les refresh tokens.

    Gere le stockage et la validation des refresh tokens JWT.
    """

    model = RefreshToken

    def store_token(
        self,
        jti: str,
        user_id: int,
        tenant_id: int,
        expires_at: datetime,
        session_id: Optional[str] = None,
        token_hash: Optional[str] = None,
        device_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> RefreshToken:
        """
        Stocke un nouveau refresh token.

        Note: Cette implementation simplifiee ne stocke pas user_id/tenant_id
        directement car RefreshToken est lie a une Session qui contient ces infos.

        Args:
            jti: JWT ID unique du token
            user_id: ID de l'utilisateur (utilise pour creer/trouver session)
            tenant_id: ID du tenant
            expires_at: Date d'expiration du token
            session_id: ID de la session associee (OBLIGATOIRE)
            token_hash: Hash SHA256 du token (OBLIGATOIRE)
            device_name: Nom du device (optionnel, pour affichage)
            ip_address: Adresse IP (optionnel)
            user_agent: User-Agent (optionnel)

        Returns:
            RefreshToken: Le token cree

        Raises:
            ValueError: Si session_id ou token_hash est None/vide
            IntegrityError: Si le JTI existe deja (collision theoriquement impossible)
        """
        # Validation du session_id - OBLIGATOIRE pour la securite et traçabilite
        if session_id is None:
            raise ValueError("session_id est obligatoire - chaque token doit etre lie a une session")

        # Validation du token_hash - OBLIGATOIRE pour la securite
        if token_hash is None:
            raise ValueError("token_hash est obligatoire - le token brut doit etre hashe")

        if not token_hash or len(token_hash) == 0:
            raise ValueError("token_hash ne peut pas etre vide")

        if token_hash == "placeholder_hash":
            raise ValueError("placeholder_hash n'est pas accepte - utilisez un vrai hash SHA256")

        # Validation basique du format SHA256 (64 caracteres hexadecimaux)
        if len(token_hash) != 64:
            raise ValueError("token_hash doit etre un hash SHA256 valide (64 caracteres)")

        # Convertir session_id en UUID si c'est une string
        session_uuid = None
        if session_id is not None:
            from uuid import UUID
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id

        token = RefreshToken(
            jti=jti,
            session_id=session_uuid,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self.session.add(token)

        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise

        return token

    def is_valid(self, jti: str) -> bool:
        """
        Verifie si un refresh token est valide.

        Un token est valide si:
        - Il existe en base
        - Il n'a pas ete utilise (used_at is NULL)
        - Il n'est pas expire (expires_at > now)

        Args:
            jti: JWT ID du token a verifier

        Returns:
            True si le token est valide, False sinon
        """
        token = (
            self.session.query(self.model)
            .filter(self.model.jti == jti)
            .first()
        )

        if token is None:
            return False

        # Verifie si le token a ete utilise (rotation)
        if token.used_at is not None:
            return False

        # Verifie l'expiration
        now = datetime.now(timezone.utc)
        if token.expires_at <= now:
            return False

        return True

    def revoke_token(self, jti: str) -> bool:
        """
        Revoque un refresh token.

        Marque le token comme utilise, ce qui l'invalide pour les futures
        utilisations.

        Args:
            jti: JWT ID du token a revoquer

        Returns:
            True si le token a ete revoque, False si non trouve
        """
        token = (
            self.session.query(self.model)
            .filter(self.model.jti == jti)
            .first()
        )

        if token is None:
            return False

        token.used_at = datetime.now(timezone.utc)
        return True

    def revoke_all_for_user(
        self,
        user_id: int,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Revoque tous les refresh tokens d'un utilisateur.

        Note: Cette implementation necessite une jointure avec sessions
        pour filtrer par user_id.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel pour filtrage)

        Returns:
            Nombre de tokens revoques
        """
        from app.models.session import Session as SessionModel

        now = datetime.now(timezone.utc)

        # Sous-requete pour trouver les sessions de l'utilisateur
        session_query = (
            self.session.query(SessionModel.id)
            .filter(SessionModel.user_id == user_id)
        )

        if tenant_id is not None:
            session_query = session_query.filter(SessionModel.tenant_id == tenant_id)

        session_ids = [s.id for s in session_query.all()]

        if not session_ids:
            return 0

        # Revoquer tous les tokens de ces sessions
        updated = (
            self.session.query(self.model)
            .filter(self.model.session_id.in_(session_ids))
            .filter(self.model.used_at.is_(None))
            .update(
                {"used_at": now},
                synchronize_session=False
            )
        )

        return updated

    def cleanup_expired(self) -> int:
        """
        Supprime les refresh tokens expires.

        Les tokens expires ne peuvent plus etre utilises, ils peuvent
        etre supprimes pour liberer de l'espace.

        Returns:
            Nombre de tokens supprimes
        """
        now = datetime.now(timezone.utc)

        deleted = (
            self.session.query(self.model)
            .filter(self.model.expires_at < now)
            .delete(synchronize_session=False)
        )

        return deleted

    def get_by_jti(self, jti: str) -> Optional[RefreshToken]:
        """
        Recupere un refresh token par son JTI.

        Args:
            jti: JWT ID du token

        Returns:
            Le token ou None si non trouve
        """
        return (
            self.session.query(self.model)
            .filter(self.model.jti == jti)
            .first()
        )

    def get_by_user_id(
        self,
        user_id: int,
        tenant_id: Optional[int] = None,
        include_revoked: bool = False
    ):
        """
        Recupere tous les tokens d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel, pour filtrage)
            include_revoked: Inclure les tokens revoques

        Returns:
            Liste des tokens
        """
        from app.models.session import Session as SessionModel

        # Sous-requete pour trouver les sessions de l'utilisateur
        session_query = (
            self.session.query(SessionModel.id)
            .filter(SessionModel.user_id == user_id)
        )

        if tenant_id is not None:
            session_query = session_query.filter(SessionModel.tenant_id == tenant_id)

        session_ids = [s.id for s in session_query.all()]

        if not session_ids:
            return []

        # Recuperer les tokens de ces sessions
        query = (
            self.session.query(self.model)
            .filter(self.model.session_id.in_(session_ids))
        )

        if not include_revoked:
            now = datetime.now(timezone.utc)
            query = query.filter(
                and_(
                    self.model.used_at.is_(None),
                    self.model.expires_at > now
                )
            )

        return query.order_by(self.model.expires_at.desc()).all()
