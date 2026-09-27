#!/usr/bin/env python3
"""Material-culture Phase 1 ingestion skeleton with production, holding and images."""
from __future__ import annotations

import json
import os
import sys

import psycopg

from common import (
    ensure_digital_resource,
    ensure_entity,
    ensure_typed_entity,
    get_term_id,
    replace_current_holding,
    upsert_term_assignment,
    uuid7,
)


def ingest(cur, p):
    oid, pid, status = ensure_entity(
        cur,
        source_key=p["source_key"],
        type_code=p.get("entity_type_code", "ENT.OBJ"),
        label=p["preferred_label"],
        summary=p.get("summary"),
    )
    cur.execute("INSERT INTO food_history.item(entity_id) VALUES (%s) ON CONFLICT(entity_id) DO NOTHING", (oid,))
    cur.execute(
        """
        INSERT INTO food_history.physical_object(
          entity_id, object_type_term_id, authenticity_status, manufacture_edtf,
          material_summary, completeness_text
        ) VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT(entity_id) DO UPDATE SET
          object_type_term_id=EXCLUDED.object_type_term_id,
          authenticity_status=EXCLUDED.authenticity_status,
          manufacture_edtf=EXCLUDED.manufacture_edtf,
          material_summary=EXCLUDED.material_summary,
          completeness_text=EXCLUDED.completeness_text
        """,
        (
            oid, get_term_id(cur, p["object_type_code"]), p.get("authenticity_status"),
            p.get("manufacture_date"), p.get("material_summary"), p.get("completeness_text"),
        ),
    )
    for t in p.get("terms", []):
        upsert_term_assignment(cur, oid, t["kind"], t["code"], t.get("primary", False))

    cur.execute("DELETE FROM food_history.measurement WHERE entity_id=%s", (oid,))
    for m in p.get("measurements", []):
        cur.execute(
            """
            INSERT INTO food_history.measurement(
              measurement_id,entity_id,measurement_type,value,value_min,value_max,unit_code,display_text,method_note
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                uuid7(), oid, m["type"], m.get("value"), m.get("value_min"), m.get("value_max"),
                m.get("unit_code"), m.get("display_text"), m.get("method_note"),
            ),
        )

    cur.execute("DELETE FROM food_history.object_mark WHERE entity_id=%s", (oid,))
    for mark in p.get("marks", []):
        cur.execute(
            """
            INSERT INTO food_history.object_mark(
              object_mark_id,entity_id,mark_type,transcription,normalized_text,location_on_object,date_code_text,note
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                uuid7(), oid, mark["type"], mark.get("transcription"), mark.get("normalized_text"),
                mark.get("location"), mark.get("date_code"), mark.get("note"),
            ),
        )

    cur.execute("DELETE FROM food_history.production_record WHERE entity_id=%s", (oid,))
    prod = p.get("production")
    if prod:
        manufacturer_id = None
        if prod.get("manufacturer_source_key") and prod.get("manufacturer_label"):
            manufacturer_id, _, _ = ensure_typed_entity(
                cur,
                source_key=prod["manufacturer_source_key"],
                type_code=prod.get("manufacturer_entity_type_code", "ENT.AGENT.BUS"),
                label=prod["manufacturer_label"],
                subtype_table="organization",
            )
        place_id = None
        if prod.get("production_place_source_key") and prod.get("production_place_label"):
            place_id, _, _ = ensure_typed_entity(
                cur,
                source_key=prod["production_place_source_key"],
                type_code="ENT.PLACE.SITE",
                label=prod["production_place_label"],
                subtype_table="place",
            )
        cur.execute(
            """
            INSERT INTO food_history.production_record(
              production_record_id, entity_id, manufacturer_entity_id, production_place_entity_id,
              model_or_pattern, design_number, batch_or_lot_code, date_edtf, process_term_id, note
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                uuid7(), oid, manufacturer_id, place_id, prod.get("model_or_pattern"),
                prod.get("design_number"), prod.get("batch_or_lot_code"), prod.get("date"),
                get_term_id(cur, prod["process_code"]) if prod.get("process_code") else None,
                prod.get("note"),
            ),
        )

    if p.get("condition"):
        cond = p["condition"]
        if cond.get("assessment_date"):
            cur.execute(
                "DELETE FROM food_history.condition_assessment WHERE entity_id=%s AND assessment_date=%s",
                (oid, cond["assessment_date"]),
            )
        cur.execute(
            """
            INSERT INTO food_history.condition_assessment(
              condition_assessment_id,entity_id,assessment_date,condition_text,
              completeness_text,restoration_text
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                uuid7(), oid, cond.get("assessment_date"), cond["condition_text"],
                cond.get("completeness_text"), cond.get("restoration_text"),
            ),
        )

    replace_current_holding(cur, item_entity_id=oid, holding=p.get("holding"))
    for i, image in enumerate(p.get("images", []), start=1):
        ensure_digital_resource(cur, image, represented_entity_id=oid, sequence=i)

    return {"status": status, "public_ids": [pid]}


def main():
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            result = ingest(cur, p)
        conn.commit()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
