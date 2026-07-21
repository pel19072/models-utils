# Database Migrations

## Description

Alembic-managed schema migrations for all models in this repo — 48 revisions in
`alembic/versions/` (head: `tk1_new_installation_v4`) — plus the idempotent seed
scripts that run after every upgrade.

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
- **Grandfathered verification**: `t2_grandfather_email_verified` — one-shot backfill marking every pre-overhaul user email-verified so the new login gate cannot lock out existing production users; irreversible by design.
- **Brownfield adoption (doc 30)**: `ba1_attested_adoption` (parent
  `t2_grandfather_email_verified`) — hand-written, nc2a-style
  guarded/idempotent ops with post-upgrade assertions: additive
  `client_service.adopted_at`/`adopted_by_user_id`/`adoption_note` columns +
  FK `fk_client_service_adopted_by_user` (→ `"user"`, SET NULL) + partial
  index `ix_client_service_adopted` (`company_id` WHERE `adopted_at IS NOT
  NULL`) + idempotent `client_services.adopt` permission insert granted to
  the global system ADMIN **only**. Total downgrade (deletes the permission +
  grants, drops index/FK/columns — attestation data is lost on downgrade).
  The seed changes ride this revision: `isp_seed.ADMIN_ONLY_PERMISSIONS` and
  `rbac_seed.MANAGER_EXCLUDED_PERMISSIONS` keep MANAGER excluded at both
  auto-grant sites (subset-pinned by `tests/test_attested_adoption.py`).
- **Client install-field removal (doc 31)**: `cf1_drop_client_install_fields`
  (parent `ba1_attested_adoption`) — hand-written, nc2a/ba1
  house style. **Destructive one-shot** — safe this release only because prod
  is pre-cycle-1: the chain creates the columns in `cd2f0076c709` and drops
  them here in one linear pass. Data cleanup runs BEFORE the DDL: deletes
  `workflow_step` rows whose `UPDATE_FIELD` `action_config` writes
  `installation_status`/`installation_date` (installed new-installation v2
  s3 copies) with edge rerouting (live predecessors → live successors
  through doomed steps, deduped; `workflow_step_execution` rows survive via
  the c2e SET NULL FK + `step_name` snapshot), and deletes clients
  `insight_chart` rows using the `installation_status` dimension/filter
  (deletion over stripping — a stripped spec silently changes meaning).
  Then `ALTER TABLE client DROP COLUMN installation_status/installation_date`
  and `DROP TYPE installationstatus`. Downgrade recreates enum + columns
  (NOT NULL DEFAULT 'NOT_INSTALLED', nullable date) — data NOT restorable.
  Guardrails incl. a quote-agnostic single-head file scan:
  `tests/test_client_install_field_drop.py`. The seed change rides this
  revision: `isp_seed` new-installation v3 drops step s3 + edge s2→s3.
- **Recurrente tenant billing**: `rb1_recurrente_billing` (parent `cf1`) —
  additive only. Adds the `recurrente_*` gateway columns:
  `tier.recurrente_product_id`/`recurrente_price_id`/`recurrente_price_yearly_id`
  (NULL price id = not purchasable online), `company.recurrente_customer_id`
  (lazy, first checkout), `subscription.recurrente_subscription_id` (unique) +
  `recurrente_checkout_id`/`card_last4`/`card_brand`, and
  `billing_invoice.recurrente_intent_id` (unique — webhook charge idempotency).
  Creates the `billing_webhook_event` table (`svix_id` string PK,
  `event_type`, `created_at`) — webhook delivery idempotency log. Fully
  reversible downgrade (drops table + columns).
