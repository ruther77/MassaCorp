"""
Tests unitaires pour app/core/security.py
TDD: Ces tests sont ecrits AVANT l'implementation

Couvre:
- Hashing de mots de passe (bcrypt)
- Verification de mots de passe
- Creation de tokens JWT (access + refresh)
- Verification de tokens JWT
- Validation de mots de passe (force)
- Gestion des erreurs et cas limites
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import time


# ============================================
# Tests Password Hashing
# ============================================

class TestPasswordHashing:
    """Tests pour les fonctions de hashing de mot de passe"""

    @pytest.mark.unit
    def test_hash_password_returns_string(self, sample_password: str):
        """hash_password doit retourner une chaine de caracteres"""
        from app.core.security import hash_password

        result = hash_password(sample_password)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.unit
    def test_hash_password_different_from_plain(self, sample_password: str):
        """Le hash doit etre different du mot de passe en clair"""
        from app.core.security import hash_password

        result = hash_password(sample_password)

        assert result != sample_password

    @pytest.mark.unit
    def test_hash_password_uses_bcrypt_format(self, sample_password: str):
        """Le hash doit etre au format bcrypt ($2b$...)"""
        from app.core.security import hash_password

        result = hash_password(sample_password)

        assert result.startswith("$2b$") or result.startswith("$2a$")

    @pytest.mark.unit
    def test_hash_password_different_each_time(self, sample_password: str):
        """Deux appels avec le meme password doivent donner des hashs differents (salt)"""
        from app.core.security import hash_password

        hash1 = hash_password(sample_password)
        hash2 = hash_password(sample_password)

        assert hash1 != hash2

    @pytest.mark.unit
    def test_hash_password_empty_raises_error(self):
        """Un mot de passe vide doit lever une erreur"""
        from app.core.security import hash_password, PasswordValidationError

        with pytest.raises(PasswordValidationError):
            hash_password("")

    @pytest.mark.unit
    def test_hash_password_none_raises_error(self):
        """Un mot de passe None doit lever une erreur"""
        from app.core.security import hash_password, PasswordValidationError

        with pytest.raises((PasswordValidationError, TypeError)):
            hash_password(None)

    @pytest.mark.unit
    @pytest.mark.slow
    def test_hash_password_cost_factor_adequate(self, sample_password: str):
        """Le cost factor bcrypt doit etre >= 12 (securite production)"""
        from app.core.security import hash_password

        result = hash_password(sample_password)

        # Format bcrypt: $2b$[cost]$[salt+hash]
        cost = int(result.split("$")[2])
        assert cost >= 12, f"Cost factor {cost} < 12 - pas assez securise"


class TestPasswordVerification:
    """Tests pour la verification de mot de passe"""

    @pytest.mark.unit
    def test_verify_password_correct(self, sample_password: str):
        """Verification doit reussir avec le bon mot de passe"""
        from app.core.security import hash_password, verify_password

        hashed = hash_password(sample_password)
        result = verify_password(sample_password, hashed)

        assert result is True

    @pytest.mark.unit
    def test_verify_password_incorrect(self, sample_password: str):
        """Verification doit echouer avec un mauvais mot de passe"""
        from app.core.security import hash_password, verify_password

        hashed = hash_password(sample_password)
        result = verify_password("WrongPassword123!", hashed)

        assert result is False

    @pytest.mark.unit
    def test_verify_password_empty_plain(self, sample_password: str):
        """Verification avec mot de passe vide doit echouer"""
        from app.core.security import hash_password, verify_password

        hashed = hash_password(sample_password)
        result = verify_password("", hashed)

        assert result is False

    @pytest.mark.unit
    def test_verify_password_invalid_hash(self, sample_password: str):
        """Verification avec hash invalide doit echouer proprement"""
        from app.core.security import verify_password

        result = verify_password(sample_password, "invalid_hash")

        assert result is False

    @pytest.mark.unit
    def test_verify_password_case_sensitive(self, sample_password: str):
        """La verification doit etre sensible a la casse"""
        from app.core.security import hash_password, verify_password

        hashed = hash_password(sample_password)
        result = verify_password(sample_password.upper(), hashed)

        assert result is False


# ============================================
# Tests JWT Token Creation
# ============================================

class TestJWTCreation:
    """Tests pour la creation de tokens JWT"""

    @pytest.mark.unit
    def test_create_access_token_returns_string(self):
        """create_access_token doit retourner une chaine"""
        from app.core.security import create_access_token

        token = create_access_token(
            subject=1,
            tenant_id=1,
            email="test@test.com"
        )

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.unit
    def test_create_access_token_jwt_format(self):
        """Le token doit etre au format JWT (3 parties separees par .)"""
        from app.core.security import create_access_token

        token = create_access_token(
            subject=1,
            tenant_id=1,
            email="test@test.com"
        )

        parts = token.split(".")
        assert len(parts) == 3, "JWT doit avoir 3 parties: header.payload.signature"

    @pytest.mark.unit
    def test_create_access_token_contains_required_claims(self):
        """Le token doit contenir les claims requis"""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            subject=42,
            tenant_id=7,
            email="user@massacorp.local"
        )

        payload = decode_token(token)

        assert payload["sub"] == "42"  # JWT stocke sub comme string
        assert payload["tenant_id"] == 7
        assert payload["email"] == "user@massacorp.local"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    @pytest.mark.unit
    def test_create_access_token_default_expiration(self):
        """Le token access doit expirer dans ~15 minutes par defaut"""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(subject=1, tenant_id=1)
        payload = decode_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Tolerance de 1 minute
        delta = exp - now
        assert 14 * 60 <= delta.total_seconds() <= 16 * 60

    @pytest.mark.unit
    def test_create_access_token_custom_expiration(self):
        """On peut specifier une duree d'expiration personnalisee"""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            subject=1,
            tenant_id=1,
            expires_delta=timedelta(hours=1)
        )

        payload = decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        delta = exp - now
        assert 59 * 60 <= delta.total_seconds() <= 61 * 60

    @pytest.mark.unit
    def test_create_refresh_token_returns_string(self):
        """create_refresh_token doit retourner une chaine"""
        from app.core.security import create_refresh_token

        token = create_refresh_token(subject=1, tenant_id=1)

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.unit
    def test_create_refresh_token_longer_expiration(self):
        """Le refresh token doit avoir une expiration plus longue (7 jours)"""
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(subject=1, tenant_id=1)
        payload = decode_token(token)

        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        delta = exp - now
        # 7 jours = 604800 secondes (tolerance 1 heure)
        assert 6 * 24 * 3600 <= delta.total_seconds() <= 8 * 24 * 3600

    @pytest.mark.unit
    def test_create_refresh_token_has_jti(self):
        """Le refresh token doit avoir un JTI unique"""
        from app.core.security import create_refresh_token, decode_token

        token = create_refresh_token(subject=1, tenant_id=1)
        payload = decode_token(token)

        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0

    @pytest.mark.unit
    def test_create_refresh_token_unique_jti(self):
        """Chaque refresh token doit avoir un JTI different"""
        from app.core.security import create_refresh_token, decode_token

        token1 = create_refresh_token(subject=1, tenant_id=1)
        token2 = create_refresh_token(subject=1, tenant_id=1)

        payload1 = decode_token(token1)
        payload2 = decode_token(token2)

        assert payload1["jti"] != payload2["jti"]


