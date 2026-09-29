# Wiki editorial foundation

The wiki is a narrative layer over the canonical Food History catalogue. Articles explain and connect records; they do not overwrite entity fields, assertions, taxonomy assignments, or citations.

## Content model

- `wiki_page` is the stable public identity and URL slug.
- `wiki_revision` is an immutable article snapshot. Saving an edit always inserts a new revision.
- `wiki_review` is an append-only trail of submissions, approvals, requested changes, and later withdrawals.
- `wiki_revision_entity` links a particular revision to canonical entity public records.
- `wiki_revision_citation` links a particular revision to canonical citation locators. Evidence stays in the existing citation/assertion model.
- `wiki_redirect` preserves renamed article URLs.
- `wiki_revision_link` indexes `[[slug]]` references in each immutable revision; public backlinks only use the currently published revision.

Only the revision selected by `published_revision_id` is visible at `/wiki` or `/v1/wiki/pages`. Drafts and review history never appear through public routes.

## Private workflow

The editorial interface exists only when `APP_MODE=editorial`. Its routes are not registered in public mode.

1. An owner or editor creates a Markdown draft and links relevant entity public IDs and citation UUIDs.
2. Every save creates a new immutable revision and returns the page to draft.
3. The author submits the current revision for review.
4. An owner or reviewer approves it or requests changes.
5. An owner publishes the approved revision. Earlier public revisions remain in the database for auditability.

Markdown is rendered with embedded HTML disabled and sanitized again before display. Editorial sessions use opaque random tokens stored only as SHA-256 digests, `HttpOnly` cookies, strict same-site policy, expiration, role checks, and synchronizer CSRF tokens. Passwords use Python's scrypt implementation with per-password salts.

## Create the first owner

After migrations have run, execute inside the private web container:

```console
docker compose --env-file .env.production -f compose.production.yaml exec web \
  python tools/create_editor.py owner --display-name "Your Name" --role owner
```

The command prompts twice for a password and never accepts it as a command-line option. Visit `/editor/login` through the private Tailscale address.

For local development, `compose.yaml` enables editorial mode and disables secure cookies only because the local URL is plain HTTP. Production should retain `EDITOR_COOKIE_SECURE=true` and use Tailscale HTTPS.

## Public boundary

The production Compose file uses two independent application processes:

- `web` runs in editorial mode, binds only to host loopback, and is reached privately through Tailscale.
- `public_web` runs in public mode, has no editor routes, and is the only application process reachable from Caddy's public network.

They deliberately share the canonical PostgreSQL database. The setup job provisions `PUBLIC_DATABASE_USER` with only `CONNECT`, schema `USAGE`, and `SELECT` privileges, enables PostgreSQL's read-only transaction default for that role, and gives `public_web` only those credentials. Credentials, sessions, review records, drafts, and base wiki tables are explicitly revoked; security-barrier views expose only published revisions and their public catalogue links.

## Phase 2 authoring tools

The article form provides authenticated type-ahead lookup for entities, canonical citations, and existing image resources. Pickers store stable IDs in the revision; labels remain display conveniences. Categories are also revision-specific and become publicly browsable only when their attached revision is published.

Article search uses PostgreSQL full-text indexing over the selected published revision's title, summary, and Markdown. The editorial history screen lists every immutable revision and compares any two versions side by side.

Image uploads accept JPEG, PNG, WebP, and GIF, verify the actual image format, enforce `MEDIA_MAX_BYTES`, compute SHA-256, and store one content-addressed file under `MEDIA_ROOT`. PostgreSQL stores the canonical `digital_resource` record and revision-specific placement, caption, and required alternative text. Uploaded resources remain staff-only until an approved attached revision is published. Only rights-cleared media should be uploaded; record more detailed rights and restrictions using the canonical rights model before public launch.

The starter briefs under `content/wiki-starters/` are editorial checklists, not historical claims. They intentionally contain citation placeholders and must not be published until a researcher replaces every placeholder with evidence-backed prose and links.

## Article navigation and links

Use `##`, `###`, and `####` headings to create an automatic on-page table of contents. Repeated headings get distinct anchors. The article breadcrumb goes through its first assigned category, when one exists; all categories remain visible as tags.

