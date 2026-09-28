#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE=${ENV_FILE:-"$ROOT/.env.production"}
BACKUP_DIR=${BACKUP_DIR:-"$ROOT/backups"}
RETENTION_DAYS=${RETENTION_DAYS:-14}

case "$RETENTION_DAYS" in
  ''|*[!0-9]*) echo "RETENTION_DAYS must be a non-negative integer" >&2; exit 2 ;;
esac

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing production environment file: $ENV_FILE" >&2
  exit 2
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/food_history_$timestamp.dump"
partial="$target.partial"
media_target="$BACKUP_DIR/food_history_$timestamp.media.tar.gz"
media_partial="$media_target.partial"
trap 'rm -f "$partial" "$media_partial"' EXIT HUP INT TERM

docker compose --env-file "$ENV_FILE" -f "$ROOT/compose.production.yaml" \
  exec -T db sh -c 'exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
  > "$partial"

docker run --rm \
  -v food_history_media:/source:ro \
  -v "$BACKUP_DIR:/backup" \
  alpine:3.22 tar -czf "/backup/$(basename "$media_partial")" -C /source .

mv "$partial" "$target"
mv "$media_partial" "$media_target"
chmod 600 "$target"
chmod 600 "$media_target"
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'food_history_*.dump' \
  -mtime "+$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'food_history_*.media.tar.gz' \
  -mtime "+$RETENTION_DAYS" -delete
trap - EXIT HUP INT TERM
echo "Created $target and $media_target"
