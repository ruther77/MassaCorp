"""
Service MFA pour MassaCorp.

Ce module fournit le service de gestion de l'authentification multi-facteur:
- Generation et verification TOTP (Time-based One-Time Password)
- Setup MFA avec generation de QR code
- Gestion des codes de recuperation
- Activation/desactivation MFA

Le service utilise pyotp pour la generation et verification TOTP.
"""
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import pyotp

from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret, is_encrypted_secret
from app.repositories.mfa import MFASecretRepository, MFARecoveryCodeRepository
from app.services.exceptions import ServiceException


class MFAAlreadyEnabledError(ServiceException):
    """MFA est deja active pour cet utilisateur"""

    def __init__(self, user_id: Optional[int] = None):
        super().__init__(
            message="MFA est deja active pour cet utilisateur",
            code="MFA_ALREADY_ENABLED"
        )
        self.user_id = user_id


class MFANotConfiguredError(ServiceException):
    """MFA n'est pas configure pour cet utilisateur"""

    def __init__(self, user_id: Optional[int] = None):
        super().__init__(
            message="MFA n'est pas configure pour cet utilisateur",
            code="MFA_NOT_CONFIGURED"
        )
        self.user_id = user_id


class InvalidMFACodeError(ServiceException):
    """Code MFA invalide"""

    def __init__(self, message: str = "Code MFA invalide"):
        super().__init__(
            message=message,
            code="INVALID_MFA_CODE"
        )


