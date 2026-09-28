#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.production"}
archive=${1:-}

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing production environment file: $ENV_FILE" >&2
  exit 2
fi
if [ -z "$archive" ] || [ ! -f "$archive" ]; then
  echo "Usage: CONFIRM_RESTORE=RESTORE_FOOD_HISTORY $0 /path/to/backup.dump" >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-}" != "RESTORE_FOOD_HISTORY" ]; then
  echo "Restore refused. Set CONFIRM_RESTORE=RESTORE_FOOD_HISTORY after verifying the target and archive." >&2
  exit 2
fi

"$ROOT/ops/backup.sh"
docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" stop web
trap 'docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" up -d web' EXIT HUP INT TERM

docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
  exec -T db sh -c 'exec pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists --exit-on-error --no-owner --no-privileges' \
  < "$archive"

docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" up -d web
trap - EXIT HUP INT TERM
echo "Restored $archive"
