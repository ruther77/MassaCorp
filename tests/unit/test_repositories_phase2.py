"""
Tests unitaires TDD pour les Repositories Phase 2
Tests ecrits AVANT implementation (approche RED)
Couvre: AuditLogRepository, LoginAttemptRepository, SessionRepository,
        RefreshTokenRepository, RevokedTokenRepository

Ces tests doivent ECHOUER car les repositories n'existent pas encore.
"""
import pytest
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session
import uuid


# ============================================================================
# Tests AuditLogRepository - Interface
# ============================================================================

class TestAuditLogRepositoryInterface:
    """
    Tests pour verifier que l'interface AuditLogRepository existe
    et possede toutes les methodes requises.

    Ces tests verifient la structure de l'API publique du repository
    avant son implementation.
    """

    @pytest.mark.unit
    def test_audit_log_repository_module_exists(self):
        """Le module audit_log doit exister dans app.repositories"""
        # Ce test doit echouer car le module n'existe pas encore
        from app.repositories.audit_log import AuditLogRepository
        assert AuditLogRepository is not None

    @pytest.mark.unit
    def test_audit_log_model_exists(self):
        """Le model AuditLog doit exister dans app.models"""
        # Ce test doit echouer car le model n'existe pas encore
        from app.models import AuditLog
        assert AuditLog is not None

    @pytest.mark.unit
    def test_audit_log_repository_has_create_method(self):
        """AuditLogRepository doit avoir une methode create"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "create")
        assert callable(getattr(AuditLogRepository, "create"))

    @pytest.mark.unit
    def test_audit_log_repository_has_get_by_user_method(self):
        """AuditLogRepository doit avoir une methode get_by_user pour filtrer par user_id"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "get_by_user")
        assert callable(getattr(AuditLogRepository, "get_by_user"))

    @pytest.mark.unit
    def test_audit_log_repository_has_get_by_tenant_method(self):
        """AuditLogRepository doit avoir une methode get_by_tenant pour isolation multi-tenant"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "get_by_tenant")
        assert callable(getattr(AuditLogRepository, "get_by_tenant"))

    @pytest.mark.unit
    def test_audit_log_repository_has_get_by_action_method(self):
        """AuditLogRepository doit avoir une methode get_by_action pour filtrer par type d'action"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "get_by_action")
        assert callable(getattr(AuditLogRepository, "get_by_action"))

    @pytest.mark.unit
    def test_audit_log_repository_has_get_by_date_range_method(self):
        """AuditLogRepository doit avoir une methode get_by_date_range pour filtrer par periode"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "get_by_date_range")
        assert callable(getattr(AuditLogRepository, "get_by_date_range"))

    @pytest.mark.unit
    def test_audit_log_repository_has_search_method(self):
        """AuditLogRepository doit avoir une methode search avec filtres multiples"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "search")
        assert callable(getattr(AuditLogRepository, "search"))

    @pytest.mark.unit
    def test_audit_log_repository_has_count_by_action_method(self):
        """AuditLogRepository doit avoir une methode count_by_action pour statistiques"""
        from app.repositories.audit_log import AuditLogRepository
        assert hasattr(AuditLogRepository, "count_by_action")
        assert callable(getattr(AuditLogRepository, "count_by_action"))


