"""change_price_and_monetary_fields_to_float

Revision ID: 99ec581fb9d3
Revises: daf2fe3f9539
Create Date: 2026-01-27 22:52:41.540907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99ec581fb9d3'
down_revision: Union[str, Sequence[str], None] = 'daf2fe3f9539'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Change monetary fields from Integer to Float."""
    # Change product.price from Integer to Float
    op.alter_column('product', 'price',
                    existing_type=sa.INTEGER(),
                    type_=sa.Float(),
                    existing_nullable=False)

    # Change order.total from Integer to Float
    op.alter_column('order', 'total',
                    existing_type=sa.INTEGER(),
                    type_=sa.Float(),
                    existing_nullable=False)

    # Change invoice.subtotal from Integer to Float
    op.alter_column('invoice', 'subtotal',
                    existing_type=sa.INTEGER(),
                    type_=sa.Float(),
                    existing_nullable=False)

    # Change invoice.tax from Integer to Float
    op.alter_column('invoice', 'tax',
                    existing_type=sa.INTEGER(),
                    type_=sa.Float(),
                    existing_nullable=False)

    # Change invoice.total from Integer to Float
    op.alter_column('invoice', 'total',
                    existing_type=sa.INTEGER(),
                    type_=sa.Float(),
                    existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema: Revert monetary fields from Float to Integer."""
    # Revert invoice.total from Float to Integer
    op.alter_column('invoice', 'total',
                    existing_type=sa.Float(),
                    type_=sa.INTEGER(),
                    existing_nullable=False)

    # Revert invoice.tax from Float to Integer
    op.alter_column('invoice', 'tax',
                    existing_type=sa.Float(),
                    type_=sa.INTEGER(),
                    existing_nullable=False)

    # Revert invoice.subtotal from Float to Integer
    op.alter_column('invoice', 'subtotal',
                    existing_type=sa.Float(),
                    type_=sa.INTEGER(),
                    existing_nullable=False)

    # Revert order.total from Float to Integer
    op.alter_column('order', 'total',
                    existing_type=sa.Float(),
                    type_=sa.INTEGER(),
                    existing_nullable=False)

    # Revert product.price from Float to Integer
    op.alter_column('product', 'price',
                    existing_type=sa.Float(),
                    type_=sa.INTEGER(),
                    existing_nullable=False)
