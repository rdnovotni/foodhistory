# Search design

Start inside PostgreSQL. Do not introduce a separate search cluster until real volume/query data warrants it.

## Retrieval order

1. Exact stable/public/external identifier lookup.
2. Exact preferred or alternate name match.
3. Prefix/name match.
4. Trigram similarity on entity names, taxonomy labels, menu printed names and object marks.
5. Full-text search over OCR/transcriptions and derived document text.
6. Facet filtering by entity type, subject, context, object type, collecting domain, place and date.

## Ranking

Suggested initial weights:

- A: exact preferred label / identifier.
- A: original or historical name exact match.
- B: alternate name / taxonomy label.
- B: menu printed name.
- C: summary / marks / bibliographic statements.
- D: OCR/transcription body text.

Entity visibility and rights must be applied before returning results.

## Taxonomy descendants

At 1,392 terms, a recursive CTE is sufficient for descendant filtering. If taxonomy queries become hot, introduce a derived closure table or materialized view; do not encode ancestry in entity records.

## Search document

Treat any flattened search representation as disposable derived data. The source tables remain canonical.
