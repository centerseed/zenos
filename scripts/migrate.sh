#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ID="${PROJECT_ID:-zenos-naruvia}"
DB_SECRET_NAME="${DB_SECRET_NAME:-database-url}"
DB_PROXY_PORT="${DB_PROXY_PORT:-}"
PYTHON_BIN="${PYTHON_BIN:-}"

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

exec "$PYTHON_BIN" "$ROOT_DIR/scripts/run_sql_migrations.py" "$@"
