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
              AND (%s::text IS NULL OR type.code = %s)
              AND (%s::text IS NULL OR e.preferred_label ILIKE '%%' || %s || '%%'
                   OR EXISTS (
                       SELECT 1 FROM entity_name name
                       WHERE name.entity_id = e.entity_id
                         AND name.name_text ILIKE '%%' || %s || '%%'
                   ))
              AND (%s::text IS NULL OR EXISTS (
                  SELECT 1 FROM entity_term_assignment assignment
                  WHERE assignment.entity_id = e.entity_id
                    AND assignment.term_id IN (SELECT term_id FROM selected_terms)
              ))
              AND (%s::text IS NULL OR (lower(e.preferred_label), e.public_id) > (%s, %s))
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
            ORDER BY is_preferred_in_language DESC, name_text
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
              AND (%s::text IS NULL OR predicate.code = %s)
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
              AND (%s::text IS NULL OR term.preferred_label ILIKE '%%' || %s || '%%'
                   OR EXISTS (SELECT 1 FROM taxonomy_label label
                              WHERE label.term_id = term.term_id
                                AND label.label_text ILIKE '%%' || %s || '%%'))
              AND (%s::text IS NULL OR EXISTS (
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
              AND (%s::text IS NULL OR occurrence.service_date_edtf >= %s)
              AND (%s::text IS NULL OR occurrence.service_date_edtf <= %s)
              AND (%s::text IS NULL OR occurrence.establishment_public_id = %s)
              AND (%s::text IS NULL OR (occurrence.menu_public_id, occurrence.sequence,
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

    def get_work(self, public_id: str) -> dict[str, Any] | None:
        entity = self.get_entity(public_id)
        if not entity:
            return None
        work = self.db.fetch_one(
            """
            SELECT work.entity_id, work.original_language_tag, work.creation_edtf,
                   type.code AS work_type_code, type.preferred_label AS work_type_label
            FROM work
            LEFT JOIN taxonomy_term type ON type.term_id = work.work_type_term_id
            WHERE work.entity_id = (SELECT entity_id FROM entity WHERE public_id = %s)
            """,
            (public_id,),
        )
        if not work:
            return None
        entity.update(
            {
                "work_type": self._term(work["work_type_code"], work["work_type_label"]),
                "original_language": work["original_language_tag"],
                "creation_date": work["creation_edtf"],
            }
        )
        credits = self.db.fetch_all(
            """
            SELECT agent.public_id AS agent_public_id,
                   agent.preferred_label AS agent_label,
                   agent_type.code AS agent_type_code,
                   agent_type.preferred_label AS agent_type_label,
                   role.code AS role_code, role.preferred_label AS role_label,
                   credit.credited_as, credit.sequence
            FROM credit
            JOIN entity agent ON agent.entity_id = credit.agent_entity_id
                             AND agent.visibility = 'public'
            JOIN taxonomy_term agent_type ON agent_type.term_id = agent.entity_type_term_id
            LEFT JOIN taxonomy_term role ON role.term_id = credit.role_term_id
            WHERE credit.resource_entity_id = %s
            ORDER BY credit.sequence NULLS LAST, agent.preferred_label
            """,
            (work["entity_id"],),
        )
        entity["credits"] = [
            {
                "agent": self._entity_ref(row, "agent_"),
                "role": self._term(row["role_code"], row["role_label"]),
                "credited_as": row["credited_as"],
                "sequence": row["sequence"],
            }
            for row in credits
        ]
        expressions = self.db.fetch_all(
            """
            SELECT expression.entity_id, expression.language_tag,
                   expression.version_statement, expression.expression_edtf,
                   entity.public_id, entity.preferred_label AS label,
                   type.code AS type_code, type.preferred_label AS type_label
            FROM expression
            JOIN entity ON entity.entity_id = expression.entity_id
                       AND entity.visibility = 'public'
            JOIN taxonomy_term type ON type.term_id = entity.entity_type_term_id
            WHERE expression.work_entity_id = %s
            ORDER BY expression.expression_edtf NULLS LAST, entity.preferred_label
            """,
            (work["entity_id"],),
        )
        expression_ids = [row["entity_id"] for row in expressions]
        result_expressions = []
        for row in expressions:
            result_expressions.append(
                {
                    "entity": self._entity_ref(row),
                    "language": row["language_tag"],
                    "version_statement": row["version_statement"],
                    "date": row["expression_edtf"],
                }
            )

        manifestations: list[dict[str, Any]] = []
        if expression_ids:
            manifestation_rows = self.db.fetch_all(
                """
                SELECT manifestation.entity_id, manifestation.edition_statement,
                       manifestation.publication_edtf, manifestation.extent_text,
                       manifestation.isbn, manifestation.issn, manifestation.oclc_number,
                       entity.public_id, entity.preferred_label AS label,
                       type.code AS type_code, type.preferred_label AS type_label,
                       array_agg(expression_entity.public_id ORDER BY relation.sequence NULLS LAST)
                           AS expression_public_ids
                FROM manifestation_expression relation
                JOIN manifestation ON manifestation.entity_id = relation.manifestation_entity_id
                JOIN entity ON entity.entity_id = manifestation.entity_id
                           AND entity.visibility = 'public'
                JOIN taxonomy_term type ON type.term_id = entity.entity_type_term_id
                JOIN entity expression_entity ON expression_entity.entity_id = relation.expression_entity_id
                WHERE relation.expression_entity_id = ANY(%s)
                GROUP BY manifestation.entity_id, entity.entity_id, type.term_id
                ORDER BY manifestation.publication_edtf NULLS LAST, entity.preferred_label
                """,
                (expression_ids,),
            )
            for row in manifestation_rows:
                statements = self.db.fetch_all(
                    """
                    SELECT statement.statement_type, statement.date_edtf,
                           statement.statement_text, statement.sequence,
                           agent.public_id AS agent_public_id,
                           agent.preferred_label AS agent_label,
                           place.public_id AS place_public_id,
                           place.preferred_label AS place_label
                    FROM publication_statement statement
                    LEFT JOIN entity agent ON agent.entity_id = statement.agent_entity_id
                                           AND agent.visibility = 'public'
                    LEFT JOIN entity place ON place.entity_id = statement.place_entity_id
                                           AND place.visibility = 'public'
                    WHERE statement.manifestation_entity_id = %s
                    ORDER BY statement.sequence NULLS LAST, statement.publication_statement_id
                    """,
                    (row["entity_id"],),
                )
                manifestations.append(
                    {
                        "entity": self._entity_ref(row),
                        "expression_public_ids": row["expression_public_ids"],
                        "edition_statement": row["edition_statement"],
                        "publication_date": row["publication_edtf"],
                        "extent": row["extent_text"],
                        "isbn": row["isbn"],
                        "issn": row["issn"],
                        "oclc_number": row["oclc_number"],
                        "publication_statements": [
                            {
                                "type": statement["statement_type"],
                                "date": statement["date_edtf"],
                                "text": statement["statement_text"],
                                "agent": self._entity_ref(statement, "agent_"),
                                "place": self._entity_ref(statement, "place_"),
                            }
                            for statement in statements
                        ],
                    }
                )

        items = self.db.fetch_all(
            """
            SELECT item.copy_number, item.item_status, item.signed_flag,
                   item.inscription_summary, entity.public_id,
                   entity.preferred_label AS label,
                   type.code AS type_code, type.preferred_label AS type_label,
                   manifestation_entity.public_id AS manifestation_public_id
            FROM item
            JOIN entity ON entity.entity_id = item.entity_id
                       AND entity.visibility = 'public'
            JOIN taxonomy_term type ON type.term_id = entity.entity_type_term_id
            JOIN manifestation_expression relation
                 ON relation.manifestation_entity_id = item.manifestation_entity_id
            JOIN expression ON expression.entity_id = relation.expression_entity_id
            JOIN entity manifestation_entity
                 ON manifestation_entity.entity_id = item.manifestation_entity_id
            WHERE expression.work_entity_id = %s
            ORDER BY entity.preferred_label, entity.public_id
            """,
            (work["entity_id"],),
        )
        return {
            "work": entity,
            "expressions": result_expressions,
            "manifestations": manifestations,
            "items": [
                {
                    **self._entity_ref(row),
                    "manifestation_public_id": row["manifestation_public_id"],
                    "status": row["item_status"],
                    "copy_number": row["copy_number"],
                    "signed": row["signed_flag"],
                    "inscription_summary": row["inscription_summary"],
                }
                for row in items
            ],
        }

    def get_object(self, public_id: str) -> dict[str, Any] | None:
        entity = self.get_entity(public_id)
        if not entity:
            return None
        record = self.db.fetch_one(
            """
            SELECT object.entity_id, object.authenticity_status,
                   object.manufacture_edtf, object.material_summary,
                   object.completeness_text, object.object_note,
                   type.code AS object_type_code,
                   type.preferred_label AS object_type_label
            FROM physical_object object
            JOIN taxonomy_term type ON type.term_id = object.object_type_term_id
            WHERE object.entity_id = (SELECT entity_id FROM entity WHERE public_id = %s)
            """,
            (public_id,),
        )
        if not record:
            return None
        entity.update(
            {
                "object_type": self._term(
                    record["object_type_code"], record["object_type_label"]
                ),
                "authenticity_status": record["authenticity_status"],
                "manufacture_date": record["manufacture_edtf"],
                "materials": record["material_summary"],
                "completeness": record["completeness_text"],
                "object_note": record["object_note"],
            }
        )
        entity["measurements"] = self.db.fetch_all(
            """
            SELECT measurement_type AS type, value, value_min, value_max,
                   unit_code AS unit, display_text, method_note
            FROM measurement WHERE entity_id = %s
            ORDER BY measurement_type, measurement_id
            """,
            (record["entity_id"],),
        )
        marks = self.db.fetch_all(
            """
            SELECT mark.mark_type AS type, mark.transcription,
                   mark.normalized_text, mark.location_on_object AS location,
                   mark.date_code_text AS date_code, mark.note,
                   maker.public_id AS maker_public_id,
                   maker.preferred_label AS maker_label
            FROM object_mark mark
            LEFT JOIN entity maker ON maker.entity_id = mark.maker_entity_id
                                  AND maker.visibility = 'public'
            WHERE mark.entity_id = %s
            ORDER BY mark.object_mark_id
            """,
            (record["entity_id"],),
        )
        entity["marks"] = [
            {
                "type": row["type"],
                "transcription": row["transcription"],
                "normalized_text": row["normalized_text"],
                "location": row["location"],
                "date_code": row["date_code"],
                "note": row["note"],
                "maker": self._entity_ref(row, "maker_"),
            }
            for row in marks
        ]
        productions = self.db.fetch_all(
            """
            SELECT production.model_or_pattern, production.design_number,
                   production.batch_or_lot_code, production.date_edtf,
                   production.note, process.code AS process_code,
                   process.preferred_label AS process_label,
                   manufacturer.public_id AS manufacturer_public_id,
                   manufacturer.preferred_label AS manufacturer_label,
                   place.public_id AS place_public_id,
                   place.preferred_label AS place_label
            FROM production_record production
            LEFT JOIN taxonomy_term process ON process.term_id = production.process_term_id
            LEFT JOIN entity manufacturer
                   ON manufacturer.entity_id = production.manufacturer_entity_id
                  AND manufacturer.visibility = 'public'
            LEFT JOIN entity place ON place.entity_id = production.production_place_entity_id
                                  AND place.visibility = 'public'
            WHERE production.entity_id = %s
            ORDER BY production.date_edtf NULLS LAST, production.production_record_id
            """,
            (record["entity_id"],),
        )
        entity["production"] = [
            {
                "manufacturer": self._entity_ref(row, "manufacturer_"),
                "place": self._entity_ref(row, "place_"),
                "date": row["date_edtf"],
                "model_or_pattern": row["model_or_pattern"],
                "design_number": row["design_number"],
                "batch_or_lot_code": row["batch_or_lot_code"],
                "process": self._term(row["process_code"], row["process_label"]),
                "note": row["note"],
            }
            for row in productions
        ]
        entity["condition_assessments"] = self.db.fetch_all(
            """
            SELECT assessment.assessment_date, assessment.condition_text,
                   assessment.completeness_text, assessment.restoration_text,
                   condition.code AS condition_code,
                   condition.preferred_label AS condition_label
            FROM condition_assessment assessment
            LEFT JOIN taxonomy_term condition ON condition.term_id = assessment.condition_term_id
            WHERE assessment.entity_id = %s
            ORDER BY assessment.assessment_date DESC NULLS LAST,
                     assessment.condition_assessment_id
            """,
            (record["entity_id"],),
        )
        holding = self.db.fetch_one(
            """
            SELECT holding.accession_number, holding.local_call_number,
                   holding.storage_location, holding.valid_from_edtf,
                   holding.valid_to_edtf,
                   holder.public_id AS holder_public_id,
                   holder.preferred_label AS holder_label,
                   collection.public_id AS collection_public_id,
                   collection.preferred_label AS collection_label
            FROM holding
            JOIN entity holder ON holder.entity_id = holding.holder_entity_id
                              AND holder.visibility = 'public'
            LEFT JOIN entity collection ON collection.entity_id = holding.collection_entity_id
                                       AND collection.visibility = 'public'
            WHERE holding.item_entity_id = %s AND holding.is_current = true
            ORDER BY holding.updated_at DESC, holding.holding_id
            LIMIT 1
            """,
            (record["entity_id"],),
        )
        if holding:
            entity["current_holding"] = {
                "holder": self._entity_ref(holding, "holder_"),
                "collection": self._entity_ref(holding, "collection_"),
                "accession_number": holding["accession_number"],
                "local_call_number": holding["local_call_number"],
                "storage_location": holding["storage_location"],
                "valid_from": holding["valid_from_edtf"],
                "valid_to": holding["valid_to_edtf"],
            }
        else:
            entity["current_holding"] = None
        provenance = self.db.fetch_all(
            """
            SELECT provenance.event_type, provenance.date_edtf, provenance.note,
                   source.public_id AS source_public_id,
                   source.preferred_label AS source_label,
                   destination.public_id AS destination_public_id,
                   destination.preferred_label AS destination_label,
                   place.public_id AS place_public_id,
                   place.preferred_label AS place_label
            FROM provenance_event provenance
            LEFT JOIN entity source ON source.entity_id = provenance.from_entity_id
                                   AND source.visibility = 'public'
            LEFT JOIN entity destination ON destination.entity_id = provenance.to_entity_id
                                        AND destination.visibility = 'public'
            LEFT JOIN entity place ON place.entity_id = provenance.place_entity_id
                                  AND place.visibility = 'public'
            WHERE provenance.subject_entity_id = %s
            ORDER BY provenance.date_edtf NULLS LAST, provenance.provenance_event_id
            """,
            (record["entity_id"],),
        )
        entity["provenance"] = [
            {
                "type": row["event_type"],
                "date": row["date_edtf"],
                "from": self._entity_ref(row, "source_"),
                "to": self._entity_ref(row, "destination_"),
                "place": self._entity_ref(row, "place_"),
                "note": row["note"],
            }
            for row in provenance
        ]
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
            (record["entity_id"],),
        )
        return entity

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
                  AND (%s::text IS NULL OR type.code = %s)
                  AND (%s::text IS NULL OR EXISTS (
                      SELECT 1 FROM entity_term_assignment assignment
                      WHERE assignment.entity_id = e.entity_id
                        AND assignment.term_id IN (SELECT term_id FROM selected_terms)
                  ))
            )
            SELECT * FROM ranked
            WHERE score >= 0.08
              AND (%s::numeric IS NULL OR (score, public_id) < (%s, %s))
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
