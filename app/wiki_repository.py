"""Wiki read models and tightly scoped private editorial writes."""

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.auth import digest_secret, verify_password
from app.db import Database


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
        return page

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
    ) -> str:
        page_id, revision_id = uuid4(), uuid4()
        public_id = f"FH-WIKI-{str(page_id).split('-')[0].upper()}"
        with self.db.connection() as connection:
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
