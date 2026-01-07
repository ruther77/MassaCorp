"""Fix restaurant_consumptions schema to match model.

Revision ID: t0a17n3s5o7q
Revises: s9p16m2r4n5q
Create Date: 2026-01-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 't0a17n3s5o7q'
down_revision: Union[str, None] = 's9p16m2r4n5q'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    consumption_type = postgresql.ENUM(
        'VENTE', 'PERTE', 'REPAS_STAFF', 'OFFERT',
        name='restaurant_consumption_type',
        create_type=False
    )
    op.execute("CREATE TYPE restaurant_consumption_type AS ENUM ('VENTE', 'PERTE', 'REPAS_STAFF', 'OFFERT')")

    # Drop old columns
    op.drop_column('restaurant_consumptions', 'date_consumption')
    op.drop_column('restaurant_consumptions', 'quantity')
    op.drop_column('restaurant_consumptions', 'unit_cost')
    op.drop_column('restaurant_consumptions', 'is_loss')

    # Add new columns matching the model
    op.add_column('restaurant_consumptions', sa.Column('type', consumption_type, nullable=False, server_default='VENTE'))
    op.add_column('restaurant_consumptions', sa.Column('quantite', sa.BigInteger(), nullable=False, server_default='1'))
    op.add_column('restaurant_consumptions', sa.Column('prix_vente', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('restaurant_consumptions', sa.Column('cout', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('restaurant_consumptions', sa.Column('date', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')))

    # Remove server defaults after adding columns
    op.alter_column('restaurant_consumptions', 'type', server_default=None)
    op.alter_column('restaurant_consumptions', 'quantite', server_default=None)
    op.alter_column('restaurant_consumptions', 'prix_vente', server_default=None)
    op.alter_column('restaurant_consumptions', 'cout', server_default=None)
    op.alter_column('restaurant_consumptions', 'date', server_default=None)


def downgrade() -> None:
    # Drop new columns
    op.drop_column('restaurant_consumptions', 'date')
    op.drop_column('restaurant_consumptions', 'cout')
    op.drop_column('restaurant_consumptions', 'prix_vente')
    op.drop_column('restaurant_consumptions', 'quantite')
    op.drop_column('restaurant_consumptions', 'type')

    # Drop enum
    op.execute("DROP TYPE restaurant_consumption_type")

    # Restore old columns
    op.add_column('restaurant_consumptions', sa.Column('date_consumption', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE')))
    op.add_column('restaurant_consumptions', sa.Column('quantity', sa.BigInteger(), nullable=False, server_default='1'))
    op.add_column('restaurant_consumptions', sa.Column('unit_cost', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('restaurant_consumptions', sa.Column('is_loss', sa.Boolean(), nullable=False, server_default='false'))