Use `[[page-slug]]` for a wiki link with the destination's current title, or `[[page-slug|custom label]]` for chosen text. The editor suggests published pages while typing after `[[`. References inside code and ordinary Markdown links are ignored. Links to unpublished or missing pages show as unresolved text until the target is published. Old slugs resolve through published redirects. “What links here” lists published articles whose published revision references the page, including references through redirects. A page without backlinks omits that section.

After applying migration `0016_wiki_links.sql` to a database with existing articles, run `python tools/backfill_wiki_links.py` once with `DATABASE_URL` set to the editorial database. The command can be safely rerun and never changes authored revisions. The public reader must be reprovisioned so it can read the new publication view while the base link table stays private.

## Series, discovery, and reading tools

- Owners and editors create a series at `/editor/series`, then choose its series and numbered position on each article revision. Public series boxes link every currently published member and show previous/next navigation. A public series landing page is `/wiki/series/{slug}`.
- Editors may choose related article slugs and mark a revision as a disambiguation page. Published articles sharing categories fill any remaining related slots; unpublished targets never render publicly. Disambiguation pages explain their purpose and list their selected destinations.
- Owners manage old page slugs in the article editor. A redirect cannot claim an active page slug or another redirect slug. Draft targets do not expose redirects publicly. Stable page slugs are not renamed by this interface.
- Every successful publication creates an append-only event. `/wiki/{slug}/history` lists only revisions with a publication event, and `/wiki/{slug}/revisions/{number}` is a stable link to their published prose. `/wiki/{slug}/information` shows the public page ID, dates, redirect names, and counts. Migration 0017 recovers the *currently published* revision for existing pages; it cannot safely reconstruct older publication events from approvals, so those older revisions remain private unless there is separate proof they were published.
- `/wiki` features recent first publications, improvements with at least two recorded publications, and articles whose optional documented event month/day matches the current date in America/Chicago. `/wiki/random` selects a published page. A page needs a researched event date set in its current published revision to enter “On this day.”
- `?view=focus` hides site navigation and supplemental sections, and browser print uses a clean article layout. Reading time uses visible prose at roughly 200 words per minute, rounded up.
- Owners create and publish reusable plain-text glossary terms at `/editor/glossary`. Authors insert `{{term-slug}}` in Markdown; an unavailable term remains literal. Clicking a term reveals its definition and, if available publicly, its related article. Hovering a wiki link displays a short preview fetched from the published article only.
- Standard Markdown footnotes (`[^1]` and a matching `[^1]: Definition`) render with anchors; hovering or focusing the reference previews the note without scrolling. Inline HTML remains disabled, and rendered markup is sanitized.

Apply migration 0017 through the normal bootstrap and reprovision the public database reader to grant the new public views while revoking the six new private tables. The bootstrap remains safe to rerun. The recovered publication timestamp for an existing page uses its last page update as the best available approximation.

## Reusable article structures

New articles may start from a versioned dish, ingredient, restaurant, person, company, book, or object template. The chosen template and version are recorded on each revision. When a newer immutable template version exists, the editor offers an upgrade that creates a new article revision, preserves authored content and links, appends the version's migration Markdown, and records the prior version.

Reusable structures are fenced JSON blocks whose language begins with `fh-`. They remain legible in source, are rendered into controlled HTML on the server, and pass through the same sanitizer as ordinary Markdown. Supported names are `infobox`, `notice`, `quotation`, `sidebar`, `gallery`, `comparison`, `timeline`, `map`, `source-excerpt`, `recipe`, `menu-excerpt`, `historical-price`, `contested-history`, and `bibliography`.

````markdown
```fh-infobox
{"public_id":"FH-FOOD-EXAMPLE"}
```

```fh-notice
{"title":"Research note","tone":"research","text":"Explain the evidence limitation."}
```

```fh-bibliography
{"title":"Bibliography","citation_ids":["00000000-0000-0000-0000-000000000000"]}
```
````

Infoboxes, maps, galleries, menu excerpts, historical prices, source excerpts, and bibliographies resolve stable canonical IDs at read time. Missing or non-public records render as unavailable and never expose draft catalogue data. Apply migration `0018_wiki_structures.sql` and reprovision the public reader after deployment.
