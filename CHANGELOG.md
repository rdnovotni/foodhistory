# Changelog

## Catalogue completion v1.2 — 2026-09-27

- Implemented the contracted bibliographic Work hierarchy API and catalogue view.
- Implemented the contracted material-culture Object API and catalogue view.
- Added a staging blueprint with private managed PostgreSQL, pre-deploy migrations, health checks, and platform-port startup.
- Made the preview blueprint explicitly use Render's free web and PostgreSQL plans and documented their disposable, no-backup limits.
- Moved the free preview's idempotent database bootstrap into container startup because Render free services do not support pre-deploy commands.
- Added deployed-catalogue smoke testing and reviewed-data acceptance guidance.

## Public catalogue v1.1 — 2026-09-27

- Added the first runnable FastAPI public catalogue and generated API documentation.
- Added read models and views for entities, evidence, taxonomy, menus, occurrences, and search.
- Added a repeatable PostgreSQL 16 Docker Compose development environment with synthetic examples.
- Added API/UI tests, PostgreSQL integration tests, linting, container validation, and application documentation.
- Added migration 0013 to make taxonomy guards independent of client search paths during ingestion.

## Backend Phase 1 v1.0 — 2026-09-27

- Established PostgreSQL-first Phase 1A–1C implementation.
- Added 56 Phase 1 tables and ordered migrations.
- Added Food History Master Taxonomy v1.1 with 1,392 controlled terms.
- Added assertion/evidence model, bibliographic hierarchy, menu ingestion, material-culture cataloging, provenance, rights, and price-history foundations.
- Added OpenAPI contract, ingest schemas, synthetic fixtures, ingestion loaders, validation tooling, and CI.