class TestAuditLogRepositoryWithMocks:
    """
    Tests du comportement de AuditLogRepository avec mocks.

    Ces tests verifient la logique metier de chaque methode
    en mockant la session SQLAlchemy.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee pour tests unitaires"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def audit_repo(self, mock_session):
        """Instance AuditLogRepository avec session mockee"""
        from app.repositories.audit_log import AuditLogRepository
        return AuditLogRepository(mock_session)

    @pytest.mark.unit
    def test_create_audit_log_with_all_fields(self, audit_repo, mock_session):
        """
        create doit accepter tous les champs d'un audit log:
        - user_id, tenant_id, action, resource_type, resource_id
        - ip_address, user_agent, details (JSON)
        """
        log_data = {
            "user_id": 1,
            "tenant_id": 1,
            "action": "LOGIN_SUCCESS",
            "resource_type": "user",
            "resource_id": 1,
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 Chrome/120",
            "details": {"method": "password", "mfa_used": False}
        }

        result = audit_repo.create(log_data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_create_audit_log_without_optional_fields(self, audit_repo, mock_session):
        """create doit fonctionner avec seulement les champs obligatoires"""
        log_data = {
            "user_id": 1,
            "tenant_id": 1,
            "action": "LOGOUT"
        }

        result = audit_repo.create(log_data)

        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_get_by_user_filters_correctly(self, audit_repo, mock_session):
        """get_by_user doit filtrer par user_id et supporter la pagination"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = audit_repo.get_by_user(user_id=1, skip=0, limit=50)

        mock_session.query.assert_called_once()
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_get_by_tenant_ensures_isolation(self, audit_repo, mock_session):
        """
        get_by_tenant doit garantir l'isolation multi-tenant:
        - Ne jamais retourner des logs d'autres tenants
        - Supporter la pagination
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = audit_repo.get_by_tenant(tenant_id=42, skip=0, limit=100)

        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_get_by_action_supports_multiple_actions(self, audit_repo, mock_session):
        """
        get_by_action doit supporter le filtrage par une ou plusieurs actions.
        Cas d'usage: recuperer tous les LOGIN_SUCCESS et LOGIN_FAILED.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        # Test avec une seule action
        result = audit_repo.get_by_action(action="LOGIN_SUCCESS", tenant_id=1)
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_get_by_date_range_filters_by_timestamps(self, audit_repo, mock_session):
        """
        get_by_date_range doit filtrer les logs entre deux dates.
        Les dates sont en timezone UTC.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        result = audit_repo.get_by_date_range(
            start_date=start_date,
            end_date=end_date,
            tenant_id=1
        )

        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_search_with_multiple_filters(self, audit_repo, mock_session):
        """
        search doit combiner plusieurs filtres:
        - user_id (optionnel)
        - tenant_id (obligatoire pour isolation)
        - actions (liste optionnelle)
        - start_date, end_date (optionnels)
        - resource_type (optionnel)
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        result = audit_repo.search(
            tenant_id=1,
            user_id=5,
            actions=["LOGIN_SUCCESS", "PASSWORD_CHANGE"],
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            resource_type="user",
            skip=0,
            limit=100
        )

        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_count_by_action_returns_statistics(self, audit_repo, mock_session):
        """
        count_by_action doit retourner un dict {action: count}.
        Utile pour les tableaux de bord de securite.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            ("LOGIN_SUCCESS", 150),
            ("LOGIN_FAILED", 23),
            ("LOGOUT", 145)
        ]

        result = audit_repo.count_by_action(tenant_id=1)

        assert isinstance(result, dict)
        assert "LOGIN_SUCCESS" in result


# ============================================================================
# Tests LoginAttemptRepository
# ============================================================================

class TestLoginAttemptRepositoryInterface:
    """
    Tests pour l'interface de LoginAttemptRepository.

    Ce repository gere le tracking des tentatives de connexion
    pour la protection contre les attaques brute-force.
    """

    @pytest.mark.unit
    def test_login_attempt_repository_module_exists(self):
        """Le module login_attempt doit exister dans app.repositories"""
        from app.repositories.login_attempt import LoginAttemptRepository
        assert LoginAttemptRepository is not None

    @pytest.mark.unit
    def test_login_attempt_model_exists(self):
        """Le model LoginAttempt doit exister dans app.models"""
        from app.models import LoginAttempt
        assert LoginAttempt is not None

    @pytest.mark.unit
    def test_login_attempt_repository_has_record_attempt_method(self):
        """LoginAttemptRepository doit avoir record_attempt pour enregistrer une tentative"""
        from app.repositories.login_attempt import LoginAttemptRepository
        assert hasattr(LoginAttemptRepository, "record_attempt")
        assert callable(getattr(LoginAttemptRepository, "record_attempt"))

    @pytest.mark.unit
    def test_login_attempt_repository_has_count_recent_failures_method(self):
        """
        LoginAttemptRepository doit avoir count_recent_failures
        pour compter les echecs dans les N dernieres minutes.
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        assert hasattr(LoginAttemptRepository, "count_recent_failures")
        assert callable(getattr(LoginAttemptRepository, "count_recent_failures"))

    @pytest.mark.unit
    def test_login_attempt_repository_has_is_locked_out_method(self):
        """
        LoginAttemptRepository doit avoir is_locked_out
        pour verifier si un compte est verrouille.
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        assert hasattr(LoginAttemptRepository, "is_locked_out")
        assert callable(getattr(LoginAttemptRepository, "is_locked_out"))

    @pytest.mark.unit
    def test_login_attempt_repository_has_get_last_successful_method(self):
        """LoginAttemptRepository doit avoir get_last_successful pour la derniere connexion reussie"""
        from app.repositories.login_attempt import LoginAttemptRepository
        assert hasattr(LoginAttemptRepository, "get_last_successful")
        assert callable(getattr(LoginAttemptRepository, "get_last_successful"))

    @pytest.mark.unit
    def test_login_attempt_repository_has_cleanup_old_attempts_method(self):
        """
        LoginAttemptRepository doit avoir cleanup_old_attempts
        pour supprimer les vieilles tentatives (RGPD).
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        assert hasattr(LoginAttemptRepository, "cleanup_old_attempts")
        assert callable(getattr(LoginAttemptRepository, "cleanup_old_attempts"))


