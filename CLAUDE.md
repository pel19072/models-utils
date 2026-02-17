# models-utils

Shared Python library containing SQLAlchemy models, Pydantic schemas, and utilities used by both `backend-erp` and `auth-erp`.

Published to GitHub: `git+https://github.com/pel19072/models-utils.git@main`

## This is a critical dependency — changes affect both backend services.

## Commands

```bash
pip install -e .     # Install in editable mode for local dev
```

## Git Policy

**Push directly to `main`.** No feature branches or PRs for models-utils.

## Migration Workflow (Alembic)

Use the **erp-migration** skill — it covers the full ordered cycle automatically. **The human never does this manually.**

Correct order:
1. Edit model + schema + bump version
2. Generate revision (`alembic revision --autogenerate`)
3. Push to main
4. Apply migration (`alembic upgrade head`)
5. Run `update_lib` in both backend services

## After Changing Models

Run `update_lib` (bash function in `~/.bashrc`) in **both** backend services:
```bash
cd backend-erp  # then repeat for auth-erp
source venv/bin/activate && source ~/.bashrc && update_lib
```

`update_lib` = `pip uninstall database-utils -y && pip install git+https://github.com/pel19072/models-utils.git@main && pip freeze > requirements.txt`

## Key Directories

- `database_utils/models/` — SQLAlchemy models (`auth.py`: User, Company, Tier; `crm.py`: Client, Order, Product, RecurringOrder)
- `database_utils/schemas/` — Pydantic request/response schemas
- `database_utils/utils/` — Shared utilities (JWT, error handling, password hashing, CRUD router factory)
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
