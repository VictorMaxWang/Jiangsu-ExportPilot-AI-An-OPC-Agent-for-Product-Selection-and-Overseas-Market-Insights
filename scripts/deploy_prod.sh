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
COMPOSE=(docker compose --ansi never --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "Required file not found: $path" >&2
    exit 1
  fi
}

wait_for_backend() {
  local port="${BACKEND_BIND_PORT:-$(read_env_value BACKEND_BIND_PORT)}"
  port="${port:-8000}"
  local url="http://127.0.0.1:${port}/health"

  for _ in {1..30}; do
    if curl -fsS "$url" >/dev/null; then
      echo "Backend health check passed: $url"
      return 0
    fi
    sleep 2
  done

  echo "Backend health check failed: $url" >&2
  return 1
}

require_file "$ENV_FILE"
require_file "$COMPOSE_FILE"

echo "Validating production compose configuration."
"${COMPOSE[@]}" config --quiet

echo "Pulling production base images."
"${COMPOSE[@]}" pull postgres redis

echo "Building application images."
"${COMPOSE[@]}" build --pull backend frontend

echo "Starting PostgreSQL and Redis."
"${COMPOSE[@]}" up -d postgres redis

echo "Running pre-migration database backup."
if [[ "${SKIP_BACKUP_BEFORE_MIGRATION:-}" == "1" ]]; then
  echo "Backup skipped because SKIP_BACKUP_BEFORE_MIGRATION=1."
else
  ENV_FILE="$ENV_FILE" COMPOSE_PROJECT_NAME="$PROJECT_NAME" bash "$SCRIPT_DIR/backup_db.sh"
fi

echo "Applying database migrations."
"${COMPOSE[@]}" run --rm --no-deps backend alembic upgrade head

echo "Starting application services."
"${COMPOSE[@]}" up -d --remove-orphans backend frontend

wait_for_backend

echo "Production deployment finished. Inspect status with: docker compose --project-name $PROJECT_NAME -f $COMPOSE_FILE ps"
