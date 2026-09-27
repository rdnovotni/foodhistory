#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

import psycopg

from common import (
    ensure_digital_resource,
    ensure_entity,
    ensure_name,
    ensure_typed_entity,
    get_term_id,
    replace_import_transcription,
    upsert_term_assignment,
    uuid7,
)


def ingest(cur, p):
    menu_id, menu_public, status = ensure_entity(
        cur,
        source_key=p["source_key"],
        type_code=p.get("entity_type_code", "ENT.DOC"),
        label=p["preferred_label"],
        summary=p.get("summary"),
    )
    cur.execute("INSERT INTO food_history.item(entity_id) VALUES (%s) ON CONFLICT (entity_id) DO NOTHING", (menu_id,))
    cur.execute(
        """
        INSERT INTO food_history.document(entity_id, document_type_term_id, date_edtf)
        VALUES (%s,%s,%s)
        ON CONFLICT (entity_id) DO UPDATE SET
          document_type_term_id=EXCLUDED.document_type_term_id,
          date_edtf=EXCLUDED.date_edtf
        """,
        (menu_id, get_term_id(cur, p.get("document_type_code", "ROT.DOC.MENU")), p.get("service_date")),
    )

    for n in p.get("names", []):
        ensure_name(
            cur, menu_id, name_type=n["type"], text=n["text"],
            language=n.get("language"), script=n.get("script"),
            preferred=n.get("preferred", False),
        )

    establishment_id = None
    if p.get("establishment"):
        e = p["establishment"]
        establishment_id, _, _ = ensure_typed_entity(
            cur,
            source_key=e["source_key"],
            type_code=e.get("entity_type_code", "ENT.AGENT.BUS"),
            label=e["preferred_label"],
            subtype_table="organization",
        )

    cur.execute(
        """
        INSERT INTO food_history.menu(
          entity_id, menu_type_term_id, establishment_entity_id, service_date_edtf, currency_code
        ) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (entity_id) DO UPDATE SET
          menu_type_term_id=EXCLUDED.menu_type_term_id,
          establishment_entity_id=EXCLUDED.establishment_entity_id,
          service_date_edtf=EXCLUDED.service_date_edtf,
          currency_code=EXCLUDED.currency_code
        """,
        (menu_id, get_term_id(cur, p["menu_type_code"]), establishment_id, p.get("service_date"), p.get("currency_code")),
    )

    for t in p.get("terms", []):
        upsert_term_assignment(cur, menu_id, t["kind"], t["code"], t.get("primary", False))

    primary_digital_id = None
    for i, image in enumerate(p.get("images", []), start=1):
        did = ensure_digital_resource(cur, image, represented_entity_id=menu_id, sequence=i)
        if primary_digital_id is None:
            primary_digital_id = did

    if p.get("transcription"):
        replace_import_transcription(
            cur,
            source_entity_id=menu_id,
            transcription=p["transcription"],
            digital_entity_id=primary_digital_id,
        )

    cur.execute("DELETE FROM food_history.menu_item WHERE menu_entity_id=%s", (menu_id,))
    cur.execute("DELETE FROM food_history.menu_section WHERE menu_entity_id=%s", (menu_id,))
    for sec in sorted(p.get("sections", []), key=lambda x: x["sequence"]):
        sid = uuid7()
        cur.execute(
            """
            INSERT INTO food_history.menu_section(
              menu_section_id, menu_entity_id, sequence, heading_original, course_term_id, page_label
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                sid, menu_id, sec["sequence"], sec.get("heading_original"),
                get_term_id(cur, sec["course_code"]) if sec.get("course_code") else None,
                sec.get("page_label"),
            ),
        )
        for item in sorted(sec["items"], key=lambda x: x["sequence"]):
            food_id = None
            if item.get("normalized_food_source_key") and item.get("normalized_food_label"):
                food_id, _, _ = ensure_entity(
                    cur,
                    source_key=item["normalized_food_source_key"],
                    type_code=item.get("normalized_food_type_code") or "ENT.CUL.FOOD",
                    label=item["normalized_food_label"],
                )
                cur.execute(
                    """
                    INSERT INTO food_history.culinary_concept(entity_id, concept_type_term_id)
                    VALUES (%s,%s)
                    ON CONFLICT (entity_id) DO UPDATE SET concept_type_term_id=EXCLUDED.concept_type_term_id
                    """,
                    (food_id, get_term_id(cur, item.get("food_class_code", "FC.FOOD"))),
                )
            cur.execute(
                """
                INSERT INTO food_history.menu_item(
                  menu_item_id, menu_entity_id, menu_section_id, sequence,
                  printed_name, printed_description, normalized_food_entity_id,
                  portion_text, price_text, price_amount, currency_code,
                  price_basis_text, availability_note, transcription_confidence
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    uuid7(), menu_id, sid, item["sequence"], item["printed_name"],
                    item.get("printed_description"), food_id, item.get("portion_text"),
                    item.get("price_text"), item.get("price_amount"),
                    item.get("currency_code") or p.get("currency_code"),
                    item.get("price_basis_text"), item.get("availability_note"),
                    item.get("transcription_confidence"),
                ),
            )
    return {"status": status, "public_ids": [menu_public]}


def main():
    payload = json.load(open(sys.argv[1], encoding="utf-8"))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            result = ingest(cur, payload)
        conn.commit()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
