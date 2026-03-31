#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ID="${PROJECT_ID:-zenos-naruvia}"
DB_SECRET_NAME="${DB_SECRET_NAME:-database-url}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python3.13}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "python not found: $PYTHON_BIN"
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

exec "$PYTHON_BIN" "$ROOT_DIR/scripts/run_sql_migrations.py" "$@"
