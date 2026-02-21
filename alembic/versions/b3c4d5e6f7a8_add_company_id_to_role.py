"""add_company_id_to_role

Revision ID: b3c4d5e6f7a8
Revises: 77905552a1b8
Create Date: 2026-02-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = '77905552a1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add company_id to role table for company-scoped custom roles.

    - NULL company_id = global base role (managed by superadmin)
    - Non-NULL company_id = company-specific custom role
    - Removes the global unique constraint on name (uniqueness now enforced in app logic)
    """
    # Add company_id column
    op.add_column('role', sa.Column('company_id', sa.Uuid(), nullable=True))

    # Add FK constraint
    op.create_foreign_key(
        'fk_role_company_id',
        'role', 'company',
        ['company_id'], ['id'],
        ondelete='CASCADE'
    )

    # Add index for efficient lookups by company
    op.create_index('ix_role_company_id', 'role', ['company_id'])

    # Drop the old global unique constraint on name
    # SQLAlchemy names it {table}_{column}_key by default
    op.drop_constraint('role_name_key', 'role', type_='unique')


def downgrade() -> None:
    """Reverse: remove company_id from role table and restore name uniqueness."""
    op.drop_index('ix_role_company_id', table_name='role')
    op.drop_constraint('fk_role_company_id', 'role', type_='foreignkey')
    op.drop_column('role', 'company_id')
    op.create_unique_constraint('role_name_key', 'role', ['name'])
