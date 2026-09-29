SET search_path TO food_history, public;

CREATE TABLE "wiki_article_template" (
    "template_key" text NOT NULL CHECK (template_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    "version" integer NOT NULL CHECK (version > 0),
    "article_type" text NOT NULL CHECK (article_type IN
        ('dish', 'ingredient', 'restaurant', 'person', 'company', 'book', 'object')),
    "title" text NOT NULL CHECK (length(trim(title)) > 0),
    "description" text NOT NULL DEFAULT '',
    "body_markdown" text NOT NULL,
    "migration_markdown" text NOT NULL DEFAULT '',
    "is_current" boolean NOT NULL DEFAULT false,
    "created_at" timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (template_key, version)
);
CREATE UNIQUE INDEX uq_wiki_article_template_current
    ON wiki_article_template (template_key) WHERE is_current;

CREATE TABLE "wiki_revision_template" (
    "revision_id" uuid PRIMARY KEY REFERENCES wiki_revision (revision_id) ON DELETE CASCADE,
    "template_key" text NOT NULL,
    "template_version" integer NOT NULL,
    "migrated_from_version" integer,
    FOREIGN KEY (template_key, template_version)
        REFERENCES wiki_article_template (template_key, version) ON DELETE RESTRICT,
    CHECK (migrated_from_version IS NULL OR migrated_from_version < template_version)
);
CREATE FUNCTION prevent_wiki_template_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR
       (OLD.template_key, OLD.version, OLD.article_type, OLD.title, OLD.description,
        OLD.body_markdown, OLD.migration_markdown, OLD.created_at) IS DISTINCT FROM
       (NEW.template_key, NEW.version, NEW.article_type, NEW.title, NEW.description,
        NEW.body_markdown, NEW.migration_markdown, NEW.created_at) THEN
        RAISE EXCEPTION 'template versions are immutable; create a new version';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_wiki_article_template_immutable BEFORE UPDATE OR DELETE
    ON wiki_article_template FOR EACH ROW EXECUTE FUNCTION prevent_wiki_template_mutation();
CREATE TRIGGER trg_wiki_revision_template_immutable BEFORE UPDATE OR DELETE
    ON wiki_revision_template FOR EACH ROW EXECUTE FUNCTION prevent_wiki_revision_mutation();

CREATE VIEW public_wiki_revision_template WITH (security_barrier = true) AS
SELECT link.revision_id, link.template_key, link.template_version,
       template.article_type, template.title
FROM wiki_revision_template link
JOIN wiki_page page ON page.published_revision_id = link.revision_id
                   AND page.status = 'published'
JOIN wiki_article_template template
  ON template.template_key = link.template_key
 AND template.version = link.template_version;

INSERT INTO wiki_article_template
    (template_key, version, article_type, title, description, body_markdown, is_current)
VALUES
('dish', 1, 'dish', 'Dish article', 'Origins, variations, evidence and cultural context for a prepared food.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Overview

## Origins and development

## Ingredients and preparation

## Regional and historical variations

## Evidence and contested claims

```fh-contested-history
{"title":"Contested history","claim":"Summarize the disputed claim.","perspectives":[{"label":"Interpretation one","text":"Evidence-based account."},{"label":"Interpretation two","text":"Alternative evidence-based account."}]}
```

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('ingredient', 1, 'ingredient', 'Ingredient article', 'Production, trade, culinary use and change over time.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Description and classification

## Production and trade

## Culinary uses

## Historical change

```fh-timeline
{"title":"Key dates","events":[]}
```

```fh-historical-price
{"title":"Historical prices","public_id":"FH-REPLACE"}
```

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('restaurant', 1, 'restaurant', 'Restaurant article', 'Restaurant history, locations, menus and ownership.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Overview

## Founding and ownership

## Locations

```fh-map
{"title":"Locations","points":[{"public_id":"FH-REPLACE"}]}
```

## Food and menus

```fh-menu-excerpt
{"title":"Menu excerpt","public_id":"FH-REPLACE","limit":12}
```

## Legacy

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('person', 1, 'person', 'Person article', 'Biography focused on documented food-history work and influence.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Early life and training

## Career

## Food-history significance

```fh-timeline
{"title":"Life and work","events":[]}
```

## Works and legacy

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('company', 1, 'company', 'Company article', 'Company chronology, brands, products and historical impact.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Founding and organization

## Products and brands

## Markets and locations

```fh-timeline
{"title":"Company timeline","events":[]}
```

## Historical significance

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('book', 1, 'book', 'Book article', 'Publication history, contents, reception and source excerpts.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Publication history

## Contents and approach

```fh-source-excerpt
{"title":"Source excerpt","citation_id":"00000000-0000-0000-0000-000000000000"}
```

## Reception and influence

```fh-recipe
{"title":"Recipe transcription","ingredients":[],"steps":[],"citation_id":"00000000-0000-0000-0000-000000000000"}
```

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true),
('object', 1, 'object', 'Object article', 'Material, manufacture, use, provenance and visual comparison.', $template$
```fh-infobox
{"public_id":"FH-REPLACE"}
```

## Description

## Manufacture and dating

## Use and cultural context

```fh-gallery
{"title":"Gallery","public_ids":[],"captions":{}}
```

```fh-comparison
{"title":"Comparison","columns":[]}
```

## Provenance and condition

```fh-bibliography
{"title":"Bibliography","citation_ids":[]}
```
$template$, true);

