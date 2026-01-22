"""replace_custom_field_tables

Revision ID: replace_custom_field_tables
Revises: f612571eaad0
Create Date: 2026-01-22 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'replace_custom_field_tables'
down_revision: Union[str, Sequence[str], None] = 'f612571eaad0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old custom_field table
    op.drop_table('custom_field')

    # Create custom_field_definition table
    op.create_table('custom_field_definition',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('field_key', sa.String(), nullable=False),
        sa.Column('field_type', sa.Enum('TEXT', 'NUMBER', 'EMAIL', 'PHONE', 'URL', 'DATE', 'BOOLEAN', name='customfieldtype'), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create client_custom_field_value table
    op.create_table('client_custom_field_value',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('value', sa.String(), nullable=True),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('field_definition_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['field_definition_id'], ['custom_field_definition.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop new tables
    op.drop_table('client_custom_field_value')
    op.drop_table('custom_field_definition')

    # Recreate old custom_field table
    op.create_table('custom_field',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('table', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('field_type', sa.String(), nullable=False),
        sa.Column('field_value', sa.String(), nullable=True),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Drop the enum type
    op.execute('DROP TYPE customfieldtype')
