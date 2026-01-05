"""
Tests TDD pour la securite MFA.

Ces tests verifient que:
1. Rate limiting sur endpoints MFA (5 tentatives/min max)
2. Bcrypt pour les recovery codes (pas SHA-256)
3. Comparaison en temps constant pour eviter timing attacks
4. Chiffrement AES-256-GCM des secrets TOTP
"""
import pytest
import secrets
import time
from unittest.mock import MagicMock, patch


class TestMFARateLimiting:
    """Tests pour le rate limiting des endpoints MFA"""

    @pytest.mark.unit
    def test_mfa_verify_endpoint_has_rate_limit(self):
        """Les endpoints MFA verify doivent avoir un rate limit strict (5/min)"""
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            default_limit=60,
            login_limit=5
        )

        # Les endpoints MFA doivent etre configures avec limite stricte
        assert "/api/v1/mfa/verify" in middleware.endpoint_limits
        assert middleware.endpoint_limits["/api/v1/mfa/verify"] <= 5

    @pytest.mark.unit
    def test_mfa_recovery_verify_endpoint_has_rate_limit(self):
        """L'endpoint recovery/verify doit avoir un rate limit strict (3/min)"""
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            default_limit=60,
            login_limit=5
        )

        # Recovery codes encore plus strict
        assert "/api/v1/mfa/recovery/verify" in middleware.endpoint_limits
        assert middleware.endpoint_limits["/api/v1/mfa/recovery/verify"] <= 3

    @pytest.mark.unit
    def test_mfa_enable_endpoint_has_rate_limit(self):
        """L'endpoint enable doit avoir un rate limit"""
        from app.middleware.rate_limit import RateLimitMiddleware

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            default_limit=60,
            login_limit=5
        )

        assert "/api/v1/mfa/enable" in middleware.endpoint_limits
        assert middleware.endpoint_limits["/api/v1/mfa/enable"] <= 5


class TestRecoveryCodeBcrypt:
    """Tests pour le hachage bcrypt des recovery codes"""

    @pytest.mark.unit
    def test_hash_recovery_code_uses_bcrypt(self):
        """_hash_recovery_code doit utiliser bcrypt (pas SHA-256)"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        code = "ABCD-EFGH"
        hashed = service._hash_recovery_code(code)

        # Bcrypt hash commence par $2b$ ou $2a$ et fait ~60 chars
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert len(hashed) == 60

    @pytest.mark.unit
    def test_hash_recovery_code_is_slow(self):
        """bcrypt doit etre intentionnellement lent (>10ms)"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        code = "ABCD-EFGH"

        start = time.time()
        service._hash_recovery_code(code)
        elapsed = time.time() - start

        # bcrypt doit prendre au moins 10ms avec cost factor raisonnable
        assert elapsed >= 0.01, f"Hash trop rapide ({elapsed*1000:.2f}ms), SHA-256 suspecte"

    @pytest.mark.unit
    def test_verify_code_hash_with_bcrypt(self):
        """_verify_code_hash doit fonctionner avec bcrypt"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        code = "WXYZ-1234"
        hashed = service._hash_recovery_code(code)

        # Verification positive
        assert service._verify_code_hash(code, hashed) is True

        # Verification negative
        assert service._verify_code_hash("WRONG-CODE", hashed) is False

    @pytest.mark.unit
    def test_hash_recovery_code_different_hashes_same_code(self):
        """Chaque hash bcrypt doit etre different (salt unique)"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        code = "SAME-CODE"
        hash1 = service._hash_recovery_code(code)
        hash2 = service._hash_recovery_code(code)

        # Bcrypt genere un salt different a chaque fois
        assert hash1 != hash2


