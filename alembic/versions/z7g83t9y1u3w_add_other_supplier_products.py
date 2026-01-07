"""Add OTHER supplier products table

Revision ID: z7g83t9y1u3w
Revises: y6f72s8x0t2v
Create Date: 2026-01-07

Table pour les produits achetés chez d'autres fournisseurs
(cash & carry africain, grossistes spécialisés, etc.)
"""
from alembic import op
import sqlalchemy as sa


revision = 'z7g83t9y1u3w'
down_revision = 'y6f72s8x0t2v'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'other_produit_agregat',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),

        # Identification
        sa.Column('designation', sa.String(255), nullable=False),
        sa.Column('designation_clean', sa.String(255), nullable=False),

        # Catégorisation
        sa.Column('famille', sa.String(50), nullable=True),
        sa.Column('categorie', sa.String(50), nullable=True),
        sa.Column('sous_categorie', sa.String(50), nullable=True),

        # Conditionnement
        sa.Column('colisage', sa.Integer(), nullable=True, comment='Nb unités par colis'),
        sa.Column('unite', sa.String(10), nullable=True, comment='U, KG, L'),
        sa.Column('contenance', sa.String(50), nullable=True, comment='Ex: 33CL, 75CL, 1KG'),

        # Prix
        sa.Column('prix_unitaire', sa.Numeric(10, 2), nullable=True, comment='Prix unitaire en centimes'),
        sa.Column('prix_colis', sa.Numeric(10, 2), nullable=True, comment='Prix colis en centimes'),

        # Fournisseur
        sa.Column('fournisseur_nom', sa.String(100), nullable=True, comment='Nom du fournisseur'),
        sa.Column('fournisseur_type', sa.String(50), nullable=True, comment='Type: CASH_CARRY, GROSSISTE, etc.'),

        # Métadonnées
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        schema='dwh'
    )

    op.create_index('ix_other_produit_tenant', 'other_produit_agregat', ['tenant_id'], schema='dwh')
    op.create_index('ix_other_produit_designation', 'other_produit_agregat', ['tenant_id', 'designation_clean'], schema='dwh')


def downgrade() -> None:
    op.drop_index('ix_other_produit_designation', table_name='other_produit_agregat', schema='dwh')
    op.drop_index('ix_other_produit_tenant', table_name='other_produit_agregat', schema='dwh')
    op.drop_table('other_produit_agregat', schema='dwh')
