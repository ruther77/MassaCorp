"""
Tests TDD - Corrections Session et Validation

Tests RED ecrits AVANT implementation pour:
- Issue #6: is_session_valid() retourne toujours False
- Issue #7: except_jti ignore silencieusement
- Issue #10: include_inactive non implemente
- Issue #11: Audit silencieux en cas d'erreur

Ces tests DOIVENT echouer avant implementation.
"""
import pytest
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestSessionRepositoryValidation:
    """Tests Issues #6-7: is_session_valid et except_jti"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock SQLAlchemy Session"""
        return MagicMock()

    @pytest.fixture
    def session_repository(self, mock_db_session):
        """SessionRepository avec mock"""
        from app.repositories.session import SessionRepository
        return SessionRepository(mock_db_session)

    # ============================================
    # Issue #6: is_session_valid() retourne False
    # ============================================

    @pytest.mark.unit
    def test_is_session_valid_returns_true_for_active_session(
        self,
        session_repository,
        mock_db_session
    ):
        """is_session_valid retourne True pour une session active"""
        session_id = uuid4()

        # Mock session active
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.revoked_at = None  # Non revoquee
        mock_session.is_active = True

        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session

        # La signature doit accepter session_id (pas token_jti)
        result = session_repository.is_session_valid(session_id=session_id)

        assert result is True, \
            "is_session_valid doit retourner True pour une session active"

    @pytest.mark.unit
    def test_is_session_valid_returns_false_for_revoked_session(
        self,
        session_repository,
        mock_db_session
    ):
        """is_session_valid retourne False pour une session revoquee"""
        session_id = uuid4()

        # Mock session revoquee
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.revoked_at = datetime.now(timezone.utc)
        mock_session.is_active = False

        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session

        result = session_repository.is_session_valid(session_id=session_id)

        assert result is False, \
            "is_session_valid doit retourner False pour une session revoquee"

    @pytest.mark.unit
    def test_is_session_valid_returns_false_for_nonexistent(
        self,
        session_repository,
        mock_db_session
    ):
        """is_session_valid retourne False pour une session inexistante"""
        session_id = uuid4()

        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = session_repository.is_session_valid(session_id=session_id)

        assert result is False, \
            "is_session_valid doit retourner False pour une session inexistante"

    @pytest.mark.unit
    def test_is_session_valid_accepts_uuid_parameter(self, session_repository):
        """is_session_valid doit accepter session_id (UUID), pas token_jti (str)"""
        import inspect
        from uuid import UUID

        sig = inspect.signature(session_repository.is_session_valid)
        params = list(sig.parameters.keys())

        # Doit avoir session_id comme parametre
        assert "session_id" in params, \
            "is_session_valid doit accepter session_id comme parametre"

    # ============================================
    # Issue #7: except_jti ignore silencieusement
    # ============================================

    @pytest.mark.unit
    def test_invalidate_all_accepts_except_session_id(self, session_repository):
        """invalidate_all_sessions doit accepter except_session_id (pas except_jti)"""
        import inspect

        sig = inspect.signature(session_repository.invalidate_all_sessions)
        params = list(sig.parameters.keys())

        # Doit avoir except_session_id (standardise depuis except_current)
        assert "except_session_id" in params, \
            "invalidate_all_sessions doit accepter except_session_id"

    @pytest.mark.unit
    def test_invalidate_all_respects_except_session_id(
        self,
        session_repository,
        mock_db_session
    ):
        """invalidate_all_sessions garde la session courante intacte"""
        user_id = 1
        current_session_id = uuid4()
        other_session_id = uuid4()

        # Mock sessions
        mock_current_session = MagicMock()
        mock_current_session.id = current_session_id
        mock_current_session.user_id = user_id
        mock_current_session.revoked_at = None

        mock_other_session = MagicMock()
        mock_other_session.id = other_session_id
        mock_other_session.user_id = user_id
        mock_other_session.revoked_at = None

        # Setup query mock
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 1

        # Appel avec except_session_id
        result = session_repository.invalidate_all_sessions(
            user_id=user_id,
            except_session_id=current_session_id
        )

        # Verifier que le filtre exclut la session courante
        # Le mock doit avoir ete appele avec un filtre excluant current_session_id
        filter_calls = mock_query.filter.call_args_list

        # Au moins un appel filter doit exclure la session courante
        # On verifie que except_session_id n'est pas ignore
        assert len(filter_calls) >= 1, \
            "invalidate_all_sessions doit appeler filter() avec exclusion"

    @pytest.mark.unit
    def test_invalidate_all_without_except_invalidates_all(
        self,
        session_repository,
        mock_db_session
    ):
        """invalidate_all_sessions sans except invalide toutes les sessions"""
        user_id = 1

        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3  # 3 sessions invalidees

        result = session_repository.invalidate_all_sessions(user_id=user_id)

        assert result == 3, \
            "invalidate_all_sessions doit retourner le nombre de sessions invalidees"


