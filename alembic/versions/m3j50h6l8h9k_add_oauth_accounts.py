"""add oauth_accounts table

Revision ID: m3j50h6l8h9k
Revises: l2i49g5k7g8j
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm3j50h6l8h9k'
down_revision: Union[str, None] = 'l2i49g5k7g8j'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create oauth_accounts table
    op.create_table(
        'oauth_accounts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('provider_user_id', sa.Text(), nullable=False),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', 'tenant_id', name='uq_oauth_provider_user_tenant'),
        comment='Comptes OAuth pour authentification sociale'
    )

    # Create indexes
    op.create_index('ix_oauth_accounts_user_id', 'oauth_accounts', ['user_id'])
    op.create_index('ix_oauth_accounts_tenant_id', 'oauth_accounts', ['tenant_id'])
    op.create_index('ix_oauth_accounts_provider', 'oauth_accounts', ['provider'])
    op.create_index('ix_oauth_accounts_provider_user', 'oauth_accounts', ['provider', 'provider_user_id'])


def downgrade() -> None:
    op.drop_index('ix_oauth_accounts_provider_user', table_name='oauth_accounts')
    op.drop_index('ix_oauth_accounts_provider', table_name='oauth_accounts')
    op.drop_index('ix_oauth_accounts_tenant_id', table_name='oauth_accounts')
    op.drop_index('ix_oauth_accounts_user_id', table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