class TestTimingAttackPrevention:
    """Tests pour la prevention des timing attacks"""

    @pytest.mark.unit
    def test_verify_code_hash_uses_constant_time_comparison(self):
        """_verify_code_hash doit utiliser une comparaison en temps constant"""
        from app.services.mfa import MFAService
        import inspect

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Verifier que le code utilise secrets.compare_digest ou bcrypt.checkpw
        source = inspect.getsource(service._verify_code_hash)

        uses_constant_time = (
            "compare_digest" in source or
            "checkpw" in source or
            "bcrypt" in source
        )
        assert uses_constant_time, (
            "_verify_code_hash n'utilise pas de comparaison en temps constant. "
            "Utilisez secrets.compare_digest() ou bcrypt.checkpw()"
        )

    @pytest.mark.unit
    def test_verify_code_hash_timing_is_constant(self):
        """Le temps de verification ne doit pas dependre du contenu"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        code = "TEST-CODE"
        correct_hash = service._hash_recovery_code(code)

        # Mesurer le temps pour un code correct vs incorrect
        times_correct = []
        times_wrong = []

        for _ in range(10):
            start = time.time()
            service._verify_code_hash(code, correct_hash)
            times_correct.append(time.time() - start)

            start = time.time()
            service._verify_code_hash("XXXX-XXXX", correct_hash)
            times_wrong.append(time.time() - start)

        avg_correct = sum(times_correct) / len(times_correct)
        avg_wrong = sum(times_wrong) / len(times_wrong)

        # La difference ne devrait pas etre significative (< 20%)
        # Avec bcrypt, les deux prennent le meme temps
        ratio = max(avg_correct, avg_wrong) / min(avg_correct, avg_wrong)
        assert ratio < 1.5, f"Timing difference suspecte: ratio={ratio:.2f}"


class TestTOTPSecretEncryption:
    """Tests pour le chiffrement des secrets TOTP"""

    @pytest.mark.unit
    def test_totp_secret_is_encrypted_before_storage(self):
        """Le secret TOTP doit etre chiffre avant stockage"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        # Simuler qu'aucun secret n'existe encore
        mock_secret_repo.get_by_user_id.return_value = None

        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Setup MFA
        service.setup_mfa(user_id=1, tenant_id=1, email="test@test.com")

        # Verifier que create_or_update a ete appele avec un secret chiffre
        call_args = mock_secret_repo.create_or_update.call_args
        stored_secret = call_args.kwargs.get("secret") or call_args[1].get("secret")

        # Le secret stocke ne doit PAS etre en base32 brut
        # Il doit etre chiffre (commence par un prefixe ou est plus long)
        assert stored_secret is not None

        # Un secret base32 brut fait 32 chars
        # Un secret chiffre AES-256-GCM fait plus (IV + ciphertext + tag)
        # Format attendu: base64(IV + ciphertext + tag) ~ 80+ chars
        is_encrypted = (
            len(stored_secret) > 50 or
            stored_secret.startswith("enc:") or
            ":" in stored_secret  # Format avec separateur
        )
        assert is_encrypted, (
            f"Le secret semble etre stocke en clair: {stored_secret[:20]}..."
        )

    @pytest.mark.unit
    def test_totp_secret_can_be_decrypted_for_verification(self):
        """Le secret chiffre doit pouvoir etre dechiffre pour verification"""
        from app.services.mfa import MFAService
        from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret

        original_secret = "JBSWY3DPEHPK3PXP"  # Example base32 secret

        # Chiffrer
        encrypted = encrypt_totp_secret(original_secret)
        assert encrypted != original_secret

        # Dechiffrer
        decrypted = decrypt_totp_secret(encrypted)
        assert decrypted == original_secret

    @pytest.mark.unit
    def test_totp_encryption_uses_aes_256_gcm(self):
        """Le chiffrement doit utiliser AES-256-GCM"""
        from app.core.crypto import encrypt_totp_secret
        import inspect

        source = inspect.getsource(encrypt_totp_secret)

        # Verifier que AES-GCM est utilise
        uses_aes_gcm = (
            "GCM" in source or
            "AESGCM" in source or
            "aes" in source.lower() and "gcm" in source.lower()
        )
        assert uses_aes_gcm, "Le chiffrement doit utiliser AES-256-GCM"

    @pytest.mark.unit
    def test_encrypt_decrypt_roundtrip(self):
        """Test complet encrypt/decrypt"""
        from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret
        import pyotp

        # Generer un vrai secret TOTP
        original_secret = pyotp.random_base32()

        # Chiffrer et dechiffrer
        encrypted = encrypt_totp_secret(original_secret)
        decrypted = decrypt_totp_secret(encrypted)

        # Doit etre identique
        assert decrypted == original_secret

        # Le secret dechiffre doit fonctionner pour TOTP
        totp = pyotp.TOTP(decrypted)
        code = totp.now()
        assert len(code) == 6
        assert code.isdigit()

    @pytest.mark.unit
    def test_encrypted_secret_changes_each_time(self):
        """Chaque chiffrement doit produire un resultat different (IV unique)"""
        from app.core.crypto import encrypt_totp_secret

        secret = "JBSWY3DPEHPK3PXP"

        encrypted1 = encrypt_totp_secret(secret)
        encrypted2 = encrypt_totp_secret(secret)

        # L'IV est different a chaque fois, donc le ciphertext aussi
        assert encrypted1 != encrypted2


class TestMFAServiceIntegrationSecurity:
    """Tests d'integration securite pour MFAService"""

    @pytest.mark.unit
    def test_verify_totp_uses_decrypted_secret(self):
        """verify_totp doit dechiffrer le secret avant verification"""
        from app.services.mfa import MFAService
        from app.core.crypto import encrypt_totp_secret
        import pyotp

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Simuler un secret chiffre en base
        original_secret = pyotp.random_base32()
        encrypted_secret = encrypt_totp_secret(original_secret)

        mock_mfa_secret = MagicMock()
        mock_mfa_secret.secret = encrypted_secret
        mock_mfa_secret.enabled = True
        mock_mfa_secret.last_totp_window = None  # Anti-replay: pas encore utilise
        mock_secret_repo.get_by_user_id.return_value = mock_mfa_secret

        # Generer un code valide avec le secret original
        totp = pyotp.TOTP(original_secret)
        valid_code = totp.now()

        # Le service doit dechiffrer et valider
        result = service.verify_totp(user_id=1, code=valid_code)
        assert result is True

    @pytest.mark.unit
    def test_recovery_codes_stored_with_bcrypt(self):
        """Les recovery codes doivent etre stockes avec bcrypt"""
        from app.services.mfa import MFAService

        mock_secret_repo = MagicMock()
        mock_recovery_repo = MagicMock()
        service = MFAService(mock_secret_repo, mock_recovery_repo)

        # Creer des codes
        codes = service.generate_recovery_codes(count=3)

        # Hasher comme le ferait _create_recovery_codes
        hashes = [service._hash_recovery_code(code) for code in codes]

        for h in hashes:
            # Chaque hash doit etre bcrypt
            assert h.startswith("$2b$") or h.startswith("$2a$")
            assert len(h) == 60