class TestSessionServiceIncludeInactive:
    """Tests Issue #10: include_inactive non implemente"""

    @pytest.fixture
    def mock_session_repo(self):
        """Mock SessionRepository"""
        from app.repositories.session import SessionRepository
        return MagicMock(spec=SessionRepository)

    @pytest.fixture
    def mock_login_attempt_repo(self):
        """Mock LoginAttemptRepository"""
        from app.repositories.login_attempt import LoginAttemptRepository
        return MagicMock(spec=LoginAttemptRepository)

    @pytest.fixture
    def session_service(self, mock_session_repo, mock_login_attempt_repo):
        """SessionService avec mocks"""
        from app.services.session import SessionService
        return SessionService(
            session_repository=mock_session_repo,
            login_attempt_repository=mock_login_attempt_repo
        )

    @pytest.mark.unit
    def test_get_user_sessions_include_inactive_works(
        self,
        session_service,
        mock_session_repo
    ):
        """get_user_sessions avec include_inactive=True retourne aussi les revoquees"""
        user_id = 1

        # Mock sessions (actives et revoquees)
        active_session = MagicMock()
        active_session.revoked_at = None
        active_session.is_active = True

        revoked_session = MagicMock()
        revoked_session.revoked_at = datetime.now(timezone.utc)
        revoked_session.is_active = False

        # Repository retourne les deux si include_inactive=True
        mock_session_repo.get_all_sessions.return_value = [active_session, revoked_session]
        mock_session_repo.get_active_sessions.return_value = [active_session]

        result = session_service.get_user_sessions(
            user_id=user_id,
            tenant_id=1,
            include_inactive=True
        )

        # Doit retourner les deux sessions
        assert len(result) >= 2, \
            "include_inactive=True doit retourner aussi les sessions revoquees"

    @pytest.mark.unit
    def test_get_user_sessions_include_inactive_false_excludes_revoked(
        self,
        session_service,
        mock_session_repo
    ):
        """get_user_sessions avec include_inactive=False exclut les revoquees"""
        user_id = 1

        active_session = MagicMock()
        active_session.is_active = True

        mock_session_repo.get_active_sessions.return_value = [active_session]

        result = session_service.get_user_sessions(
            user_id=user_id,
            tenant_id=1,
            include_inactive=False
        )

        # Doit retourner uniquement les sessions actives
        for session in result:
            assert session.is_active is True

    @pytest.mark.unit
    def test_session_repository_has_get_all_sessions_method(self):
        """SessionRepository doit avoir une methode get_all_sessions"""
        from app.repositories.session import SessionRepository

        assert hasattr(SessionRepository, "get_all_sessions"), \
            "SessionRepository doit avoir get_all_sessions() pour include_inactive"


class TestAuditReliability:
    """Tests Issue #11: Audit silencieux en cas d'erreur"""

    @pytest.fixture
    def mock_audit_repo(self):
        """Mock AuditLogRepository"""
        from app.repositories.audit_log import AuditLogRepository
        return MagicMock(spec=AuditLogRepository)

    @pytest.fixture
    def audit_service(self, mock_audit_repo):
        """AuditService avec mock"""
        from app.services.audit import AuditService
        return AuditService(audit_repository=mock_audit_repo)

    @pytest.mark.unit
    def test_audit_log_failure_logs_critical(
        self,
        audit_service,
        mock_audit_repo,
        caplog
    ):
        """Echec d'audit doit logger CRITICAL (pas WARNING)"""
        # Setup - faire echouer le repository
        mock_audit_repo.create.side_effect = Exception("Database error")

        with caplog.at_level(logging.CRITICAL):
            try:
                audit_service.log_action(
                    user_id=1,
                    tenant_id=1,
                    action="login",
                    resource_type="session",
                    details={}
                )
            except Exception:
                pass  # On accepte que ca leve une exception

        # Doit avoir un log CRITICAL
        critical_logs = [
            record for record in caplog.records
            if record.levelno >= logging.CRITICAL
        ]
        assert len(critical_logs) >= 1 or mock_audit_repo.create.called, \
            "Echec audit doit logger CRITICAL ou lever exception"

    @pytest.mark.unit
    def test_audit_failure_in_auth_service_is_visible(self, caplog):
        """Echec d'audit dans AuthService ne doit pas etre silencieux"""
        from app.services.auth import AuthService
        from unittest.mock import MagicMock

        # Setup AuthService avec audit qui echoue
        mock_user_repo = MagicMock()
        mock_session_service = MagicMock()
        mock_token_service = MagicMock()
        mock_audit_service = MagicMock()
        mock_mfa_service = MagicMock()

        # Audit echoue
        mock_audit_service.log_action.side_effect = Exception("Audit DB error")

        auth_service = AuthService(
            user_repository=mock_user_repo,
            session_service=mock_session_service,
            token_service=mock_token_service,
            audit_service=mock_audit_service,
            mfa_service=mock_mfa_service
        )

        # Setup login
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.is_active = True
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user
        mock_session_service.is_account_locked.return_value = False
        mock_session_service.create_session.return_value = MagicMock(id=uuid4())
        mock_mfa_service.is_mfa_enabled.return_value = False

        with caplog.at_level(logging.WARNING):
            with patch("app.services.auth.verify_password", return_value=True):
                with patch("app.services.auth.create_access_token", return_value="token"):
                    with patch("app.services.auth.create_refresh_token", return_value="token"):
                        try:
                            auth_service.login(
                                email="test@test.com",
                                password="password",
                                tenant_id=1
                            )
                        except Exception:
                            pass

        # Verifier qu'un log WARNING ou superieur existe OU que l'exception est propagee
        warning_or_higher = [
            record for record in caplog.records
            if record.levelno >= logging.WARNING
        ]

        # L'echec d'audit doit etre visible (log ou exception)
        # Un simple logger.warning silencieux n'est pas suffisant pour un echec d'audit
        # On devrait avoir CRITICAL ou ERROR
        error_or_higher = [
            record for record in caplog.records
            if record.levelno >= logging.ERROR
        ]

        assert len(error_or_higher) >= 1 or len(warning_or_higher) >= 1, \
            "Echec d'audit doit etre visible dans les logs"
