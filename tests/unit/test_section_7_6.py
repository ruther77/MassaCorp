"""
Tests comportementaux Section 7.6 - Migration Argon2id et HSTS preload

Couverture:
- 7.6.1: Migration bcrypt -> Argon2id (OWASP recommandation)
- 7.6.2: HSTS avec preload (deja couvert section 7.3)

Tests verifient que:
1. hash_password() cree des hashes Argon2id par defaut
2. verify_password() accepte les deux formats (Argon2id et bcrypt)
3. needs_rehash() retourne True pour bcrypt
4. verify_and_rehash() retourne un nouveau hash pour bcrypt
5. Migration progressive fonctionne au login
"""
import pytest
from unittest.mock import MagicMock, patch


# ============================================
# 7.6.1 - Tests Argon2id hashing
# ============================================

class TestArgon2idHashing:
    """Tests pour le hashing Argon2id."""

    def test_hash_password_creates_argon2id_by_default(self):
        """hash_password() doit creer un hash Argon2id par defaut."""
        from app.core.security import hash_password, is_argon2_hash

        password = "TestPassword123!"
        hashed = hash_password(password)

        assert is_argon2_hash(hashed)
        assert hashed.startswith("$argon2id$")

    def test_hash_password_can_create_bcrypt_if_requested(self):
        """hash_password() peut creer bcrypt si explicitement demande."""
        from app.core.security import hash_password, is_bcrypt_hash

        password = "TestPassword123!"
        hashed = hash_password(password, use_argon2=False)

        assert is_bcrypt_hash(hashed)
        assert hashed.startswith("$2")

    def test_argon2id_hash_format_correct(self):
        """Le hash Argon2id doit avoir le format correct avec parametres OWASP."""
        from app.core.security import hash_password

        password = "TestPassword123!"
        hashed = hash_password(password)

        # Format: $argon2id$v=19$m=65536,t=3,p=4$salt$hash
        assert "$argon2id$" in hashed
        assert "v=19" in hashed
        assert "m=65536" in hashed  # 64 MiB memory
        assert "t=3" in hashed      # 3 iterations
        assert "p=4" in hashed      # 4 parallelism

    def test_different_passwords_produce_different_hashes(self):
        """Deux mots de passe differents produisent des hashes differents."""
        from app.core.security import hash_password

        hash1 = hash_password("Password1!")
        hash2 = hash_password("Password2!")

        assert hash1 != hash2

    def test_same_password_produces_different_hashes_due_to_salt(self):
        """Le meme mot de passe produit des hashes differents (salt unique)."""
        from app.core.security import hash_password

        password = "TestPassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts


class TestDualVerification:
    """Tests pour la verification duale Argon2id/bcrypt."""

    def test_verify_password_with_argon2id_hash(self):
        """verify_password() doit accepter les hashes Argon2id."""
        from app.core.security import hash_password, verify_password

        password = "TestPassword123!"
        hashed = hash_password(password)  # Argon2id

        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword!", hashed)

    def test_verify_password_with_bcrypt_hash(self):
        """verify_password() doit accepter les hashes bcrypt (legacy)."""
        from app.core.security import hash_password, verify_password

        password = "TestPassword123!"
        hashed = hash_password(password, use_argon2=False)  # bcrypt

        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword!", hashed)

    def test_verify_password_rejects_invalid_hash_format(self):
        """verify_password() doit rejeter les formats de hash inconnus."""
        from app.core.security import verify_password

        password = "TestPassword123!"
        invalid_hash = "$unknown$format$hash"

        assert not verify_password(password, invalid_hash)

    def test_verify_password_rejects_empty_values(self):
        """verify_password() doit rejeter les valeurs vides."""
        from app.core.security import verify_password, hash_password

        hashed = hash_password("TestPassword123!")

        assert not verify_password("", hashed)
        assert not verify_password(None, hashed)
        assert not verify_password("TestPassword123!", "")
        assert not verify_password("TestPassword123!", None)


class TestNeedsRehash:
    """Tests pour la detection de re-hash necessaire."""

    def test_needs_rehash_true_for_bcrypt(self):
        """needs_rehash() doit retourner True pour les hashes bcrypt."""
        from app.core.security import hash_password, needs_rehash

        bcrypt_hash = hash_password("TestPassword123!", use_argon2=False)

        assert needs_rehash(bcrypt_hash)

    def test_needs_rehash_false_for_current_argon2id(self):
        """needs_rehash() doit retourner False pour Argon2id avec params actuels."""
        from app.core.security import hash_password, needs_rehash

        argon2_hash = hash_password("TestPassword123!")

        assert not needs_rehash(argon2_hash)

    def test_needs_rehash_handles_empty_hash(self):
        """needs_rehash() doit gerer les hashes vides/None."""
        from app.core.security import needs_rehash

        assert not needs_rehash("")
        assert not needs_rehash(None)


