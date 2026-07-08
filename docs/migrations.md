# Database Migrations

## Description
Alembic-managed database schema migrations for all models defined in models-utils.

## Goal
Provide a safe, versioned, and automated migration path for schema changes across development and production databases.

## Migration Files
Located in `alembic/versions/` — each file is an auto-generated Alembic revision with `upgrade()` and `downgrade()` functions.

## Current Head

The head revision is **`c4b_drop_installation_address`** (Cycle 4). The most recent linear chain is:

```
c3a_topology_purpose
  -> c3b_device_categories        (Cycle 3: global device_category table)
  -> c4a_insights_dashboards      (Cycle 4: creates insight_dashboard + insight_chart)
  -> c4b_drop_installation_address (Cycle 4: drops client.installation_address)  <-- head
```

- **`c4a_insights_dashboards`** — purely additive; adds the two tenant-scoped Insights tables (`insight_dashboard`, `insight_chart`). No changes to existing tables.
- **`c4b_drop_installation_address`** — drops `client.installation_address`. Safe on production: that column was introduced by `cd2f0076c709` (the isp-platform-core migration), which itself has **not** reached production (the prod head predates it), and it was never populated separately — clients use their single `address`.

## Connections to Other Components
- **auth-erp** and **backend-erp**: Both share the same PostgreSQL database; migrations apply to both
- **Local development**: the `migrate` service in the root `docker-compose.yml` runs `alembic upgrade head` against the local DB on every `docker compose up` (Railway dev was decommissioned)
- **GitHub Actions**: Runs `alembic upgrade head` on the **production** DB when merged to `main`
- **Feature branches**: Schema changes committed to a feature branch in models-utils, then composed into `develop`

## Key Implementation Details
- Migration workflow:
  1. Modify model in `database_utils/models/`
  2. Run `alembic revision --autogenerate -m "description"` to generate revision file
  3. Review generated file for correctness
  4. Commit to feature branch; the local `migrate` service applies it on `docker compose up`, and GitHub Actions applies it to prod on merge to `main`
- `alembic.ini`: configured to use `POSTGRES_*` env vars for connection string
- All migrations are reversible (downgrade functions implemented)
- Additive changes (new columns, new tables): safe to apply before consuming service code
- Destructive changes (removing/renaming): apply AFTER all consuming service code is deployed

## Environment Variables
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB` — Database connection
