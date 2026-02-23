"""add_integration_table_and_http_request_step_type

Revision ID: c865c4c8e97a
Revises: a2f968506210
Create Date: 2026-02-23 11:15:32.785448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c865c4c8e97a'
down_revision: Union[str, Sequence[str], None] = 'a2f968506210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create the integration table (with its own IntegrationAuthType enum)
    op.create_table('integration',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('base_url', sa.String(), nullable=False),
    sa.Column('auth_type', sa.Enum('NONE', 'API_KEY', 'BEARER_TOKEN', 'BASIC_AUTH', name='integrationauthtype'), nullable=False),
    sa.Column('credentials', sa.JSON(), nullable=True),
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    # 2. Add HTTP_REQUEST to the stepactiontype enum (PostgreSQL ALTER TYPE)
    op.execute("ALTER TYPE stepactiontype ADD VALUE IF NOT EXISTS 'HTTP_REQUEST'")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the integration table (and its enum)
    op.drop_table('integration')
    op.execute("DROP TYPE IF EXISTS integrationauthtype")
    # NOTE: PostgreSQL does not support removing enum values;
    # HTTP_REQUEST in stepactiontype cannot be automatically rolled back.