class TestVerifyAndRehash:
    """Tests pour la verification avec re-hash automatique."""

    def test_verify_and_rehash_with_bcrypt_returns_new_hash(self):
        """verify_and_rehash() doit retourner un nouveau hash pour bcrypt."""
        from app.core.security import hash_password, verify_and_rehash, is_argon2_hash

        password = "TestPassword123!"
        bcrypt_hash = hash_password(password, use_argon2=False)

        is_valid, new_hash = verify_and_rehash(password, bcrypt_hash)

        assert is_valid
        assert new_hash is not None
        assert is_argon2_hash(new_hash)

    def test_verify_and_rehash_with_argon2id_returns_no_new_hash(self):
        """verify_and_rehash() ne doit pas re-hasher un Argon2id actuel."""
        from app.core.security import hash_password, verify_and_rehash

        password = "TestPassword123!"
        argon2_hash = hash_password(password)

        is_valid, new_hash = verify_and_rehash(password, argon2_hash)

        assert is_valid
        assert new_hash is None

    def test_verify_and_rehash_invalid_password_returns_false(self):
        """verify_and_rehash() doit retourner False pour mot de passe invalide."""
        from app.core.security import hash_password, verify_and_rehash

        password = "TestPassword123!"
        hashed = hash_password(password)

        is_valid, new_hash = verify_and_rehash("WrongPassword!", hashed)

        assert not is_valid
        assert new_hash is None


class TestHashDetection:
    """Tests pour la detection du type de hash."""

    def test_is_argon2_hash_detects_argon2id(self):
        """is_argon2_hash() doit detecter les hashes Argon2id."""
        from app.core.security import is_argon2_hash

        assert is_argon2_hash("$argon2id$v=19$m=65536,t=3,p=4$salt$hash")
        assert is_argon2_hash("$argon2i$v=19$m=65536,t=3,p=4$salt$hash")
        assert is_argon2_hash("$argon2d$v=19$m=65536,t=3,p=4$salt$hash")

    def test_is_argon2_hash_rejects_bcrypt(self):
        """is_argon2_hash() doit rejeter les hashes bcrypt."""
        from app.core.security import is_argon2_hash

        assert not is_argon2_hash("$2b$12$salt.hash")
        assert not is_argon2_hash("$2a$12$salt.hash")
        assert not is_argon2_hash("$2y$12$salt.hash")

    def test_is_bcrypt_hash_detects_bcrypt(self):
        """is_bcrypt_hash() doit detecter les hashes bcrypt."""
        from app.core.security import is_bcrypt_hash

        assert is_bcrypt_hash("$2b$12$salt.hash")
        assert is_bcrypt_hash("$2a$12$salt.hash")
        assert is_bcrypt_hash("$2y$12$salt.hash")

    def test_is_bcrypt_hash_rejects_argon2(self):
        """is_bcrypt_hash() doit rejeter les hashes Argon2."""
        from app.core.security import is_bcrypt_hash

        assert not is_bcrypt_hash("$argon2id$v=19$m=65536,t=3,p=4$salt$hash")


# ============================================
# 7.6.2 - Tests HSTS preload (verification)
# ============================================

class TestHSTSPreload:
    """Tests pour HSTS avec preload."""

    def test_hsts_header_includes_preload(self):
        """Le header HSTS doit inclure la directive preload."""
        from app.middleware.security_headers import SecurityHeadersMiddleware

        hsts_header = SecurityHeadersMiddleware.security_headers.get(
            "Strict-Transport-Security", ""
        )

        assert "preload" in hsts_header
        assert "includeSubDomains" in hsts_header
        assert "max-age=31536000" in hsts_header


# ============================================
# 7.6.3 - Tests integration AuthService
# ============================================

