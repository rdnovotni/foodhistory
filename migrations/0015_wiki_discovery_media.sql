SET search_path TO food_history, public;

CREATE TABLE "wiki_category" (
    "category_id" uuid NOT NULL,
    "slug" text NOT NULL UNIQUE,
    "name" text NOT NULL,
    "description" text,
    "created_by_user_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_wiki_category_" PRIMARY KEY ("category_id"),
    CONSTRAINT "fk_wiki_category_creator" FOREIGN KEY ("created_by_user_id") REFERENCES "app_user" ("user_id") ON DELETE RESTRICT
);

CREATE TABLE "wiki_revision_category" (
    "revision_id" uuid NOT NULL,
    "category_id" uuid NOT NULL,
    "sequence" integer NOT NULL CHECK ("sequence" > 0),
    CONSTRAINT "pk_wiki_revision_category_" PRIMARY KEY ("revision_id", "category_id"),
    CONSTRAINT "uq_wiki_revision_category_sequence" UNIQUE ("revision_id", "sequence"),
    CONSTRAINT "fk_wiki_revision_category_revision" FOREIGN KEY ("revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_revision_category_category" FOREIGN KEY ("category_id") REFERENCES "wiki_category" ("category_id") ON DELETE RESTRICT
);

CREATE TABLE "wiki_revision_image" (
    "revision_id" uuid NOT NULL,
    "digital_entity_id" uuid NOT NULL,
    "placement" varchar(16) NOT NULL DEFAULT 'gallery' CHECK ("placement" IN ('lead', 'gallery', 'inline')),
    "alt_text" text NOT NULL CHECK (length(trim("alt_text")) > 0),
    "caption" text,
    "sequence" integer NOT NULL CHECK ("sequence" > 0),
    CONSTRAINT "pk_wiki_revision_image_" PRIMARY KEY ("revision_id", "digital_entity_id"),
    CONSTRAINT "uq_wiki_revision_image_sequence" UNIQUE ("revision_id", "sequence"),
    CONSTRAINT "fk_wiki_revision_image_revision" FOREIGN KEY ("revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_revision_image_resource" FOREIGN KEY ("digital_entity_id") REFERENCES "digital_resource" ("entity_id") ON DELETE RESTRICT
);

CREATE INDEX "idx_wiki_page_search" ON "wiki_revision" USING gin (
    to_tsvector('simple', coalesce("title", '') || ' ' || coalesce("summary", '') || ' ' || "body_markdown")
);
CREATE INDEX "idx_wiki_category_name" ON "wiki_category" (lower("name"));
CREATE UNIQUE INDEX "uq_wiki_revision_lead_image" ON "wiki_revision_image" ("revision_id") WHERE "placement" = 'lead';

CREATE TRIGGER trg_wiki_category_updated_at BEFORE UPDATE ON "wiki_category" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_wiki_revision_entity_immutable BEFORE UPDATE OR DELETE ON "wiki_revision_entity" FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_revision_citation_immutable BEFORE UPDATE OR DELETE ON "wiki_revision_citation" FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_revision_category_immutable BEFORE UPDATE OR DELETE ON "wiki_revision_category" FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();
CREATE TRIGGER trg_wiki_revision_image_immutable BEFORE UPDATE OR DELETE ON "wiki_revision_image" FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();

CREATE VIEW "public_wiki_revision_category" WITH (security_barrier = true) AS
SELECT l.revision_id, c.slug, c.name, c.description, l.sequence
FROM wiki_revision_category l
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published'
JOIN wiki_category c ON c.category_id = l.category_id;

CREATE VIEW "public_wiki_revision_image" WITH (security_barrier = true) AS
SELECT l.revision_id, e.public_id, r.storage_uri, r.mime_type,
       r.width_px, r.height_px, l.placement, l.alt_text, l.caption, l.sequence
FROM wiki_revision_image l
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published'
JOIN digital_resource r ON r.entity_id = l.digital_entity_id
JOIN entity e ON e.entity_id = r.entity_id AND e.visibility = 'public';

CREATE VIEW "public_wiki_category" WITH (security_barrier = true) AS
SELECT c.slug, c.name, c.description, count(DISTINCT p.page_id)::integer AS page_count
FROM wiki_category c
JOIN wiki_revision_category l ON l.category_id = c.category_id
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published'
GROUP BY c.category_id, c.slug, c.name, c.description;

COMMENT ON TABLE "wiki_revision_image" IS 'Revision-specific presentation metadata for a canonical digital resource; binary content remains outside PostgreSQL.';
