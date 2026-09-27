# API conventions

- Prefix stable endpoints with `/v1`.
- Return public IDs, never internal UUIDs, in the normal public API.
- Use cursor pagination for entity, occurrence and search result sets.
- Return dates as preserved human/EDTF-compatible strings when uncertain; do not serialize invented ISO dates.
- Include printed/original text alongside normalized links.
- Use compact entity references (`public_id`, label, type) when embedding relations.
- Expand evidence only on research/detail endpoints to keep browse payloads small.
- Treat write/ingest endpoints as staff/internal in Phase 1. Public contribution endpoints belong to Phase 2 workflow.
- API resources are read models; they do not need to mirror one database table exactly.
