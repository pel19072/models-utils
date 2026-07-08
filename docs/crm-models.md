# CRM Models

## Description

SQLAlchemy ORM models for the CRM domain (`database_utils/models/crm.py`):
clients, orders + the payment ledger, invoices, legacy catalog/recurring
billing, custom fields, the task board, and integrations.

## Goal

Provide a single shared definition for CRM database tables consumed primarily
by backend-erp (and cron-erp for recurring orders).

## Models (in `database_utils/models/crm.py`; table names in parens)

| Model | Purpose |
|-------|---------|
| `Client` (client) | Tenant's subscriber/customer |
| `Product` (product) | **Legacy catalog item** — absorbed by the Cycle 2 catalog merge (`c2a`) into `ServicePlan` with hybrid `CatalogKind`; bridge-less legacy products are treated as SERVICE. Retained during the rollback window |
| `Order` (order) | Customer order — enums include `OrderStatus`, `OrderType`, `PaymentStatus`, plus installation/serviceability fields (`ServiceAvailability`, `InstallationStatus`) |
| `OrderItem` (order_item) | Order line item (`product_id` deprecated but still honored) |
| `RecurringOrder` (recurring_order) + `RecurringOrderItem` | **Legacy billing engine** (`RecurrenceEnum`) — `ClientService` absorbed its billing in Cycle 2 (`c2b`) but still dual-writes here during the rollback window; consumed by cron-erp |
| `Invoice` (invoice) | Customer invoice |
| `Payment` (payment) | **Cycle 1 payment ledger** — `PaymentKind`, `PaymentMethodType` |
| `CustomFieldDefinition` / `ClientCustomFieldValue` | Dynamic per-tenant client fields |
| `TaskState` (task_state) | Kanban column (`TaskStateColor`) |
| `Task` (task) | Work item; assignees via `task_assignee` M2M; `TaskLinkedObjectType` CLIENT/ORDER/RECURRING_ORDER |
| `TaskTemplate` (task_template) | Task blueprint |
| `Integration` (integration) | External API connection — `IntegrationAuthType` NONE/API_KEY/BEARER_TOKEN/BASIC_AUTH |

## Connections to Other Components

- **backend-erp**: primary consumer of all CRM models
- **cron-erp**: consumes `RecurringOrder` for nightly recurring order generation
- **ISP models** ([isp-models.md](isp-models.md)): `ServicePlan` superseded
  `Product`; `ClientService` supersedes `RecurringOrder` billing (dual-write
  link retained)
- **Workflow engine** ([workflow-engine.md](workflow-engine.md)): fires on CRM
  entity events; `CREATE_ORDER`/`CREATE_TASK` steps create these rows;
  `HTTP_REQUEST` steps use `Integration` credentials
- **CRM schemas** ([schemas.md](schemas.md)): Pydantic representations

## Key Implementation Details

- All models: UUID v4 primary key + `created_at`/`updated_at` timestamps
- Cycle 2 dual-write: `ClientService` still writes legacy `recurring_order`
  rows until the rollback window closes (see
  [limitations.md](limitations.md))
- Enums: `OrderStatus`, `OrderType`, `PaymentStatus`, `PaymentKind`,
  `PaymentMethodType`, `RecurrenceEnum`, `ServiceAvailability`,
  `InstallationStatus`, `TaskStateColor`, `TaskLinkedObjectType`,
  `IntegrationAuthType`
- Task assignees: many-to-many with `User` via the `task_assignee` table

## Environment Variables

- `POSTGRES_*` / `DATABASE_URL` / `DB_URL` — database connection (via `database.py`)
