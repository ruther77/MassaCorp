"""Add TAIYAT tables

Tables pour les factures fournisseur TAI YAT DISTRIBUTION:
- dwh.taiyat_facture: Entêtes de factures
- dwh.taiyat_ligne: Lignes de factures
- dwh.taiyat_produit_agregat: Agrégation des produits

Revision ID: v2c39p5u7q9s
Revises: u1b28o4t6p8r
Create Date: 2026-01-07 00:55:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'v2c39p5u7q9s'
down_revision: Union[str, None] = 'u1b28o4t6p8r'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer le schéma dwh s'il n'existe pas
    op.execute("CREATE SCHEMA IF NOT EXISTS dwh")

    # Table taiyat_facture
    op.create_table(
        'taiyat_facture',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('numero', sa.String(50), nullable=False, comment='Numéro de facture TAIYAT'),
        sa.Column('date_facture', sa.Date(), nullable=False, comment='Date de la facture'),
        sa.Column('echeance', sa.Date(), nullable=True, comment='Date d\'échéance'),
        sa.Column('client_nom', sa.String(100), nullable=False, comment='Nom client (NOUTAM, INCONTOURNABLE)'),
        sa.Column('client_code', sa.String(20), nullable=True, comment='Code client TAIYAT'),
        sa.Column('total_ht', sa.Numeric(12, 2), nullable=True, comment='Total HT'),
        sa.Column('total_tva', sa.Numeric(12, 2), nullable=True, comment='Total TVA'),
        sa.Column('total_ttc', sa.Numeric(12, 2), nullable=False, server_default='0', comment='Total TTC'),
        sa.Column('fichier_source', sa.String(255), nullable=True, comment='Fichier PDF source'),
        sa.Column('importee_le', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='Date d\'import'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'numero', name='uq_taiyat_facture_numero'),
        schema='dwh'
    )
    op.create_index('ix_taiyat_facture_numero', 'taiyat_facture', ['tenant_id', 'numero'], schema='dwh')
    op.create_index('ix_taiyat_facture_date', 'taiyat_facture', ['tenant_id', 'date_facture'], schema='dwh')
    op.create_index('ix_taiyat_facture_client', 'taiyat_facture', ['tenant_id', 'client_nom'], schema='dwh')

    # Table taiyat_ligne
    op.create_table(
        'taiyat_ligne',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('facture_id', sa.BigInteger(), nullable=False),
        sa.Column('designation', sa.String(255), nullable=False, comment='Désignation brute'),
        sa.Column('designation_clean', sa.String(200), nullable=True, comment='Désignation normalisée'),
        sa.Column('provenance', sa.String(50), nullable=True, comment='Pays d\'origine'),
        sa.Column('colis', sa.BigInteger(), nullable=False, server_default='1', comment='Nombre de colis'),
        sa.Column('pieces', sa.BigInteger(), nullable=True, comment='Nombre de pièces'),
        sa.Column('unite', sa.String(10), nullable=False, server_default='c', comment='Unité de vente'),
        sa.Column('prix_unitaire_ht', sa.Numeric(10, 4), nullable=False, comment='Prix unitaire HT'),
        sa.Column('prix_unitaire_ttc', sa.Numeric(10, 4), nullable=True, comment='Prix unitaire TTC'),
        sa.Column('montant_ttc', sa.Numeric(12, 2), nullable=False, comment='Montant TTC'),
        sa.Column('montant_ht', sa.Numeric(12, 2), nullable=True, comment='Montant HT calculé'),
        sa.Column('code_tva', sa.String(5), nullable=True, comment='Code TVA'),
        sa.Column('taux_tva', sa.Numeric(5, 2), nullable=False, server_default='5.5', comment='Taux de TVA'),
        sa.Column('est_remise', sa.Boolean(), nullable=False, server_default='false', comment='Ligne de remise'),
        sa.Column('categorie_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['facture_id'], ['dwh.taiyat_facture.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='dwh'
    )
    op.create_index('ix_taiyat_ligne_designation', 'taiyat_ligne', ['tenant_id', 'designation_clean'], schema='dwh')
    op.create_index('ix_taiyat_ligne_facture', 'taiyat_ligne', ['facture_id'], schema='dwh')
    op.create_index('ix_taiyat_ligne_provenance', 'taiyat_ligne', ['tenant_id', 'provenance'], schema='dwh')

    # Table taiyat_produit_agregat
    op.create_table(
        'taiyat_produit_agregat',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('designation_brute', sa.Text(), nullable=False, comment='Désignation originale'),
        sa.Column('designation_clean', sa.String(200), nullable=False, comment='Désignation normalisée'),
        sa.Column('provenance', sa.String(50), nullable=True, comment='Pays d\'origine principal'),
        sa.Column('quantite_colis_totale', sa.Numeric(12, 3), nullable=False, server_default='0'),
        sa.Column('quantite_pieces_totale', sa.Numeric(12, 3), nullable=True),
        sa.Column('nb_achats', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('montant_total_ht', sa.Numeric(14, 2), nullable=True),
        sa.Column('montant_total_tva', sa.Numeric(14, 2), nullable=True),
        sa.Column('montant_total', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('prix_moyen_ht', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('prix_min_ht', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('prix_max_ht', sa.Numeric(10, 4), nullable=False, server_default='0'),
        sa.Column('taux_tva', sa.Numeric(5, 2), nullable=False, server_default='5.5'),
        sa.Column('categorie_id', sa.BigInteger(), nullable=True),
        sa.Column('famille', sa.String(50), nullable=False, server_default='EPICERIE'),
        sa.Column('categorie', sa.String(50), nullable=False, server_default='Alimentaire'),
        sa.Column('sous_categorie', sa.String(50), nullable=True),
        sa.Column('premier_achat', sa.Date(), nullable=True),
        sa.Column('dernier_achat', sa.Date(), nullable=True),
        sa.Column('calcule_le', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'designation_clean', name='uq_taiyat_produit_designation'),
        schema='dwh'
    )
    op.create_index('ix_taiyat_produit_designation', 'taiyat_produit_agregat', ['tenant_id', 'designation_clean'], schema='dwh')
    op.create_index('ix_taiyat_produit_provenance', 'taiyat_produit_agregat', ['tenant_id', 'provenance'], schema='dwh')
    op.create_index('ix_taiyat_produit_categorie', 'taiyat_produit_agregat', ['tenant_id', 'categorie_id'], schema='dwh')
    op.create_index('ix_taiyat_produit_montant', 'taiyat_produit_agregat', ['tenant_id', 'montant_total'], schema='dwh')


def downgrade() -> None:
    op.drop_table('taiyat_produit_agregat', schema='dwh')
    op.drop_table('taiyat_ligne', schema='dwh')
    op.drop_table('taiyat_facture', schema='dwh')
