"""add unique index on order recurring_order_id due_date

Revision ID: f9a8f43a1cbb
Revises: 090ee4ba0ead
Create Date: 2026-05-05 00:49:12.580494

Cleans up duplicate recurring-order generations and enforces uniqueness at the
DB layer. The race in RecurringOrderService.generate_order_from_template
(read-then-write without SELECT FOR UPDATE) allowed two concurrent cron runs
to generate two non-cancelled orders for the same (recurring_order_id, due_date).

Cleanup rule: within each (recurring_order_id, due_date) group, keep one
non-cancelled order. Prefer paid orders; among unpaid, keep the oldest. Cancel
the rest. If two or more orders are paid for the same period, leave them all
non-cancelled (manual review required) — the partial unique index creation
will fail in that case, which is the correct outcome.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a8f43a1cbb'
down_revision: Union[str, Sequence[str], None] = '090ee4ba0ead'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Cancel newer unpaid duplicates per (recurring_order_id, due_date).
    op.execute(
        """
        UPDATE "order"
        SET status = 'CANCELLED'
        WHERE id IN (
            SELECT id FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY recurring_order_id, due_date
                        ORDER BY paid DESC, created_at ASC
                    ) AS rn
                FROM "order"
                WHERE recurring_order_id IS NOT NULL
                  AND status != 'CANCELLED'
            ) ranked
            WHERE rn > 1 AND id IN (
                SELECT id FROM "order" WHERE paid = false
            )
        )
        """
    )

    # 2. Partial unique index. Excludes CANCELLED so historical cancellations
    #    do not collide with new generations for the same period.
    op.create_index(
        "uq_order_active_recurring_due_date",
        "order",
        ["recurring_order_id", "due_date"],
        unique=True,
        postgresql_where=sa.text(
            "status != 'CANCELLED' AND recurring_order_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_order_active_recurring_due_date", table_name="order")
