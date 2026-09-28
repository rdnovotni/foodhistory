#!/usr/bin/env python3
"""Create a private editorial account without placing a password in shell history."""

from __future__ import annotations

import argparse
import getpass

from app.auth import hash_password
from app.config import Settings
from app.db import Database
from app.wiki_repository import WikiRepository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--role", choices=("owner", "editor", "reviewer", "viewer"), default="editor"
    )
    args = parser.parse_args()
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    repository = WikiRepository(Database(Settings.from_env().database_url))
    account_id = repository.create_account(
        args.username, args.display_name, hash_password(password), args.role
    )
    print(f"Created {args.role} account {args.username!r} ({account_id})")


if __name__ == "__main__":
    main()
