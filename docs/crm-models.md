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

## Environment Variables
- `POSTGRES_*` — Database connection string components
