#!/usr/bin/env python3
"""Static validation for the Food History Phase 1 backend package."""
from __future__ import annotations

import csv
import gzip
import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

def fail(message: str):
    raise SystemExit(f"ERROR: {message}")

def read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, mode="rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def validate_examples():
    pairs = [
        ("ingestion/schemas/ingest-menu.schema.json", "ingestion/examples/menu.example.json"),
        ("ingestion/schemas/ingest-cookbook.schema.json", "ingestion/examples/cookbook.example.json"),
        ("ingestion/schemas/ingest-object.schema.json", "ingestion/examples/object.example.json"),
    ]
    for schema_rel, example_rel in pairs:
        schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
        example = json.loads((ROOT / example_rel).read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(example), key=lambda e: list(e.path))
        if errors:
            fail(f"{example_rel} does not validate: {errors[0].message}")

def load_taxonomy_codes():
    codes = set()
    manifest = json.loads((ROOT / "seeds/taxonomy/manifest.json").read_text(encoding="utf-8"))
    total = 0
    for entry in manifest:
        path = ROOT / entry["file"]
        rows = read_rows(path)
        if len(rows) != entry["term_count"]:
            fail(f"taxonomy manifest count mismatch for {path}: {len(rows)} != {entry['term_count']}")
        for row in rows:
            code = row["code"]
            if code in codes:
                fail(f"duplicate taxonomy code {code}")
            codes.add(code)
            total += 1
    if total != 1392:
        fail(f"expected 1,392 taxonomy terms, found {total}")
    return codes

def validate_example_codes(codes):
    code_key_names = {
        "entity_type_code", "document_type_code", "menu_type_code", "course_code",
        "normalized_food_type_code", "food_class_code", "object_type_code", "role_code",
        "process_code", "code"
    }
    def walk(obj, context=()):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    is_taxonomy = k in code_key_names and (k != "code" or (context and context[-1] == "terms"))
                    if is_taxonomy and v not in codes:
                        fail(f"unknown taxonomy code {v} at {'.'.join(context + (k,))}")
                walk(v, context + (k,))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, context + (str(i),))
    for p in sorted((ROOT / "ingestion/examples").glob("*.json")):
        walk(json.loads(p.read_text(encoding="utf-8")), (p.name,))

def validate_openapi():
    doc = yaml.safe_load((ROOT / "api/openapi.yaml").read_text(encoding="utf-8"))
    if not str(doc.get("openapi", "")).startswith("3."):
        fail("OpenAPI document is not version 3.x")
    for rel in ["api/ingest-menu.schema.json", "api/ingest-cookbook.schema.json", "api/ingest-object.schema.json"]:
        json.loads((ROOT / rel).read_text(encoding="utf-8"))

def parse_migrations():
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "migrations").glob("*.sql")))
    create_re = re.compile(r'CREATE TABLE\s+"(?P<table>[^"]+)"\s*\((?P<body>.*?)\n\);', re.S | re.I)
    tables = {}
    for m in create_re.finditer(sql):
        table = m.group("table")
        cols = set(re.findall(r'^\s*"([^"]+)"\s+', m.group("body"), re.M))
        if table in tables:
            fail(f"table created twice: {table}")
        tables[table] = cols
    if len(tables) != 68:
        fail(f"expected 68 application tables, parsed {len(tables)}")
    fk_re = re.compile(r'ALTER TABLE\s+"(?P<child>[^"]+)".*?FOREIGN KEY\s*\("(?P<childcol>[^"]+)"\)\s*REFERENCES\s+"(?P<parent>[^"]+)"\s*\("(?P<parentcol>[^"]+)"\)', re.I)
    for m in fk_re.finditer(sql):
        child, childcol, parent, parentcol = m.group("child"), m.group("childcol"), m.group("parent"), m.group("parentcol")
        if child not in tables or childcol not in tables[child]:
            fail(f"bad FK source {child}.{childcol}")
        if parent not in tables or parentcol not in tables[parent]:
            fail(f"bad FK target {parent}.{parentcol}")
    return tables

def main():
    validate_examples()
    codes = load_taxonomy_codes()
    validate_example_codes(codes)
    validate_openapi()
    tables = parse_migrations()
    print(f"PASS: examples, taxonomy (1,392 terms), OpenAPI, and {len(tables)} application tables are internally consistent.")

if __name__ == "__main__":
    main()
