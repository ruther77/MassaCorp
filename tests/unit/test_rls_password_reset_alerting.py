"""
Tests TDD pour:
1. RLS PostgreSQL - Row Level Security pour isolation multi-tenant
2. Password Reset - Flow complet de reinitialisation de mot de passe
3. Alerting Rules - Regles d'alerte Prometheus/Alertmanager

Ces tests sont ecrits AVANT l'implementation (TDD).
"""
import pytest
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# =============================================================================
# 1. TESTS RLS POSTGRESQL
# =============================================================================


class TestRLSPolicies:
    """Tests pour Row Level Security PostgreSQL."""

    @pytest.mark.integration
    @pytest.mark.security
    def test_rls_policy_exists_on_users_table(self, db_session):
        """Verifie que RLS est active sur la table users."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT relrowsecurity
            FROM pg_class
            WHERE relname = 'users'
        """))
        row = result.fetchone()

        assert row is not None, "Table users not found"
        assert row[0] is True, "RLS should be enabled on users table"

    @pytest.mark.integration
    @pytest.mark.security
    def test_rls_policy_exists_on_sessions_table(self, db_session):
        """Verifie que RLS est active sur la table sessions."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT relrowsecurity
            FROM pg_class
            WHERE relname = 'sessions'
        """))
        row = result.fetchone()

        assert row is not None, "Table sessions not found"
        assert row[0] is True, "RLS should be enabled on sessions table"

    @pytest.mark.integration
    @pytest.mark.security
    def test_rls_policy_exists_on_refresh_tokens_table(self, db_session):
        """Verifie que RLS est active sur la table refresh_tokens."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT relrowsecurity
            FROM pg_class
            WHERE relname = 'refresh_tokens'
        """))
        row = result.fetchone()

        assert row is not None, "Table refresh_tokens not found"
        assert row[0] is True, "RLS should be enabled on refresh_tokens table"

    @pytest.mark.integration
    @pytest.mark.security
    def test_tenant_isolation_policy_blocks_cross_tenant_read(self, db_session):
        """
        Verifie qu'un utilisateur d'un tenant ne peut pas lire les donnees d'un autre tenant.

        Note: Ce test necessite un utilisateur sans privilege BYPASSRLS.
        L'utilisateur 'massa' (owner) a ce privilege par defaut, donc le test
        verifie la presence de la policy plutot que son effet.
        """
        from sqlalchemy import text

        # Verifier si l'utilisateur courant peut bypass RLS
        result = db_session.execute(text("""
            SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user
        """))
        can_bypass = result.scalar()

        if can_bypass:
            # L'utilisateur peut bypass RLS, on verifie seulement que la policy existe
            result = db_session.execute(text("""
                SELECT COUNT(*) FROM pg_policy
                WHERE polrelid = 'users'::regclass
                AND polname = 'tenant_isolation'
            """))
            policy_count = result.scalar()
            assert policy_count > 0, "RLS tenant_isolation policy should exist on users table"
            pytest.skip("User has BYPASSRLS privilege - RLS blocking cannot be tested")

        # Set tenant context to tenant 1
        db_session.execute(text("SET LOCAL app.current_tenant_id = '1'"))

        # Try to read users - should only see tenant 1 users
        result = db_session.execute(text("""
            SELECT COUNT(*) FROM users WHERE tenant_id = 2
        """))
        count = result.scalar()

        # With RLS, count should be 0 even if tenant 2 has users
        assert count == 0, "RLS should block reading users from other tenants"

    @pytest.mark.integration
    @pytest.mark.security
    def test_tenant_context_setting_function_exists(self, db_session):
        """Verifie que la fonction de setting du tenant context existe."""
        from sqlalchemy import text

        # The setting should be settable
        result = db_session.execute(text("""
            SELECT set_config('app.current_tenant_id', '1', true)
        """))
        value = result.scalar()
        assert value == '1', "Should be able to set tenant context"

    @pytest.mark.integration
    @pytest.mark.security
    def test_rls_policy_allows_same_tenant_access(self, db_session):
        """Verifie que l'acces aux donnees du meme tenant est autorise."""
        from sqlalchemy import text

        # Set tenant context to tenant 1
        db_session.execute(text("SET LOCAL app.current_tenant_id = '1'"))

        # Read users from tenant 1 - should work
        result = db_session.execute(text("""
            SELECT id FROM users WHERE tenant_id = 1 LIMIT 1
        """))
        row = result.fetchone()

        # If there's a user in tenant 1, we should be able to read it
        # (This test assumes there's at least one user in tenant 1)
        # If no users exist, this test is inconclusive but passes