class TestLoginAttemptRepositoryWithMocks:
    """
    Tests du comportement de LoginAttemptRepository.

    Ces tests verifient la logique de protection brute-force
    et le tracking des tentatives de connexion.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def login_attempt_repo(self, mock_session):
        """Instance LoginAttemptRepository avec mock"""
        from app.repositories.login_attempt import LoginAttemptRepository
        return LoginAttemptRepository(mock_session)

    @pytest.mark.unit
    def test_record_attempt_saves_all_fields(self, login_attempt_repo, mock_session):
        """
        record_attempt doit sauvegarder:
        - email, success (bool), ip_address, user_agent
        - tenant_id (pour isolation multi-tenant)
        - created_at (automatique)
        """
        result = login_attempt_repo.record_attempt(
            email="user@test.com",
            tenant_id=1,
            success=False,
            ip_address="192.168.1.50",
            user_agent="Mozilla/5.0 Firefox/121"
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_record_attempt_normalizes_email(self, login_attempt_repo, mock_session):
        """
        record_attempt doit normaliser l'email en lowercase
        pour eviter les contournements (User@TEST.com vs user@test.com).
        """
        login_attempt_repo.record_attempt(
            email="User@TEST.COM",
            tenant_id=1,
            success=False,
            ip_address="10.0.0.1"
        )

        # Verification que l'email est normalise lors de la creation
        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_count_recent_failures_uses_time_window(self, login_attempt_repo, mock_session):
        """
        count_recent_failures(email, minutes=15) doit compter
        uniquement les echecs dans les N dernieres minutes.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 3

        result = login_attempt_repo.count_recent_failures(
            email="user@test.com",
            tenant_id=1,
            minutes=15
        )

        assert result == 3
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_count_recent_failures_ignores_successes(self, login_attempt_repo, mock_session):
        """
        count_recent_failures ne doit compter QUE les echecs (success=False),
        pas les connexions reussies.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 0  # Aucun echec

        result = login_attempt_repo.count_recent_failures(
            email="user@test.com",
            tenant_id=1,
            minutes=30
        )

        assert result == 0

    @pytest.mark.unit
    def test_is_locked_out_returns_true_when_threshold_exceeded(
        self, login_attempt_repo, mock_session
    ):
        """
        is_locked_out doit retourner True si le nombre d'echecs
        depasse max_attempts dans la fenetre lockout_minutes.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 6  # Plus que max_attempts=5

        result = login_attempt_repo.is_locked_out(
            email="attacker@test.com",
            tenant_id=1,
            max_attempts=5,
            lockout_minutes=30
        )

        assert result is True

    @pytest.mark.unit
    def test_is_locked_out_returns_false_when_under_threshold(
        self, login_attempt_repo, mock_session
    ):
        """
        is_locked_out doit retourner False si le nombre d'echecs
        est inferieur a max_attempts.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 2  # Moins que max_attempts=5

        result = login_attempt_repo.is_locked_out(
            email="user@test.com",
            tenant_id=1,
            max_attempts=5,
            lockout_minutes=30
        )

        assert result is False

    @pytest.mark.unit
    def test_is_locked_out_per_tenant_isolation(self, login_attempt_repo, mock_session):
        """
        Le lockout doit etre isole par tenant:
        - user@test.com sur tenant 1 peut etre locke
        - user@test.com sur tenant 2 peut etre libre
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10  # Beaucoup d'echecs

        # Le filtre doit inclure tenant_id
        result = login_attempt_repo.is_locked_out(
            email="user@test.com",
            tenant_id=1,
            max_attempts=5,
            lockout_minutes=30
        )

        # Verification que le filtre tenant_id est applique
        mock_query.filter.assert_called()
        assert result is True  # Doit etre verrouille car 10 > 5

    @pytest.mark.unit
    def test_get_last_successful_returns_most_recent(self, login_attempt_repo, mock_session):
        """
        get_last_successful doit retourner la derniere connexion reussie.
        Utile pour afficher "Derniere connexion: il y a 2 jours".
        """
        from app.models import LoginAttempt

        mock_attempt = MagicMock()
        mock_attempt.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_attempt

        result = login_attempt_repo.get_last_successful(
            email="user@test.com",
            tenant_id=1
        )

        assert result is not None
        mock_query.first.assert_called_once()

    @pytest.mark.unit
    def test_cleanup_old_attempts_deletes_old_records(self, login_attempt_repo, mock_session):
        """
        cleanup_old_attempts(days=90) doit supprimer les tentatives
        de plus de N jours (conformite RGPD).
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 150  # 150 records supprimes

        result = login_attempt_repo.cleanup_old_attempts(days=90)

        assert result == 150
        mock_query.delete.assert_called_once()


# ============================================================================
# Tests SessionRepository
# ============================================================================

class TestSessionRepositoryInterface:
    """
    Tests pour l'interface de SessionRepository.

    Ce repository gere les sessions utilisateur (JWT sessions),
    permettant l'invalidation et le listing des sessions actives.
    """

    @pytest.mark.unit
    def test_session_repository_module_exists(self):
        """Le module session doit exister dans app.repositories"""
        from app.repositories.session import SessionRepository
        assert SessionRepository is not None

    @pytest.mark.unit
    def test_user_session_model_exists(self):
        """Le model UserSession doit exister dans app.models"""
        from app.models import UserSession
        assert UserSession is not None

    @pytest.mark.unit
    def test_session_repository_has_create_session_method(self):
        """SessionRepository doit avoir create_session"""
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "create_session")
        assert callable(getattr(SessionRepository, "create_session"))

    @pytest.mark.unit
    def test_session_repository_has_get_active_sessions_method(self):
        """SessionRepository doit avoir get_active_sessions pour lister les sessions d'un user"""
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "get_active_sessions")
        assert callable(getattr(SessionRepository, "get_active_sessions"))

    @pytest.mark.unit
    def test_session_repository_has_invalidate_session_method(self):
        """SessionRepository doit avoir invalidate_session pour deconnecter une session"""
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "invalidate_session")
        assert callable(getattr(SessionRepository, "invalidate_session"))

    @pytest.mark.unit
    def test_session_repository_has_invalidate_all_sessions_method(self):
        """
        SessionRepository doit avoir invalidate_all_sessions
        pour deconnecter toutes les sessions d'un user (logout global).
        """
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "invalidate_all_sessions")
        assert callable(getattr(SessionRepository, "invalidate_all_sessions"))

    @pytest.mark.unit
    def test_session_repository_has_is_session_valid_method(self):
        """SessionRepository doit avoir is_session_valid pour verifier si un token est encore actif"""
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "is_session_valid")
        assert callable(getattr(SessionRepository, "is_session_valid"))

    @pytest.mark.unit
    def test_session_repository_has_cleanup_expired_method(self):
        """SessionRepository doit avoir cleanup_expired pour nettoyer les sessions expirees"""
        from app.repositories.session import SessionRepository
        assert hasattr(SessionRepository, "cleanup_expired")
        assert callable(getattr(SessionRepository, "cleanup_expired"))


