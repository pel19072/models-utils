# models-utils

Shared Python library containing SQLAlchemy models, Pydantic schemas, and utilities used by both `backend-erp` and `auth-erp`.

Published to GitHub: `git+https://github.com/pel19072/models-utils.git@main`

## This is a critical dependency — changes affect both backend services.

## Commands

```bash
pip install -e .     # Install in editable mode for local dev
```

## Migration Workflow (Alembic)

```bash
cd models-utils
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## After Changing Models

You must update both backend services:
```bash
cd backend-erp  # then repeat for auth-erp
pip uninstall database-utils -y
pip install git+https://github.com/pel19072/models-utils.git@main
pip freeze > requirements.txt
```

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
