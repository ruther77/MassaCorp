"""
Tests pour la liaison obligatoire Session <-> RefreshToken.

Ces tests verifient que:
1. Un RefreshToken doit TOUJOURS avoir un session_id
2. Lors du refresh, le nouveau token conserve le session_id
3. Les tokens sans session_id sont rejetes
"""
import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.security import hash_token, hash_password


@pytest.fixture
def tenant(db_session):
    """Cree un tenant de test."""
    from app.models.tenant import Tenant

    tenant = Tenant(
        name="Test Tenant",
        slug=f"test-tenant-{uuid4().hex[:8]}"
    )
    db_session.add(tenant)
    db_session.flush()
    return tenant


@pytest.fixture
def user(db_session, tenant):
    """Cree un utilisateur de test."""
    from app.models.user import User

    user = User(
        email=f"test-{uuid4().hex[:8]}@massacorp.local",
        password_hash=hash_password("SecurePass123!"),
        tenant_id=tenant.id,
        first_name="Test",
        last_name="User",
        is_active=True
    )
    db_session.add(user)
    db_session.flush()
    return user


class TestRefreshTokenSessionLinking:
    """Tests pour la liaison RefreshToken -> Session obligatoire."""

    def test_store_token_requires_session_id(self, db_session, tenant, user):
        """
        RED TEST: store_token() doit exiger un session_id non-null.

        Actuellement session_id est nullable, ce qui permet de creer
        des tokens orphelins sans session associee.
        """
        from app.repositories.refresh_token import RefreshTokenRepository

        repo = RefreshTokenRepository(db_session)

        # Token sans session_id devrait echouer
        with pytest.raises(ValueError, match="session_id"):
            repo.store_token(
                jti=str(uuid4()),
                user_id=user.id,
                tenant_id=tenant.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                session_id=None,  # Pas de session!
                token_hash=hash_token("test_token_123")
            )

    def test_refresh_tokens_preserves_session_id(self, db_session, tenant, user):
        """
        RED TEST: Lors d'un refresh, le nouveau token doit conserver le session_id.

        Actuellement auth.py refresh_tokens() ne passe pas le session_id
        lors du stockage du nouveau token.
        """
        from app.repositories.session import SessionRepository
        from app.repositories.refresh_token import RefreshTokenRepository
        from app.repositories.revoked_token import RevokedTokenRepository
        from app.repositories.user import UserRepository
        from app.services.session import SessionService
        from app.services.token import TokenService
        from app.services.auth import AuthService

        # Setup repositories
        session_repo = SessionRepository(db_session)
        token_repo = RefreshTokenRepository(db_session)
        revoked_token_repo = RevokedTokenRepository(db_session)
        user_repo = UserRepository(db_session)

        # Setup services
        session_service = SessionService(session_repo)
        token_service = TokenService(token_repo, revoked_token_repo)

        auth_service = AuthService(
            user_repository=user_repo,
            session_service=session_service,
            token_service=token_service
        )

        # 1. Login pour obtenir les tokens initiaux
        login_result = auth_service.login(
            email=user.email,
            password="SecurePass123!",
            tenant_id=tenant.id,
            ip_address="10.0.0.1"
        )

        assert login_result is not None, "Login should succeed"
        original_refresh_token = login_result["refresh_token"]
        original_session_id = login_result["session_id"]
        assert original_session_id is not None, "Login should create a session"

        db_session.commit()

        # 2. Refresh les tokens
        refresh_result = auth_service.refresh_tokens(
            refresh_token=original_refresh_token,
            ip_address="10.0.0.1"
        )

        assert refresh_result is not None, "Refresh should succeed"
        new_refresh_token = refresh_result["refresh_token"]

        db_session.commit()

        # 3. Verifier que le nouveau token a le meme session_id
        from app.core.security import get_token_payload
        new_payload = get_token_payload(new_refresh_token)
        new_jti = new_payload.get("jti")

        new_token_record = token_repo.get_by_jti(new_jti)
        assert new_token_record is not None, "New token should be stored"
        assert new_token_record.session_id is not None, \
            "Le nouveau token doit avoir un session_id"
        assert str(new_token_record.session_id) == original_session_id, \
            "Le nouveau token doit conserver le session_id original"


class TestRefreshTokenSessionIdValidation:
    """
    Tests pour la validation de session_id obligatoire.

    Note: La contrainte est validee au niveau repository/service
    plutot que dans le modele SQL pour eviter une migration de DB.
    """

    def test_session_id_validated_at_repository_level(self, db_session, tenant, user):
        """
        La validation de session_id se fait au niveau repository.

        Cette approche est equivalente en securite a une contrainte SQL
        NOT NULL, mais plus flexible pour les migrations.
        """
        from app.repositories.refresh_token import RefreshTokenRepository

        repo = RefreshTokenRepository(db_session)

        # Sans session_id, doit lever ValueError
        with pytest.raises(ValueError, match="session_id"):
            repo.store_token(
                jti="test-jti",
                user_id=user.id,
                tenant_id=tenant.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                session_id=None,
                token_hash=hash_token("test_token")
            )
