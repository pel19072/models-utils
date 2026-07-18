# ISP Models

## Description

SQLAlchemy ORM models for the ISP vertical (`database_utils/models/isp.py` —
the largest model module): service catalog, subscriber services, network
inventory, topology, and provisioning. Built across Cycles 2–3 of the Uplink
ISP pivot (platform ADRs 002/003/005/006); Cycle 7 (core config, doc 25,
revision `nc2a_core_config`) added the CORE/EDGE tier axis, the device
management surface, topology pinning, and the subscriber install state machine
— detailed in [network-models.md](network-models.md).

## Models (in `database_utils/models/isp.py`; table names in parens)

### Catalog

| Model | Purpose |
|---|---|
| `ServicePlan` (service_plan) | Merged catalog item. `ServicePlanType`; `CatalogKind` is the **hybrid kind** introduced when the legacy CRM `Product` was absorbed by the Cycle 2 catalog merge (revision `c2a_catalog_merge`) |

### Subscriber services

| Model | Purpose |
|---|---|
| `ClientService` (client_service) | A client's subscription to a plan; `ClientServiceStatus`. Absorbed recurring-order billing in `c2b_service_billing`; the dual-write link to legacy `recurring_order` is retained during the rollback window. Cycle 7 (`nc2a`): `install_state` (`INSTALL_STATES` CHECK: NOT_INSTALLED/IN_PROGRESS/INSTALLED, separate from billing `status`, written only by backend-erp's `recompute_install_state`) + `installed_at` (stamped on first INSTALLED, never cleared) |
| `ServiceSuspension` (service_suspension) | Suspension records with `SuspensionReason` |

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
| `Playbook` (playbook) | Declarative provisioning steps |
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
