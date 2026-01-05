"""
Repository pour la gestion de la blacklist des tokens revoques.

Ce module gere la blacklist des tokens JWT revoques, permettant d'invalider
des access tokens avant leur expiration naturelle.

Fonctionnalites principales:
- Ajout de tokens a la blacklist (logout, compromission)
- Verification rapide si un token est blackliste
- Ajout en masse (logout global)
- Nettoyage des entrees obsoletes

Notes de securite:
- La verification is_revoked doit etre tres rapide (chaque requete)
- Les tokens expires peuvent etre purges de la blacklist
- En production, envisager un cache Redis pour les performances
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.session import RevokedToken
from app.repositories.base import BaseRepository


class RevokedTokenRepository(BaseRepository[RevokedToken]):
    """
    Repository pour la blacklist des tokens revoques.

    Gere l'ajout et la verification des tokens JWT revoques.
    Optimise pour des lookups rapides.
    """

    model = RevokedToken

    def add_to_blacklist(
        self,
        jti: str,
        expires_at: datetime,
        reason: Optional[str] = None
    ) -> bool:
        """
        Ajoute un token a la blacklist.

        L'operation est idempotente: ajouter un token deja blackliste
        ne leve pas d'erreur.

        Args:
            jti: JWT ID du token a revoquer
            expires_at: Date d'expiration originale du token
            reason: Raison de la revocation (optionnel, pour audit)

        Returns:
            True si le token a ete ajoute (ou existait deja)
        """
        revoked = RevokedToken(
            jti=jti,
            expires_at=expires_at,
        )

        self.session.add(revoked)

        try:
            self.session.flush()
        except IntegrityError:
            # Token deja dans la blacklist - c'est OK (idempotent)
            self.session.rollback()

        return True

    def is_revoked(self, jti: str) -> bool:
        """
        Verifie si un token est dans la blacklist.

        Cette methode est appelee a chaque verification de token,
        elle doit etre optimisee pour la performance.

        Args:
            jti: JWT ID du token a verifier

        Returns:
            True si le token est blackliste, False sinon
        """
        revoked = (
            self.session.query(self.model)
            .filter(self.model.jti == jti)
            .first()
        )

        # Un token est revoque s'il existe dans la blacklist,
        # meme si son entree est "expiree" (cleanup pas encore passe)
        return revoked is not None

    def cleanup_expired(self) -> int:
        """
        Supprime les entrees de tokens expires de la blacklist.

        Une fois qu'un token est expire, il n'a plus besoin d'etre
        dans la blacklist car il serait rejete de toute facon.

        Returns:
            Nombre d'entrees supprimees
        """
        now = datetime.now(timezone.utc)

        deleted = (
            self.session.query(self.model)
            .filter(self.model.expires_at < now)
            .delete(synchronize_session=False)
        )

        return deleted

    def bulk_add(self, tokens: List[dict]) -> int:
        """
        Ajoute plusieurs tokens a la blacklist en une operation.

        Optimise pour le logout global ou la revocation de masse.

        Args:
            tokens: Liste de dicts avec 'jti' et 'expires_at'

        Returns:
            Nombre de tokens ajoutes
        """
        if not tokens:
            return 0

        # Creer les objets RevokedToken
        revoked_tokens = []
        for token_data in tokens:
            revoked_tokens.append(
                RevokedToken(
                    jti=token_data["jti"],
                    expires_at=token_data["expires_at"],
                )
            )

        # Ajouter en masse
        self.session.add_all(revoked_tokens)

        try:
            self.session.flush()
        except IntegrityError:
            # Certains tokens peuvent deja exister - on ignore
            self.session.rollback()
            # Ajouter un par un pour ignorer les doublons
            count = 0
            for revoked in revoked_tokens:
                try:
                    self.session.add(revoked)
                    self.session.flush()
                    count += 1
                except IntegrityError:
                    self.session.rollback()
                    continue
            return count

        return len(revoked_tokens)
