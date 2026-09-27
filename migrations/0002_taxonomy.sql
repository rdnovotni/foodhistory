SET search_path TO food_history, public;

CREATE TABLE "vocabulary" (
    "vocabulary_id" uuid NOT NULL,
    "code" varchar(24) NOT NULL UNIQUE,
    "name" text NOT NULL,
    "version" varchar(32),
    "source_uri" text,
    "is_local" boolean NOT NULL DEFAULT true,
    "description" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_vocabulary_" PRIMARY KEY ("vocabulary_id")
);
COMMENT ON TABLE "vocabulary" IS 'Registers each controlled vocabulary or taxonomy family.';

CREATE TABLE "taxonomy_term" (
    "term_id" uuid NOT NULL,
    "vocabulary_id" uuid NOT NULL,
    "code" varchar(96) NOT NULL UNIQUE,
    "preferred_label" text NOT NULL,
    "scope_note" text,
    "term_status" varchar(24) NOT NULL DEFAULT 'approved',
    "introduced_version" varchar(32),
    "deprecated_version" varchar(32),
    "replaced_by_term_id" uuid,
    "sort_key" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_taxonomy_term_" PRIMARY KEY ("term_id")
);
COMMENT ON TABLE "taxonomy_term" IS 'Canonical concept record for every local controlled term.';

CREATE TABLE "taxonomy_label" (
    "taxonomy_label_id" uuid NOT NULL,
    "term_id" uuid NOT NULL,
    "label_type" varchar(24) NOT NULL CHECK ("label_type" IN ('preferred', 'alternate', 'historical', 'deprecated', 'search')),
    "label_text" text NOT NULL,
    "language_tag" varchar(35) NOT NULL DEFAULT 'en',
    "script_code" char(4),
    "transliteration_scheme" text,
    "is_preferred_in_language" boolean NOT NULL DEFAULT false,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_taxonomy_label_" PRIMARY KEY ("taxonomy_label_id")
);
COMMENT ON TABLE "taxonomy_label" IS 'Multilingual preferred, alternate, historical, deprecated, and search-only labels for terms.';

CREATE TABLE "taxonomy_edge" (
    "taxonomy_edge_id" uuid NOT NULL,
    "child_term_id" uuid NOT NULL,
    "parent_term_id" uuid NOT NULL,
    "edge_type" varchar(16) NOT NULL DEFAULT 'broader' CHECK ("edge_type" IN ('broader', 'related')),
    "sequence" integer,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_taxonomy_edge_" PRIMARY KEY ("taxonomy_edge_id")
);
COMMENT ON TABLE "taxonomy_edge" IS 'Supports polyhierarchy and associative relationships among taxonomy concepts.';

CREATE TABLE "taxonomy_mapping" (
    "taxonomy_mapping_id" uuid NOT NULL,
    "term_id" uuid NOT NULL,
    "external_scheme" varchar(64) NOT NULL,
    "external_identifier" text NOT NULL,
    "external_uri" text,
    "mapping_type" varchar(16) NOT NULL CHECK ("mapping_type" IN ('exact', 'close', 'broader', 'narrower', 'related')),
    "confidence_term_id" uuid,
    "mapping_note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_taxonomy_mapping_" PRIMARY KEY ("taxonomy_mapping_id")
);
COMMENT ON TABLE "taxonomy_mapping" IS 'Maps local terms to external authorities without treating close matches as identity.';
