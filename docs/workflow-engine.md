# Workflow Engine & Provisioning Resolution

## Description

The platform's core automation logic lives in this library:

- `database_utils/utils/workflow_engine.py` (57.7 KB — the largest file in the
  repo): trigger matching and asynchronous DAG execution of workflow steps
- `database_utils/utils/provisioning_resolution.py`: resolution of a topology +
  purpose into a concrete playbook and per-chain-position devices

Data model reference: [workflow-models.md](workflow-models.md) and
[isp-models.md](isp-models.md).

## Why it lives here (import-direction constraint)

backend-erp imports models-utils, **never the reverse** (documented in the
`provisioning_resolution.py` module docstring). Anything the engine needs must
therefore live in this repo — which is why `provisioning_resolution.py` was
moved *down* from backend-erp in Cycle 3, so the engine's
`ENQUEUE_PROVISIONING` step can call it directly.

## Engine flow (`workflow_engine.py`)

1. **Trigger** — backend-erp CRUD routers fire the engine after entity
   mutations via `asyncio.create_task`. `check_workflow_triggers` matches the
   resource type + event (`CREATED`/`UPDATED`/`DELETED`) against active
   `WorkflowTrigger` rows, including their `field_conditions` JSON.
2. **Execution** — `execute_workflow` walks the step DAG
   (`WorkflowStep` + `WorkflowStepEdge`), calling `execute_step` per node and
   recording `WorkflowExecution` / `WorkflowStepExecution` rows.
3. **Step actions** (`StepActionType`):
   - `UPDATE_FIELD` — mutate a field on the trigger entity
   - `CREATE_ENTITY` — create a related entity
   - `HTTP_REQUEST` — call an external `Integration` target; URLs are guarded
     by `utils/ssrf.py` `validate_url_no_ssrf` (SEC-6)
   - `ENQUEUE_PROVISIONING` — enqueue a `ProvisioningJob`; supports the
     `use_topology` **purpose-resolution mode** (Cycle 3) which resolves the
     playbook from the topology's purpose-keyed map instead of a hardcoded id
   - `CREATE_ORDER` — creates an order with **service-plan resolution** and a
     **billing denylist** (Cycle 2/3 additions preventing automation from
     touching billing-critical fields)
   - `CREATE_TASK` — creates a task board item
   (`CREATE_ORDER` and `CREATE_TASK` were added by the irreversible
   `c1e_install_actions` `ALTER TYPE` migration.)
4. **Trigger-context variables** — `utils/workflow_fields.py` handles
   variable/field substitution from the triggering entity's context.

Catalog-merge compatibility: bridge-less legacy products are treated as
`SERVICE` inside the engine (see [limitations.md](limitations.md)).

## Provisioning resolution (`provisioning_resolution.py`)

Given a topology and a purpose (`PURPOSE_ACTIVATION` / `PURPOSE_SUSPENSION` /
`PURPOSE_REACTIVATION` / `PURPOSE_DEPROVISION`), it resolves:

1. the **playbook** from the topology's purpose-keyed `TopologyPlaybook` map
   (Cycle 3 `c3a`), and
2. the **devices** per chain position (`TopologyDeviceType` chain model).

Callers: the workflow engine (`ENQUEUE_PROVISIONING` with `use_topology`) and
backend-erp (provisioning worker + manual provision endpoint).

## Templates

`WorkflowTemplate` rows are globally seeded blueprints
(`alembic/seeds/isp_seed.py`, purpose-based blueprint versions) that tenants install as
concrete workflows — this powers the founder "install automation" flow.

## Tests

`tests/` covers the engine (9 tests), topology purpose resolution (16), and
provisioning resolution (7), plus SSRF (2) — all on in-memory SQLite.
