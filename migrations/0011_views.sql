SET search_path TO food_history, public;

CREATE OR REPLACE VIEW v_entity_display AS
SELECT
    e.entity_id,
    e.public_id,
    e.preferred_label,
    e.canonical_slug,
    e.summary,
    e.record_status,
    e.visibility,
    tt.code AS entity_type_code,
    tt.preferred_label AS entity_type_label
FROM entity e
JOIN taxonomy_term tt ON tt.term_id = e.entity_type_term_id;

CREATE OR REPLACE VIEW v_menu_item_occurrence AS
SELECT
    mi.menu_item_id,
    m.entity_id AS menu_entity_id,
    me.public_id AS menu_public_id,
    me.preferred_label AS menu_label,
    m.service_date_edtf,
    m.establishment_entity_id,
    est.public_id AS establishment_public_id,
    est.preferred_label AS establishment_label,
    mi.sequence,
    mi.printed_name,
    mi.printed_description,
    mi.normalized_food_entity_id,
    food.public_id AS food_public_id,
    food.preferred_label AS normalized_food_label,
    mi.price_text,
    mi.price_amount,
    COALESCE(mi.currency_code, m.currency_code) AS currency_code,
    mi.portion_text,
    mi.citation_id
FROM menu_item mi
JOIN menu m ON m.entity_id = mi.menu_entity_id
JOIN entity me ON me.entity_id = m.entity_id
LEFT JOIN entity est ON est.entity_id = m.establishment_entity_id
LEFT JOIN entity food ON food.entity_id = mi.normalized_food_entity_id;

CREATE OR REPLACE VIEW v_current_holding AS
SELECT
    h.holding_id,
    h.item_entity_id,
    item.public_id AS item_public_id,
    item.preferred_label AS item_label,
    h.holder_entity_id,
    holder.public_id AS holder_public_id,
    holder.preferred_label AS holder_label,
    h.collection_entity_id,
    h.accession_number,
    h.local_call_number,
    h.storage_location,
    h.citation_id
FROM holding h
JOIN entity item ON item.entity_id = h.item_entity_id
JOIN entity holder ON holder.entity_id = h.holder_entity_id
WHERE h.is_current = true;
