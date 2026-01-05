"""Add updated_at to sessions table

Revision ID: e5a72b8c9d0f
Revises: d4cf1a3e5f7c
Create Date: 2025-12-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a72b8c9d0f'
down_revision: Union[str, None] = 'd4cf1a3e5f7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add updated_at column to sessions table
    op.add_column(
        'sessions',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False
        )
    )


def downgrade() -> None:
    op.drop_column('sessions', 'updated_at')
