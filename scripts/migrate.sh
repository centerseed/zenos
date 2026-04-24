#!/usr/bin/env bash
# migrate.sh — Apply SQL migrations to a ZenOS database target.
#
# Secret / database mapping
# ─────────────────────────
#   MIGRATION_TARGET: prod | staging             (default: prod)
#   DB_SECRET_NAME  : zenos-database-url         (prod)
#                 or zenos-staging-database-url  (staging)
#   GCP project     : zentropy-4f7a5             (default)
#   Database        : Cloud SQL zentropy-db, schema zenos
#
# The legacy secret "database-url" in project "zenos-naruvia" points to
# neondb which is an empty / legacy database — NOT production.
# Do NOT change the defaults back to those values.
#
# Override via environment variables or flags:
#   ./scripts/migrate.sh --target staging --status
#   ./scripts/migrate.sh --target prod --only 20260423_0004_wave9_l3_action_preflight
#   PROJECT_ID=<gcp-project>  DB_SECRET_NAME=<secret>  ./scripts/migrate.sh
#   DATABASE_URL=<url>  ./scripts/migrate.sh            (skip Secret Manager)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ID="${PROJECT_ID:-zentropy-4f7a5}"
MIGRATION_TARGET="${MIGRATION_TARGET:-prod}"
RUNNER_ARGS=()
DB_PROXY_PORT="${DB_PROXY_PORT:-}"
PYTHON_BIN="${PYTHON_BIN:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      if [ "$#" -lt 2 ]; then
        echo "--target requires a value: prod or staging"
        exit 1
      fi
      MIGRATION_TARGET="$2"
      shift 2
      ;;
    --target=*)
      MIGRATION_TARGET="${1#--target=}"
      shift
      ;;
    *)
      RUNNER_ARGS+=("$1")
      shift
      ;;
  esac
done

case "$MIGRATION_TARGET" in
  prod)
    DEFAULT_DB_SECRET_NAME="zenos-database-url" # pragma: allowlist secret
    ;;
  staging)
    DEFAULT_DB_SECRET_NAME="zenos-staging-database-url" # pragma: allowlist secret
    ;;
  *)
    echo "Unknown MIGRATION_TARGET: $MIGRATION_TARGET"
    echo "Expected: prod or staging"
    exit 1
    ;;
esac

DB_SECRET_NAME="${DB_SECRET_NAME:-$DEFAULT_DB_SECRET_NAME}"

if [ -z "$PYTHON_BIN" ]; then
  for candidate in \
    "$ROOT_DIR/.venv/bin/python3.13" \
    "$ROOT_DIR/.venv/bin/python3.14" \
    "$ROOT_DIR/.venv/bin/python3" \
    "$ROOT_DIR/.venv/bin/python" \
    "$(command -v python3 2>/dev/null || true)" \
    "$(command -v python 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  echo "python not found."
  echo "Set PYTHON_BIN or create venv first."
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  if ! command -v gcloud >/dev/null 2>&1; then
    echo "gcloud is required when DATABASE_URL is not set"
    exit 1
  fi
  export DATABASE_URL="$(gcloud secrets versions access latest \
    --secret="$DB_SECRET_NAME" \
    --project="$PROJECT_ID")"
fi

if [ -n "$DB_PROXY_PORT" ]; then
  export DATABASE_URL="$(printf '%s' "$DATABASE_URL" | sed -E "s#@(localhost|127\\.0\\.0\\.1):5432/#@127.0.0.1:${DB_PROXY_PORT}/#")"
fi

echo "Migration target: $MIGRATION_TARGET (secret: $DB_SECRET_NAME)"
exec "$PYTHON_BIN" "$ROOT_DIR/scripts/run_sql_migrations.py" "${RUNNER_ARGS[@]}"
