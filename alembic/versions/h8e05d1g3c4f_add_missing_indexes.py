"""Add missing indexes for performance

Revision ID: h8e05d1g3c4f
Revises: g7d94c0f2b3e
Create Date: 2025-12-28 17:00:00.000000

Adds indexes on:
- mfa_recovery_codes.tenant_id
- user_identities.email
- Various created_at columns for time-based queries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h8e05d1g3c4f'
down_revision: Union[str, None] = 'g7d94c0f2b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing indexes."""

    # Index on mfa_recovery_codes.tenant_id (critical for RLS)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mfa_recovery_codes_tenant_id
        ON mfa_recovery_codes(tenant_id)
    """)

    # Index on user_identities.email for SSO lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_identities_email
        ON user_identities(email)
    """)

    # Composite index for session lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sessions_user_tenant_active
        ON sessions(user_id, tenant_id)
        WHERE revoked_at IS NULL
    """)

    # Composite index for refresh token lookup (uses used_at, not revoked_at)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_refresh_tokens_session_active
        ON refresh_tokens(session_id)
        WHERE used_at IS NULL
    """)

    # Index sur login_attempts pour les requetes anti-bruteforce
    # Note: utilise attempted_at (pas created_at) et ip (pas ip_address)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_login_attempts_identifier_time
        ON login_attempts(identifier, attempted_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_login_attempts_ip_time
        ON login_attempts(ip, attempted_at DESC)
    """)

    # Add audit_log immutability trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'Audit logs are immutable - UPDATE not allowed';
            ELSIF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Audit logs are immutable - DELETE not allowed';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
    """)

    # Add check constraint on sessions
    op.execute("""
        ALTER TABLE sessions
        ADD CONSTRAINT chk_sessions_revoked_after_created
        CHECK (revoked_at IS NULL OR revoked_at >= created_at)
    """)


def downgrade() -> None:
    """Remove indexes and triggers."""

    # Remove check constraint
    op.execute("""
        ALTER TABLE sessions
        DROP CONSTRAINT IF EXISTS chk_sessions_revoked_after_created
    """)

    # Remove trigger
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification()")

    # Remove indexes
    op.execute("DROP INDEX IF EXISTS ix_login_attempts_ip_time")
    op.execute("DROP INDEX IF EXISTS ix_login_attempts_identifier_time")
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_session_active")
    op.execute("DROP INDEX IF EXISTS ix_sessions_user_tenant_active")
    op.execute("DROP INDEX IF EXISTS ix_user_identities_email")
    op.execute("DROP INDEX IF EXISTS ix_mfa_recovery_codes_tenant_id")
