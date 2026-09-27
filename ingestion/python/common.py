from __future__ import annotations

import re
import secrets
import time
import uuid
from pathlib import PurePosixPath

UUID7_MASK_48 = (1 << 48) - 1


def uuid7() -> uuid.UUID:
    """Portable UUIDv7 generator for Python versions without uuid.uuid7()."""
    ms = int(time.time_ns() // 1_000_000) & UUID7_MASK_48
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)


def public_id(u: uuid.UUID) -> str:
    """Opaque public identifier. Production may replace the display encoding, not the identity."""
    return "FH-" + u.hex.upper()


def slugify(value: str) -> str:
    s = value.casefold().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:105] or "record"


def get_term_id(cur, code: str):
    cur.execute("SELECT term_id FROM food_history.taxonomy_term WHERE code=%s", (code,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Unknown taxonomy code: {code}")
    return row[0]


def find_by_ingest_key(cur, source_key: str):
    cur.execute(
        """
        SELECT e.entity_id, e.public_id
        FROM food_history.external_identifier x
        JOIN food_history.entity e ON e.entity_id=x.entity_id
        WHERE x.scheme_code='ingest-key' AND x.identifier_value=%s
        """,
        (source_key,),
    )
    return cur.fetchone()


def ensure_entity(cur, *, source_key: str, type_code: str, label: str, summary=None, status="draft"):
    """Idempotently create/update an entity using the ingest-key mapping."""
    found = find_by_ingest_key(cur, source_key)
    type_id = get_term_id(cur, type_code)
    if found:
        eid, pid = found
        cur.execute(
            """
            UPDATE food_history.entity
            SET preferred_label=%s, summary=%s, entity_type_term_id=%s, updated_at=now()
            WHERE entity_id=%s
            """,
            (label, summary, type_id, eid),
        )
        return eid, pid, "updated"

    eid = uuid7()
    pid = public_id(eid)
    slug = f"{slugify(label)}-{eid.hex[:8]}"
    cur.execute(
        """
        INSERT INTO food_history.entity(
            entity_id, public_id, entity_type_term_id, preferred_label,
            canonical_slug, summary, record_status, visibility
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,'public')
        """,
        (eid, pid, type_id, label, slug, summary, status),
    )
    cur.execute(
        """
        INSERT INTO food_history.external_identifier(
            external_identifier_id, entity_id, scheme_code, identifier_value, is_primary_for_scheme
        ) VALUES (%s,%s,'ingest-key',%s,true)
        """,
        (uuid7(), eid, source_key),
    )
    return eid, pid, "created"


def ensure_typed_entity(cur, *, source_key: str, type_code: str, label: str, subtype_table: str, summary=None):
    eid, pid, status = ensure_entity(
        cur, source_key=source_key, type_code=type_code, label=label, summary=summary
    )
    if subtype_table not in {"person", "organization", "place", "item"}:
        raise ValueError(f"Unsupported simple subtype: {subtype_table}")
    cur.execute(f'INSERT INTO food_history."{subtype_table}"(entity_id) VALUES (%s) ON CONFLICT (entity_id) DO NOTHING', (eid,))
    return eid, pid, status


def ensure_name(cur, entity_id, *, name_type: str, text: str, language=None, script=None, preferred=False):
    cur.execute(
        """
        SELECT entity_name_id FROM food_history.entity_name
        WHERE entity_id=%s AND name_type=%s AND name_text=%s
          AND language_tag IS NOT DISTINCT FROM %s AND script_code IS NOT DISTINCT FROM %s
        """,
        (entity_id, name_type, text, language, script),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE food_history.entity_name SET is_preferred_in_language=%s, updated_at=now() WHERE entity_name_id=%s",
            (preferred, row[0]),
        )
        return row[0]
    nid = uuid7()
    cur.execute(
        """
        INSERT INTO food_history.entity_name(
          entity_name_id, entity_id, name_type, name_text, language_tag, script_code, is_preferred_in_language
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (nid, entity_id, name_type, text, language, script, preferred),
    )
    return nid


def upsert_term_assignment(cur, entity_id, kind: str, code: str, primary=False):
    tid = get_term_id(cur, code)
    cur.execute(
        """
        SELECT entity_term_assignment_id FROM food_history.entity_term_assignment
        WHERE entity_id=%s AND term_id=%s AND assignment_kind=%s
        """,
        (entity_id, tid, kind),
    )
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE food_history.entity_term_assignment SET is_primary=%s, updated_at=now() WHERE entity_term_assignment_id=%s",
            (primary, row[0]),
        )
        return row[0]
    aid = uuid7()
    cur.execute(
        """
        INSERT INTO food_history.entity_term_assignment(
          entity_term_assignment_id, entity_id, term_id, assignment_kind, is_primary
        ) VALUES (%s,%s,%s,%s,%s)
        """,
        (aid, entity_id, tid, kind, primary),
    )
    return aid


def ensure_digital_resource(cur, image: dict, *, represented_entity_id, sequence=1):
    """Create/reuse a managed digital file and its representation link."""
    sha = image.get("sha256")
    found = None
    if sha:
        cur.execute("SELECT entity_id FROM food_history.digital_resource WHERE sha256=%s", (sha,))
        found = cur.fetchone()
    if found:
        did = found[0]
        cur.execute(
            """
            UPDATE food_history.digital_resource SET storage_uri=%s, original_filename=%s,
              mime_type=%s, width_px=%s, height_px=%s, dpi=%s, updated_at=now()
            WHERE entity_id=%s
            """,
            (
                image["storage_uri"], image.get("original_filename"), image.get("mime_type"),
                image.get("width_px"), image.get("height_px"), image.get("dpi"), did,
            ),
        )
    else:
        storage_uri = image["storage_uri"]
        fallback_name = PurePosixPath(storage_uri.split("?", 1)[0]).name or "digital resource"
        label = image.get("original_filename") or fallback_name
        source_key = f"file:sha256:{sha}" if sha else f"file:uri:{storage_uri}"
        did, _, _ = ensure_entity(cur, source_key=source_key, type_code="ENT.DIG", label=label)
        cur.execute(
            """
            INSERT INTO food_history.digital_resource(
              entity_id, storage_uri, original_filename, mime_type, file_size_bytes, sha256,
              width_px, height_px, dpi, duration_ms, iiif_manifest_uri
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (entity_id) DO UPDATE SET
              storage_uri=EXCLUDED.storage_uri, original_filename=EXCLUDED.original_filename,
              mime_type=EXCLUDED.mime_type, file_size_bytes=EXCLUDED.file_size_bytes,
              sha256=EXCLUDED.sha256, width_px=EXCLUDED.width_px, height_px=EXCLUDED.height_px,
              dpi=EXCLUDED.dpi, duration_ms=EXCLUDED.duration_ms,
              iiif_manifest_uri=EXCLUDED.iiif_manifest_uri
            """,
            (
                did, storage_uri, image.get("original_filename"), image.get("mime_type"),
                image.get("file_size_bytes"), sha, image.get("width_px"), image.get("height_px"),
                image.get("dpi"), image.get("duration_ms"), image.get("iiif_manifest_uri"),
            ),
        )

    role = image.get("role", "detail")
    cur.execute(
        """
        SELECT digital_representation_id FROM food_history.digital_representation
        WHERE digital_entity_id=%s AND represented_entity_id=%s AND role_code=%s
        """,
        (did, represented_entity_id, role),
    )
    row = cur.fetchone()
    is_primary = image.get("primary", role == "primary" or sequence == 1)
    if row:
        cur.execute(
            """
            UPDATE food_history.digital_representation
            SET sequence=%s, is_primary=%s, caption=%s, updated_at=now()
            WHERE digital_representation_id=%s
            """,
            (sequence, is_primary, image.get("caption"), row[0]),
        )
    else:
        cur.execute(
            """
            INSERT INTO food_history.digital_representation(
              digital_representation_id, digital_entity_id, represented_entity_id,
              role_code, sequence, is_primary, caption
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (uuid7(), did, represented_entity_id, role, sequence, is_primary, image.get("caption")),
        )
    return did


def replace_import_transcription(cur, *, source_entity_id, transcription: dict, digital_entity_id=None):
    """Replace only transcription rows owned by this Phase-1 import mechanism."""
    ttype = transcription["type"]
    cur.execute(
        """
        DELETE FROM food_history.transcription
        WHERE source_entity_id=%s AND transcription_type=%s AND generated_by='phase1-ingest'
        """,
        (source_entity_id, ttype),
    )
    tid = uuid7()
    cur.execute(
        """
        INSERT INTO food_history.transcription(
          transcription_id, source_entity_id, digital_entity_id, transcription_type,
          status, language_tag, text_content, overall_confidence, generated_by
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'phase1-ingest')
        """,
        (
            tid, source_entity_id, digital_entity_id, ttype, transcription["status"],
            transcription.get("language"), transcription["text"], transcription.get("confidence"),
        ),
    )
    return tid


def replace_current_holding(cur, *, item_entity_id, holding: dict | None):
    if holding is None:
        return None
    holder_id, _, _ = ensure_typed_entity(
        cur,
        source_key=holding["holder_source_key"],
        type_code=holding.get("holder_entity_type_code", "ENT.AGENT.ORG"),
        label=holding["holder_label"],
        subtype_table="organization",
    )
    cur.execute("DELETE FROM food_history.holding WHERE item_entity_id=%s AND is_current=true", (item_entity_id,))
    hid = uuid7()
    cur.execute(
        """
        INSERT INTO food_history.holding(
          holding_id, item_entity_id, holder_entity_id, accession_number,
          local_call_number, storage_location, is_current
        ) VALUES (%s,%s,%s,%s,%s,%s,true)
        """,
        (
            hid, item_entity_id, holder_id, holding.get("accession_number"),
            holding.get("local_call_number"), holding.get("storage_location"),
        ),
    )
    return hid
