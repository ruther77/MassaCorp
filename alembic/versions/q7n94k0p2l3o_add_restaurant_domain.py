"""Add Restaurant Domain tables

Revision ID: q7n94k0p2l3o
Revises: p6m83j9o1k2n
Create Date: 2026-01-05

This migration creates all Restaurant Domain tables:
- restaurant_ingredients: Ingredients cuisine
- restaurant_plats: Plats et menus
- restaurant_plat_ingredients: Composition des plats
- restaurant_epicerie_links: Liens ingredient-produit
- restaurant_stock: Stock actuel des ingredients
- restaurant_stock_movements: Historique mouvements stock
- restaurant_consumptions: Consommations de plats
- restaurant_charges: Charges fixes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision = 'q7n94k0p2l3o'
down_revision = 'p6m83j9o1k2n'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Restaurant Domain tables."""

    # ========================================
    # 1. CREATE ENUMS
    # ========================================
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_unit') THEN
                CREATE TYPE restaurant_unit AS ENUM ('U', 'KG', 'L', 'G', 'CL', 'ML');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_ingredient_category') THEN
                CREATE TYPE restaurant_ingredient_category AS ENUM (
                    'VIANDE', 'POISSON', 'LEGUME', 'FRUIT',
                    'PRODUIT_LAITIER', 'EPICERIE', 'BOISSON', 'CONDIMENT', 'AUTRE'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_plat_category') THEN
                CREATE TYPE restaurant_plat_category AS ENUM (
                    'ENTREE', 'PLAT', 'DESSERT', 'BOISSON',
                    'MENU', 'ACCOMPAGNEMENT', 'AUTRE'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_stock_movement_type') THEN
                CREATE TYPE restaurant_stock_movement_type AS ENUM (
                    'ENTREE', 'SORTIE', 'AJUSTEMENT', 'PERTE', 'TRANSFERT'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_charge_type') THEN
                CREATE TYPE restaurant_charge_type AS ENUM (
                    'LOYER', 'SALAIRES', 'ELECTRICITE', 'EAU',
                    'GAZ', 'ASSURANCE', 'ENTRETIEN', 'MARKETING', 'AUTRES'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'restaurant_charge_frequency') THEN
                CREATE TYPE restaurant_charge_frequency AS ENUM (
                    'MENSUEL', 'TRIMESTRIEL', 'ANNUEL', 'PONCTUEL'
                );
            END IF;
        END $$;
    """)

    # ========================================
    # 2. CREATE TABLES
    # ========================================

    # restaurant_ingredients
    op.create_table(
        'restaurant_ingredients',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('unit', ENUM('U', 'KG', 'L', 'G', 'CL', 'ML', name='restaurant_unit', create_type=False), nullable=False),
        sa.Column('category', ENUM(
            'VIANDE', 'POISSON', 'LEGUME', 'FRUIT',
            'PRODUIT_LAITIER', 'EPICERIE', 'BOISSON', 'CONDIMENT', 'AUTRE',
            name='restaurant_ingredient_category', create_type=False
        ), nullable=False, server_default='AUTRE'),
        sa.Column('default_supplier_id', sa.BigInteger(), sa.ForeignKey('finance_vendors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prix_unitaire', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('seuil_alerte', sa.Numeric(10, 3), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_ingredients_tenant', 'restaurant_ingredients', ['tenant_id'])
    op.create_index('ix_restaurant_ingredients_name', 'restaurant_ingredients', ['tenant_id', 'name'])
    op.create_index('ix_restaurant_ingredients_category', 'restaurant_ingredients', ['tenant_id', 'category'])
    op.create_index('ix_restaurant_ingredients_active', 'restaurant_ingredients', ['tenant_id', 'is_active'])

    # restaurant_plats
    op.create_table(
        'restaurant_plats',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', ENUM(
            'ENTREE', 'PLAT', 'DESSERT', 'BOISSON',
            'MENU', 'ACCOMPAGNEMENT', 'AUTRE',
            name='restaurant_plat_category', create_type=False
        ), nullable=False, server_default='PLAT'),
        sa.Column('prix_vente', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_menu', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_plats_tenant', 'restaurant_plats', ['tenant_id'])
    op.create_index('ix_restaurant_plats_name', 'restaurant_plats', ['tenant_id', 'name'])
    op.create_index('ix_restaurant_plats_category', 'restaurant_plats', ['tenant_id', 'category'])
    op.create_index('ix_restaurant_plats_active', 'restaurant_plats', ['tenant_id', 'is_active'])

    # restaurant_plat_ingredients
    op.create_table(
        'restaurant_plat_ingredients',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('plat_id', sa.BigInteger(), sa.ForeignKey('restaurant_plats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ingredient_id', sa.BigInteger(), sa.ForeignKey('restaurant_ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quantite', sa.Numeric(10, 3), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_plat_ingredients_plat', 'restaurant_plat_ingredients', ['plat_id'])
    op.create_index('ix_restaurant_plat_ingredients_ingredient', 'restaurant_plat_ingredients', ['ingredient_id'])
    op.create_index('ix_restaurant_plat_ingredients_unique', 'restaurant_plat_ingredients', ['plat_id', 'ingredient_id'], unique=True)

    # restaurant_epicerie_links
    op.create_table(
        'restaurant_epicerie_links',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('ingredient_id', sa.BigInteger(), sa.ForeignKey('restaurant_ingredients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('produit_id', sa.BigInteger(), nullable=False),
        sa.Column('ratio', sa.Numeric(10, 4), server_default='1.0', nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_epicerie_links_ingredient', 'restaurant_epicerie_links', ['ingredient_id'])
    op.create_index('ix_restaurant_epicerie_links_produit', 'restaurant_epicerie_links', ['produit_id'])
    op.create_index('ix_restaurant_epicerie_links_tenant', 'restaurant_epicerie_links', ['tenant_id'])

    # restaurant_stock
    op.create_table(
        'restaurant_stock',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('ingredient_id', sa.BigInteger(), sa.ForeignKey('restaurant_ingredients.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('quantity', sa.Numeric(10, 3), server_default='0', nullable=False),
        sa.Column('last_inventory_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_stock_tenant', 'restaurant_stock', ['tenant_id'])
    op.create_index('ix_restaurant_stock_ingredient', 'restaurant_stock', ['ingredient_id'])

    # restaurant_stock_movements
    op.create_table(
        'restaurant_stock_movements',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('stock_id', sa.BigInteger(), sa.ForeignKey('restaurant_stock.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', ENUM(
            'ENTREE', 'SORTIE', 'AJUSTEMENT', 'PERTE', 'TRANSFERT',
            name='restaurant_stock_movement_type', create_type=False
        ), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('date_mouvement', sa.Date(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_stock_movements_stock', 'restaurant_stock_movements', ['stock_id'])
    op.create_index('ix_restaurant_stock_movements_date', 'restaurant_stock_movements', ['date_mouvement'])
    op.create_index('ix_restaurant_stock_movements_type', 'restaurant_stock_movements', ['type'])

    # restaurant_consumptions
    op.create_table(
        'restaurant_consumptions',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('plat_id', sa.BigInteger(), sa.ForeignKey('restaurant_plats.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date_consumption', sa.Date(), nullable=False),
        sa.Column('quantity', sa.BigInteger(), server_default='1', nullable=False),
        sa.Column('unit_cost', sa.BigInteger(), nullable=False),
        sa.Column('is_loss', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_consumptions_tenant', 'restaurant_consumptions', ['tenant_id'])
    op.create_index('ix_restaurant_consumptions_plat', 'restaurant_consumptions', ['plat_id'])
    op.create_index('ix_restaurant_consumptions_date', 'restaurant_consumptions', ['date_consumption'])
    op.create_index('ix_restaurant_consumptions_tenant_date', 'restaurant_consumptions', ['tenant_id', 'date_consumption'])

    # restaurant_charges
    op.create_table(
        'restaurant_charges',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('type', ENUM(
            'LOYER', 'SALAIRES', 'ELECTRICITE', 'EAU',
            'GAZ', 'ASSURANCE', 'ENTRETIEN', 'MARKETING', 'AUTRES',
            name='restaurant_charge_type', create_type=False
        ), nullable=False),
        sa.Column('montant', sa.BigInteger(), nullable=False),
        sa.Column('frequency', ENUM(
            'MENSUEL', 'TRIMESTRIEL', 'ANNUEL', 'PONCTUEL',
            name='restaurant_charge_frequency', create_type=False
        ), nullable=False, server_default='MENSUEL'),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_restaurant_charges_tenant', 'restaurant_charges', ['tenant_id'])
    op.create_index('ix_restaurant_charges_type', 'restaurant_charges', ['tenant_id', 'type'])
    op.create_index('ix_restaurant_charges_active', 'restaurant_charges', ['tenant_id', 'is_active'])

    # ========================================
    # 3. ENABLE RLS ON RESTAURANT TABLES
    # ========================================
    restaurant_tables_with_tenant = [
        'restaurant_ingredients',
        'restaurant_plats',
        'restaurant_epicerie_links',
        'restaurant_stock',
        'restaurant_consumptions',
        'restaurant_charges',
    ]

    for table in restaurant_tables_with_tenant:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
            );
        """)

    print("Restaurant Domain tables created successfully")


def downgrade() -> None:
    """Drop Restaurant Domain tables."""

    # Drop tables in reverse order (dependencies first)
    tables = [
        'restaurant_charges',
        'restaurant_consumptions',
        'restaurant_stock_movements',
        'restaurant_stock',
        'restaurant_epicerie_links',
        'restaurant_plat_ingredients',
        'restaurant_plats',
        'restaurant_ingredients',
    ]

    for table in tables:
        op.drop_table(table)

    # Drop enums
    op.execute("DROP TYPE IF EXISTS restaurant_charge_frequency;")
    op.execute("DROP TYPE IF EXISTS restaurant_charge_type;")
    op.execute("DROP TYPE IF EXISTS restaurant_stock_movement_type;")
    op.execute("DROP TYPE IF EXISTS restaurant_plat_category;")
    op.execute("DROP TYPE IF EXISTS restaurant_ingredient_category;")
    op.execute("DROP TYPE IF EXISTS restaurant_unit;")