# ============================================
# Tests JWT Token Verification
# ============================================

class TestJWTVerification:
    """Tests pour la verification de tokens JWT"""

    @pytest.mark.unit
    def test_decode_token_valid(self):
        """decode_token doit decoder un token valide"""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(subject=1, tenant_id=1)
        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "1"  # JWT stocke sub comme string

    @pytest.mark.unit
    def test_decode_token_expired_raises_error(self):
        """decode_token doit lever une erreur pour un token expire"""
        from app.core.security import create_access_token, decode_token, TokenExpiredError

        token = create_access_token(
            subject=1,
            tenant_id=1,
            expires_delta=timedelta(seconds=-1)  # Deja expire
        )

        with pytest.raises(TokenExpiredError):
            decode_token(token)

    @pytest.mark.unit
    def test_decode_token_invalid_signature(self):
        """decode_token doit lever une erreur pour une signature invalide"""
        from app.core.security import create_access_token, decode_token, InvalidTokenError

        token = create_access_token(subject=1, tenant_id=1)
        # Modifier la signature
        tampered_token = token[:-5] + "XXXXX"

        with pytest.raises(InvalidTokenError):
            decode_token(tampered_token)

    @pytest.mark.unit
    def test_decode_token_malformed(self):
        """decode_token doit lever une erreur pour un token malformed"""
        from app.core.security import decode_token, InvalidTokenError

        with pytest.raises(InvalidTokenError):
            decode_token("not.a.valid.jwt")

    @pytest.mark.unit
    def test_decode_token_empty(self):
        """decode_token doit lever une erreur pour un token vide"""
        from app.core.security import decode_token, InvalidTokenError

        with pytest.raises(InvalidTokenError):
            decode_token("")

    @pytest.mark.unit
    def test_decode_token_none(self):
        """decode_token doit lever une erreur pour None"""
        from app.core.security import decode_token, InvalidTokenError

        with pytest.raises((InvalidTokenError, TypeError)):
            decode_token(None)

    @pytest.mark.unit
    def test_verify_token_type_access(self):
        """verify_token doit valider le type access"""
        from app.core.security import (
            create_access_token,
            verify_token_type,
            InvalidTokenError
        )

        token = create_access_token(subject=1, tenant_id=1)

        # Doit reussir pour type access
        assert verify_token_type(token, "access") is True

        # Doit echouer pour type refresh
        with pytest.raises(InvalidTokenError):
            verify_token_type(token, "refresh")

    @pytest.mark.unit
    def test_verify_token_type_refresh(self):
        """verify_token doit valider le type refresh"""
        from app.core.security import (
            create_refresh_token,
            verify_token_type,
            InvalidTokenError
        )

        token = create_refresh_token(subject=1, tenant_id=1)

        # Doit reussir pour type refresh
        assert verify_token_type(token, "refresh") is True

        # Doit echouer pour type access
        with pytest.raises(InvalidTokenError):
            verify_token_type(token, "access")


