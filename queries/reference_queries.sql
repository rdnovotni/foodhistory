-- Food History Phase 1 reference queries
SET search_path TO food_history, public;

-- 1. Resolve one entity by stable public ID.
SELECT e.entity_id, e.public_id, e.preferred_label, e.summary,
       tt.code AS entity_type_code, tt.preferred_label AS entity_type_label,
       e.record_status, e.visibility
FROM entity e
JOIN taxonomy_term tt ON tt.term_id = e.entity_type_term_id
WHERE e.public_id = $1;

-- 2. All searchable names for an entity.
SELECT n.name_type, n.name_text, n.language_tag, n.script_code,
       n.valid_from_edtf, n.valid_to_edtf, n.is_preferred_in_language
FROM entity_name n
JOIN entity e ON e.entity_id = n.entity_id
WHERE e.public_id = $1
ORDER BY n.is_preferred_in_language DESC, n.name_type, n.name_text;

-- 3. All descendants of a taxonomy term using recursive hierarchy traversal.
WITH RECURSIVE descendants AS (
    SELECT t.term_id, t.code, t.preferred_label, 0 AS depth
    FROM taxonomy_term t
    WHERE t.code = $1
  UNION ALL
    SELECT child.term_id, child.code, child.preferred_label, d.depth + 1
    FROM descendants d
    JOIN taxonomy_edge edge ON edge.parent_term_id = d.term_id AND edge.edge_type='broader'
    JOIN taxonomy_term child ON child.term_id = edge.child_term_id
)
SELECT * FROM descendants ORDER BY depth, code;

-- 4. Dish/product appearances on menus.
SELECT food.public_id AS food_public_id,
       food.preferred_label AS normalized_food,
       menu_entity.public_id AS menu_public_id,
       menu_entity.preferred_label AS menu_label,
       m.service_date_edtf,
       establishment.public_id AS establishment_public_id,
       establishment.preferred_label AS establishment,
       mi.printed_name, mi.printed_description,
       mi.price_text, mi.price_amount, mi.currency_code,
       ms.heading_original AS menu_section,
       c.locator_text
FROM menu_item mi
JOIN entity food ON food.entity_id = mi.normalized_food_entity_id
JOIN menu m ON m.entity_id = mi.menu_entity_id
JOIN entity menu_entity ON menu_entity.entity_id = m.entity_id
LEFT JOIN entity establishment ON establishment.entity_id = m.establishment_entity_id
LEFT JOIN menu_section ms ON ms.menu_section_id = mi.menu_section_id
LEFT JOIN citation c ON c.citation_id = mi.citation_id
WHERE food.public_id = $1
ORDER BY m.service_date_edtf NULLS LAST, menu_entity.public_id, mi.sequence;

-- 5. Work → expression → manifestation → item tree.
SELECT w_ent.public_id AS work_public_id, w_ent.preferred_label AS work,
       ex_ent.public_id AS expression_public_id, ex_ent.preferred_label AS expression,
       m_ent.public_id AS manifestation_public_id, m_ent.preferred_label AS manifestation,
       m.edition_statement, m.publication_edtf,
       i_ent.public_id AS item_public_id, i_ent.preferred_label AS item,
       i.copy_number, i.signed_flag
FROM entity w_ent
JOIN work w ON w.entity_id = w_ent.entity_id
LEFT JOIN expression ex ON ex.work_entity_id = w.entity_id
LEFT JOIN entity ex_ent ON ex_ent.entity_id = ex.entity_id
LEFT JOIN manifestation_expression me ON me.expression_entity_id = ex.entity_id
LEFT JOIN manifestation m ON m.entity_id = me.manifestation_entity_id
LEFT JOIN entity m_ent ON m_ent.entity_id = m.entity_id
LEFT JOIN item i ON i.manifestation_entity_id = m.entity_id
LEFT JOIN entity i_ent ON i_ent.entity_id = i.entity_id
WHERE w_ent.public_id = $1
ORDER BY m.publication_edtf NULLS LAST, i_ent.public_id;

-- 6. Material-object identification summary: marks, production, current holding.
SELECT obj.public_id, obj.preferred_label,
       po.manufacture_edtf, po.material_summary, po.completeness_text,
       om.mark_type, om.transcription AS mark_text, om.date_code_text,
       maker.preferred_label AS mark_maker,
       pr.model_or_pattern, pr.batch_or_lot_code,
       manufacturer.preferred_label AS manufacturer,
       holder.preferred_label AS current_holder, h.accession_number
