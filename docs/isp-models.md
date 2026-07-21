# ISP Models

## Description

SQLAlchemy ORM models for the ISP vertical (`database_utils/models/isp.py` —
the largest model module): service catalog, subscriber services, network
inventory, topology, and provisioning. Built across Cycles 2–3 of the Uplink
ISP pivot (platform ADRs 002/003/005/006); Cycle 7 (core config, doc 25,
revision `nc2a_core_config`) added the CORE/EDGE tier axis, the device
management surface, topology pinning, and the subscriber install state machine
— detailed in [network-models.md](network-models.md). Cycle 8 (network UX, doc
26, revision `c8a_playbook_topology`) made playbooks **topology-owned**: the old
`Playbook.target_vendor`/`target_category_id` targeting columns were dropped in
favor of a nullable `Playbook.topology_id`. The service-lifecycle cycle (doc 35,
revisions `bf1_topology_backfill` → `lc1_retire_removal_tmpl`) added the
**service status machine** (`PURPOSE_TO_STATUS`, `ALLOWED_TRANSITIONS`,
`purpose_allowed_for_status`) that backs the per-purpose lifecycle actions.

## Models (in `database_utils/models/isp.py`; table names in parens)

### Catalog

| Model | Purpose |
|---|---|
| `ServicePlan` (service_plan) | Merged catalog item. `ServicePlanType`; `CatalogKind` is the **hybrid kind** introduced when the legacy CRM `Product` was absorbed by the Cycle 2 catalog merge (revision `c2a_catalog_merge`). `provisioning_params` (JSON) holds the plan's playbook parameters as `[{key, value, description, scope}]` — `scope` is `plan` (one shared value) or `service` (declared here, valued on each `ClientService`); a row without `scope` is plan-scoped, so pre-feature rows keep their behaviour |

### Subscriber services

| Model | Purpose |
|---|---|
| `ClientService` (client_service) | A client's subscription to a plan; `ClientServiceStatus`. Absorbed recurring-order billing in `c2b_service_billing`; the dual-write link to legacy `recurring_order` is retained during the rollback window. Cycle 7 (`nc2a`): `install_state` (`INSTALL_STATES` CHECK: NOT_INSTALLED/IN_PROGRESS/INSTALLED, separate from billing `status`, written only by backend-erp's `recompute_install_state`) + `installed_at` (stamped on first INSTALLED, never cleared). Brownfield adoption (doc 30, `ba1_attested_adoption`): `adopted_at` (TIMESTAMPTZ NULL) + `adopted_by_user_id` (UUID FK → `user`, SET NULL, `adopted_by` relationship) + `adoption_note` (VARCHAR NULL) + partial index `ix_client_service_adopted` (`company_id` WHERE `adopted_at IS NOT NULL`) — a persistent attestation FACT substituting for a missing SUCCEEDED activation job inside backend-erp's install_state derivation (never a state, never writes `install_state`, the CHECK is unchanged); writable only via the adopt/un-adopt endpoints behind the ADMIN-only `client_services.adopt` permission; historical `installed_at` may be pre-set at adopt time only when still NULL. `ACTIVATION_EVIDENCE_*` module constants back the backend-computed `activation_evidence` field. Per-service provisioning parameters (`sp1_service_params`): `provisioning_params` (JSON NULL, `[{key, value}]`) holds this service's VALUES for the parameters its plan declares with `scope='service'` — the plan owns the declaration, the service owns only the value, and both resolve to `{{service_plan.<key>}}`. Distinct from `connection_params`, which stays free-form and is not a playbook variable source |
| `ServiceSuspension` (service_suspension) | Suspension records with `SuspensionReason` |

#### Service lifecycle status machine (doc 35)

Module-level constants in `models/isp.py`, next to the purpose constants. They
live **here, not in backend-erp**, because the workflow engine resolves the same
purposes and the import direction is strictly downward (see CLAUDE.md). They are
the single source of truth for both the backend's pre-flight gate and the
frontend's per-purpose action buttons (a button is enabled only when the machine
allows the transition **and** the topology has a playbook for that purpose).

- `PURPOSE_TO_STATUS` — the status each canonical purpose writes:
  `SUSPENSION → SUSPENDED`, `REACTIVATION → ACTIVE`, `DEPROVISION → CANCELLED`,
  and **`ACTIVATION → None`**. `None` is deliberate: activating a service
  *enqueues only*. The `PENDING_INSTALL → ACTIVE` flip is written by backend-erp's
  `recompute_install_state` once the install state reaches `INSTALLED` — i.e.
  after the provisioning job succeeds. Encoding `None` means a caller writing
  `new_status = PURPOSE_TO_STATUS[purpose]` cannot short-circuit that and mark a
  service ACTIVE before the network agrees.
- `ALLOWED_TRANSITIONS` — legal status writes. `PENDING_INSTALL → {ACTIVE,
  CANCELLED}`, `ACTIVE → {SUSPENDED, CANCELLED}`, `SUSPENDED → {ACTIVE,
  CANCELLED}`, and `CANCELLED → {}`: **CANCELLED is terminal**, a cancelled
  service is never revived (re-selling creates a NEW `client_service` row).
  DELETE additionally refuses any non-cancelled service, so cancel is the only
  way out.
