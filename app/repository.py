"""Read models built directly from the canonical Food History schema."""

import base64
import json
from typing import Any

from app.db import Database


def encode_cursor(*values: object) -> str:
    payload = json.dumps(values, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str | None, expected: int) -> list[Any] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        values = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
    if not isinstance(values, list) or len(values) != expected:
        raise ValueError("Invalid cursor")
    return values


class Repository:
    """Query-only repository; all writes remain in the ingestion subsystem."""

    def __init__(self, database: Database):
        self.db = database

    @staticmethod
    def _term(code: str | None, label: str | None) -> dict[str, str] | None:
        return {"code": code, "label": label} if code and label else None

    @classmethod
    def _entity_ref(cls, row: dict[str, Any], prefix: str = "") -> dict[str, Any] | None:
        public_id = row.get(f"{prefix}public_id")
        if not public_id:
            return None
        result: dict[str, Any] = {
            "public_id": public_id,
            "label": row.get(f"{prefix}label"),
        }
        entity_type = cls._term(
            row.get(f"{prefix}type_code"), row.get(f"{prefix}type_label")
        )
        if entity_type:
            result["type"] = entity_type
        return result

    @classmethod
    def _entity_summary(cls, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "public_id": row["public_id"],
            "preferred_label": row["preferred_label"],
            "slug": row.get("canonical_slug"),
            "type": cls._term(row["entity_type_code"], row["entity_type_label"]),
            "summary": row.get("summary"),
            "record_status": row["record_status"],
            "visibility": row["visibility"],
        }

    def list_entities(
        self,
        *,
        q: str | None = None,
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        after = decode_cursor(cursor, 2)
        rows = self.db.fetch_all(
            """
            WITH RECURSIVE selected_terms AS (
                SELECT term_id FROM taxonomy_term WHERE code = %s
                UNION ALL
                SELECT edge.child_term_id
                FROM taxonomy_edge edge
                JOIN selected_terms parent ON parent.term_id = edge.parent_term_id
                WHERE edge.edge_type = 'broader'
            )
            SELECT e.public_id, e.preferred_label, e.canonical_slug,
                   e.summary, e.record_status, e.visibility,
                   type.code AS entity_type_code,
                   type.preferred_label AS entity_type_label
            FROM entity e
            JOIN taxonomy_term type ON type.term_id = e.entity_type_term_id
            WHERE e.visibility = 'public'
              AND (%s IS NULL OR type.code = %s)
              AND (%s IS NULL OR e.preferred_label ILIKE '%%' || %s || '%%'
                   OR EXISTS (
                       SELECT 1 FROM entity_name name
                       WHERE name.entity_id = e.entity_id
                         AND name.name_text ILIKE '%%' || %s || '%%'
                   ))
              AND (%s IS NULL OR EXISTS (
                  SELECT 1 FROM entity_term_assignment assignment
                  WHERE assignment.entity_id = e.entity_id
                    AND assignment.term_id IN (SELECT term_id FROM selected_terms)
              ))
              AND (%s IS NULL OR (lower(e.preferred_label), e.public_id) > (%s, %s))
            ORDER BY lower(e.preferred_label), e.public_id
            LIMIT %s
            """,
            (
                term_code,
                type_code,
                type_code,
                q,
                q,
                q,
                term_code,
                after[0] if after else None,
                after[0] if after else "",
                after[1] if after else "",
                limit + 1,
            ),
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [self._entity_summary(row) for row in rows],
            "next_cursor": (
                encode_cursor(rows[-1]["preferred_label"].lower(), rows[-1]["public_id"])
                if has_more
                else None
            ),
        }

    def get_entity(self, public_id: str) -> dict[str, Any] | None:
        row = self.db.fetch_one(
            """
            SELECT e.public_id, e.preferred_label, e.canonical_slug, e.summary,
                   e.record_status, e.visibility, e.entity_id,
                   type.code AS entity_type_code,
                   type.preferred_label AS entity_type_label
            FROM entity e
            JOIN taxonomy_term type ON type.term_id = e.entity_type_term_id
            WHERE e.public_id = %s AND e.visibility = 'public'
            """,
            (public_id,),
        )
        if not row:
            return None
        entity = self._entity_summary(row)
        entity["names"] = self.db.fetch_all(
            """
            SELECT name_type AS type, name_text AS text, language_tag AS language,
                   script_code AS script, valid_from_edtf AS valid_from,
                   valid_to_edtf AS valid_to
            FROM entity_name WHERE entity_id = %s
            ORDER BY is_preferred DESC, name_text
            """,
            (row["entity_id"],),
        )
        entity["identifiers"] = self.db.fetch_all(
            """
            SELECT scheme_code AS scheme, identifier_value AS value,
                   identifier_uri AS uri
            FROM external_identifier WHERE entity_id = %s
            ORDER BY is_primary_for_scheme DESC, scheme_code, identifier_value
            """,
            (row["entity_id"],),
        )
        assignments = self.db.fetch_all(
            """
            SELECT assignment.assignment_kind AS kind, assignment.is_primary AS primary,
                   term.code, term.preferred_label
            FROM entity_term_assignment assignment
            JOIN taxonomy_term term ON term.term_id = assignment.term_id
            WHERE assignment.entity_id = %s
            ORDER BY assignment.assignment_kind, assignment.is_primary DESC,
                     assignment.sequence NULLS LAST, term.preferred_label
            """,
            (row["entity_id"],),
        )
        entity["terms"] = [
            {
                "kind": assignment["kind"],
                "primary": assignment["primary"],
                "term": self._term(assignment["code"], assignment["preferred_label"]),
            }
            for assignment in assignments
        ]
        image = self.db.fetch_one(
            """
            SELECT representation.role_code AS role, resource.storage_uri AS uri,
                   resource.iiif_manifest_uri, resource.mime_type,
                   resource.width_px, resource.height_px, representation.caption
            FROM digital_representation representation
            JOIN digital_resource resource ON resource.entity_id = representation.digital_entity_id
            JOIN entity digital ON digital.entity_id = resource.entity_id
            WHERE representation.represented_entity_id = %s
              AND digital.visibility = 'public'
              AND representation.is_primary = true
            ORDER BY representation.sequence NULLS LAST
            LIMIT 1
            """,
            (row["entity_id"],),
        )
        entity["primary_image"] = image
        return entity

    def get_assertions(
        self, public_id: str, predicate_code: str | None = None
    ) -> list[dict[str, Any]] | None:
        subject = self.db.fetch_one(
            "SELECT entity_id FROM entity WHERE public_id = %s AND visibility = 'public'",
            (public_id,),
        )
        if not subject:
            return None
        rows = self.db.fetch_all(
            """
            SELECT assertion.*, predicate.code AS predicate_code,
                   predicate.preferred_label AS predicate_label,
                   object.public_id AS object_public_id,
                   object.preferred_label AS object_label,
                   object_type.code AS object_type_code,
                   object_type.preferred_label AS object_type_label,
                   status.code AS status_code, status.preferred_label AS status_label,
                   confidence.code AS confidence_code,
                   confidence.preferred_label AS confidence_label
            FROM assertion
            JOIN taxonomy_term predicate ON predicate.term_id = assertion.predicate_term_id
            LEFT JOIN entity object ON object.entity_id = assertion.object_entity_id
                                      AND object.visibility = 'public'
            LEFT JOIN taxonomy_term object_type ON object_type.term_id = object.entity_type_term_id
            LEFT JOIN taxonomy_term status ON status.term_id = assertion.claim_status_term_id
            LEFT JOIN taxonomy_term confidence ON confidence.term_id = assertion.confidence_term_id
            WHERE assertion.subject_entity_id = %s
              AND (%s IS NULL OR predicate.code = %s)
            ORDER BY assertion.is_preferred DESC, assertion.created_at, assertion.assertion_id
            """,
            (subject["entity_id"], predicate_code, predicate_code),
        )
        results = []
        for row in rows:
            value = {
                "text": row["value_text"],
                "number": row["value_number"],
                "date": row["value_date"],
                "boolean": row["value_boolean"],
                "json": row["value_json"],
            }.get(row["value_kind"])
            evidence = self.db.fetch_all(
                """
                SELECT link.evidence_role AS role, source.public_id AS source_public_id,
                       source.preferred_label AS source_label,
                       source_type.code AS source_type_code,
                       source_type.preferred_label AS source_type_label,
                       citation.locator_text AS locator, citation.page_label AS page,
                       citation.folio_label AS folio, citation.image_label AS image,
                       citation.stable_uri, citation.excerpt
                FROM assertion_evidence link
                JOIN citation ON citation.citation_id = link.citation_id
                JOIN entity source ON source.entity_id = citation.source_entity_id
                JOIN taxonomy_term source_type ON source_type.term_id = source.entity_type_term_id
                WHERE link.assertion_id = %s AND source.visibility = 'public'
                ORDER BY link.evidence_role, link.assertion_evidence_id
                """,
                (row["assertion_id"],),
            )
            results.append(
                {
                    "predicate": self._term(row["predicate_code"], row["predicate_label"]),
                    "value_kind": row["value_kind"],
                    "object": self._entity_ref(row, "object_"),
                    "value": value,
                    "valid_from": row["valid_from_edtf"],
                    "valid_to": row["valid_to_edtf"],
                    "status": self._term(row["status_code"], row["status_label"]),
                    "confidence": self._term(
                        row["confidence_code"], row["confidence_label"]
                    ),
                    "preferred": row["is_preferred"],
                    "evidence": [
                        {
                            "role": item["role"],
                            "citation": {
                                "source": self._entity_ref(item, "source_"),
                                "locator": item["locator"],
                                "page": item["page"],
                                "folio": item["folio"],
                                "image": item["image"],
                                "stable_uri": item["stable_uri"],
                                "excerpt": item["excerpt"],
                            },
                        }
                        for item in evidence
                    ],
                }
            )
        return results

    def list_taxonomy_terms(
        self, vocabulary_code: str, parent_code: str | None = None, q: str | None = None
    ) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            """
            SELECT term.code, vocabulary.code AS vocabulary_code,
                   term.preferred_label, term.scope_note, term.term_status AS status
            FROM taxonomy_term term
            JOIN vocabulary ON vocabulary.vocabulary_id = term.vocabulary_id
            WHERE vocabulary.code = %s
              AND (%s IS NULL OR term.preferred_label ILIKE '%%' || %s || '%%'
                   OR EXISTS (SELECT 1 FROM taxonomy_label label
                              WHERE label.term_id = term.term_id
                                AND label.label_text ILIKE '%%' || %s || '%%'))
              AND (%s IS NULL OR EXISTS (
                  SELECT 1 FROM taxonomy_edge edge
                  JOIN taxonomy_term parent ON parent.term_id = edge.parent_term_id
                  WHERE edge.child_term_id = term.term_id
                    AND edge.edge_type = 'broader' AND parent.code = %s
              ))
            ORDER BY COALESCE(term.sort_key, term.preferred_label), term.code
            """,
            (vocabulary_code, q, q, q, parent_code, parent_code),
        )
        return [self._taxonomy_summary(row) for row in rows]

    @staticmethod
    def _taxonomy_summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "code": row["code"],
            "vocabulary_code": row["vocabulary_code"],
            "preferred_label": row["preferred_label"],
            "scope_note": row.get("scope_note"),
            "status": row["status"],
        }

    def list_vocabularies(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT vocabulary.code, vocabulary.name, vocabulary.version,
                   vocabulary.description, count(term.term_id) AS term_count
            FROM vocabulary
            LEFT JOIN taxonomy_term term ON term.vocabulary_id = vocabulary.vocabulary_id
            GROUP BY vocabulary.vocabulary_id
            ORDER BY vocabulary.code
            """
        )

    def get_taxonomy_term(self, code: str) -> dict[str, Any] | None:
        row = self.db.fetch_one(
            """
            SELECT term.term_id, term.code, vocabulary.code AS vocabulary_code,
                   term.preferred_label, term.scope_note, term.term_status AS status
            FROM taxonomy_term term
            JOIN vocabulary ON vocabulary.vocabulary_id = term.vocabulary_id
            WHERE term.code = %s
            """,
            (code,),
        )
        if not row:
            return None
        result = self._taxonomy_summary(row)
        for relation, select_id in (("broader", "parent_term_id"), ("narrower", "child_term_id")):
            join_id = "child_term_id" if relation == "broader" else "parent_term_id"
            result[relation] = self.db.fetch_all(
                f"""
                SELECT related.code, related.preferred_label AS label
                FROM taxonomy_edge edge
                JOIN taxonomy_term related ON related.term_id = edge.{select_id}
                WHERE edge.{join_id} = %s AND edge.edge_type = 'broader'
                ORDER BY edge.sequence NULLS LAST, related.preferred_label
                """,
                (row["term_id"],),
            )
        result["labels"] = self.db.fetch_all(
            """
            SELECT label_type AS type, label_text AS text, language_tag AS language,
                   script_code AS script
            FROM taxonomy_label WHERE term_id = %s
            ORDER BY is_preferred_in_language DESC, label_type, label_text
            """,
            (row["term_id"],),
        )
        return result

    def get_menu(self, public_id: str) -> dict[str, Any] | None:
        entity = self.get_entity(public_id)
        if not entity:
            return None
        menu = self.db.fetch_one(
            """
            SELECT menu.entity_id, menu.service_date_edtf AS service_date,
                   menu.currency_code, type.code AS menu_type_code,
                   type.preferred_label AS menu_type_label,
                   establishment.public_id AS establishment_public_id,
                   establishment.preferred_label AS establishment_label,
                   establishment_type.code AS establishment_type_code,
                   establishment_type.preferred_label AS establishment_type_label
            FROM menu
            JOIN taxonomy_term type ON type.term_id = menu.menu_type_term_id
            LEFT JOIN entity establishment ON establishment.entity_id = menu.establishment_entity_id
                                          AND establishment.visibility = 'public'
            LEFT JOIN taxonomy_term establishment_type
                   ON establishment_type.term_id = establishment.entity_type_term_id
            WHERE menu.entity_id = (SELECT entity_id FROM entity WHERE public_id = %s)
            """,
            (public_id,),
        )
        if not menu:
            return None
        entity.update(
            {
                "menu_type": self._term(menu["menu_type_code"], menu["menu_type_label"]),
                "establishment": self._entity_ref(menu, "establishment_"),
                "service_date": menu["service_date"],
                "currency_code": menu["currency_code"],
                "sections": [],
            }
        )
        sections = self.db.fetch_all(
            """
            SELECT menu_section_id, sequence, heading_original
            FROM menu_section WHERE menu_entity_id = %s
            ORDER BY sequence, menu_section_id
            """,
            (menu["entity_id"],),
        )
        unsectioned = {"sequence": 0, "heading_original": None, "items": []}
        by_id = {}
        for section in sections:
            section["items"] = []
            by_id[section.pop("menu_section_id")] = section
            entity["sections"].append(section)
        items = self.db.fetch_all(
            """
            SELECT item.menu_section_id, item.sequence, item.printed_name,
                   item.printed_description, item.portion_text AS portion,
                   item.price_text, item.price_amount,
                   COALESCE(item.currency_code, menu.currency_code) AS currency_code,
                   food.public_id AS food_public_id, food.preferred_label AS food_label,
                   food_type.code AS food_type_code,
                   food_type.preferred_label AS food_type_label
            FROM menu_item item
            JOIN menu ON menu.entity_id = item.menu_entity_id
            LEFT JOIN entity food ON food.entity_id = item.normalized_food_entity_id
                                 AND food.visibility = 'public'
            LEFT JOIN taxonomy_term food_type ON food_type.term_id = food.entity_type_term_id
            WHERE item.menu_entity_id = %s
            ORDER BY item.sequence, item.menu_item_id
            """,
            (menu["entity_id"],),
        )
        for item in items:
            section_id = item.pop("menu_section_id")
            item["normalized_food"] = self._entity_ref(item, "food_")
            for key in ("food_public_id", "food_label", "food_type_code", "food_type_label"):
                item.pop(key, None)
            target = by_id.get(section_id) if section_id is not None else None
            (target if target is not None else unsectioned)["items"].append(item)
        if unsectioned["items"]:
            entity["sections"].insert(0, unsectioned)
        entity["images"] = self.db.fetch_all(
            """
            SELECT representation.role_code AS role, resource.storage_uri AS uri,
                   resource.iiif_manifest_uri, resource.mime_type,
                   resource.width_px, resource.height_px, representation.caption
            FROM digital_representation representation
            JOIN digital_resource resource ON resource.entity_id = representation.digital_entity_id
            JOIN entity digital ON digital.entity_id = resource.entity_id
            WHERE representation.represented_entity_id = %s
              AND digital.visibility = 'public'
            ORDER BY representation.is_primary DESC, representation.sequence NULLS LAST
            """,
            (menu["entity_id"],),
        )
        return entity

    def get_menu_occurrences(
        self,
        public_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        place_id: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any] | None:
        food = self.db.fetch_one(
            "SELECT entity_id FROM entity WHERE public_id = %s AND visibility = 'public'",
            (public_id,),
        )
        if not food:
            return None
        after = decode_cursor(cursor, 3)
        rows = self.db.fetch_all(
            """
            SELECT occurrence.menu_item_id, occurrence.menu_public_id,
                   occurrence.menu_label, occurrence.service_date_edtf AS service_date,
                   occurrence.establishment_public_id, occurrence.establishment_label,
                   occurrence.sequence, occurrence.printed_name,
                   occurrence.printed_description, occurrence.portion_text AS portion,
                   occurrence.price_text, occurrence.price_amount, occurrence.currency_code
            FROM v_menu_item_occurrence occurrence
            WHERE occurrence.normalized_food_entity_id = %s
              AND (%s IS NULL OR occurrence.service_date_edtf >= %s)
              AND (%s IS NULL OR occurrence.service_date_edtf <= %s)
              AND (%s IS NULL OR occurrence.establishment_public_id = %s)
              AND (%s IS NULL OR (occurrence.menu_public_id, occurrence.sequence,
                                   occurrence.menu_item_id) > (%s, %s, %s::uuid))
            ORDER BY occurrence.menu_public_id, occurrence.sequence, occurrence.menu_item_id
            LIMIT %s
            """,
            (
                food["entity_id"], date_from, date_from, date_to, date_to,
                place_id, place_id,
                after[0] if after else None,
                after[0] if after else "", after[1] if after else -1,
                after[2] if after else "00000000-0000-0000-0000-000000000000",
                limit + 1,
            ),
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for row in rows:
            item_id = row.pop("menu_item_id")
            item = dict(row)
            item["menu"] = {
                "public_id": item.pop("menu_public_id"),
                "label": item.pop("menu_label"),
            }
            if item.get("establishment_public_id"):
                item["establishment"] = {
                    "public_id": item.pop("establishment_public_id"),
                    "label": item.pop("establishment_label"),
                }
            else:
                item.pop("establishment_public_id", None)
                item.pop("establishment_label", None)
                item["establishment"] = None
            item["_cursor_id"] = str(item_id)
            items.append(item)
        next_cursor = None
        if has_more:
            last = items[-1]
            next_cursor = encode_cursor(
                last["menu"]["public_id"], last["sequence"], last["_cursor_id"]
            )
        for item in items:
            item.pop("_cursor_id", None)
        return {"items": items, "next_cursor": next_cursor}

    def search(
        self,
        q: str,
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        after = decode_cursor(cursor, 2)
        rows = self.db.fetch_all(
            """
            WITH RECURSIVE selected_terms AS (
                SELECT term_id FROM taxonomy_term WHERE code = %s
                UNION ALL
                SELECT edge.child_term_id FROM taxonomy_edge edge
                JOIN selected_terms parent ON parent.term_id = edge.parent_term_id
                WHERE edge.edge_type = 'broader'
            ), ranked AS (
                SELECT e.entity_id, e.public_id, e.preferred_label AS label,
                       type.code AS type_code, type.preferred_label AS type_label,
                       e.summary,
                       GREATEST(
                           CASE WHEN lower(e.preferred_label) = lower(%s) THEN 1.0 ELSE 0 END,
                           CASE WHEN e.preferred_label ILIKE %s || '%%' THEN 0.9 ELSE 0 END,
                           similarity(e.preferred_label, %s),
                           COALESCE((SELECT max(similarity(name.name_text, %s))
                                     FROM entity_name name WHERE name.entity_id = e.entity_id), 0),
                           COALESCE((SELECT max(similarity(item.printed_name, %s))
                                     FROM menu_item item WHERE item.menu_entity_id = e.entity_id), 0),
                           COALESCE((SELECT max(similarity(mark.normalized_text, %s))
                                     FROM object_mark mark WHERE mark.entity_id = e.entity_id), 0),
                           COALESCE((SELECT max(ts_rank(to_tsvector('simple', transcription.text_content),
                                                       plainto_tsquery('simple', %s)))
                                     FROM transcription WHERE transcription.source_entity_id = e.entity_id), 0)
                       ) AS score
                FROM entity e
                JOIN taxonomy_term type ON type.term_id = e.entity_type_term_id
                WHERE e.visibility = 'public'
                  AND (%s IS NULL OR type.code = %s)
                  AND (%s IS NULL OR EXISTS (
                      SELECT 1 FROM entity_term_assignment assignment
                      WHERE assignment.entity_id = e.entity_id
                        AND assignment.term_id IN (SELECT term_id FROM selected_terms)
                  ))
            )
            SELECT * FROM ranked
            WHERE score >= 0.08
              AND (%s IS NULL OR (score, public_id) < (%s, %s))
            ORDER BY score DESC, public_id
            LIMIT %s
            """,
            (
                term_code, q, q, q, q, q, q, q,
                type_code, type_code, term_code,
                after[0] if after else None,
                after[0] if after else 0, after[1] if after else "",
                limit + 1,
            ),
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [
            {
                "entity": {
                    "public_id": row["public_id"],
                    "label": row["label"],
                    "type": self._term(row["type_code"], row["type_label"]),
                },
                "score": float(row["score"]),
                "snippet": row["summary"],
                "matched_fields": ["preferred_label"],
            }
            for row in rows
        ]
        type_facets: dict[str, int] = {}
        for item in items:
            code = item["entity"]["type"]["code"]
            type_facets[code] = type_facets.get(code, 0) + 1
        return {
            "items": items,
            "facets": {"type_code": type_facets},
            "next_cursor": (
                encode_cursor(float(rows[-1]["score"]), rows[-1]["public_id"])
                if has_more
                else None
            ),
        }
