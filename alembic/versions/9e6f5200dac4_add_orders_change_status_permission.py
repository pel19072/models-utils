"""add_orders_change_status_permission

Revision ID: 9e6f5200dac4
Revises: 384a24a274db
Create Date: 2026-02-07 11:43:55.476637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = '9e6f5200dac4'
down_revision: Union[str, Sequence[str], None] = '384a24a274db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add orders.change_status permission and assign to ADMIN role."""
    connection = op.get_bind()

    # Insert the new permission
    connection.execute(
        text(
            """
            INSERT INTO permission (id, created_at, name, resource, action, description)
            VALUES (gen_random_uuid(), NOW(), 'orders.change_status', 'orders', 'change_status', 'Change order status (cancel/activate) - ADMIN only')
            ON CONFLICT (name) DO NOTHING
            """
        )
    )

    # Assign the permission to ADMIN role
    connection.execute(
        text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r, permission p
            WHERE r.name = 'ADMIN' AND p.name = 'orders.change_status'
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """Remove orders.change_status permission."""
    connection = op.get_bind()

    # Remove role_permission association first
    connection.execute(
        text(
            """
            DELETE FROM role_permission
            WHERE permission_id = (SELECT id FROM permission WHERE name = 'orders.change_status')
            """
        )
    )

    # Remove the permission
    connection.execute(
        text("DELETE FROM permission WHERE name = 'orders.change_status'")
    )