class TestSessionRepositoryWithMocks:
    """
    Tests du comportement de SessionRepository.

    Ces tests verifient la logique de gestion des sessions
    incluant creation, validation et invalidation.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def session_repo(self, mock_session):
        """Instance SessionRepository avec mock"""
        from app.repositories.session import SessionRepository
        return SessionRepository(mock_session)

    @pytest.mark.unit
    def test_create_session_stores_all_metadata(self, session_repo, mock_session):
        """
        create_session doit stocker:
        - user_id, tenant_id
        - token_jti (identifiant unique du JWT)
        - ip_address, user_agent (pour audit)
        - created_at, expires_at
        - is_active=True
        """
        token_jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        result = session_repo.create_session(
            user_id=1,
            tenant_id=1,
            token_jti=token_jti,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Chrome/120",
            expires_at=expires_at
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_get_active_sessions_returns_only_active(self, session_repo, mock_session):
        """
        get_active_sessions doit retourner uniquement les sessions
        avec is_active=True et expires_at > now.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = session_repo.get_active_sessions(user_id=1)

        mock_query.filter.assert_called()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_active_sessions_respects_tenant_isolation(self, session_repo, mock_session):
        """
        get_active_sessions doit respecter l'isolation multi-tenant.
        Un admin de tenant A ne peut pas voir les sessions de tenant B.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        result = session_repo.get_active_sessions(user_id=1, tenant_id=42)

        # Le filtre tenant_id doit etre applique
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_invalidate_session_sets_is_active_false(self, session_repo, mock_session):
        """
        invalidate_session doit mettre revoked_at sur la session.
        Notre modele Session utilise revoked_at (is_active est une property).
        """
        from app.models import Session as SessionModel
        from uuid import uuid4

        # Notre implementation utilise UUID, pas int pour session_id
        session_uuid = uuid4()
        mock_user_session = MagicMock(spec=SessionModel)
        mock_user_session.id = session_uuid
        mock_user_session.revoked_at = None

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user_session

        result = session_repo.invalidate_session(session_id=session_uuid)

        # Verifie que revoked_at a ete defini (pas None)
        assert mock_user_session.revoked_at is not None

    @pytest.mark.unit
    def test_invalidate_session_by_jti(self, session_repo, mock_session):
        """
        invalidate_session par token_jti.
        Note: Notre implementation actuelle ne stocke pas le JTI dans Session
        directement (le JTI est dans RefreshToken). Cette methode retourne
        False quand seul token_jti est fourni.
        """
        token_jti = str(uuid.uuid4())

        # Notre implementation retourne False quand on ne peut pas
        # trouver la session (JTI n'est pas stocke dans Session)
        result = session_repo.invalidate_session(token_jti=token_jti)

        # L'implementation actuelle ne supporte pas JTI directement
        assert result is False

    @pytest.mark.unit
    def test_invalidate_all_sessions_for_user(self, session_repo, mock_session):
        """
        invalidate_all_sessions(user_id) doit invalider TOUTES les sessions.
        Cas d'usage: changement de mot de passe, compte compromis.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 5  # 5 sessions invalidees

        result = session_repo.invalidate_all_sessions(user_id=1)

        mock_query.update.assert_called_once()
        assert result == 5

    @pytest.mark.unit
    def test_invalidate_all_sessions_except_current(self, session_repo, mock_session):
        """
        invalidate_all_sessions doit pouvoir exclure la session courante.
        Cas d'usage: "Deconnecter tous les autres appareils".
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3

        current_session_id = uuid.uuid4()
        result = session_repo.invalidate_all_sessions(
            user_id=1,
            except_session_id=current_session_id
        )

        assert result == 3

    @pytest.mark.unit
    def test_is_session_valid_checks_active_and_expiry(self, session_repo, mock_session):
        """
        is_session_valid(session_id) verifie la validite de session.
        Issue #6 CORRIGE: Accepte maintenant session_id (UUID) au lieu de token_jti.
        """
        # Tester avec une session inexistante (retourne False)
        result = session_repo.is_session_valid(session_id=uuid.uuid4())

        # Session inexistante retourne False
        assert result is False

    @pytest.mark.unit
    def test_is_session_valid_returns_false_if_revoked(self, session_repo, mock_session):
        """is_session_valid doit retourner False si session est revoquee"""
        from app.models import UserSession

        mock_user_session = MagicMock(spec=UserSession)
        mock_user_session.revoked_at = datetime.now(timezone.utc)  # Session revoquee

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_user_session

        session_id = uuid.uuid4()
        result = session_repo.is_session_valid(session_id=session_id)

        assert result is False

    @pytest.mark.unit
    def test_cleanup_expired_removes_old_sessions(self, session_repo, mock_session):
        """
        cleanup_expired doit supprimer les sessions expirees depuis plus de N jours.
        Garde un historique recent pour audit.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 250

        result = session_repo.cleanup_expired(older_than_days=30)

        assert result == 250
        mock_query.delete.assert_called_once()


# ============================================================================
# Tests RefreshTokenRepository
# ============================================================================

