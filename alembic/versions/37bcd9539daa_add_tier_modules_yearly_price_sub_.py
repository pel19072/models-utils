"""add_tier_modules_yearly_price_sub_billing_cycle

Revision ID: 37bcd9539daa
Revises: d4e5f6a7b8c9
Create Date: 2026-02-26 16:32:39.166056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37bcd9539daa'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add billing_cycle to subscription (per-company chosen cycle)
    op.add_column('subscription', sa.Column('billing_cycle', sa.String(), server_default='MONTHLY', nullable=False))

    # Add price_yearly and modules columns to tier
    op.add_column('tier', sa.Column('price_yearly', sa.Float(), nullable=True))
    op.add_column('tier', sa.Column('modules', sa.JSON(), nullable=True))

    # Change tier.price from INTEGER (cents) to FLOAT (GTQ)
    # USING clause converts existing integer cents values to GTQ floats (divides by 100)
    op.alter_column(
        'tier', 'price',
        existing_type=sa.INTEGER(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='price / 100.0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert tier.price from FLOAT (GTQ) back to INTEGER (cents)
    # USING clause converts GTQ float back to integer cents (multiplies by 100)
    op.alter_column(
        'tier', 'price',
        existing_type=sa.Float(),
        type_=sa.INTEGER(),
        existing_nullable=False,
        postgresql_using='(price * 100)::integer',
    )
    op.drop_column('tier', 'modules')
    op.drop_column('tier', 'price_yearly')
    op.drop_column('subscription', 'billing_cycle')