class MFAService:
    """
    Service pour la gestion de l'authentification multi-facteur.

    Fonctionnalites:
    - Setup MFA avec generation de secret TOTP
    - Verification des codes TOTP
    - Gestion des codes de recuperation
    - Activation/desactivation MFA
    """

    # Configuration par defaut
    DEFAULT_ISSUER = "MassaCorp"
    RECOVERY_CODES_COUNT = 10
    TOTP_WINDOW = 1  # Accepte +/- 1 intervalle (30 sec)

    def __init__(
        self,
        mfa_secret_repository: MFASecretRepository,
        mfa_recovery_code_repository: MFARecoveryCodeRepository,
        issuer: Optional[str] = None
    ):
        """
        Initialise le service MFA.

        Args:
            mfa_secret_repository: Repository pour les secrets MFA
            mfa_recovery_code_repository: Repository pour les codes de recuperation
            issuer: Nom de l'emetteur pour les URI TOTP (defaut: MassaCorp)
        """
        self.mfa_secret_repository = mfa_secret_repository
        self.mfa_recovery_code_repository = mfa_recovery_code_repository
        self.issuer = issuer or self.DEFAULT_ISSUER

    # ========================================================================
    # Generation de secrets et URIs
    # ========================================================================

    def generate_secret(self) -> str:
        """
        Genere un nouveau secret TOTP en base32.

        Returns:
            Secret base32 de 32 caracteres
        """
        return pyotp.random_base32()

    def get_provisioning_uri(
        self,
        secret: str,
        email: str,
        issuer: Optional[str] = None
    ) -> str:
        """
        Genere l'URI de provisionnement pour les apps TOTP.

        Cette URI peut etre encodee dans un QR code pour configuration
        automatique de l'app (Google Authenticator, Authy, etc.)

        Args:
            secret: Secret TOTP en base32
            email: Email de l'utilisateur (identifiant dans l'app)
            issuer: Nom de l'emetteur (defaut: self.issuer)

        Returns:
            URI otpauth:// pour configuration TOTP
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=email,
            issuer_name=issuer or self.issuer
        )

    # ========================================================================
    # Setup MFA
    # ========================================================================

    def setup_mfa(
        self,
        user_id: int,
        tenant_id: int,
        email: str
    ) -> Dict[str, Any]:
        """
        Configure MFA pour un utilisateur.

        Si MFA est deja active, leve une exception.
        Si un secret existe mais n'est pas active, le retourne.
        Sinon, cree un nouveau secret.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant
            email: Email pour l'URI de provisionnement

        Returns:
            Dict avec secret, provisioning_uri, qr_code_base64

        Raises:
            MFAAlreadyEnabledError: Si MFA est deja active
        """
        existing = self.mfa_secret_repository.get_by_user_id(user_id)

        if existing and existing.enabled:
            raise MFAAlreadyEnabledError(user_id=user_id)

        if existing and not existing.enabled:
            # Secret existe mais pas encore active - le dechiffrer et retourner
            stored_secret = existing.secret
            if is_encrypted_secret(stored_secret):
                secret = decrypt_totp_secret(stored_secret)
            else:
                secret = stored_secret
        else:
            # Generer un nouveau secret
            secret = self.generate_secret()
            # Chiffrer avant stockage
            encrypted_secret = encrypt_totp_secret(secret)
            self.mfa_secret_repository.create_or_update(
                user_id=user_id,
                tenant_id=tenant_id,
                secret=encrypted_secret
            )

        provisioning_uri = self.get_provisioning_uri(
            secret=secret,
            email=email
        )

        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code_base64": self._generate_qr_code_base64(provisioning_uri),
        }

    def _generate_qr_code_base64(self, data: str) -> Optional[str]:
        """
        Genere un QR code en base64 pour l'URI donnee.

        Args:
            data: Donnees a encoder dans le QR code

        Returns:
            Image QR code en base64 ou None si qrcode n'est pas installe
        """
        try:
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            return base64.b64encode(buffer.getvalue()).decode()
        except ImportError:
            # qrcode n'est pas installe
            return None

    # ========================================================================
    # Verification TOTP
    # ========================================================================

    def _get_decrypted_secret(self, user_id: int) -> Optional[Tuple[Any, str]]:
        """
        Recupere et dechiffre le secret MFA d'un utilisateur.

        Methode interne partagee par verify_totp() et _verify_totp_for_setup().

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Tuple (mfa_secret, decrypted_secret) ou None si non trouve
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)

        if mfa_secret is None:
            return None

        # Dechiffrer le secret si necessaire
        stored_secret = mfa_secret.secret
        if is_encrypted_secret(stored_secret):
            secret = decrypt_totp_secret(stored_secret)
        else:
            secret = stored_secret

        return (mfa_secret, secret)

    def verify_totp(
        self,
        user_id: int,
        code: str,
        window: Optional[int] = None
    ) -> bool:
        """
        Verifie un code TOTP pour un utilisateur avec protection anti-replay.

        La protection anti-replay empeche la reutilisation d'un code TOTP
        dans la meme fenetre de 30 secondes. Cela protege contre les attaques
        ou un code intercepte serait rejoue.

        Args:
            user_id: ID de l'utilisateur
            code: Code TOTP a 6 chiffres
            window: Fenetre de tolerance (defaut: TOTP_WINDOW)

        Returns:
            True si le code est valide et non-replay, False sinon
        """
        # Utiliser la methode commune pour recuperer le secret
        result = self._get_decrypted_secret(user_id)
        if result is None:
            return False

        mfa_secret, secret = result

        # Verification specifique: MFA doit etre active
        if not mfa_secret.enabled:
            return False

        totp = pyotp.TOTP(secret)

        # Calculer le window actuel pour anti-replay
        current_window = int(datetime.now(timezone.utc).timestamp() // 30)

        # Anti-replay: verifier que ce window n'a pas deja ete utilise
        if mfa_secret.last_totp_window is not None:
            if mfa_secret.last_totp_window >= current_window:
                # Code deja utilise dans cette fenetre - replay attack!
                return False

        # Verifier le code TOTP
        valid = totp.verify(code, valid_window=window or self.TOTP_WINDOW)

        if valid:
            # Mettre a jour le dernier window utilise (anti-replay)
            self.mfa_secret_repository.update_last_totp_window(user_id, current_window)
            self.mfa_secret_repository.update_last_used(user_id)

        return valid

    def _verify_totp_for_setup(
        self,
        user_id: int,
        code: str
    ) -> bool:
        """
        Verifie un code TOTP pendant le setup (avant activation).

        Pas de protection anti-replay ni de verification enabled car
        le MFA n'est pas encore active a ce stade.

        Args:
            user_id: ID de l'utilisateur
            code: Code TOTP a verifier

        Returns:
            True si le code est valide
        """
        # Utiliser la methode commune pour recuperer le secret
        result = self._get_decrypted_secret(user_id)
        if result is None:
            return False

        _, secret = result  # On n'a pas besoin de mfa_secret ici

        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=self.TOTP_WINDOW)

    # ========================================================================
    # Activation/Desactivation MFA
    # ========================================================================

    def enable_mfa(
        self,
        user_id: int,
        code: str
    ) -> Dict[str, Any]:
        """
        Active MFA pour un utilisateur apres verification du code.

        Args:
            user_id: ID de l'utilisateur
            code: Code TOTP pour verification

        Returns:
            Dict avec enabled=True et recovery_codes

        Raises:
            MFANotConfiguredError: Si aucun secret n'existe
            InvalidMFACodeError: Si le code est invalide
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)

        if mfa_secret is None:
            raise MFANotConfiguredError(user_id=user_id)

        # Verifier le code TOTP
        if not self._verify_totp_for_setup(user_id, code):
            raise InvalidMFACodeError("Code TOTP invalide")

        # Activer MFA
        self.mfa_secret_repository.enable_mfa(user_id)

        # Generer les codes de recuperation
        recovery_codes = self._create_recovery_codes(
            user_id=user_id,
            tenant_id=mfa_secret.tenant_id
        )

        return {
            "enabled": True,
            "recovery_codes": recovery_codes,
        }

    def disable_mfa(
        self,
        user_id: int,
        code: str
    ) -> bool:
        """
        Desactive MFA pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            code: Code TOTP ou code de recuperation

        Returns:
            True si desactive avec succes

        Raises:
            MFANotConfiguredError: Si MFA n'est pas active
            InvalidMFACodeError: Si le code est invalide
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)

        if mfa_secret is None or not mfa_secret.enabled:
            raise MFANotConfiguredError(user_id=user_id)

        # Verifier le code TOTP
        if not self.verify_totp(user_id, code):
            raise InvalidMFACodeError("Code TOTP invalide")

        # Desactiver MFA
        self.mfa_secret_repository.disable_mfa(user_id)

        # Supprimer les codes de recuperation
        self.mfa_recovery_code_repository.delete_all_for_user(user_id)

        return True

    # ========================================================================
    # Codes de recuperation
    # ========================================================================

    def generate_recovery_codes(self, count: Optional[int] = None) -> List[str]:
        """
        Genere des codes de recuperation aleatoires.

        Format: XXXX-XXXX (8 caracteres + tiret)

        Args:
            count: Nombre de codes a generer (defaut: RECOVERY_CODES_COUNT)

        Returns:
            Liste des codes en clair
        """
        count = count or self.RECOVERY_CODES_COUNT
        codes = []

        for _ in range(count):
            # Generer 8 caracteres alphanumeriques
            chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Sans I, O, 0, 1
            part1 = "".join(secrets.choice(chars) for _ in range(4))
            part2 = "".join(secrets.choice(chars) for _ in range(4))
            code = f"{part1}-{part2}"
            codes.append(code)

        return codes

    def _hash_recovery_code(self, code: str) -> str:
        """
        Hash un code de recuperation avec bcrypt.

        Utilise bcrypt pour le hachage (lent par design, resistant au brute-force).
        Chaque hash inclut un salt unique genere automatiquement.

        Args:
            code: Code en clair

        Returns:
            Hash bcrypt du code (60 caracteres, commence par $2b$)
        """
        # Normaliser le code (majuscules, sans tirets)
        normalized = code.upper().replace("-", "")
        # Bcrypt avec cost factor 10 (bon compromis securite/performance)
        hashed = bcrypt.hashpw(normalized.encode("utf-8"), bcrypt.gensalt(rounds=10))
        return hashed.decode("utf-8")

    def _verify_code_hash(self, code: str, code_hash: str) -> bool:
        """
        Verifie si un code correspond a un hash bcrypt.

        Utilise bcrypt.checkpw qui est resistant aux timing attacks
        (comparaison en temps constant).

        Args:
            code: Code en clair
            code_hash: Hash bcrypt stocke

        Returns:
            True si le code correspond
        """
        try:
            # Normaliser le code (majuscules, sans tirets)
            normalized = code.upper().replace("-", "")
            # bcrypt.checkpw est constant-time et secure
            return bcrypt.checkpw(normalized.encode("utf-8"), code_hash.encode("utf-8"))
        except (ValueError, TypeError):
            # Hash invalide ou autre erreur
            return False

    def _create_recovery_codes(
        self,
        user_id: int,
        tenant_id: int
    ) -> List[str]:
        """
        Cree et stocke les codes de recuperation.

        Args:
            user_id: ID de l'utilisateur
            tenant_id: ID du tenant

        Returns:
            Liste des codes en clair (a afficher une seule fois)
        """
        # Supprimer les anciens codes
        self.mfa_recovery_code_repository.delete_all_for_user(user_id)

        # Generer de nouveaux codes
        codes = self.generate_recovery_codes()

        # Hasher et stocker
        code_hashes = [self._hash_recovery_code(code) for code in codes]
        self.mfa_recovery_code_repository.create_codes_for_user(
            user_id=user_id,
            tenant_id=tenant_id,
            code_hashes=code_hashes
        )

        return codes

    def verify_recovery_code(
        self,
        user_id: int,
        code: str
    ) -> bool:
        """
        Verifie et consomme un code de recuperation.

        Args:
            user_id: ID de l'utilisateur
            code: Code de recuperation

        Returns:
            True si le code est valide et a ete consomme
        """
        valid_codes = self.mfa_recovery_code_repository.get_valid_codes_for_user(user_id)

        for stored_code in valid_codes:
            if self._verify_code_hash(code, stored_code.code_hash):
                # Marquer comme utilise
                self.mfa_recovery_code_repository.mark_code_as_used(stored_code.id)
                return True

        return False

    def regenerate_recovery_codes(
        self,
        user_id: int,
        totp_code: str
    ) -> List[str]:
        """
        Regenere les codes de recuperation (necessite verification TOTP).

        Args:
            user_id: ID de l'utilisateur
            totp_code: Code TOTP pour verification

        Returns:
            Nouveaux codes de recuperation

        Raises:
            MFANotConfiguredError: Si MFA n'est pas active
            InvalidMFACodeError: Si le code TOTP est invalide
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)

        if mfa_secret is None or not mfa_secret.enabled:
            raise MFANotConfiguredError(user_id=user_id)

        if not self.verify_totp(user_id, totp_code):
            raise InvalidMFACodeError("Code TOTP invalide")

        return self._create_recovery_codes(
            user_id=user_id,
            tenant_id=mfa_secret.tenant_id
        )

    def get_recovery_codes_count(self, user_id: int) -> int:
        """
        Retourne le nombre de codes de recuperation valides.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Nombre de codes non utilises
        """
        return self.mfa_recovery_code_repository.count_valid_codes(user_id)

    # ========================================================================
    # Statut MFA
    # ========================================================================

    def get_mfa_status(self, user_id: int) -> Dict[str, Any]:
        """
        Retourne le statut MFA complet d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Dict avec enabled, configured, recovery_codes_remaining, etc.
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)

        if mfa_secret is None:
            return {
                "enabled": False,
                "configured": False,
                "recovery_codes_remaining": 0,
                "last_used_at": None,
            }

        recovery_count = self.mfa_recovery_code_repository.count_valid_codes(user_id)

        return {
            "enabled": mfa_secret.enabled,
            "configured": True,
            "recovery_codes_remaining": recovery_count,
            "last_used_at": mfa_secret.last_used_at.isoformat() if mfa_secret.last_used_at else None,
            "created_at": mfa_secret.created_at.isoformat() if mfa_secret.created_at else None,
        }

    def is_mfa_required(self, user_id: int) -> bool:
        """
        Verifie si MFA est requis pour un utilisateur.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si MFA est active et doit etre verifie
        """
        mfa_secret = self.mfa_secret_repository.get_by_user_id(user_id)
        return mfa_secret is not None and mfa_secret.enabled

    def is_mfa_enabled(self, user_id: int) -> bool:
        """
        Verifie si MFA est active pour un utilisateur.

        Alias de is_mfa_required() pour coherence avec les tests.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            True si MFA est active
        """
        return self.is_mfa_required(user_id)

    def is_mfa_setup_required(self, user: "User") -> bool:
        """
        Verifie si l'utilisateur doit configurer MFA (force par admin).

        Cette methode est utilisee apres une compromission suspecte
        pour forcer l'utilisateur a activer MFA avant de continuer.

        Args:
            user: Objet User

        Returns:
            True si MFA doit etre configure (mais n'est pas encore active)
        """
        # Si mfa_required est True et MFA n'est pas encore active
        if not hasattr(user, 'mfa_required'):
            return False
        return user.mfa_required and not self.is_mfa_enabled(user.id)
