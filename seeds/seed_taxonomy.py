#!/usr/bin/env python3
"""Seed Food History Master Taxonomy v1.1 into PostgreSQL.

Usage:
  DATABASE_URL=postgresql://... python seeds/seed_taxonomy.py
Requires: psycopg >= 3
"""
import csv, gzip, os, uuid
from pathlib import Path
import psycopg

NAMESPACE = uuid.UUID("df3d1731-1d8a-4b6c-b548-0e743b964f98")
VERSION = "1.1"
VOCABS = {
    "ENT": "Entity Classes", "FC": "Food Concepts", "SUB": "Subject Domains",
    "ROT": "Resource & Object Types", "CTX": "Contexts", "COL": "Collecting Domains",
    "FAC": "Metadata Facets", "REL": "Relationships", "EVD": "Evidence & Status",
    "CAT": "Catalogue Modules",
}

def stable_uuid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{key}")

def read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, mode="rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def main():
    url = os.environ["DATABASE_URL"]
    base = Path(__file__).parent / "taxonomy"
    manifest = __import__("json").loads((base / "manifest.json").read_text(encoding="utf-8"))
    by_code = {x["vocabulary_code"]: x for x in manifest}
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO food_history, public")
            vocab_ids = {}
            for code, name in VOCABS.items():
                vid = stable_uuid("vocabulary", code)
                vocab_ids[code] = vid
                cur.execute("""
                    INSERT INTO vocabulary(vocabulary_id, code, name, version, is_local, description)
                    VALUES (%s,%s,%s,%s,true,%s)
                    ON CONFLICT (code) DO UPDATE SET
                      name=EXCLUDED.name, version=EXCLUDED.version, updated_at=now()
                """, (vid, code, name, VERSION, f"Food History Master Taxonomy {VERSION}"))

            rows_by_vocab = {}
            for code in VOCABS:
                path = Path(__file__).resolve().parents[1] / by_code[code]["file"]
                rows_by_vocab[code] = read_rows(path)
                if len(rows_by_vocab[code]) != by_code[code]["term_count"]:
                    raise ValueError(f"Taxonomy count mismatch for {code}: {len(rows_by_vocab[code])}")

            for code, rows in rows_by_vocab.items():
                for row in rows:
                    tid = stable_uuid("term", row["code"])
                    cur.execute("""
                        INSERT INTO taxonomy_term(term_id, vocabulary_id, code, preferred_label, scope_note,
                                                  term_status, introduced_version, sort_key)
                        VALUES (%s,%s,%s,%s,%s,'approved',%s,%s)
                        ON CONFLICT (code) DO UPDATE SET
                          preferred_label=EXCLUDED.preferred_label,
                          scope_note=EXCLUDED.scope_note,
                          vocabulary_id=EXCLUDED.vocabulary_id,
                          updated_at=now()
                    """, (tid, vocab_ids[code], row["code"], row["preferred_label"], row["scope_note"] or None, VERSION, row["code"]))
                    cur.execute("""
                        INSERT INTO taxonomy_label(taxonomy_label_id, term_id, label_type, label_text,
                                                   language_tag, is_preferred_in_language)
                        VALUES (%s,%s,'preferred',%s,'en',true)
                        ON CONFLICT (term_id, label_type, language_tag, label_text) DO NOTHING
                    """, (stable_uuid("label", row["code"]+":en:preferred"), tid, row["preferred_label"]))

            for code, rows in rows_by_vocab.items():
                for row in rows:
                    if not row["parent_code"]:
                        continue
                    cur.execute("SELECT term_id FROM taxonomy_term WHERE code=%s", (row["code"],))
                    child = cur.fetchone()[0]
                    cur.execute("SELECT term_id FROM taxonomy_term WHERE code=%s", (row["parent_code"],))
                    parent = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO taxonomy_edge(taxonomy_edge_id, child_term_id, parent_term_id, edge_type)
                        VALUES (%s,%s,%s,'broader')
                        ON CONFLICT (child_term_id, parent_term_id, edge_type) DO NOTHING
                    """, (stable_uuid("edge", row["code"]+">"+row["parent_code"]), child, parent))
        conn.commit()
    print("Seeded Food History Master Taxonomy v1.1")

if __name__ == "__main__":
    main()
