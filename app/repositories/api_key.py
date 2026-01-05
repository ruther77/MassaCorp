"""
Repository pour la gestion des API Keys.

Ce module gere les API Keys pour l'authentification Machine-to-Machine (M2M),
permettant la creation, validation, revocation et listing des keys.

Fonctionnalites principales:
- Creation de keys avec hash SHA-256
- Validation de keys par hash
- Revocation individuelle ou par tenant
- Listing avec isolation multi-tenant
- Mise a jour du last_used_at

Notes de securite:
- Les keys brutes ne sont JAMAIS stockees en base
- Seul le hash SHA-256 est persiste
- Toutes les requetes respectent l'isolation multi-tenant
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session as SQLAlchemySession

from app.models.api_key import APIKey
from app.repositories.base import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    """
    Repository pour les API Keys M2M.

    Gere le cycle de vie des API Keys avec isolation multi-tenant.
    """

    model = APIKey

    # Prefix pour les API keys (ex: "mc_sk_" pour secret key)
    KEY_PREFIX = "mc_sk_"
    KEY_LENGTH = 32  # 32 bytes = 256 bits

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """
        Hash une API key avec SHA-256.

        Args:
            raw_key: La key brute a hasher

        Returns:
            Le hash SHA-256 en hexadecimal
        """
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """
        Genere une nouvelle API key securisee.

        Returns:
            Tuple (raw_key, key_hash):
                - raw_key: La key brute a afficher une seule fois
                - key_hash: Le hash a stocker en base
        """
        # Generer 32 bytes aleatoires (256 bits)
        random_bytes = secrets.token_hex(APIKeyRepository.KEY_LENGTH)
        raw_key = f"{APIKeyRepository.KEY_PREFIX}{random_bytes}"
        key_hash = APIKeyRepository.hash_key(raw_key)
        return raw_key, key_hash

    def create_api_key(
        self,
        tenant_id: int,
        name: str,
        expires_at: Optional[datetime] = None,
        created_by_user_id: Optional[int] = None,
        scopes: Optional[List[str]] = None
    ) -> tuple[APIKey, str]:
        """
        Cree une nouvelle API key.

        Args:
            tenant_id: ID du tenant
            name: Nom descriptif de la key
            expires_at: Date d'expiration (optionnel)
            created_by_user_id: ID de l'utilisateur createur
            scopes: Liste des scopes autorises (None = tous les droits)

        Returns:
            Tuple (api_key, raw_key):
                - api_key: L'objet APIKey cree
                - raw_key: La key brute (a afficher une seule fois!)
        """
        raw_key, key_hash = self.generate_key()

        # Extraire le prefix visible (premiers caracteres)
        key_prefix = raw_key[:12] + "..."

        api_key = APIKey(
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
            scopes=scopes
        )

        self.session.add(api_key)
        self.session.flush()

        return api_key, raw_key

    def get_by_hash(self, key_hash: str) -> Optional[APIKey]:
        """
        Recupere une API key par son hash.

        Args:
            key_hash: Hash SHA-256 de la key

        Returns:
            L'APIKey si trouvee, None sinon
        """
        return (
            self.session.query(self.model)
            .filter(self.model.key_hash == key_hash)
            .first()
        )

    def validate_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Valide une API key brute et retourne l'objet si valide.

        Cette methode:
        1. Hash la key brute
        2. Cherche le hash en base
        3. Verifie que la key est active (non revoquee, non expiree)

        Args:
            raw_key: La key brute a valider

        Returns:
            L'APIKey si valide, None sinon
        """
        key_hash = self.hash_key(raw_key)
        api_key = self.get_by_hash(key_hash)

        if api_key is None:
            return None

        if not api_key.is_valid:
            return None

        return api_key

    def update_last_used(self, api_key_id: int) -> bool:
        """
        Met a jour le timestamp last_used_at d'une API key.

        Args:
            api_key_id: ID de l'API key

        Returns:
            True si mise a jour, False si non trouvee
        """
        api_key = self.get_by_id(api_key_id)
        if api_key is None:
            return False

        api_key.update_last_used()
        self.session.flush()
        return True

    def revoke(self, api_key_id: int, tenant_id: Optional[int] = None) -> bool:
        """
        Revoque une API key.

        Args:
            api_key_id: ID de l'API key a revoquer
            tenant_id: ID du tenant (pour verification d'isolation)

        Returns:
            True si revoquee, False si non trouvee ou mauvais tenant
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.id == api_key_id)
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        api_key = query.first()

        if api_key is None:
            return False

        api_key.revoke()
        self.session.flush()
        return True

    def get_by_tenant(
        self,
        tenant_id: int,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[APIKey]:
        """
        Liste les API keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            include_revoked: Inclure les keys revoquees
            skip: Offset pour pagination
            limit: Limite pour pagination

        Returns:
            Liste des API keys
        """
        query = (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
        )

        if not include_revoked:
            query = query.filter(self.model.revoked_at.is_(None))

        return (
            query
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_by_tenant(self, tenant_id: int) -> List[APIKey]:
        """
        Liste les API keys actives (non revoquees, non expirees) d'un tenant.

        Args:
            tenant_id: ID du tenant

        Returns:
            Liste des API keys actives
        """
        now = datetime.now(timezone.utc)

        return (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .filter(self.model.revoked_at.is_(None))
            .filter(
                (self.model.expires_at.is_(None)) |
                (self.model.expires_at > now)
            )
            .order_by(self.model.created_at.desc())
            .all()
        )

    def count_by_tenant(
        self,
        tenant_id: int,
        include_revoked: bool = False
    ) -> int:
        """
        Compte les API keys d'un tenant.

        Args:
            tenant_id: ID du tenant
            include_revoked: Inclure les keys revoquees

        Returns:
            Nombre de keys
        """
        from sqlalchemy import func

        query = (
            self.session.query(func.count(self.model.id))
            .filter(self.model.tenant_id == tenant_id)
        )

        if not include_revoked:
            query = query.filter(self.model.revoked_at.is_(None))

        return query.scalar() or 0

    def revoke_all_by_tenant(self, tenant_id: int) -> int:
        """
        Revoque toutes les API keys d'un tenant.

        Cas d'usage: compromission du tenant, desactivation du compte.

        Args:
            tenant_id: ID du tenant

        Returns:
            Nombre de keys revoquees
        """
        now = datetime.now(timezone.utc)

        updated = (
            self.session.query(self.model)
            .filter(self.model.tenant_id == tenant_id)
            .filter(self.model.revoked_at.is_(None))
            .update(
                {"revoked_at": now},
                synchronize_session='fetch'
            )
        )

        self.session.flush()
        return updated

    def cleanup_expired(
        self,
        older_than_days: int = 90,
        tenant_id: Optional[int] = None
    ) -> int:
        """
        Supprime les API keys revoquees ou expirees anciennes.

        Args:
            older_than_days: Age minimum en jours pour suppression
            tenant_id: Limiter au tenant specifie (None = tous)

        Returns:
            Nombre de keys supprimees
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        query = (
            self.session.query(self.model)
            .filter(
                (self.model.revoked_at.isnot(None) & (self.model.revoked_at < cutoff)) |
                (self.model.expires_at.isnot(None) & (self.model.expires_at < cutoff))
            )
        )

        if tenant_id is not None:
            query = query.filter(self.model.tenant_id == tenant_id)

        deleted = query.delete(synchronize_session=False)
        return deleted
