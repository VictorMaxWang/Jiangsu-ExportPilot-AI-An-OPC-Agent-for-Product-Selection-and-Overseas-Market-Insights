#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.prod.yml"

read_env_value() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  awk -F= -v key="$key" '
    /^[[:space:]]*#/ { next }
    $1 == key {
      value = $0
      sub(/^[^=]*=/, "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^"|"$/, "", value)
      gsub(/^'\''|'\''$/, "", value)
      print value
      exit
    }
  ' "$ENV_FILE"
}

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(read_env_value COMPOSE_PROJECT_NAME)}"
PROJECT_NAME="${PROJECT_NAME:-supinzhihang_prod}"
BACKUP_DIR="${BACKUP_DIR:-$(read_env_value BACKUP_DIR)}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/supinzhihang/postgres}"
COMPOSE=(docker compose --ansi never --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Required env file not found: $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp_file="$BACKUP_DIR/supinzhihang_${timestamp}.dump.tmp"
backup_file="${tmp_file%.tmp}"

cleanup() {
  rm -f "$tmp_file"
}
trap cleanup ERR INT TERM

echo "Creating PostgreSQL backup."
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' > "$tmp_file"

echo "Verifying PostgreSQL backup archive."
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$tmp_file" >/dev/null

mv "$tmp_file" "$backup_file"
chmod 600 "$backup_file"

size_bytes="$(wc -c < "$backup_file" | tr -d '[:space:]')"
echo "Backup written: $backup_file (${size_bytes} bytes)"
