# Ingestion pipeline

## Stages

1. **Acquire** — receive metadata package and binaries; record original source/partner identifiers.
2. **Validate** — JSON Schema validation, taxonomy-code existence, date syntax, currency codes and required fields.
3. **Hash/store files** — compute SHA-256, write immutable master file, create/reuse `digital_resource`.
4. **Reconcile** — search `external_identifier` first, then authoritative identifiers, then carefully reviewed name/date/place candidates. Never silently merge on fuzzy name alone.
5. **Transactional write** — create/update the canonical entity and typed extension rows inside one database transaction.
6. **Link taxonomy** — add `entity_term_assignment` rows.
7. **Text extraction** — create OCR/transcription versions; do not overwrite source text with normalized text.
8. **Evidence/claims** — create citations/assertions only when the ingest contains source-backed historical claims.
9. **Derived search/index refresh** — after commit.
10. **Review/publish** — move `record_status` from draft → reviewed → published according to editorial workflow.

## Idempotency

Every package carries a `source_key`. The loaders map it to `external_identifier(scheme_code='ingest-key')`. Re-import updates the same canonical entity rather than creating duplicates. Ordered menu rows are rebuilt inside the transaction in the sample loader; production importers may use granular upserts for very large documents.

## Validation fixtures

The JSON files under `examples/` are intentionally synthetic. They test database behavior and must never be presented as historical records.

## Menu mapping

`entity → item → document → menu → menu_section → menu_item`

Preserve `printed_name` and price notation. Link `normalized_food_entity_id` only when identification is sufficient.

## Cookbook mapping

`work → expression → manifestation → item`

Credits and publication statements are separate relations; a signed/annotated physical copy remains an Item-level fact.

## Object mapping

`entity → item → physical_object` plus measurements, marks, production, dated condition, digital representations, holding and provenance. Collector domains are taxonomy assignments, not the object type.
