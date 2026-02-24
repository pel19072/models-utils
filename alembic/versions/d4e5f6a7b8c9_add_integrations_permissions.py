"""add_integrations_permissions

Revision ID: d4e5f6a7b8c9
Revises: c865c4c8e97a
Create Date: 2026-02-24 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c865c4c8e97a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSIONS = [
    ('integrations.create', 'integrations', 'create', 'Create external API integrations'),
    ('integrations.read',   'integrations', 'read',   'View external API integrations'),
    ('integrations.update', 'integrations', 'update', 'Update external API integrations'),
    ('integrations.delete', 'integrations', 'delete', 'Delete external API integrations'),
]


def upgrade() -> None:
    """Insert integrations.* permissions and assign to ADMIN and MANAGER roles."""
    connection = op.get_bind()

    # Insert the four new permissions (idempotent)
    for name, resource, action, description in _PERMISSIONS:
        connection.execute(
            text(
                """
                INSERT INTO permission (id, created_at, name, resource, action, description)
                VALUES (gen_random_uuid(), NOW(), :name, :resource, :action, :description)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {'name': name, 'resource': resource, 'action': action, 'description': description},
        )

    # Assign all four permissions to ADMIN and MANAGER roles (idempotent)
    for role_name in ('ADMIN', 'MANAGER'):
        for perm_name, _, _, _ in _PERMISSIONS:
            connection.execute(
                text(
                    """
                    INSERT INTO role_permission (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM role r, permission p
                    WHERE r.name = :role_name AND p.name = :perm_name
                    ON CONFLICT DO NOTHING
                    """
                ),
                {'role_name': role_name, 'perm_name': perm_name},
            )


def downgrade() -> None:
    """Remove integrations.* permissions."""
    connection = op.get_bind()

    # Remove role_permission associations first
    for name, _, _, _ in _PERMISSIONS:
        connection.execute(
            text(
                "DELETE FROM role_permission WHERE permission_id = (SELECT id FROM permission WHERE name = :name)"
            ),
            {'name': name},
        )

    # Remove the permissions
    for name, _, _, _ in _PERMISSIONS:
        connection.execute(
            text("DELETE FROM permission WHERE name = :name"),
            {'name': name},
        )