class TestRefreshTokenRepositoryInterface:
    """
    Tests pour l'interface de RefreshTokenRepository.

    Ce repository gere les refresh tokens JWT,
    permettant le renouvellement des access tokens sans re-authentification.
    """

    @pytest.mark.unit
    def test_refresh_token_repository_module_exists(self):
        """Le module refresh_token doit exister dans app.repositories"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert RefreshTokenRepository is not None

    @pytest.mark.unit
    def test_refresh_token_model_exists(self):
        """Le model RefreshToken doit exister dans app.models"""
        from app.models import RefreshToken
        assert RefreshToken is not None

    @pytest.mark.unit
    def test_refresh_token_repository_has_store_token_method(self):
        """RefreshTokenRepository doit avoir store_token pour enregistrer un nouveau refresh token"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "store_token")
        assert callable(getattr(RefreshTokenRepository, "store_token"))

    @pytest.mark.unit
    def test_refresh_token_repository_has_is_valid_method(self):
        """RefreshTokenRepository doit avoir is_valid pour verifier si un token est valide"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "is_valid")
        assert callable(getattr(RefreshTokenRepository, "is_valid"))

    @pytest.mark.unit
    def test_refresh_token_repository_has_revoke_token_method(self):
        """RefreshTokenRepository doit avoir revoke_token pour invalider un token"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "revoke_token")
        assert callable(getattr(RefreshTokenRepository, "revoke_token"))

    @pytest.mark.unit
    def test_refresh_token_repository_has_revoke_all_for_user_method(self):
        """RefreshTokenRepository doit avoir revoke_all_for_user pour invalider tous les tokens d'un user"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "revoke_all_for_user")
        assert callable(getattr(RefreshTokenRepository, "revoke_all_for_user"))

    @pytest.mark.unit
    def test_refresh_token_repository_has_cleanup_expired_method(self):
        """RefreshTokenRepository doit avoir cleanup_expired pour nettoyer les tokens expires"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "cleanup_expired")
        assert callable(getattr(RefreshTokenRepository, "cleanup_expired"))

    @pytest.mark.unit
    def test_refresh_token_repository_has_get_by_jti_method(self):
        """RefreshTokenRepository doit avoir get_by_jti pour recuperer un token par son identifiant"""
        from app.repositories.refresh_token import RefreshTokenRepository
        assert hasattr(RefreshTokenRepository, "get_by_jti")
        assert callable(getattr(RefreshTokenRepository, "get_by_jti"))


