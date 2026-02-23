"""add_linked_object_type_to_task_template

Revision ID: a2f968506210
Revises: b3c4d5e6f7a8
Create Date: 2026-02-22 15:09:29.195456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2f968506210'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('task_template', sa.Column('linked_object_type', sa.Enum('CLIENT', 'ORDER', 'RECURRING_ORDER', name='tasklinkedobjecttype'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('task_template', 'linked_object_type')
