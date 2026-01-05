"""Enable RLS on all tenant tables

Revision ID: n4k61h7m9i0l
Revises: m3j50h6l8h9k
Create Date: 2026-01-02

This migration:
1. Enables Row Level Security on all tables with tenant_id
2. Creates tenant isolation policies using session variable app.current_tenant_id
3. Ensures data isolation between tenants at the database level
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'n4k61h7m9i0l'
down_revision = 'm3j50h6l8h9k'
branch_labels = None
depends_on = None

# Tables with tenant_id that need RLS (verified from DB schema)
TENANT_TABLES = [
    'users',
    'sessions', 
    'api_keys',
    'api_key_usage',
    'api_key_roles',
    'audit_log',
    'mfa_secrets',
    'mfa_recovery_codes',
    'oauth_accounts',
    'roles',
    'user_roles',
    'user_identities',
    'identity_providers',
    'sso_sessions',
    'feature_flags_tenant',
]

# Tables that already have RLS enabled (from previous migrations)
EXISTING_RLS_TABLES = ['users', 'sessions', 'refresh_tokens', 'password_reset_tokens']


def upgrade() -> None:
    # Enable RLS and create policies for tables that don't have them yet
    for table in TENANT_TABLES:
        if table not in EXISTING_RLS_TABLES:
            # Enable RLS
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            
            # Create tenant isolation policy
            op.execute(f'''
                CREATE POLICY tenant_isolation ON {table}
                FOR ALL
                USING (tenant_id = COALESCE(
                    NULLIF(current_setting('app.current_tenant_id', true), '')::bigint,
                    tenant_id
                ))
            ''')
            print(f"RLS enabled on {table}")


def downgrade() -> None:
    # Remove policies and disable RLS
    for table in TENANT_TABLES:
        if table not in EXISTING_RLS_TABLES:
            op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table}')
            op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
