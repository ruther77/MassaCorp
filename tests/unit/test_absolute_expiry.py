"""
Tests pour l'expiration absolue des sessions (30 jours max).

Ces tests verifient que:
- Les sessions ont une expiration absolue definie a la creation
- Les tokens ne peuvent pas depasser l'expiration absolue de la session
- La rotation de tokens respecte l'expiration absolue
- Les sessions expirees absolument sont correctement detectees
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestSessionAbsoluteExpiry:
    """Tests pour l'expiration absolue au niveau du modele Session."""

    @pytest.mark.unit
    def test_session_has_absolute_expiry_attribute(self):
        """Session doit avoir un attribut absolute_expiry."""
        from app.models.session import Session

        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1
        )

        assert hasattr(session, 'absolute_expiry')

    @pytest.mark.unit
    def test_session_is_active_checks_absolute_expiry(self):
        """is_active doit retourner False si absolute_expiry est depasse."""
        from app.models.session import Session

        now = datetime.now(timezone.utc)

        # Session avec expiration absolue dans le futur
        active_session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now + timedelta(days=1)
        )
        assert active_session.is_active is True

        # Session avec expiration absolue dans le passe
        expired_session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now - timedelta(hours=1)
        )
        assert expired_session.is_active is False

    @pytest.mark.unit
    def test_session_is_absolute_expired_property(self):
        """is_absolute_expired doit detecter les sessions expirees."""
        from app.models.session import Session

        now = datetime.now(timezone.utc)

        # Session non expiree
        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now + timedelta(days=10)
        )
        assert session.is_absolute_expired is False

        # Session expiree
        expired = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now - timedelta(seconds=1)
        )
        assert expired.is_absolute_expired is True

    @pytest.mark.unit
    def test_session_without_absolute_expiry_is_active(self):
        """Session sans absolute_expiry (legacy) est toujours active."""
        from app.models.session import Session

        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=None
        )

        assert session.is_active is True
        assert session.is_absolute_expired is False

    @pytest.mark.unit
    def test_session_to_dict_includes_absolute_expiry(self):
        """to_dict doit inclure absolute_expiry."""
        from app.models.session import Session

        now = datetime.now(timezone.utc)
        expiry = now + timedelta(days=30)

        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=expiry
        )
        # Simuler created_at et last_seen_at
        session.created_at = now
        session.last_seen_at = now

        data = session.to_dict()

        assert 'absolute_expiry' in data
        assert data['absolute_expiry'] == expiry.isoformat()


class TestSessionRepositoryAbsoluteExpiry:
    """Tests pour la creation de session avec absolute_expiry."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock SQLAlchemy session."""
        return MagicMock()

    @pytest.fixture
    def session_repository(self, mock_db_session):
        """SessionRepository avec mock."""
        from app.repositories.session import SessionRepository
        return SessionRepository(mock_db_session)

    @pytest.mark.unit
    def test_create_session_sets_absolute_expiry(self, session_repository):
        """create_session doit definir absolute_expiry a 30 jours."""
        now = datetime.now(timezone.utc)

        session = session_repository.create_session(
            user_id=1,
            tenant_id=1,
            token_jti="test-jti",
            ip_address="127.0.0.1"
        )

        assert session.absolute_expiry is not None
        # Verifier que c'est environ 30 jours dans le futur
        expected = now + timedelta(days=30)
        delta = abs((session.absolute_expiry - expected).total_seconds())
        assert delta < 5  # Tolerance de 5 secondes

    @pytest.mark.unit
    def test_create_session_custom_expiry_days(self, session_repository):
        """create_session doit accepter une duree personnalisee."""
        now = datetime.now(timezone.utc)

        session = session_repository.create_session(
            user_id=1,
            tenant_id=1,
            token_jti="test-jti",
            absolute_expiry_days=7  # 7 jours au lieu de 30
        )

        expected = now + timedelta(days=7)
        delta = abs((session.absolute_expiry - expected).total_seconds())
        assert delta < 5

    @pytest.mark.unit
    def test_session_repository_has_constant(self, session_repository):
        """SessionRepository doit avoir SESSION_ABSOLUTE_EXPIRY_DAYS = 30."""
        assert hasattr(session_repository, 'SESSION_ABSOLUTE_EXPIRY_DAYS')
        assert session_repository.SESSION_ABSOLUTE_EXPIRY_DAYS == 30


