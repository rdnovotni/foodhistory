-- Pin lookup resolution for taxonomy guard functions.
-- Ingestion uses schema-qualified writes and must not depend on the client search_path.

ALTER FUNCTION food_history.require_term_vocabulary()
    SET search_path TO food_history, public;

ALTER FUNCTION food_history.require_assignment_vocabulary()
    SET search_path TO food_history, public;
