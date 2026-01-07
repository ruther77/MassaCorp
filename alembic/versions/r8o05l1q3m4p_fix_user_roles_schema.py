"""Fix user_roles schema to match model.

Revision ID: r8o05l1q3m4p
Revises: q7n94k0p2l3o
Create Date: 2026-01-06 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r8o05l1q3m4p'
down_revision: Union[str, None] = 'q7n94k0p2l3o'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix user_roles table schema to match SQLAlchemy model.

    Changes:
    - Add id column as primary key (SERIAL/BIGSERIAL)
    - Add assigned_by column for audit
    - Add expires_at column for temporary roles
    - Change primary key from (user_id, role_id) to id
    - Add unique constraint on (user_id, role_id)
    """
    # Drop existing primary key constraint
    op.execute("""
        ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_pkey;
    """)

    # Add id column as BIGSERIAL
    op.execute("""
        ALTER TABLE user_roles
        ADD COLUMN id BIGSERIAL;
    """)

    # Set id as primary key
    op.execute("""
        ALTER TABLE user_roles
        ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);
    """)

    # Add unique constraint on (user_id, role_id) to maintain data integrity
    op.execute("""
        ALTER TABLE user_roles
        ADD CONSTRAINT uq_user_role UNIQUE (user_id, role_id);
    """)

    # Add assigned_by column for audit trail
    op.execute("""
        ALTER TABLE user_roles
        ADD COLUMN assigned_by BIGINT NULL;

        ALTER TABLE user_roles
        ADD CONSTRAINT user_roles_assigned_by_fk
        FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL;
    """)

    # Add expires_at column for temporary role assignments
    op.execute("""
        ALTER TABLE user_roles
        ADD COLUMN expires_at TIMESTAMPTZ NULL;
    """)

    # Add created_at and updated_at columns (from TimestampMixin)
    op.execute("""
        ALTER TABLE user_roles
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

        ALTER TABLE user_roles
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    """)

    # Create index on role_id if not exists
    op.execute("""
        CREATE INDEX IF NOT EXISTS user_roles_role_idx ON user_roles (role_id);
    """)


def downgrade() -> None:
    """Revert user_roles to original composite primary key schema."""
    # Remove new columns
    op.execute("""
        ALTER TABLE user_roles DROP COLUMN IF EXISTS expires_at;
        ALTER TABLE user_roles DROP COLUMN IF EXISTS assigned_by;
        ALTER TABLE user_roles DROP COLUMN IF EXISTS created_at;
        ALTER TABLE user_roles DROP COLUMN IF EXISTS updated_at;
    """)

    # Drop unique constraint
    op.execute("""
        ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS uq_user_role;
    """)

    # Drop id primary key and column
    op.execute("""
        ALTER TABLE user_roles DROP CONSTRAINT IF EXISTS user_roles_pkey;
        ALTER TABLE user_roles DROP COLUMN IF EXISTS id;
    """)

    # Restore original composite primary key
    op.execute("""
        ALTER TABLE user_roles ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);
    """)

    # Drop role index
    op.execute("""
        DROP INDEX IF EXISTS user_roles_role_idx;
    """)
