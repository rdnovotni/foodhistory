# Binary storage and IIIF conventions

## Master storage

Use immutable content-addressed master storage when possible:

`masters/sha256/<first-2>/<next-2>/<full-sha256>`

Keep original filename and MIME type in `digital_resource`. The storage key need not expose a filename.

## Derivatives

Derivatives can be regenerated from a master and should be keyed by master hash plus profile:

`derivatives/<sha256>/<profile>.<ext>`

Examples: `web-2000.jpg`, `thumb-400.jpg`, `ocr.pdf`, `audio-preview.mp3`.

## Representation model

A file is not an object's identity. Link a `digital_resource` to any represented entity using `digital_representation`, with roles such as `front`, `back`, `page`, `detail`, `mark`, `condition` and `provenance`.

## IIIF

Recommended manifest URL:

`/iiif/3/{public_id}/manifest`

For multi-page documents, one canvas per page/image. `transcription_segment.iiif_canvas_uri` and `xywh` can anchor OCR or diplomatic transcription to image regions.

## Integrity

Compute SHA-256 at ingest before publication. The Phase 1 database enforces uniqueness for non-null managed hashes. If a file already exists, create another representation link rather than storing duplicate bytes.