- **New-installation template v4 (task-context cycle, doc 32)**:
  `tk1_new_installation_v4` (parent `rb1_recurrente_billing`, **head**) —
  schema **no-op** (`upgrade()`/`downgrade()` both pass); it exists so the
  path-filtered prod `migrate.yml` workflow fires and replays seeds. The seed
  change rides this revision: `isp_seed` bumps the `new-installation` blueprint
  to v4 — the installation-fee param moves from the retired legacy Product
  catalog to a **service plan** (param type `service_plan`, key
  `installation_fee_plan_id`), and the `CREATE_ORDER` step item uses
  `service_plan_id` (the engine's preferred resolution). The old required
  `product` param blocked fresh tenants entirely (products have no create path
  anymore, so the required product UUID could never be satisfied). Installed v3
  tenant copies keep running — `product_id` items remain
  deprecated-but-honored during the rollback window.
- **Free/Trial unlimited**: `t1_free_trial_unlimited` — data migration; merges `{max_users,max_products,max_clients} = -1` into Free/Trial `tier.features` and grants the full module list. Product decision: free tier has NO limits until further notice. `tier_seed.py` seeds fresh DBs the same way (now also writes `tier.modules`).
- **Cycle 8 (topology-owned playbooks)**: `c8a_playbook_topology` —
  hand-written (not autogenerate), nc2a-style guarded/idempotent ops
  (`DROP … IF EXISTS`, `ADD COLUMN IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`)
  with in-migration assertions verifying each object's final state, so a re-run
  is a no-op. **Destructive**: drops `playbook.target_vendor` and
  `playbook.target_category_id` (+ its FK `fk_playbook_target_category_id` from
  `c3b`) — safe because the consuming backend/frontend ship in the same release
  and Cycles 1–8 have not reached prod. Adds `playbook.topology_id` (UUID FK →
  `topology.id` **ON DELETE CASCADE**, nullable, indexed
  `ix_playbook_topology_id`): NULL = a system/global playbook, non-NULL = an
  inline playbook owned by that topology. No backfill (existing playbooks keep
  `topology_id` NULL until the topology editor re-saves). The CASCADE removes an
  inline playbook when its topology is deleted but does **not** on its own
  guarantee an orphan-free delete — `provisioning_job.playbook_id` is
  `ON DELETE RESTRICT` (NOT NULL, no topology FK), so the backend
  topology-delete path must first clear dependent `provisioning_job` rows; the
  RESTRICT backstop deliberately preserves job history. Downgrade re-adds the
  dropped columns (shape only — a destructive drop's data is unrecoverable) with
  the RESTRICT FK restored, and drops `topology_id`
- **ISP core**: `cd2f0076c709_isp_platform_core_service_plans_`; plus tenant
  indexes (`a1f2b3c4d5e6`), timezone fixes, and task/workflow/integration modules

- **Namespaced playbook variables**: `pv1_namespaced_variables` — a
  DATA-only revision (no DDL). Rewrites every `{{token}}` in
  `playbook.definition` through the flat→namespaced name map, converts
  `service_plan.provisioning_params` from `{"vlan": 110}` to
  `[{key, value, description}]` rows, and prefixes workflow `action_config`
  variable KEYS with `input.` (values may be `{{trigger.*}}` templates, a
  different namespace, and are left alone). Rewritten playbooks get
  `last_dry_run_version = NULL` so machine-edited device config must be
  re-simulated before it runs live. Idempotent: a second run finds no legacy
  tokens and leaves every row byte-identical. **Not reversible** — the flat
  namespace was ambiguous by construction (which is why it was replaced), and
  the retired unique-category aliases (`onu_serial`, …) cannot be recovered at
  all; they are rewritten to a greppable `RETIRED_ALIAS.*` marker so they fail
  loudly instead of resolving to nothing

- **Per-service provisioning parameters**: `sp1_service_params` — purely
  additive, one nullable JSON column `client_service.provisioning_params`
  holding this service's values for the parameters its plan declares with
  `scope='service'`. `service_plan.provisioning_params` is NOT rewritten: its
  rows gain an optional `scope` and a row without one is plan-scoped, which is
  exactly what every pre-feature row is. Reversible (drops the column).

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