FROM entity obj
JOIN physical_object po ON po.entity_id = obj.entity_id
LEFT JOIN object_mark om ON om.entity_id = obj.entity_id
LEFT JOIN entity maker ON maker.entity_id = om.maker_entity_id
LEFT JOIN production_record pr ON pr.entity_id = obj.entity_id
LEFT JOIN entity manufacturer ON manufacturer.entity_id = pr.manufacturer_entity_id
LEFT JOIN holding h ON h.item_entity_id = obj.entity_id AND h.is_current=true
LEFT JOIN entity holder ON holder.entity_id = h.holder_entity_id
WHERE obj.public_id = $1;

-- 7. Evidence graph for one subject entity.
SELECT subject.public_id AS subject_public_id,
       pred.code AS predicate_code, pred.preferred_label AS predicate,
       a.value_kind,
       object.public_id AS object_public_id, object.preferred_label AS object_label,
       a.value_text, a.value_number, a.value_date, a.value_boolean,
       status.code AS claim_status_code,
       confidence.code AS confidence_code,
       ae.evidence_role,
       source.public_id AS source_public_id, source.preferred_label AS source_label,
       c.locator_text, c.page_label, c.folio_label, c.image_label, c.stable_uri
FROM assertion a
JOIN entity subject ON subject.entity_id = a.subject_entity_id
JOIN taxonomy_term pred ON pred.term_id = a.predicate_term_id
LEFT JOIN entity object ON object.entity_id = a.object_entity_id
LEFT JOIN taxonomy_term status ON status.term_id = a.claim_status_term_id
LEFT JOIN taxonomy_term confidence ON confidence.term_id = a.confidence_term_id
LEFT JOIN assertion_evidence ae ON ae.assertion_id = a.assertion_id
LEFT JOIN citation c ON c.citation_id = ae.citation_id
LEFT JOIN entity source ON source.entity_id = c.source_entity_id
WHERE subject.public_id = $1
ORDER BY pred.code, a.is_preferred DESC, ae.evidence_role;

-- 8. Provenance timeline.
SELECT pe.date_edtf, pe.event_type,
       from_e.preferred_label AS from_party,
       to_e.preferred_label AS to_party,
       place_e.preferred_label AS place,
       pe.note,
       source.preferred_label AS evidence_source,
       c.locator_text
FROM provenance_event pe
JOIN entity subject ON subject.entity_id = pe.subject_entity_id
LEFT JOIN entity from_e ON from_e.entity_id = pe.from_entity_id
LEFT JOIN entity to_e ON to_e.entity_id = pe.to_entity_id
LEFT JOIN entity place_e ON place_e.entity_id = pe.place_entity_id
LEFT JOIN citation c ON c.citation_id = pe.citation_id
LEFT JOIN entity source ON source.entity_id = c.source_entity_id
WHERE subject.public_id = $1
ORDER BY pe.date_edtf NULLS LAST, pe.created_at;

-- 9. Historical price series for any subject entity.
SELECT p.date_edtf, p.price_type, p.amount, p.amount_text,
       p.currency_code, p.currency_text_original,
       p.quantity_value, p.quantity_unit, p.basis_text,
       place.preferred_label AS place,
       source.preferred_label AS source,
       c.locator_text
FROM price_observation p
JOIN entity subject ON subject.entity_id = p.subject_entity_id
LEFT JOIN entity place ON place.entity_id = p.place_entity_id
JOIN citation c ON c.citation_id = p.citation_id
JOIN entity source ON source.entity_id = c.source_entity_id
WHERE subject.public_id = $1
ORDER BY p.date_edtf NULLS LAST;

-- 10. Basic public fuzzy search seed query. Production API should also add FTS over transcriptions.
SELECT DISTINCT e.public_id, e.preferred_label,
       tt.code AS entity_type_code,
       GREATEST(
         similarity(e.preferred_label, $1),
         COALESCE(MAX(similarity(n.name_text, $1)), 0)
       ) AS score
FROM entity e
JOIN taxonomy_term tt ON tt.term_id = e.entity_type_term_id
LEFT JOIN entity_name n ON n.entity_id = e.entity_id
WHERE e.visibility='public' AND e.record_status='published'
  AND (e.preferred_label % $1 OR n.name_text % $1)
GROUP BY e.entity_id, e.public_id, e.preferred_label, tt.code
ORDER BY score DESC, e.preferred_label
LIMIT 50;