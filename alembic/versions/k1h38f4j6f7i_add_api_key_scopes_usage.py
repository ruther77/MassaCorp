"""Add API Key scopes and usage logging

Revision ID: k1h38f4j6f7i
Revises: j0g27e3i5e6h_add_session_absolute_expiry
Create Date: 2025-01-27

Ajoute:
- Colonne scopes (JSONB) sur api_keys pour le principe de moindre privilege
- Table api_key_usage pour le logging d'utilisation (audit)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'k1h38f4j6f7i'
down_revision = 'j0g27e3i5e6h'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajouter colonne scopes sur api_keys
    op.add_column(
        'api_keys',
        sa.Column(
            'scopes',
            JSONB,
            nullable=True,
            comment='Scopes autorises - null = tous les droits (legacy)'
        )
    )

    # Creer table api_key_usage pour audit
    op.create_table(
        'api_key_usage',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column(
            'api_key_id',
            sa.BigInteger(),
            sa.ForeignKey('api_keys.id', ondelete='CASCADE'),
            nullable=False,
            index=True
        ),
        sa.Column(
            'tenant_id',
            sa.BigInteger(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True
        ),
        sa.Column(
            'used_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True
        ),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('method', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('response_status', sa.BigInteger(), nullable=True),
        sa.Column('response_time_ms', sa.BigInteger(), nullable=True),
    )

    # Index composite pour recherche par key + periode
    op.create_index(
        'ix_api_key_usage_key_used_at',
        'api_key_usage',
        ['api_key_id', 'used_at']
    )


def downgrade() -> None:
    op.drop_index('ix_api_key_usage_key_used_at', table_name='api_key_usage')
    op.drop_table('api_key_usage')
    op.drop_column('api_keys', 'scopes')