class TestAuthServiceRehash:
    """Tests pour la migration au login via AuthService."""

    def test_authenticate_rehashes_bcrypt_password(self):
        """authenticate() doit re-hasher les mots de passe bcrypt vers Argon2id."""
        from app.core.security import hash_password, is_argon2_hash
        from app.services.auth import AuthService

        # Mock user avec password bcrypt
        password = "TestPassword123!"
        bcrypt_hash = hash_password(password, use_argon2=False)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = bcrypt_hash
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.tenant_id = 1

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.get_by_email_and_tenant.return_value = mock_user

        # Creer AuthService
        auth_service = AuthService(user_repository=mock_repo)

        # Authentifier
        result = auth_service.authenticate(
            email="test@example.com",
            password=password,
            tenant_id=1
        )

        # Verifier que l'utilisateur est retourne
        assert result is not None
        assert result == mock_user

        # Verifier que update_password a ete appele avec un hash Argon2id
        mock_repo.update_password.assert_called_once()
        call_args = mock_repo.update_password.call_args
        new_hash = call_args[0][1]  # Deuxieme argument positionnel
        assert is_argon2_hash(new_hash)

    def test_authenticate_does_not_rehash_argon2id(self):
        """authenticate() ne doit pas re-hasher les mots de passe Argon2id."""
        from app.core.security import hash_password
        from app.services.auth import AuthService

        # Mock user avec password Argon2id
        password = "TestPassword123!"
        argon2_hash = hash_password(password)  # Argon2id

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = argon2_hash
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.tenant_id = 1

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.get_by_email_and_tenant.return_value = mock_user

        # Creer AuthService
        auth_service = AuthService(user_repository=mock_repo)

        # Authentifier
        result = auth_service.authenticate(
            email="test@example.com",
            password=password,
            tenant_id=1
        )

        # Verifier que l'utilisateur est retourne
        assert result is not None

        # Verifier que update_password n'a PAS ete appele
        mock_repo.update_password.assert_not_called()

    def test_authenticate_wrong_password_no_rehash(self):
        """authenticate() ne doit pas re-hasher si mot de passe incorrect."""
        from app.core.security import hash_password
        from app.services.auth import AuthService

        # Mock user avec password bcrypt
        bcrypt_hash = hash_password("CorrectPassword123!", use_argon2=False)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.password_hash = bcrypt_hash
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.tenant_id = 1

        # Mock repository
        mock_repo = MagicMock()
        mock_repo.get_by_email_and_tenant.return_value = mock_user

        # Creer AuthService
        auth_service = AuthService(user_repository=mock_repo)

        # Authentifier avec mauvais mot de passe
        result = auth_service.authenticate(
            email="test@example.com",
            password="WrongPassword123!",
            tenant_id=1
        )

        # Verifier que None est retourne
        assert result is None

        # Verifier que update_password n'a PAS ete appele
        mock_repo.update_password.assert_not_called()


# ============================================
# 7.6.4 - Tests DUMMY_HASH
# ============================================

class TestDummyHash:
    """Tests pour DUMMY_HASH (timing-safe login)."""

    def test_dummy_hash_argon2_exists(self):
        """DUMMY_HASH_ARGON2 doit exister et etre valide."""
        from app.core.security import DUMMY_HASH_ARGON2, is_argon2_hash

        assert DUMMY_HASH_ARGON2
        assert is_argon2_hash(DUMMY_HASH_ARGON2)

    def test_dummy_hash_bcrypt_exists(self):
        """DUMMY_HASH_BCRYPT doit exister et etre valide."""
        from app.core.security import DUMMY_HASH_BCRYPT, is_bcrypt_hash

        assert DUMMY_HASH_BCRYPT
        assert is_bcrypt_hash(DUMMY_HASH_BCRYPT)

    def test_dummy_hash_is_argon2(self):
        """DUMMY_HASH par defaut doit etre Argon2id."""
        from app.core.security import DUMMY_HASH, DUMMY_HASH_ARGON2

        assert DUMMY_HASH == DUMMY_HASH_ARGON2


# ============================================
# 7.6.5 - Tests de securite
# ============================================

class TestArgon2SecurityParameters:
    """Tests pour les parametres de securite Argon2id."""

    def test_argon2_hasher_uses_correct_type(self):
        """Le hasher doit utiliser Argon2id (pas argon2i ou argon2d)."""
        from app.core.security import ARGON2_HASHER
        from argon2 import Type

        assert ARGON2_HASHER.type == Type.ID

    def test_argon2_hasher_memory_cost(self):
        """Le memory_cost doit etre 64 MiB (OWASP)."""
        from app.core.security import ARGON2_HASHER

        assert ARGON2_HASHER.memory_cost == 65536  # 64 MiB

    def test_argon2_hasher_time_cost(self):
        """Le time_cost doit etre >= 3 (OWASP)."""
        from app.core.security import ARGON2_HASHER

        assert ARGON2_HASHER.time_cost >= 3

    def test_argon2_hasher_parallelism(self):
        """Le parallelism doit etre >= 1."""
        from app.core.security import ARGON2_HASHER

        assert ARGON2_HASHER.parallelism >= 1

    def test_argon2_hasher_hash_length(self):
        """Le hash_len doit etre >= 32 bytes."""
        from app.core.security import ARGON2_HASHER

        assert ARGON2_HASHER.hash_len >= 32


class TestPasswordValidationErrors:
    """Tests pour les erreurs de validation de mot de passe."""

    def test_hash_password_rejects_none(self):
        """hash_password() doit rejeter None."""
        from app.core.security import hash_password, PasswordValidationError

        with pytest.raises(PasswordValidationError):
            hash_password(None)

    def test_hash_password_rejects_empty_string(self):
        """hash_password() doit rejeter les chaines vides."""
        from app.core.security import hash_password, PasswordValidationError

        with pytest.raises(PasswordValidationError):
            hash_password("")
