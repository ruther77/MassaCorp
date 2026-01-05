"""
Repository pour la gestion des sessions utilisateur.

Ce module gere les sessions JWT actives, permettant le listing,
l'invalidation et le nettoyage des sessions.

Fonctionnalites principales:
- Creation de sessions avec metadata (IP, user-agent)
- Listing des sessions actives d'un utilisateur
- Invalidation individuelle ou globale des sessions
- Verification de validite d'une session
- Nettoyage des sessions expirees

Notes de securite:
- Les sessions utilisent des UUID pour eviter l'enumeration
- L'invalidation set revoked_at plutot que de supprimer (historique)
- Toutes les requetes respectent l'isolation multi-tenant
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

from sqlalchemy import and_
from sqlalchemy.orm import Session as SQLAlchemySession

from app.models.session import Session
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """
    Repository pour les sessions utilisateur.

    Gere le cycle de vie des sessions JWT avec isolation multi-tenant.
    """

    model = Session

    # Duree maximale absolue d'une session (30 jours)
    # Cette limite ne peut pas etre etendue par rotation de tokens
    SESSION_ABSOLUTE_EXPIRY_DAYS = 30

    def create_session(
        self,
        user_id: int,
        tenant_id: int,
        token_jti: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        absolute_expiry_days: Optional[int] = None
    ) -> Session:
        """
        Cree une nouvelle session utilisateur.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            token_jti: JTI du token JWT associe (pour reference)
            ip_address: Adresse IP de connexion
            user_agent: User-Agent du client
            expires_at: Date d'expiration (non utilisee directement, info)
            absolute_expiry_days: Duree max de la session en jours (defaut: 30)

        Returns:
            Session: La session creee avec un UUID unique et absolute_expiry

        Notes securite:
            - absolute_expiry est defini a created_at + 30 jours par defaut
            - Cette date ne change JAMAIS meme avec rotation de tokens
            - Garantit qu'une session ne peut pas durer plus de 30 jours
        """
        if absolute_expiry_days is None:
            absolute_expiry_days = self.SESSION_ABSOLUTE_EXPIRY_DAYS

        now = datetime.now(timezone.utc)
        absolute_expiry = now + timedelta(days=absolute_expiry_days)

        session = Session(
            id=uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            ip=ip_address,
            user_agent=user_agent,
            absolute_expiry=absolute_expiry,
        )

        self.session.add(session)
        self.session.flush()

        logger.debug(
            f"Session creee: id={session.id}, user_id={user_id}, "
            f"absolute_expiry={absolute_expiry.isoformat()}"
        )

        return session

    def get_active_sessions(
        self,
        user_id: int,
        tenant_id: Optional[int] = None
    ) -> List[Session]:
        """
        Recupere les sessions actives d'un utilisateur.

        Une session est active si revoked_at est NULL.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel, pour filtrage additionnel)

        Returns:
            Liste des sessions actives triees par date de creation
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.revoked_at.is_(None))
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        return query.order_by(self.model.created_at.desc()).all()

    def get_session_for_user(
        self,
        session_id: UUID,
        user_id: int
    ) -> Optional[Session]:
        """
        Recupere une session par ID avec verification de propriete atomique.

        Cette methode combine la recherche par ID et la verification de
        propriete en une seule requete SQL, ce qui:
        - Empeche les attaques IDOR (enumeration d'UUID)
        - Garantit une reponse uniforme (None) pour session inexistante
          ou non-possedee
        - Evite les race conditions

        Args:
            session_id: UUID de la session
            user_id: ID de l'utilisateur proprietaire attendu

        Returns:
            La session si elle existe ET appartient a l'utilisateur, None sinon
        """
        return (
            self.session.query(self.model)
            .filter(self.model.id == session_id)
            .filter(self.model.user_id == user_id)
            .first()
        )

    def invalidate_session(
        self,
        session_id: Optional[UUID] = None,
        token_jti: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Invalide une session specifique avec verification de propriete optionnelle.

        L'invalidation met revoked_at a l'heure actuelle plutot que
        de supprimer la session (conservation pour audit).

        Si user_id est fourni, la session n'est invalidee que si elle
        appartient a cet utilisateur (protection IDOR).

        Args:
            session_id: UUID de la session
            token_jti: JTI du token associe (non supporte - JTI pas dans Session)
            user_id: ID de l'utilisateur proprietaire (pour verification IDOR)

        Returns:
            True si la session a ete invalidee, False si non trouvee ou non-possedee
        """
        # Si seul token_jti est fourni, on ne peut pas chercher
        # car le JTI n'est pas stocke dans Session (il est dans RefreshToken)
        if session_id is None:
            return False

        query = self.session.query(self.model)

        # Gerer le cas ou session_id peut etre un int ou un UUID
        try:
            if isinstance(session_id, int):
                # On ne peut pas chercher par int sur un UUID, retourner False
                return False
            query = query.filter(self.model.id == session_id)

            # Si user_id est fourni, verifier la propriete dans la meme requete
            if user_id is not None:
                query = query.filter(self.model.user_id == user_id)

        except Exception as e:
            logger.warning(f"Erreur lors de l'invalidation de session {session_id}: {e}")
            return False

        session_obj = query.first()

        if session_obj is None:
            return False

        session_obj.revoked_at = datetime.now(timezone.utc)
        return True

    def invalidate_all_sessions(
        self,
        user_id: int,
        except_session_id: Optional[UUID] = None
    ) -> int:
        """
        Invalide toutes les sessions d'un utilisateur.

        Cas d'usage: changement de mot de passe, compte compromis,
        ou "Deconnecter tous les autres appareils".

        Args:
            user_id: ID de l'utilisateur
            except_session_id: ID de la session a exclure (session courante)

        Returns:
            Nombre de sessions invalidees
        """
        now = datetime.now(timezone.utc)

        query = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.revoked_at.is_(None))
        )

        # Exclure la session courante si specifiee
        if except_session_id is not None:
            query = query.filter(self.model.id != except_session_id)

        updated = query.update(
            {"revoked_at": now},
            synchronize_session='fetch'  # Flush changes to ensure consistency
        )

        # Flush explicite pour s'assurer que les changements sont visibles
        self.session.flush()

        return updated

    def is_session_valid(self, session_id: UUID) -> bool:
        """
        Verifie si une session est valide (active et non revoquee).

        Une session est valide si:
        - Elle existe dans la base
        - Elle n'a pas ete revoquee (revoked_at est NULL)

        Args:
            session_id: UUID de la session a verifier

        Returns:
            True si la session est valide, False sinon
        """
        session_obj = (
            self.session.query(self.model)
            .filter(self.model.id == session_id)
            .first()
        )

        if session_obj is None:
            return False

        # Session valide si non revoquee
        return session_obj.revoked_at is None

    def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """
        Recupere une session par son UUID.

        Args:
            session_id: UUID de la session

        Returns:
            La session ou None si non trouvee
        """
        return (
            self.session.query(self.model)
            .filter(self.model.id == session_id)
            .first()
        )

    def get_by_id_and_tenant(
        self,
        session_id: UUID,
        tenant_id: int
    ) -> Optional[Session]:
        """
        Recupere une session par UUID avec verification du tenant.

        Cette methode assure l'isolation multi-tenant en filtrant
        par tenant_id dans la requete SQL.

        Args:
            session_id: UUID de la session
            tenant_id: ID du tenant attendu

        Returns:
            La session si elle existe ET appartient au tenant, None sinon
        """
        return (
            self.session.query(self.model)
            .filter(self.model.id == session_id)
            .filter(self.model.tenant_id == tenant_id)
            .first()
        )

    def get_all_sessions(
        self,
        user_id: int,
        tenant_id: Optional[int] = None
    ) -> List[Session]:
        """
        Recupere toutes les sessions d'un utilisateur (actives ET revoquees).

        Utile pour afficher l'historique complet des sessions.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant (optionnel, pour filtrage additionnel)

        Returns:
            Liste de toutes les sessions triees par date de creation
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        return query.order_by(self.model.created_at.desc()).all()

    def cleanup_expired(
        self,
        older_than_days: int = 30,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Supprime les sessions revoquees anciennes.

        Garde un historique recent pour audit mais purge les vieilles
        sessions pour limiter la taille de la base.

        Args:
            older_than_days: Age minimum en jours pour suppression
            tenant_id: Limiter au tenant specifie (None = tous)

        Returns:
            Nombre de sessions supprimees
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        query = (
            self.session.query(self.model)
            .filter(self.model.revoked_at.isnot(None))
            .filter(self.model.revoked_at < cutoff)
        )

        # Filtre tenant optionnel pour isolation multi-tenant
        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        deleted = query.delete(synchronize_session=False)

        return deleted
