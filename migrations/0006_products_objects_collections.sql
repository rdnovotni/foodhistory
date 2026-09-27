SET search_path TO food_history, public;

CREATE TABLE "brand" (
    "entity_id" uuid NOT NULL,
    "brand_kind" varchar(32),
    "first_use_edtf" varchar(64),
    "retired_edtf" varchar(64),
    CONSTRAINT "pk_brand_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "brand" IS 'Brand/trademark identity extension, independent of product and company ownership.';

CREATE TABLE "product" (
    "entity_id" uuid NOT NULL,
    "generic_food_entity_id" uuid,
    "launch_edtf" varchar(64),
    "discontinue_edtf" varchar(64),
    "default_size_text" text,
    "gtin" varchar(32),
    CONSTRAINT "pk_product_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "product" IS 'Commercially marketed food/beverage/product extension.';

CREATE TABLE "product_brand_assignment" (
    "product_brand_assignment_id" uuid NOT NULL,
    "product_entity_id" uuid NOT NULL,
    "brand_entity_id" uuid NOT NULL,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "is_primary" boolean NOT NULL DEFAULT true,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_product_brand_assignment_" PRIMARY KEY ("product_brand_assignment_id")
);
COMMENT ON TABLE "product_brand_assignment" IS 'Date-bounded brand assignment for products, allowing brand ownership and branding to change over time.';

CREATE TABLE "physical_object" (
    "entity_id" uuid NOT NULL,
    "object_type_term_id" uuid NOT NULL,
    "authenticity_status" varchar(32) CHECK ("authenticity_status" IN ('original', 'period_copy', 'authorized_reproduction', 'reproduction', 'replica', 'fantasy', 'counterfeit', 'uncertain')),
    "manufacture_edtf" varchar(64),
    "material_summary" text,
    "completeness_text" text,
    "object_note" text,
    CONSTRAINT "pk_physical_object_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "physical_object" IS 'Tangible human-made object extension, independent of subject or collector specialty.';

CREATE TABLE "measurement" (
    "measurement_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "measurement_type" varchar(32) NOT NULL,
    "value" numeric(24,8),
    "value_min" numeric(24,8),
    "value_max" numeric(24,8),
    "unit_code" varchar(32),
    "display_text" text,
    "method_note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_measurement_" PRIMARY KEY ("measurement_id")
);
COMMENT ON TABLE "measurement" IS 'Reusable measurements for objects, documents, specimens, and packages.';

CREATE TABLE "object_mark" (
    "object_mark_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "mark_type" varchar(32) NOT NULL,
    "transcription" text,
    "normalized_text" text,
    "location_on_object" text,
    "maker_entity_id" uuid,
    "date_code_text" text,
    "digital_entity_id" uuid,
    "citation_id" uuid,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_object_mark_" PRIMARY KEY ("object_mark_id")
);
COMMENT ON TABLE "object_mark" IS 'Maker marks, backstamps, hallmarks, embossed text, signatures, labels, date codes, inscriptions, and other diagnostic marks.';

CREATE TABLE "production_record" (
    "production_record_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "manufacturer_entity_id" uuid,
    "production_place_entity_id" uuid,
    "model_or_pattern" text,
    "design_number" text,
    "batch_or_lot_code" text,
    "date_edtf" varchar(64),
    "process_term_id" uuid,
    "citation_id" uuid,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_production_record_" PRIMARY KEY ("production_record_id")
);
COMMENT ON TABLE "production_record" IS 'Manufacturing/production details for objects and products without forcing every maker/date into the object row.';

CREATE TABLE "condition_assessment" (
    "condition_assessment_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "assessment_date" date,
    "condition_term_id" uuid,
    "condition_text" text NOT NULL,
    "completeness_text" text,
    "restoration_text" text,
    "assessor_entity_id" uuid,
    "assessor_user_id" uuid,
    "digital_entity_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_condition_assessment_" PRIMARY KEY ("condition_assessment_id")
);
COMMENT ON TABLE "condition_assessment" IS 'Dated condition/completeness/conservation observation rather than a permanent identity attribute.';

CREATE TABLE "collection" (
    "entity_id" uuid NOT NULL,
    "collection_type_term_id" uuid,
    "owning_entity_id" uuid,
    "collection_identifier" text,
    "finding_aid_uri" text,
    CONSTRAINT "pk_collection_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "collection" IS 'Curated collection/archive/aggregate extension.';

CREATE TABLE "collection_membership" (
    "collection_membership_id" uuid NOT NULL,
    "collection_entity_id" uuid NOT NULL,
    "member_entity_id" uuid NOT NULL,
    "membership_role" text,
    "sequence" integer,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_collection_membership_" PRIMARY KEY ("collection_membership_id")
);
COMMENT ON TABLE "collection_membership" IS 'Membership of entities in collections, sets, services, archival aggregates, or auction lots.';

CREATE TABLE "holding" (
    "holding_id" uuid NOT NULL,
    "item_entity_id" uuid NOT NULL,
    "holder_entity_id" uuid NOT NULL,
    "collection_entity_id" uuid,
    "accession_number" text,
    "local_call_number" text,
    "storage_location" text,
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "is_current" boolean NOT NULL DEFAULT true,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_holding_" PRIMARY KEY ("holding_id")
);
COMMENT ON TABLE "holding" IS 'Current or historical institutional/private holding, accession, and storage-location record.';

CREATE TABLE "provenance_event" (
    "provenance_event_id" uuid NOT NULL,
    "subject_entity_id" uuid NOT NULL,
    "event_type" varchar(24) NOT NULL CHECK ("event_type" IN ('ownership', 'custody', 'acquisition', 'disposal', 'loan', 'exhibition', 'publication', 'restoration')),
    "from_entity_id" uuid,
    "to_entity_id" uuid,
    "place_entity_id" uuid,
    "date_edtf" varchar(64),
    "transaction_entity_id" uuid,
    "citation_id" uuid,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_provenance_event_" PRIMARY KEY ("provenance_event_id")
);
COMMENT ON TABLE "provenance_event" IS 'Dated ownership/custody/acquisition/loan/exhibition/publication/restoration event for an entity.';
