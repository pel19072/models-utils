"""add tenant (company_id) and hot-path indexes (PERF-1)

Additive only: creates btree indexes on the multi-tenant filter column
(company_id) across every tenant-scoped table, plus two composite hot-path
indexes. Uses CREATE INDEX IF NOT EXISTS / DROP INDEX IF EXISTS so the
migration is idempotent and safe to re-run.

Revision ID: a1f2b3c4d5e6
Revises: 5cc0e3f33187
Create Date: 2026-07-04

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a1f2b3c4d5e6"
down_revision = "5cc0e3f33187"
branch_labels = None
depends_on = None


# (index_name, quoted_table, column_list) for the plain company_id indexes.
_COMPANY_ID_INDEXES = [
    ("ix_client_company_id", '"client"', "company_id"),
    ("ix_product_company_id", '"product"', "company_id"),
    ("ix_recurring_order_company_id", '"recurring_order"', "company_id"),
    ("ix_order_company_id", '"order"', "company_id"),
    ("ix_invoice_company_id", '"invoice"', "company_id"),
    ("ix_custom_field_definition_company_id", '"custom_field_definition"', "company_id"),
    ("ix_task_state_company_id", '"task_state"', "company_id"),
    ("ix_task_company_id", '"task"', "company_id"),
    ("ix_task_template_company_id", '"task_template"', "company_id"),
    ("ix_integration_company_id", '"integration"', "company_id"),
    ("ix_workflow_company_id", '"workflow"', "company_id"),
    ("ix_notification_company_id", '"notification"', "company_id"),
    ("ix_user_invitation_company_id", '"user_invitation"', "company_id"),
    ("ix_payment_method_company_id", '"payment_method"', "company_id"),
    ("ix_tier_change_request_company_id", '"tier_change_request"', "company_id"),
]

# Composite / partial hot-path indexes.
_COMPOSITE_INDEXES = [
    # cron "due recurring orders" scan filters status (+ company_id)
    ("ix_recurring_order_status_company", 'CREATE INDEX IF NOT EXISTS ix_recurring_order_status_company ON "recurring_order" (status, company_id)'),
    # "overdue / delayed-unpaid" dashboard query
    ("ix_order_company_overdue", "CREATE INDEX IF NOT EXISTS ix_order_company_overdue ON \"order\" (company_id, due_date) WHERE paid = false AND status = 'ACTIVE'"),
]

_ALL_INDEX_NAMES = [name for name, _, _ in _COMPANY_ID_INDEXES] + [name for name, _ in _COMPOSITE_INDEXES]


def upgrade() -> None:
    for name, table, col in _COMPANY_ID_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({col})")
    for _name, ddl in _COMPOSITE_INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    for name in _ALL_INDEX_NAMES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
