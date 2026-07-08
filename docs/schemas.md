# Pydantic Schemas

## Description

Pydantic v2 request/response schemas for all models — 36 modules in
`database_utils/schemas/`, shared between auth-erp and backend-erp to keep API
contracts consistent (frontend-erp consumes the resulting JSON shapes via the
backend proxies).

## Goal

Validate API inputs and serialize API outputs with a single shared schema
definition across services.

## Schema Modules (in `database_utils/schemas/`)

One module per entity. `schemas/__init__.py` star-imports all modules and runs
`model_rebuild()` to resolve circular Order/RecurringOrder references.

| Domain | Modules |
|---|---|
| Auth / tenancy | `user`, `company`, `role`, `permission`, `invitation`, `notification`, `audit_log`, `requests` (Login/Signup), `email_verification`, `password_reset` |
| SaaS billing | `tier`, `subscription`, `payment_method`, `billing_invoice`, `tier_change_request` |
| CRM | `client`, `custom_field`, `order`, `order_item`, `payment`, `invoice`, `product` (legacy), `recurring_order` (legacy), `task`, `task_state`, `task_template`, `integration` |
| ISP | `service_plan`, `client_service`, `inventory`, `topology`, `playbook`, `device_category` |
| Workflow | `workflow`, `workflow_template` |
| Generic | `pagination` — `PaginatedResponse[T]` wrapper |

`schemas/network.py` was **deleted** with the network-graph removal (Cycle 2
`c2d_graph_removal`) — a comment in `__init__.py` records this.

## Connections to Other Components

- **auth-erp** and **backend-erp** import schemas directly from this package
- **Models** ([auth-models.md](auth-models.md), [crm-models.md](crm-models.md),
  [isp-models.md](isp-models.md), [workflow-models.md](workflow-models.md)):
  schemas mirror model fields
- **frontend-erp**: no direct dependency; its API responses are shaped by
  these schemas via the backends

## Key Implementation Details

- `Out` schemas use `from_attributes=True` for ORM compatibility
- Sensitive fields are excluded from `Out` schemas (e.g. `password_hash`,
  integration `credentials`)
- `PaginatedResponse[T]`: generic paginated wrapper
- `order_item.product_id` is deprecated but still honored (catalog-merge
  rollback window — see [limitations.md](limitations.md))
- UUID fields serialize as strings in JSON responses

## Environment Variables

None — schemas are pure Python/Pydantic.
