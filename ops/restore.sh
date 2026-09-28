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
media_archive=${archive%.dump}.media.tar.gz
if [ ! -f "$media_archive" ]; then
  echo "Missing paired media archive: $media_archive" >&2
  exit 2
fi

"$ROOT/ops/backup.sh"
public_was_running=$(docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
  --profile public ps --status running -q public_web)
docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" stop web
if [ -n "$public_was_running" ]; then
  docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
    --profile public stop public_web
fi
restart_services() {
  docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" up -d web
  if [ -n "$public_was_running" ]; then
    docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
      --profile public up -d public_web
  fi
}
trap restart_services EXIT HUP INT TERM

docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
  exec -T db sh -c 'exec pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists --exit-on-error --no-owner --no-privileges' \
  < "$archive"

media_dir=$(CDPATH= cd -- "$(dirname -- "$media_archive")" && pwd)
media_name=$(basename -- "$media_archive")
docker run --rm \
  -v food_history_media:/target \
  -v "$media_dir:/backup:ro" \
  alpine:3.22 sh -c 'rm -rf /target/* && tar -xzf "/backup/$1" -C /target' sh "$media_name"

restart_services
trap - EXIT HUP INT TERM
echo "Restored $archive and $media_archive"
