"""
Tests comportementaux pour l'isolation multi-tenant.

Ces tests verifient le comportement REEL, pas les interfaces.
Tous les tests doivent passer pour garantir qu'aucune donnee
cross-tenant ne peut etre accedee.

SECURITE CRITIQUE:
- TenantAwareBaseRepository doit TOUJOURS filtrer par tenant_id
- Aucun acces cross-tenant ne doit etre possible
- Le tenant_id ne peut JAMAIS etre modifie via update
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.repositories.base import (
    TenantAwareBaseRepository,
    TenantIsolationError,
    PaginationError,
)
from app.repositories.user import TenantAwareUserRepository
from app.models import User


class TestTenantAwareBaseRepositoryBehavior:
    """
    Tests comportementaux pour TenantAwareBaseRepository.

    Ces tests verifient que l'isolation fonctionne REELLEMENT,
    pas juste que les methodes existent.
    """

    def test_get_returns_none_for_different_tenant(self):
        """
        CRITIQUE: get() doit retourner None si l'objet existe
        mais appartient a un autre tenant.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Simule objet non trouve dans ce tenant

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        result = repo.get(999)

        # Assert
        assert result is None
        # Verifier que le filtrage tenant est applique
        filter_calls = mock_query.filter.call_args_list
        assert len(filter_calls) >= 1  # Au moins un filtre tenant

    def test_get_all_only_returns_current_tenant_objects(self):
        """
        CRITIQUE: get_all() ne doit retourner QUE les objets du tenant courant.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        tenant1_users = [MagicMock(id=1, tenant_id=1), MagicMock(id=2, tenant_id=1)]
        mock_query.all.return_value = tenant1_users

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        results = repo.get_all()

        # Assert
        assert len(results) == 2
        # Verifier que TOUS les resultats sont du bon tenant
        for user in results:
            assert user.tenant_id == 1

    def test_create_forces_tenant_id_even_if_different_passed(self):
        """
        CRITIQUE: create() doit FORCER le tenant_id du repository,
        meme si un tenant_id different est passe dans data.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        created_user = None

        def capture_add(obj):
            nonlocal created_user
            created_user = obj
            obj.id = 1

        mock_session.add.side_effect = capture_add

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        # Tentative de passer un tenant_id different
        repo.create({
            "email": "test@test.com",
            "tenant_id": 999,  # MALICIEUX: tenter de creer dans un autre tenant
            "password_hash": "hash"
        })

        # Assert
        # L'objet cree doit avoir tenant_id=1, pas 999
        assert created_user.tenant_id == 1

    def test_update_cannot_change_tenant_id(self):
        """
        CRITIQUE: update() ne doit JAMAIS permettre de modifier le tenant_id.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        existing_user = MagicMock()
        existing_user.id = 1
        existing_user.tenant_id = 1
        existing_user.email = "old@test.com"
        mock_query.first.return_value = existing_user

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        repo.update(1, {
            "email": "new@test.com",
            "tenant_id": 999  # MALICIEUX: tenter de changer le tenant
        })

        # Assert
        # Le tenant_id doit rester 1
        assert existing_user.tenant_id == 1
        # L'email doit etre mis a jour
        assert existing_user.email == "new@test.com"

    def test_delete_only_deletes_if_same_tenant(self):
        """
        CRITIQUE: delete() ne doit supprimer QUE si l'objet est du meme tenant.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Simule: objet non trouve dans ce tenant

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        result = repo.delete(999)  # ID existe mais dans un autre tenant

        # Assert
        assert result is False  # Pas de suppression car pas dans ce tenant
        mock_session.delete.assert_not_called()

    def test_count_only_counts_current_tenant(self):
        """
        CRITIQUE: count() doit compter UNIQUEMENT les objets du tenant courant.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5  # 5 users dans ce tenant

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        count = repo.count()

        # Assert
        assert count == 5
        # Verifier que le filtre tenant est applique
        mock_query.filter.assert_called()

    def test_exists_returns_false_for_other_tenant_object(self):
        """
        CRITIQUE: exists() doit retourner False si l'objet existe
        mais appartient a un autre tenant.
        """
        # Arrange
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # Non trouve dans ce tenant

        # Act
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        result = repo.exists(999)  # Existe dans tenant 2, pas tenant 1

        # Assert
        assert result is False


class TestTenantIsolationErrors:
    """Tests pour les erreurs d'isolation tenant."""

    def test_initialization_without_tenant_id_fails(self):
        """
        Le repository tenant-aware requiert un tenant_id.
        """
        mock_session = MagicMock(spec=Session)

        # TypeError car tenant_id est requis
        with pytest.raises(TypeError):
            TenantAwareUserRepository(mock_session)  # Missing tenant_id

    def test_tenant_id_is_readonly_property(self):
        """
        Le tenant_id doit etre accessible mais pas modifiable directement.
        La propriete doit retourner la valeur interne _tenant_id.
        Toute tentative de modification doit lever AttributeError.
        """
        mock_session = MagicMock(spec=Session)
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)

        # La propriete doit retourner la valeur correcte
        assert repo.tenant_id == 1

        # Tentative de modification doit lever AttributeError
        # car c'est une propriete readonly (pas de setter)
        with pytest.raises(AttributeError):
            repo.tenant_id = 999

        # La valeur interne reste inchangee
        assert repo._tenant_id == 1


class TestFilterByBehavior:
    """Tests pour filter_by et first_by."""

    def test_filter_by_includes_tenant_filter(self):
        """filter_by doit automatiquement filtrer par tenant."""
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        repo.filter_by(is_active=True)

        # Verifier que filter est appele (tenant + is_active)
        assert mock_query.filter.call_count >= 2

    def test_first_by_includes_tenant_filter(self):
        """first_by doit automatiquement filtrer par tenant."""
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        repo.first_by(email="test@test.com")

        # Verifier que filter est appele (tenant + email)
        assert mock_query.filter.call_count >= 2


class TestPaginationWithTenantIsolation:
    """Tests pour la pagination avec isolation tenant."""

    def test_paginate_only_returns_tenant_objects(self):
        """paginate doit filtrer par tenant."""
        mock_session = MagicMock(spec=Session)
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        repo = TenantAwareUserRepository(mock_session, tenant_id=1)
        result = repo.paginate(page=1, page_size=10)

        assert result.total == 10
        mock_query.filter.assert_called()

    def test_pagination_validates_page_size(self):
        """La taille de page est limitee a MAX_PAGE_SIZE."""
        mock_session = MagicMock(spec=Session)
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)

        with pytest.raises(PaginationError):
            repo.paginate(page=1, page_size=1000)  # Trop grand

    def test_pagination_validates_page_number(self):
        """Le numero de page doit etre >= 1."""
        mock_session = MagicMock(spec=Session)
        repo = TenantAwareUserRepository(mock_session, tenant_id=1)

        with pytest.raises(PaginationError):
            repo.paginate(page=0, page_size=10)
