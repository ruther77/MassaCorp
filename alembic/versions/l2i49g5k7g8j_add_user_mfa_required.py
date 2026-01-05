"""Add mfa_required field to users

Revision ID: l2i49g5k7g8j
Revises: k1h38f4j6f7i
Create Date: 2025-01-27

Ajoute:
- Colonne mfa_required sur users pour forcer l'activation MFA apres compromission
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l2i49g5k7g8j'
down_revision = 'k1h38f4j6f7i'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajouter colonne mfa_required sur users avec valeur par defaut
    op.add_column(
        'users',
        sa.Column(
            'mfa_required',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='Force MFA activation after suspected compromise'
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'mfa_required')
