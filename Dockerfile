# Local development image for models-utils Alembic migrations.
# Used by the docker-compose `migrate` one-shot service to bring the local
# Postgres up to head before the backends start.
# Production/dev DB migrations on Railway run via GitHub Actions, not this file.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the package (pulls SQLAlchemy, Alembic, psycopg2, etc.) plus the
# working-tree source which carries the alembic/ migration scripts.
COPY . .
RUN pip install --no-cache-dir .

# alembic.ini lives at the repo root; DB_URL is injected by docker-compose.
CMD ["alembic", "upgrade", "head"]