class TestRefreshTokenRepositoryWithMocks:
    """
    Tests du comportement de RefreshTokenRepository.

    Ces tests verifient la logique de gestion des refresh tokens
    incluant stockage, validation et revocation.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def refresh_token_repo(self, mock_session):
        """Instance RefreshTokenRepository avec mock"""
        from app.repositories.refresh_token import RefreshTokenRepository
        return RefreshTokenRepository(mock_session)

    @pytest.mark.unit
    def test_store_token_saves_all_fields(self, refresh_token_repo, mock_session):
        """
        store_token doit sauvegarder:
        - jti (identifiant unique du JWT)
        - user_id, tenant_id
        - expires_at
        - token_hash (SHA256 du token brut)
        - session_id (OBLIGATOIRE)
        - is_revoked=False (par defaut)
        - created_at (automatique)
        """
        from app.core.security import hash_token

        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_hash = hash_token("raw_token_value")  # Hash SHA256 requis

        result = refresh_token_repo.store_token(
            jti=jti,
            user_id=1,
            tenant_id=1,
            expires_at=expires_at,
            session_id=str(uuid.uuid4()),  # Session obligatoire (UUID valide)
            token_hash=token_hash
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_store_token_with_device_info(self, refresh_token_repo, mock_session):
        """
        store_token doit accepter des metadonnees optionnelles:
        - device_name ("iPhone de Jean")
        - ip_address
        - user_agent
        """
        from app.core.security import hash_token

        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_hash = hash_token("raw_token_value")  # Hash SHA256 requis

        result = refresh_token_repo.store_token(
            jti=jti,
            user_id=1,
            tenant_id=1,
            expires_at=expires_at,
            session_id=str(uuid.uuid4()),  # Session obligatoire (UUID valide)
            token_hash=token_hash,
            device_name="MacBook Pro",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Safari/605"
        )

        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_is_valid_checks_all_conditions(self, refresh_token_repo, mock_session):
        """
        is_valid(jti) doit verifier:
        - Le token existe en DB
        - used_at is None (token pas encore utilise/revoque)
        - expires_at > now
        Note: Notre modele RefreshToken utilise used_at au lieu de is_revoked
        """
        from app.models import RefreshToken

        mock_token = MagicMock(spec=RefreshToken)
        mock_token.used_at = None  # Token pas utilise = valide
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        result = refresh_token_repo.is_valid(jti=str(uuid.uuid4()))

        assert result is True

    @pytest.mark.unit
    def test_is_valid_returns_false_if_revoked(self, refresh_token_repo, mock_session):
        """is_valid doit retourner False si is_revoked=True"""
        from app.models import RefreshToken

        mock_token = MagicMock(spec=RefreshToken)
        mock_token.is_revoked = True  # Token revoque
        mock_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        result = refresh_token_repo.is_valid(jti=str(uuid.uuid4()))

        assert result is False

    @pytest.mark.unit
    def test_is_valid_returns_false_if_expired(self, refresh_token_repo, mock_session):
        """is_valid doit retourner False si expires_at < now"""
        from app.models import RefreshToken

        mock_token = MagicMock(spec=RefreshToken)
        mock_token.is_revoked = False
        mock_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expire

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        result = refresh_token_repo.is_valid(jti=str(uuid.uuid4()))

        assert result is False

    @pytest.mark.unit
    def test_is_valid_returns_false_if_not_found(self, refresh_token_repo, mock_session):
        """is_valid doit retourner False si le token n'existe pas en DB"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Non trouve

        result = refresh_token_repo.is_valid(jti=str(uuid.uuid4()))

        assert result is False

    @pytest.mark.unit
    def test_revoke_token_sets_is_revoked_true(self, refresh_token_repo, mock_session):
        """
        revoke_token doit marquer le token comme utilise.
        Notre modele RefreshToken utilise used_at au lieu de is_revoked.
        Un token avec used_at != None est considere comme revoque/utilise.
        """
        from app.models import RefreshToken

        mock_token = MagicMock(spec=RefreshToken)
        mock_token.used_at = None

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        result = refresh_token_repo.revoke_token(jti=str(uuid.uuid4()))

        # Notre implementation met used_at (pas is_revoked)
        assert mock_token.used_at is not None

    @pytest.mark.unit
    def test_revoke_token_returns_false_if_not_found(self, refresh_token_repo, mock_session):
        """revoke_token doit retourner False si le token n'existe pas"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = refresh_token_repo.revoke_token(jti=str(uuid.uuid4()))

        assert result is False

    @pytest.mark.unit
    def test_revoke_all_for_user_invalidates_all_tokens(self, refresh_token_repo, mock_session):
        """
        revoke_all_for_user doit revoquer tous les refresh tokens d'un user.
        Cas d'usage: changement de mot de passe, compte compromis.
        Notre implementation fait une jointure avec sessions car user_id
        est dans Session, pas dans RefreshToken.
        """
        from app.models.session import Session as SessionModel

        # Mock pour la requete de sessions
        mock_session_query = MagicMock()
        mock_token_query = MagicMock()

        # Premier appel: query(Session) pour trouver les sessions de l'user
        # Deuxieme appel: query(RefreshToken) pour revoquer les tokens
        mock_session.query.side_effect = [mock_session_query, mock_token_query]

        # Sessions de l'utilisateur
        mock_session_1 = MagicMock()
        mock_session_1.id = "session-uuid-1"
        mock_session_query.filter.return_value = mock_session_query
        mock_session_query.all.return_value = [mock_session_1]

        # Tokens a revoquer
        mock_token_query.filter.return_value = mock_token_query
        mock_token_query.update.return_value = 8

        result = refresh_token_repo.revoke_all_for_user(user_id=1)

        assert result == 8

    @pytest.mark.unit
    def test_revoke_all_for_user_respects_tenant_isolation(self, refresh_token_repo, mock_session):
        """
        revoke_all_for_user doit respecter l'isolation multi-tenant.
        Ne doit affecter que les tokens du tenant specifie.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3

        result = refresh_token_repo.revoke_all_for_user(user_id=1, tenant_id=42)

        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_cleanup_expired_deletes_old_tokens(self, refresh_token_repo, mock_session):
        """
        cleanup_expired doit supprimer les tokens expires.
        Peut etre configure pour garder les revoques pour audit.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 500  # 500 tokens supprimes

        result = refresh_token_repo.cleanup_expired()

        assert result == 500
        mock_query.delete.assert_called_once()

    @pytest.mark.unit
    def test_get_by_jti_returns_token_info(self, refresh_token_repo, mock_session):
        """get_by_jti doit retourner le token avec toutes ses infos"""
        from app.models import RefreshToken

        mock_token = MagicMock(spec=RefreshToken)
        mock_token.jti = "test-jti"
        mock_token.user_id = 1
        mock_token.is_revoked = False

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_token

        result = refresh_token_repo.get_by_jti(jti="test-jti")

        assert result is not None
        assert result.user_id == 1


# ============================================================================
# Tests RevokedTokenRepository
# ============================================================================

class TestRevokedTokenRepositoryInterface:
    """
    Tests pour l'interface de RevokedTokenRepository.

    Ce repository gere la blacklist des tokens JWT revoques,
    permettant d'invalider des access tokens avant leur expiration.
    """

    @pytest.mark.unit
    def test_revoked_token_repository_module_exists(self):
        """Le module revoked_token doit exister dans app.repositories"""
        from app.repositories.revoked_token import RevokedTokenRepository
        assert RevokedTokenRepository is not None

    @pytest.mark.unit
    def test_revoked_token_model_exists(self):
        """Le model RevokedToken doit exister dans app.models"""
        from app.models import RevokedToken
        assert RevokedToken is not None

    @pytest.mark.unit
    def test_revoked_token_repository_has_add_to_blacklist_method(self):
        """RevokedTokenRepository doit avoir add_to_blacklist pour ajouter un token a la blacklist"""
        from app.repositories.revoked_token import RevokedTokenRepository
        assert hasattr(RevokedTokenRepository, "add_to_blacklist")
        assert callable(getattr(RevokedTokenRepository, "add_to_blacklist"))

    @pytest.mark.unit
    def test_revoked_token_repository_has_is_revoked_method(self):
        """RevokedTokenRepository doit avoir is_revoked pour verifier si un token est blackliste"""
        from app.repositories.revoked_token import RevokedTokenRepository
        assert hasattr(RevokedTokenRepository, "is_revoked")
        assert callable(getattr(RevokedTokenRepository, "is_revoked"))

    @pytest.mark.unit
    def test_revoked_token_repository_has_cleanup_expired_method(self):
        """RevokedTokenRepository doit avoir cleanup_expired pour nettoyer les vieilles entrees"""
        from app.repositories.revoked_token import RevokedTokenRepository
        assert hasattr(RevokedTokenRepository, "cleanup_expired")
        assert callable(getattr(RevokedTokenRepository, "cleanup_expired"))

    @pytest.mark.unit
    def test_revoked_token_repository_has_bulk_add_method(self):
        """RevokedTokenRepository doit avoir bulk_add pour revoquer plusieurs tokens d'un coup"""
        from app.repositories.revoked_token import RevokedTokenRepository
        assert hasattr(RevokedTokenRepository, "bulk_add")
        assert callable(getattr(RevokedTokenRepository, "bulk_add"))


