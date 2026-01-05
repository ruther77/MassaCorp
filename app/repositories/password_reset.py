"""
Repository pour la gestion des tokens de reinitialisation de mot de passe.

Ce module gere les tokens de reset password avec securite renforcee:
- Tokens hashes en SHA-256 (jamais stockes en clair)
- Expiration courte (1 heure par defaut)
- Usage unique
- Rate limiting (max 3 demandes/heure/email)

Notes de securite:
- Le token brut est envoye par email, seul le hash est en base
- Un token utilise ne peut plus servir
- Les tokens expires sont purges periodiquement
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session as SQLAlchemySession

from app.models.password_reset import PasswordResetToken
from app.repositories.base import BaseRepository


class PasswordResetRepository(BaseRepository[PasswordResetToken]):
    """
    Repository pour les tokens de reinitialisation de mot de passe.

    Gere le cycle de vie des tokens avec securite et rate limiting.
    """

    model = PasswordResetToken

    # Configuration
    TOKEN_LENGTH = 32  # 32 bytes = 256 bits
    DEFAULT_EXPIRY_HOURS = 1
    MAX_REQUESTS_PER_HOUR = 3

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """
        Hash un token avec SHA-256.

        Args:
            raw_token: Le token brut a hasher

        Returns:
            Le hash SHA-256 en hexadecimal
        """
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def generate_token() -> tuple[str, str]:
        """
        Genere un nouveau token de reset securise.

        Returns:
            Tuple (raw_token, token_hash):
                - raw_token: Le token brut a envoyer par email
                - token_hash: Le hash a stocker en base
        """
        raw_token = secrets.token_urlsafe(PasswordResetRepository.TOKEN_LENGTH)
        token_hash = PasswordResetRepository.hash_token(raw_token)
        return raw_token, token_hash

    def create_reset_token(
        self,
        user_id: int,
        expiry_hours: Optional[int] = None
    ) -> tuple[PasswordResetToken, str]:
        """
        Cree un nouveau token de reinitialisation.

        Args:
            user_id: ID de l'utilisateur
            expiry_hours: Duree de validite en heures (defaut: 1h)

        Returns:
            Tuple (token_obj, raw_token):
                - token_obj: L'objet PasswordResetToken cree
                - raw_token: Le token brut (a envoyer par email!)
        """
        if expiry_hours is None:
            expiry_hours = self.DEFAULT_EXPIRY_HOURS

        raw_token, token_hash = self.generate_token()

        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

        token_obj = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        self.session.add(token_obj)
        self.session.flush()

        return token_obj, raw_token

    def get_by_hash(self, token_hash: str) -> Optional[PasswordResetToken]:
        """
        Recupere un token par son hash.

        Args:
            token_hash: Hash SHA-256 du token

        Returns:
            Le PasswordResetToken si trouve, None sinon
        """
        return (
            self.session.query(self.model)
            .filter(self.model.token_hash == token_hash)
            .first()
        )

    def validate_token(self, raw_token: str) -> Optional[PasswordResetToken]:
        """
        Valide un token brut et retourne l'objet si valide.

        Cette methode:
        1. Hash le token brut
        2. Cherche le hash en base
        3. Verifie que le token est valide (non utilise, non expire)

        Args:
            raw_token: Le token brut a valider

        Returns:
            Le PasswordResetToken si valide, None sinon
        """
        token_hash = self.hash_token(raw_token)
        token_obj = self.get_by_hash(token_hash)

        if token_obj is None:
            return None

        if not token_obj.is_valid:
            return None

        return token_obj

    def use_token(self, token_id: int) -> bool:
        """
        Marque un token comme utilise.

        Un token utilise ne peut plus servir (usage unique).

        Args:
            token_id: ID du token

        Returns:
            True si marque, False si non trouve ou deja utilise
        """
        token_obj = self.get_by_id(token_id)

        if token_obj is None:
            return False

        if token_obj.is_used:
            return False

        token_obj.mark_as_used()
        self.session.flush()
        return True

    def invalidate_all_for_user(self, user_id: int) -> int:
        """
        Invalide tous les tokens d'un utilisateur.

        Cas d'usage: apres reset reussi, ou changement de mot de passe.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de tokens invalides
        """
        now = datetime.now(timezone.utc)

        updated = (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.used_at.is_(None))
            .update(
                {"used_at": now},
                synchronize_session='fetch'
            )
        )

        self.session.flush()
        return updated

    def get_pending_for_user(self, user_id: int) -> List[PasswordResetToken]:
        """
        Recupere les tokens en attente (non utilises, non expires) d'un user.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Liste des tokens en attente
        """
        now = datetime.now(timezone.utc)

        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.used_at.is_(None))
            .filter(self.model.expires_at > now)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def count_recent_requests(
        self,
        user_id: int,
        hours: int = 1
    ) -> int:
        """
        Compte les demandes de reset recentes pour un utilisateur.

        Utilise pour le rate limiting.

        Args:
            user_id: ID de l'utilisateur
            hours: Fenetre de temps en heures

        Returns:
            Nombre de demandes dans la fenetre
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        return (
            self.session.query(func.count(self.model.id))
            .filter(self.model.user_id == user_id)
            .filter(self.model.created_at >= cutoff)
            .scalar() or 0
        )

    def can_request_reset(self, user_id: int) -> bool:
        """
        Verifie si un utilisateur peut demander un reset (rate limiting).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si autorise, False si rate limited
        """
        recent_count = self.count_recent_requests(user_id, hours=1)
        return recent_count < self.MAX_REQUESTS_PER_HOUR

    def cleanup_expired(
        self,
        older_than_days: int = 7
    ) -> int:
        """
        Supprime les tokens expires ou utilises anciens.

        Args:
            older_than_days: Age minimum en jours pour suppression

        Returns:
            Nombre de tokens supprimes
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        # Supprimer les tokens expires OU utilises avant le cutoff
        deleted = (
            self.session.query(self.model)
            .filter(
                (self.model.expires_at < cutoff) |
                ((self.model.used_at.isnot(None)) & (self.model.used_at < cutoff))
            )
            .delete(synchronize_session=False)
        )

        return deleted

    def get_valid_token_for_user(self, user_id: int) -> Optional[PasswordResetToken]:
        """
        Recupere le token valide le plus recent pour un utilisateur.

        Utile pour eviter de generer plusieurs tokens.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Le token valide le plus recent ou None
        """
        now = datetime.now(timezone.utc)

        return (
            self.session.query(self.model)
            .filter(self.model.user_id == user_id)
            .filter(self.model.used_at.is_(None))
            .filter(self.model.expires_at > now)
            .order_by(self.model.created_at.desc())
            .first()
        )
