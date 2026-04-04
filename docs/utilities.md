# Utilities

## Description
Shared utility modules for JWT handling, password hashing, audit logging, permission checking, tier limits, pagination, timezone, and workflow engine.

## Goal
Eliminate code duplication across auth-erp and backend-erp by centralizing common patterns.

## Utility Modules (in `database_utils/utils/`)

| File | Purpose |
|------|---------|
| `jwt_utils.py` | JWT token creation (`create_token`), validation (`decode_token`), and payload extraction |
| `password.py` | bcrypt password hashing (`hash_password`) and verification (`verify_password`) |
| `exception_handlers.py` | Standardized FastAPI exception handlers (400, 401, 403, 404, 422, 500) |
| `permission_utils.py` | `@require_permission("resource.action")` FastAPI dependency decorator |
| `audit_utils.py` | `write_audit_log(action, resource_type, resource_id, user_id, ip, details)` helper |
| `router_factory.py` | FastAPI router factory with automatic OTEL span creation per route |
| `tier_limits.py` | `check_tier_limit(resource, company_id, db)` — raises 403 if company exceeds tier cap |
| `pagination_utils.py` | `paginate(query, page, page_size)` — returns `PaginatedResponse` |
| `timezone_utils.py` | `now_gt()` (Guatemala timezone datetime), `today_gt()` (Guatemala date) |
| `workflow_engine.py` | `check_triggers(resource_type, event_type, entity, db)` — evaluates and executes workflows |
| `logging_utils.py` | Loguru structured logging setup with JSON format |

## Connections to Other Components
- **auth-erp** and **backend-erp**: Import and use all utilities
- **JWT utilities**: Used in auth-erp for token issuance; in both services for validation
- **Tier limits**: Reads `Tier.features` and company resource counts from database
- **Workflow engine**: Called by backend-erp after every CRM entity mutation
- **Audit utilities**: Called by all mutation endpoints in both services

## Key Implementation Details
- `require_permission` raises HTTP 403 if token lacks the specified permission string
- `check_tier_limit` queries current count and compares to tier's limit for the resource type
- `now_gt()` and `today_gt()` use `America/Guatemala` timezone (UTC-6, no DST)
- `workflow_engine.check_triggers`: loads active workflows, matches trigger conditions, executes step graph
- `router_factory.py`: wraps each route handler with OTEL span using `resource.action` as span name

## Environment Variables
- `JWT_SECRET` — For `jwt_utils.py`
- `POSTGRES_*` — For `tier_limits.py`, `audit_utils.py`, `workflow_engine.py`