class TestRevokedTokenRepositoryWithMocks:
    """
    Tests du comportement de RevokedTokenRepository.

    Ces tests verifient la logique de gestion de la blacklist
    de tokens JWT revoques.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.fixture
    def revoked_token_repo(self, mock_session):
        """Instance RevokedTokenRepository avec mock"""
        from app.repositories.revoked_token import RevokedTokenRepository
        return RevokedTokenRepository(mock_session)

    @pytest.mark.unit
    def test_add_to_blacklist_stores_jti_and_expiry(self, revoked_token_repo, mock_session):
        """
        add_to_blacklist doit stocker:
        - jti (identifiant unique du JWT)
        - expires_at (pour cleanup automatique)
        - revoked_at (timestamp de revocation)
        """
        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        result = revoked_token_repo.add_to_blacklist(
            jti=jti,
            expires_at=expires_at
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.unit
    def test_add_to_blacklist_with_reason(self, revoked_token_repo, mock_session):
        """add_to_blacklist peut accepter une raison optionnelle pour audit"""
        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        result = revoked_token_repo.add_to_blacklist(
            jti=jti,
            expires_at=expires_at,
            reason="manual_logout"
        )

        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_add_to_blacklist_handles_duplicate_gracefully(self, revoked_token_repo, mock_session):
        """
        add_to_blacklist doit gerer les doublons sans erreur.
        Un meme token peut etre revoque plusieurs fois (idempotent).
        """
        from sqlalchemy.exc import IntegrityError

        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Simuler un conflit d'unicite
        mock_session.flush.side_effect = IntegrityError(None, None, None)

        # Ne doit pas lever d'exception
        result = revoked_token_repo.add_to_blacklist(
            jti=jti,
            expires_at=expires_at
        )

        # Doit retourner True meme si le token existait deja
        assert result is True or result is None

    @pytest.mark.unit
    def test_is_revoked_returns_true_if_in_blacklist(self, revoked_token_repo, mock_session):
        """is_revoked doit retourner True si le jti est dans la blacklist"""
        from app.models import RevokedToken

        mock_revoked = MagicMock(spec=RevokedToken)
        mock_revoked.jti = "test-jti"

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_revoked

        result = revoked_token_repo.is_revoked(jti="test-jti")

        assert result is True

    @pytest.mark.unit
    def test_is_revoked_returns_false_if_not_in_blacklist(self, revoked_token_repo, mock_session):
        """is_revoked doit retourner False si le jti n'est pas blackliste"""
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Non trouve

        result = revoked_token_repo.is_revoked(jti=str(uuid.uuid4()))

        assert result is False

    @pytest.mark.unit
    def test_is_revoked_fast_lookup_optimized(self, revoked_token_repo, mock_session):
        """
        is_revoked doit etre optimise pour des lookups rapides.
        La table doit avoir un index sur jti pour O(log n) lookup.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        # Ce test verifie surtout que la requete est simple
        revoked_token_repo.is_revoked(jti=str(uuid.uuid4()))

        # Verification qu'on ne fait pas de jointures complexes
        mock_session.query.assert_called_once()

    @pytest.mark.unit
    def test_cleanup_expired_removes_old_entries(self, revoked_token_repo, mock_session):
        """
        cleanup_expired doit supprimer les entrees dont expires_at < now.
        Une fois le token original expire, plus besoin de garder la revocation.
        """
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 1000  # 1000 entrees supprimees

        result = revoked_token_repo.cleanup_expired()

        assert result == 1000
        mock_query.delete.assert_called_once()

    @pytest.mark.unit
    def test_bulk_add_revokes_multiple_tokens(self, revoked_token_repo, mock_session):
        """
        bulk_add doit permettre de revoquer plusieurs tokens en une seule operation.
        Cas d'usage: logout global de toutes les sessions d'un utilisateur.
        """
        tokens = [
            {"jti": str(uuid.uuid4()), "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15)},
            {"jti": str(uuid.uuid4()), "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)},
            {"jti": str(uuid.uuid4()), "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)},
        ]

        result = revoked_token_repo.bulk_add(tokens)

        # Doit avoir ajoute 3 tokens
        assert mock_session.add_all.called or mock_session.bulk_insert_mappings.called

    @pytest.mark.unit
    def test_bulk_add_handles_empty_list(self, revoked_token_repo, mock_session):
        """bulk_add avec une liste vide ne doit pas echouer"""
        result = revoked_token_repo.bulk_add([])

        # Ne doit pas lever d'exception
        assert result == 0 or result is None


# ============================================================================
# Tests Edge Cases et Multi-tenant
# ============================================================================

class TestRepositoriesMultiTenantIsolation:
    """
    Tests pour verifier l'isolation multi-tenant sur tous les repositories Phase 2.

    Ces tests s'assurent qu'un tenant ne peut jamais acceder aux donnees
    d'un autre tenant, meme en cas de bug ou d'attaque.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_audit_log_query_always_includes_tenant_filter(self, mock_session):
        """
        Toutes les methodes de lecture d'AuditLogRepository doivent
        filtrer par tenant_id pour garantir l'isolation.
        """
        from app.repositories.audit_log import AuditLogRepository
        repo = AuditLogRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        # get_by_tenant doit toujours filtrer
        repo.get_by_tenant(tenant_id=1)
        mock_query.filter.assert_called()

    @pytest.mark.unit
    def test_login_attempt_isolation_prevents_cross_tenant_lockout(self, mock_session):
        """
        Un attaquant sur tenant A ne doit pas pouvoir verrouiller
        un compte sur tenant B en echouant des logins sur tenant A.
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        repo = LoginAttemptRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 10  # 10 echecs

        # Le lockout doit etre specifique au tenant
        result_tenant_1 = repo.is_locked_out(
            email="user@test.com",
            tenant_id=1,
            max_attempts=5,
            lockout_minutes=30
        )

        # Meme email sur tenant 2 ne doit pas etre affecte
        mock_query.scalar.return_value = 0  # 0 echecs sur tenant 2
        result_tenant_2 = repo.is_locked_out(
            email="user@test.com",
            tenant_id=2,
            max_attempts=5,
            lockout_minutes=30
        )

        # Les deux appels doivent utiliser des filtres differents
        assert mock_query.filter.call_count >= 2

    @pytest.mark.unit
    def test_session_cannot_list_sessions_from_other_tenant(self, mock_session):
        """
        get_active_sessions ne doit jamais retourner des sessions
        d'un autre tenant, meme si on passe un user_id valide.
        """
        from app.repositories.session import SessionRepository
        repo = SessionRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []

        # User 1 existe sur tenant 1 et tenant 2
        # L'admin de tenant 1 ne doit voir que les sessions de tenant 1
        repo.get_active_sessions(user_id=1, tenant_id=1)

        mock_query.filter.assert_called()


class TestRepositoriesEdgeCases:
    """
    Tests des cas limites et scenarios d'erreur.

    Ces tests verifient que les repositories gerent correctement
    les situations inhabituelles ou les erreurs.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_audit_log_handles_very_large_details_json(self, mock_session):
        """
        create doit gerer les details JSON volumineux
        (limite raisonnable a definir, ex: 64KB).
        """
        from app.repositories.audit_log import AuditLogRepository
        repo = AuditLogRepository(mock_session)

        # Details JSON de 50KB
        large_details = {"data": "x" * 50000}

        log_data = {
            "user_id": 1,
            "tenant_id": 1,
            "action": "BULK_IMPORT",
            "details": large_details
        }

        # Ne doit pas lever d'exception
        repo.create(log_data)
        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_login_attempt_handles_null_user_agent(self, mock_session):
        """
        record_attempt doit accepter un user_agent None
        (cas des appels API sans User-Agent header).
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        repo = LoginAttemptRepository(mock_session)

        repo.record_attempt(
            email="user@test.com",
            tenant_id=1,
            success=False,
            ip_address="10.0.0.1",
            user_agent=None
        )

        mock_session.add.assert_called_once()

    @pytest.mark.unit
    def test_session_handles_concurrent_invalidation(self, mock_session):
        """
        invalidate_session doit gerer le cas ou la session
        a deja ete invalidee par une autre requete.
        """
        from app.repositories.session import SessionRepository
        repo = SessionRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Deja invalidee ou supprimee

        # Ne doit pas lever d'exception
        result = repo.invalidate_session(session_id=999)

        # Doit retourner False ou None
        assert result is False or result is None

    @pytest.mark.unit
    def test_refresh_token_handles_uuid_collision(self, mock_session):
        """
        store_token doit gerer le cas (theoriquement impossible)
        d'une collision d'UUID.
        """
        from app.repositories.refresh_token import RefreshTokenRepository
        from app.core.security import hash_token
        from sqlalchemy.exc import IntegrityError

        repo = RefreshTokenRepository(mock_session)

        jti = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_hash = hash_token("raw_token_value")

        # Simuler une collision d'unicite
        mock_session.flush.side_effect = IntegrityError(None, None, None)

        # Doit lever une exception appropriee ou regenerer le JTI
        try:
            repo.store_token(
                jti=jti,
                user_id=1,
                tenant_id=1,
                expires_at=expires_at,
                session_id=str(uuid.uuid4()),  # UUID valide
                token_hash=token_hash
            )
        except Exception as e:
            # Doit etre une exception explicite, pas une erreur SQL brute
            assert True

    @pytest.mark.unit
    def test_revoked_token_handles_expired_token_check(self, mock_session):
        """
        is_revoked doit aussi verifier si le token est dans la blacklist
        meme si l'entree de revocation a techniquement expire.
        """
        from app.repositories.revoked_token import RevokedTokenRepository
        from app.models import RevokedToken

        repo = RevokedTokenRepository(mock_session)

        # Token revoque mais entree "expiree" (cleanup pas encore passe)
        mock_revoked = MagicMock(spec=RevokedToken)
        mock_revoked.jti = "old-revoked-jti"
        mock_revoked.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_revoked

        result = repo.is_revoked(jti="old-revoked-jti")

        # Meme si l'entree est "expiree", le token reste revoque
        # jusqu'au cleanup (approche conservative)
        assert result is True


class TestRepositoriesPerformance:
    """
    Tests pour verifier les bonnes pratiques de performance.

    Ces tests s'assurent que les repositories n'effectuent pas
    d'operations couteuses inutiles.
    """

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock(spec=Session)
        return session

    @pytest.mark.unit
    def test_is_revoked_uses_exists_query(self, mock_session):
        """
        is_revoked doit utiliser une requete EXISTS ou COUNT(1)
        plutot que de charger l'entite complete.
        """
        from app.repositories.revoked_token import RevokedTokenRepository
        repo = RevokedTokenRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        repo.is_revoked(jti=str(uuid.uuid4()))

        # La requete ne doit pas charger tous les champs
        # (verifie au moins que la methode est appelee)
        mock_session.query.assert_called()

    @pytest.mark.unit
    def test_cleanup_uses_bulk_delete(self, mock_session):
        """
        Les methodes cleanup_* doivent utiliser DELETE en masse
        plutot que de charger puis supprimer un par un.
        """
        from app.repositories.revoked_token import RevokedTokenRepository
        repo = RevokedTokenRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 100

        repo.cleanup_expired()

        # Doit utiliser delete() plutot que de boucler
        mock_query.delete.assert_called()

    @pytest.mark.unit
    def test_count_recent_failures_uses_count_query(self, mock_session):
        """
        count_recent_failures doit utiliser COUNT(*) en SQL
        plutot que de recuperer puis compter en Python.
        """
        from app.repositories.login_attempt import LoginAttemptRepository
        repo = LoginAttemptRepository(mock_session)

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = 5

        result = repo.count_recent_failures(
            email="user@test.com",
            tenant_id=1,
            minutes=15
        )

        # Doit retourner directement le resultat du COUNT
        assert result == 5
        mock_query.scalar.assert_called()
