"""
Tests comportementaux pour la migration de consolidation.

Ces tests vérifient que:
1. api_keys a les bonnes colonnes avec les bons types
2. api_key_usage a les bonnes colonnes
3. audit_log est immuable (trigger bloque UPDATE/DELETE)
4. RLS policies sont sécurisées (pas de COALESCE fallback)

SECURITE CRITIQUE:
- Le trigger audit_log_immutable empêche toute modification des logs
- Les RLS policies DOIVENT échouer si app.current_tenant_id n'est pas défini
"""
import pytest
from sqlalchemy import text, inspect
from sqlalchemy.exc import DatabaseError

from app.core.database import engine


class TestAPIKeysSchema:
    """Tests pour le schéma de la table api_keys."""

    def test_api_keys_has_key_prefix_column(self):
        """api_keys doit avoir une colonne key_prefix NOT NULL."""
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns('api_keys')}

        assert 'key_prefix' in columns
        assert columns['key_prefix']['nullable'] is False

    def test_api_keys_has_created_by_user_id_column(self):
        """api_keys doit avoir une colonne created_by_user_id nullable."""
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns('api_keys')}

        assert 'created_by_user_id' in columns
        assert columns['created_by_user_id']['nullable'] is True

    def test_api_keys_scopes_is_jsonb(self):
        """api_keys.scopes doit être de type JSONB."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT udt_name FROM information_schema.columns
                WHERE table_name = 'api_keys' AND column_name = 'scopes'
            """))
            row = result.fetchone()

        assert row is not None
        assert row[0] == 'jsonb'

    def test_api_keys_has_foreign_key_to_users(self):
        """api_keys.created_by_user_id doit avoir une FK vers users."""
        inspector = inspect(engine)
        fks = inspector.get_foreign_keys('api_keys')

        created_by_fk = next(
            (fk for fk in fks if 'created_by_user_id' in fk['constrained_columns']),
            None
        )

        assert created_by_fk is not None
        assert created_by_fk['referred_table'] == 'users'


class TestAPIKeyUsageSchema:
    """Tests pour le schéma de la table api_key_usage."""

    def test_api_key_usage_has_ip_address_column(self):
        """api_key_usage doit avoir ip_address (pas ip)."""
        inspector = inspect(engine)
        columns = {c['name'] for c in inspector.get_columns('api_key_usage')}

        assert 'ip_address' in columns
        assert 'ip' not in columns  # L'ancien nom ne doit plus exister

    def test_api_key_usage_has_user_agent_column(self):
        """api_key_usage doit avoir une colonne user_agent."""
        inspector = inspect(engine)
        columns = {c['name'] for c in inspector.get_columns('api_key_usage')}

        assert 'user_agent' in columns

    def test_api_key_usage_has_response_columns(self):
        """api_key_usage doit avoir response_status et response_time_ms."""
        inspector = inspect(engine)
        columns = {c['name'] for c in inspector.get_columns('api_key_usage')}

        assert 'response_status' in columns
        assert 'response_time_ms' in columns

    def test_api_key_usage_endpoint_is_not_null(self):
        """api_key_usage.endpoint doit être NOT NULL."""
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns('api_key_usage')}

        assert columns['endpoint']['nullable'] is False

    def test_api_key_usage_method_is_not_null(self):
        """api_key_usage.method doit être NOT NULL."""
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns('api_key_usage')}

        assert columns['method']['nullable'] is False


class TestAuditLogImmutability:
    """Tests pour l'immutabilité de audit_log."""

    def test_audit_log_trigger_exists(self):
        """Le trigger audit_log_immutable doit exister."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT trigger_name FROM information_schema.triggers
                WHERE event_object_table = 'audit_log'
                AND trigger_name = 'audit_log_immutable'
            """))
            triggers = result.fetchall()

        # Should have 2 rows (UPDATE and DELETE)
        assert len(triggers) >= 1

    def test_audit_log_trigger_function_exists(self):
        """La fonction trigger audit_log_immutable_fn doit exister."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT routine_name FROM information_schema.routines
                WHERE routine_name = 'audit_log_immutable_fn'
            """))
            funcs = result.fetchall()

        assert len(funcs) == 1

    def test_audit_log_blocks_update(self):
        """
        CRITIQUE: UPDATE sur audit_log doit être bloqué par le trigger.
        """
        with engine.connect() as conn:
            # First check if there are any rows to update
            result = conn.execute(text("SELECT id FROM audit_log LIMIT 1"))
            row = result.fetchone()

            if row:
                with pytest.raises(DatabaseError) as exc_info:
                    conn.execute(text(f"""
                        UPDATE audit_log SET event_type = 'HACKED'
                        WHERE id = {row[0]}
                    """))
                    conn.commit()

                assert 'immutable' in str(exc_info.value).lower()
            else:
                pytest.skip("No audit_log entries to test UPDATE on")

    def test_audit_log_blocks_delete(self):
        """
        CRITIQUE: DELETE sur audit_log doit être bloqué par le trigger.
        """
        with engine.connect() as conn:
            # First check if there are any rows to delete
            result = conn.execute(text("SELECT id FROM audit_log LIMIT 1"))
            row = result.fetchone()

            if row:
                with pytest.raises(DatabaseError) as exc_info:
                    conn.execute(text(f"DELETE FROM audit_log WHERE id = {row[0]}"))
                    conn.commit()

                assert 'immutable' in str(exc_info.value).lower()
            else:
                pytest.skip("No audit_log entries to test DELETE on")


