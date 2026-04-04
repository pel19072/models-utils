# models-utils

Shared Python library containing SQLAlchemy models, Pydantic schemas, and utilities used by both `backend-erp` and `auth-erp`.

Published to GitHub: `git+https://github.com/pel19072/models-utils.git@main`

## This is a critical dependency — changes affect both backend services.

## Commands

```bash
pip install -e .     # Install in editable mode for local dev
```

## Git Policy

Uses the same feature branch + PR model as all other services. **Never push directly to `main`.**

Branch naming: `{type}/{feature-id}/models-{description}` (e.g. `feat/tier-billing/models-subscription`)

GitHub Actions runs `alembic upgrade head` automatically:
- On PR open/push to `develop` → migrates **development** database
- On merge to `main` → migrates **production** database

## Migration Workflow (Alembic)

Use the **erp-migration** skill — it covers the full ordered cycle automatically.

Correct order:
1. Create feature branch from `main`
2. Edit model + schema + bump version in `pyproject.toml`
3. Generate revision: `alembic revision --autogenerate -m "description"`
4. Commit and push feature branch
5. Open PR to `develop` — GitHub Actions migrates dev DB
6. Pin consuming services (`backend-erp`, `auth-erp`) to the feature branch SHA
7. After E2E passes, merge PR to `main` — GitHub Actions migrates prod DB

## After Changing Models (local dev)

Pin consuming services to the feature branch SHA in their `requirements.txt`:
```
database-utils @ git+https://github.com/pel19072/models-utils.git@<sha>
```

After the models-utils PR merges to `main`, update the pin to the new `main` SHA.

## Key Directories

- `database_utils/models/` — SQLAlchemy models
  - `auth.py`: User, Company, Tier, Subscription, BillingInvoice, PaymentMethod, TierChangeRequest
  - `crm.py`: Client, Order, Product, RecurringOrder, Integration
- `database_utils/schemas/` — Pydantic request/response schemas
- `database_utils/utils/` — Shared utilities (JWT, error handling, password hashing, CRUD router factory, tier limits, timezone)
- `alembic/` — Database migration scripts

## Conventions

- Always increment version in `pyproject.toml` for non-trivial changes
- Document breaking changes
- All exports must be well-typed
- Test changes from consuming projects (`backend-erp`, `auth-erp`) before publishing

## Recommended Agents and MCP Tools

- **Model/schema implementation**: `python-pro` subagent
- **Library API lookup**: Context7 MCP (`mcp__context7__resolve-library-id` → `mcp__context7__query-docs`) for SQLAlchemy, Pydantic, and Alembic APIs
- **DB query/performance issues**: `postgres-pro` subagent
- **Python syntax errors** are automatically caught by hooks after every edit
