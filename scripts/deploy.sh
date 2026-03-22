#!/usr/bin/env bash
set -euo pipefail

# ZenOS Deploy Script
# Runs tests → build → deploy (hosting + firestore rules)
# Any step fails = abort, no partial deploy.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$ROOT_DIR/dashboard"
HOSTING_URL="https://zenos-naruvia.web.app"

echo "=== ZenOS Deploy ==="
echo ""

# Step 1: Python tests
echo "[1/5] Running Python tests..."
cd "$ROOT_DIR"
GITHUB_TOKEN="${GITHUB_TOKEN:-test-dummy}" python3.11 -m pytest tests/ -v --tb=short
echo "  ✓ Python tests passed"
echo ""

# Step 2: Dashboard tests
echo "[2/5] Running Dashboard tests..."
cd "$DASHBOARD_DIR"
npm test
echo "  ✓ Dashboard tests passed"
echo ""

# Step 3: Dashboard lint (TypeScript type check)
echo "[3/5] Running TypeScript type check..."
npm run lint
echo "  ✓ Type check passed"
echo ""

# Step 4: Dashboard build
echo "[4/5] Building Dashboard..."
npm run build
echo "  ✓ Build succeeded"
echo ""

# Step 5: Deploy
echo "[5/5] Deploying to Firebase (hosting + firestore rules)..."
cd "$ROOT_DIR"
firebase deploy --only hosting,firestore
echo "  ✓ Deploy completed"
echo ""

# Post-deploy verification
echo "=== Post-deploy verification ==="
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HOSTING_URL")
if [ "$HTTP_STATUS" = "200" ]; then
  echo "  ✓ $HOSTING_URL is accessible (HTTP $HTTP_STATUS)"
else
  echo "  ✗ $HOSTING_URL returned HTTP $HTTP_STATUS — check deployment!"
  exit 1
fi

echo ""
echo "=== Deploy complete ==="
