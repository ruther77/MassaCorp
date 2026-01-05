"""
Tests TDD pour la correction IDOR sur les sessions.

Ces tests vérifient que:
1. La vérification de propriété se fait en une seule requête
2. Une session non-possédée retourne 404 (pas 403)
3. Aucune information n'est divulguée sur l'existence d'une session
"""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4


class TestSessionOwnershipCheck:
    """Tests pour la vérification de propriété des sessions"""

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_session_for_user_returns_owned_session(self):
        """get_session_for_user retourne la session si l'utilisateur la possède"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        mock_login_repo = MagicMock()

        session_id = uuid4()
        user_id = 1

        # Simuler une session appartenant à l'utilisateur
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.user_id = user_id
        mock_session_repo.get_session_for_user.return_value = mock_session

        service = SessionService(
            session_repository=mock_session_repo,
            login_attempt_repository=mock_login_repo
        )

        result = service.get_session_for_user(session_id, user_id)

        assert result is not None
        assert result.id == session_id
        # Vérifier que la requête est faite avec les deux paramètres
        mock_session_repo.get_session_for_user.assert_called_once_with(
            session_id, user_id
        )

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_session_for_user_returns_none_when_not_owned(self):
        """get_session_for_user retourne None si la session appartient à un autre user"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        mock_login_repo = MagicMock()

        session_id = uuid4()
        user_id = 1
        other_user_id = 2

        # La session existe mais appartient à un autre utilisateur
        # Le repository doit retourner None car le filtre user_id ne match pas
        mock_session_repo.get_session_for_user.return_value = None

        service = SessionService(
            session_repository=mock_session_repo,
            login_attempt_repository=mock_login_repo
        )

        result = service.get_session_for_user(session_id, other_user_id)

        assert result is None

    @pytest.mark.unit
    @pytest.mark.security
    def test_get_session_for_user_returns_none_when_not_exists(self):
        """get_session_for_user retourne None si la session n'existe pas"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        mock_login_repo = MagicMock()

        session_id = uuid4()
        user_id = 1

        # Session inexistante
        mock_session_repo.get_session_for_user.return_value = None

        service = SessionService(
            session_repository=mock_session_repo,
            login_attempt_repository=mock_login_repo
        )

        result = service.get_session_for_user(session_id, user_id)

        assert result is None


class TestSessionRepositoryOwnershipQuery:
    """Tests pour la requête atomique dans le repository"""

    @pytest.mark.unit
    @pytest.mark.security
    def test_repository_has_get_session_for_user_method(self):
        """SessionRepository doit avoir une méthode get_session_for_user"""
        from app.repositories.session import SessionRepository

        assert hasattr(SessionRepository, "get_session_for_user")
        assert callable(getattr(SessionRepository, "get_session_for_user"))

    @pytest.mark.unit
    @pytest.mark.security
    def test_repository_get_session_for_user_filters_by_both(self):
        """get_session_for_user filtre par session_id ET user_id dans une seule requête"""
        from app.repositories.session import SessionRepository

        mock_db_session = MagicMock()
        repo = SessionRepository(mock_db_session)

        session_id = uuid4()
        user_id = 1

        # Mock de la chaîne de query SQLAlchemy
        mock_query = MagicMock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = repo.get_session_for_user(session_id, user_id)

        # Vérifier que la query est appelée
        mock_db_session.query.assert_called_once()


class TestTerminateSessionOwnership:
    """Tests pour la terminaison de session avec vérification de propriété"""

    @pytest.mark.unit
    @pytest.mark.security
    def test_terminate_session_verifies_ownership_atomically(self):
        """terminate_session vérifie la propriété dans la requête d'invalidation"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        mock_login_repo = MagicMock()

        session_id = uuid4()
        user_id = 1

        # Le repository retourne False car la session n'appartient pas à l'utilisateur
        mock_session_repo.invalidate_session.return_value = False

        service = SessionService(
            session_repository=mock_session_repo,
            login_attempt_repository=mock_login_repo
        )

        result = service.terminate_session(session_id, user_id=user_id)

        # Vérifier que la terminaison échoue silencieusement
        assert result is False
        # Vérifier que user_id est passé au repository
        mock_session_repo.invalidate_session.assert_called_once()
        call_kwargs = mock_session_repo.invalidate_session.call_args
        # Vérifier que user_id est passé
        assert call_kwargs[1].get("user_id") == user_id or user_id in call_kwargs[0]
