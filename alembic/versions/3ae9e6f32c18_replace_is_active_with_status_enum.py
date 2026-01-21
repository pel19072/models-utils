"""replace_is_active_with_status_enum

Revision ID: 3ae9e6f32c18
Revises: 5e70de00414c
Create Date: 2026-01-20 19:13:01.565677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ae9e6f32c18'
down_revision: Union[str, Sequence[str], None] = '5e70de00414c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Replace is_active boolean with status enum."""
    # Create the ENUM type for RecurringOrderStatus
    recurring_order_status = sa.Enum(
        'ACTIVE', 'PAUSED', 'INACTIVE', 'CANCELLED',
        name='recurringorderstatus'
    )
    recurring_order_status.create(op.get_bind(), checkfirst=True)

    # Add the new status column with a temporary default
    op.add_column(
        'recurring_order',
        sa.Column('status', recurring_order_status, nullable=True)
    )

    # Migrate data: is_active=true -> ACTIVE, is_active=false -> INACTIVE
    op.execute("""
        UPDATE recurring_order
        SET status = CASE
            WHEN is_active = true THEN 'ACTIVE'::recurringorderstatus
            ELSE 'INACTIVE'::recurringorderstatus
        END
    """)

    # Make status NOT NULL now that all rows have values
    op.alter_column('recurring_order', 'status', nullable=False)

    # Drop the old is_active column
    op.drop_column('recurring_order', 'is_active')


def downgrade() -> None:
    """Downgrade schema: Revert status enum back to is_active boolean."""
    # Add back the is_active column
    op.add_column(
        'recurring_order',
        sa.Column('is_active', sa.Boolean(), nullable=True)
    )

    # Migrate data: ACTIVE -> true, others -> false
    op.execute("""
        UPDATE recurring_order
        SET is_active = CASE
            WHEN status = 'ACTIVE' THEN true
            ELSE false
        END
    """)

    # Make is_active NOT NULL with default true
    op.alter_column('recurring_order', 'is_active', nullable=False, server_default=sa.text('true'))

    # Drop the status column
    op.drop_column('recurring_order', 'status')

    # Drop the ENUM type
    sa.Enum(name='recurringorderstatus').drop(op.get_bind(), checkfirst=True)
