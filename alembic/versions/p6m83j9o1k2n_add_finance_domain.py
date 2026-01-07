"""Add Finance Domain tables

Revision ID: p6m83j9o1k2n
Revises: o5l72i8n0j1m
Create Date: 2026-01-05

This migration creates all Finance Domain tables:
- finance_entities: Entites financieres (societes, etablissements)
- finance_entity_members: Membres d'une entite
- finance_categories: Categories de transactions
- finance_cost_centers: Centres de couts
- finance_accounts: Comptes bancaires
- finance_account_balances: Historique des soldes
- finance_transactions: Transactions
- finance_transaction_lines: Lignes de transactions
- finance_vendors: Fournisseurs
- finance_invoices: Factures fournisseurs
- finance_invoice_lines: Lignes de factures
- finance_payments: Paiements
- finance_bank_statements: Releves bancaires
- finance_bank_statement_lines: Lignes de releves
- finance_reconciliations: Rapprochements
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ENUM


revision = 'p6m83j9o1k2n'
down_revision = 'o5l72i8n0j1m'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Finance Domain tables."""

    # ========================================
    # 1. CREATE ENUMS
    # ========================================
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_category_type') THEN
                CREATE TYPE finance_category_type AS ENUM ('INCOME', 'EXPENSE', 'TRANSFER');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_account_type') THEN
                CREATE TYPE finance_account_type AS ENUM ('BANQUE', 'CAISSE', 'CB', 'PLATFORM', 'AUTRE');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_tx_direction') THEN
                CREATE TYPE finance_tx_direction AS ENUM ('IN', 'OUT', 'TRANSFER');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_tx_status') THEN
                CREATE TYPE finance_tx_status AS ENUM ('DRAFT', 'CONFIRMED', 'CANCELLED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_invoice_status') THEN
                CREATE TYPE finance_invoice_status AS ENUM ('EN_ATTENTE', 'PARTIELLE', 'PAYEE', 'ANNULEE');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'finance_reconciliation_status') THEN
                CREATE TYPE finance_reconciliation_status AS ENUM ('AUTO', 'MANUAL', 'REJECTED');
            END IF;
        END $$;
    """)

    # ========================================
    # 2. CREATE TABLES
    # ========================================

    # finance_entities
    op.create_table(
        'finance_entities',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('currency', sa.Text(), server_default='EUR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('siret', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_entities_tenant_name', 'finance_entities', ['tenant_id', 'name'])
    op.create_index('ix_finance_entities_tenant_code', 'finance_entities', ['tenant_id', 'code'], unique=True)
    op.create_index('ix_finance_entities_tenant_active', 'finance_entities', ['tenant_id', 'is_active'])

    # finance_entity_members
    op.create_table(
        'finance_entity_members',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Text(), server_default='viewer', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_entity_members_entity_id', 'finance_entity_members', ['entity_id'])
    op.create_index('ix_finance_entity_members_user_id', 'finance_entity_members', ['user_id'])
    op.create_index('ix_finance_entity_members_entity_user', 'finance_entity_members', ['entity_id', 'user_id'], unique=True)

    # finance_categories
    op.create_table(
        'finance_categories',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('type', ENUM('INCOME', 'EXPENSE', 'TRANSFER', name='finance_category_type', create_type=False), nullable=False),
        sa.Column('parent_id', sa.BigInteger(), sa.ForeignKey('finance_categories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_categories_entity_id', 'finance_categories', ['entity_id'])
    op.create_index('ix_finance_categories_entity_type', 'finance_categories', ['entity_id', 'type'])
    op.create_index('ix_finance_categories_tenant_entity', 'finance_categories', ['tenant_id', 'entity_id'])
    op.create_index('ix_finance_categories_parent', 'finance_categories', ['parent_id'])

    # finance_cost_centers
    op.create_table(
        'finance_cost_centers',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('budget_annual', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_cost_centers_entity_id', 'finance_cost_centers', ['entity_id'])
    op.create_index('ix_finance_cost_centers_entity_active', 'finance_cost_centers', ['entity_id', 'is_active'])
    op.create_index('ix_finance_cost_centers_entity_code', 'finance_cost_centers', ['entity_id', 'code'], unique=True)
    op.create_index('ix_finance_cost_centers_tenant', 'finance_cost_centers', ['tenant_id'])

    # finance_accounts
    op.create_table(
        'finance_accounts',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', ENUM('BANQUE', 'CAISSE', 'CB', 'PLATFORM', 'AUTRE', name='finance_account_type', create_type=False), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('bank_name', sa.Text(), nullable=True),
        sa.Column('iban', sa.Text(), nullable=True),
        sa.Column('bic', sa.Text(), nullable=True),
        sa.Column('currency', sa.Text(), server_default='EUR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('initial_balance', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('current_balance', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_accounts_entity_id', 'finance_accounts', ['entity_id'])
    op.create_index('ix_finance_accounts_entity_type', 'finance_accounts', ['entity_id', 'type'])
    op.create_index('ix_finance_accounts_entity_active', 'finance_accounts', ['entity_id', 'is_active'])
    op.create_index('ix_finance_accounts_tenant', 'finance_accounts', ['tenant_id'])
    op.create_index('ix_finance_accounts_iban', 'finance_accounts', ['iban'])

    # finance_account_balances
    op.create_table(
        'finance_account_balances',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('finance_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('balance', sa.BigInteger(), nullable=False),
        sa.Column('source', sa.Text(), server_default='manual', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_account_balances_account_id', 'finance_account_balances', ['account_id'])
    op.create_index('ix_finance_account_balances_account_date', 'finance_account_balances', ['account_id', 'date'], unique=True)

    # finance_vendors
    op.create_table(
        'finance_vendors',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('siret', sa.Text(), nullable=True),
        sa.Column('tva_intra', sa.Text(), nullable=True),
        sa.Column('contact_name', sa.Text(), nullable=True),
        sa.Column('contact_email', sa.Text(), nullable=True),
        sa.Column('contact_phone', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('postal_code', sa.Text(), nullable=True),
        sa.Column('city', sa.Text(), nullable=True),
        sa.Column('country', sa.Text(), server_default='FR', nullable=False),
        sa.Column('iban', sa.Text(), nullable=True),
        sa.Column('bic', sa.Text(), nullable=True),
        sa.Column('payment_terms_days', sa.BigInteger(), server_default='30', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_vendors_entity_id', 'finance_vendors', ['entity_id'])
    op.create_index('ix_finance_vendors_entity_name', 'finance_vendors', ['entity_id', 'name'])
    op.create_index('ix_finance_vendors_entity_active', 'finance_vendors', ['entity_id', 'is_active'])
    op.create_index('ix_finance_vendors_tenant', 'finance_vendors', ['tenant_id'])
    op.create_index('ix_finance_vendors_siret', 'finance_vendors', ['siret'])

    # finance_transactions
    op.create_table(
        'finance_transactions',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('finance_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('direction', ENUM('IN', 'OUT', 'TRANSFER', name='finance_tx_direction', create_type=False), nullable=False),
        sa.Column('status', ENUM('DRAFT', 'CONFIRMED', 'CANCELLED', name='finance_tx_status', create_type=False), server_default='CONFIRMED', nullable=False),
        sa.Column('date_operation', sa.Date(), nullable=False),
        sa.Column('date_valeur', sa.Date(), nullable=True),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), server_default='manual', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_transactions_entity_id', 'finance_transactions', ['entity_id'])
    op.create_index('ix_finance_transactions_account_id', 'finance_transactions', ['account_id'])
    op.create_index('ix_finance_tx_entity_date', 'finance_transactions', ['entity_id', 'date_operation'])
    op.create_index('ix_finance_tx_account_date', 'finance_transactions', ['account_id', 'date_operation'])
    op.create_index('ix_finance_tx_tenant_date', 'finance_transactions', ['tenant_id', 'date_operation'])
    op.create_index('ix_finance_tx_status', 'finance_transactions', ['status'])

    # finance_transaction_lines
    op.create_table(
        'finance_transaction_lines',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('transaction_id', sa.BigInteger(), sa.ForeignKey('finance_transactions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', sa.BigInteger(), sa.ForeignKey('finance_categories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cost_center_id', sa.BigInteger(), sa.ForeignKey('finance_cost_centers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('montant_ht', sa.BigInteger(), nullable=False),
        sa.Column('tva_pct', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('montant_ttc', sa.BigInteger(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_tx_lines_transaction', 'finance_transaction_lines', ['transaction_id'])
    op.create_index('ix_finance_tx_lines_category', 'finance_transaction_lines', ['category_id'])
    op.create_index('ix_finance_tx_lines_cost_center', 'finance_transaction_lines', ['cost_center_id'])

    # finance_invoices
    op.create_table(
        'finance_invoices',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('entity_id', sa.BigInteger(), sa.ForeignKey('finance_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vendor_id', sa.BigInteger(), sa.ForeignKey('finance_vendors.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('invoice_number', sa.Text(), nullable=False),
        sa.Column('date_invoice', sa.Date(), nullable=False),
        sa.Column('date_due', sa.Date(), nullable=False),
        sa.Column('date_received', sa.Date(), nullable=True),
        sa.Column('montant_ht', sa.BigInteger(), nullable=False),
        sa.Column('montant_tva', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('montant_ttc', sa.BigInteger(), nullable=False),
        sa.Column('status', ENUM('EN_ATTENTE', 'PARTIELLE', 'PAYEE', 'ANNULEE', name='finance_invoice_status', create_type=False), server_default='EN_ATTENTE', nullable=False),
        sa.Column('file_name', sa.Text(), nullable=True),
        sa.Column('file_hash', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_invoices_entity_id', 'finance_invoices', ['entity_id'])
    op.create_index('ix_finance_invoices_vendor_id', 'finance_invoices', ['vendor_id'])
    op.create_index('ix_finance_invoices_entity_status', 'finance_invoices', ['entity_id', 'status'])
    op.create_index('ix_finance_invoices_due', 'finance_invoices', ['date_due'])
    op.create_index('ix_finance_invoices_tenant_date', 'finance_invoices', ['tenant_id', 'date_invoice'])
    op.create_index('ix_finance_invoices_entity_number', 'finance_invoices', ['entity_id', 'vendor_id', 'invoice_number'], unique=True)

    # finance_invoice_lines
    op.create_table(
        'finance_invoice_lines',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('invoice_id', sa.BigInteger(), sa.ForeignKey('finance_invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', sa.BigInteger(), sa.ForeignKey('finance_categories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('quantite', sa.BigInteger(), server_default='100', nullable=False),
        sa.Column('prix_unitaire', sa.BigInteger(), nullable=False),
        sa.Column('montant_ht', sa.BigInteger(), nullable=False),
        sa.Column('tva_pct', sa.BigInteger(), server_default='2000', nullable=False),
        sa.Column('montant_ttc', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_invoice_lines_invoice', 'finance_invoice_lines', ['invoice_id'])
    op.create_index('ix_finance_invoice_lines_category', 'finance_invoice_lines', ['category_id'])

    # finance_payments
    op.create_table(
        'finance_payments',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('invoice_id', sa.BigInteger(), sa.ForeignKey('finance_invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transaction_id', sa.BigInteger(), sa.ForeignKey('finance_transactions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('date_payment', sa.Date(), nullable=False),
        sa.Column('mode', sa.Text(), server_default='virement', nullable=False),
        sa.Column('reference', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_payments_invoice', 'finance_payments', ['invoice_id'])
    op.create_index('ix_finance_payments_transaction', 'finance_payments', ['transaction_id'])

    # finance_bank_statements
    op.create_table(
        'finance_bank_statements',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('account_id', sa.BigInteger(), sa.ForeignKey('finance_accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=True),
        sa.Column('file_hash', sa.Text(), nullable=True),
        sa.Column('balance_start', sa.BigInteger(), nullable=True),
        sa.Column('balance_end', sa.BigInteger(), nullable=True),
        sa.Column('lines_imported', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('lines_matched', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_bank_statements_account_id', 'finance_bank_statements', ['account_id'])
    op.create_index('ix_finance_bank_statements_account_period', 'finance_bank_statements', ['account_id', 'period_start', 'period_end'])
    op.create_index('ix_finance_bank_statements_tenant', 'finance_bank_statements', ['tenant_id'])
    op.create_index('ix_finance_bank_statements_hash', 'finance_bank_statements', ['file_hash'])

    # finance_bank_statement_lines
    op.create_table(
        'finance_bank_statement_lines',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('statement_id', sa.BigInteger(), sa.ForeignKey('finance_bank_statements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date_operation', sa.Date(), nullable=False),
        sa.Column('date_valeur', sa.Date(), nullable=True),
        sa.Column('libelle_banque', sa.Text(), nullable=False),
        sa.Column('montant', sa.BigInteger(), nullable=False),
        sa.Column('ref_banque', sa.Text(), nullable=True),
        sa.Column('checksum', sa.Text(), nullable=True),
        sa.Column('is_matched', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_bank_statement_lines_statement', 'finance_bank_statement_lines', ['statement_id'])
    op.create_index('ix_finance_bank_statement_lines_date', 'finance_bank_statement_lines', ['date_operation'])
    op.create_index('ix_finance_bank_statement_lines_ref', 'finance_bank_statement_lines', ['ref_banque'])
    op.create_index('ix_finance_bank_statement_lines_checksum', 'finance_bank_statement_lines', ['checksum'])

    # finance_reconciliations
    op.create_table(
        'finance_reconciliations',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('statement_line_id', sa.BigInteger(), sa.ForeignKey('finance_bank_statement_lines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transaction_id', sa.BigInteger(), sa.ForeignKey('finance_transactions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', ENUM('AUTO', 'MANUAL', 'REJECTED', name='finance_reconciliation_status', create_type=False), server_default='MANUAL', nullable=False),
        sa.Column('confidence', sa.BigInteger(), server_default='100', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_finance_reconciliations_statement_line', 'finance_reconciliations', ['statement_line_id'])
    op.create_index('ix_finance_reconciliations_transaction', 'finance_reconciliations', ['transaction_id'])
    op.create_index('ix_finance_reconciliations_status', 'finance_reconciliations', ['status'])
    op.create_index('ix_finance_reconciliations_unique', 'finance_reconciliations', ['statement_line_id', 'transaction_id'], unique=True)

    # ========================================
    # 3. ENABLE RLS ON FINANCE TABLES
    # ========================================
    finance_tables_with_tenant = [
        'finance_entities',
        'finance_categories',
        'finance_cost_centers',
        'finance_accounts',
        'finance_transactions',
        'finance_vendors',
        'finance_invoices',
        'finance_bank_statements',
    ]

    for table in finance_tables_with_tenant:
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

    print("Finance Domain tables created successfully")


def downgrade() -> None:
    """Drop Finance Domain tables."""

    # Drop tables in reverse order (dependencies first)
    tables = [
        'finance_reconciliations',
        'finance_bank_statement_lines',
        'finance_bank_statements',
        'finance_payments',
        'finance_invoice_lines',
        'finance_invoices',
        'finance_transaction_lines',
        'finance_transactions',
        'finance_vendors',
        'finance_account_balances',
        'finance_accounts',
        'finance_cost_centers',
        'finance_categories',
        'finance_entity_members',
        'finance_entities',
    ]

    for table in tables:
        op.drop_table(table)

    # Drop enums
    op.execute("DROP TYPE IF EXISTS finance_reconciliation_status;")
    op.execute("DROP TYPE IF EXISTS finance_invoice_status;")
    op.execute("DROP TYPE IF EXISTS finance_tx_status;")
    op.execute("DROP TYPE IF EXISTS finance_tx_direction;")
    op.execute("DROP TYPE IF EXISTS finance_account_type;")
    op.execute("DROP TYPE IF EXISTS finance_category_type;")
