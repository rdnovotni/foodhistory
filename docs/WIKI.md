# Wiki editorial foundation

The wiki is a narrative layer over the canonical Food History catalogue. Articles explain and connect records; they do not overwrite entity fields, assertions, taxonomy assignments, or citations.

## Content model

- `wiki_page` is the stable public identity and URL slug.
- `wiki_revision` is an immutable article snapshot. Saving an edit always inserts a new revision.
- `wiki_review` is an append-only trail of submissions, approvals, requested changes, and later withdrawals.
- `wiki_revision_entity` links a particular revision to canonical entity public records.
- `wiki_revision_citation` links a particular revision to canonical citation locators. Evidence stays in the existing citation/assertion model.
- `wiki_redirect` preserves renamed article URLs.

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
