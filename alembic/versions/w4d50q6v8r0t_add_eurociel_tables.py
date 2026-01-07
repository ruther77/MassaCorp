"""Add EUROCIEL tables

Tables pour les factures fournisseur EUROCIEL (grossiste africain/tropical):
- dwh.eurociel_facture: Entetes de factures
- dwh.eurociel_ligne: Lignes de factures
- dwh.eurociel_produit_agregat: Agregation des produits

Fournisseur:
- Nom: EUROCIEL
- SIRET: 510154313
- TVA: FR55510154313

Revision ID: w4d50q6v8r0t
Revises: v3a45b67c89d
Create Date: 2026-01-07 19:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'w4d50q6v8r0t'
down_revision: Union[str, None] = 'v3a45b67c89d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Creer le schema dwh s'il n'existe pas
    op.execute("CREATE SCHEMA IF NOT EXISTS dwh")

    # Table eurociel_facture
    op.create_table(
        'eurociel_facture',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('numero', sa.String(20), nullable=False, comment='Numero de facture (FA/AV + numero)'),
        sa.Column('type_document', sa.String(10), nullable=False, server_default='FA', comment='Type: FA=Facture, AV=Avoir'),
        sa.Column('date_facture', sa.Date(), nullable=False, comment='Date de la facture'),
        sa.Column('client_nom', sa.String(100), nullable=False, comment='Nom client (L\'INCONTOURNABLE, NOUTAM)'),
        sa.Column('client_code', sa.String(50), nullable=True, comment='Code client EUROCIEL'),
        sa.Column('client_adresse', sa.String(255), nullable=True, comment='Adresse client'),
        sa.Column('client_telephone', sa.String(20), nullable=True, comment='Telephone client'),
        sa.Column('total_ht', sa.Numeric(12, 2), nullable=False, server_default='0', comment='Total HT'),
        sa.Column('total_tva', sa.Numeric(12, 2), nullable=False, server_default='0', comment='Total TVA'),
        sa.Column('total_ttc', sa.Numeric(12, 2), nullable=False, server_default='0', comment='Total TTC (NET A PAYER)'),
        sa.Column('poids_total', sa.Numeric(10, 2), nullable=True, comment='Poids total en kg'),
        sa.Column('quantite_totale', sa.Numeric(10, 3), nullable=True, comment='Quantite totale'),
        sa.Column('fichier_source', sa.String(255), nullable=True, comment='Fichier PDF source'),
        sa.Column('page_source', sa.BigInteger(), nullable=True, comment='Page dans le PDF source'),
        sa.Column('importee_le', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='Date d\'import'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'numero', name='uq_eurociel_facture_numero'),
        schema='dwh'
    )
    op.create_index('ix_eurociel_facture_numero', 'eurociel_facture', ['tenant_id', 'numero'], schema='dwh')
    op.create_index('ix_eurociel_facture_date', 'eurociel_facture', ['tenant_id', 'date_facture'], schema='dwh')
    op.create_index('ix_eurociel_facture_client', 'eurociel_facture', ['tenant_id', 'client_code'], schema='dwh')

    # Table eurociel_ligne
    op.create_table(
        'eurociel_ligne',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('facture_id', sa.BigInteger(), nullable=False),
        sa.Column('numero_ligne', sa.BigInteger(), nullable=False, server_default='1', comment='Numero de reference ligne'),
        sa.Column('ean', sa.String(20), nullable=True, comment='Code EAN (peut etre renseigne manuellement)'),
        sa.Column('designation', sa.String(255), nullable=False, comment='Designation brute du produit'),
        sa.Column('designation_clean', sa.String(200), nullable=True, comment='Designation normalisee'),
        sa.Column('quantite', sa.Numeric(10, 3), nullable=False, server_default='1', comment='Quantite commandee'),
        sa.Column('poids', sa.Numeric(10, 2), nullable=True, comment='Poids en kg'),
        sa.Column('prix_unitaire', sa.Numeric(10, 4), nullable=False, comment='Prix unitaire HT (au colis/kg)'),
        sa.Column('montant_ht', sa.Numeric(12, 2), nullable=False, comment='Montant HT'),
        sa.Column('code_tva', sa.String(5), nullable=False, server_default='C07', comment='Code TVA (C07=5.5%, C08=20%)'),
        sa.Column('taux_tva', sa.Numeric(5, 2), nullable=False, server_default='5.5', comment='Taux de TVA'),
        sa.Column('montant_tva', sa.Numeric(12, 2), nullable=True, comment='Montant TVA calcule'),
        sa.Column('montant_ttc', sa.Numeric(12, 2), nullable=True, comment='Montant TTC calcule'),
        sa.Column('est_promo', sa.Boolean(), nullable=False, server_default='false', comment='Produit en promotion'),
        sa.Column('categorie_id', sa.BigInteger(), nullable=True, comment='FK vers dim_categorie_produit'),
        sa.ForeignKeyConstraint(['facture_id'], ['dwh.eurociel_facture.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='dwh'
    )
    op.create_index('ix_eurociel_ligne_designation', 'eurociel_ligne', ['tenant_id', 'designation_clean'], schema='dwh')
    op.create_index('ix_eurociel_ligne_facture', 'eurociel_ligne', ['facture_id'], schema='dwh')
    op.create_index('ix_eurociel_ligne_ean', 'eurociel_ligne', ['tenant_id', 'ean'], schema='dwh')

    # Table eurociel_produit_agregat
    op.create_table(
        'eurociel_produit_agregat',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('ean', sa.String(20), nullable=True, comment='Code EAN (renseigne manuellement)'),
        sa.Column('designation_brute', sa.Text(), nullable=False, comment='Designation originale'),
        sa.Column('designation_clean', sa.String(200), nullable=False, comment='Designation normalisee (cle)'),
        sa.Column('dim_produit_id', sa.BigInteger(), nullable=True, comment='FK vers dwh.dim_produit'),
        sa.Column('quantite_totale', sa.Numeric(12, 3), nullable=False, server_default='0', comment='Quantite totale'),
        sa.Column('poids_total', sa.Numeric(12, 2), nullable=True, comment='Poids total en kg'),
        sa.Column('nb_achats', sa.BigInteger(), nullable=False, server_default='0', comment='Nombre d\'achats'),
        sa.Column('montant_total_ht', sa.Numeric(14, 2), nullable=False, server_default='0', comment='Montant total HT'),
        sa.Column('montant_total_tva', sa.Numeric(14, 2), nullable=True, comment='Montant total TVA'),
        sa.Column('montant_total', sa.Numeric(14, 2), nullable=False, server_default='0', comment='Montant total TTC'),
        sa.Column('prix_moyen', sa.Numeric(10, 4), nullable=False, server_default='0', comment='Prix moyen HT'),
        sa.Column('prix_min', sa.Numeric(10, 4), nullable=False, server_default='0', comment='Prix minimum HT'),
        sa.Column('prix_max', sa.Numeric(10, 4), nullable=False, server_default='0', comment='Prix maximum HT'),
        sa.Column('taux_tva', sa.Numeric(5, 2), nullable=False, server_default='5.5', comment='Taux TVA principal'),
        sa.Column('categorie_id', sa.BigInteger(), nullable=True, comment='FK vers dim_categorie_produit'),
        sa.Column('famille', sa.String(50), nullable=False, server_default='EPICERIE', comment='Famille'),
        sa.Column('categorie', sa.String(50), nullable=False, server_default='Alimentaire', comment='Categorie'),
        sa.Column('sous_categorie', sa.String(50), nullable=True, comment='Sous-categorie'),
        sa.Column('premier_achat', sa.Date(), nullable=True, comment='Date du premier achat'),
        sa.Column('dernier_achat', sa.Date(), nullable=True, comment='Date du dernier achat'),
        sa.Column('calcule_le', sa.DateTime(timezone=True), server_default=sa.func.now(), comment='Date du dernier calcul'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'designation_clean', name='uq_eurociel_produit_designation'),
        schema='dwh'
    )
    op.create_index('ix_eurociel_produit_designation', 'eurociel_produit_agregat', ['tenant_id', 'designation_clean'], schema='dwh')
    op.create_index('ix_eurociel_produit_categorie', 'eurociel_produit_agregat', ['tenant_id', 'categorie_id'], schema='dwh')
    op.create_index('ix_eurociel_produit_montant', 'eurociel_produit_agregat', ['tenant_id', 'montant_total'], schema='dwh')
    op.create_index('ix_eurociel_produit_ean', 'eurociel_produit_agregat', ['tenant_id', 'ean'], schema='dwh')


def downgrade() -> None:
    op.drop_table('eurociel_produit_agregat', schema='dwh')
    op.drop_table('eurociel_ligne', schema='dwh')
    op.drop_table('eurociel_facture', schema='dwh')
