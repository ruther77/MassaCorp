"""add tenants and users tables

Revision ID: d4cf1a3e5f7c
Revises: c3bee0e2b93b
Create Date: 2025-12-27 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4cf1a3e5f7c'
down_revision: Union[str, None] = 'c3bee0e2b93b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================
    # Table: tenants
    # ============================================
    op.execute("""
        CREATE TABLE tenants (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            settings JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        -- Index pour recherche par slug
        CREATE INDEX tenants_slug_idx ON tenants (slug);

        -- Index pour tenants actifs
        CREATE INDEX tenants_active_idx ON tenants (is_active) WHERE is_active = TRUE;
    """)

    # ============================================
    # Table: users
    # ============================================
    op.execute("""
        CREATE TABLE users (
            id BIGSERIAL PRIMARY KEY,
            tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            password_hash TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_login_at TIMESTAMPTZ,
            password_changed_at TIMESTAMPTZ,
            UNIQUE (tenant_id, email)
        );

        -- Index pour recherche par tenant
        CREATE INDEX users_tenant_idx ON users (tenant_id);

        -- Index pour recherche par email (case-insensitive)
        CREATE INDEX users_email_lower_idx ON users (LOWER(email));

        -- Index pour users actifs par tenant
        CREATE INDEX users_tenant_active_idx ON users (tenant_id, is_active)
            WHERE is_active = TRUE;

        -- Index pour superusers
        CREATE INDEX users_superuser_idx ON users (is_superuser)
            WHERE is_superuser = TRUE;
    """)

    # ============================================
    # Ajouter FK manquantes sur tables existantes
    # ============================================
    # Note: Les tables existantes referencent user_id et tenant_id
    # sans FK. On ajoute les contraintes maintenant.

    # sessions -> users
    op.execute("""
        ALTER TABLE sessions
        ADD CONSTRAINT sessions_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE sessions
        ADD CONSTRAINT sessions_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # mfa_secrets -> users
    op.execute("""
        ALTER TABLE mfa_secrets
        ADD CONSTRAINT mfa_secrets_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE mfa_secrets
        ADD CONSTRAINT mfa_secrets_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # mfa_recovery_codes -> users
    op.execute("""
        ALTER TABLE mfa_recovery_codes
        ADD CONSTRAINT mfa_recovery_codes_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE mfa_recovery_codes
        ADD CONSTRAINT mfa_recovery_codes_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # user_identities -> users
    op.execute("""
        ALTER TABLE user_identities
        ADD CONSTRAINT user_identities_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE user_identities
        ADD CONSTRAINT user_identities_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # sso_sessions -> users
    op.execute("""
        ALTER TABLE sso_sessions
        ADD CONSTRAINT sso_sessions_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE sso_sessions
        ADD CONSTRAINT sso_sessions_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # identity_providers -> tenants
    op.execute("""
        ALTER TABLE identity_providers
        ADD CONSTRAINT identity_providers_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # api_keys -> tenants
    op.execute("""
        ALTER TABLE api_keys
        ADD CONSTRAINT api_keys_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # api_key_usage -> tenants
    op.execute("""
        ALTER TABLE api_key_usage
        ADD CONSTRAINT api_key_usage_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # roles -> tenants
    op.execute("""
        ALTER TABLE roles
        ADD CONSTRAINT roles_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # user_roles -> users
    op.execute("""
        ALTER TABLE user_roles
        ADD CONSTRAINT user_roles_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

        ALTER TABLE user_roles
        ADD CONSTRAINT user_roles_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # api_key_roles -> tenants
    op.execute("""
        ALTER TABLE api_key_roles
        ADD CONSTRAINT api_key_roles_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # feature_flags_tenant -> tenants
    op.execute("""
        ALTER TABLE feature_flags_tenant
        ADD CONSTRAINT feature_flags_tenant_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    """)

    # feature_flags_user -> users
    op.execute("""
        ALTER TABLE feature_flags_user
        ADD CONSTRAINT feature_flags_user_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    """)

    # audit_log (nullable FK)
    op.execute("""
        ALTER TABLE audit_log
        ADD CONSTRAINT audit_log_user_fk
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;

        ALTER TABLE audit_log
        ADD CONSTRAINT audit_log_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;
    """)


def downgrade() -> None:
    # Supprimer les FK ajoutees
    op.execute("""
        ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_tenant_fk;
        ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_user_fk;
        ALTER TABLE feature_flags_user DROP CONSTRAINT IF EXISTS feature_flags_user_user_fk;
        ALTER TABLE feature_flags_tenant DROP CONSTRAINT IF EXISTS feature_flags_tenant_tenant_fk;
        ALTER TABLE api_key_roles DROP CONSTRAINT IF EXISTS api_key_roles_tenant_fk;
        ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_tenant_fk;
        ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_user_fk;
        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_tenant_fk;
        ALTER TABLE api_key_usage DROP CONSTRAINT IF EXISTS api_key_usage_tenant_fk;
        ALTER TABLE api_keys DROP CONSTRAINT IF EXISTS api_keys_tenant_fk;
        ALTER TABLE identity_providers DROP CONSTRAINT IF EXISTS identity_providers_tenant_fk;
        ALTER TABLE sso_sessions DROP CONSTRAINT IF EXISTS sso_sessions_tenant_fk;
        ALTER TABLE sso_sessions DROP CONSTRAINT IF EXISTS sso_sessions_user_fk;
        ALTER TABLE user_identities DROP CONSTRAINT IF EXISTS user_identities_tenant_fk;
        ALTER TABLE user_identities DROP CONSTRAINT IF EXISTS user_identities_user_fk;
        ALTER TABLE mfa_recovery_codes DROP CONSTRAINT IF EXISTS mfa_recovery_codes_tenant_fk;
        ALTER TABLE mfa_recovery_codes DROP CONSTRAINT IF EXISTS mfa_recovery_codes_user_fk;
        ALTER TABLE mfa_secrets DROP CONSTRAINT IF EXISTS mfa_secrets_tenant_fk;
        ALTER TABLE mfa_secrets DROP CONSTRAINT IF EXISTS mfa_secrets_user_fk;
        ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_tenant_fk;
        ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_user_fk;
    """)

    # Supprimer les tables
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE;")
