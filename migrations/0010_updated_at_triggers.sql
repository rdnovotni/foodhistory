SET search_path TO food_history, public;

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_app_user_updated_at ON "app_user";
CREATE TRIGGER trg_app_user_updated_at BEFORE UPDATE ON "app_user" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_assertion_updated_at ON "assertion";
CREATE TRIGGER trg_assertion_updated_at BEFORE UPDATE ON "assertion" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_assertion_evidence_updated_at ON "assertion_evidence";
CREATE TRIGGER trg_assertion_evidence_updated_at BEFORE UPDATE ON "assertion_evidence" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_citation_updated_at ON "citation";
CREATE TRIGGER trg_citation_updated_at BEFORE UPDATE ON "citation" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_collection_membership_updated_at ON "collection_membership";
CREATE TRIGGER trg_collection_membership_updated_at BEFORE UPDATE ON "collection_membership" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_condition_assessment_updated_at ON "condition_assessment";
CREATE TRIGGER trg_condition_assessment_updated_at BEFORE UPDATE ON "condition_assessment" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_credit_updated_at ON "credit";
CREATE TRIGGER trg_credit_updated_at BEFORE UPDATE ON "credit" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_digital_representation_updated_at ON "digital_representation";
CREATE TRIGGER trg_digital_representation_updated_at BEFORE UPDATE ON "digital_representation" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_digital_resource_updated_at ON "digital_resource";
CREATE TRIGGER trg_digital_resource_updated_at BEFORE UPDATE ON "digital_resource" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_entity_updated_at ON "entity";
CREATE TRIGGER trg_entity_updated_at BEFORE UPDATE ON "entity" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_entity_language_updated_at ON "entity_language";
CREATE TRIGGER trg_entity_language_updated_at BEFORE UPDATE ON "entity_language" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_entity_name_updated_at ON "entity_name";
CREATE TRIGGER trg_entity_name_updated_at BEFORE UPDATE ON "entity_name" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_entity_note_updated_at ON "entity_note";
CREATE TRIGGER trg_entity_note_updated_at BEFORE UPDATE ON "entity_note" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_entity_term_assignment_updated_at ON "entity_term_assignment";
CREATE TRIGGER trg_entity_term_assignment_updated_at BEFORE UPDATE ON "entity_term_assignment" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_external_identifier_updated_at ON "external_identifier";
CREATE TRIGGER trg_external_identifier_updated_at BEFORE UPDATE ON "external_identifier" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_holding_updated_at ON "holding";
CREATE TRIGGER trg_holding_updated_at BEFORE UPDATE ON "holding" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_measurement_updated_at ON "measurement";
CREATE TRIGGER trg_measurement_updated_at BEFORE UPDATE ON "measurement" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_menu_item_updated_at ON "menu_item";
CREATE TRIGGER trg_menu_item_updated_at BEFORE UPDATE ON "menu_item" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_object_mark_updated_at ON "object_mark";
CREATE TRIGGER trg_object_mark_updated_at BEFORE UPDATE ON "object_mark" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_observation_updated_at ON "observation";
CREATE TRIGGER trg_observation_updated_at BEFORE UPDATE ON "observation" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_place_address_updated_at ON "place_address";
CREATE TRIGGER trg_place_address_updated_at BEFORE UPDATE ON "place_address" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_price_observation_updated_at ON "price_observation";
CREATE TRIGGER trg_price_observation_updated_at BEFORE UPDATE ON "price_observation" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_product_brand_assignment_updated_at ON "product_brand_assignment";
CREATE TRIGGER trg_product_brand_assignment_updated_at BEFORE UPDATE ON "product_brand_assignment" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_production_record_updated_at ON "production_record";
CREATE TRIGGER trg_production_record_updated_at BEFORE UPDATE ON "production_record" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_provenance_event_updated_at ON "provenance_event";
CREATE TRIGGER trg_provenance_event_updated_at BEFORE UPDATE ON "provenance_event" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_publication_statement_updated_at ON "publication_statement";
CREATE TRIGGER trg_publication_statement_updated_at BEFORE UPDATE ON "publication_statement" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_recipe_occurrence_updated_at ON "recipe_occurrence";
CREATE TRIGGER trg_recipe_occurrence_updated_at BEFORE UPDATE ON "recipe_occurrence" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_rights_assignment_updated_at ON "rights_assignment";
CREATE TRIGGER trg_rights_assignment_updated_at BEFORE UPDATE ON "rights_assignment" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_taxonomy_edge_updated_at ON "taxonomy_edge";
CREATE TRIGGER trg_taxonomy_edge_updated_at BEFORE UPDATE ON "taxonomy_edge" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_taxonomy_label_updated_at ON "taxonomy_label";
CREATE TRIGGER trg_taxonomy_label_updated_at BEFORE UPDATE ON "taxonomy_label" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_taxonomy_mapping_updated_at ON "taxonomy_mapping";
CREATE TRIGGER trg_taxonomy_mapping_updated_at BEFORE UPDATE ON "taxonomy_mapping" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_taxonomy_term_updated_at ON "taxonomy_term";
CREATE TRIGGER trg_taxonomy_term_updated_at BEFORE UPDATE ON "taxonomy_term" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_transaction_line_updated_at ON "transaction_line";
CREATE TRIGGER trg_transaction_line_updated_at BEFORE UPDATE ON "transaction_line" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_transcription_updated_at ON "transcription";
CREATE TRIGGER trg_transcription_updated_at BEFORE UPDATE ON "transcription" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_vocabulary_updated_at ON "vocabulary";
CREATE TRIGGER trg_vocabulary_updated_at BEFORE UPDATE ON "vocabulary" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
