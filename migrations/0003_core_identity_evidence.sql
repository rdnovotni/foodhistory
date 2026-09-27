SET search_path TO food_history, public;

CREATE TABLE "entity" (
    "entity_id" uuid NOT NULL,
    "public_id" varchar(40) NOT NULL UNIQUE,
    "entity_type_term_id" uuid NOT NULL,
    "preferred_label" text NOT NULL,
    "canonical_slug" text UNIQUE,
    "summary" text,
    "record_status" varchar(24) NOT NULL DEFAULT 'draft' CHECK ("record_status" IN ('draft', 'reviewed', 'published', 'superseded', 'merged', 'restricted')),
    "visibility" varchar(24) NOT NULL DEFAULT 'public' CHECK ("visibility" IN ('public', 'registered', 'staff', 'restricted')),
    "merged_into_entity_id" uuid,
    "created_by_user_id" uuid,
    "updated_by_user_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_entity_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "entity" IS 'Stable identity spine for every independently addressable historical, bibliographic, material, biological, analytical, or research entity.';

CREATE TABLE "entity_name" (
    "entity_name_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "name_type" varchar(24) NOT NULL CHECK ("name_type" IN ('preferred', 'alternate', 'original', 'historical', 'translated', 'romanized', 'acronym', 'former', 'trade')),
    "name_text" text NOT NULL,
    "language_tag" varchar(35),
    "script_code" char(4),
    "transliteration_scheme" text,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "is_preferred_in_language" boolean NOT NULL DEFAULT false,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_entity_name_" PRIMARY KEY ("entity_name_id")
);
COMMENT ON TABLE "entity_name" IS 'Multilingual, historical, original, translated, romanized, and alternate names for entities.';

CREATE TABLE "entity_note" (
    "entity_note_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "note_type" varchar(24) NOT NULL DEFAULT 'general' CHECK ("note_type" IN ('general', 'research', 'editorial', 'provenance', 'identification', 'private')),
    "note_text" text NOT NULL,
    "visibility" varchar(24) NOT NULL DEFAULT 'public' CHECK ("visibility" IN ('public', 'registered', 'staff', 'restricted')),
    "created_by_user_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_entity_note_" PRIMARY KEY ("entity_note_id")
);
COMMENT ON TABLE "entity_note" IS 'Typed human-authored notes that should not be forced into structured fields.';

CREATE TABLE "external_identifier" (
    "external_identifier_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "scheme_code" varchar(64) NOT NULL,
    "identifier_value" text NOT NULL,
    "identifier_uri" text,
    "is_primary_for_scheme" boolean NOT NULL DEFAULT false,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_external_identifier_" PRIMARY KEY ("external_identifier_id")
);
COMMENT ON TABLE "external_identifier" IS 'Links entities to external authority, catalogue, registration, barcode, library, or specialist identifiers.';

CREATE TABLE "entity_language" (
    "entity_language_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "language_tag" varchar(35) NOT NULL,
    "script_code" char(4),
    "role_code" varchar(32) NOT NULL,
    "is_primary" boolean NOT NULL DEFAULT false,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_entity_language_" PRIMARY KEY ("entity_language_id")
);
COMMENT ON TABLE "entity_language" IS 'Associates entities with languages/scripts in roles such as original language, publication language, inscription language, or translation language.';

CREATE TABLE "entity_term_assignment" (
    "entity_term_assignment_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "term_id" uuid NOT NULL,
    "assignment_kind" varchar(32) NOT NULL CHECK ("assignment_kind" IN ('classification', 'subject', 'context', 'collecting_domain', 'food_class', 'object_type', 'evidence_status')),
    "is_primary" boolean NOT NULL DEFAULT false,
    "sequence" integer,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "confidence_term_id" uuid,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_entity_term_assignment_" PRIMARY KEY ("entity_term_assignment_id")
);
COMMENT ON TABLE "entity_term_assignment" IS 'Applies subject, context, collecting-domain, object-type, food-class, and other controlled terms to entities.';

CREATE TABLE "citation" (
    "citation_id" uuid NOT NULL,
    "source_entity_id" uuid NOT NULL,
    "locator_text" text,
    "page_label" varchar(64),
    "folio_label" varchar(64),
    "image_label" varchar(128),
    "timestamp_start_ms" bigint,
    "timestamp_end_ms" bigint,
    "repository_entity_id" uuid,
    "archival_container" text,
    "stable_uri" text,
    "access_date" date,
    "excerpt" text,
    "citation_note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_citation_" PRIMARY KEY ("citation_id")
);
COMMENT ON TABLE "citation" IS 'Precise locator into a source entity, including page/folio/image/timestamp/repository context and optional excerpt.';

CREATE TABLE "assertion" (
    "assertion_id" uuid NOT NULL,
    "subject_entity_id" uuid NOT NULL,
    "predicate_term_id" uuid NOT NULL,
    "value_kind" varchar(16) NOT NULL CHECK ("value_kind" IN ('entity', 'text', 'number', 'date', 'boolean', 'json')),
    "object_entity_id" uuid,
    "value_text" text,
    "value_number" numeric(24,8),
    "value_date" date,
    "value_boolean" boolean,
    "value_json" jsonb,
    "unit_entity_id" uuid,
    "qualifier_place_entity_id" uuid,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "date_display" text,
    "claim_status_term_id" uuid,
    "confidence_term_id" uuid,
    "is_preferred" boolean NOT NULL DEFAULT false,
    "assertion_note" text,
    "created_by_user_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_assertion_" PRIMARY KEY ("assertion_id")
);
COMMENT ON TABLE "assertion" IS 'Evidence-bearing proposition linking an entity to another entity or typed literal; used for contested, sourced, date-bounded, or historically variable facts.';

CREATE TABLE "assertion_evidence" (
    "assertion_evidence_id" uuid NOT NULL,
    "assertion_id" uuid NOT NULL,
    "citation_id" uuid NOT NULL,
    "evidence_role" varchar(16) NOT NULL CHECK ("evidence_role" IN ('supports', 'contradicts', 'qualifies')),
    "strength_term_id" uuid,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_assertion_evidence_" PRIMARY KEY ("assertion_evidence_id")
);
COMMENT ON TABLE "assertion_evidence" IS 'Connects assertions to citations as supporting, contradicting, or qualifying evidence.';

CREATE TABLE "observation" (
    "observation_id" uuid NOT NULL,
    "observation_entity_id" uuid,
    "observed_entity_id" uuid,
    "observation_type_term_id" uuid NOT NULL,
    "source_entity_id" uuid NOT NULL,
    "citation_id" uuid,
    "observed_text" text,
    "place_entity_id" uuid,
    "date_edtf" varchar(64),
    "date_display" text,
    "confidence_term_id" uuid,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_observation_" PRIMARY KEY ("observation_id")
);
COMMENT ON TABLE "observation" IS 'Structured occurrence of an entity in a source, time, place, market, menu, advertisement, recipe, or other historical context.';
