# Food History — Database and Public Catalogue

This repository is the technical source of truth for the Food History project: taxonomy, database schema, migrations, API contracts, ingestion tooling, research-data conventions, reference artifacts, the public catalogue, and a private editorial wiki foundation.

The current implementation turns **Food History Master Taxonomy v1.1** and **Database Schema/Data Dictionary v1.0** into a PostgreSQL-first backend with a small FastAPI application. The database remains canonical; the application exposes query-only read models and server-rendered catalogue pages without replacing the ingestion or evidence contracts.

## Run the catalogue

The supported development path requires Docker with the Compose plugin:

```console
docker compose up --build
```

Open <http://localhost:8000> for the catalogue or <http://localhost:8000/api/docs> for interactive API documentation. The first run starts PostgreSQL 16, applies the ordered migrations, loads all 1,392 taxonomy terms between migrations 0008 and 0009, loads the three existing synthetic examples, and starts the read-only web application.

The setup service is repeatable. It records applied migration filenames in the existing `food_history.schema_version` table and uses the idempotent taxonomy/fixture loaders. To reset only the local development database, run `docker compose down --volumes`; this removes the Compose-managed database volume.

## Repository contents

- `migrations/` — ordered Phase 1 PostgreSQL migrations.
- `seeds/taxonomy/` — all 1,392 taxonomy terms as CSV plus a manifest.
- `seeds/seed_taxonomy.py` — deterministic taxonomy seeder.
- `api/openapi.yaml` — Phase 1 API contract.
- `ingestion/schemas/` — JSON Schema contracts for menu, cookbook, and object ingest packages.
- `ingestion/examples/` — synthetic validation fixtures; they are not historical claims.
- `ingestion/python/` — transactional/idempotent ingestion skeletons.
- `docs/` — architecture, identifiers, storage, search, ingestion, testing, and deployment guidance.
- `queries/` — reference research/read queries.
- `reference/` — taxonomy and schema/data-dictionary source artifacts.
- `app/` — read-only FastAPI routes, PostgreSQL query layer, templates, and styles.
- `tests/` — API/UI unit tests and PostgreSQL integration tests.
- `compose.yaml` and `Dockerfile` — reproducible local application stack.
- `compose.production.yaml` and `ops/` — private-first self-hosting, backups, monitoring, service units, and a dormant public HTTPS edge.

## Bootstrap order

1. Create a PostgreSQL database.
2. Run migrations through `0008_foreign_keys_constraints.sql`.
3. Install Python requirements and run `seeds/seed_taxonomy.py`.
4. Run `0009_indexes.sql` and all later migrations in lexical order.
5. Validate the three ingest fixtures against their JSON Schemas.
6. Ingest fixtures into a development database.
7. Run the public read application in `app/`.

## Implemented public surface

- Entity browse/detail and evidence-bearing assertions
- Controlled-vocabulary browse/detail, including hierarchy and alternate labels
- Menu detail with ordered sections, original printed text, and normalized food links
- Normalized food menu occurrences
- Bibliographic Work → Expression → Manifestation → Item hierarchy
- Material-culture objects with measurements, marks, production, condition, holdings, provenance, and images
- Unified PostgreSQL search across names, menu text, object marks, and transcriptions
- Reviewed wiki articles with immutable revisions, canonical citations, and entity links
- HTML catalogue views for entities, taxonomy, menus, and search
- Health check and generated interactive API documentation

All public queries enforce `entity.visibility = 'public'`. They return public IDs rather than internal UUIDs, retain original/printed text next to normalized links, and expose evidence as citations attached to assertions. The application now implements every public read resource specified in `api/openapi.yaml`; the three staff ingestion routes remain command-line transactional loaders rather than public web writes.

## Staging

`render.yaml` defines a free, disposable Render preview with a Docker web service and private managed PostgreSQL 16 database. See `docs/STAGING.md` for free-tier limits, provisioning, reviewed-data requirements, smoke testing, backup verification, and the production gate. A durable staging or production environment requires a database plan with backups and retention beyond the free database's 30-day lifetime.

The current public preview is available at [food-history-staging.onrender.com](https://food-history-staging.onrender.com).

## Public self-hosting

`compose.production.yaml` runs PostgreSQL on an internal-only network and binds the editorial application only to host loopback by default. Tailscale can provide private HTTPS access without opening router ports. A disabled `public` profile contains a separate read-only application process and Caddy HTTPS edge for the eventual website launch. Follow `docs/SELF_HOSTING.md` and `docs/WIKI.md`; do not expose the development Compose stack publicly.

## Development without Compose

With Python 3.12 and an already migrated PostgreSQL database:

```console
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://food_history:food_history@127.0.0.1:5432/food_history
python tools/bootstrap_db.py
uvicorn app.main:app --reload
```

Run `pytest -q` for the complete suite when `DATABASE_URL` points at the migrated test database. Without `DATABASE_URL`, the two PostgreSQL integration tests skip. Run `ruff check app tools/bootstrap_db.py tests` for application linting.

The complete conceptual design began with 85 planned research-data tables. The implementation contains 56 Phase 1 research tables plus 8 wiki/editorial tables.

## Version baseline

- Taxonomy: **v1.1**
- Database schema/data dictionary: **v1.0**
- Phase 1 backend implementation: **v1.0**

Historical claims, uncertain dates, provenance, collector-market values, multilingual names, and source evidence are modeled as first-class research data rather than flattened into unsourced fields.
