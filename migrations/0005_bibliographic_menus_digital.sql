SET search_path TO food_history, public;

CREATE TABLE "work" (
    "entity_id" uuid NOT NULL,
    "work_type_term_id" uuid,
    "original_language_tag" varchar(35),
    "creation_edtf" varchar(64),
    CONSTRAINT "pk_work_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "work" IS 'Abstract intellectual or creative work.';

CREATE TABLE "expression" (
    "entity_id" uuid NOT NULL,
    "work_entity_id" uuid NOT NULL,
    "language_tag" varchar(35),
    "version_statement" text,
    "expression_edtf" varchar(64),
    CONSTRAINT "pk_expression_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "expression" IS 'Version, translation, revision, adaptation, or other expression of a work.';

CREATE TABLE "manifestation" (
    "entity_id" uuid NOT NULL,
    "edition_statement" text,
    "publication_edtf" varchar(64),
    "extent_text" text,
    "isbn" varchar(32),
    "issn" varchar(16),
    "oclc_number" varchar(32),
    CONSTRAINT "pk_manifestation_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "manifestation" IS 'Edition, issue, printing, release, or produced embodiment shared by multiple copies/items.';

CREATE TABLE "manifestation_expression" (
    "manifestation_expression_id" uuid NOT NULL,
    "manifestation_entity_id" uuid NOT NULL,
    "expression_entity_id" uuid NOT NULL,
    "sequence" integer,
    CONSTRAINT "pk_manifestation_expression_" PRIMARY KEY ("manifestation_expression_id")
);
COMMENT ON TABLE "manifestation_expression" IS 'Many-to-many link allowing a manifestation to embody one or more expressions.';

CREATE TABLE "item" (
    "entity_id" uuid NOT NULL,
    "manifestation_entity_id" uuid,
    "item_status" varchar(32),
    "copy_number" text,
    "signed_flag" boolean NOT NULL DEFAULT false,
    "inscription_summary" text,
    CONSTRAINT "pk_item_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "item" IS 'Individual physical or digital exemplar; may instantiate a manifestation or exist as a unique standalone item.';

CREATE TABLE "credit" (
    "credit_id" uuid NOT NULL,
    "resource_entity_id" uuid NOT NULL,
    "agent_entity_id" uuid NOT NULL,
    "role_term_id" uuid,
    "credited_as" text,
    "sequence" integer,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_credit_" PRIMARY KEY ("credit_id")
);
COMMENT ON TABLE "credit" IS 'Agent credit for a work/expression/manifestation/item such as author, editor, translator, illustrator, photographer, printer, or chef.';

CREATE TABLE "publication_statement" (
    "publication_statement_id" uuid NOT NULL,
    "manifestation_entity_id" uuid NOT NULL,
    "statement_type" varchar(24) NOT NULL,
    "agent_entity_id" uuid,
    "place_entity_id" uuid,
    "date_edtf" varchar(64),
    "statement_text" text,
    "sequence" integer,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_publication_statement_" PRIMARY KEY ("publication_statement_id")
);
COMMENT ON TABLE "publication_statement" IS 'Publisher, printer, place, and date statements for manifestations; supports multiple statements/agents.';

CREATE TABLE "document" (
    "entity_id" uuid NOT NULL,
    "document_type_term_id" uuid NOT NULL,
    "page_count" integer,
    "date_edtf" varchar(64),
    "language_summary" text,
    "document_note" text,
    CONSTRAINT "pk_document_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "document" IS 'Document-specific extension of an Item, including menus, letters, invoices, labels, ration books, pamphlets, cards, and other textual records.';

CREATE TABLE "menu" (
    "entity_id" uuid NOT NULL,
    "menu_type_term_id" uuid NOT NULL,
    "establishment_entity_id" uuid,
    "host_event_entity_id" uuid,
    "meal_term_id" uuid,
    "service_date_edtf" varchar(64),
    "currency_code" char(3),
    "menu_note" text,
    CONSTRAINT "pk_menu_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "menu" IS 'Menu-specific extension of a document; venue/transport/institution is modeled by linked agents/contexts rather than separate menu tables.';

CREATE TABLE "menu_section" (
    "menu_section_id" uuid NOT NULL,
    "menu_entity_id" uuid NOT NULL,
    "sequence" integer NOT NULL,
    "heading_original" text,
    "course_term_id" uuid,
    "page_label" text,
    CONSTRAINT "pk_menu_section_" PRIMARY KEY ("menu_section_id")
);
COMMENT ON TABLE "menu_section" IS 'Ordered section/course heading within a menu.';

CREATE TABLE "menu_item" (
    "menu_item_id" uuid NOT NULL,
    "menu_entity_id" uuid NOT NULL,
    "menu_section_id" uuid,
    "sequence" integer NOT NULL,
    "printed_name" text NOT NULL,
    "printed_description" text,
    "normalized_food_entity_id" uuid,
    "portion_text" text,
    "price_text" text,
    "price_amount" numeric(18,6),
    "currency_code" char(3),
    "price_basis_text" text,
    "availability_note" text,
    "transcription_confidence" numeric(5,4),
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_menu_item_" PRIMARY KEY ("menu_item_id")
);
COMMENT ON TABLE "menu_item" IS 'Transcribed offered dish/beverage/product line on a menu, retaining the printed text and optional normalized entity link.';

CREATE TABLE "media_item" (
    "entity_id" uuid NOT NULL,
    "media_type_term_id" uuid NOT NULL,
    "capture_or_creation_edtf" varchar(64),
    "duration_ms" bigint,
    "media_note" text,
    CONSTRAINT "pk_media_item_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "media_item" IS 'Photographic, graphic, audio, or moving-image item extension.';

CREATE TABLE "digital_resource" (
    "entity_id" uuid NOT NULL,
    "resource_type_term_id" uuid,
    "storage_uri" text NOT NULL,
    "original_filename" text,
    "mime_type" varchar(128),
    "file_size_bytes" bigint,
    "sha256" char(64),
    "width_px" integer,
    "height_px" integer,
    "dpi" numeric(8,2),
    "duration_ms" bigint,
    "iiif_manifest_uri" text,
    "source_digital_entity_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_digital_resource_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "digital_resource" IS 'Born-digital resource or managed digital file/surrogate with preservation metadata.';

CREATE TABLE "digital_representation" (
    "digital_representation_id" uuid NOT NULL,
    "digital_entity_id" uuid NOT NULL,
    "represented_entity_id" uuid NOT NULL,
    "role_code" varchar(24) NOT NULL CHECK ("role_code" IN ('primary', 'front', 'back', 'interior', 'page', 'detail', 'mark', 'label', 'condition', 'provenance')),
    "sequence" integer,
    "is_primary" boolean NOT NULL DEFAULT false,
    "caption" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_digital_representation_" PRIMARY KEY ("digital_representation_id")
);
COMMENT ON TABLE "digital_representation" IS 'Links digital resources to the entities they depict, scan, reproduce, document, or represent.';

CREATE TABLE "transcription" (
    "transcription_id" uuid NOT NULL,
    "source_entity_id" uuid NOT NULL,
    "digital_entity_id" uuid,
    "transcription_type" varchar(24) NOT NULL CHECK ("transcription_type" IN ('ocr', 'diplomatic', 'normalized', 'translation', 'metadata')),
    "status" varchar(24) NOT NULL CHECK ("status" IN ('draft', 'machine', 'human_checked', 'expert_reviewed')),
    "language_tag" varchar(35),
    "text_content" text NOT NULL,
    "overall_confidence" numeric(5,4),
    "generated_by" text,
    "reviewed_by_user_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_transcription_" PRIMARY KEY ("transcription_id")
);
COMMENT ON TABLE "transcription" IS 'OCR, diplomatic transcription, normalized transcription, or translation of a source entity or digital representation.';
