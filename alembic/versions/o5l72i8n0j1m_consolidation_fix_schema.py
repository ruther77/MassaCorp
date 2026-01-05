"""Consolidation migration - Fix schema divergences

Revision ID: o5l72i8n0j1m
Revises: n4k61h7m9i0l
Create Date: 2026-01-05

This migration consolidates and fixes all schema divergences:

1. api_keys table:
   - Add missing key_prefix column
   - Add missing created_by_user_id column
   - Convert scopes from ARRAY to JSONB

2. api_key_usage table:
   - Rename ip to ip_address
   - Add missing columns: user_agent, response_status, response_time_ms
   - Fix nullable constraints on endpoint and method

3. audit_log trigger:
   - Create unified immutability trigger

4. RLS policies:
   - Fix insecure COALESCE fallback that bypasses tenant isolation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'o5l72i8n0j1m'
down_revision = 'n4k61h7m9i0l'
branch_labels = None
depends_on = None


# Tables that need RLS policy fix
RLS_TABLES_TO_FIX = [
    'api_key_roles',
    'api_key_usage',
    'api_keys',
    'audit_log',
    'feature_flags_tenant',
    'identity_providers',
    'mfa_recovery_codes',
    'mfa_secrets',
    'oauth_accounts',
    'roles',
    'sso_sessions',
    'user_identities',
    'user_roles',
    'users',
    'sessions',
]


def upgrade() -> None:
    """Apply all schema fixes."""

    # ========================================
    # 1. FIX api_keys TABLE
    # ========================================

    # Add key_prefix column if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_keys' AND column_name = 'key_prefix'
            ) THEN
                ALTER TABLE api_keys ADD COLUMN key_prefix TEXT;
                -- Set default value for existing rows
                UPDATE api_keys SET key_prefix = 'mc_' || LEFT(key_hash, 8) WHERE key_prefix IS NULL;
                ALTER TABLE api_keys ALTER COLUMN key_prefix SET NOT NULL;
            END IF;
        END $$;
    """)

    # Add created_by_user_id column if not exists
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_keys' AND column_name = 'created_by_user_id'
            ) THEN
                ALTER TABLE api_keys ADD COLUMN created_by_user_id BIGINT;
                ALTER TABLE api_keys ADD CONSTRAINT fk_api_keys_created_by
                    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)

    # Convert scopes from ARRAY to JSONB if needed
    op.execute("""
        DO $$
        DECLARE
            col_type TEXT;
        BEGIN
            SELECT udt_name INTO col_type
            FROM information_schema.columns
            WHERE table_name = 'api_keys' AND column_name = 'scopes';

            IF col_type = '_text' THEN
                -- Convert ARRAY to JSONB
                ALTER TABLE api_keys ADD COLUMN scopes_new JSONB;
                UPDATE api_keys SET scopes_new = to_jsonb(scopes) WHERE scopes IS NOT NULL;
                ALTER TABLE api_keys DROP COLUMN scopes;
                ALTER TABLE api_keys RENAME COLUMN scopes_new TO scopes;
            END IF;
        END $$;
    """)

    # ========================================
    # 2. FIX api_key_usage TABLE
    # ========================================

    # Rename ip to ip_address if needed
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_key_usage' AND column_name = 'ip'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_key_usage' AND column_name = 'ip_address'
            ) THEN
                ALTER TABLE api_key_usage RENAME COLUMN ip TO ip_address;
            END IF;
        END $$;
    """)

    # Add missing columns to api_key_usage
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_key_usage' AND column_name = 'user_agent'
            ) THEN
                ALTER TABLE api_key_usage ADD COLUMN user_agent TEXT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_key_usage' AND column_name = 'response_status'
            ) THEN
                ALTER TABLE api_key_usage ADD COLUMN response_status BIGINT;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'api_key_usage' AND column_name = 'response_time_ms'
            ) THEN
                ALTER TABLE api_key_usage ADD COLUMN response_time_ms BIGINT;
            END IF;
        END $$;
    """)

    # Fix nullable constraints - set defaults first for existing NULL values
    op.execute("""
        UPDATE api_key_usage SET endpoint = 'unknown' WHERE endpoint IS NULL;
        UPDATE api_key_usage SET method = 'GET' WHERE method IS NULL;
    """)

    op.execute("""
        ALTER TABLE api_key_usage ALTER COLUMN endpoint SET NOT NULL;
        ALTER TABLE api_key_usage ALTER COLUMN method SET NOT NULL;
    """)

    # ========================================
    # 3. FIX audit_log IMMUTABILITY TRIGGER
    # ========================================

    # Drop any existing triggers and functions
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable_trigger();")

    # Create unified trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable_fn()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is immutable: % operation not allowed', TG_OP
                USING ERRCODE = 'restrict_violation';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create the trigger
    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_immutable_fn();
    """)

    # ========================================
    # 4. FIX RLS POLICIES (SECURITY CRITICAL)
    # ========================================

    # Drop existing insecure policies and create secure ones
    for table in RLS_TABLES_TO_FIX:
        # Drop existing policy
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")

        # Create secure policy - NO fallback to tenant_id!
        # If app.current_tenant_id is not set, no rows are visible
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            );
        """)

    # Fix refresh_tokens policy (joins to sessions)
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON refresh_tokens;")
    op.execute("""
        CREATE POLICY tenant_isolation ON refresh_tokens
        FOR ALL
        USING (
            session_id IS NULL
            OR session_id IN (
                SELECT id FROM sessions
                WHERE tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            )
        );
    """)

    # Fix password_reset_tokens policy (joins to users)
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON password_reset_tokens;")
    op.execute("""
        CREATE POLICY tenant_isolation ON password_reset_tokens
        FOR ALL
        USING (
            user_id IN (
                SELECT id FROM users
                WHERE tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            )
        );
    """)

    print("Consolidation migration applied successfully")


def downgrade() -> None:
    """Revert changes - restore previous (insecure) state."""

    # Note: This downgrade restores the INSECURE policies.
    # Only use this if you need to rollback for debugging.

    # Revert RLS policies to insecure versions
    for table in RLS_TABLES_TO_FIX:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            USING (
                tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant_id', true), '')::bigint,
                    tenant_id
                )
            );
        """)

    # Revert refresh_tokens policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON refresh_tokens;")
    op.execute("""
        CREATE POLICY tenant_isolation ON refresh_tokens
        FOR ALL
        USING (
            session_id IS NULL
            OR session_id IN (
                SELECT id FROM sessions
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant_id', true), '')::bigint,
                    tenant_id
                )
            )
        );
    """)

    # Revert password_reset_tokens policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON password_reset_tokens;")
    op.execute("""
        CREATE POLICY tenant_isolation ON password_reset_tokens
        FOR ALL
        USING (
            user_id IN (
                SELECT id FROM users
                WHERE tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant_id', true), '')::bigint,
                    tenant_id
                )
            )
        );
    """)

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable_fn();")

    # Note: Column changes are not reverted to avoid data loss
