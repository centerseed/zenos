#!/usr/bin/env bash
set -euo pipefail

# ZenOS Deploy Script
# Runs tests → build → deploy (hosting + firestore rules)
# Any step fails = abort, no partial deploy.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$ROOT_DIR/dashboard"
PROJECT_ID="zenos-naruvia"
HOSTING_URL="https://zenos-naruvia.web.app"
HOSTING_TARGET="app"
SKIP_TESTS=false
VENV_PYTHON=""

export NEXT_PUBLIC_FIREBASE_API_KEY="${NEXT_PUBLIC_FIREBASE_API_KEY:-AIzaSyDjAsF7t4nR34RuouBDcMOnYi6kIjVDxRA}"
export NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="${NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN:-zenos-naruvia.firebaseapp.com}"
export NEXT_PUBLIC_FIREBASE_PROJECT_ID="${NEXT_PUBLIC_FIREBASE_PROJECT_ID:-zenos-naruvia}"
export NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="${NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET:-zenos-naruvia.firebasestorage.app}"
export NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="${NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID:-165893875709}"
export NEXT_PUBLIC_FIREBASE_APP_ID="${NEXT_PUBLIC_FIREBASE_APP_ID:-1:165893875709:web:e7f2c1836462d49a601b94}"

usage() {
  cat <<'EOF'
Usage: ./scripts/deploy.sh [--project <id>] [--hosting-url <url>] [--skip-tests]

Options:
  --project <id>       Firebase project ID. Default: zenos-naruvia
  --hosting-url <url>  Hosting base URL for post-deploy verification.
  --skip-tests         Skip Python tests, dashboard tests, and lint. Build still runs.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --project" >&2
        usage
        exit 1
      fi
      PROJECT_ID="$2"
      shift 2
      ;;
    --hosting-url)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --hosting-url" >&2
        usage
        exit 1
      fi
      HOSTING_URL="$2"
      shift 2
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ "$SKIP_TESTS" = false ]; then
  if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
  elif [ -x "$ROOT_DIR/.venv/bin/python3" ]; then
    VENV_PYTHON="$ROOT_DIR/.venv/bin/python3"
  else
    echo "Python venv not found under .venv/bin/. Expected python or python3." >&2
    exit 1
  fi
fi

if command -v firebase >/dev/null 2>&1; then
  FIREBASE_CLI="firebase"
elif [ -x "$DASHBOARD_DIR/node_modules/.bin/firebase" ]; then
  FIREBASE_CLI="$DASHBOARD_DIR/node_modules/.bin/firebase"
else
  echo "Firebase CLI not found. Install it globally or run npm install in dashboard/." >&2
  exit 1
fi

echo "=== ZenOS Deploy ==="
echo ""
echo "Project: $PROJECT_ID"
echo "Hosting URL: $HOSTING_URL"
if [ "$SKIP_TESTS" = true ]; then
  echo "Mode: skip tests/lint (fresh build still runs)"
fi
echo ""

echo "Firebase public config:"
echo "  projectId=$NEXT_PUBLIC_FIREBASE_PROJECT_ID"
echo "  authDomain=$NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN"
echo "  appId=$NEXT_PUBLIC_FIREBASE_APP_ID"
echo ""

# Step 1: Python tests
if [ "$SKIP_TESTS" = true ]; then
  echo "[1/5] Skipping Python tests (--skip-tests)"
else
  echo "[1/5] Running Python tests..."
  cd "$ROOT_DIR" && GITHUB_TOKEN="${GITHUB_TOKEN:-test-dummy}" "$VENV_PYTHON" -m pytest tests/ -v --tb=short --ignore=tests/integration --ignore=tests/scripts/test_fix_entity_partner_ids.py
  echo "  ✓ Python tests passed"
fi
echo ""

# Step 2: Dashboard tests
if [ "$SKIP_TESTS" = true ]; then
  echo "[2/5] Skipping Dashboard tests (--skip-tests)"
else
  echo "[2/5] Running Dashboard tests..."
  cd "$DASHBOARD_DIR"
  npm test
  echo "  ✓ Dashboard tests passed"
fi
echo ""

# Step 3: Dashboard lint (TypeScript type check)
if [ "$SKIP_TESTS" = true ]; then
  echo "[3/5] Skipping TypeScript type check (--skip-tests)"
else
  echo "[3/5] Running TypeScript type check..."
  cd "$DASHBOARD_DIR"
  npm run lint
  echo "  ✓ Type check passed"
fi
echo ""

# Step 4: Dashboard build
echo "[4/5] Building Dashboard..."
cd "$DASHBOARD_DIR"
rm -rf out
if [ -x "$DASHBOARD_DIR/node_modules/.bin/next" ]; then
  "$DASHBOARD_DIR/node_modules/.bin/next" build
else
  npm run build
fi
echo "  ✓ Build succeeded"
echo ""

# Step 5: Deploy
echo "[5/5] Deploying to Firebase (hosting + firestore rules)..."
cd "$ROOT_DIR"
"$FIREBASE_CLI" deploy --only "hosting:${HOSTING_TARGET},firestore" --project "$PROJECT_ID"
echo "  ✓ Deploy completed"
echo ""

# Post-deploy verification
echo "=== Post-deploy verification ==="
for path in / /tasks /knowledge-map /projects
do
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HOSTING_URL}${path}")
  if [ "$HTTP_STATUS" = "200" ]; then
    echo "  ✓ ${HOSTING_URL}${path} is accessible (HTTP $HTTP_STATUS)"
  else
    echo "  ✗ ${HOSTING_URL}${path} returned HTTP $HTTP_STATUS — check deployment!"
    exit 1
  fi
done

echo ""
echo "=== Deploy complete ==="
