SET search_path TO food_history, public;

CREATE TABLE "wiki_revision_link" (
    "revision_id" uuid NOT NULL REFERENCES wiki_revision (revision_id) ON DELETE CASCADE,
    "target_slug" text NOT NULL CHECK (target_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "sequence" integer NOT NULL CHECK (sequence > 0),
    PRIMARY KEY (revision_id, target_slug),
    UNIQUE (revision_id, sequence)
);
CREATE INDEX idx_wiki_revision_link_target ON wiki_revision_link (target_slug, revision_id);
CREATE TRIGGER trg_wiki_revision_link_immutable BEFORE UPDATE OR DELETE ON wiki_revision_link
    FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();

CREATE VIEW public_wiki_revision_link WITH (security_barrier = true) AS
SELECT l.revision_id, l.target_slug, l.sequence
FROM wiki_revision_link l
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published';

-- Existing revisions were authored before link indexing existed. Preserve their
-- immutable bodies; the application backfill command parses them into this table.
