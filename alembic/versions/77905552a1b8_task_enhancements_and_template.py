"""task_enhancements_and_template

Revision ID: 77905552a1b8
Revises: 9464159c360b
Create Date: 2026-02-19 17:07:22.424444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77905552a1b8'
down_revision: Union[str, Sequence[str], None] = '9464159c360b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


linked_object_type_enum = sa.Enum('CLIENT', 'ORDER', 'RECURRING_ORDER', name='tasklinkedobjecttype')


def upgrade() -> None:
    """Upgrade schema."""
    linked_object_type_enum.create(op.get_bind(), checkfirst=True)
    op.create_table('task_template',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('task_name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('due_date_offset_days', sa.Integer(), nullable=True),
    sa.Column('default_assignee_ids', sa.JSON(), nullable=True),
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('task', sa.Column('time_spent_minutes', sa.Integer(), nullable=True))
    op.add_column('task', sa.Column('linked_object_type', linked_object_type_enum, nullable=True))
    op.add_column('task', sa.Column('linked_object_id', sa.Uuid(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('task', 'linked_object_id')
    op.drop_column('task', 'linked_object_type')
    op.drop_column('task', 'time_spent_minutes')
    op.drop_table('task_template')
    linked_object_type_enum.drop(op.get_bind(), checkfirst=True)
