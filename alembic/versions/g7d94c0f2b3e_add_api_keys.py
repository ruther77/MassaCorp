"""Add api_keys table for M2M authentication

Revision ID: g7d94c0f2b3e
Revises: f6b83c9d0e1a
Create Date: 2025-12-28 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7d94c0f2b3e'
down_revision: Union[str, None] = 'f6b83c9d0e1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_keys table with RLS."""

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('key_hash', sa.Text(), nullable=False),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', NOW())"), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_key_prefix', 'api_keys', ['key_prefix'])

    # Enable RLS on api_keys table
    op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")

    # Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY tenant_isolation ON api_keys
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::BIGINT)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', TRUE)::BIGINT)
    """)


def downgrade() -> None:
    """Drop api_keys table."""

    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON api_keys")

    # Disable RLS
    op.execute("ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY")

    # Drop indexes
    op.drop_index('ix_api_keys_key_prefix', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_index('ix_api_keys_tenant_id', table_name='api_keys')

    # Drop table
    op.drop_table('api_keys')
