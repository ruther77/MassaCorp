"""add session absolute_expiry

Revision ID: j0g27e3i5e6h
Revises: i9f16e2h4d5g
Create Date: 2024-12-28

Ajoute la colonne absolute_expiry a la table sessions.
Cette colonne definit une expiration absolue de 30 jours qui ne peut
pas etre etendue par rotation de tokens.

SECURITE:
- Empeche les sessions de durer indefiniment avec des rotations successives
- Force une re-authentification apres 30 jours maximum
- Les sessions existantes auront NULL (compatibilite), mais les nouvelles
  sessions auront cette valeur definie automatiquement
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP


# revision identifiers, used by Alembic.
revision = 'j0g27e3i5e6h'
down_revision = 'i9f16e2h4d5g'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Ajoute la colonne absolute_expiry a la table sessions."""
    # Ajouter la colonne absolute_expiry
    op.add_column(
        'sessions',
        sa.Column(
            'absolute_expiry',
            TIMESTAMP(timezone=True),
            nullable=True,  # Nullable pour compatibilite avec sessions existantes
            comment='Expiration absolue de la session (30 jours max apres creation)'
        )
    )

    # Ajouter un index pour les requetes de cleanup
    op.create_index(
        'ix_sessions_absolute_expiry',
        'sessions',
        ['absolute_expiry'],
        unique=False
    )

    # Mettre a jour les sessions existantes avec une expiration basee sur created_at
    # Les sessions existantes ont 30 jours a partir de leur creation
    op.execute("""
        UPDATE sessions
        SET absolute_expiry = created_at + INTERVAL '30 days'
        WHERE absolute_expiry IS NULL
    """)


def downgrade() -> None:
    """Supprime la colonne absolute_expiry."""
    op.drop_index('ix_sessions_absolute_expiry', table_name='sessions')
    op.drop_column('sessions', 'absolute_expiry')
