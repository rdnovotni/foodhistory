# Contributing

Food History is designed as a reviewed historical research database rather than an uncontrolled wiki.

## Changes to taxonomy

- Preserve stable term codes once published.
- Add scope notes for non-obvious terms.
- Keep synonyms, historical spellings, original-language names, and collector terminology as labels/aliases rather than duplicate concepts.
- Use contexts and collecting domains instead of creating combinatorial object types.
- Deprecate published terms rather than silently deleting them.

## Historical claims

Origin stories, firsts, attributions, dates, ownership, and similar historical conclusions should be expressed as evidence-bearing assertions when they are sourced, disputed, uncertain, or historically variable.

Citations should identify the smallest practical locator: page, folio, image, timestamp, archival container, menu line, or object mark.

## Database changes

- Use ordered migrations.
- Do not edit an already-deployed migration to change production history; add a new migration.
- Keep PostgreSQL as the source of truth.
- Avoid universal EAV/JSONB storage for ordinary searchable data.
- Validate taxonomy-branch requirements and referential integrity.
- Run the complete validation workflow before merging.

## Ingestion

Preserve source wording even when normalization is possible. Menu item names, recipe ingredient lines, inscriptions, marks, package text, prices, and transcriptions should retain their original form.

All synthetic fixtures must be clearly identified as synthetic and must never be presented as historical evidence.
