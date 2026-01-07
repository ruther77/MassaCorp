"""Add EUROCIEL catalogue table

Revision ID: x5e61r7w9s1u
Revises: w4d50q6v8r0t
Create Date: 2026-01-07

Table: dwh.eurociel_catalogue_produit
- Référence produit du catalogue EUROCIEL
- Données master (toutes références disponibles)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x5e61r7w9s1u'
down_revision = 'w4d50q6v8r0t'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table catalogue produits EUROCIEL
    op.create_table(
        'eurociel_catalogue_produit',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),

        # Identification
        sa.Column('reference', sa.String(20), nullable=False, comment='Code référence EUROCIEL (ex: 10 126)'),
        sa.Column('designation', sa.String(255), nullable=False, comment='Nom du produit'),
        sa.Column('designation_clean', sa.String(255), nullable=False, comment='Nom normalisé (uppercase)'),

        # Catégorisation
        sa.Column('categorie', sa.String(100), nullable=False, comment='Catégorie catalogue'),
        sa.Column('sous_categorie', sa.String(100), nullable=True, comment='Sous-catégorie'),

        # Caractéristiques
        sa.Column('taille', sa.String(50), nullable=True, comment='Calibre/taille (ex: 500/800)'),
        sa.Column('conditionnement', sa.String(50), nullable=True, comment='Conditionnement (ex: 10KG)'),
        sa.Column('poids_kg', sa.Numeric(10, 2), nullable=True, comment='Poids conditionnement en kg'),
        sa.Column('origine', sa.String(50), nullable=True, comment='Pays origine'),

        # Métadonnées
        sa.Column('page_source', sa.BigInteger(), nullable=True, comment='Page dans catalogue PDF'),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default='true', comment='Produit actif'),

        # Lien produit agrégé
        sa.Column('produit_agregat_id', sa.BigInteger(), nullable=True, comment='Lien vers produit si acheté'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['produit_agregat_id'], ['dwh.eurociel_produit_agregat.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('tenant_id', 'reference', name='uq_eurociel_catalogue_ref'),

        schema='dwh'
    )

    # Index
    op.create_index('ix_eurociel_cat_ref', 'eurociel_catalogue_produit', ['tenant_id', 'reference'], schema='dwh')
    op.create_index('ix_eurociel_cat_designation', 'eurociel_catalogue_produit', ['tenant_id', 'designation'], schema='dwh')
    op.create_index('ix_eurociel_cat_categorie', 'eurociel_catalogue_produit', ['tenant_id', 'categorie'], schema='dwh')
    op.create_index('ix_eurociel_cat_origine', 'eurociel_catalogue_produit', ['tenant_id', 'origine'], schema='dwh')


def downgrade() -> None:
    op.drop_index('ix_eurociel_cat_origine', table_name='eurociel_catalogue_produit', schema='dwh')
    op.drop_index('ix_eurociel_cat_categorie', table_name='eurociel_catalogue_produit', schema='dwh')
    op.drop_index('ix_eurociel_cat_designation', table_name='eurociel_catalogue_produit', schema='dwh')
    op.drop_index('ix_eurociel_cat_ref', table_name='eurociel_catalogue_produit', schema='dwh')
    op.drop_table('eurociel_catalogue_produit', schema='dwh')
