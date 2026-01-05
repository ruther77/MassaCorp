"""initial schema

Revision ID: c3bee0e2b93b
Revises: 
Create Date: 2025-12-27 20:38:36.023063

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3bee0e2b93b'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql_path = Path(__file__).resolve().parents[2] / "db" / "sql" / "00_init_flat.sql"
    sql = sql_path.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    # OPTION SIMPLE: drop tables in reverse dependency order
    op.execute("""
    DROP TABLE IF EXISTS feature_flags_user CASCADE;
    DROP TABLE IF EXISTS feature_flags_role CASCADE;
    DROP TABLE IF EXISTS feature_flags_tenant CASCADE;
    DROP TABLE IF EXISTS feature_flags_global CASCADE;
    DROP TABLE IF EXISTS features CASCADE;

    DROP TABLE IF EXISTS role_hierarchy CASCADE;
    DROP TABLE IF EXISTS api_key_roles CASCADE;
    DROP TABLE IF EXISTS user_roles CASCADE;
    DROP TABLE IF EXISTS role_permissions CASCADE;
    DROP TABLE IF EXISTS permissions CASCADE;
    DROP TABLE IF EXISTS roles CASCADE;

    DROP TABLE IF EXISTS api_key_usage CASCADE;
    DROP TABLE IF EXISTS api_keys CASCADE;

    DROP TABLE IF EXISTS sso_sessions CASCADE;
    DROP TABLE IF EXISTS user_identities CASCADE;
    DROP TABLE IF EXISTS identity_providers CASCADE;

    DROP TABLE IF EXISTS mfa_recovery_codes CASCADE;
    DROP TABLE IF EXISTS mfa_secrets CASCADE;

    DROP TABLE IF EXISTS login_attempts CASCADE;
    DROP TABLE IF EXISTS audit_log CASCADE;

    DROP TABLE IF EXISTS refresh_tokens CASCADE;
    DROP TABLE IF EXISTS sessions CASCADE;
    DROP TABLE IF EXISTS revoked_tokens CASCADE;
    """)