class TestTokenServiceAbsoluteExpiry:
    """Tests pour le respect de l'expiration absolue dans TokenService."""

    @pytest.fixture
    def mock_refresh_repo(self):
        """Mock RefreshTokenRepository."""
        from app.repositories.refresh_token import RefreshTokenRepository
        return MagicMock(spec=RefreshTokenRepository)

    @pytest.fixture
    def mock_revoked_repo(self):
        """Mock RevokedTokenRepository."""
        from app.repositories.revoked_token import RevokedTokenRepository
        return MagicMock(spec=RevokedTokenRepository)

    @pytest.fixture
    def token_service(self, mock_refresh_repo, mock_revoked_repo):
        """TokenService avec mocks."""
        from app.services.token import TokenService
        return TokenService(mock_refresh_repo, mock_revoked_repo)

    @pytest.mark.unit
    def test_store_token_limits_expiry_by_session_absolute(
        self,
        token_service,
        mock_refresh_repo
    ):
        """store_refresh_token doit limiter expires_at par session_absolute_expiry."""
        now = datetime.now(timezone.utc)
        session_expiry = now + timedelta(days=5)  # Session expire dans 5 jours
        token_expiry = now + timedelta(days=30)  # Token veut 30 jours

        mock_refresh_repo.store_token.return_value = MagicMock()

        token_service.store_refresh_token(
            jti="test-jti",
            user_id=1,
            tenant_id=1,
            expires_at=token_expiry,
            session_id=str(uuid4()),
            raw_token="test-token",
            session_absolute_expiry=session_expiry
        )

        # Verifier que le token a ete stocke avec l'expiration limitee
        call_kwargs = mock_refresh_repo.store_token.call_args.kwargs
        assert call_kwargs['expires_at'] == session_expiry

    @pytest.mark.unit
    def test_store_token_rejects_expired_session(self, token_service):
        """store_refresh_token doit rejeter si session deja expiree."""
        from app.services.token import SessionAbsolutelyExpiredError

        now = datetime.now(timezone.utc)
        past_expiry = now - timedelta(hours=1)

        with pytest.raises(SessionAbsolutelyExpiredError):
            token_service.store_refresh_token(
                jti="test-jti",
                user_id=1,
                tenant_id=1,
                expires_at=now + timedelta(days=7),
                session_id=str(uuid4()),
                raw_token="test-token",
                session_absolute_expiry=past_expiry
            )

    @pytest.mark.unit
    def test_rotate_token_respects_absolute_expiry(
        self,
        token_service,
        mock_refresh_repo
    ):
        """rotate_refresh_token_complete doit limiter par absolute_expiry."""
        now = datetime.now(timezone.utc)
        session_expiry = now + timedelta(days=3)
        new_token_expiry = now + timedelta(days=7)

        # Mock ancien token
        old_token = MagicMock()
        old_token.used_at = None
        old_token.user_id = 1
        old_token.tenant_id = 1
        mock_refresh_repo.get_by_jti.return_value = old_token
        mock_refresh_repo.store_token.return_value = MagicMock()

        token_service.rotate_refresh_token_complete(
            old_jti="old-jti",
            new_jti="new-jti",
            new_expires_at=new_token_expiry,
            session_id=str(uuid4()),
            raw_token="new-token",
            session_absolute_expiry=session_expiry
        )

        # Verifier que expires_at est limite par session_expiry
        call_kwargs = mock_refresh_repo.store_token.call_args.kwargs
        assert call_kwargs['expires_at'] == session_expiry

    @pytest.mark.unit
    def test_rotate_token_rejects_expired_session(
        self,
        token_service,
        mock_refresh_repo
    ):
        """rotate_refresh_token_complete doit rejeter session expiree."""
        from app.services.token import SessionAbsolutelyExpiredError

        now = datetime.now(timezone.utc)
        past_expiry = now - timedelta(minutes=5)

        with pytest.raises(SessionAbsolutelyExpiredError):
            token_service.rotate_refresh_token_complete(
                old_jti="old-jti",
                new_jti="new-jti",
                new_expires_at=now + timedelta(days=7),
                session_id=str(uuid4()),
                raw_token="new-token",
                session_absolute_expiry=past_expiry
            )

    @pytest.mark.unit
    def test_session_absolutely_expired_error_exists(self):
        """SessionAbsolutelyExpiredError doit exister avec le bon code."""
        from app.services.token import SessionAbsolutelyExpiredError

        error = SessionAbsolutelyExpiredError(session_id="test-session")
        assert error.code == "SESSION_ABSOLUTE_EXPIRED"
        assert "30 jours" in error.message or "reconnexion" in error.message


class TestAbsoluteExpiryIntegration:
    """Tests d'integration pour le flow complet."""

    @pytest.mark.unit
    def test_session_revoked_takes_precedence_over_expiry(self):
        """Session revoquee doit etre inactive meme si non expiree."""
        from app.models.session import Session

        now = datetime.now(timezone.utc)

        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now + timedelta(days=30),  # Non expiree
            revoked_at=now - timedelta(hours=1)  # Mais revoquee
        )

        assert session.is_active is False

    @pytest.mark.unit
    def test_both_revoked_and_expired(self):
        """Session revoquee ET expiree doit etre inactive."""
        from app.models.session import Session

        now = datetime.now(timezone.utc)

        session = Session(
            id=uuid4(),
            user_id=1,
            tenant_id=1,
            absolute_expiry=now - timedelta(days=1),
            revoked_at=now - timedelta(hours=1)
        )

        assert session.is_active is False
        assert session.is_absolute_expired is True