# ============================================
# Tests Password Validation (Force)
# ============================================

class TestPasswordValidation:
    """Tests pour la validation de la force des mots de passe"""

    @pytest.mark.unit
    def test_validate_password_strong(self, sample_password: str):
        """Un mot de passe fort doit passer la validation"""
        from app.core.security import validate_password_strength

        result = validate_password_strength(sample_password)

        assert result is True

    @pytest.mark.unit
    def test_validate_password_min_length(self):
        """Le mot de passe doit avoir au moins 8 caracteres"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("Sh0rt!")

        assert "8" in str(exc_info.value) or "length" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_validate_password_requires_uppercase(self):
        """Le mot de passe doit contenir au moins une majuscule"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("nouppercase123!")

        assert "upper" in str(exc_info.value).lower() or "majuscule" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_validate_password_requires_lowercase(self):
        """Le mot de passe doit contenir au moins une minuscule"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("NOLOWERCASE123!")

        assert "lower" in str(exc_info.value).lower() or "minuscule" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_validate_password_requires_digit(self):
        """Le mot de passe doit contenir au moins un chiffre"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("NoDigitsHere!")

        assert "digit" in str(exc_info.value).lower() or "chiffre" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_validate_password_requires_special(self):
        """Le mot de passe doit contenir au moins un caractere special"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("NoSpecialChar123")

        assert "special" in str(exc_info.value).lower() or "caractere" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_validate_password_max_length(self):
        """Le mot de passe ne doit pas depasser 128 caracteres"""
        from app.core.security import validate_password_strength, PasswordValidationError

        long_password = "A" * 129 + "a1!"

        with pytest.raises(PasswordValidationError):
            validate_password_strength(long_password)

    @pytest.mark.unit
    @pytest.mark.parametrize("weak_password", [
        "password",
        "12345678",
        "qwerty123",
        "Password1",  # Pas de caractere special
    ])
    def test_validate_password_common_weak(self, weak_password: str):
        """Les mots de passe faibles courants doivent etre rejetes"""
        from app.core.security import validate_password_strength, PasswordValidationError

        with pytest.raises(PasswordValidationError):
            validate_password_strength(weak_password)


# ============================================
# Tests Security Edge Cases
# ============================================

class TestSecurityEdgeCases:
    """Tests pour les cas limites et la securite"""

    @pytest.mark.unit
    @pytest.mark.security
    def test_timing_attack_resistance(self, sample_password: str):
        """La verification doit etre resistante aux timing attacks"""
        from app.core.security import hash_password, verify_password

        hashed = hash_password(sample_password)

        # Mesurer le temps pour un bon et un mauvais mot de passe
        times_correct = []
        times_wrong = []

        for _ in range(10):
            start = time.perf_counter()
            verify_password(sample_password, hashed)
            times_correct.append(time.perf_counter() - start)

            start = time.perf_counter()
            verify_password("WrongPassword123!", hashed)
            times_wrong.append(time.perf_counter() - start)

        avg_correct = sum(times_correct) / len(times_correct)
        avg_wrong = sum(times_wrong) / len(times_wrong)

        # La difference ne doit pas etre significative (< 20%)
        diff_ratio = abs(avg_correct - avg_wrong) / max(avg_correct, avg_wrong)
        assert diff_ratio < 0.2, f"Timing difference trop importante: {diff_ratio:.2%}"

    @pytest.mark.unit
    @pytest.mark.security
    def test_jwt_algorithm_is_secure(self):
        """L'algorithme JWT doit etre HS256 ou mieux"""
        from app.core.security import JWT_ALGORITHM

        secure_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        assert JWT_ALGORITHM in secure_algorithms

    @pytest.mark.unit
    @pytest.mark.security
    def test_jwt_secret_not_default(self):
        """Le secret JWT ne doit pas etre la valeur par defaut en production"""
        from app.core.config import get_settings

        settings = get_settings()

        if settings.ENV == "production":
            default_secrets = [
                "CHANGER_EN_PRODUCTION_MIN_32_CARACTERES",
                "secret",
                "changeme",
            ]
            assert settings.JWT_SECRET not in default_secrets

    @pytest.mark.unit
    @pytest.mark.security
    def test_password_hash_not_reversible(self, sample_password: str):
        """Le hash ne doit pas permettre de retrouver le mot de passe"""
        from app.core.security import hash_password

        hashed = hash_password(sample_password)

        # Le password ne doit pas apparaitre dans le hash
        assert sample_password not in hashed
        assert sample_password.encode() not in hashed.encode()

    @pytest.mark.unit
    def test_unicode_password_support(self):
        """Les mots de passe Unicode doivent etre supportes"""
        from app.core.security import hash_password, verify_password

        unicode_password = "Sécurisé123!日本語"

        hashed = hash_password(unicode_password)
        assert verify_password(unicode_password, hashed) is True
        assert verify_password("Securise123!", hashed) is False
