"""Add fournisseur column to restaurant_epicerie_links

Revision ID: y6f72s8x0t2v
Revises: x5e61r7w9s1u
Create Date: 2026-01-07

Ajout de la colonne fournisseur pour supporter METRO, TAIYAT, EUROCIEL.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y6f72s8x0t2v'
down_revision = 'x5e61r7w9s1u'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ajouter la colonne fournisseur avec valeur par defaut METRO
    op.add_column(
        'restaurant_epicerie_links',
        sa.Column('fournisseur', sa.String(50), nullable=False, server_default='METRO')
    )


def downgrade() -> None:
    op.drop_column('restaurant_epicerie_links', 'fournisseur')
