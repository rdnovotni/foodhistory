# Testing checklist

## Migration tests
- Fresh database can run all Phase 1 migrations in order.
- Taxonomy seed creates 10 vocabularies and 1,392 terms.
- Re-running taxonomy seed is idempotent.
- Foreign keys reject invalid term/entity references.
- `uq_current_holding` permits only one current holding per item.
- duplicate non-null SHA-256 values are rejected.

## Ingestion contract tests
- Each fixture validates against its JSON Schema.
- Re-ingesting the same `source_key` updates rather than duplicates the entity.
- Menu item order survives round trip.
- Printed menu names survive normalization unchanged.
- Cookbook Work/Expression/Manifestation/Item remain distinct.
- Object condition creates a dated assessment rather than mutating identity.

## Research/evidence tests
- Two contradictory assertions can coexist for one predicate.
- One citation can support multiple assertions.
- Evidence roles support/contradict/qualify are all preserved.
- Earliest-occurrence queries do not delete older research when a new earlier source is found.

## Rights/search tests
- restricted entities do not appear in public search.
- alternate/historical names are searchable.
- OCR/transcription full text is searchable.
- taxonomy descendant filters return child concepts without requiring duplicated assignments.
