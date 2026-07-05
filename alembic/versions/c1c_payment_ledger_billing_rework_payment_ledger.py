"""billing rework R3: payment ledger table + legacy synthesis + one-valid-invoice rule

Revision ID: c1c_payment_ledger
Revises: c1b_backfill
Create Date: 2026-07-05

Doc 16 §2.4 R3 / §2.5 item 9. DDL + data:
- Creates the append-only `payment` table (§2.1) using the enum types owned by
  R1 (create_type=False).
- Synthesizes one LEGACY ledger row per historically paid order WHERE paid AND
  total_cents > 0 (MAJOR fix: zero-total paid orders — e.g. free installs —
  are skipped; ck_payment_amount_positive would otherwise abort the
  migration). Makes payment_status ledger-derivable with zero legacy
  special-casing beyond the zero-total carve-out.
- Creates uq_invoice_order_valid (partial unique) — safe now that R2
  remediated any duplicate valid invoices.

Rollback (doc 16 §7): before cutover only LEGACY rows exist (re-synthesizable).
After the first real PARTIAL payment R3 is the point of no return —
`pg_dump -t payment` is mandatory before any post-cutover downgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = 'c1c_payment_ledger'
down_revision: Union[str, Sequence[str], None] = 'c1b_backfill'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BATCH = 10_000


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(text("SET lock_timeout = '5s'"))

    # --- payment table (§2.1) — enum types owned by R1, do not re-create ---
    op.create_table(
        'payment',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('invoice_id', sa.Uuid(), nullable=True),
        sa.Column('kind', postgresql.ENUM(name='paymentkind', create_type=False), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('method', postgresql.ENUM(name='paymentmethodtype', create_type=False),
                  server_default='OTHER', nullable=False),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('received_by', sa.Uuid(), nullable=True),
        sa.Column('reverses_payment_id', sa.Uuid(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        # RESTRICT: DB-level guard — orders with money history cannot be deleted.
        sa.ForeignKeyConstraint(['order_id'], ['order.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['received_by'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reverses_payment_id'], ['payment.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('amount_cents > 0', name='ck_payment_amount_positive'),
        sa.CheckConstraint("(kind = 'PAYMENT') = (reverses_payment_id IS NULL)",
                           name='ck_payment_refund_link'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_company_id'), 'payment', ['company_id'], unique=False)
    op.create_index(op.f('ix_payment_order_id'), 'payment', ['order_id'], unique=False)
    op.create_index('ix_payment_company_order', 'payment', ['company_id', 'order_id'], unique=False)
    op.create_index('ix_payment_company_paid_at', 'payment', ['company_id', 'paid_at'], unique=False)

    # --- Legacy ledger synthesis (§2.5.9) — batched, idempotent ---
    with op.get_context().autocommit_block():
        total = 0
        while True:
            result = connection.execute(text("""
                INSERT INTO payment (
                    id, created_at, company_id, order_id, invoice_id, kind,
                    amount_cents, method, reference, paid_at, received_by,
                    reverses_payment_id, notes
                )
                SELECT gen_random_uuid(), NOW(), o.company_id, o.id,
                       NULL, 'PAYMENT', o.total_cents, 'LEGACY',
                       'LEGACY_BACKFILL',
                       COALESCE(o.payment_date, o.created_at), NULL, NULL, NULL
                FROM "order" o
                WHERE o.paid
                  AND o.total_cents > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM payment p
                      WHERE p.order_id = o.id AND p.reference = 'LEGACY_BACKFILL'
                  )
                LIMIT :batch
            """), {"batch": BATCH})
            total += result.rowcount
            if result.rowcount < BATCH:
                break
        print(f"[c1c_payment_ledger] LEGACY_BACKFILL rows synthesized: {total}")

    # --- one-valid-invoice rule, DB-enforced (duplicates remediated in R2) ---
    op.create_index(
        'uq_invoice_order_valid', 'invoice', ['order_id'],
        unique=True, postgresql_where=sa.text('is_valid'),
    )

    # --- Assertions — RAISE on mismatch (rehearsal check e5, doc 16 §6) ---
    failures = []
    missing = connection.execute(text("""
        SELECT COUNT(*) FROM "order" o
        WHERE o.paid AND o.total_cents > 0
          AND NOT EXISTS (SELECT 1 FROM payment p WHERE p.order_id = o.id)
    """)).scalar()
    if missing:
        failures.append(f"paid orders (total_cents>0) without a ledger row: {missing}")
    mismatched = connection.execute(text("""
        SELECT COUNT(*) FROM payment p
        JOIN "order" o ON o.id = p.order_id
        WHERE p.reference = 'LEGACY_BACKFILL' AND p.amount_cents <> o.total_cents
    """)).scalar()
    if mismatched:
        failures.append(f"LEGACY_BACKFILL rows with amount <> order.total_cents: {mismatched}")
    if failures:
        raise RuntimeError("c1c_payment_ledger post-conditions FAILED — " + "; ".join(failures))
    print("[c1c_payment_ledger] all post-condition assertions passed")


def downgrade() -> None:
    """Drop the one-valid-invoice index and the payment table.

    The paymentkind/paymentmethodtype enum types are owned by R1
    (c1a_billing_ddl) and are dropped there. After the first real (non-LEGACY)
    payment this downgrade destroys money history — pg_dump -t payment first
    (doc 16 §7)."""
    op.drop_index('uq_invoice_order_valid', table_name='invoice', postgresql_where=sa.text('is_valid'))
    op.drop_index('ix_payment_company_paid_at', table_name='payment')
    op.drop_index('ix_payment_company_order', table_name='payment')
    op.drop_index(op.f('ix_payment_order_id'), table_name='payment')
    op.drop_index(op.f('ix_payment_company_id'), table_name='payment')
    op.drop_table('payment')
