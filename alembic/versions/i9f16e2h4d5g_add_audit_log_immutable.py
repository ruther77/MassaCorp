"""Add audit_log immutability trigger

Revision ID: i9f16e2h4d5g
Revises: 9ed31d547bd7
Create Date: 2025-12-28 21:30:00.000000

Ce trigger empeche la modification ou suppression des logs d'audit.
Conformite: logs d'audit doivent etre immuables pour audit trail.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'i9f16e2h4d5g'
down_revision: Union[str, None] = '9ed31d547bd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute le trigger d'immutabilite sur audit_log."""

    # Creer la fonction trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_immutable_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is immutable: % not allowed', TG_OP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Creer le trigger pour bloquer UPDATE et DELETE
    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_immutable_trigger();
    """)


def downgrade() -> None:
    """Supprime le trigger d'immutabilite."""

    # Supprimer le trigger
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log;")

    # Supprimer la fonction
    op.execute("DROP FUNCTION IF EXISTS audit_log_immutable_trigger();")
