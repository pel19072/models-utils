# ISP Models

## Description

SQLAlchemy ORM models for the ISP vertical (`database_utils/models/isp.py` —
the largest model module): service catalog, subscriber services, network
inventory, topology, and provisioning. Built across Cycles 2–3 of the Uplink
ISP pivot (platform ADRs 002/003/005/006).

## Models (in `database_utils/models/isp.py`; table names in parens)

### Catalog

| Model | Purpose |
|---|---|
| `ServicePlan` (service_plan) | Merged catalog item. `ServicePlanType`; `CatalogKind` is the **hybrid kind** introduced when the legacy CRM `Product` was absorbed by the Cycle 2 catalog merge (revision `c2a_catalog_merge`) |

### Subscriber services

| Model | Purpose |
|---|---|
| `ClientService` (client_service) | A client's subscription to a plan; `ClientServiceStatus`. Absorbed recurring-order billing in `c2b_service_billing`; the dual-write link to legacy `recurring_order` is retained during the rollback window |
| `ServiceSuspension` (service_suspension) | Suspension records with `SuspensionReason` |

### Inventory (ADR-002 hybrid model)

| Model | Purpose |
|---|---|
| `DeviceCategory` (device_category) | **Global SaaS-admin table** (Cycle 3 `c3b` converted it from an enum to a FK table) |
| `DeviceType` (device_type) | Tenant device type catalog |
| `Warehouse` (warehouse) | Stock location |
| `InventoryItem` (inventory_item) | Physical unit |
| `EquipmentEvent` (equipment_event) | Equipment lifecycle events |

### Topology (ADR-003 → Cycle 2 chain model)

| Model | Purpose |
|---|---|
| `Topology` (topology) | A network topology definition |
| `TopologyDeviceType` (topology_device_type) | Per-position device chain (ordered chain, not a graph) |
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
- **CRM models** ([crm-models.md](crm-models.md)): `ClientService` links to
  `Client` and dual-writes legacy `RecurringOrder` rows

## Key Implementation Details

- All models: UUID v4 primary keys + `created_at`/`updated_at`
- `DeviceCategory` is global (SaaS-admin managed), unlike the tenant-scoped
  inventory tables; seeds converge with admin edits (idempotent upserts)
- The topology chain + purpose-keyed playbook map replaced the removed graph
  model as the provisioning source of truth

## Environment Variables

- `POSTGRES_*` / `DATABASE_URL` / `DB_URL` — database connection (via `database.py`)
