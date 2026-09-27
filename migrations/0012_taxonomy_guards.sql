SET search_path TO food_history, public;

-- Enforce taxonomy vocabulary boundaries at the database layer.
-- These guards validate the vocabulary family, not the exact narrower branch.

CREATE OR REPLACE FUNCTION require_term_vocabulary()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    term_value uuid;
    actual_vocab text;
BEGIN
    term_value := NULLIF(to_jsonb(NEW) ->> TG_ARGV[0], '')::uuid;
    IF term_value IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT v.code INTO actual_vocab
    FROM taxonomy_term t
    JOIN vocabulary v ON v.vocabulary_id = t.vocabulary_id
    WHERE t.term_id = term_value;

    IF actual_vocab IS NULL THEN
        RAISE EXCEPTION 'Unknown taxonomy term % in %.%', term_value, TG_TABLE_NAME, TG_ARGV[0];
    END IF;
    IF actual_vocab <> TG_ARGV[1] THEN
        RAISE EXCEPTION 'Invalid taxonomy vocabulary for %.%: expected %, got %',
            TG_TABLE_NAME, TG_ARGV[0], TG_ARGV[1], actual_vocab;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION require_assignment_vocabulary()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_vocab text;
    actual_vocab text;
BEGIN
    expected_vocab := CASE NEW.assignment_kind
        WHEN 'subject' THEN 'SUB'
        WHEN 'context' THEN 'CTX'
        WHEN 'collecting_domain' THEN 'COL'
        WHEN 'food_class' THEN 'FC'
        WHEN 'object_type' THEN 'ROT'
        WHEN 'evidence_status' THEN 'EVD'
        ELSE NULL
    END;

    IF expected_vocab IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT v.code INTO actual_vocab
    FROM taxonomy_term t
    JOIN vocabulary v ON v.vocabulary_id = t.vocabulary_id
    WHERE t.term_id = NEW.term_id;

    IF actual_vocab IS DISTINCT FROM expected_vocab THEN
        RAISE EXCEPTION 'Invalid taxonomy assignment: kind % requires vocabulary %, got %',
            NEW.assignment_kind, expected_vocab, coalesce(actual_vocab, '<missing>');
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_entity_type_vocab ON entity;
CREATE TRIGGER trg_entity_type_vocab
BEFORE INSERT OR UPDATE OF entity_type_term_id ON entity
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('entity_type_term_id', 'ENT');

DROP TRIGGER IF EXISTS trg_assertion_predicate_vocab ON assertion;
CREATE TRIGGER trg_assertion_predicate_vocab
BEFORE INSERT OR UPDATE OF predicate_term_id ON assertion
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('predicate_term_id', 'REL');

DROP TRIGGER IF EXISTS trg_observation_type_vocab ON observation;
CREATE TRIGGER trg_observation_type_vocab
BEFORE INSERT OR UPDATE OF observation_type_term_id ON observation
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('observation_type_term_id', 'REL');

DROP TRIGGER IF EXISTS trg_entity_term_assignment_vocab ON entity_term_assignment;
CREATE TRIGGER trg_entity_term_assignment_vocab
BEFORE INSERT OR UPDATE OF term_id, assignment_kind ON entity_term_assignment
FOR EACH ROW EXECUTE FUNCTION require_assignment_vocabulary();

DROP TRIGGER IF EXISTS trg_document_type_vocab ON document;
CREATE TRIGGER trg_document_type_vocab
BEFORE INSERT OR UPDATE OF document_type_term_id ON document
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('document_type_term_id', 'ROT');

DROP TRIGGER IF EXISTS trg_menu_type_vocab ON menu;
CREATE TRIGGER trg_menu_type_vocab
BEFORE INSERT OR UPDATE OF menu_type_term_id ON menu
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('menu_type_term_id', 'ROT');

DROP TRIGGER IF EXISTS trg_work_type_vocab ON work;
CREATE TRIGGER trg_work_type_vocab
BEFORE INSERT OR UPDATE OF work_type_term_id ON work
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('work_type_term_id', 'ROT');

DROP TRIGGER IF EXISTS trg_media_type_vocab ON media_item;
CREATE TRIGGER trg_media_type_vocab
BEFORE INSERT OR UPDATE OF media_type_term_id ON media_item
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('media_type_term_id', 'ROT');

DROP TRIGGER IF EXISTS trg_object_type_vocab ON physical_object;
CREATE TRIGGER trg_object_type_vocab
BEFORE INSERT OR UPDATE OF object_type_term_id ON physical_object
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('object_type_term_id', 'ROT');

DROP TRIGGER IF EXISTS trg_assertion_claim_status_vocab ON assertion;
CREATE TRIGGER trg_assertion_claim_status_vocab
BEFORE INSERT OR UPDATE OF claim_status_term_id ON assertion
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('claim_status_term_id', 'EVD');

DROP TRIGGER IF EXISTS trg_assertion_confidence_vocab ON assertion;
CREATE TRIGGER trg_assertion_confidence_vocab
BEFORE INSERT OR UPDATE OF confidence_term_id ON assertion
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('confidence_term_id', 'EVD');

DROP TRIGGER IF EXISTS trg_observation_confidence_vocab ON observation;
CREATE TRIGGER trg_observation_confidence_vocab
BEFORE INSERT OR UPDATE OF confidence_term_id ON observation
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('confidence_term_id', 'EVD');

DROP TRIGGER IF EXISTS trg_assertion_evidence_strength_vocab ON assertion_evidence;
CREATE TRIGGER trg_assertion_evidence_strength_vocab
BEFORE INSERT OR UPDATE OF strength_term_id ON assertion_evidence
FOR EACH ROW EXECUTE FUNCTION require_term_vocabulary('strength_term_id', 'EVD');
