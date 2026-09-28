# Public catalogue application

## Why this stack

The first application is a FastAPI modular monolith with Jinja templates and direct Psycopg queries. This follows the existing Python ingestion runtime, keeps deployment to one process, and makes the established PostgreSQL schema—not an ORM model—a shared contract. It also leaves the existing hand-authored OpenAPI contract and loaders usable by other clients.

## Boundaries

- `app/main.py` owns HTTP routing, validation, error mapping, and HTML views.
- `app/repository.py` builds public read models with parameterized SQL.
- `app/db.py` owns short-lived database connections. A pool can replace this boundary when traffic warrants it.
- `app/templates/` and `app/static/` provide a progressively enhanced, dependency-free public interface.
- All writes continue through the transactional ingestion tools. The public application has no write route.

This remains one deployable service over one canonical database. It does not split catalogue, taxonomy, evidence, or search into separate network services.

## Research-data rules enforced in reads

1. Public endpoints filter restricted entities before returning records or digital representations.
2. URLs and embedded references use `public_id`; database UUIDs never appear in normal responses.
3. Menu items retain `printed_name` and `printed_description` alongside an optional normalized entity.
4. Assertions keep their typed value, uncertainty/status terms, validity strings, and supporting, contradicting, or qualifying citations.
5. EDTF-compatible strings are compared and returned as preserved strings; the application does not invent precise dates.
6. Taxonomy filtering expands descendants with a recursive CTE against the canonical hierarchy.
7. Search documents are computed from canonical tables. Search does not become a second source of truth.

## Routes

The JSON API is under `/v1`. Interactive generated documentation is at `/api/docs`.

| Area | JSON route | HTML route |
| --- | --- | --- |
| Entities | `/v1/entities`, `/v1/entities/{public_id}` | `/entities`, `/entities/{public_id}` |
| Evidence | `/v1/entities/{public_id}/assertions` | Included on entity detail |
| Taxonomy | `/v1/taxonomy/{code}/terms`, `/v1/taxonomy/terms/{code}` | `/taxonomy`, `/taxonomy/{code}` |
| Menus | `/v1/menus/{public_id}` | `/menus/{public_id}` |
| Occurrences | `/v1/foods/{public_id}/menu-occurrences` | JSON only |
| Bibliography | `/v1/works/{public_id}` | `/works/{public_id}` |
| Material culture | `/v1/objects/{public_id}` | `/objects/{public_id}` |
| Search | `/v1/search` | `/search` |
| Operations | `/health` | — |

Entity, occurrence, and search collections use opaque cursors. Invalid cursors return HTTP 400 rather than being interpreted as database values.

## Search behavior

Search starts inside PostgreSQL as required by `SEARCH_DESIGN.md`. Results combine exact label matches, prefixes, trigram similarity over preferred/alternate names, menu printed names and object marks, plus full-text transcription rank. Visibility, entity-type filters, and descendant taxonomy filters are applied before ranking. A dedicated search service should only be introduced after real volume and query measurements justify it.

## Local lifecycle

`docker compose up --build` starts `db`, runs the one-shot `setup` service, and then starts `web`. `tools/bootstrap_db.py` preserves the required migration/seed boundary and records each applied migration in the pre-existing `schema_version` table. `LOAD_EXAMPLES=true` imports only the repository's explicitly synthetic development fixtures.

Production deployments should run setup as a release job, omit `LOAD_EXAMPLES`, supply `DATABASE_URL` from secret management, and place the ASGI service behind TLS termination. The included Render blueprint follows those rules for staging; see `STAGING.md`.