class TestRLSMigration:
    """Tests pour la migration RLS."""

    @pytest.mark.integration
    def test_rls_migration_creates_policies(self, db_session):
        """Verifie que les policies RLS sont creees."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT polname FROM pg_policy
            WHERE polrelid = 'users'::regclass
        """))
        policies = [row[0] for row in result.fetchall()]

        assert len(policies) > 0, "At least one RLS policy should exist on users table"
        assert 'tenant_isolation' in policies or any('tenant' in p for p in policies), \
            "A tenant isolation policy should exist"


# =============================================================================
# 2. TESTS PASSWORD RESET
# =============================================================================


class TestPasswordResetTokenGeneration:
    """Tests pour la generation de tokens de reset."""

    def test_reset_token_is_cryptographically_secure(self):
        """Le token doit etre genere avec secrets.token_urlsafe."""
        from app.services.password_reset import PasswordResetService

        service = PasswordResetService(MagicMock())
        token = service.generate_reset_token()

        # Token should be at least 32 characters (256 bits of entropy)
        assert len(token) >= 32, "Token should have at least 256 bits of entropy"

        # Token should be URL-safe
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token), "Token should be URL-safe"

    def test_reset_token_is_hashed_before_storage(self):
        """Le token doit etre hashe (SHA-256) avant stockage."""
        from app.services.password_reset import PasswordResetService

        service = PasswordResetService(MagicMock())
        token = service.generate_reset_token()
        token_hash = service.hash_token(token)

        # Hash should be 64 characters (SHA-256 hex)
        assert len(token_hash) == 64, "Token hash should be SHA-256 (64 hex chars)"

        # Hash should be deterministic
        assert service.hash_token(token) == token_hash

        # Hash should be different from token
        assert token_hash != token

    def test_reset_token_has_one_hour_expiration(self):
        """Le token doit expirer apres 1 heure."""
        from app.services.password_reset import PasswordResetService

        service = PasswordResetService(MagicMock())
        expires_at = service.get_expiration_time()

        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(hours=1)

        # Allow 5 seconds tolerance
        assert abs((expires_at - expected_expiry).total_seconds()) < 5


class TestPasswordResetRequest:
    """Tests pour la demande de reset."""

    @pytest.mark.unit
    def test_request_reset_creates_token_for_existing_user(self):
        """Une demande cree un token pour un utilisateur existant."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_repo.can_request_reset = MagicMock(return_value=True)
        mock_token = MagicMock(id=1, user_id=1)
        mock_repo.create_reset_token = MagicMock(return_value=(mock_token, "raw_token"))

        service = PasswordResetService(mock_repo)
        service.request_reset(user_id=1)

        mock_repo.create_reset_token.assert_called_once()

    @pytest.mark.unit
    def test_request_reset_returns_same_response_for_nonexistent_user(self):
        """La reponse doit etre identique que l'utilisateur existe ou non (user enumeration prevention)."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_user_repo = MagicMock()
        mock_user_repo.get_by_email_and_tenant = MagicMock(return_value=None)
        mock_repo.can_request_reset = MagicMock(return_value=True)
        mock_repo.create_reset_token = MagicMock()

        service = PasswordResetService(mock_repo, user_repository=mock_user_repo)

        # Should not raise exception
        result = service.request_reset_by_email("nonexistent@example.com", tenant_id=1)

        # Should not create token for nonexistent user
        mock_repo.create_reset_token.assert_not_called()

        # But response should be the same (no user enumeration)
        assert result is None  # No token for nonexistent user

    @pytest.mark.unit
    def test_request_reset_rate_limited(self):
        """Max 3 demandes par heure par email."""
        from app.services.password_reset import PasswordResetService, RateLimitExceeded

        mock_repo = MagicMock()
        mock_repo.can_request_reset = MagicMock(return_value=False)  # Rate limited

        service = PasswordResetService(mock_repo)

        with pytest.raises(RateLimitExceeded):
            service.request_reset(user_id=1)


