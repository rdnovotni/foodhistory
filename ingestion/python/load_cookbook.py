#!/usr/bin/env python3
"""Cookbook Phase 1 ingestion: Work → Expression → Manifestation → Item."""
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
    ids = []
    work, wpid, status = ensure_entity(
        cur,
        source_key=p["source_key"] + ":work",
        type_code="ENT.WORK",
        label=p["work"]["preferred_label"],
        summary=p["work"].get("summary"),
    )
    ids.append(wpid)
    cur.execute(
        """
        INSERT INTO food_history.work(entity_id, work_type_term_id)
        VALUES (%s,%s)
        ON CONFLICT (entity_id) DO UPDATE SET work_type_term_id=EXCLUDED.work_type_term_id
        """,
        (work, get_term_id(cur, "ROT.DOC.BOOK.COOK")),
    )
    for t in p["work"].get("terms", []):
        upsert_term_assignment(cur, work, t["kind"], t["code"], t.get("primary", False))

    expr, epid, _ = ensure_entity(
        cur,
        source_key=p["source_key"] + ":expression",
        type_code="ENT.EXPR",
        label=p["expression"]["preferred_label"],
    )
    ids.append(epid)
    cur.execute(
        """
        INSERT INTO food_history.expression(entity_id,work_entity_id,language_tag,version_statement,expression_edtf)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT(entity_id) DO UPDATE SET
          work_entity_id=EXCLUDED.work_entity_id,
          language_tag=EXCLUDED.language_tag,
          version_statement=EXCLUDED.version_statement,
          expression_edtf=EXCLUDED.expression_edtf
        """,
        (expr, work, p["expression"].get("language"), p["expression"].get("version_statement"), p["expression"].get("date")),
    )

    mani, mpid, _ = ensure_entity(
        cur,
        source_key=p["source_key"] + ":manifestation",
        type_code="ENT.MANI",
        label=p["manifestation"]["preferred_label"],
    )
    ids.append(mpid)
    cur.execute(
        """
        INSERT INTO food_history.manifestation(entity_id,edition_statement,publication_edtf,extent_text,isbn,oclc_number)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT(entity_id) DO UPDATE SET
          edition_statement=EXCLUDED.edition_statement,
          publication_edtf=EXCLUDED.publication_edtf,
          extent_text=EXCLUDED.extent_text,
          isbn=EXCLUDED.isbn,
          oclc_number=EXCLUDED.oclc_number
        """,
        (
            mani, p["manifestation"].get("edition_statement"), p["manifestation"].get("publication_date"),
            p["manifestation"].get("extent_text"), p["manifestation"].get("isbn"),
            p["manifestation"].get("oclc_number"),
        ),
    )
    cur.execute(
        """
        INSERT INTO food_history.manifestation_expression(
          manifestation_expression_id, manifestation_entity_id, expression_entity_id
        ) VALUES (%s,%s,%s)
        ON CONFLICT(manifestation_entity_id,expression_entity_id) DO NOTHING
        """,
        (uuid7(), mani, expr),
    )

    cur.execute("DELETE FROM food_history.publication_statement WHERE manifestation_entity_id=%s", (mani,))
    pub = p["manifestation"].get("publisher")
    pub_id = None
    if pub:
        pub_id, _, _ = ensure_typed_entity(
            cur, source_key=pub["source_key"], type_code="ENT.AGENT.ORG",
            label=pub["preferred_label"], subtype_table="organization"
        )
    place = p["manifestation"].get("publication_place")
    place_id = None
    if place:
        place_id, _, _ = ensure_typed_entity(
            cur, source_key=place["source_key"], type_code="ENT.PLACE.GEO",
            label=place["preferred_label"], subtype_table="place"
        )
    if pub_id or place_id or p["manifestation"].get("publication_date"):
        cur.execute(
            """
            INSERT INTO food_history.publication_statement(
              publication_statement_id, manifestation_entity_id, statement_type,
              agent_entity_id, place_entity_id, date_edtf, sequence
            ) VALUES (%s,%s,'publication',%s,%s,%s,1)
            """,
            (uuid7(), mani, pub_id, place_id, p["manifestation"].get("publication_date")),
        )

    cur.execute("DELETE FROM food_history.credit WHERE resource_entity_id=%s", (work,))
    for i, credit in enumerate(p.get("credits", []), start=1):
        agent_id, _, _ = ensure_entity(
            cur,
            source_key=credit["agent_source_key"],
            type_code=credit.get("agent_entity_type_code", "ENT.AGENT.PER"),
            label=credit["agent_label"],
        )
        if credit.get("agent_entity_type_code", "ENT.AGENT.PER") == "ENT.AGENT.PER":
            cur.execute("INSERT INTO food_history.person(entity_id) VALUES (%s) ON CONFLICT (entity_id) DO NOTHING", (agent_id,))
        cur.execute(
            """
            INSERT INTO food_history.credit(
              credit_id, resource_entity_id, agent_entity_id, role_term_id, credited_as, sequence
            ) VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (uuid7(), work, agent_id, get_term_id(cur, credit["role_code"]), credit.get("credited_as"), i),
        )

    item, ipid, _ = ensure_entity(
        cur,
        source_key=p["source_key"] + ":item",
        type_code="ENT.ITEM",
        label=p["item"]["preferred_label"],
    )
    ids.append(ipid)
    cur.execute(
        """
        INSERT INTO food_history.item(entity_id,manifestation_entity_id,copy_number,signed_flag,inscription_summary)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT(entity_id) DO UPDATE SET
          manifestation_entity_id=EXCLUDED.manifestation_entity_id,
          copy_number=EXCLUDED.copy_number,
          signed_flag=EXCLUDED.signed_flag,
          inscription_summary=EXCLUDED.inscription_summary
        """,
        (
            item, mani, p["item"].get("copy_number"), p["item"].get("signed", False),
            p["item"].get("inscription_summary"),
        ),
    )

    replace_current_holding(cur, item_entity_id=item, holding=p["item"].get("holding"))
    for i, image in enumerate(p["item"].get("images", []), start=1):
        ensure_digital_resource(cur, image, represented_entity_id=item, sequence=i)

    return {"status": status, "public_ids": ids}


def main():
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            result = ingest(cur, p)
        conn.commit()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