- `purpose_allowed_for_status(purpose, current_status) -> bool` — accepts a
  `ClientServiceStatus` or its string value and a purpose in any case/spacing the
  normalizer would take. Four cases:
  1. **ACTIVATION** is special-cased (it writes no status, so it has no target to
     look up): legal **only from `PENDING_INSTALL`**.
  2. **REACTIVATION** is *also* special-cased: it is the exact inverse of
     SUSPENSION, so it is legal **only from `SUSPENDED`**. The generic lookup
     would wrongly allow it from `PENDING_INSTALL`, because its target `ACTIVE`
     happens to be a legal edge out of `PENDING_INSTALL` — but that edge belongs
     to ACTIVATION and is owned by `recompute_install_state`, not by a status
     write. Taking the generic path there would mark a **never-installed service
     ACTIVE and start billing it** (status/`activation_date`/`billing_status`/
     `next_generation_date` all written) for an install that never happened and a
     CPE that was never linked. The legacy `POST /client-services/{id}/reactivate`
     endpoint has always rejected this; both paths share `_apply_reactivation`,
     so they must agree.
  3. Any other canonical purpose — legal iff its target status is in
     `ALLOWED_TRANSITIONS[current_status]`.
  4. A **tenant-defined custom purpose** (purposes are extensible free strings,
     see `TOPOLOGY_PURPOSE_PATTERN`) falls through to `True`: it is enqueue-only
     and writes no status, so there is no transition to police. It must never
     raise — an unknown purpose is normal tenant config, not a bug.

  A `None` purpose or an unparseable status returns `False`.

Covered by `tests/test_service_lifecycle.py`.

### Inventory (ADR-002 hybrid model)

| Model | Purpose |
|---|---|
| `DeviceCategory` (device_category) | **Global SaaS-admin table** (Cycle 3 `c3b` converted it from an enum to a FK table). Cycle 7 (`nc2a`): `tier` (`DEVICE_CATEGORY_TIERS` CHECK: CORE/EDGE; NULL = passives) — admin-editable, backfilled by key |
| `DeviceType` (device_type) | Tenant device type catalog. Cycle 7: `cli_platform` (netmiko platform id, free string; NULL → generic drivers) |
| `Warehouse` (warehouse) | Stock location |
| `InventoryItem` (inventory_item) | Physical unit. Cycle 7 mgmt surface: `mgmt_host`/`mgmt_port`/`cli_protocol` (`CLI_PROTOCOLS` CHECK: ssh/telnet) + worker-stamped `mgmt_last_check_at`/`mgmt_last_check_ok` |
| `EquipmentEvent` (equipment_event) | Equipment lifecycle events |

### Topology (ADR-003 → Cycle 2 chain model)

| Model | Purpose |
|---|---|
| `Topology` (topology) | A network topology definition |
| `TopologyDeviceType` (topology_device_type) | Per-position device chain (ordered chain, not a graph). Cycle 7: `inventory_item_id` (FK, SET NULL) pins the concrete shared CORE device serving the position — pinned positions bypass candidate matching in provisioning resolution |
| `TopologyPlaybook` (topology_playbook) | Cycle 3 `c3a` **purpose-keyed map**: `PURPOSE_ACTIVATION` / `PURPOSE_SUSPENSION` / `PURPOSE_REACTIVATION` / `PURPOSE_DEPROVISION` (validated by `TOPOLOGY_PURPOSE_PATTERN`) |

The earlier free-form network graph (`network_node`/`network_link`) was
**removed** in `c2d_graph_removal`; `schemas/network.py` was deleted with it.

### Provisioning (ADR-005/006)

| Model | Purpose |
|---|---|
| `Playbook` (playbook) | Declarative provisioning steps. Cycle 8 (`c8a`): **topology-owned** — `topology_id` (FK → topology, **ON DELETE CASCADE**, nullable, indexed): NULL = a system/global playbook (the seeded per-company `core_connectivity_check_*`), non-NULL = an inline playbook authored inside that topology's editor, one per purpose. The topology now supplies the device context, so the old `target_vendor`/`target_category_id` columns (+ the `target_category_ref` relationship and `target_category` @property) were removed. CASCADE cleans up an inline playbook on topology delete, but `provisioning_job.playbook_id` is `ON DELETE RESTRICT`, so the backend topology-delete path must clear dependent jobs first (the RESTRICT preserves job history) |
| `ProvisioningJob` (provisioning_job) | Durable job queue row — `ProvisioningJobStatus`, `ProvisioningTrigger`; consumed by backend-erp's `provision-worker` process (SKIP LOCKED claiming) |

## Connections to Other Components

- **backend-erp**: primary consumer (ISP routers + the provisioning worker)
- **Workflow engine** ([workflow-engine.md](workflow-engine.md)): the
  `ENQUEUE_PROVISIONING` step's `use_topology` mode resolves
  topology → purpose → playbook via `utils/provisioning_resolution.py`
- **Seeds**: `alembic/seeds/isp_seed.py` seeds ISP permissions, tier modules,
  purpose-based workflow-template blueprints, and the device_category baseline
  (Cycle 7: baseline entries carry a CORE/EDGE tier; a gated backfill classifies
  pre-nc2a rows only while no row has a tier yet, so admin edits survive re-seeds)
- **CRM models** ([crm-models.md](crm-models.md)): `ClientService` links to
  `Client` and dual-writes legacy `RecurringOrder` rows

## Key Implementation Details

- All models: UUID v4 primary keys + `created_at`/`updated_at`
- `DeviceCategory` is global (SaaS-admin managed), unlike the tenant-scoped
  inventory tables; seeds converge with admin edits (idempotent upserts)
- Cycle-7 value sets are CHECK-constrained strings, never PG enums:
  `DEVICE_CATEGORY_TIERS`, `CLI_PROTOCOLS`, `INSTALL_STATES` (constants in
  `models/isp.py`, SQL fragments byte-identical with the nc2a migration)
- The topology chain + purpose-keyed playbook map replaced the removed graph
  model as the provisioning source of truth

## Environment Variables

- `POSTGRES_*` / `DATABASE_URL` / `DB_URL` — database connection (via `database.py`)