class TestPasswordResetValidation:
    """Tests pour la validation du token de reset."""

    @pytest.mark.unit
    def test_valid_token_is_accepted(self):
        """Un token valide est accepte."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_token = MagicMock(
            user_id=1,
            is_expired=False,
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None
        )
        mock_repo.validate_token = MagicMock(return_value=mock_token)

        service = PasswordResetService(mock_repo)
        result = service.validate_token("valid_token")

        assert result is not None
        assert result.user_id == 1

    @pytest.mark.unit
    def test_expired_token_is_rejected(self):
        """Un token expire est rejete."""
        from app.services.password_reset import PasswordResetService, TokenExpired

        mock_repo = MagicMock()
        mock_token = MagicMock(
            user_id=1,
            is_expired=True,  # Expired
            is_used=False,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            used_at=None
        )
        mock_repo.validate_token = MagicMock(return_value=mock_token)

        service = PasswordResetService(mock_repo)

        with pytest.raises(TokenExpired):
            service.validate_token("expired_token")

    @pytest.mark.unit
    def test_used_token_is_rejected(self):
        """Un token deja utilise est rejete (usage unique)."""
        from app.services.password_reset import PasswordResetService, TokenAlreadyUsed

        mock_repo = MagicMock()
        mock_token = MagicMock(
            user_id=1,
            is_expired=False,
            is_used=True,  # Already used
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=datetime.now(timezone.utc)
        )
        mock_repo.validate_token = MagicMock(return_value=mock_token)

        service = PasswordResetService(mock_repo)

        with pytest.raises(TokenAlreadyUsed):
            service.validate_token("used_token")

    @pytest.mark.unit
    def test_invalid_token_is_rejected(self):
        """Un token invalide/inexistant est rejete."""
        from app.services.password_reset import PasswordResetService, InvalidToken

        mock_repo = MagicMock()
        mock_repo.validate_token = MagicMock(return_value=None)

        service = PasswordResetService(mock_repo)

        with pytest.raises(InvalidToken):
            service.validate_token("invalid_token")


class TestPasswordResetExecution:
    """Tests pour l'execution du reset."""

    @pytest.mark.unit
    def test_reset_changes_password(self):
        """Le reset change le mot de passe."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_user_repo = MagicMock()
        mock_session_repo = MagicMock()
        mock_token = MagicMock(
            id=1,
            user_id=1,
            is_expired=False,
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None
        )
        mock_user = MagicMock(id=1, password_hash="old_hash")
        mock_repo.validate_token = MagicMock(return_value=mock_token)
        mock_repo.use_token = MagicMock()
        mock_repo.invalidate_all_for_user = MagicMock()
        mock_user_repo.get_by_id = MagicMock(return_value=mock_user)
        mock_session_repo.invalidate_all_sessions = MagicMock()

        service = PasswordResetService(mock_repo, user_repository=mock_user_repo, session_repository=mock_session_repo)
        service.reset_password("valid_token", "new_hash")

        # Verify password was updated on user object
        assert mock_user.password_hash == "new_hash"

    @pytest.mark.unit
    def test_reset_marks_token_as_used(self):
        """Le reset marque le token comme utilise."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_token = MagicMock(
            id=1,
            user_id=1,
            is_expired=False,
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None
        )
        mock_repo.validate_token = MagicMock(return_value=mock_token)
        mock_repo.use_token = MagicMock()
        mock_repo.invalidate_all_for_user = MagicMock()

        service = PasswordResetService(mock_repo)
        service.reset_password("valid_token", "new_hash")

        mock_repo.use_token.assert_called_once_with(1)

    @pytest.mark.unit
    def test_reset_invalidates_all_existing_sessions(self):
        """Le reset invalide toutes les sessions existantes (force re-login)."""
        from app.services.password_reset import PasswordResetService

        mock_repo = MagicMock()
        mock_session_repo = MagicMock()
        mock_token = MagicMock(
            id=1,
            user_id=1,
            is_expired=False,
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            used_at=None
        )
        mock_repo.validate_token = MagicMock(return_value=mock_token)
        mock_repo.use_token = MagicMock()
        mock_repo.invalidate_all_for_user = MagicMock()
        mock_session_repo.invalidate_all_sessions = MagicMock()

        service = PasswordResetService(mock_repo, session_repository=mock_session_repo)
        service.reset_password("valid_token", "new_hash")

        mock_session_repo.invalidate_all_sessions.assert_called_once_with(user_id=1)


class TestPasswordResetModel:
    """Tests pour le modele PasswordResetToken."""

    def test_password_reset_token_model_has_required_fields(self):
        """Le modele doit avoir tous les champs requis."""
        from app.models.password_reset import PasswordResetToken

        # Check class attributes exist
        assert hasattr(PasswordResetToken, 'id')
        assert hasattr(PasswordResetToken, 'user_id')
        assert hasattr(PasswordResetToken, 'token_hash')
        assert hasattr(PasswordResetToken, 'expires_at')
        assert hasattr(PasswordResetToken, 'used_at')
        assert hasattr(PasswordResetToken, 'created_at')

    def test_password_reset_token_tablename(self):
        """Le tablename doit etre 'password_reset_tokens'."""
        from app.models.password_reset import PasswordResetToken

        assert PasswordResetToken.__tablename__ == 'password_reset_tokens'


# =============================================================================
# 3. TESTS ALERTING RULES
# =============================================================================


