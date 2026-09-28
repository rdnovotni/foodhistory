SET search_path TO food_history, public;

CREATE TABLE "editor_account" (
    "account_id" uuid NOT NULL,
    "username" text NOT NULL,
    "password_hash" text NOT NULL,
    "role" varchar(16) NOT NULL CHECK ("role" IN ('owner', 'editor', 'reviewer', 'viewer')),
    "is_active" boolean NOT NULL DEFAULT true,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_editor_account_" PRIMARY KEY ("account_id"),
    CONSTRAINT "fk_editor_account_app_user" FOREIGN KEY ("account_id") REFERENCES "app_user" ("user_id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX "uq_editor_account_username_ci" ON "editor_account" (lower("username"));
COMMENT ON TABLE "editor_account" IS 'Private authentication credentials and roles linked one-to-one to the canonical application user audit identity.';

CREATE TABLE "editor_session" (
    "token_hash" char(64) NOT NULL,
    "csrf_token_hash" char(64) NOT NULL,
    "account_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "expires_at" timestamptz NOT NULL,
    "last_seen_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_editor_session_" PRIMARY KEY ("token_hash"),
    CONSTRAINT "fk_editor_session_account" FOREIGN KEY ("account_id") REFERENCES "editor_account" ("account_id") ON DELETE CASCADE
);

CREATE TABLE "wiki_page" (
    "page_id" uuid NOT NULL,
    "public_id" varchar(40) NOT NULL UNIQUE,
    "slug" text NOT NULL UNIQUE,
    "status" varchar(24) NOT NULL DEFAULT 'draft' CHECK ("status" IN ('draft', 'in_review', 'approved', 'published', 'withdrawn')),
    "current_revision_id" uuid,
    "published_revision_id" uuid,
    "created_by_user_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_wiki_page_" PRIMARY KEY ("page_id"),
    CONSTRAINT "fk_wiki_page_creator" FOREIGN KEY ("created_by_user_id") REFERENCES "app_user" ("user_id") ON DELETE RESTRICT
);
COMMENT ON TABLE "wiki_page" IS 'Stable wiki identity; mutable workflow pointers refer to immutable authored revisions.';

CREATE TABLE "wiki_revision" (
    "revision_id" uuid NOT NULL,
    "page_id" uuid NOT NULL,
    "revision_number" integer NOT NULL CHECK ("revision_number" > 0),
    "title" text NOT NULL,
    "summary" text,
    "body_markdown" text NOT NULL,
    "change_note" text,
    "created_by_user_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_wiki_revision_" PRIMARY KEY ("revision_id"),
    CONSTRAINT "uq_wiki_revision_number" UNIQUE ("page_id", "revision_number"),
    CONSTRAINT "fk_wiki_revision_page" FOREIGN KEY ("page_id") REFERENCES "wiki_page" ("page_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_revision_creator" FOREIGN KEY ("created_by_user_id") REFERENCES "app_user" ("user_id") ON DELETE RESTRICT
);
COMMENT ON TABLE "wiki_revision" IS 'Immutable narrative snapshot; edits always create a new revision.';

ALTER TABLE "wiki_page" ADD CONSTRAINT "fk_wiki_page_current_revision" FOREIGN KEY ("current_revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE RESTRICT;
ALTER TABLE "wiki_page" ADD CONSTRAINT "fk_wiki_page_published_revision" FOREIGN KEY ("published_revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE RESTRICT;

CREATE TABLE "wiki_review" (
    "review_id" uuid NOT NULL,
    "revision_id" uuid NOT NULL,
    "decision" varchar(24) NOT NULL CHECK ("decision" IN ('submitted', 'approved', 'changes_requested', 'publication_withdrawn')),
    "note" text,
    "reviewer_user_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_wiki_review_" PRIMARY KEY ("review_id"),
    CONSTRAINT "fk_wiki_review_revision" FOREIGN KEY ("revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_review_user" FOREIGN KEY ("reviewer_user_id") REFERENCES "app_user" ("user_id") ON DELETE RESTRICT
);
COMMENT ON TABLE "wiki_review" IS 'Append-only submission, review, approval, and withdrawal decisions for wiki revisions.';

CREATE TABLE "wiki_revision_entity" (
    "revision_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "relationship" varchar(16) NOT NULL CHECK ("relationship" IN ('subject', 'mentions')),
    "sequence" integer NOT NULL DEFAULT 1 CHECK ("sequence" > 0),
    CONSTRAINT "pk_wiki_revision_entity_" PRIMARY KEY ("revision_id", "entity_id", "relationship"),
    CONSTRAINT "fk_wiki_revision_entity_revision" FOREIGN KEY ("revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_revision_entity_entity" FOREIGN KEY ("entity_id") REFERENCES "entity" ("entity_id") ON DELETE RESTRICT
);

CREATE TABLE "wiki_revision_citation" (
    "revision_id" uuid NOT NULL,
    "citation_id" uuid NOT NULL,
    "sequence" integer NOT NULL CHECK ("sequence" > 0),
    "note" text,
    CONSTRAINT "pk_wiki_revision_citation_" PRIMARY KEY ("revision_id", "citation_id"),
    CONSTRAINT "uq_wiki_revision_citation_sequence" UNIQUE ("revision_id", "sequence"),
    CONSTRAINT "fk_wiki_revision_citation_revision" FOREIGN KEY ("revision_id") REFERENCES "wiki_revision" ("revision_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_revision_citation_citation" FOREIGN KEY ("citation_id") REFERENCES "citation" ("citation_id") ON DELETE RESTRICT
);
COMMENT ON TABLE "wiki_revision_citation" IS 'Revision-specific links to canonical evidence locators; wiki prose does not duplicate or replace citations.';

CREATE TABLE "wiki_redirect" (
    "source_slug" text NOT NULL,
    "page_id" uuid NOT NULL,
    "created_by_user_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_wiki_redirect_" PRIMARY KEY ("source_slug"),
    CONSTRAINT "fk_wiki_redirect_page" FOREIGN KEY ("page_id") REFERENCES "wiki_page" ("page_id") ON DELETE CASCADE,
    CONSTRAINT "fk_wiki_redirect_creator" FOREIGN KEY ("created_by_user_id") REFERENCES "app_user" ("user_id") ON DELETE RESTRICT
);

CREATE INDEX "idx_editor_session_expiry" ON "editor_session" ("expires_at");
CREATE INDEX "idx_wiki_page_status" ON "wiki_page" ("status", "updated_at" DESC);
CREATE INDEX "idx_wiki_revision_page" ON "wiki_revision" ("page_id", "revision_number" DESC);
CREATE INDEX "idx_wiki_review_revision" ON "wiki_review" ("revision_id", "created_at" DESC);

CREATE FUNCTION prevent_wiki_revision_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'wiki revisions are immutable; create a new revision';
END;
$$;
CREATE TRIGGER trg_wiki_revision_immutable BEFORE UPDATE OR DELETE ON "wiki_revision" FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();

CREATE TRIGGER trg_editor_account_updated_at BEFORE UPDATE ON "editor_account" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_wiki_page_updated_at BEFORE UPDATE ON "wiki_page" FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE VIEW "public_wiki_page" WITH (security_barrier = true) AS
SELECT p.page_id, p.public_id, p.slug, r.revision_id, r.revision_number,
       r.title, r.summary, r.body_markdown, r.created_at
FROM wiki_page p
JOIN wiki_revision r ON r.revision_id = p.published_revision_id
WHERE p.status = 'published';

CREATE VIEW "public_wiki_revision_entity" WITH (security_barrier = true) AS
SELECT l.revision_id, e.public_id, e.preferred_label AS label,
       l.relationship, l.sequence
FROM wiki_revision_entity l
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published'
JOIN entity e ON e.entity_id = l.entity_id AND e.visibility = 'public';

CREATE VIEW "public_wiki_revision_citation" WITH (security_barrier = true) AS
SELECT l.revision_id, l.sequence, l.note, c.locator_text, c.page_label,
       c.stable_uri, s.public_id AS source_public_id,
       s.preferred_label AS source_label
FROM wiki_revision_citation l
JOIN wiki_page p ON p.published_revision_id = l.revision_id AND p.status = 'published'
JOIN citation c ON c.citation_id = l.citation_id
JOIN entity s ON s.entity_id = c.source_entity_id AND s.visibility = 'public';

CREATE VIEW "public_wiki_redirect" WITH (security_barrier = true) AS
SELECT d.source_slug, p.slug AS target_slug
FROM wiki_redirect d
JOIN wiki_page p ON p.page_id = d.page_id AND p.status = 'published';

COMMENT ON VIEW "public_wiki_page" IS 'Publication boundary exposing only the selected published wiki revision.';
