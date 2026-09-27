# Identifier and URL conventions

## Internal IDs

Use application-generated UUIDv7 for domain rows. They are opaque and never encode taxonomy, date, ownership or object type.

Taxonomy vocabulary/term seed IDs are a deliberate exception: the seed script uses deterministic UUIDv5 based on stable taxonomy codes so development, staging and production can share identical taxonomy IDs.

## Public IDs

Every `entity` receives a permanent opaque `public_id`. Public IDs never change when labels, taxonomy or slugs change. A production encoder can replace the sample `FH-<UUIDHEX>` form with Crockford Base32 or another checked compact representation, but the public identifier must remain opaque.

## Slugs

`canonical_slug` is human-readable and mutable. Route entities as `/e/{public_id}/{optional-slug}`; resolve on public ID and redirect stale slugs to the current slug. Never make a slug the identity key.

## External identifiers

VIAF, Wikidata, OCLC, ISBN, GTIN, PLU, auction IDs and partner IDs are mappings. They do not replace local identity. Ingestion uses the reserved `external_identifier.scheme_code = ingest-key` for idempotency.
