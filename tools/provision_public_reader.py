#!/usr/bin/env python3
"""Provision the public site's PostgreSQL login with read-only privileges."""

import os

import psycopg
from psycopg import sql


def provision(database_url: str, username: str, password: str) -> None:
    if not username or not password:
        raise ValueError("Public database username and password are required")
    with psycopg.connect(database_url) as connection:
        database = connection.info.dbname
        if username == connection.info.user:
            raise ValueError("Public reader must not be the database owner login")
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (username,)
        ).fetchone()
        role = sql.Identifier(username)
        password_literal = sql.Literal(password)
        if exists:
            connection.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    role, password_literal
                )
            )
        else:
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    role, password_literal
                )
            )
        connection.execute(sql.SQL(
            "ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
        ).format(role))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(database), role
        ))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA food_history TO {}").format(role))
        connection.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA food_history TO {}").format(role))
        private_tables = (
            "app_user", "editor_account", "editor_session", "wiki_page",
            "wiki_revision", "wiki_review", "wiki_revision_entity",
            "wiki_revision_citation", "wiki_redirect",
        )
        connection.execute(
            sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(
                sql.SQL(", ").join(sql.Identifier(name) for name in private_tables), role
            )
        )
        connection.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(role))
    print(f"Provisioned read-only public database role {username!r}")


def main() -> None:
    provision(
        os.environ["DATABASE_URL"],
        os.environ["PUBLIC_DATABASE_USER"],
        os.environ["PUBLIC_DATABASE_PASSWORD"],
    )


if __name__ == "__main__":
    main()
