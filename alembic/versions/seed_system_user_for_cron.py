"""Seed system user for CRON service

Revision ID: seed_cron_user_001
Revises: 4d5c4f653bdb
Create Date: 2025-11-29 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision: str = 'seed_cron_user_001'
down_revision: Union[str, Sequence[str], None] = '4d5c4f653bdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    """
    Create system tier, system company, and system user for CRON service.
    This allows the CRON service to authenticate and process recurring orders.
    """
    # Create a connection to execute raw SQL
    conn = op.get_bind()

    # 1. Check if System tier exists, if not create it
    tier_result = conn.execute(
        sa.text("SELECT id FROM tier WHERE name = 'System'")
    ).fetchone()

    if tier_result:
        tier_id = tier_result[0]
    else:
        # Insert System tier
        tier_insert = conn.execute(
            sa.text(
                "INSERT INTO tier (created_at, name) "
                "VALUES (:created_at, :name) "
                "RETURNING id"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': 'System'
            }
        )
        tier_id = tier_insert.fetchone()[0]

    # 2. Check if System company exists, if not create it
    company_result = conn.execute(
        sa.text("SELECT id FROM company WHERE name = 'System Company'")
    ).fetchone()

    if company_result:
        company_id = company_result[0]
    else:
        # Insert System company
        company_insert = conn.execute(
            sa.text(
                "INSERT INTO company (created_at, name, email, active, tier_id, tax_id, address) "
                "VALUES (:created_at, :name, :email, :active, :tier_id, :tax_id, :address) "
                "RETURNING id"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': 'System Company',
                'email': 'system@internal.erp',
                'active': True,
                'tier_id': tier_id,
                'tax_id': '00-0000000',
                'address': 'Internal System'
            }
        )
        company_id = company_insert.fetchone()[0]

    # 3. Check if CRON system user exists, if not create it
    user_result = conn.execute(
        sa.text("SELECT id FROM \"user\" WHERE email = 'system-cron@internal.erp'")
    ).fetchone()

    if not user_result:
        # Hash the password: CronSystem2025!
        password_hash = pwd_context.hash("CronSystem2025!")

        # Insert CRON system user
        conn.execute(
            sa.text(
                "INSERT INTO \"user\" (created_at, name, email, age, password_hash, role, admin, company_id) "
                "VALUES (:created_at, :name, :email, :age, :password_hash, :role, :admin, :company_id)"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': 'CRON System User',
                'email': 'system-cron@internal.erp',
                'age': 0,
                'password_hash': password_hash,
                'role': 'ADMIN',
                'admin': True,
                'company_id': company_id
            }
        )

    # Commit the transaction
    conn.commit()


def downgrade() -> None:
    """
    Remove system user, company, and tier.
    This is for rollback purposes only - use with caution in production.
    """
    conn = op.get_bind()

    # Delete in reverse order due to foreign key constraints
    conn.execute(
        sa.text("DELETE FROM \"user\" WHERE email = 'system-cron@internal.erp'")
    )
    conn.execute(
        sa.text("DELETE FROM company WHERE name = 'System Company'")
    )
    conn.execute(
        sa.text("DELETE FROM tier WHERE name = 'System'")
    )

    conn.commit()
