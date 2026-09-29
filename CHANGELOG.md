# Changelog

## Reusable article structures v1.6 — 2026-09-29

- Added versioned editorial templates for dishes, ingredients, restaurants, people, companies, books, and objects, with revision provenance and an append-only template migration path.
- Added canonical-record infoboxes and reusable notice, quotation, sidebar, gallery, comparison, timeline, map, source excerpt, recipe transcription, menu excerpt, historical-price, contested-history, and bibliography blocks.
- Structured blocks resolve only public canonical records and render through the existing server-side sanitizer and public-reader boundary.

## Wiki reading and navigation v1.5 — 2026-09-29

- Added automatic article outlines, category breadcrumbs, internal wiki links with editor autocomplete, published backlinks, and redirect-aware link resolution.
- Added related articles, series and collection navigation, disambiguation pages, public redirects, permanent published-revision links, public history, and page information.
- Added print and focus layouts, reading-time estimates, random and date-based discovery, recent publication and improvement lists, glossary popovers, article previews, and footnote previews.
- Kept backlink and related-article API responses aligned with the public schema, made autocomplete safe during rapid typing, and rendered resolved link labels in article outlines.

## Wiki authoring v1.4 — 2026-09-28

- Added private searchable pickers for canonical entities, citations, and managed images.
- Added validated, content-addressed image uploads with required alternative text and revision-specific presentation metadata.
- Added revision-specific categories, public category browsing, and PostgreSQL full-text article search.
- Added complete revision history and side-by-side Markdown comparison.
- Added persistent shared media storage plus paired database/media backup and restore operations.
- Added published-only category and media views while revoking draft/media-link tables from the public database role.
- Added citation-first starter briefs for the first three editorial articles without inventing unsourced historical claims.

## Wiki foundation v1.3 — 2026-09-28

- Added private editorial accounts with scrypt password hashes, opaque expiring sessions, role checks, and CSRF protection.
- Added immutable wiki revisions, append-only review events, stable pages and redirects, entity links, and canonical citation links.
- Added Markdown drafting and sanitized preview, draft/review/approval/publication workflow, and public wiki HTML/API reads.
- Split production into a loopback-only editorial process and a separately profiled public read process with no editor routes.
- Added owner-account tooling, Wiki architecture and operating documentation, tests, and API contract updates.

## Catalogue completion v1.2 — 2026-09-27

- Implemented the contracted bibliographic Work hierarchy API and catalogue view.
- Implemented the contracted material-culture Object API and catalogue view.
- Added a staging blueprint with private managed PostgreSQL, pre-deploy migrations, health checks, and platform-port startup.
- Made the preview blueprint explicitly use Render's free web and PostgreSQL plans and documented their disposable, no-backup limits.
- Moved the free preview's idempotent database bootstrap into container startup because Render free services do not support pre-deploy commands.
- Fixed platform startup to resolve the application package from the repository root.
- Deployed and smoke-tested the public Render preview at `food-history-staging.onrender.com`.
- Added deployed-catalogue smoke testing and reviewed-data acceptance guidance.
- Added a hardened private-first self-hosting stack with Tailscale-ready access, private PostgreSQL networking, guarded backup/restore tooling, health checks, update automation, boot recovery, and a disabled public HTTPS profile for the later website launch.

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
