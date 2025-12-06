"""Add super admin support

Revision ID: add_super_admin_support
Revises: 95da85acc5c9
Create Date: 2025-12-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_super_admin_support'
down_revision: Union[str, Sequence[str], None] = '95da85acc5c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make User.company_id nullable
    op.alter_column('user', 'company_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)

    # Add is_super_admin column to User table
    op.add_column('user', sa.Column('is_super_admin', sa.Boolean(),
                                     nullable=False, server_default='false'))

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on audit_log for common queries
    op.create_index('idx_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('idx_audit_log_resource', 'audit_log', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_log_created_at', 'audit_log', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop audit_log indexes and table
    op.drop_index('idx_audit_log_created_at', 'audit_log')
    op.drop_index('idx_audit_log_resource', 'audit_log')
    op.drop_index('idx_audit_log_user_id', 'audit_log')
    op.drop_table('audit_log')

    # Remove is_super_admin column
    op.drop_column('user', 'is_super_admin')

    # Make User.company_id non-nullable again
    # WARNING: This will fail if there are any users with NULL company_id
    op.alter_column('user', 'company_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)