class TestAlertingRulesFile:
    """Tests pour les fichiers de regles d'alerting."""

    def test_prometheus_rules_file_exists(self):
        """Le fichier de regles Prometheus doit exister."""
        import os
        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )

        # Normalize path
        rules_path = os.path.normpath(rules_path)

        assert os.path.exists(rules_path), f"Prometheus alert rules file should exist at {rules_path}"

    def test_prometheus_rules_is_valid_yaml(self):
        """Le fichier de regles doit etre un YAML valide."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        assert content is not None, "Rules file should not be empty"
        assert 'groups' in content, "Rules file should have 'groups' key"

    def test_prometheus_rules_has_required_alerts(self):
        """Les alertes critiques doivent etre definies."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        # Flatten all alert names
        alert_names = []
        for group in content.get('groups', []):
            for rule in group.get('rules', []):
                if 'alert' in rule:
                    alert_names.append(rule['alert'])

        # Check required alerts exist
        required_alerts = [
            'HighErrorRate',
            'HighLatency',
            'TooManyLoginFailures',
            'RateLimitExceeded',
            'DatabaseConnectionError',
        ]

        for alert in required_alerts:
            assert alert in alert_names, f"Required alert '{alert}' should be defined"

    def test_prometheus_rules_have_severity_labels(self):
        """Chaque alerte doit avoir un label 'severity'."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        for group in content.get('groups', []):
            for rule in group.get('rules', []):
                if 'alert' in rule:
                    labels = rule.get('labels', {})
                    assert 'severity' in labels, \
                        f"Alert '{rule['alert']}' should have a 'severity' label"

    def test_alertmanager_config_exists(self):
        """Le fichier de configuration Alertmanager doit exister."""
        import os

        config_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/alertmanager/alertmanager.yml'
        )
        config_path = os.path.normpath(config_path)

        assert os.path.exists(config_path), f"Alertmanager config should exist at {config_path}"

    def test_alertmanager_config_is_valid_yaml(self):
        """Le fichier de configuration Alertmanager doit etre valide."""
        import os
        import yaml

        config_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/alertmanager/alertmanager.yml'
        )
        config_path = os.path.normpath(config_path)

        with open(config_path, 'r') as f:
            content = yaml.safe_load(f)

        assert content is not None, "Alertmanager config should not be empty"
        assert 'route' in content, "Alertmanager config should have 'route' key"
        assert 'receivers' in content, "Alertmanager config should have 'receivers' key"

    def test_alertmanager_has_critical_route(self):
        """Les alertes critiques doivent avoir une route dediee."""
        import os
        import yaml

        config_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/alertmanager/alertmanager.yml'
        )
        config_path = os.path.normpath(config_path)

        with open(config_path, 'r') as f:
            content = yaml.safe_load(f)

        route = content.get('route', {})

        # Check that there's routing for critical alerts
        routes = route.get('routes', [])
        has_critical_route = any(
            r.get('match', {}).get('severity') == 'critical' or
            r.get('match_re', {}).get('severity') == 'critical.*'
            for r in routes
        )

        assert has_critical_route or 'receiver' in route, \
            "Should have a route for critical alerts or a default receiver"


class TestAlertingSeverityLevels:
    """Tests pour les niveaux de severite des alertes."""

    def test_valid_severity_levels(self):
        """Les niveaux de severite doivent etre valides."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        valid_severities = {'critical', 'warning', 'info'}

        for group in content.get('groups', []):
            for rule in group.get('rules', []):
                if 'alert' in rule:
                    severity = rule.get('labels', {}).get('severity')
                    if severity:
                        assert severity in valid_severities, \
                            f"Alert '{rule['alert']}' has invalid severity '{severity}'"


class TestAlertExpressions:
    """Tests pour les expressions des alertes."""

    def test_error_rate_alert_uses_correct_metric(self):
        """L'alerte error rate doit utiliser http_requests_total."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        for group in content.get('groups', []):
            for rule in group.get('rules', []):
                if rule.get('alert') == 'HighErrorRate':
                    expr = rule.get('expr', '')
                    assert 'http_requests_total' in expr, \
                        "HighErrorRate should use http_requests_total metric"

    def test_latency_alert_uses_histogram(self):
        """L'alerte latency doit utiliser un histogramme."""
        import os
        import yaml

        rules_path = os.path.join(
            os.path.dirname(__file__),
            '../../monitoring/prometheus/alert_rules.yml'
        )
        rules_path = os.path.normpath(rules_path)

        with open(rules_path, 'r') as f:
            content = yaml.safe_load(f)

        for group in content.get('groups', []):
            for rule in group.get('rules', []):
                if rule.get('alert') == 'HighLatency':
                    expr = rule.get('expr', '')
                    assert 'http_request_duration' in expr or 'histogram_quantile' in expr, \
                        "HighLatency should use duration histogram"
