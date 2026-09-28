#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.production"}

if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
  echo "Refusing to update a checkout with uncommitted changes." >&2
  exit 2
fi

"$ROOT/ops/backup.sh"
git -C "$ROOT" pull --ff-only
docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" build --pull
docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" up -d --remove-orphans
docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" ps

echo "Update complete. Run ops/healthcheck.sh against the public URL."
