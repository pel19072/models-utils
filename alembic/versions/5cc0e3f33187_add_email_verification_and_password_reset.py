"""add_email_verification_and_password_reset

Revision ID: 5cc0e3f33187
Revises: f9a8f43a1cbb
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cc0e3f33187'
down_revision: Union[str, Sequence[str], None] = 'f9a8f43a1cbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add email_verified column to user table; server_default='false' so existing rows are not NULL
    op.add_column(
        'user',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )

    # Create email_verification_token table
    op.create_table(
        'email_verification_token',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )

    # Create password_reset_token table
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('password_reset_token')
    op.drop_table('email_verification_token')
    op.drop_column('user', 'email_verified')
