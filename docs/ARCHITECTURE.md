# Backend architecture

## 1. System boundaries

**PostgreSQL is the canonical metadata store.** Historical entities, taxonomy assignments, bibliographic hierarchy, menu lines, object measurements, citations, assertions, holdings and provenance are relational data.

**Object storage is the canonical binary store.** TIFF/JPEG/PDF/WAV/MP4/WARC/3D files are never stored as PostgreSQL blobs. `digital_resource` stores their checksum, MIME type, storage URI and technical metadata.

**The taxonomy is data.** The v1.1 taxonomy is loaded into controlled-vocabulary tables. Adding a new collectible domain or subject term should not require a database migration.

**The knowledge graph is controlled, not generic EAV.** `assertion` is reserved for historically variable, contested or evidence-bearing propositions. Menu lines, ingredient lines, measurements and other high-volume structured data have normal tables.

## 2. Service modules

A single modular monolith is the preferred starting shape:

- Catalog: `entity`, names, identifiers, taxonomy assignments.
- Research/Evidence: citations, assertions, observations.
- Places/Agents: people, organizations, places, events.
- Bibliography: Work → Expression → Manifestation → Item.
- Menus: menu, sections, items, normalized-food links.
- Digital: files, representations, transcription.
- Material culture: physical objects, marks, production, measurements, condition.
- Collections: holdings, collections, provenance.
- Economics: historical prices and transactions.

Do not split these into network microservices initially. Their transactions and referential integrity are more valuable than deployment independence at the project's early scale.

## 3. Transaction boundaries

One ingest package is one database transaction. A menu ingest either creates/updates the entity, document/menu subtypes, term assignments and ordered lines together, or commits nothing. The same rule applies to cookbook and object packages.

## 4. Extension strategy

Phase 2 can add specialist bottle/can/match/postcard/restaurant-ware tables, archaeology, scientific analysis, structured recipe ingredients/steps and public contribution workflow without replacing the Phase 1 identity model.
