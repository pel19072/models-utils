# Utilities

## Description

Shared utility modules in `database_utils/utils/` (21 modules) plus the
supporting `dependencies/` and `middleware/` packages. The two largest —
the workflow engine and provisioning resolution — have their own page:
[workflow-engine.md](workflow-engine.md).

## Goal

Eliminate duplication across auth-erp and backend-erp by centralizing common
patterns, and host all logic the workflow engine needs (backends import this
library, never the reverse).

## Utility Modules (in `database_utils/utils/`)

| Module | Purpose |
|------|---------|
| `workflow_engine.py` (58 KB) | Trigger matching + async DAG execution (`check_workflow_triggers`, `execute_workflow`, `execute_step`) — see [workflow-engine.md](workflow-engine.md) |
| `provisioning_resolution.py` | Topology → purpose → playbook + per-chain-position device resolution (moved down from backend-erp in Cycle 3; Cycle 7 adds pinned positions + `device{i}_category_tier`) |
| `jwt_utils.py` | HS256 JWT create/decode. Env: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE` (minutes, default 1440), `REFRESH_TOKEN_EXPIRE`. **Fails fast if `SECRET_KEY` is unset when `ENVIRONMENT=production`**; dev fallback otherwise |
| `permission_utils.py` | `PermissionChecker` and require-permission FastAPI dependencies |
| `audit_utils.py` | `log_create_operation` / `log_update_operation` / `log_delete_operation` / `log_custom_operation` helpers writing `AuditLog` rows |
| `ssrf.py` | `validate_url_no_ssrf` blocklist — shared by the integration-test endpoint and workflow `HTTP_REQUEST` steps (SEC-6) |
| `workflow_fields.py` | Trigger-context variable/field handling for workflow steps |
| `tier_limits.py` | Tier resource-cap enforcement |
| `pagination_utils.py` | Pagination helpers returning `PaginatedResponse[T]` |
| `timezone_utils.py` | `now_gt()` / `today_gt()` — America/Guatemala (UTC-6, no DST) |
| `token_utils.py` | Token generation/validation helpers (email verification, password reset) |
| `password.py` | bcrypt password hashing/verification |
| `order_typing.py` | Order type/classification helpers |
| `json_utils.py` | JSON serialization helpers |
| `email_templates.py` | Jinja2 rendering of the email templates (see [email-service.md](email-service.md)) |
| `error_handling.py` | Error-handling helpers |
| `exception_handlers.py` | Standardized FastAPI exception handlers |
| `logging_utils.py` | Loguru structured JSON logging setup |
| `telemetry_utils.py` | `get_tracer`, `set_request_span_attributes` — OTEL **API only**; SDK/exporter configured by the consuming services |
| `router_factory.py` | FastAPI router factory helpers |

## Related packages

| Path | Purpose |
|---|---|
| `dependencies/db.py` | `get_db` FastAPI session dependency (rollback + close) |
| `dependencies/audit.py` | `AuditContext`, `get_client_ip` (proxy-aware), `get_audit_context[_optional]` |
| `middleware/logging_middleware.py` | `create_logging_middleware` — request-ID + JWT-context + duration ASGI middleware |
| `constants/roles.py` | `Roles` ADMIN/MANAGER/SALES/USER |

## Connections to Other Components

- **auth-erp** and **backend-erp** import these utilities directly
- **JWT utilities**: auth-erp issues tokens; both backends validate with the
  shared `SECRET_KEY`
- **Workflow engine**: fired by backend-erp after CRM/ISP entity mutations
- **Audit utilities**: called by mutation endpoints in both services

## Environment Variables

- `SECRET_KEY`, `ENVIRONMENT`, `ACCESS_TOKEN_EXPIRE`, `REFRESH_TOKEN_EXPIRE` — `jwt_utils.py`
- `POSTGRES_*` / `DATABASE_URL` / `DB_URL` — anything touching the DB (via `database.py`)
- `EMAIL_PROVIDER`, `SMTP_USE_TLS` — email service (see [email-service.md](email-service.md))
