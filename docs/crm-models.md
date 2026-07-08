# CRM Models

## Description
SQLAlchemy ORM models for all CRM entities: clients, products, orders, invoices, tasks, and integrations.

## Goal
Provide a single shared definition for CRM database tables consumed by backend-erp and referenced for auth validation.

## Models (in `database_utils/models/crm.py`)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Client` | name, tax_id, address, phone, email, contact, observations, company_id, advisor_id | Company customer |
| `Product` | name, price, description, stock, company_id | Catalog item |
| `Order` | due_date, payment_date, total, paid, status (ACTIVE/CANCELLED), company_id, client_id, recurring_order_id | Customer order |
| `OrderItem` | quantity, order_id, product_id | Order line item |
| `RecurringOrder` | recurrence, recurrence_end, next_generation_date, status, client_id | Recurring order template |
| `RecurringOrderItem` | quantity, recurring_order_id, product_id | Template line item |
| `Invoice` | issue_date, subtotal, tax, total, details (JSON), is_valid, company_id, order_id | Customer invoice |
| `CustomFieldDefinition` | field_name, field_key, field_type, is_required, display_order, company_id | Dynamic field schema |
| `ClientCustomFieldValue` | value (string), client_id, field_definition_id | Custom field data |
| `TaskState` | name, color, position, company_id | Kanban column |
| `Task` | name, description, due_date, time_spent_minutes, linked_object_type, linked_object_id, task_state_id | Work item |
| `TaskTemplate` | task_name, due_date_offset_days, default_assignee_ids (JSON), linked_object_type, company_id | Task template |
| `Integration` | name, base_url, auth_type, credentials (JSON), company_id | External API connection |

## Connections to Other Components
- **backend-erp**: Primary consumer of all CRM models
- **auth-erp**: References Client/Order counts for tier limit checks
- **Workflow models**: Workflow triggers reference CRM resource types
- **CRM schemas** (`schemas/`): Pydantic representations of these models

## Key Implementation Details
- All models: UUID primary key + created_at/updated_at timestamps
- `RecurringOrder.status` enum: ACTIVE/PAUSED/INACTIVE/CANCELLED
- `CustomFieldDefinition.field_type` enum: TEXT/NUMBER/EMAIL/PHONE/URL/DATE/BOOLEAN
- `TaskState.color` enum: GRAY/RED/ORANGE/YELLOW/GREEN/BLUE/PURPLE/PINK
- `Task.linked_object_type` enum: CLIENT/ORDER/RECURRING_ORDER
- `Integration.auth_type` enum: NONE/API_KEY/BEARER_TOKEN/BASIC_AUTH
- Task assignees: many-to-many with User via association table

## ISP: Insights dashboards (Cycle 4)

Tenant-defined analytics dashboards live in `database_utils/models/isp.py` (alongside the other ISP models: service plans, client services, device categories, topologies). Each company builds dashboards of simple charts driven off existing entities (clients, orders, client_services, …); chart data is resolved server-side by backend-erp's insights service.

| Model | Table | Key Fields | Purpose |
|-------|-------|-----------|---------|
| `InsightDashboard` | `insight_dashboard` | name, ordering, company_id | A named, company-scoped collection of charts |
| `InsightChart` | `insight_chart` | title, chart_type, spec (JSON), ordering, dashboard_id | One chart within a dashboard |

- **Tenant scope**: `insight_dashboard.company_id` FK → `company.id` (`ondelete=CASCADE`); `Company` exposes an `insight_dashboards` relationship. `insight_chart` has **no** `company_id` — its tenant scope derives via `dashboard_id` → dashboard's `company_id` (same scoping-through-parent pattern as `topology_device_type` → `topology`).
- **Uniqueness**: `UniqueConstraint(company_id, name)` on `insight_dashboard` (`uq_insight_dashboard_company_name`).
- **Cascade**: deleting a dashboard cascades to its charts (`insight_chart.dashboard_id` FK `ondelete=CASCADE` + ORM `delete-orphan`).
- **`InsightChart.chart_type`** enum `InsightChartType`: `NUMBER` / `BAR` / `PIE`.
- **`InsightChart.spec`** JSON shape: `{entity, measure, dimension?, filters?}` where `filters` is a list of `{column, op, value}` clauses — the exact payload backend-erp's `/insights/query` engine accepts, so a saved chart replays verbatim.
- Both tables carry UUID PKs + `created_at`/`updated_at`. Purely additive (revision `c4a_insights_dashboards`).

> **Cycle 4 note:** `Client.installation_address` was removed (revision `c4b_drop_installation_address`). It was intended to be distinct from the billing `address` but was never populated separately; clients now use their single `address`.

> **Cycle 5 Phase 1 note:** the network configuration models (`device_credential`,
> `network_access`, `acs_device_registration`, `provisioning_settings`,
> `device_action_log`) and the `ProvisioningJob` extensions (`PENDING_INFORM` status,
> dry-run / device-lock / heartbeat columns) also live in `isp.py` — documented
> separately in [network-models.md](network-models.md).

## Environment Variables
- `POSTGRES_*` — Database connection string components
