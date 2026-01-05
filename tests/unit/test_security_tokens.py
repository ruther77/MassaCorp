"""
Tests TDD pour le hachage sécurisé des tokens.

Ces tests vérifient que:
1. Les refresh tokens sont hashés avant stockage
2. Le hash est irréversible (SHA256)
3. La vérification de token fonctionne
4. Aucun "placeholder_hash" n'est accepté
"""
import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone, timedelta


class TestTokenHashing:
    """Tests pour le hachage des tokens"""

    @pytest.mark.unit
    def test_hash_token_returns_sha256_hex(self):
        """hash_token retourne un hash SHA256 en hexadécimal (64 chars)"""
        from app.core.security import hash_token

        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"
        result = hash_token(token)

        assert result is not None
        assert len(result) == 64  # SHA256 = 32 bytes = 64 hex chars
        assert result != token  # Hash != original

    @pytest.mark.unit
    def test_hash_token_is_deterministic(self):
        """Le même token produit toujours le même hash"""
        from app.core.security import hash_token

        token = "same_token_value"
        hash1 = hash_token(token)
        hash2 = hash_token(token)

        assert hash1 == hash2

    @pytest.mark.unit
    def test_hash_token_different_tokens_different_hashes(self):
        """Deux tokens différents produisent des hashes différents"""
        from app.core.security import hash_token

        token1 = "token_one"
        token2 = "token_two"

        hash1 = hash_token(token1)
        hash2 = hash_token(token2)

        assert hash1 != hash2

    @pytest.mark.unit
    def test_verify_token_hash_valid(self):
        """verify_token_hash retourne True pour un token valide"""
        from app.core.security import hash_token, verify_token_hash

        token = "my_refresh_token"
        token_hash = hash_token(token)

        assert verify_token_hash(token, token_hash) is True

    @pytest.mark.unit
    def test_verify_token_hash_invalid(self):
        """verify_token_hash retourne False pour un mauvais token"""
        from app.core.security import hash_token, verify_token_hash

        token = "my_refresh_token"
        token_hash = hash_token(token)

        assert verify_token_hash("wrong_token", token_hash) is False

    @pytest.mark.unit
    def test_verify_token_hash_rejects_placeholder(self):
        """verify_token_hash rejette 'placeholder_hash'"""
        from app.core.security import verify_token_hash

        # Peu importe le token, placeholder_hash doit être rejeté
        assert verify_token_hash("any_token", "placeholder_hash") is False

    @pytest.mark.unit
    def test_hash_token_empty_string_raises(self):
        """hash_token lève une exception pour une chaîne vide"""
        from app.core.security import hash_token

        with pytest.raises(ValueError):
            hash_token("")

    @pytest.mark.unit
    def test_hash_token_none_raises(self):
        """hash_token lève une exception pour None"""
        from app.core.security import hash_token

        with pytest.raises((ValueError, TypeError)):
            hash_token(None)


class TestRefreshTokenRepositoryHashing:
    """Tests pour le repository avec hachage obligatoire"""

    @pytest.mark.unit
    def test_store_token_requires_hash(self):
        """store_token exige un token_hash valide"""
        from app.repositories.refresh_token import RefreshTokenRepository
        from uuid import uuid4

        mock_session = MagicMock()
        repo = RefreshTokenRepository(mock_session)

        # Sans token_hash, doit lever une erreur
        with pytest.raises(ValueError, match="token_hash"):
            repo.store_token(
                jti="test-jti-123",
                user_id=1,
                tenant_id=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                session_id=str(uuid4()),  # Session obligatoire
                token_hash=None  # Manquant!
            )

    @pytest.mark.unit
    def test_store_token_rejects_placeholder_hash(self):
        """store_token refuse 'placeholder_hash'"""
        from app.repositories.refresh_token import RefreshTokenRepository
        from uuid import uuid4

        mock_session = MagicMock()
        repo = RefreshTokenRepository(mock_session)

        with pytest.raises(ValueError, match="placeholder"):
            repo.store_token(
                jti="test-jti-123",
                user_id=1,
                tenant_id=1,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                session_id=str(uuid4()),  # Session obligatoire
                token_hash="placeholder_hash"  # Interdit!
            )

    @pytest.mark.unit
    def test_store_token_accepts_valid_sha256_hash(self):
        """store_token accepte un hash SHA256 valide"""
        from app.repositories.refresh_token import RefreshTokenRepository
        from app.core.security import hash_token
        from uuid import uuid4

        mock_session = MagicMock()
        repo = RefreshTokenRepository(mock_session)

        valid_hash = hash_token("my_refresh_token")

        # Ne doit pas lever d'exception
        token = repo.store_token(
            jti="test-jti-123",
            user_id=1,
            tenant_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            session_id=str(uuid4()),  # Session obligatoire
            token_hash=valid_hash
        )

        assert token is not None


class TestTokenServiceHashing:
    """Tests pour le service Token avec hachage"""

    @pytest.mark.unit
    def test_store_refresh_token_hashes_before_storage(self):
        """TokenService hash le token avant de le stocker"""
        from app.services.token import TokenService
        from app.core.security import hash_token
        from uuid import uuid4

        mock_refresh_repo = MagicMock()
        mock_revoked_repo = MagicMock()

        service = TokenService(
            refresh_token_repository=mock_refresh_repo,
            revoked_token_repository=mock_revoked_repo
        )

        raw_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.raw_token"
        expected_hash = hash_token(raw_token)
        session_id = str(uuid4())

        service.store_refresh_token(
            jti="jti-123",
            user_id=1,
            tenant_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            session_id=session_id,  # Session obligatoire
            raw_token=raw_token  # Le token brut
        )

        # Vérifier que le repo a reçu le HASH, pas le token brut
        mock_refresh_repo.store_token.assert_called_once()
        call_kwargs = mock_refresh_repo.store_token.call_args.kwargs
        assert call_kwargs["token_hash"] == expected_hash
        assert "raw_token" not in str(call_kwargs)  # Le token brut ne doit pas être passé

    @pytest.mark.unit
    def test_verify_refresh_token_uses_hash_comparison(self):
        """TokenService vérifie le token via hash, pas en clair"""
        from app.services.token import TokenService
        from app.core.security import hash_token

        mock_refresh_repo = MagicMock()
        mock_revoked_repo = MagicMock()

        service = TokenService(
            refresh_token_repository=mock_refresh_repo,
            revoked_token_repository=mock_revoked_repo
        )

        raw_token = "my_refresh_token"
        stored_hash = hash_token(raw_token)

        # Simuler un token stocké
        mock_token = MagicMock()
        mock_token.token_hash = stored_hash
        mock_token.used_at = None
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        mock_refresh_repo.get_by_jti.return_value = mock_token

        # Vérification avec le bon token
        is_valid = service.verify_refresh_token("jti-123", raw_token)
        assert is_valid is True

        # Vérification avec un mauvais token
        is_valid = service.verify_refresh_token("jti-123", "wrong_token")
        assert is_valid is False
