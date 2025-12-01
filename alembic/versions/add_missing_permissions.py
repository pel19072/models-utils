"""Add missing field-level and action permissions

Revision ID: add_missing_permissions
Revises: 33a329dd038b
Create Date: 2025-11-30 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = 'add_missing_permissions'
down_revision: Union[str, Sequence[str], None] = '33a329dd038b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add missing field-level permissions for products and company,
    and recurring_orders.generate permission
    """
    conn = op.get_bind()

    # New permissions to add
    new_permissions = [
        # Recurring Orders - Generate action
        {"name": "recurring_orders.generate", "resource": "recurring_orders", "action": "generate", "description": "Manually generate orders from recurring templates"},

        # Products - Field-level permissions
        {"name": "products.update_name", "resource": "products", "action": "update_name", "description": "Update product name"},
        {"name": "products.update_price", "resource": "products", "action": "update_price", "description": "Update product price"},
        {"name": "products.update_description", "resource": "products", "action": "update_description", "description": "Update product description"},

        # Company - Field-level permissions
        {"name": "company.update_name", "resource": "company", "action": "update_name", "description": "Update company name"},
        {"name": "company.update_email", "resource": "company", "action": "update_email", "description": "Update company email"},
        {"name": "company.update_phone", "resource": "company", "action": "update_phone", "description": "Update company phone"},
        {"name": "company.update_address", "resource": "company", "action": "update_address", "description": "Update company address"},
        {"name": "company.update_tier", "resource": "company", "action": "update_tier", "description": "Update company subscription tier"},

        # Roles - Assign permissions action
        {"name": "roles.assign_permissions", "resource": "roles", "action": "assign_permissions", "description": "Assign permissions to roles"},
    ]

    # Insert new permissions
    permission_ids = {}
    for perm in new_permissions:
        result = conn.execute(
            sa.text(
                "INSERT INTO permission (created_at, name, resource, action, description) "
                "VALUES (:created_at, :name, :resource, :action, :description) "
                "RETURNING id"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': perm['name'],
                'resource': perm['resource'],
                'action': perm['action'],
                'description': perm['description']
            }
        )
        permission_ids[perm['name']] = result.fetchone()[0]

    # Get ADMIN role ID
    admin_role = conn.execute(
        sa.text("SELECT id FROM role WHERE name = 'ADMIN'")
    ).fetchone()

    if admin_role:
        admin_role_id = admin_role[0]

        # Assign all new permissions to ADMIN role
        for perm_name, perm_id in permission_ids.items():
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id)"
                ),
                {
                    'role_id': admin_role_id,
                    'permission_id': perm_id
                }
            )

    # Get MANAGER role ID and assign relevant permissions
    manager_role = conn.execute(
        sa.text("SELECT id FROM role WHERE name = 'MANAGER'")
    ).fetchone()

    if manager_role:
        manager_role_id = manager_role[0]

        # MANAGER gets all product and recurring_orders permissions, but NOT company permissions
        manager_permission_names = [
            'recurring_orders.generate',
            'products.update_name',
            'products.update_price',
            'products.update_description',
        ]

        for perm_name in manager_permission_names:
            if perm_name in permission_ids:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permission (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id)"
                    ),
                    {
                        'role_id': manager_role_id,
                        'permission_id': permission_ids[perm_name]
                    }
                )

    # Get SALES role ID and assign relevant permissions
    sales_role = conn.execute(
        sa.text("SELECT id FROM role WHERE name = 'SALES'")
    ).fetchone()

    if sales_role:
        sales_role_id = sales_role[0]

        # SALES gets recurring_orders.generate permission
        sales_permission_names = ['recurring_orders.generate']

        for perm_name in sales_permission_names:
            if perm_name in permission_ids:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permission (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id)"
                    ),
                    {
                        'role_id': sales_role_id,
                        'permission_id': permission_ids[perm_name]
                    }
                )

    conn.commit()


def downgrade() -> None:
    """
    Remove the added permissions
    """
    conn = op.get_bind()

    permission_names = [
        'recurring_orders.generate',
        'products.update_name',
        'products.update_price',
        'products.update_description',
        'company.update_name',
        'company.update_email',
        'company.update_phone',
        'company.update_address',
        'company.update_tier',
        'roles.assign_permissions',
    ]

    for perm_name in permission_names:
        conn.execute(
            sa.text("DELETE FROM permission WHERE name = :name"),
            {'name': perm_name}
        )

    conn.commit()
