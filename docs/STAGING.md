# Staging deployment and acceptance

## Provision

`render.yaml` defines a Docker web service and a private managed PostgreSQL 16 database. Both resources explicitly use Render's free plan so this preview can be provisioned without a paid compute commitment. Import the repository as a Render Blueprint, review the proposed region, and apply it. The web service receives its private database connection automatically. Because Render does not support pre-deploy commands on free web services, `RUN_DB_BOOTSTRAP=true` makes the container apply the idempotent migrations and deterministic taxonomy seed before starting the server.

This is disposable preview infrastructure, not production staging. The free web service spins down while idle and can take about a minute to wake; the database check adds a little more startup work. The free PostgreSQL database is limited to 1 GB, has no managed backups, and expires 30 days after creation. Export any reviewed acceptance data that must survive, or move the database to a paid plan before expiry.

The staging release job applies all unapplied migrations and the deterministic taxonomy seed. It intentionally does not set `LOAD_EXAMPLES`; synthetic fixtures must never be mistaken for staging research data.

After Render reports the service healthy, run:

```console
python tools/smoke_test.py --base-url https://food-history-staging.onrender.com
```

The same check is available from GitHub Actions under **Staging smoke test** and accepts the public staging URL as a manual input.

The current service was connected through the repository's public URL rather than a GitHub account integration. Render does not provide automatic deploys for that connection type. After merging application changes, manually deploy the latest `main` commit from the service dashboard, then rerun the smoke test.

## Load reviewed acceptance data

Prepare one reviewed package of each supported ingest type:

- one menu with a real source citation, transcription, sections, and normalized foods;
- one cookbook Work → Expression → Manifestation → Item hierarchy;
- one material-culture object with measurements, marks, condition, holding, provenance, and rights review.

Run the existing transactional loaders against staging only after the packages have passed schema validation and a researcher has confirmed that they are not synthetic examples. Keep the source packages outside the public repository when they contain restricted locations, rights details, or private collection data.

## Acceptance checklist

- `/health` returns HTTP 200 and `status: ok`.
- The homepage and generated API documentation load over HTTPS.
- Entity browse and search never reveal `staff`, `registered`, or `restricted` entities.
- Taxonomy counts total 1,392 and descendant filters return expected records.
- Menu pages preserve printed wording and separately show normalized food links.
- Work pages show the complete Work → Expression → Manifestation → Item chain.
- Object pages show measurements, marks, production, condition, current holding, provenance, and public images.
- Assertions retain claim status, confidence, validity strings, and supporting or contradicting citations.
- On durable paid staging, a database restore test has been completed using the hosting provider's backup/export mechanism. The free preview database has no managed backups and cannot satisfy this production gate.
- Application logs contain no database URLs, credentials, restricted notes, or source excerpts beyond public responses.

## Production gate

Do not promote staging until the acceptance checklist passes with reviewed data, the database is on a durable plan, a backup restore has been demonstrated, and the final public hostname, monitoring ownership, retention policy, and budget have named owners.
