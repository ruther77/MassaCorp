"""
Service Authentification pour MassaCorp
Logique metier pour login, tokens, sessions

Ce module fournit le service d'authentification complet:
- Authentification email/password avec protection brute-force
- Generation et rotation des tokens JWT (access + refresh)
- Gestion des sessions utilisateur
- Audit logging des evenements de securite
- Integration multi-tenant complete

Securite:
- Protection contre les attaques brute-force via lockout
- Rotation automatique des refresh tokens
- Revocation des tokens via blacklist Redis
- Audit trail complet pour compliance
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, TYPE_CHECKING
from uuid import UUID

logger = logging.getLogger(__name__)

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    verify_and_rehash,
    get_token_payload,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    DUMMY_HASH,
)
from app.core.config import get_settings
from app.core.logging import mask_email
from app.models import User
from app.repositories.user import UserRepository
from app.services.exceptions import (
    InvalidCredentialsError,
    InactiveUserError,
    InvalidTokenError,
    AccountLockedError,
)

# Type checking imports pour eviter les imports circulaires
if TYPE_CHECKING:
    from app.services.session import SessionService
    from app.services.token import TokenService
    from app.services.audit import AuditService
    from app.services.mfa import MFAService


class AuthService:
    """
    Service pour l'authentification complete.

    Contient la logique metier pour:
    - Authentification (email/password) avec protection brute-force
    - Generation de tokens JWT (access + refresh)
    - Refresh de tokens avec rotation
    - Gestion des sessions utilisateur
    - Audit logging des evenements de securite

    Integration Phase 2:
    - SessionService: creation/termination des sessions
    - TokenService: stockage/revocation des refresh tokens
    - AuditService: logging des actions sensibles

    Configuration brute-force protection:
    - MAX_LOGIN_ATTEMPTS: 5 echecs avant lockout
    - LOCKOUT_MINUTES: 30 minutes de verrouillage
    """

    # Configuration protection brute-force
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_MINUTES = 30

    # Configuration MFA session token
    MFA_SESSION_TOKEN_EXPIRE_MINUTES = 5  # 5 minutes pour completer MFA

    def __init__(
        self,
        user_repository: UserRepository,
        session_service: Optional["SessionService"] = None,
        token_service: Optional["TokenService"] = None,
        audit_service: Optional["AuditService"] = None,
        mfa_service: Optional["MFAService"] = None
    ):
        """
        Initialise le service avec les repositories et services.

        Args:
            user_repository: Repository pour les users (obligatoire)
            session_service: Service de gestion des sessions (Phase 2)
            token_service: Service de gestion des tokens (Phase 2)
            audit_service: Service d'audit logging (Phase 2)
            mfa_service: Service MFA pour TOTP (Phase 3)

        Note:
            Les services Phase 2/3 sont optionnels pour la retrocompatibilite.
            S'ils sont fournis, les fonctionnalites avancees sont activees.
        """
        self.user_repository = user_repository
        self.session_service = session_service
        self.token_service = token_service
        self.audit_service = audit_service
        self.mfa_service = mfa_service

        # Warning si MFA service non injecte - MFA sera ignore
        if self.mfa_service is None:
            logger.warning(
                "AuthService initialise sans mfa_service - "
                "la verification MFA sera desactivee. "
                "Injecter MFAService pour activer le MFA."
            )

    def authenticate(
        self,
        email: str,
        password: str,
        tenant_id: int
    ) -> Optional[User]:
        """
        Authentifie un utilisateur par email et mot de passe.

        SECURITE: Cette methode utilise DUMMY_HASH pour empecher les timing attacks
        qui permettraient de detecter si un email existe en base.

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair
            tenant_id: ID du tenant

        Returns:
            User si authentification reussie, None sinon
        """
        # Chercher l'utilisateur
        user = self.user_repository.get_by_email_and_tenant(
            email=email.lower().strip(),
            tenant_id=tenant_id
        )

        # TIMING-SAFE: Toujours faire une verification de hash
        # meme si l'utilisateur n'existe pas (empeche enumeration par timing)
        if user is None:
            # Verifier contre DUMMY_HASH pour maintenir un temps constant
            verify_password(password, DUMMY_HASH)
            return None

        # ----------------------------------------------------------------
        # Etape 2.5: Verification email si exigee
        # ----------------------------------------------------------------
        settings = get_settings()
        if settings.EMAIL_VERIFICATION_REQUIRED and not user.is_verified:
            # Enregistrer l'echec de connexion sans reveler le statut du compte
            self._record_login_attempt(
                email=normalized_email,
                tenant_id=tenant_id,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self._log_audit_event(
                action="login_failed",
                user_id=None,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={"email": normalized_email, "reason": "email_unverified"}
            )
            return None

        # Verifier que le compte est actif
        if not user.is_active:
            # Toujours verifier le password meme si inactif (timing-safe)
            verify_password(password, user.password_hash)
            return None

        # Verifier le mot de passe et migration Argon2id si necessaire
        is_valid, new_hash = verify_and_rehash(password, user.password_hash)

        if not is_valid:
            return None

        # Re-hash progressif bcrypt -> Argon2id
        if new_hash:
            self.user_repository.update_password(user.id, new_hash)
            logger.info(f"Password rehashed to Argon2id for user_id={user.id}")

        return user

    def login(
        self,
        email: str,
        password: str,
        tenant_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Connecte un utilisateur et retourne les tokens.

        Processus complet:
        1. Verification du lockout (brute-force protection)
        2. Authentification email/password
        3. Creation de session (Phase 2)
        4. Generation et stockage des tokens (Phase 2)
        5. Logging audit (Phase 2)
        6. Enregistrement tentative de connexion (Phase 2)

        Args:
            email: Email de l'utilisateur
            password: Mot de passe en clair
            tenant_id: ID du tenant
            ip_address: Adresse IP du client (optionnel, pour audit)
            user_agent: User-Agent du client (optionnel, pour audit)

        Returns:
            Dict avec access_token, refresh_token, expires_in, session_id
            ou None si echec d'authentification

        Raises:
            AccountLockedError: Si le compte est verrouille (trop de tentatives)
        """
        normalized_email = email.lower().strip()

        # ----------------------------------------------------------------
        # Etape 1: Verification brute-force protection
        # ----------------------------------------------------------------
        if self.session_service:
            is_locked = self.session_service.is_account_locked(
                email=normalized_email,
                tenant_id=tenant_id,
                max_attempts=self.MAX_LOGIN_ATTEMPTS,
                lockout_minutes=self.LOCKOUT_MINUTES
            )
            if is_locked:
                # Logger la tentative sur compte verrouille
                self._log_audit_event(
                    action="login_attempt_locked",
                    user_id=None,
                    tenant_id=tenant_id,
                    ip_address=ip_address,
                    details={"email": normalized_email, "reason": "account_locked"}
                )
                raise AccountLockedError(
                    email=normalized_email,
                    lockout_minutes=self.LOCKOUT_MINUTES
                )

        # ----------------------------------------------------------------
        # Etape 2: Authentification
        # ----------------------------------------------------------------
        user = self.authenticate(email, password, tenant_id)

        if user is None:
            # Enregistrer l'echec de connexion
            self._record_login_attempt(
                email=normalized_email,
                tenant_id=tenant_id,
                success=False,
                ip_address=ip_address,
                user_agent=user_agent
            )
            # Logger l'echec d'authentification
            self._log_audit_event(
                action="login_failed",
                user_id=None,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={"email": normalized_email, "reason": "invalid_credentials"}
            )
            return None

        # ----------------------------------------------------------------
        # Etape 3: Verification MFA (Phase 3)
        # ----------------------------------------------------------------
        if self.mfa_service and self.mfa_service.is_mfa_enabled(user.id):
            # MFA active - retourner mfa_session_token pour flow 2 etapes
            mfa_session_token = self._create_mfa_session_token(
                user_id=user.id,
                tenant_id=user.tenant_id
            )

            # Logger la tentative MFA
            self._log_audit_event(
                action="login_mfa_required",
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                details={"email": user.email}
            )

            return {
                "mfa_required": True,
                "mfa_session_token": mfa_session_token,
                "message": "MFA verification required"
            }

        # ----------------------------------------------------------------
        # Etape 4: Creation de session (Phase 2) - AVANT tokens pour avoir session_id
        # ----------------------------------------------------------------
        session_id = None
        if self.session_service:
            session = self.session_service.create_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            if session:
                session_id = str(session.id)
                # Mise a jour last_login APRES creation session reussie
                self.user_repository.update_last_login(user.id)
            else:
                logger.warning(
                    f"Session creation failed for user_id={user.id}, "
                    f"tenant_id={user.tenant_id} - login continues without session tracking"
                )
        else:
            # Pas de session_service: MAJ last_login quand meme
            self.user_repository.update_last_login(user.id)

        # ----------------------------------------------------------------
        # Etape 5: Generation des tokens (avec session_id)
        # ----------------------------------------------------------------
        access_token = create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            extra_claims={"email": user.email},
            session_id=session_id
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            tenant_id=user.tenant_id
        )

        # Extraire le JTI du refresh token pour stockage
        refresh_payload = get_token_payload(refresh_token)
        refresh_jti = refresh_payload.get("jti") if refresh_payload else None
        refresh_exp = None
        if refresh_payload and refresh_payload.get("exp"):
            try:
                refresh_exp = datetime.fromtimestamp(
                    refresh_payload.get("exp"),
                    tz=timezone.utc
                )
            except (TypeError, ValueError, OSError) as e:
                # SECURITE: Log et continue sans exp - le token sera invalide au refresh
                logger.warning(f"Impossible de parser exp du refresh token: {e}")

        # ----------------------------------------------------------------
        # Etape 6: Stockage du refresh token (Phase 2)
        # ----------------------------------------------------------------
        if self.token_service and refresh_jti and refresh_exp:
            self.token_service.store_refresh_token(
                jti=refresh_jti,
                user_id=user.id,
                tenant_id=user.tenant_id,
                expires_at=refresh_exp,
                session_id=session_id,
                raw_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # ----------------------------------------------------------------
        # Etape 7: Enregistrement tentative reussie (Phase 2)
        # ----------------------------------------------------------------
        self._record_login_attempt(
            email=normalized_email,
            tenant_id=tenant_id,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # ----------------------------------------------------------------
        # Etape 8: Logging audit (Phase 2)
        # ----------------------------------------------------------------
        self._log_audit_event(
            action="login_success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={
                "email": user.email,
                "session_id": session_id,
                "token_jti": refresh_jti
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": session_id,
        }

    def create_session_tokens(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cree une session et des tokens pour un utilisateur authentifie via OAuth.

        Cette methode est utilisee par le service OAuth pour creer des tokens
        apres une authentification reussie via un provider externe.

        Args:
            user: Utilisateur authentifie
            ip_address: Adresse IP du client
            user_agent: User-Agent du navigateur

        Returns:
            Dict avec access_token, refresh_token, token_type, expires_in
        """
        # Creation de session
        session_id = None
        if self.session_service:
            session = self.session_service.create_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            if session:
                session_id = str(session.id)
                self.user_repository.update_last_login(user.id)
        else:
            self.user_repository.update_last_login(user.id)

        # Generation des tokens
        access_token = create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            extra_claims={"email": user.email},
            session_id=session_id
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            tenant_id=user.tenant_id
        )

        # Stockage du refresh token
        refresh_payload = get_token_payload(refresh_token)
        refresh_jti = refresh_payload.get("jti") if refresh_payload else None
        refresh_exp = None
        if refresh_payload and refresh_payload.get("exp"):
            try:
                refresh_exp = datetime.fromtimestamp(
                    refresh_payload.get("exp"),
                    tz=timezone.utc
                )
            except (TypeError, ValueError, OSError):
                pass

        if self.token_service and refresh_jti and refresh_exp:
            self.token_service.store_refresh_token(
                jti=refresh_jti,
                user_id=user.id,
                tenant_id=user.tenant_id,
                expires_at=refresh_exp,
                session_id=session_id,
                raw_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # Audit logging
        self._log_audit_event(
            action="oauth_login_success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={
                "email": user.email,
                "session_id": session_id,
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": session_id,
        }

    def logout(
        self,
        user_id: int,
        tenant_id: int,
        refresh_token: Optional[str] = None,
        session_id: Optional[str] = None,
        all_sessions: bool = False,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Deconnecte un utilisateur avec revocation complete.

        Processus complet:
        1. Revocation du refresh token specifique (si fourni)
        2. Termination de la session specifique (si fournie)
        3. Si all_sessions: revocation de tous les tokens et sessions
        4. Logging audit

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            refresh_token: Token de refresh a revoquer (optionnel)
            session_id: ID de la session a terminer (optionnel)
            all_sessions: Revoquer toutes les sessions de l'utilisateur
            ip_address: IP pour l'audit logging

        Returns:
            True si succes
        """
        revoked_tokens = 0
        terminated_sessions = 0

        # ----------------------------------------------------------------
        # Cas 1: Revocation de toutes les sessions
        # ----------------------------------------------------------------
        if all_sessions:
            # Revoquer tous les tokens de l'utilisateur
            if self.token_service:
                revoked_tokens = self.token_service.revoke_all_user_tokens(
                    user_id=user_id,
                    tenant_id=tenant_id
                )

            # Terminer toutes les sessions
            if self.session_service:
                terminated_sessions = self.session_service.terminate_all_sessions(
                    user_id=user_id
                )

            # Logger l'evenement
            self._log_audit_event(
                action="logout_all_sessions",
                user_id=user_id,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={
                    "revoked_tokens": revoked_tokens,
                    "terminated_sessions": terminated_sessions
                }
            )
            return True

        # ----------------------------------------------------------------
        # Cas 2: Revocation d'une session specifique
        # ----------------------------------------------------------------
        # Revoquer le refresh token si fourni
        if refresh_token and self.token_service:
            payload = get_token_payload(refresh_token)
            if payload and payload.get("jti"):
                self.token_service.revoke_refresh_token(
                    jti=payload.get("jti"),
                    add_to_blacklist=True
                )
                revoked_tokens = 1

        # Terminer la session si fournie
        if session_id and self.session_service:
            try:
                session_uuid = UUID(session_id)
                self.session_service.terminate_session(
                    session_id=session_uuid,
                    user_id=user_id
                )
                terminated_sessions = 1
            except (ValueError, TypeError) as e:
                # session_id invalide - log pour debug mais on continue
                logger.debug(f"Invalid session_id ignored during logout: {e}")

        # Logger l'evenement
        self._log_audit_event(
            action="logout",
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address=ip_address,
            details={
                "session_id": session_id,
                "token_revoked": revoked_tokens > 0
            }
        )

        return True

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Valide et decode un token JWT

        Args:
            token: Token JWT a valider

        Returns:
            Payload decode ou None si invalide
        """
        try:
            payload = decode_token(token)
            return payload
        except Exception as e:
            logger.debug(f"Token validation failed: {e}")
            return None

    def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Rafraichit les tokens avec rotation securisee.

        Processus complet:
        1. Validation du refresh token (format, signature, expiration)
        2. Verification dans la blacklist Redis (Phase 2)
        3. Detection de replay attack (Phase 2)
        4. Rotation du token (ancien revoque, nouveau cree)
        5. Logging audit

        Args:
            refresh_token: Token de refresh valide
            ip_address: IP pour l'audit logging

        Returns:
            Dict avec nouveaux tokens ou None si invalide

        Raises:
            TokenReplayDetectedError: Si tentative de replay detectee
        """
        # ----------------------------------------------------------------
        # Etape 1: Validation du token
        # ----------------------------------------------------------------
        payload = self.validate_token(refresh_token)
        if payload is None:
            return None

        # Verifier que c'est un refresh token
        token_type = payload.get("type")
        if token_type != "refresh":
            return None

        old_jti = payload.get("jti")

        # Valider sub de maniere securisee
        sub = payload.get("sub")
        if sub is None:
            return None

        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            return None

        if user_id <= 0:
            return None

        tenant_id = payload.get("tenant_id")

        # ----------------------------------------------------------------
        # Etape 2: Verification blacklist (Phase 2)
        # ----------------------------------------------------------------
        if self.token_service and old_jti:
            # Verifier si le token est revoque
            if self.token_service.is_token_revoked(old_jti):
                self._log_audit_event(
                    action="refresh_token_revoked",
                    user_id=user_id,
                    tenant_id=tenant_id,
                    ip_address=ip_address,
                    details={"jti": old_jti, "reason": "token_revoked"}
                )
                return None

            # Detecter les attaques de replay
            if self.token_service.detect_token_replay(old_jti):
                # Attaque detectee! Revoquer tous les tokens de l'utilisateur
                self.token_service.revoke_all_user_tokens(
                    user_id=user_id,
                    tenant_id=tenant_id
                )
                self._log_audit_event(
                    action="token_replay_detected",
                    user_id=user_id,
                    tenant_id=tenant_id,
                    ip_address=ip_address,
                    details={"jti": old_jti, "action": "all_tokens_revoked"}
                )
                # Importer ici pour eviter import circulaire
                from app.services.token import TokenReplayDetectedError
                raise TokenReplayDetectedError(jti=old_jti)

        # ----------------------------------------------------------------
        # Etape 3: Verifier la session (Phase 2)
        # ----------------------------------------------------------------
        session_id = None
        if self.token_service and old_jti:
            old_token = self.token_service.refresh_token_repository.get_by_jti(old_jti)
            if old_token and old_token.session_id:
                session_id = str(old_token.session_id)
                # Verifier que la session est encore active
                if self.session_service:
                    session = self.session_service.get_session_by_id(old_token.session_id)
                    if session is None or not session.is_active:
                        self._log_audit_event(
                            action="refresh_token_session_revoked",
                            user_id=user_id,
                            tenant_id=tenant_id,
                            ip_address=ip_address,
                            details={"jti": old_jti, "session_id": session_id}
                        )
                        return None

        # ----------------------------------------------------------------
        # Etape 4: Recuperer l'utilisateur
        # ----------------------------------------------------------------
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            return None

        # ----------------------------------------------------------------
        # Etape 5: Generation des nouveaux tokens (avec session_id)
        # ----------------------------------------------------------------
        access_token = create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            extra_claims={"email": user.email},
            session_id=session_id
        )
        new_refresh_token = create_refresh_token(
            subject=user.id,
            tenant_id=user.tenant_id
        )

        # Extraire les infos du nouveau token
        new_payload = get_token_payload(new_refresh_token)
        new_jti = new_payload.get("jti") if new_payload else None
        new_exp = None
        if new_payload and new_payload.get("exp"):
            try:
                new_exp = datetime.fromtimestamp(
                    new_payload.get("exp"),
                    tz=timezone.utc
                )
            except (TypeError, ValueError, OSError) as e:
                logger.warning(f"Impossible de parser exp du nouveau refresh token: {e}")

        # ----------------------------------------------------------------
        # Etape 6: Rotation du token (Phase 2)
        # ----------------------------------------------------------------
        if self.token_service and old_jti and new_jti:
            # session_id deja recupere a l'etape 3

            # Effectuer la rotation (marque l'ancien comme utilise)
            self.token_service.rotate_refresh_token(
                old_jti=old_jti,
                new_jti=new_jti,
                new_expires_at=new_exp,
                session_id=session_id
            )

            # Stocker le nouveau token avec le meme session_id
            if new_exp and session_id:
                self.token_service.store_refresh_token(
                    jti=new_jti,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    expires_at=new_exp,
                    session_id=session_id,
                    raw_token=new_refresh_token,
                    ip_address=ip_address
                )
            else:
                # Log si le token n'a pas pu etre stocke
                logger.warning(
                    f"Refresh token non stocke pour user_id={user.id}: "
                    f"new_exp={new_exp is not None}, session_id={session_id is not None}"
                )

        # ----------------------------------------------------------------
        # Etape 6: Logging audit
        # ----------------------------------------------------------------
        self._log_audit_event(
            action="token_refresh",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={
                "old_jti": old_jti,
                "new_jti": new_jti
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    def get_current_user(self, token: str) -> Optional[User]:
        """
        Recupere l'utilisateur courant depuis un token

        Args:
            token: Token JWT d'acces

        Returns:
            User ou None si token invalide
        """
        payload = self.validate_token(token)
        if payload is None:
            return None

        # Verifier que c'est un access token
        token_type = payload.get("type")
        if token_type != "access":
            return None

        # Valider sub de maniere securisee
        sub = payload.get("sub")
        if sub is None:
            return None

        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            return None

        if user_id <= 0:
            return None

        # Recuperer l'utilisateur
        user = self.user_repository.get_by_id(user_id)

        if user is None or not user.is_active:
            return None

        return user

    # ========================================================================
    # Methodes privees pour l'integration Phase 2
    # ========================================================================

    def _log_audit_event(
        self,
        action: str,
        user_id: Optional[int],
        tenant_id: int,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log un evenement d'audit (si AuditService disponible).

        Cette methode est silencieuse en cas d'erreur pour ne pas
        bloquer le flux d'authentification.

        Args:
            action: Type d'action (login_success, login_failed, logout, etc.)
            user_id: ID de l'utilisateur (None si echec d'auth)
            tenant_id: ID du tenant
            ip_address: Adresse IP du client
            details: Details supplementaires a logger
        """
        if not self.audit_service:
            return

        try:
            self.audit_service.log_action(
                action=action,
                user_id=user_id,
                tenant_id=tenant_id,
                resource="auth",  # Corrige: resource au lieu de resource_type
                resource_id=user_id if user_id else None,  # None si pas d'user (login failed)
                ip_address=ip_address,
                details=details
            )
        except Exception as e:
            # Logger l'erreur mais ne pas bloquer l'authentification
            logger.warning(f"Error logging audit action={action}: {e}")

    def _record_login_attempt(
        self,
        email: str,
        tenant_id: int,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Enregistre une tentative de connexion (si SessionService disponible).

        Utilise pour la protection brute-force. Les tentatives echouees
        sont comptabilisees pour le lockout.

        Args:
            email: Email utilise pour la tentative
            tenant_id: ID du tenant
            success: True si connexion reussie
            ip_address: Adresse IP du client
            user_agent: User-Agent du client
        """
        if not self.session_service:
            return

        try:
            self.session_service.record_login_attempt(
                email=email,
                tenant_id=tenant_id,
                success=success,
                ip_address=ip_address or "unknown",
                user_agent=user_agent
            )
        except Exception as e:
            # Logger l'erreur mais ne pas bloquer l'authentification
            logger.warning(f"Error recording login attempt email={mask_email(email)}: {e}")

    def _create_mfa_session_token(
        self,
        user_id: int,
        tenant_id: int
    ) -> str:
        """
        Cree un token de session MFA temporaire.

        Ce token est utilise pour le flow MFA en 2 etapes:
        - Courte duree de vie (5 minutes)
        - Type 'mfa_session' (non utilisable comme access token)
        - Contient user_id et tenant_id pour la verification

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            JWT mfa_session_token
        """
        from jose import jwt
        from app.core.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.MFA_SESSION_TOKEN_EXPIRE_MINUTES)

        payload = {
            "sub": str(user_id),
            "tenant_id": tenant_id,
            "type": "mfa_session",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }

        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def complete_mfa_login(
        self,
        mfa_session_token: str,
        totp_code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expected_tenant_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Complete l'authentification MFA en 2eme etape.

        Processus:
        1. Valider le mfa_session_token
        2. Verifier que le tenant_id correspond (si expected_tenant_id fourni)
        3. Verifier le code TOTP
        4. Generer les tokens finaux (access + refresh)
        5. Creer la session et logger l'audit

        Args:
            mfa_session_token: Token de session MFA
            totp_code: Code TOTP a 6 chiffres
            ip_address: Adresse IP du client
            user_agent: User-Agent du client

        Returns:
            Dict avec access_token, refresh_token ou None si echec
        """
        from app.core.security import TokenExpiredError, InvalidTokenError

        # ----------------------------------------------------------------
        # Etape 1: Valider le mfa_session_token
        # ----------------------------------------------------------------
        try:
            payload = decode_token(mfa_session_token)
        except (TokenExpiredError, InvalidTokenError) as e:
            logger.debug(f"Invalid MFA session token: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error decoding MFA token: {e}")
            return None

        # Verifier que le payload n'est pas None
        if payload is None:
            logger.debug("MFA session token decoded to None")
            return None

        # Verifier le type de token
        if payload.get("type") != "mfa_session":
            logger.debug("Token is not of type mfa_session")
            return None

        # Valider sub de maniere securisee
        sub = payload.get("sub")
        if sub is None:
            logger.debug("MFA Token: sub missing")
            return None

        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            logger.debug("MFA Token: invalid sub")
            return None

        if user_id <= 0:
            logger.debug("MFA Token: invalid user_id")
            return None

        tenant_id = payload.get("tenant_id")

        # Validation tenant_id si expected_tenant_id est fourni (securite cross-tenant)
        if expected_tenant_id is not None and tenant_id != expected_tenant_id:
            logger.warning(
                f"MFA tenant mismatch: token has {tenant_id}, expected {expected_tenant_id}"
            )
            return None

        # ----------------------------------------------------------------
        # Etape 2: Recuperer l'utilisateur
        # ----------------------------------------------------------------
        user = self.user_repository.get_by_id(user_id)
        if user is None or not user.is_active:
            return None

        # ----------------------------------------------------------------
        # Etape 3: Verifier le code TOTP
        # ----------------------------------------------------------------
        if not self.mfa_service:
            logger.error("MFAService non configure pour complete_mfa_login")
            return None

        try:
            totp_valid = self.mfa_service.verify_totp(user_id=user_id, code=totp_code)
        except Exception as e:
            # MFALockoutError ou autre exception - re-raise pour l'endpoint
            # L'endpoint doit gerer MFALockoutError avec HTTP 429
            self._log_audit_event(
                action="mfa_verification_failed",
                user_id=user_id,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={"reason": "lockout_or_error", "error": str(e)}
            )
            raise

        if not totp_valid:
            # Logger l'echec MFA
            self._log_audit_event(
                action="mfa_verification_failed",
                user_id=user_id,
                tenant_id=tenant_id,
                ip_address=ip_address,
                details={"reason": "invalid_totp_code"}
            )
            return None

        # ----------------------------------------------------------------
        # Etape 4: Creation de session (Phase 2) - AVANT tokens pour avoir session_id
        # ----------------------------------------------------------------
        session_id = None
        if self.session_service:
            session = self.session_service.create_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            if session:
                session_id = str(session.id)
                # Mise a jour last_login APRES creation session reussie
                self.user_repository.update_last_login(user.id)
            else:
                logger.warning(
                    f"Session creation failed for user_id={user.id}, "
                    f"tenant_id={user.tenant_id} - MFA login continues without session tracking"
                )
        else:
            # Pas de session_service: MAJ last_login quand meme
            self.user_repository.update_last_login(user.id)

        # ----------------------------------------------------------------
        # Etape 5: Generation des tokens (avec session_id)
        # ----------------------------------------------------------------
        access_token = create_access_token(
            subject=user.id,
            tenant_id=user.tenant_id,
            extra_claims={"email": user.email},
            session_id=session_id
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            tenant_id=user.tenant_id
        )

        # Extraire le JTI du refresh token
        refresh_payload = get_token_payload(refresh_token)
        refresh_jti = refresh_payload.get("jti") if refresh_payload else None
        refresh_exp = None
        if refresh_payload and refresh_payload.get("exp"):
            try:
                refresh_exp = datetime.fromtimestamp(
                    refresh_payload.get("exp"),
                    tz=timezone.utc
                )
            except (TypeError, ValueError, OSError) as e:
                logger.warning(f"Impossible de parser exp du refresh token (MFA): {e}")

        # ----------------------------------------------------------------
        # Etape 6: Stockage du refresh token (Phase 2)
        # ----------------------------------------------------------------
        if self.token_service and refresh_jti and refresh_exp:
            self.token_service.store_refresh_token(
                jti=refresh_jti,
                user_id=user.id,
                tenant_id=user.tenant_id,
                expires_at=refresh_exp,
                session_id=session_id,
                raw_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent
            )

        # ----------------------------------------------------------------
        # Etape 8: Logging audit
        # ----------------------------------------------------------------
        self._log_audit_event(
            action="login_mfa_success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={
                "email": user.email,
                "session_id": session_id,
                "token_jti": refresh_jti
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "session_id": session_id,
        }
