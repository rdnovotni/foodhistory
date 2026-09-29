"""Wiki read models and tightly scoped private editorial writes."""

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.auth import digest_secret, verify_password
from app.db import Database
from app.wiki_render import wiki_link_slugs


class WikiRepository:
    def __init__(self, database: Database):
        self.db = database

    def list_published(
        self, q: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT p.public_id, p.slug, p.title, p.summary, p.created_at AS published_at
            FROM public_wiki_page p
            WHERE (%s::text IS NULL OR to_tsvector('simple', coalesce(p.title, '') || ' ' ||
                   coalesce(p.summary, '') || ' ' || p.body_markdown)
                   @@ websearch_to_tsquery('simple', %s))
              AND (%s::text IS NULL OR EXISTS (
                  SELECT 1 FROM public_wiki_revision_category c
                  WHERE c.revision_id = p.revision_id AND c.slug = %s
              ))
            ORDER BY p.title
            """,
            (q or None, q or None, category or None, category or None),
        )

    def list_public_categories(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT slug, name, description, page_count FROM public_wiki_category ORDER BY name"
        )

    def list_editor_categories(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT slug, name, description FROM wiki_category ORDER BY name"
        )

    def list_article_templates(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT template_key, version, article_type, title, description "
            "FROM wiki_article_template WHERE is_current ORDER BY title"
        )

    def get_article_template(self, key: str, version: int | None = None) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT template_key, version, article_type, title, description, body_markdown, "
            "migration_markdown FROM wiki_article_template WHERE template_key = %s "
            "AND (%s::integer IS NULL AND is_current OR version = %s) "
            "ORDER BY version DESC LIMIT 1",
            (key, version, version),
        )

    def list_template_versions(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT template_key, version, article_type, title, description, "
            "migration_markdown, is_current, created_at FROM wiki_article_template "
            "ORDER BY template_key, version DESC"
        )

    def create_template_version(self, key: str, article_type: str, title: str,
                                description: str, body_markdown: str,
                                migration_markdown: str) -> int:
        with self.db.connection() as connection:
            rows = connection.execute(
                "SELECT version, article_type FROM wiki_article_template WHERE template_key = %s "
                "ORDER BY version DESC FOR UPDATE", (key,),
            ).fetchall()
            if rows and rows[0]["article_type"] != article_type:
                raise ValueError("A template's article type cannot change between versions")
            version = (rows[0]["version"] + 1) if rows else 1
            connection.execute(
                "UPDATE wiki_article_template SET is_current = false "
                "WHERE template_key = %s AND is_current", (key,),
            )
            connection.execute(
                "INSERT INTO wiki_article_template "
                "(template_key, version, article_type, title, description, body_markdown, "
                "migration_markdown, is_current) VALUES (%s, %s, %s, %s, %s, %s, %s, true)",
                (key, version, article_type, title, description, body_markdown,
                 migration_markdown),
            )
        return version

    def structured_block_data(self, references: dict[str, list[str]]) -> dict[str, Any]:
        """Resolve only public canonical records requested by authored blocks."""
        result: dict[str, Any] = {
            "entities": {}, "citations": {}, "menus": {}, "prices": {}, "media": {},
        }
        if references["entities"]:
            rows = self.db.fetch_all(
                """
                SELECT e.entity_id, e.public_id, e.preferred_label AS label,
                       type.preferred_label AS type_label,
                       person.birth_edtf, person.death_edtf, person.occupation_summary,
                       organization.founded_edtf, organization.dissolved_edtf,
                       organization.website_uri, place.latitude, place.longitude,
                       place.current_address_text, work.creation_edtf,
                       object.manufacture_edtf, object.material_summary,
                       (SELECT string_agg(x.scheme_code || ': ' || x.identifier_value, '; '
                                          ORDER BY x.scheme_code)
                        FROM external_identifier x WHERE x.entity_id = e.entity_id) AS identifiers
                FROM entity e JOIN taxonomy_term type ON type.term_id = e.entity_type_term_id
                LEFT JOIN person ON person.entity_id = e.entity_id
                LEFT JOIN organization ON organization.entity_id = e.entity_id
                LEFT JOIN place ON place.entity_id = e.entity_id
                LEFT JOIN work ON work.entity_id = e.entity_id
                LEFT JOIN physical_object object ON object.entity_id = e.entity_id
                WHERE e.public_id = ANY(%s) AND e.visibility = 'public'
                """,
                (references["entities"],),
            )
            for row in rows:
                row["dates"] = "–".join(
                    str(value) for value in (row.pop("birth_edtf"), row.pop("death_edtf")) if value
                ) or None
                row["occupation"] = row.pop("occupation_summary")
                row["founded"] = "–".join(
                    str(value) for value in (row.pop("founded_edtf"), row.pop("dissolved_edtf")) if value
                ) or None
                row["website"] = row.pop("website_uri")
                row["address"] = row.pop("current_address_text")
                row["creation_date"] = row.pop("creation_edtf")
                row["manufacture_date"] = row.pop("manufacture_edtf")
                row["materials"] = row.pop("material_summary")
                result["entities"][row["public_id"]] = row
        citation_ids = []
        for value in references["citations"]:
            try:
                citation_ids.append(UUID(value))
            except ValueError:
                continue
        if citation_ids:
            rows = self.db.fetch_all(
                """
                SELECT c.citation_id, c.locator_text, c.page_label, c.stable_uri, c.excerpt,
                       source.public_id AS source_public_id,
                       source.preferred_label AS source_label
                FROM citation c JOIN entity source ON source.entity_id = c.source_entity_id
                WHERE c.citation_id = ANY(%s) AND source.visibility = 'public'
                """,
                (citation_ids,),
            )
            result["citations"] = {str(row["citation_id"]): row for row in rows}
        if references["media"]:
            rows = self.db.fetch_all(
                """
                SELECT e.public_id, e.preferred_label AS label, resource.storage_uri AS uri
                FROM digital_resource resource JOIN entity e ON e.entity_id = resource.entity_id
                WHERE e.public_id = ANY(%s) AND e.visibility = 'public'
                  AND resource.mime_type LIKE 'image/%%'
                """,
                (references["media"],),
            )
            result["media"] = {row["public_id"]: row for row in rows}
        if references["menus"]:
            menus = self.db.fetch_all(
                """
                SELECT e.entity_id, e.public_id, e.preferred_label AS label,
                       menu.service_date_edtf AS date
                FROM menu JOIN entity e ON e.entity_id = menu.entity_id
                WHERE e.public_id = ANY(%s) AND e.visibility = 'public'
                """, (references["menus"],),
            )
            for menu in menus:
                menu["items"] = self.db.fetch_all(
                    "SELECT printed_name AS name, printed_description AS description, "
                    "coalesce(price_text, concat_ws(' ', price_amount, currency_code)) AS price "
                    "FROM menu_item WHERE menu_entity_id = %s ORDER BY sequence",
                    (menu.pop("entity_id"),),
                )
                result["menus"][menu["public_id"]] = menu
        if references["prices"]:
            rows = self.db.fetch_all(
                """
                SELECT subject.public_id, price.date_edtf AS date,
                       coalesce(price.amount_text,
                           concat_ws(' ', price.amount, price.currency_code, price.basis_text)) AS display,
                       place.preferred_label AS place, citation.citation_id,
                       citation.locator_text, citation.page_label, citation.excerpt,
                       source.public_id AS source_public_id,
                       source.preferred_label AS source_label
                FROM price_observation price
                JOIN entity subject ON subject.entity_id = price.subject_entity_id
                JOIN citation ON citation.citation_id = price.citation_id
                JOIN entity source ON source.entity_id = citation.source_entity_id
                LEFT JOIN entity place ON place.entity_id = price.place_entity_id
                WHERE subject.public_id = ANY(%s) AND subject.visibility = 'public'
                  AND source.visibility = 'public'
                ORDER BY price.date_edtf, price.price_observation_id
                """, (references["prices"],),
            )
            for row in rows:
                citation = {key: row.pop(key) for key in (
                    "citation_id", "locator_text", "page_label", "excerpt",
                    "source_public_id", "source_label",
                )}
                row["citation"] = citation
                result["prices"].setdefault(row.pop("public_id"), []).append(row)
        return result

    def list_series(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT slug, title, description FROM wiki_series ORDER BY title")

    def create_series(self, slug: str, title: str, description: str) -> None:
        with self.db.connection() as connection:
            connection.execute(
                "INSERT INTO wiki_series (series_id, slug, title, description) VALUES (%s, %s, %s, %s)",
                (uuid4(), slug, title, description),
            )

    def list_redirects(self, page_id: UUID | str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT source_slug, created_at FROM wiki_redirect WHERE page_id = %s ORDER BY source_slug",
            (page_id,),
        )

    def add_redirect(self, page_id: UUID | str, slug: str, user_id: UUID | str) -> None:
        with self.db.connection() as connection:
            page = connection.execute("SELECT slug FROM wiki_page WHERE page_id = %s", (page_id,)).fetchone()
            if not page:
                raise ValueError("Wiki page not found")
            if slug == page["slug"] or connection.execute(
                "SELECT 1 FROM wiki_page WHERE slug = %s", (slug,)
            ).fetchone():
                raise ValueError("Redirect slug is already used by a page")
            if connection.execute(
                "SELECT 1 FROM wiki_redirect WHERE source_slug = %s", (slug,)
            ).fetchone():
                raise ValueError("Redirect slug is already in use")
            connection.execute(
                "INSERT INTO wiki_redirect (source_slug, page_id, created_by_user_id) VALUES (%s, %s, %s)",
                (slug, page_id, user_id),
            )

    def delete_redirect(self, page_id: UUID | str, slug: str) -> None:
        with self.db.connection() as connection:
            result = connection.execute(
                "DELETE FROM wiki_redirect WHERE page_id = %s AND source_slug = %s RETURNING source_slug",
                (page_id, slug),
            ).fetchone()
            if not result:
                raise ValueError("Redirect not found")

    def recent_pages(self, improved: bool = False, limit: int = 8) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT p.slug, p.title, p.summary, max(e.published_at) AS published_at
            FROM public_wiki_page p JOIN public_wiki_publication e ON e.page_id = p.page_id
            GROUP BY p.page_id, p.slug, p.title, p.summary
            HAVING (count(*) > 1) = %s
            ORDER BY published_at DESC, p.slug LIMIT %s
            """,
            (improved, limit),
        )

    def on_this_day(self, month: int, day: int, limit: int = 8) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT p.slug, p.title, p.summary FROM public_wiki_page p
            JOIN public_wiki_revision_metadata m ON m.revision_id = p.revision_id
            WHERE m.event_month = %s AND m.event_day = %s ORDER BY p.title LIMIT %s
            """,
            (month, day, limit),
        )

    def random_page(self) -> dict[str, Any] | None:
        return self.db.fetch_one("SELECT slug FROM public_wiki_page ORDER BY random() LIMIT 1")

    def published_revisions(self, slug: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT revision_number, title, published_at,
                   revision_number = (SELECT revision_number FROM public_wiki_page WHERE slug = %s)
                     AS is_current
            FROM public_wiki_publication WHERE slug = %s
            ORDER BY published_at DESC, revision_number DESC
            """,
            (slug, slug),
        )

    def published_revision(self, slug: str, number: int) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT slug, revision_number, title, summary, body_markdown, published_at "
            "FROM public_wiki_publication WHERE slug = %s AND revision_number = %s",
            (slug, number),
        )

    def page_information(self, slug: str) -> dict[str, Any] | None:
        page = self.db.fetch_one(
            """SELECT p.slug, p.public_id, p.title, p.created_at AS revision_created_at,
                      (SELECT min(e.published_at) FROM public_wiki_publication e WHERE e.page_id = p.page_id)
                        AS first_published_at
               FROM public_wiki_page p WHERE p.slug = %s""", (slug,),
        )
        if page:
            page["redirects"] = self.db.fetch_all(
                "SELECT source_slug FROM public_wiki_redirect WHERE target_slug = %s ORDER BY source_slug",
                (slug,),
            )
            page["revision_count"] = len(self.published_revisions(slug))
            page["backlink_count"] = len(self.backlinks(slug))
        return page

    def series_navigation(self, revision_id: UUID | str) -> list[dict[str, Any]]:
        series = self.db.fetch_all(
            "SELECT slug, title, description, position FROM public_wiki_revision_series "
            "WHERE revision_id = %s ORDER BY title", (revision_id,),
        )
        for item in series:
            members = self.db.fetch_all(
                """SELECT p.slug, p.title, p.revision_id, m.position FROM public_wiki_revision_series m
                   JOIN public_wiki_page p ON p.revision_id = m.revision_id
                   WHERE m.slug = %s ORDER BY m.position, p.title""", (item["slug"],),
            )
            item["members"] = members
            current = next((index for index, member in enumerate(members)
                            if member["revision_id"] == revision_id), None)
            for member in members:
                member.pop("revision_id")
            item["previous"] = members[current - 1] if current is not None and current > 0 else None
            item["next"] = members[current + 1] if current is not None and current + 1 < len(members) else None
        return series

    def public_series(self, slug: str) -> dict[str, Any] | None:
        series = self.db.fetch_one(
            "SELECT slug, title, description FROM public_wiki_revision_series WHERE slug = %s LIMIT 1",
            (slug,),
        )
        if series:
            series["members"] = self.db.fetch_all(
                """SELECT p.slug, p.title, p.summary, m.position
                   FROM public_wiki_revision_series m JOIN public_wiki_page p
                     ON p.revision_id = m.revision_id
                   WHERE m.slug = %s ORDER BY m.position, p.title""", (slug,),
            )
        return series

    def related_pages(self, revision_id: UUID | str, slug: str,
                      suggest: bool = True) -> list[dict[str, Any]]:
        curated = self.db.fetch_all(
            """
            SELECT p.public_id, p.slug, p.title, p.summary
            FROM public_wiki_revision_related r
            JOIN public_wiki_page p ON p.slug = r.target_slug
            WHERE r.revision_id = %s AND p.slug <> %s ORDER BY r.sequence LIMIT 8
            """, (revision_id, slug),
        )
        if len(curated) >= 8 or not suggest:
            return curated
        candidates = self.db.fetch_all(
            """
            SELECT p.public_id, p.slug, p.title, p.summary,
                   count(*) AS shared_categories
            FROM public_wiki_revision_category mine
            JOIN public_wiki_revision_category other ON other.slug = mine.slug
            JOIN public_wiki_page p ON p.revision_id = other.revision_id
            WHERE mine.revision_id = %s AND p.slug <> %s
            GROUP BY p.public_id, p.slug, p.title, p.summary
            ORDER BY shared_categories DESC, p.title LIMIT 16
            """, (revision_id, slug),
        )
        seen = {slug, *(item["slug"] for item in curated)}
        return curated + [
            {key: item[key] for key in ("public_id", "slug", "title", "summary")}
            for item in candidates if item["slug"] not in seen
        ][:8 - len(curated)]

    def glossary_terms(self, slugs: list[str]) -> dict[str, dict[str, Any]]:
        if not slugs:
            return {}
        rows = self.db.fetch_all(
            "SELECT slug, term, definition, article_slug FROM public_wiki_glossary WHERE slug = ANY(%s)",
            (slugs,),
        )
        return {row["slug"]: row for row in rows}

    def list_glossary(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT slug, term, definition, article_slug, is_published FROM wiki_glossary ORDER BY term")

    def save_glossary(self, slug: str, term: str, definition: str, article_slug: str | None,
                      is_published: bool) -> None:
        with self.db.connection() as connection:
            connection.execute(
                """INSERT INTO wiki_glossary (slug, term, definition, article_slug, is_published)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (slug) DO UPDATE SET
                   term = excluded.term, definition = excluded.definition,
                   article_slug = excluded.article_slug, is_published = excluded.is_published""",
                (slug, term, definition, article_slug, is_published),
            )

    def search_wiki_pages(self, q: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            "SELECT slug, title FROM public_wiki_page "
            "WHERE slug ILIKE %s OR title ILIKE %s ORDER BY title LIMIT %s",
            (f"%{q}%", f"%{q}%", limit),
        )

    def public_link_targets(self, slugs: list[str]) -> dict[str, dict[str, Any]]:
        if not slugs:
            return {}
        rows = self.db.fetch_all(
            "SELECT source_slug, target_slug FROM public_wiki_redirect WHERE source_slug = ANY(%s)",
            (slugs,),
        )
        redirects = {row["source_slug"]: row["target_slug"] for row in rows}
        pages = self.db.fetch_all(
            "SELECT slug, title FROM public_wiki_page WHERE slug = ANY(%s)",
            (list(set(slugs) | set(redirects.values())),),
        )
        targets = {row["slug"]: row for row in pages}
        return {slug: targets[target] for slug in slugs
                if (target := redirects.get(slug, slug)) in targets}

    def backlinks(self, slug: str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT DISTINCT source.public_id, source.slug, source.title, source.summary
            FROM public_wiki_revision_link l
            JOIN public_wiki_page source ON source.revision_id = l.revision_id
            WHERE l.target_slug = %s OR l.target_slug IN (
                SELECT source_slug FROM public_wiki_redirect WHERE target_slug = %s
            )
            ORDER BY source.title
            """,
            (slug, slug),
        )

    def get_published(self, slug: str) -> dict[str, Any] | None:
        page = self.db.fetch_one(
            """
            SELECT page_id, public_id, slug, revision_id, revision_number,
                   title, summary, body_markdown, created_at
            FROM public_wiki_page
            WHERE slug = %s
            """,
            (slug,),
        )
        if page is None:
            redirect = self.db.fetch_one(
                "SELECT target_slug AS slug FROM public_wiki_redirect WHERE source_slug = %s",
                (slug,),
            )
            return {"redirect_slug": redirect["slug"]} if redirect else None
        page["entities"] = self.db.fetch_all(
            """
            SELECT l.public_id, l.label, l.relationship
            FROM public_wiki_revision_entity l
            WHERE l.revision_id = %s
            ORDER BY l.relationship, l.sequence, l.label
            """,
            (page["revision_id"],),
        )
        page["citations"] = self.db.fetch_all(
            """
            SELECT l.sequence, l.note, l.locator_text, l.page_label,
                   l.stable_uri, l.source_public_id, l.source_label
            FROM public_wiki_revision_citation l
            WHERE l.revision_id = %s
            ORDER BY l.sequence
            """,
            (page["revision_id"],),
        )
        page["categories"] = self.db.fetch_all(
            "SELECT slug, name FROM public_wiki_revision_category "
            "WHERE revision_id = %s ORDER BY sequence",
            (page["revision_id"],),
        )
        page["images"] = self.db.fetch_all(
            """
            SELECT public_id, storage_uri, mime_type, width_px, height_px,
                   placement, alt_text, caption
            FROM public_wiki_revision_image
            WHERE revision_id = %s ORDER BY sequence
            """,
            (page["revision_id"],),
        )
        page["series"] = self.series_navigation(page["revision_id"])
        page["metadata"] = self.db.fetch_one(
            "SELECT is_disambiguation, event_month, event_day "
            "FROM public_wiki_revision_metadata WHERE revision_id = %s",
            (page["revision_id"],),
        ) or {"is_disambiguation": False, "event_month": None, "event_day": None}
        page["template"] = self.db.fetch_one(
            "SELECT template_key, template_version, article_type, title "
            "FROM public_wiki_revision_template WHERE revision_id = %s",
            (page["revision_id"],),
        )
        page["related"] = self.related_pages(
            page["revision_id"], slug, suggest=not page["metadata"]["is_disambiguation"]
        )
        page.pop("page_id")
        page.pop("revision_id")
        return page

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        account = self.db.fetch_one(
            """
            SELECT a.account_id, a.username, a.password_hash, a.role, u.display_name
            FROM editor_account a JOIN app_user u ON u.user_id = a.account_id
            WHERE lower(a.username) = lower(%s) AND a.is_active AND u.is_active
            """,
            (username,),
        )
        if not account or not verify_password(password, account.pop("password_hash")):
            return None
        return account

    def create_session(
        self, account_id: UUID | str, token: str, csrf_token: str, hours: int
    ) -> None:
        expires_at = datetime.now(UTC) + timedelta(hours=hours)
        with self.db.connection() as connection:
            connection.execute("DELETE FROM editor_session WHERE expires_at <= now()")
            connection.execute(
                "INSERT INTO editor_session "
                "(token_hash, csrf_token_hash, account_id, expires_at) VALUES (%s, %s, %s, %s)",
                (digest_secret(token), digest_secret(csrf_token), account_id, expires_at),
            )

    def get_session(self, token: str) -> dict[str, Any] | None:
        return self.db.fetch_one(
            """
            SELECT a.account_id, a.username, a.role, u.display_name, s.csrf_token_hash
            FROM editor_session s
            JOIN editor_account a ON a.account_id = s.account_id
            JOIN app_user u ON u.user_id = a.account_id
            WHERE s.token_hash = %s AND s.expires_at > now() AND a.is_active AND u.is_active
            """,
            (digest_secret(token),),
        )

    def delete_session(self, token: str) -> None:
        with self.db.connection() as connection:
            connection.execute(
                "DELETE FROM editor_session WHERE token_hash = %s", (digest_secret(token),)
            )

    def create_account(
        self, username: str, display_name: str, password_hash: str, role: str
    ) -> str:
        if role not in {"owner", "editor", "reviewer", "viewer"}:
            raise ValueError("Invalid editorial role")
        account_id = uuid4()
        with self.db.connection() as connection:
            connection.execute(
                "INSERT INTO app_user (user_id, display_name, is_staff) VALUES (%s, %s, true)",
                (account_id, display_name),
            )
            connection.execute(
                "INSERT INTO editor_account (account_id, username, password_hash, role) "
                "VALUES (%s, %s, %s, %s)",
                (account_id, username.strip(), password_hash, role),
            )
        return str(account_id)

    def list_editor_pages(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT p.page_id, p.public_id, p.slug, p.status, p.updated_at,
                   r.revision_number, r.title,
                   (SELECT decision FROM wiki_review w WHERE w.revision_id = r.revision_id
                    ORDER BY w.created_at DESC, w.review_id DESC LIMIT 1) AS review_decision
            FROM wiki_page p JOIN wiki_revision r ON r.revision_id = p.current_revision_id
            ORDER BY p.updated_at DESC
            """
        )

    def get_editor_page(self, page_id: UUID | str) -> dict[str, Any] | None:
        page = self.db.fetch_one(
            """
            SELECT p.*, r.revision_number, r.title, r.summary, r.body_markdown,
                   r.change_note, r.created_at AS revision_created_at,
                   u.display_name AS revision_author
            FROM wiki_page p
            JOIN wiki_revision r ON r.revision_id = p.current_revision_id
            JOIN app_user u ON u.user_id = r.created_by_user_id
            WHERE p.page_id = %s
            """,
            (page_id,),
        )
        if page is None:
            return None
        revision_id = page["current_revision_id"]
        page["entity_public_ids"] = [
            row["public_id"]
            for row in self.db.fetch_all(
                "SELECT e.public_id FROM wiki_revision_entity l JOIN entity e ON e.entity_id = l.entity_id "
                "WHERE l.revision_id = %s ORDER BY l.sequence",
                (revision_id,),
            )
        ]
        page["citation_ids"] = [
            str(row["citation_id"])
            for row in self.db.fetch_all(
                "SELECT citation_id FROM wiki_revision_citation WHERE revision_id = %s ORDER BY sequence",
                (revision_id,),
            )
        ]
        page["category_names"] = [
            row["name"]
            for row in self.db.fetch_all(
                "SELECT c.name FROM wiki_revision_category l "
                "JOIN wiki_category c ON c.category_id = l.category_id "
                "WHERE l.revision_id = %s ORDER BY l.sequence",
                (revision_id,),
            )
        ]
        page["images"] = self.db.fetch_all(
            """
            SELECT e.public_id, e.preferred_label, l.placement, l.alt_text, l.caption
            FROM wiki_revision_image l JOIN entity e ON e.entity_id = l.digital_entity_id
            WHERE l.revision_id = %s ORDER BY l.sequence
            """,
            (revision_id,),
        )
        page["reviews"] = self.db.fetch_all(
            """
            SELECT w.decision, w.note, w.created_at, u.display_name
            FROM wiki_review w JOIN app_user u ON u.user_id = w.reviewer_user_id
            WHERE w.revision_id = %s ORDER BY w.created_at DESC, w.review_id DESC
            """,
            (revision_id,),
        )
        page["series_membership"] = self.db.fetch_one(
            "SELECT s.slug, m.position FROM wiki_revision_series m "
            "JOIN wiki_series s ON s.series_id = m.series_id WHERE m.revision_id = %s",
            (revision_id,),
        )
        page["related_slugs"] = [row["target_slug"] for row in self.db.fetch_all(
            "SELECT target_slug FROM wiki_revision_related WHERE revision_id = %s ORDER BY sequence",
            (revision_id,),
        )]
        page["metadata"] = self.db.fetch_one(
            "SELECT is_disambiguation, event_month, event_day FROM wiki_revision_metadata "
            "WHERE revision_id = %s", (revision_id,),
        ) or {"is_disambiguation": False, "event_month": None, "event_day": None}
        page["template"] = self.db.fetch_one(
            "SELECT link.template_key, link.template_version, link.migrated_from_version, "
            "template.article_type, template.title, "
            "(SELECT version FROM wiki_article_template latest "
            " WHERE latest.template_key = link.template_key AND latest.is_current) AS latest_version "
            "FROM wiki_revision_template link JOIN wiki_article_template template "
            "ON template.template_key = link.template_key AND template.version = link.template_version "
            "WHERE link.revision_id = %s",
            (revision_id,),
        )
        page["redirects"] = self.list_redirects(page_id)
        return page

    @staticmethod
    def _attach_reading_metadata(connection: Any, revision_id: UUID, *,
                                 series_slug: str, series_position: int | None,
                                 related_slugs: list[str], is_disambiguation: bool,
                                 event_month: int | None, event_day: int | None) -> None:
        if bool(event_month) != bool(event_day):
            raise ValueError("Both event month and day are required")
        if event_month is not None:
            try:
                datetime(2000, event_month, event_day)
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid historical month and day") from exc
        connection.execute(
            "INSERT INTO wiki_revision_metadata (revision_id, is_disambiguation, event_month, event_day) "
            "VALUES (%s, %s, %s, %s)",
            (revision_id, is_disambiguation, event_month, event_day),
        )
        if series_slug:
            series = connection.execute(
                "SELECT series_id FROM wiki_series WHERE slug = %s", (series_slug,)
            ).fetchone()
            if not series or not series_position or series_position < 1:
                raise ValueError("Choose a valid series and positive position")
            connection.execute(
                "INSERT INTO wiki_revision_series (revision_id, series_id, position) VALUES (%s, %s, %s)",
                (revision_id, series["series_id"], series_position),
            )
        elif series_position:
            raise ValueError("Series position requires a series")
        for sequence, slug in enumerate(dict.fromkeys(related_slugs), 1):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                raise ValueError("Related articles must use valid page slugs")
            connection.execute(
                "INSERT INTO wiki_revision_related (revision_id, target_slug, sequence) "
                "VALUES (%s, %s, %s)", (revision_id, slug, sequence),
            )

    def _attach_links(
        self,
        connection: Any,
        revision_id: UUID,
        entity_public_ids: list[str],
        citation_ids: list[str],
        category_names: list[str],
        images: list[dict[str, str]],
    ) -> None:
        for sequence, public_id in enumerate(dict.fromkeys(entity_public_ids), 1):
            entity = connection.execute(
                "SELECT entity_id FROM entity WHERE public_id = %s", (public_id,)
            ).fetchone()
            if not entity:
                raise ValueError(f"Unknown entity public ID: {public_id}")
            connection.execute(
                "INSERT INTO wiki_revision_entity (revision_id, entity_id, relationship, sequence) "
                "VALUES (%s, %s, 'subject', %s)",
                (revision_id, entity["entity_id"], sequence),
            )
        for sequence, citation_id in enumerate(dict.fromkeys(citation_ids), 1):
            try:
                parsed_id = UUID(citation_id)
            except ValueError as exc:
                raise ValueError(f"Invalid citation UUID: {citation_id}") from exc
            exists = connection.execute(
                "SELECT 1 FROM citation WHERE citation_id = %s", (parsed_id,)
            ).fetchone()
            if not exists:
                raise ValueError(f"Unknown citation UUID: {citation_id}")
            connection.execute(
                "INSERT INTO wiki_revision_citation (revision_id, citation_id, sequence) "
                "VALUES (%s, %s, %s)",
                (revision_id, parsed_id, sequence),
            )
        unique_categories: dict[str, str] = {}
        for name in category_names:
            clean_name = " ".join(name.split()).strip()
            if not clean_name:
                continue
            slug = self._category_slug(clean_name)
            unique_categories.setdefault(slug, clean_name)
        for sequence, (slug, clean_name) in enumerate(unique_categories.items(), 1):
            category = connection.execute(
                "SELECT category_id FROM wiki_category WHERE slug = %s", (slug,)
            ).fetchone()
            if category:
                category_id = category["category_id"]
            else:
                category_id = uuid4()
                connection.execute(
                    "INSERT INTO wiki_category (category_id, slug, name, created_by_user_id) "
                    "SELECT %s, %s, %s, created_by_user_id FROM wiki_revision WHERE revision_id = %s",
                    (category_id, slug, clean_name, revision_id),
                )
            connection.execute(
                "INSERT INTO wiki_revision_category (revision_id, category_id, sequence) "
                "VALUES (%s, %s, %s)",
                (revision_id, category_id, sequence),
            )
        unique_images = {image.get("public_id", ""): image for image in images}
        unique_images.pop("", None)
        if sum(image.get("placement", "gallery") == "lead" for image in unique_images.values()) > 1:
            raise ValueError("Only one lead image is allowed")
        for sequence, image in enumerate(unique_images.values(), 1):
            resource = connection.execute(
                "SELECT r.entity_id FROM digital_resource r JOIN entity e ON e.entity_id = r.entity_id "
                "WHERE e.public_id = %s",
                (image["public_id"],),
            ).fetchone()
            if not resource:
                raise ValueError(f"Unknown image public ID: {image['public_id']}")
            placement = image.get("placement", "gallery")
            if placement not in {"lead", "gallery", "inline"}:
                raise ValueError("Invalid image placement")
            alt_text = image.get("alt_text", "").strip()
            if not alt_text:
                raise ValueError("Every image requires alternative text")
            connection.execute(
                "INSERT INTO wiki_revision_image "
                "(revision_id, digital_entity_id, placement, alt_text, caption, sequence) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    revision_id, resource["entity_id"], placement, alt_text,
                    image.get("caption", "").strip() or None, sequence,
                ),
            )

    @staticmethod
    def _attach_wiki_links(connection: Any, revision_id: UUID, body: str) -> None:
        for sequence, slug in enumerate(wiki_link_slugs(body), 1):
            connection.execute(
                "INSERT INTO wiki_revision_link (revision_id, target_slug, sequence) "
                "VALUES (%s, %s, %s)", (revision_id, slug, sequence),
            )

    @staticmethod
    def _attach_template(connection: Any, revision_id: UUID, template_key: str,
                         template_version: int | None,
                         migrated_from_version: int | None = None) -> None:
        if not template_key:
            return
        template = connection.execute(
            "SELECT version FROM wiki_article_template WHERE template_key = %s "
            "AND (%s::integer IS NULL AND is_current OR version = %s) "
            "ORDER BY version DESC LIMIT 1",
            (template_key, template_version, template_version),
        ).fetchone()
        if not template:
            raise ValueError("Unknown article template version")
        connection.execute(
            "INSERT INTO wiki_revision_template "
            "(revision_id, template_key, template_version, migrated_from_version) "
            "VALUES (%s, %s, %s, %s)",
            (revision_id, template_key, template["version"], migrated_from_version),
        )

    @staticmethod
    def _category_slug(name: str) -> str:
        value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
        value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        if not value:
            raise ValueError("Category name must contain a letter or number")
        return value

    def create_page(
        self,
        *,
        slug: str,
        title: str,
        summary: str,
        body_markdown: str,
        change_note: str,
        user_id: UUID | str,
        entity_public_ids: list[str],
        citation_ids: list[str],
        category_names: list[str],
        images: list[dict[str, str]],
        series_slug: str = "",
        series_position: int | None = None,
        related_slugs: list[str] | None = None,
        is_disambiguation: bool = False,
        event_month: int | None = None,
        event_day: int | None = None,
        template_key: str = "",
        template_version: int | None = None,
        migrated_from_version: int | None = None,
    ) -> str:
        page_id, revision_id = uuid4(), uuid4()
        public_id = f"FH-WIKI-{str(page_id).split('-')[0].upper()}"
        with self.db.connection() as connection:
            if connection.execute(
                "SELECT 1 FROM wiki_redirect WHERE source_slug = %s", (slug,)
            ).fetchone():
                raise ValueError("Page slug is reserved by a redirect")
            connection.execute(
                "INSERT INTO wiki_page (page_id, public_id, slug, created_by_user_id) "
                "VALUES (%s, %s, %s, %s)",
                (page_id, public_id, slug, user_id),
            )
            connection.execute(
                "INSERT INTO wiki_revision (revision_id, page_id, revision_number, title, summary, "
                "body_markdown, change_note, created_by_user_id) VALUES (%s, %s, 1, %s, %s, %s, %s, %s)",
                (revision_id, page_id, title, summary or None, body_markdown, change_note or None, user_id),
            )
            self._attach_links(
                connection, revision_id, entity_public_ids, citation_ids,
                category_names, images,
            )
            self._attach_wiki_links(connection, revision_id, body_markdown)
            self._attach_template(
                connection, revision_id, template_key, template_version, migrated_from_version
            )
            self._attach_reading_metadata(
                connection, revision_id, series_slug=series_slug, series_position=series_position,
                related_slugs=related_slugs or [], is_disambiguation=is_disambiguation,
                event_month=event_month, event_day=event_day,
            )
            connection.execute(
                "UPDATE wiki_page SET current_revision_id = %s WHERE page_id = %s",
                (revision_id, page_id),
            )
        return str(page_id)

    def add_revision(
        self,
        page_id: UUID | str,
        *,
        title: str,
        summary: str,
        body_markdown: str,
        change_note: str,
        user_id: UUID | str,
        entity_public_ids: list[str],
        citation_ids: list[str],
        category_names: list[str],
        images: list[dict[str, str]],
        series_slug: str = "",
        series_position: int | None = None,
        related_slugs: list[str] | None = None,
        is_disambiguation: bool = False,
        event_month: int | None = None,
        event_day: int | None = None,
        template_key: str = "",
        template_version: int | None = None,
        migrated_from_version: int | None = None,
    ) -> None:
        revision_id = uuid4()
        with self.db.connection() as connection:
            locked = connection.execute(
                "SELECT page_id FROM wiki_page WHERE page_id = %s FOR UPDATE", (page_id,)
            ).fetchone()
            if not locked:
                raise ValueError("Wiki page not found")
            page = connection.execute(
                "SELECT COALESCE(max(revision_number), 0) + 1 AS next_number "
                "FROM wiki_revision WHERE page_id = %s",
                (page_id,),
            ).fetchone()
            connection.execute(
                "INSERT INTO wiki_revision (revision_id, page_id, revision_number, title, summary, "
                "body_markdown, change_note, created_by_user_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (revision_id, page_id, page["next_number"], title, summary or None, body_markdown, change_note or None, user_id),
            )
            self._attach_links(
                connection, revision_id, entity_public_ids, citation_ids,
                category_names, images,
            )
            self._attach_wiki_links(connection, revision_id, body_markdown)
            self._attach_template(
                connection, revision_id, template_key, template_version, migrated_from_version
            )
            self._attach_reading_metadata(
                connection, revision_id, series_slug=series_slug, series_position=series_position,
                related_slugs=related_slugs or [], is_disambiguation=is_disambiguation,
                event_month=event_month, event_day=event_day,
            )
            connection.execute(
                "UPDATE wiki_page SET current_revision_id = %s, status = 'draft' WHERE page_id = %s",
                (revision_id, page_id),
            )

    def review(self, page_id: UUID | str, decision: str, note: str, user_id: UUID | str) -> None:
        states = {
            "submitted": "in_review",
            "approved": "approved",
            "changes_requested": "draft",
        }
        if decision not in states:
            raise ValueError("Invalid review decision")
        with self.db.connection() as connection:
            page = connection.execute(
                "SELECT current_revision_id, status FROM wiki_page WHERE page_id = %s FOR UPDATE",
                (page_id,),
            ).fetchone()
            if not page:
                raise ValueError("Wiki page not found")
            required_state = "draft" if decision == "submitted" else "in_review"
            if page["status"] != required_state:
                raise ValueError(
                    f"Cannot record {decision!r} while page is {page['status']!r}"
                )
            connection.execute(
                "INSERT INTO wiki_review (review_id, revision_id, decision, note, reviewer_user_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (uuid4(), page["current_revision_id"], decision, note or None, user_id),
            )
            connection.execute(
                "UPDATE wiki_page SET status = %s WHERE page_id = %s",
                (states[decision], page_id),
            )

    def publish(self, page_id: UUID | str) -> None:
        with self.db.connection() as connection:
            result = connection.execute(
                "UPDATE wiki_page SET published_revision_id = current_revision_id, status = 'published' "
                "WHERE page_id = %s AND status = 'approved' RETURNING page_id",
                (page_id,),
            ).fetchone()
            if not result:
                raise ValueError("Only an approved revision can be published")
            connection.execute(
                "INSERT INTO wiki_publication (revision_id, page_id) "
                "SELECT published_revision_id, page_id FROM wiki_page WHERE page_id = %s "
                "ON CONFLICT (revision_id) DO NOTHING", (page_id,),
            )
            connection.execute(
                """
                UPDATE entity SET visibility = 'public', record_status = 'published'
                WHERE entity_id IN (
                    SELECT digital_entity_id FROM wiki_revision_image
                    WHERE revision_id = (
                        SELECT published_revision_id FROM wiki_page WHERE page_id = %s
                    )
                )
                """,
                (page_id,),
            )

    def search_entities(self, q: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT e.public_id, e.preferred_label AS label, t.code AS type_code
            FROM entity e JOIN taxonomy_term t ON t.term_id = e.entity_type_term_id
            WHERE e.preferred_label ILIKE '%%' || %s || '%%'
               OR e.public_id ILIKE '%%' || %s || '%%'
            ORDER BY CASE WHEN e.preferred_label ILIKE %s || '%%' THEN 0 ELSE 1 END,
                     e.preferred_label LIMIT %s
            """,
            (q, q, q, limit),
        )

    def search_citations(self, q: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT c.citation_id, s.public_id AS source_public_id,
                   s.preferred_label AS source_label, c.locator_text,
                   c.page_label, left(c.excerpt, 180) AS excerpt
            FROM citation c JOIN entity s ON s.entity_id = c.source_entity_id
            WHERE s.preferred_label ILIKE '%%' || %s || '%%'
               OR coalesce(c.locator_text, '') ILIKE '%%' || %s || '%%'
               OR coalesce(c.excerpt, '') ILIKE '%%' || %s || '%%'
            ORDER BY s.preferred_label, c.page_label NULLS LAST LIMIT %s
            """,
            (q, q, q, limit),
        )

    def search_media(self, q: str, limit: int = 12) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT e.public_id, e.preferred_label AS label, r.storage_uri,
                   r.mime_type, r.width_px, r.height_px
            FROM digital_resource r JOIN entity e ON e.entity_id = r.entity_id
            WHERE r.mime_type LIKE 'image/%%'
              AND (e.preferred_label ILIKE '%%' || %s || '%%'
                   OR e.public_id ILIKE '%%' || %s || '%%')
            ORDER BY e.preferred_label LIMIT %s
            """,
            (q, q, limit),
        )

    def register_media(
        self,
        *,
        sha256: str,
        storage_uri: str,
        original_filename: str,
        mime_type: str,
        file_size_bytes: int,
        width_px: int,
        height_px: int,
        user_id: UUID | str,
    ) -> dict[str, Any]:
        with self.db.connection() as connection:
            existing = connection.execute(
                """
                SELECT e.public_id, e.preferred_label AS label, r.storage_uri,
                       r.mime_type, r.width_px, r.height_px
                FROM digital_resource r JOIN entity e ON e.entity_id = r.entity_id
                WHERE r.sha256 = %s
                """,
                (sha256,),
            ).fetchone()
            if existing:
                return existing
            term = connection.execute(
                "SELECT term_id FROM taxonomy_term WHERE code = 'ENT.DIG'"
            ).fetchone()
            if not term:
                raise ValueError("ENT.DIG taxonomy term is not loaded")
            entity_id = uuid4()
            public_id = f"FH-DIG-{str(entity_id).split('-')[0].upper()}"
            connection.execute(
                """
                INSERT INTO entity (
                    entity_id, public_id, entity_type_term_id, preferred_label,
                    record_status, visibility, created_by_user_id, updated_by_user_id
                ) VALUES (%s, %s, %s, %s, 'draft', 'staff', %s, %s)
                """,
                (entity_id, public_id, term["term_id"], original_filename, user_id, user_id),
            )
            connection.execute(
                """
                INSERT INTO digital_resource (
                    entity_id, storage_uri, original_filename, mime_type,
                    file_size_bytes, sha256, width_px, height_px
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entity_id, storage_uri, original_filename, mime_type,
                    file_size_bytes, sha256, width_px, height_px,
                ),
            )
            return {
                "public_id": public_id, "label": original_filename,
                "storage_uri": storage_uri, "mime_type": mime_type,
                "width_px": width_px, "height_px": height_px,
            }

    def media_is_public(self, storage_uri: str) -> bool:
        return self.db.fetch_one(
            "SELECT 1 AS allowed FROM public_wiki_revision_image WHERE storage_uri = %s LIMIT 1",
            (storage_uri,),
        ) is not None

    def media_exists(self, storage_uri: str) -> bool:
        return self.db.fetch_one(
            "SELECT 1 AS allowed FROM digital_resource WHERE storage_uri = %s LIMIT 1",
            (storage_uri,),
        ) is not None

    def list_revisions(self, page_id: UUID | str) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT r.revision_number, r.title, r.summary, r.change_note, r.created_at,
                   u.display_name AS author,
                   (p.published_revision_id = r.revision_id) AS is_published
            FROM wiki_revision r
            JOIN wiki_page p ON p.page_id = r.page_id
            JOIN app_user u ON u.user_id = r.created_by_user_id
            WHERE r.page_id = %s ORDER BY r.revision_number DESC
            """,
            (page_id,),
        )

    def get_revision(self, page_id: UUID | str, number: int) -> dict[str, Any] | None:
        return self.db.fetch_one(
            """
            SELECT r.revision_number, r.title, r.summary, r.body_markdown,
                   r.change_note, r.created_at, u.display_name AS author
            FROM wiki_revision r JOIN app_user u ON u.user_id = r.created_by_user_id
            WHERE r.page_id = %s AND r.revision_number = %s
            """,
            (page_id, number),
        )
