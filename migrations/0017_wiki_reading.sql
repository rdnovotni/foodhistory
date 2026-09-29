SET search_path TO food_history, public;

CREATE TABLE "wiki_series" (
    "series_id" uuid PRIMARY KEY,
    "slug" text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "title" text NOT NULL CHECK (length(trim(title)) > 0),
    "description" text NOT NULL DEFAULT ''
);
CREATE TABLE "wiki_revision_series" (
    "revision_id" uuid NOT NULL REFERENCES wiki_revision (revision_id) ON DELETE CASCADE,
    "series_id" uuid NOT NULL REFERENCES wiki_series (series_id) ON DELETE RESTRICT,
    "position" integer NOT NULL CHECK (position > 0),
    PRIMARY KEY (revision_id, series_id)
);
CREATE INDEX idx_wiki_revision_series_order ON wiki_revision_series (series_id, position);
CREATE TABLE "wiki_revision_related" (
    "revision_id" uuid NOT NULL REFERENCES wiki_revision (revision_id) ON DELETE CASCADE,
    "target_slug" text NOT NULL CHECK (target_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "sequence" integer NOT NULL CHECK (sequence > 0),
    PRIMARY KEY (revision_id, target_slug),
    UNIQUE (revision_id, sequence)
);
CREATE TABLE "wiki_revision_metadata" (
    "revision_id" uuid PRIMARY KEY REFERENCES wiki_revision (revision_id) ON DELETE CASCADE,
    "is_disambiguation" boolean NOT NULL DEFAULT false,
    "event_month" integer CHECK (event_month BETWEEN 1 AND 12),
    "event_day" integer CHECK (event_day BETWEEN 1 AND 31),
    CHECK ((event_month IS NULL) = (event_day IS NULL)),
    CHECK (event_month IS NULL OR event_day <= extract(day FROM
           make_date(2000, event_month, 1) + interval '1 month - 1 day'))
);
CREATE TABLE "wiki_publication" (
    "revision_id" uuid PRIMARY KEY REFERENCES wiki_revision (revision_id) ON DELETE RESTRICT,
    "page_id" uuid NOT NULL REFERENCES wiki_page (page_id) ON DELETE CASCADE,
    "published_at" timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_wiki_publication_recent ON wiki_publication (published_at DESC);
-- The current publication is safe to recover. Earlier historical publication
-- events cannot be inferred from review approvals and must remain private.
INSERT INTO wiki_publication (revision_id, page_id, published_at)
SELECT published_revision_id, page_id, updated_at FROM wiki_page
WHERE status = 'published' AND published_revision_id IS NOT NULL;
CREATE TABLE "wiki_glossary" (
    "slug" text PRIMARY KEY CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "term" text NOT NULL CHECK (length(trim(term)) > 0),
    "definition" text NOT NULL CHECK (length(trim(definition)) > 0),
    "article_slug" text CHECK (article_slug IS NULL OR article_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "is_published" boolean NOT NULL DEFAULT false
);

CREATE TRIGGER trg_wiki_revision_series_immutable BEFORE UPDATE OR DELETE ON wiki_revision_series FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_revision_related_immutable BEFORE UPDATE OR DELETE ON wiki_revision_related FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_revision_metadata_immutable BEFORE UPDATE OR DELETE ON wiki_revision_metadata FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_publication_immutable BEFORE UPDATE OR DELETE ON wiki_publication FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();

CREATE VIEW public_wiki_publication WITH (security_barrier = true) AS
SELECT e.revision_id, e.page_id, e.published_at, r.revision_number, r.title,
       r.summary, r.body_markdown, p.slug, p.public_id
FROM wiki_publication e
JOIN wiki_page p ON p.page_id = e.page_id AND p.status = 'published'
JOIN wiki_revision r ON r.revision_id = e.revision_id AND r.page_id = p.page_id;

CREATE VIEW public_wiki_revision_series WITH (security_barrier = true) AS
SELECT m.revision_id, s.slug, s.title, s.description, m.position
FROM wiki_revision_series m
JOIN wiki_page p ON p.published_revision_id = m.revision_id AND p.status = 'published'
JOIN wiki_series s ON s.series_id = m.series_id;

CREATE VIEW public_wiki_revision_related WITH (security_barrier = true) AS
SELECT m.revision_id, m.target_slug, m.sequence
FROM wiki_revision_related m
JOIN wiki_page p ON p.published_revision_id = m.revision_id AND p.status = 'published'
JOIN wiki_page target ON target.slug = m.target_slug AND target.status = 'published';

CREATE VIEW public_wiki_revision_metadata WITH (security_barrier = true) AS
SELECT m.revision_id, m.is_disambiguation, m.event_month, m.event_day
FROM wiki_revision_metadata m
JOIN wiki_page p ON p.published_revision_id = m.revision_id AND p.status = 'published';

CREATE VIEW public_wiki_glossary WITH (security_barrier = true) AS
SELECT g.slug, g.term, g.definition,
       CASE WHEN EXISTS (
           SELECT 1 FROM wiki_page p WHERE p.slug = g.article_slug AND p.status = 'published'
       ) THEN g.article_slug ELSE NULL END AS article_slug
FROM wiki_glossary g WHERE g.is_published = true;
