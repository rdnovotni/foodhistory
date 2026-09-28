#!/usr/bin/env python3
"""Index links in revisions that predate migration 0016. Safe to rerun."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Database
from app.wiki_render import wiki_link_slugs


def backfill(database_url: str) -> int:
    count = 0
    with Database(database_url).connection() as connection:
        rows = connection.execute(
            "SELECT revision_id, body_markdown FROM wiki_revision ORDER BY created_at"
        ).fetchall()
        for row in rows:
            for sequence, slug in enumerate(wiki_link_slugs(row["body_markdown"]), 1):
                result = connection.execute(
                    "INSERT INTO wiki_revision_link (revision_id, target_slug, sequence) "
                    "VALUES (%s, %s, %s) ON CONFLICT (revision_id, target_slug) DO NOTHING",
                    (row["revision_id"], slug, sequence),
                )
                count += result.rowcount
    return count


if __name__ == "__main__":
    print(f"Indexed {backfill(os.environ['DATABASE_URL'])} existing wiki links")
