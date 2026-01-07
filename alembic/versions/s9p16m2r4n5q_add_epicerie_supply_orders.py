"""Add epicerie supply orders tables.

Revision ID: s9p16m2r4n5q
Revises: r8o05l1q3m4p
Create Date: 2026-01-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's9p16m2r4n5q'
down_revision: Union[str, None] = 'r8o05l1q3m4p'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create supply_orders and supply_order_lines tables for epicerie domain.

    These tables manage supplier orders (METRO, Promocash, etc.) with:
    - Order tracking with status workflow
    - Line items with product references
    - Receipt tracking for partial deliveries
    - Multi-tenant support via tenant_id
    """
    # Create update_updated_at_column function if not exists
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Create enum type for supply order status
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE supply_order_status AS ENUM (
                'en_attente',
                'confirmee',
                'expediee',
                'livree',
                'annulee'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create supply_orders table
    op.execute("""
        CREATE TABLE IF NOT EXISTS supply_orders (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            vendor_id BIGINT NOT NULL REFERENCES finance_vendors(id) ON DELETE RESTRICT,
            reference TEXT,
            date_commande DATE NOT NULL,
            date_livraison_prevue DATE,
            date_livraison_reelle DATE,
            statut supply_order_status NOT NULL DEFAULT 'en_attente',
            montant_ht BIGINT NOT NULL DEFAULT 0,
            montant_tva BIGINT NOT NULL DEFAULT 0,
            notes TEXT,
            created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Create supply_order_lines table
    op.execute("""
        CREATE TABLE IF NOT EXISTS supply_order_lines (
            id BIGSERIAL PRIMARY KEY,
            order_id BIGINT NOT NULL REFERENCES supply_orders(id) ON DELETE CASCADE,
            produit_id BIGINT REFERENCES dwh.dim_produit(id) ON DELETE SET NULL,
            designation TEXT NOT NULL,
            quantity NUMERIC(10, 3) NOT NULL,
            prix_unitaire BIGINT NOT NULL,
            received_quantity NUMERIC(10, 3),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Create indexes for supply_orders
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_supply_orders_tenant ON supply_orders(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_supply_orders_vendor ON supply_orders(vendor_id);
        CREATE INDEX IF NOT EXISTS ix_supply_orders_statut ON supply_orders(statut);
        CREATE INDEX IF NOT EXISTS ix_supply_orders_date_commande ON supply_orders(date_commande);
        CREATE INDEX IF NOT EXISTS ix_supply_orders_date_livraison ON supply_orders(date_livraison_prevue);
    """)

    # Create indexes for supply_order_lines
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_supply_order_lines_order ON supply_order_lines(order_id);
        CREATE INDEX IF NOT EXISTS ix_supply_order_lines_produit ON supply_order_lines(produit_id);
    """)

    # Enable RLS on supply_orders
    op.execute("""
        ALTER TABLE supply_orders ENABLE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS supply_orders_tenant_isolation ON supply_orders;
        CREATE POLICY supply_orders_tenant_isolation ON supply_orders
            USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);
    """)

    # Add trigger for updated_at on supply_orders
    op.execute("""
        DROP TRIGGER IF EXISTS update_supply_orders_updated_at ON supply_orders;
        CREATE TRIGGER update_supply_orders_updated_at
            BEFORE UPDATE ON supply_orders
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # Add trigger for updated_at on supply_order_lines
    op.execute("""
        DROP TRIGGER IF EXISTS update_supply_order_lines_updated_at ON supply_order_lines;
        CREATE TRIGGER update_supply_order_lines_updated_at
            BEFORE UPDATE ON supply_order_lines
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Remove supply orders tables and related objects."""
    # Drop triggers
    op.execute("""
        DROP TRIGGER IF EXISTS update_supply_order_lines_updated_at ON supply_order_lines;
        DROP TRIGGER IF EXISTS update_supply_orders_updated_at ON supply_orders;
    """)

    # Drop RLS policy
    op.execute("""
        DROP POLICY IF EXISTS supply_orders_tenant_isolation ON supply_orders;
    """)

    # Drop indexes
    op.execute("""
        DROP INDEX IF EXISTS ix_supply_order_lines_produit;
        DROP INDEX IF EXISTS ix_supply_order_lines_order;
        DROP INDEX IF EXISTS ix_supply_orders_date_livraison;
        DROP INDEX IF EXISTS ix_supply_orders_date_commande;
        DROP INDEX IF EXISTS ix_supply_orders_statut;
        DROP INDEX IF EXISTS ix_supply_orders_vendor;
        DROP INDEX IF EXISTS ix_supply_orders_tenant;
    """)

    # Drop tables
    op.execute("""
        DROP TABLE IF EXISTS supply_order_lines;
        DROP TABLE IF EXISTS supply_orders;
    """)

    # Drop enum type
    op.execute("""
        DROP TYPE IF EXISTS supply_order_status;
    """)
