# models-utils

Shared Python library (package `database-utils`, module `database_utils`) — the
**schema authority** of the Uplink platform. Contains all SQLAlchemy models,
Pydantic schemas, Alembic migrations + seeds, cross-service utilities (JWT,
permissions, audit, SSRF guard), the **workflow engine**, provisioning
resolution, and the transactional email service. Not a running service — no
server, no port.

**This is a critical dependency — changes affect `backend-erp`, `auth-erp`, and `cron-erp`.**

Published to GitHub, consumed pinned by commit SHA:
`database-utils @ git+https://github.com/pel19072/models-utils.git@<sha>`

Docs wiki: [docs/README.md](docs/README.md) · Navigation: [CODEBASE_INDEX.md](CODEBASE_INDEX.md)

## Commands

```bash
pip install -e .                                  # editable local dev
pytest -v                                         # ~66 tests, in-memory SQLite (needs placeholder POSTGRES_* env)
alembic revision --autogenerate -m "description"  # generate revision (needs reachable DB env)
```

## Git Policy

Same feature branch + PR model as all other services. **Never push directly to `main` or `develop`.**

Branch naming: `{type}/{feature-id}/models-{description}` (e.g. `feat/tier-billing/models-subscription`)

Database migrations:
- **Development** = the LOCAL docker compose DB — the `migrate` compose service (built from this repo's `Dockerfile`) runs `alembic upgrade head` + seeds on every `docker compose up` (Railway dev was decommissioned)
- **Production**: GitHub Actions (`.github/workflows/migrate.yml`) runs `alembic upgrade head` against prod `DB_URL` on push to `main` (alembic path filter)

## Migration Workflow (Alembic)

Use the **erp-migration** skill — it covers the full ordered cycle automatically.

Correct order:
1. Create feature branch from `main`
2. Edit model + schema + bump `version` in `setup.cfg`
3. Generate revision: `alembic revision --autogenerate -m "description"`
4. Commit and push feature branch
5. Compose into `develop` (erp-release); the local `migrate` compose service applies the revision on `docker compose up`
6. Pin consuming services (`backend-erp`, `auth-erp`) to the branch commit SHA in their `requirements.txt`
7. After E2E passes locally, merge PR to `main` — GitHub Actions migrates the prod DB

## Key Directories

- `database_utils/models/` — SQLAlchemy models (UUID PKs, created_at/updated_at), registered in `__init__.py` for Alembic autogenerate
  - `auth.py`: Tier, Company, User, Role, Permission, Notification, AuditLog, UserInvitation, EmailVerificationToken, PasswordResetToken, Subscription, PaymentMethod, BillingInvoice, TierChangeRequest
  - `crm.py`: Client, Product (legacy, absorbed by catalog merge), Order, OrderItem, RecurringOrder(+Item) (legacy billing, dual-written; consumed by cron-erp), Invoice, Payment (Cycle 1 ledger), custom fields, TaskState/Task/TaskTemplate, Integration
  - `isp.py` (largest): ServicePlan, ClientService, ServiceSuspension, DeviceCategory, DeviceType, Warehouse, InventoryItem, EquipmentEvent, Topology, TopologyDeviceType, TopologyPlaybook (purpose-keyed), Playbook, ProvisioningJob
  - `workflow.py`: WorkflowTemplate, Workflow, WorkflowTrigger, WorkflowStep, WorkflowStepEdge, WorkflowExecution, WorkflowStepExecution
- `database_utils/schemas/` — 36 Pydantic v2 modules; `__init__.py` star-imports all + `model_rebuild()`
- `database_utils/utils/` — 20 modules; notable: `workflow_engine.py` (trigger matching + DAG execution), `provisioning_resolution.py` (topology→purpose→playbook), `jwt_utils.py`, `permission_utils.py`, `audit_utils.py`, `ssrf.py`, `tier_limits.py`, `timezone_utils.py` (America/Guatemala)
- `database_utils/dependencies/` — `get_db` FastAPI session dependency, audit context
- `database_utils/middleware/` — request-ID/JWT-context logging ASGI middleware
- `database_utils/services/email_service.py` + `database_utils/templates/email/` — transactional email (SMTP via aiosmtplib) + 8 Jinja2 templates (shipped via `[options.package_data]`)
- `database_utils/database.py` — engine bootstrap from `DATABASE_URL`/`DB_URL`/`POSTGRES_*` (raises at import if none)
- `alembic/` — 36 revisions; `env.py` imports all model modules and runs seeds after upgrade
- `alembic/seeds/` — idempotent seed scripts: `rbac_seed.py`, `tier_seed.py`, `isp_seed.py` (importable as `seeds.*` because `env.py` adds the alembic dir to `sys.path`)
- `tests/` — 13 files, ~66 tests (`asyncio_mode = auto`, SQLite)
- `.github/workflows/` — `ci.yml` (migration guard + ruff advisory + pytest), `migrate.yml` (prod migration)
- `Dockerfile` — exists solely for the compose `migrate` one-shot; production images never build it

## Conventions & Gotchas

- **Import direction is strictly downward**: backends import models-utils, never the reverse. Any logic the workflow engine needs (e.g. provisioning resolution) must live HERE, not in backend-erp.
- Every model change ships with an Alembic revision — CI blocks PRs to develop/main otherwise (migration guard).
- **Every seed change ships with a (possibly no-op) revision** — the prod `migrate.yml` workflow is path-filtered on `alembic/**`.
- Seeds must stay idempotent (ON CONFLICT / upsert) so SaaS-admin edits converge.
- Not all migrations are reversible: `c1e_install_actions` uses `ALTER TYPE ... ADD VALUE` (no downgrade).
- Bump `version` in `setup.cfg` for non-trivial changes (NOT `pyproject.toml` — that file only holds build-system config).
- Naming mismatch is historical and intentional: repo `models-utils`, pip package `database-utils`, module `database_utils`.
- Additive schema changes: safe once consuming code is ready. Destructive (drop/rename): all consuming service code must be in production FIRST.
- Test changes from consuming projects (`backend-erp`, `auth-erp`) before publishing.
- Dual-write rollback window is still open: `ClientService` dual-writes into legacy `recurring_order`; don't remove legacy `Product`/`RecurringOrder` paths without checking [docs/limitations.md](docs/limitations.md).

## Recommended Agents and MCP Tools

- **Model/schema implementation**: `python-pro` subagent
- **Library API lookup**: Context7 MCP (`resolve-library-id` → `query-docs`) for SQLAlchemy, Pydantic, and Alembic APIs
- **DB query/performance issues**: `postgres-pro` subagent
- **Python syntax errors** are automatically caught by hooks after every edit