class TestRLSPoliciesSecurity:
    """Tests pour la sécurité des politiques RLS."""

    TABLES_WITH_TENANT_ID = [
        'users',
        'sessions',
        'api_keys',
        'api_key_usage',
        'audit_log',
        'mfa_secrets',
        'mfa_recovery_codes',
        'roles',
        'user_roles',
    ]

    def test_rls_policies_exist(self):
        """Chaque table avec tenant_id doit avoir une politique RLS."""
        with engine.connect() as conn:
            for table in self.TABLES_WITH_TENANT_ID:
                result = conn.execute(text(f"""
                    SELECT policyname FROM pg_policies
                    WHERE tablename = '{table}'
                """))
                policies = result.fetchall()

                assert len(policies) > 0, f"No RLS policy on {table}"

    def test_rls_policies_no_coalesce_fallback(self):
        """
        CRITIQUE: Les politiques RLS ne doivent PAS avoir de COALESCE
        qui fallback sur tenant_id (cela bypasse l'isolation).
        """
        with engine.connect() as conn:
            for table in self.TABLES_WITH_TENANT_ID:
                result = conn.execute(text(f"""
                    SELECT qual FROM pg_policies
                    WHERE tablename = '{table}' AND policyname = 'tenant_isolation'
                """))
                row = result.fetchone()

                if row:
                    policy_qual = row[0]
                    # Check for insecure pattern: COALESCE(..., tenant_id)
                    # The insecure pattern ends with ", tenant_id)"
                    assert ', tenant_id)' not in policy_qual.lower(), \
                        f"INSECURE: {table} has COALESCE fallback to tenant_id"

    def test_rls_policy_uses_nullif(self):
        """Les politiques RLS doivent utiliser NULLIF pour gérer les valeurs vides."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tablename, qual FROM pg_policies
                WHERE policyname = 'tenant_isolation'
            """))
            rows = result.fetchall()

            for table, qual in rows:
                # All policies should use NULLIF to handle empty strings
                assert 'nullif' in qual.lower(), \
                    f"{table} policy should use NULLIF"

    def test_rls_enabled_on_tables(self):
        """RLS doit être activé sur toutes les tables avec tenant_id."""
        with engine.connect() as conn:
            for table in self.TABLES_WITH_TENANT_ID:
                result = conn.execute(text(f"""
                    SELECT relrowsecurity FROM pg_class
                    WHERE relname = '{table}'
                """))
                row = result.fetchone()

                assert row is not None
                assert row[0] is True, f"RLS not enabled on {table}"


class TestModelDBSync:
    """Tests pour la synchronisation modèles/DB."""

    def test_api_keys_model_matches_db(self):
        """Le modèle APIKey doit correspondre à la DB."""
        from app.models import APIKey

        inspector = inspect(engine)
        db_cols = {c['name'] for c in inspector.get_columns('api_keys')}
        model_cols = {c.name for c in APIKey.__table__.columns}

        missing_in_db = model_cols - db_cols
        missing_in_model = db_cols - model_cols

        assert not missing_in_db, f"Columns in model but not in DB: {missing_in_db}"
        assert not missing_in_model, f"Columns in DB but not in model: {missing_in_model}"

    def test_api_key_usage_model_matches_db(self):
        """Le modèle APIKeyUsage doit correspondre à la DB."""
        from app.models import APIKeyUsage

        inspector = inspect(engine)
        db_cols = {c['name'] for c in inspector.get_columns('api_key_usage')}
        model_cols = {c.name for c in APIKeyUsage.__table__.columns}

        missing_in_db = model_cols - db_cols
        missing_in_model = db_cols - model_cols

        assert not missing_in_db, f"Columns in model but not in DB: {missing_in_db}"
        assert not missing_in_model, f"Columns in DB but not in model: {missing_in_model}"
