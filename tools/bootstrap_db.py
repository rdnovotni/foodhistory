#!/usr/bin/env python3
"""Apply the immutable migrations, seed taxonomy, and optionally load examples."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))


def applied_versions(connection: psycopg.Connection) -> set[str]:
    exists = connection.execute(
        "SELECT to_regclass('food_history.schema_version') IS NOT NULL"
    ).fetchone()[0]
    if not exists:
        return set()
    return {
        row[0]
        for row in connection.execute(
            "SELECT version FROM food_history.schema_version"
        ).fetchall()
    }


def apply_migration(database_url: str, path: Path) -> None:
    version = path.stem.split("_", 1)[0]
    description = path.stem.split("_", 1)[1].replace("_", " ")
    with psycopg.connect(database_url) as connection:
        if version in applied_versions(connection):
            return
        connection.execute(path.read_text(encoding="utf-8"))
        connection.execute(
            """
            INSERT INTO food_history.schema_version(version, description)
            VALUES (%s, %s) ON CONFLICT (version) DO NOTHING
            """,
            (version, description),
        )
    print(f"Applied {path.name}")


def run_script(database_url: str, *parts: str) -> None:
    environment = dict(os.environ, DATABASE_URL=database_url)
    subprocess.run([sys.executable, str(ROOT.joinpath(*parts))], check=True, env=environment)


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    for path in MIGRATIONS[:8]:
        apply_migration(database_url, path)

    run_script(database_url, "seeds", "seed_taxonomy.py")

    for path in MIGRATIONS[8:]:
        apply_migration(database_url, path)

    public_password = os.getenv("PUBLIC_DATABASE_PASSWORD")
    if public_password:
        from provision_public_reader import provision

        provision(
            database_url,
            os.getenv("PUBLIC_DATABASE_USER", "food_history_public"),
            public_password,
        )

    if os.getenv("LOAD_EXAMPLES", "").lower() in {"1", "true", "yes"}:
        for kind in ("menu", "cookbook", "object"):
            environment = dict(os.environ, DATABASE_URL=database_url)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "ingestion" / "python" / f"load_{kind}.py"),
                    str(ROOT / "ingestion" / "examples" / f"{kind}.example.json"),
                ],
                check=True,
                env=environment,
            )
        print("Loaded synthetic development examples")


if __name__ == "__main__":
    main()
