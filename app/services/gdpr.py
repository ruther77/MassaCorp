"""
Service GDPR pour MassaCorp API.

Gere:
- Export des donnees utilisateur (Right to Access - Art. 15)
- Suppression des donnees (Right to Deletion - Art. 17)
- Anonymisation des donnees
- Inventaire des donnees (Art. 30)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFound
from app.repositories.user import UserRepository
from app.repositories.session import SessionRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.mfa import MFASecretRepository, MFARecoveryCodeRepository
from app.repositories.api_key import APIKeyRepository

logger = logging.getLogger(__name__)


class GDPRService:
    """
    Service de conformite GDPR.

    Fonctionnalites:
    - export_user_data: Exporte toutes les donnees d'un utilisateur (Art. 15)
    - delete_user_data: Supprime toutes les donnees (Art. 17)
    - anonymize_user_data: Anonymise les donnees (alternative au delete)
    - get_data_inventory: Inventaire des donnees collectees (Art. 30)
    """

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: SessionRepository,
        audit_repository: AuditLogRepository,
        mfa_secret_repository: Optional[MFASecretRepository] = None,
        mfa_recovery_repository: Optional[MFARecoveryCodeRepository] = None,
        api_key_repository: Optional[APIKeyRepository] = None
    ):
        """
        Initialise le service GDPR.

        Args:
            user_repository: Repository pour les utilisateurs
            session_repository: Repository pour les sessions
            audit_repository: Repository pour les logs d'audit
            mfa_secret_repository: Repository pour les secrets MFA
            mfa_recovery_repository: Repository pour les codes de recuperation MFA
            api_key_repository: Repository pour les API keys
        """
        self.user_repo = user_repository
        self.session_repo = session_repository
        self.audit_repo = audit_repository
        self.mfa_secret_repo = mfa_secret_repository
        self.mfa_recovery_repo = mfa_recovery_repository
        self.api_key_repo = api_key_repository

    def export_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Exporte toutes les donnees d'un utilisateur (GDPR Art. 15).

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Dict contenant toutes les donnees utilisateur

        Raises:
            NotFound: Si l'utilisateur n'existe pas
        """
        logger.info(f"GDPR: Export demande pour utilisateur {user_id}")

        # Recuperer l'utilisateur
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFound("User")

        # Recuperer les sessions
        sessions = self.session_repo.get_all_sessions(user_id=user_id)

        # Recuperer les logs d'audit
        audit_logs = self.audit_repo.get_by_user(user_id, limit=1000)

        # Recuperer les donnees MFA (si repository disponible)
        mfa_data = None
        if self.mfa_secret_repo:
            mfa_secret = self.mfa_secret_repo.get_by_user_id(user_id)
            if mfa_secret:
                mfa_data = {
                    "enabled": mfa_secret.enabled,
                    "created_at": mfa_secret.created_at.isoformat() if mfa_secret.created_at else None,
                    "last_used_at": mfa_secret.last_used_at.isoformat() if mfa_secret.last_used_at else None,
                }

        # Recuperer les codes de recuperation MFA (si repository disponible)
        recovery_codes_data = []
        if self.mfa_recovery_repo:
            recovery_codes = self.mfa_recovery_repo.get_all_for_user(user_id)
            recovery_codes_data = [
                {
                    "id": code.id,
                    "is_used": code.used_at is not None,
                    "used_at": code.used_at.isoformat() if code.used_at else None,
                    "created_at": code.created_at.isoformat() if code.created_at else None,
                }
                for code in recovery_codes
            ]

        # Recuperer les API keys creees par l'utilisateur (si repository disponible)
        api_keys_data = []
        if self.api_key_repo:
            # Recuperer les API keys du tenant de l'utilisateur
            api_keys = self.api_key_repo.get_by_tenant(user.tenant_id, include_revoked=True)
            # Filtrer celles creees par cet utilisateur
            api_keys_data = [
                {
                    "id": key.id,
                    "name": key.name,
                    "key_prefix": key.key_prefix,
                    "scopes": key.scopes,
                    "created_at": key.created_at.isoformat() if key.created_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                    "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "is_valid": key.is_valid,
                }
                for key in api_keys
                if key.created_by_user_id == user_id
            ]

        # Compiler l'export
        export_data = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "user": {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
                "tenant_id": user.tenant_id,
                "mfa_enabled": getattr(user, 'mfa_enabled', False),
            },
            "sessions": [
                {
                    "id": str(s.id),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "ip_address": getattr(s, 'ip', None),
                    "user_agent": getattr(s, 'user_agent', None),
                    "is_active": s.revoked_at is None,
                    "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
                }
                for s in sessions
            ],
            "audit_logs": [
                {
                    "event_type": getattr(log, 'event_type', None),
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                    "ip_address": getattr(log, 'ip', None),
                }
                for log in audit_logs
            ],
            "mfa_data": mfa_data,
            "recovery_codes": recovery_codes_data,
            "api_keys": api_keys_data,
            "data_retention": {
                "policy": "12 mois pour les logs d'audit, sessions expirent apres 30 jours",
                "contact": "privacy@massacorp.dev"
            }
        }

        logger.info(f"GDPR: Export termine pour utilisateur {user_id}")
        return export_data

    def delete_user_data(
        self,
        user_id: int,
        reason: str,
        performed_by: Optional[int] = None
    ) -> bool:
        """
        Supprime toutes les donnees d'un utilisateur (GDPR Art. 17).

        ATTENTION: Cette operation est irreversible!

        Args:
            user_id: ID de l'utilisateur a supprimer
            reason: Raison de la suppression (pour audit)
            performed_by: ID de l'admin effectuant la suppression

        Returns:
            True si succes

        Raises:
            NotFound: Si l'utilisateur n'existe pas
        """
        logger.warning(
            f"GDPR: Suppression demandee pour utilisateur {user_id}, "
            f"raison: {reason}, par: {performed_by}"
        )

        # Verifier que l'utilisateur existe
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFound("User")

        tenant_id = user.tenant_id

        # Supprimer les donnees MFA (avant suppression user pour eviter FK errors)
        if self.mfa_secret_repo:
            self.mfa_secret_repo.delete_by_user_id(user_id)

        if self.mfa_recovery_repo:
            self.mfa_recovery_repo.delete_all_for_user(user_id)

        # Revoquer toutes les sessions d'abord
        self.session_repo.invalidate_all_sessions(user_id=user_id)

        # Supprimer l'utilisateur (cascade supprime sessions)
        deleted = self.user_repo.delete(user_id)

        if deleted:
            # Logger la suppression (ce log reste pour conformite)
            self.audit_repo.create({
                "event_type": "gdpr_user_deletion",
                "user_id": performed_by,  # Qui a fait la suppression
                "tenant_id": tenant_id,
                "extra_data": {
                    "deleted_user_id": user_id,
                    "reason": reason,
                    "performed_by": performed_by,
                }
            })

            logger.warning(f"GDPR: Suppression terminee pour utilisateur {user_id}")

        return deleted

    def anonymize_user_data(
        self,
        user_id: int,
        reason: str,
        performed_by: Optional[int] = None
    ) -> bool:
        """
        Anonymise les donnees utilisateur (alternative a la suppression).

        Conserve la structure mais remplace les PII par des valeurs anonymes.
        L'utilisateur ne peut plus se connecter mais les donnees statistiques
        restent exploitables.

        Args:
            user_id: ID de l'utilisateur
            reason: Raison de l'anonymisation
            performed_by: ID de l'admin effectuant l'operation

        Returns:
            True si succes

        Raises:
            NotFound: Si l'utilisateur n'existe pas
        """
        logger.info(f"GDPR: Anonymisation demandee pour utilisateur {user_id}")

        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFound("User")

        tenant_id = user.tenant_id

        # Generer des valeurs anonymes
        anonymous_email = f"deleted_{user_id}@anonymized.local"

        # Mettre a jour l'utilisateur avec des donnees anonymes
        self.user_repo.update(user_id, {
            "email": anonymous_email,
            "password_hash": "ANONYMIZED_USER_CANNOT_LOGIN",
            "is_active": False,
        })

        # Supprimer les donnees MFA (l'utilisateur ne pourra plus se connecter)
        if self.mfa_secret_repo:
            self.mfa_secret_repo.delete_by_user_id(user_id)

        if self.mfa_recovery_repo:
            self.mfa_recovery_repo.delete_all_for_user(user_id)

        # Revoquer toutes les sessions
        self.session_repo.invalidate_all_sessions(user_id=user_id)

        # Logger l'anonymisation
        self.audit_repo.create({
            "event_type": "gdpr_user_anonymization",
            "user_id": performed_by,
            "tenant_id": tenant_id,
            "extra_data": {
                "anonymized_user_id": user_id,
                "reason": reason,
                "performed_by": performed_by,
            }
        })

        logger.info(f"GDPR: Anonymisation terminee pour utilisateur {user_id}")
        return True

    def get_data_inventory(self, tenant_id: int) -> Dict[str, Any]:
        """
        Retourne l'inventaire des donnees pour un tenant (GDPR Art. 30).

        Args:
            tenant_id: ID du tenant

        Returns:
            Inventaire des types de donnees collectees
        """
        return {
            "tenant_id": tenant_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_categories": [
                {
                    "category": "Donnees d'identite",
                    "fields": ["email", "user_id"],
                    "purpose": "Authentification et gestion de compte",
                    "retention": "Jusqu'a suppression du compte",
                    "legal_basis": "Execution du contrat"
                },
                {
                    "category": "Donnees techniques",
                    "fields": ["ip_address", "user_agent", "session_id"],
                    "purpose": "Securite et prevention de la fraude",
                    "retention": "30 jours pour sessions, 12 mois pour audit",
                    "legal_basis": "Interet legitime (securite)"
                },
                {
                    "category": "Donnees d'activite",
                    "fields": ["login_attempts", "audit_logs"],
                    "purpose": "Monitoring de securite et conformite",
                    "retention": "12 mois",
                    "legal_basis": "Obligation legale"
                },
                {
                    "category": "Donnees MFA",
                    "fields": ["totp_secret", "recovery_codes"],
                    "purpose": "Authentification multi-facteur",
                    "retention": "Jusqu'a desactivation MFA",
                    "legal_basis": "Consentement explicite"
                },
                {
                    "category": "API Keys",
                    "fields": ["api_key_hash", "api_key_name", "scopes", "usage_logs"],
                    "purpose": "Authentification machine-to-machine (M2M)",
                    "retention": "Jusqu'a revocation ou expiration",
                    "legal_basis": "Execution du contrat"
                }
            ],
            "data_processors": [
                {
                    "name": "Base de donnees PostgreSQL",
                    "location": "Auto-heberge / Fournisseur cloud",
                    "dpa_in_place": True
                }
            ],
            "data_subject_rights": {
                "access": "GET /api/v1/gdpr/export",
                "deletion": "DELETE /api/v1/gdpr/delete",
                "portability": "GET /api/v1/gdpr/export (format JSON)",
                "rectification": "PATCH /api/v1/users/me"
            }
        }
