-- resync_billing_cents.sql
-- Re-runnable version of the c1b_backfill (R2) UPDATE set (doc 16 §2.4/§2.5).
--
-- Purpose: repair dual-window drift — rows written by an old backend build
-- (floats/paid only) between the models migration and the backend deploy, or
-- during a temporary rollback to a pre-Cycle-1 build. Referenced by R4
-- (c1d_tighten, follow-up branch feat/billing-rework/models-tighten), which
-- runs it before SET NOT NULL / CHECK tightening.
--
-- Safe to run at any time, any number of times:
--   * every statement is guarded (IS NULL / convergent state) — rows already
--     in cents are never touched, so ledger-written values are preserved;
--   * conversion is ROUND(x::numeric * 100)::bigint, identical to R2.
--
-- Usage: psql "$DB_URL" -f scripts/resync_billing_cents.sql
--        (wrap in a transaction if desired: psql --single-transaction)

-- §2.5.1 order.total_cents — copied from the Float, never recomputed from items.
UPDATE "order"
SET total_cents = ROUND(total::numeric * 100)::bigint
WHERE total_cents IS NULL;

-- §2.5.2 invoice — identity-preserving: subtotal derived so that
-- subtotal_cents + tax_cents = total_cents holds exactly.
UPDATE invoice
SET tax_cents      = ROUND(tax::numeric * 100)::bigint,
    total_cents    = ROUND(total::numeric * 100)::bigint,
    subtotal_cents = ROUND(total::numeric * 100)::bigint
                     - ROUND(tax::numeric * 100)::bigint
WHERE total_cents IS NULL;

-- §2.5.3 catalog money (NULL stays NULL).
UPDATE product
SET price_cents = ROUND(price::numeric * 100)::bigint
WHERE price_cents IS NULL AND price IS NOT NULL;

UPDATE service_plan
SET price_cents = ROUND(price::numeric * 100)::bigint
WHERE price_cents IS NULL AND price IS NOT NULL;

UPDATE inventory_item
SET cost_cents = ROUND(cost::numeric * 100)::bigint
WHERE cost_cents IS NULL AND cost IS NOT NULL;

-- §2.5.4 order_item snapshots from CURRENT product price/name (best-effort;
-- historical amount truth stays in order.total_cents).
UPDATE order_item oi
SET unit_price_cents = ROUND(p.price::numeric * 100)::bigint,
    product_name     = p.name
FROM product p
WHERE oi.product_id = p.id
  AND oi.unit_price_cents IS NULL;

-- §2.5.5 payment_status / order_type coherence with the boolean/FK world.
-- NOTE: only lifts PENDING->PAID for legacy-style rows; it never demotes
-- PARTIAL/REFUNDED states written by the payment ledger.
UPDATE "order"
SET payment_status = 'PAID'
WHERE paid AND payment_status = 'PENDING';

UPDATE "order"
SET order_type = 'RECURRING'
WHERE recurring_order_id IS NOT NULL AND order_type <> 'RECURRING';

-- §2.5.6 order.client_service_id via the recurring bridge — unambiguous
-- (exactly one client_service per recurring order) mappings only.
UPDATE "order" o
SET client_service_id = b.cs_id
FROM (
    SELECT recurring_order_id AS ro_id, MIN(id::text)::uuid AS cs_id
    FROM client_service
    WHERE recurring_order_id IS NOT NULL
    GROUP BY recurring_order_id
    HAVING COUNT(*) = 1
) b
WHERE o.recurring_order_id = b.ro_id
  AND o.client_service_id IS NULL;

-- §2.5.7 payment_date for paid orders (revenue-chart date basis).
UPDATE "order" o
SET payment_date = COALESCE(
    (SELECT MAX(i.created_at) FROM invoice i
     WHERE i.order_id = o.id AND i.is_valid),
    o.created_at
)
WHERE o.paid AND o.payment_date IS NULL;

-- §2.5.8 duplicate valid invoices: keep newest, invalidate the rest.
-- (No-op once uq_invoice_order_valid exists — kept for pre-R3 windows.)
UPDATE invoice
SET is_valid = false
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY created_at DESC, id DESC
        ) AS rn
        FROM invoice WHERE is_valid
    ) t
    WHERE rn > 1
);
