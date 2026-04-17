#!/usr/bin/env bash
set -euo pipefail

# E2E test for cowork helper
# Tests: bootstrap -> health -> SSE streaming -> MCP tool access

HELPER_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE=$(mktemp -d)
TOKEN="test-$(date +%s)"

echo "[1/4] Starting helper with bootstrap..."
ZENOS_API_KEY="${ZENOS_API_KEY:?ZENOS_API_KEY is required}" \
ALLOWED_ORIGINS="http://localhost:3000" \
ALLOWED_CWDS="$WORKSPACE" \
LOCAL_HELPER_TOKEN="$TOKEN" \
PORT=4399 \
node "$HELPER_DIR/server.mjs" &
HELPER_PID=$!

cleanup() {
  kill "$HELPER_PID" 2>/dev/null || true
  rm -rf "$WORKSPACE"
}
trap cleanup EXIT

# Wait for helper to be ready
MAX_WAIT=10
WAITED=0
until curl -sf -H "Origin: http://localhost:3000" -H "X-Local-Helper-Token: $TOKEN" "http://127.0.0.1:4399/health" >/dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "FAIL: helper did not start within ${MAX_WAIT}s"
    exit 1
  fi
  sleep 1
  WAITED=$((WAITED + 1))
done
echo "  helper started after ${WAITED}s"

echo "[2/4] Checking health..."
HEALTH=$(curl -sf \
  -H "Origin: http://localhost:3000" \
  -H "X-Local-Helper-Token: $TOKEN" \
  "http://127.0.0.1:4399/health")
MCP_OK=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin)['capability']['mcp_ok'])")
TOOLS=$(echo "$HEALTH" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['capability'].get('allowed_tools', [])))")
echo "  mcp_ok=$MCP_OK allowed_tools=$TOOLS"
[ "$MCP_OK" = "True" ] || { echo "FAIL: mcp_ok is not True"; exit 1; }
[ "$TOOLS" -gt 0 ] || { echo "FAIL: no allowed tools"; exit 1; }

echo "[3/4] Checking bootstrap files..."
[ -f "$WORKSPACE/.claude/mcp.json" ] || { echo "FAIL: mcp.json not created"; exit 1; }
[ -f "$WORKSPACE/.claude/settings.local.json" ] || { echo "FAIL: settings.local.json not created"; exit 1; }
echo "  bootstrap files exist"

echo "[4/4] Testing SSE stream (simple prompt)..."
RESULT=$(curl -sf -N \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:3000" \
  -H "X-Local-Helper-Token: $TOKEN" \
  -X POST "http://127.0.0.1:4399/v1/chat/start" \
  -d "{\"conversationId\":\"e2e-test\",\"prompt\":\"reply with OK\",\"maxTurns\":1}" \
  2>&1 | timeout 30 grep -c "content_block_delta" || echo "0")
echo "  content_block_delta events: $RESULT"
[ "$RESULT" -gt 0 ] || { echo "FAIL: no streaming deltas received"; exit 1; }

echo ""
echo "=== ALL TESTS PASSED ==="
