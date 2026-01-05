"""
Tests unitaires TDD pour les repositories MFA.

Ces tests definissent le comportement attendu des repositories:
- MFASecretRepository: CRUD pour les secrets TOTP
- MFARecoveryCodeRepository: CRUD pour les codes de recuperation

TDD: Ces tests sont ecrits AVANT l'implementation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from typing import List


class TestMFASecretRepository:
    """Tests pour MFASecretRepository"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def repository(self, mock_session):
        """Repository avec session mockee"""
        from app.repositories.mfa import MFASecretRepository
        return MFASecretRepository(mock_session)

    def test_repository_has_model_attribute(self, repository):
        """Le repository definit le modele MFASecret"""
        from app.models.mfa import MFASecret
        assert repository.model == MFASecret

    def test_get_by_user_id(self, repository, mock_session):
        """get_by_user_id retourne le secret d'un utilisateur"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.get_by_user_id(user_id=1)

        assert result is not None
        assert result.user_id == 1
        mock_session.query.assert_called()

    def test_get_by_user_id_not_found(self, repository, mock_session):
        """get_by_user_id retourne None si pas trouve"""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.get_by_user_id(user_id=999)

        assert result is None

    def test_get_by_user_and_tenant(self, repository, mock_session):
        """get_by_user_and_tenant filtre par tenant"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=2,
            secret="SECRET",
            enabled=True
        )
        mock_session.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.get_by_user_and_tenant(user_id=1, tenant_id=2)

        assert result is not None
        assert result.tenant_id == 2

    def test_create_or_update_creates_new(self, repository, mock_session):
        """create_or_update cree un nouveau secret si inexistant"""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.create_or_update(
            user_id=1,
            tenant_id=1,
            secret="NEWSECRET"
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_or_update_updates_existing(self, repository, mock_session):
        """create_or_update met a jour un secret existant"""
        from app.models.mfa import MFASecret

        existing = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="OLDSECRET",
            enabled=False
        )
        mock_session.query.return_value.filter.return_value.first.return_value = existing

        result = repository.create_or_update(
            user_id=1,
            tenant_id=1,
            secret="NEWSECRET"
        )

        assert existing.secret == "NEWSECRET"

    def test_enable_mfa(self, repository, mock_session):
        """enable_mfa active le MFA pour un utilisateur"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=False
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.enable_mfa(user_id=1)

        assert result is True
        assert mock_secret.enabled is True

    def test_enable_mfa_not_found(self, repository, mock_session):
        """enable_mfa retourne False si pas de secret"""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.enable_mfa(user_id=999)

        assert result is False

    def test_disable_mfa(self, repository, mock_session):
        """disable_mfa desactive le MFA"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.disable_mfa(user_id=1)

        assert result is True
        assert mock_secret.enabled is False

    def test_delete_by_user_id(self, repository, mock_session):
        """delete_by_user_id supprime le secret"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.delete_by_user_id(user_id=1)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_secret)

    def test_is_mfa_enabled(self, repository, mock_session):
        """is_mfa_enabled retourne True si MFA active"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.is_mfa_enabled(user_id=1)

        assert result is True

    def test_is_mfa_enabled_false_when_disabled(self, repository, mock_session):
        """is_mfa_enabled retourne False si MFA desactive"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=False
        )
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        result = repository.is_mfa_enabled(user_id=1)

        assert result is False

    def test_is_mfa_enabled_false_when_no_secret(self, repository, mock_session):
        """is_mfa_enabled retourne False si pas de secret"""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = repository.is_mfa_enabled(user_id=1)

        assert result is False

    def test_update_last_used(self, repository, mock_session):
        """update_last_used met a jour le timestamp"""
        from app.models.mfa import MFASecret

        mock_secret = MFASecret(
            user_id=1,
            tenant_id=1,
            secret="SECRET",
            enabled=True
        )
        mock_secret.last_used_at = None
        mock_session.query.return_value.filter.return_value.first.return_value = mock_secret

        repository.update_last_used(user_id=1)

        assert mock_secret.last_used_at is not None


class TestMFARecoveryCodeRepository:
    """Tests pour MFARecoveryCodeRepository"""

    @pytest.fixture
    def mock_session(self):
        """Session SQLAlchemy mockee"""
        session = MagicMock()
        return session

    @pytest.fixture
    def repository(self, mock_session):
        """Repository avec session mockee"""
        from app.repositories.mfa import MFARecoveryCodeRepository
        return MFARecoveryCodeRepository(mock_session)

    def test_repository_has_model_attribute(self, repository):
        """Le repository definit le modele MFARecoveryCode"""
        from app.models.mfa import MFARecoveryCode
        assert repository.model == MFARecoveryCode

    def test_create_codes_for_user(self, repository, mock_session):
        """create_codes_for_user cree plusieurs codes"""
        code_hashes = ["hash1", "hash2", "hash3"]

        result = repository.create_codes_for_user(
            user_id=1,
            tenant_id=1,
            code_hashes=code_hashes
        )

        assert mock_session.add_all.called or mock_session.add.call_count == 3
        mock_session.flush.assert_called()

    def test_get_valid_codes_for_user(self, repository, mock_session):
        """get_valid_codes_for_user retourne les codes non utilises"""
        from app.models.mfa import MFARecoveryCode

        codes = [
            MFARecoveryCode(id=1, user_id=1, tenant_id=1, code_hash="h1"),
            MFARecoveryCode(id=2, user_id=1, tenant_id=1, code_hash="h2"),
        ]
        mock_session.query.return_value.filter.return_value.filter.return_value.all.return_value = codes

        result = repository.get_valid_codes_for_user(user_id=1)

        assert len(result) == 2

    def test_get_code_by_hash(self, repository, mock_session):
        """get_code_by_hash trouve un code par son hash"""
        from app.models.mfa import MFARecoveryCode

        mock_code = MFARecoveryCode(
            id=1,
            user_id=1,
            tenant_id=1,
            code_hash="target_hash"
        )
        mock_session.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_code

        result = repository.get_code_by_hash(user_id=1, code_hash="target_hash")

        assert result is not None
        assert result.code_hash == "target_hash"

    def test_mark_code_as_used(self, repository, mock_session):
        """mark_code_as_used marque un code comme utilise"""
        from app.models.mfa import MFARecoveryCode

        mock_code = MFARecoveryCode(
            id=1,
            user_id=1,
            tenant_id=1,
            code_hash="hash"
        )
        mock_code.used_at = None
        mock_session.query.return_value.filter.return_value.first.return_value = mock_code

        result = repository.mark_code_as_used(code_id=1)

        assert result is True
        assert mock_code.used_at is not None

    def test_delete_all_for_user(self, repository, mock_session):
        """delete_all_for_user supprime tous les codes d'un utilisateur"""
        mock_session.query.return_value.filter.return_value.delete.return_value = 5

        result = repository.delete_all_for_user(user_id=1)

        assert result == 5

    def test_count_valid_codes(self, repository, mock_session):
        """count_valid_codes compte les codes non utilises"""
        mock_session.query.return_value.filter.return_value.filter.return_value.count.return_value = 8

        result = repository.count_valid_codes(user_id=1)

        assert result == 8

    def test_get_all_for_user(self, repository, mock_session):
        """get_all_for_user retourne tous les codes d'un utilisateur"""
        from app.models.mfa import MFARecoveryCode

        codes = [
            MFARecoveryCode(id=1, user_id=1, tenant_id=1, code_hash="h1"),
            MFARecoveryCode(id=2, user_id=1, tenant_id=1, code_hash="h2", used_at=datetime.now(timezone.utc)),
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = codes

        result = repository.get_all_for_user(user_id=1)

        assert len(result) == 2
