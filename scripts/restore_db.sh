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
EXPECTED_CONFIRM="${RESTORE_CONFIRM_VALUE:-$(read_env_value RESTORE_CONFIRM_VALUE)}"
EXPECTED_CONFIRM="${EXPECTED_CONFIRM:-$PROJECT_NAME}"
COMPOSE=(docker compose --ansi never --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

backup_file="${1:-}"
if [[ -z "$backup_file" ]]; then
  echo "Usage: RESTORE_CONFIRM=$EXPECTED_CONFIRM $0 /path/to/backup.dump" >&2
  exit 1
fi

if [[ "${RESTORE_CONFIRM:-}" != "$EXPECTED_CONFIRM" ]]; then
  echo "Refusing restore. Set RESTORE_CONFIRM=$EXPECTED_CONFIRM to continue." >&2
  exit 1
fi

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Required env file not found: $ENV_FILE" >&2
  exit 1
fi

echo "Starting PostgreSQL for restore."
"${COMPOSE[@]}" up -d postgres

echo "Verifying PostgreSQL backup archive."
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$backup_file" >/dev/null

echo "Stopping application writers."
"${COMPOSE[@]}" stop backend frontend || true

echo "Restoring PostgreSQL backup."
"${COMPOSE[@]}" exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$backup_file"

echo "Applying migrations after restore."
"${COMPOSE[@]}" run --rm --no-deps backend alembic upgrade head

echo "Restarting application services."
"${COMPOSE[@]}" up -d backend frontend

echo "Database restore finished."
