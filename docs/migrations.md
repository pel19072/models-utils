# Database Migrations

## Description
Alembic-managed database schema migrations for all models defined in models-utils.

## Goal
Provide a safe, versioned, and automated migration path for schema changes across development and production databases.

## Migration Files
Located in `alembic/versions/` — each file is an auto-generated Alembic revision with `upgrade()` and `downgrade()` functions.

## Connections to Other Components
- **auth-erp** and **backend-erp**: Both share the same PostgreSQL database; migrations apply to both
- **GitHub Actions**: Automatically runs `alembic upgrade head` on dev DB when PR to `develop` is opened; on prod DB when merged to `main`
- **Feature branches**: Schema changes committed to feature branch in models-utils; PR to develop triggers migration

## Key Implementation Details
- Migration workflow:
  1. Modify model in `database_utils/models/`
  2. Run `alembic revision --autogenerate -m "description"` to generate revision file
  3. Review generated file for correctness
  4. Commit to feature branch; GitHub Actions applies on push to develop/main
- `alembic.ini`: configured to use `POSTGRES_*` env vars for connection string
- All migrations are reversible (downgrade functions implemented)
- Additive changes (new columns, new tables): safe to apply before consuming service code
- Destructive changes (removing/renaming): apply AFTER all consuming service code is deployed

## Environment Variables
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` — Database connection
