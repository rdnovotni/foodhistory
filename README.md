# Food History Backend — Phase 1A–1C

This repository is the technical source of truth for the Food History project: taxonomy, database schema, migrations, API contracts, ingestion tooling, research-data conventions, and reference artifacts.

The current implementation turns **Food History Master Taxonomy v1.1** and **Database Schema/Data Dictionary v1.0** into a PostgreSQL-first backend contract. It is intentionally framework-neutral: Django, FastAPI, Rails, Node, Go, or another service can sit on top of the same database and API semantics.

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
- `releases/` — generated delivery archives and preview assets.

## Bootstrap order

1. Create a PostgreSQL database.
2. Run migrations through `0008_foreign_keys_constraints.sql`.
3. Install Python requirements and run `seeds/seed_taxonomy.py`.
4. Run `0009_indexes.sql` through `0012_taxonomy_guards.sql`.
5. Validate the three ingest fixtures against their JSON Schemas.
6. Ingest fixtures into a development database.
7. Implement read endpoints defined by `api/openapi.yaml`.

The complete conceptual design contains 85 tables. The current implementation intentionally starts with the 56 Phase 1 tables.

## Version baseline

- Taxonomy: **v1.1**
- Database schema/data dictionary: **v1.0**
- Phase 1 backend implementation: **v1.0**

Historical claims, uncertain dates, provenance, collector-market values, multilingual names, and source evidence are modeled as first-class research data rather than flattened into unsourced fields.
