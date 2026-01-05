"""Add RLS policies and password_reset_tokens table

Revision ID: f6b83c9d0e1a
Revises: e5a72b8c9d0f
Create Date: 2025-12-28 14:30:00.000000

This migration:
1. Creates password_reset_tokens table
2. Enables Row Level Security on tenant-scoped tables
3. Creates RLS policies for tenant isolation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b83c9d0e1a'
down_revision: Union[str, None] = 'e5a72b8c9d0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # 0. Add missing last_totp_window column to mfa_secrets (pre-existing issue)
    # =========================================================================
    op.add_column(
        'mfa_secrets',
        sa.Column('last_totp_window', sa.BigInteger(), nullable=True)
    )

    # =========================================================================
    # 1. Create password_reset_tokens table
    # =========================================================================
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )

    # Index for token lookup by hash
    op.create_index(
        'ix_password_reset_tokens_token_hash',
        'password_reset_tokens',
        ['token_hash']
    )

    # Index for cleanup of expired tokens
    op.create_index(
        'ix_password_reset_tokens_expires_at',
        'password_reset_tokens',
        ['expires_at']
    )

    # Index for user's recent requests (rate limiting)
    op.create_index(
        'ix_password_reset_tokens_user_created',
        'password_reset_tokens',
        ['user_id', 'created_at']
    )

    # =========================================================================
    # 2. Enable Row Level Security on tenant-scoped tables
    # =========================================================================

    # Enable RLS on users table
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")

    # Enable RLS on sessions table
    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")

    # Enable RLS on refresh_tokens table (via session relationship)
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")

    # Enable RLS on password_reset_tokens (via user relationship)
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")

    # =========================================================================
    # 3. Create RLS policies for tenant isolation
    # =========================================================================

    # Policy for users table - tenant isolation
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        FOR ALL
        USING (
            tenant_id = COALESCE(
                current_setting('app.current_tenant_id', true)::bigint,
                tenant_id
            )
        )
    """)

    # Policy for sessions table - tenant isolation
    op.execute("""
        CREATE POLICY tenant_isolation ON sessions
        FOR ALL
        USING (
            tenant_id = COALESCE(
                current_setting('app.current_tenant_id', true)::bigint,
                tenant_id
            )
        )
    """)

    # Policy for refresh_tokens - via session's tenant
    op.execute("""
        CREATE POLICY tenant_isolation ON refresh_tokens
        FOR ALL
        USING (
            session_id IS NULL OR
            session_id IN (
                SELECT id FROM sessions
                WHERE tenant_id = COALESCE(
                    current_setting('app.current_tenant_id', true)::bigint,
                    tenant_id
                )
            )
        )
    """)

    # Policy for password_reset_tokens - via user's tenant
    op.execute("""
        CREATE POLICY tenant_isolation ON password_reset_tokens
        FOR ALL
        USING (
            user_id IN (
                SELECT id FROM users
                WHERE tenant_id = COALESCE(
                    current_setting('app.current_tenant_id', true)::bigint,
                    tenant_id
                )
            )
        )
    """)

    # =========================================================================
    # 4. Grant permissions to application role
    # =========================================================================

    # Note: In production, you should create a dedicated app role
    # and grant specific permissions. For now, we use the default role.
    # Example:
    # op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON password_reset_tokens TO app_role")


def downgrade() -> None:
    # =========================================================================
    # 1. Drop RLS policies
    # =========================================================================
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON password_reset_tokens")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON refresh_tokens")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sessions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")

    # =========================================================================
    # 2. Disable Row Level Security
    # =========================================================================
    op.execute("ALTER TABLE password_reset_tokens DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    # =========================================================================
    # 3. Drop password_reset_tokens table
    # =========================================================================
    op.drop_index('ix_password_reset_tokens_user_created')
    op.drop_index('ix_password_reset_tokens_expires_at')
    op.drop_index('ix_password_reset_tokens_token_hash')
    op.drop_table('password_reset_tokens')

    # =========================================================================
    # 4. Drop last_totp_window column from mfa_secrets
    # =========================================================================
    op.drop_column('mfa_secrets', 'last_totp_window')
