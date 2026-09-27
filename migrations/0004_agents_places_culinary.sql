SET search_path TO food_history, public;

CREATE TABLE "person" (
    "entity_id" uuid NOT NULL,
    "sort_name" text,
    "birth_edtf" varchar(64),
    "death_edtf" varchar(64),
    "occupation_summary" text,
    CONSTRAINT "pk_person_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "person" IS 'Person-specific extension of entity; preferred biographical values are curated summaries backed by assertions/citations when needed.';

CREATE TABLE "organization" (
    "entity_id" uuid NOT NULL,
    "organization_type_term_id" uuid,
    "founded_edtf" varchar(64),
    "dissolved_edtf" varchar(64),
    "website_uri" text,
    CONSTRAINT "pk_organization_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "organization" IS 'Organization/business/institution extension.';

CREATE TABLE "place" (
    "entity_id" uuid NOT NULL,
    "place_type_term_id" uuid,
    "parent_place_entity_id" uuid,
    "latitude" numeric(9,6),
    "longitude" numeric(10,6),
    "coordinate_precision_m" numeric(12,2),
    "geometry_wkt" text,
    "current_address_text" text,
    CONSTRAINT "pk_place_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "place" IS 'Geographic, site, property, building, culinary-region, or archaeological-place extension.';

CREATE TABLE "place_address" (
    "place_address_id" uuid NOT NULL,
    "place_entity_id" uuid NOT NULL,
    "address_line_1" text,
    "address_line_2" text,
    "locality" text,
    "region" text,
    "postal_code" text,
    "country_code" char(2),
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_place_address_" PRIMARY KEY ("place_address_id")
);
COMMENT ON TABLE "place_address" IS 'Historical and current street/address records with validity periods.';

CREATE TABLE "event" (
    "entity_id" uuid NOT NULL,
    "event_type_term_id" uuid,
    "start_edtf" varchar(64),
    "end_edtf" varchar(64),
    "place_entity_id" uuid,
    CONSTRAINT "pk_event_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "event" IS 'Event/occurrence extension for banquets, fairs, competitions, service events, production events, regulatory events, etc.';

CREATE TABLE "culinary_concept" (
    "entity_id" uuid NOT NULL,
    "concept_type_term_id" uuid NOT NULL,
    "foodon_uri" text,
    "langual_code" text,
    CONSTRAINT "pk_culinary_concept_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "culinary_concept" IS 'Extension for dish, beverage, ingredient, process, meal, cuisine/foodway, diet, and unit concepts.';

CREATE TABLE "recipe" (
    "entity_id" uuid NOT NULL,
    "recipe_type_term_id" uuid,
    "yield_text" text,
    "servings_min" numeric(10,2),
    "servings_max" numeric(10,2),
    "temperature_system" varchar(16),
    "recipe_note" text,
    CONSTRAINT "pk_recipe_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "recipe" IS 'Recipe/formulation extension; a recipe is distinct from a dish and from its appearances in sources.';

CREATE TABLE "recipe_occurrence" (
    "recipe_occurrence_id" uuid NOT NULL,
    "recipe_entity_id" uuid,
    "source_entity_id" uuid NOT NULL,
    "citation_id" uuid,
    "title_as_printed" text,
    "date_edtf" varchar(64),
    "transcription_id" uuid,
    "confidence_term_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_recipe_occurrence_" PRIMARY KEY ("recipe_occurrence_id")
);
COMMENT ON TABLE "recipe_occurrence" IS 'Occurrence of a recipe/formulation in a specific source location.';
