"""Add RBAC tables and seed default permissions and roles

Revision ID: rbac_system_001
Revises: seed_cron_user_001
Create Date: 2025-11-30 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = 'rbac_system_001'
down_revision: Union[str, Sequence[str], None] = 'seed_cron_user_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create RBAC tables (permission, role, role_permission, user_role)
    Add phone column to company table
    Seed default permissions and roles
    """
    conn = op.get_bind()

    # 1. Create Permission table
    op.create_table(
        'permission',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('resource', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 2. Create Role table
    op.create_table(
        'role',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), default=False, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # 3. Create role_permission association table
    op.create_table(
        'role_permission',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id')
    )

    # 4. Create user_role association table
    op.create_table(
        'user_role',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    # 5. Add phone column to company table
    op.add_column('company', sa.Column('phone', sa.String(), nullable=True))

    # 6. Seed default permissions
    permissions_data = [
        # Client permissions
        {"name": "clients.create", "resource": "clients", "action": "create", "description": "Create new clients"},
        {"name": "clients.read", "resource": "clients", "action": "read", "description": "View client information"},
        {"name": "clients.update", "resource": "clients", "action": "update", "description": "Update client information"},
        {"name": "clients.delete", "resource": "clients", "action": "delete", "description": "Delete clients"},

        # Order permissions
        {"name": "orders.create", "resource": "orders", "action": "create", "description": "Create new orders"},
        {"name": "orders.read", "resource": "orders", "action": "read", "description": "View order information"},
        {"name": "orders.update", "resource": "orders", "action": "update", "description": "Update order information"},
        {"name": "orders.delete", "resource": "orders", "action": "delete", "description": "Delete orders"},

        # Product permissions
        {"name": "products.create", "resource": "products", "action": "create", "description": "Create new products"},
        {"name": "products.read", "resource": "products", "action": "read", "description": "View product information"},
        {"name": "products.update", "resource": "products", "action": "update", "description": "Update product information"},
        {"name": "products.delete", "resource": "products", "action": "delete", "description": "Delete products"},

        # Recurring order permissions
        {"name": "recurring_orders.create", "resource": "recurring_orders", "action": "create", "description": "Create recurring orders"},
        {"name": "recurring_orders.read", "resource": "recurring_orders", "action": "read", "description": "View recurring orders"},
        {"name": "recurring_orders.update", "resource": "recurring_orders", "action": "update", "description": "Update recurring orders"},
        {"name": "recurring_orders.delete", "resource": "recurring_orders", "action": "delete", "description": "Delete recurring orders"},

        # User management permissions
        {"name": "users.create", "resource": "users", "action": "create", "description": "Create new users"},
        {"name": "users.read", "resource": "users", "action": "read", "description": "View user information"},
        {"name": "users.update", "resource": "users", "action": "update", "description": "Update user information"},
        {"name": "users.delete", "resource": "users", "action": "delete", "description": "Delete users"},

        # Role management permissions
        {"name": "roles.create", "resource": "roles", "action": "create", "description": "Create new roles"},
        {"name": "roles.read", "resource": "roles", "action": "read", "description": "View role information"},
        {"name": "roles.update", "resource": "roles", "action": "update", "description": "Update role information"},
        {"name": "roles.delete", "resource": "roles", "action": "delete", "description": "Delete roles"},

        # Permission management permissions
        {"name": "permissions.create", "resource": "permissions", "action": "create", "description": "Create new permissions"},
        {"name": "permissions.read", "resource": "permissions", "action": "read", "description": "View permission information"},
        {"name": "permissions.update", "resource": "permissions", "action": "update", "description": "Update permission information"},
        {"name": "permissions.delete", "resource": "permissions", "action": "delete", "description": "Delete permissions"},

        # Company settings permissions
        {"name": "company.read", "resource": "company", "action": "read", "description": "View company settings"},
        {"name": "company.update", "resource": "company", "action": "update", "description": "Update company settings"},
    ]

    for perm in permissions_data:
        conn.execute(
            sa.text(
                "INSERT INTO permission (created_at, name, resource, action, description) "
                "VALUES (:created_at, :name, :resource, :action, :description)"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': perm['name'],
                'resource': perm['resource'],
                'action': perm['action'],
                'description': perm['description']
            }
        )

    # 7. Create default roles
    roles_data = [
        {"name": "ADMIN", "description": "Administrator with all permissions", "is_system": True},
        {"name": "MANAGER", "description": "Manager with most permissions except system settings", "is_system": True},
        {"name": "SALES", "description": "Sales representative with client and order permissions", "is_system": True},
        {"name": "USER", "description": "Basic user with read-only permissions", "is_system": True},
    ]

    role_ids = {}
    for role_data in roles_data:
        result = conn.execute(
            sa.text(
                "INSERT INTO role (created_at, name, description, is_system) "
                "VALUES (:created_at, :name, :description, :is_system) "
                "RETURNING id"
            ),
            {
                'created_at': datetime.utcnow(),
                'name': role_data['name'],
                'description': role_data['description'],
                'is_system': role_data['is_system']
            }
        )
        role_ids[role_data['name']] = result.fetchone()[0]

    # 8. Assign permissions to roles

    # ADMIN: All permissions
    admin_permissions = conn.execute(
        sa.text("SELECT id FROM permission")
    ).fetchall()

    for perm_row in admin_permissions:
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission_id) "
                "VALUES (:role_id, :permission_id)"
            ),
            {
                'role_id': role_ids['ADMIN'],
                'permission_id': perm_row[0]
            }
        )

    # MANAGER: All permissions except roles, permissions, and company settings
    manager_permissions = conn.execute(
        sa.text(
            "SELECT id FROM permission WHERE resource NOT IN ('roles', 'permissions', 'company')"
        )
    ).fetchall()

    for perm_row in manager_permissions:
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission_id) "
                "VALUES (:role_id, :permission_id)"
            ),
            {
                'role_id': role_ids['MANAGER'],
                'permission_id': perm_row[0]
            }
        )

    # SALES: CRUD on clients, orders, recurring orders, read on products
    sales_permission_names = [
        'clients.create', 'clients.read', 'clients.update', 'clients.delete',
        'orders.create', 'orders.read', 'orders.update', 'orders.delete',
        'recurring_orders.create', 'recurring_orders.read', 'recurring_orders.update', 'recurring_orders.delete',
        'products.read'
    ]

    for perm_name in sales_permission_names:
        perm_row = conn.execute(
            sa.text("SELECT id FROM permission WHERE name = :name"),
            {'name': perm_name}
        ).fetchone()

        if perm_row:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id)"
                ),
                {
                    'role_id': role_ids['SALES'],
                    'permission_id': perm_row[0]
                }
            )

    # USER: Read-only permissions
    user_permission_names = [
        'clients.read', 'orders.read', 'products.read', 'recurring_orders.read'
    ]

    for perm_name in user_permission_names:
        perm_row = conn.execute(
            sa.text("SELECT id FROM permission WHERE name = :name"),
            {'name': perm_name}
        ).fetchone()

        if perm_row:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permission (role_id, permission_id) "
                    "VALUES (:role_id, :permission_id)"
                ),
                {
                    'role_id': role_ids['USER'],
                    'permission_id': perm_row[0]
                }
            )

    # 9. Migrate existing users to new role system
    # Users with admin=True get ADMIN role, others get USER role
    admin_users = conn.execute(
        sa.text("SELECT id FROM \"user\" WHERE admin = true")
    ).fetchall()

    for user_row in admin_users:
        conn.execute(
            sa.text(
                "INSERT INTO user_role (user_id, role_id) "
                "VALUES (:user_id, :role_id)"
            ),
            {
                'user_id': user_row[0],
                'role_id': role_ids['ADMIN']
            }
        )

    regular_users = conn.execute(
        sa.text("SELECT id FROM \"user\" WHERE admin = false OR admin IS NULL")
    ).fetchall()

    for user_row in regular_users:
        conn.execute(
            sa.text(
                "INSERT INTO user_role (user_id, role_id) "
                "VALUES (:user_id, :role_id)"
            ),
            {
                'user_id': user_row[0],
                'role_id': role_ids['USER']
            }
        )

    conn.commit()


def downgrade() -> None:
    """
    Remove RBAC tables and phone column from company
    """
    # Drop tables in reverse order
    op.drop_table('user_role')
    op.drop_table('role_permission')
    op.drop_table('role')
    op.drop_table('permission')

    # Remove phone column from company
    op.drop_column('company', 'phone')
