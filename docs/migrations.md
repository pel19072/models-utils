# Database Migrations

## Description

Alembic-managed schema migrations for all models in this repo — 41 revisions in
`alembic/versions/` — plus the idempotent seed scripts that run after every
upgrade.

## Goal

Provide a safe, versioned, automated migration path for the single shared
PostgreSQL database across local development and production.

## How migrations run

- **Local development**: the `migrate` service in the root
  `docker-compose.yml` builds this repo's `Dockerfile` and runs
  `alembic upgrade head` on every `docker compose up` (Railway dev was
  decommissioned; local compose is the only dev migration path)
- **Production**: GitHub Actions (`.github/workflows/migrate.yml`) runs
  `alembic upgrade head` against the prod `secrets.DB_URL` on push to `main`.
  The workflow is path-filtered on `alembic/**` (widened to include `env.py`
  and seeds) — so **every seed change must ship with a possibly-no-op
  revision** to trigger it
- **CI migration guard** (`.github/workflows/ci.yml`): PRs that change
  `database_utils/models/**` without adding an `alembic/versions/**` file are
  rejected

## Workflow

1. Modify the model in `database_utils/models/` (on a feature branch from `main`)
2. `alembic revision --autogenerate -m "description"` (needs a reachable DB env)
3. Review the generated revision for correctness
4. Commit; compose into `develop` (erp-release), pin backends to the SHA
5. Local `migrate` service applies it on `docker compose up`; GitHub Actions
   applies it to prod on merge to `main`

Full release mechanics: [deployment-production.md](deployment-production.md).

## Connection configuration

`alembic/env.py` imports all four model modules (for autogenerate) and builds
the DB URL itself from `DATABASE_URL`, `DB_URL`, or the composed `POSTGRES_*`
env vars — the URL is **not** hardcoded in `alembic.ini`.

## Seeds

After `upgrade`, `env.py` runs `_run_seeds(connection)`:

| Seed | Contents |
|---|---|
| `alembic/seeds/rbac_seed.py` | Permissions and roles |
| `alembic/seeds/tier_seed.py` | SaaS tiers |
| `alembic/seeds/isp_seed.py` | ISP permissions, tier modules, purpose-based workflow-template blueprints, device_category baseline (Cycle 7: entries carry a CORE/EDGE tier, column-existence-gated for pre-nc2a positions; a backfill classifies existing rows only while no row has a tier yet, so admin tier edits — including clear-to-NULL — survive re-seeds) |

The modules are importable as `seeds.*` because `env.py` adds the alembic dir to
`sys.path`. All seeds are idempotent (ON CONFLICT / upsert), so re-runs converge
even after SaaS-admin edits.

`scripts/resync_billing_cents.sql` is an ad-hoc billing cents resync helper
(not part of the Alembic chain).

## Notable revision chains

Base revision: `f612571eaad0_initial_schema_with_uuid` (the schema is UUID-native
from the start).

- **Cycle 1 (billing rework)**: `c1a_billing_ddl` → `c1b_backfill` (data
  backfill) → `c1c_payment_ledger` → `c1e_install_actions` → `c1f_verify_grandfather`
- **Cycle 2 (entity merge / topology)**: `c2a_catalog_merge` →
  `c2b_service_billing` (client_service absorbs recurring_order) →
  `c2c_topology_device_chain_playbook` → `c2d_graph_removal` → `c2e_step_exec_snapshot`
- **Cycle 3**: `c3a_topology_purpose_playbooks`, `c3b_device_categories_global_table`
- **Cycle 4 (insights)**: `c4a_insights_dashboards` → `c4b_drop_installation_address`
- **Cycle 5 (network config)**: `nc1a` (five network tables + `ProvisioningJob`
  columns + `PENDING_INFORM` via `ALTER TYPE … ADD VALUE` + 17 permissions) →
  `nc1b` (append-only `device_action_log` trigger)
- **Cycle 7 (core config)**: `nc2a_core_config` — hand-written (not
  autogenerate), additive, guarded/idempotent with in-migration assertions:
  `device_category.tier` (+ key-based backfill, ONU → 'ONU / ONT' rename),
  `device_type.cli_platform`, the `inventory_item` mgmt surface,
  `topology_device_type.inventory_item_id` (FK SET NULL + index),
  `client_service.install_state`/`installed_at` (+ index); three new CHECK
  constraints whose SQL fragments are kept byte-identical with
  `models/isp.py` (guarded by `tests/test_core_config_constants.py`).
  Fully reversible; backfill UPDATEs are convergent (second run = zero rows)
- **ISP core**: `cd2f0076c709_isp_platform_core_service_plans_`; plus tenant
  indexes (`a1f2b3c4d5e6`), timezone fixes, and task/workflow/integration modules

## Key rules

- **Not all migrations are reversible**: `c1e_install_actions` uses
  `ALTER TYPE ... ADD VALUE`, which has no downgrade. Check each revision's
  `downgrade()` before assuming rollback is possible
- Additive changes (new columns/tables): safe to apply before consuming
  service code ships
- Destructive changes (removing/renaming): apply AFTER all consuming service
  code is in production
- Parallel schema features use separate branches/revisions — never combine
  unrelated schema changes

## Environment Variables

- `DATABASE_URL` / `DB_URL` / `POSTGRES_USER`+`POSTGRES_PASSWORD`+`POSTGRES_HOST`+`POSTGRES_PORT`+`POSTGRES_DB` — connection for `alembic/env.py`
