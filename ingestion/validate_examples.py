#!/usr/bin/env python3
import json
from pathlib import Path
from jsonschema import Draft202012Validator

base=Path(__file__).parent
pairs=[
 ('schemas/ingest-menu.schema.json','examples/menu.example.json'),
 ('schemas/ingest-cookbook.schema.json','examples/cookbook.example.json'),
 ('schemas/ingest-object.schema.json','examples/object.example.json'),
]
for s,e in pairs:
    schema=json.loads((base/s).read_text(encoding='utf-8'))
    example=json.loads((base/e).read_text(encoding='utf-8'))
    errors=sorted(Draft202012Validator(schema).iter_errors(example), key=lambda x:list(x.path))
    if errors:
        for err in errors: print(e, list(err.path), err.message)
        raise SystemExit(1)
    print('OK', e)
