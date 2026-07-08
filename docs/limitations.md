# Limitations, TODOs, Known Debt

## Transitional / rollback-window debt

- **Dual-write rollback window is still open** (Cycle 2 entity merge):
  - `ClientService` still dual-writes into the legacy `recurring_order` table
    (see the comment near `isp.py:256`).
  - `order_item.product_id` is deprecated but still honored
    (`schemas/order_item.py`).
  - Bridge-less legacy products are treated as `SERVICE` by the workflow
    engine (`workflow_engine.py`, catalog-merge handling).
  - Removal awaits a post-production bake period.
- **Legacy models retained**: `Product`, `RecurringOrder`/`RecurringOrderItem`
  are kept for the transition and because `cron-erp` still consumes
  RecurringOrder for recurring order generation.

## Migrations

- **`c1e_install_actions` is irreversible** — it uses
  `ALTER TYPE ... ADD VALUE`, which PostgreSQL cannot undo; there is no
  working downgrade. Any claim that "all migrations are reversible" is wrong.

## CI / packaging

- **ruff is advisory only** in CI (`continue-on-error: true`) — lint failures
  do not block merges.
- `setup.cfg` still carries the placeholder `author_email = you@example.com`.
- `CHANGELOG.md` has a documented gap: 0.7.0 → 1.10.0 releases were not
  recorded per-version (see the note at the top of that file).
- **Naming mismatch** (repo `models-utils`, package `database-utils`, module
  `database_utils`) is historical and now documented, but still a recurring
  source of confusion.

## Platform-level accepted debt (ADR-009)

- Real device drivers (ssh / telnet / snmp / tr069) are tracked TODOs. They
  will land in backend-erp's provisioning worker; the **resolution logic**
  (topology → purpose → playbook) lives here. The network config layer design
  (platform docs 21/23 — cloud-side drivers, shared GenieACS, netmiko) is
  design-only and not implemented in this repo.

## Architectural constraint (by design, but worth knowing)

- Because backends may never be imported by this library, business logic the
  workflow engine needs keeps migrating *down* into models-utils (e.g.
  `provisioning_resolution.py` moved here in Cycle 3). Expect this "models"
  library to keep accumulating engine-adjacent logic — see
  [architecture.md](architecture.md).
