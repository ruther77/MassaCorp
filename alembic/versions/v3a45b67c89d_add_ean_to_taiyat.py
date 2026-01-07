"""Add EAN and dim_produit_id to TAIYAT tables

Revision ID: v3a45b67c89d
Revises: v2c39p5u7q9s
Create Date: 2026-01-07 02:00:00.000000

Adds:
- ean column to taiyat_ligne (nullable, for manual entry)
- ean column to taiyat_produit_agregat
- dim_produit_id column to taiyat_produit_agregat (FK to dim_produit)
- Indexes on new columns
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'v3a45b67c89d'
down_revision: Union[str, None] = 'v2c39p5u7q9s'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add EAN to taiyat_ligne
    op.add_column(
        'taiyat_ligne',
        sa.Column('ean', sa.String(20), nullable=True, comment='Code EAN (peut être renseigné manuellement)'),
        schema='dwh'
    )
    op.create_index(
        'ix_taiyat_ligne_ean',
        'taiyat_ligne',
        ['tenant_id', 'ean'],
        schema='dwh'
    )

    # Add EAN and dim_produit_id to taiyat_produit_agregat
    op.add_column(
        'taiyat_produit_agregat',
        sa.Column('ean', sa.String(20), nullable=True, comment='Code EAN (renseigné manuellement)'),
        schema='dwh'
    )
    op.add_column(
        'taiyat_produit_agregat',
        sa.Column('dim_produit_id', sa.BigInteger(), nullable=True, comment='FK vers dwh.dim_produit'),
        schema='dwh'
    )
    op.create_index(
        'ix_taiyat_produit_ean',
        'taiyat_produit_agregat',
        ['tenant_id', 'ean'],
        schema='dwh'
    )
    op.create_index(
        'ix_taiyat_produit_dim_produit',
        'taiyat_produit_agregat',
        ['dim_produit_id'],
        schema='dwh'
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_taiyat_produit_dim_produit', table_name='taiyat_produit_agregat', schema='dwh')
    op.drop_index('ix_taiyat_produit_ean', table_name='taiyat_produit_agregat', schema='dwh')
    op.drop_index('ix_taiyat_ligne_ean', table_name='taiyat_ligne', schema='dwh')

    # Remove columns
    op.drop_column('taiyat_produit_agregat', 'dim_produit_id', schema='dwh')
    op.drop_column('taiyat_produit_agregat', 'ean', schema='dwh')
    op.drop_column('taiyat_ligne', 'ean', schema='dwh')
