SET search_path TO food_history, public;

CREATE TABLE "price_observation" (
    "price_observation_id" uuid NOT NULL,
    "subject_entity_id" uuid NOT NULL,
    "price_type" varchar(16) NOT NULL CHECK ("price_type" IN ('menu', 'retail', 'wholesale', 'commodity', 'asking', 'sold', 'estimate')),
    "amount" numeric(24,8),
    "amount_text" text,
    "currency_code" char(3),
    "currency_text_original" text,
    "quantity_value" numeric(24,8),
    "quantity_unit" varchar(32),
    "basis_text" text,
    "place_entity_id" uuid,
    "date_edtf" varchar(64),
    "citation_id" uuid NOT NULL,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_price_observation_" PRIMARY KEY ("price_observation_id")
);
COMMENT ON TABLE "price_observation" IS 'Historical food/product/service/object price observation distinct from collectible sale transactions.';

CREATE TABLE "transaction_event" (
    "entity_id" uuid NOT NULL,
    "transaction_type" varchar(24) NOT NULL CHECK ("transaction_type" IN ('sale', 'auction', 'gift', 'donation', 'trade', 'consignment', 'bequest', 'transfer')),
    "seller_entity_id" uuid,
    "buyer_entity_id" uuid,
    "venue_entity_id" uuid,
    "auction_or_sale_name" text,
    "sale_date" date,
    "currency_code" char(3),
    "total_amount" numeric(24,8),
    "fees_amount" numeric(24,8),
    "citation_id" uuid,
    CONSTRAINT "pk_transaction_event_" PRIMARY KEY ("entity_id")
);
COMMENT ON TABLE "transaction_event" IS 'Sale/auction/gift/donation/trade/consignment/bequest/transfer event treated as a first-class historical event.';

CREATE TABLE "transaction_line" (
    "transaction_line_id" uuid NOT NULL,
    "transaction_entity_id" uuid NOT NULL,
    "subject_entity_id" uuid NOT NULL,
    "lot_number" text,
    "quantity" numeric(18,6),
    "realized_amount" numeric(24,8),
    "currency_code" char(3),
    "hammer_amount" numeric(24,8),
    "buyer_premium_amount" numeric(24,8),
    "condition_at_sale_text" text,
    "citation_id" uuid,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_transaction_line_" PRIMARY KEY ("transaction_line_id")
);
COMMENT ON TABLE "transaction_line" IS 'Lot/line-level transfer and realized price for entities within a transaction.';

CREATE TABLE "rights_assignment" (
    "rights_assignment_id" uuid NOT NULL,
    "entity_id" uuid NOT NULL,
    "rights_statement_uri" text,
    "license_uri" text,
    "rights_holder_entity_id" uuid,
    "copyright_status_text" text,
    "access_level" varchar(32) NOT NULL DEFAULT 'public' CHECK ("access_level" IN ('public', 'restricted', 'embargoed', 'culturally_sensitive', 'private')),
    "valid_from_edtf" varchar(64),
    "valid_to_edtf" varchar(64),
    "ethical_protocol_text" text,
    "note" text,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    "updated_at" timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT "pk_rights_assignment_" PRIMARY KEY ("rights_assignment_id")
);
COMMENT ON TABLE "rights_assignment" IS 'Rights, licensing, access restrictions, and cultural/ethical protocol metadata for entities and digital resources.';
