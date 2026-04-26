#!/usr/bin/env bash
set -euo pipefail

# ZenOS MCP Server Deploy Script
# Deploys the Cloud Run MCP server from the repo root Dockerfile.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SERVICE_NAME="${SERVICE_NAME:-zenos-mcp}"
REGION="${REGION:-asia-east1}"
PROJECT_ID="${PROJECT_ID:-zenos-naruvia}"
SOURCE_DIR="${SOURCE_DIR:-$ROOT_DIR}"
MCP_TRANSPORT="${MCP_TRANSPORT:-dual}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-zentropy-4f7a5:asia-east1:zentropy-db}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-165893875709-compute@developer.gserviceaccount.com}"

echo "=== ZenOS MCP Deploy ==="
echo ""

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud is required but was not found in PATH."
  exit 1
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [ -z "$ACTIVE_ACCOUNT" ]; then
  echo "No active gcloud account found. Run 'gcloud auth login' first."
  exit 1
fi

echo "[1/3] Deploying Cloud Run service..."
echo "  service: $SERVICE_NAME"
echo "  region:  $REGION"
echo "  project: $PROJECT_ID"
echo "  source:  $SOURCE_DIR"
echo "  account: $ACTIVE_ACCOUNT"
echo ""

cd "$ROOT_DIR"
DEPLOY_CMD=(
  run deploy "$SERVICE_NAME"
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --platform=managed \
  --source="$SOURCE_DIR" \
  --service-account="$SERVICE_ACCOUNT" \
  --max-instances="$MAX_INSTANCES" \
  --add-cloudsql-instances="$CLOUDSQL_INSTANCE" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,MCP_TRANSPORT=$MCP_TRANSPORT,GOOGLE_SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT,ZENOS_L3_READ_NEW_PATH=1,ZENOS_L3_WRITE_NEW_PATH=1" \
  --update-secrets="DATABASE_URL=database-url:latest,GITHUB_TOKEN=github-token:latest,ZENOS_JWT_SECRET=zenos-jwt-secret:latest,GEMINI_API_KEY=gemini-api-key:latest" # pragma: allowlist secret
)

if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
  DEPLOY_CMD+=(--allow-unauthenticated)
fi

gcloud "${DEPLOY_CMD[@]}"

echo ""
echo "[2/3] Verifying Cloud Run traffic..."
TARGET_REVISION="$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='value(status.latestCreatedRevisionName)')"

if [ -z "$TARGET_REVISION" ]; then
  TARGET_REVISION="$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format='value(status.latestReadyRevisionName)')"
fi

if [ -z "$TARGET_REVISION" ]; then
  echo "Unable to resolve latest Cloud Run revision."
  exit 1
fi

echo "  target revision: $TARGET_REVISION"

_service_traffic_json() {
  gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format='json(status.traffic)'
}

_parse_service_traffic() {
  local mode="$1"
  local expected_revision="${2:-}"
  _service_traffic_json | TRAFFIC_PARSE_MODE="$mode" TARGET_TRAFFIC_REVISION="$expected_revision" python3 -c '
import json
import os
import sys


def traffic_entries(payload):
    if isinstance(payload, dict):
        traffic = payload.get("traffic")
        if isinstance(traffic, list):
            return traffic
        status = payload.get("status")
        if isinstance(status, dict):
            traffic = status.get("traffic")
            if isinstance(traffic, list):
                return traffic
        return []
    if isinstance(payload, list):
        if all(isinstance(item, dict) and ("revisionName" in item or "percent" in item or "tag" in item) for item in payload):
            return payload
        entries = []
        for item in payload:
            entries.extend(traffic_entries(item))
        return entries
    return []


mode = os.environ["TRAFFIC_PARSE_MODE"]
expected_revision = os.environ.get("TARGET_TRAFFIC_REVISION", "")
payload = json.load(sys.stdin)
for entry in traffic_entries(payload):
    if mode == "rows":
        revision = entry.get("revisionName", "")
        percent = entry.get("percent", "")
        tag = entry.get("tag", "")
        print(f"{revision} {percent} {tag}")
        continue

    if mode == "has_100":
        if entry.get("revisionName") != expected_revision:
            continue
        try:
            percent = int(entry.get("percent", 0))
        except (TypeError, ValueError):
            percent = -1
        if percent == 100:
            sys.exit(0)

if mode == "has_100":
    sys.exit(1)

if mode != "rows":
    raise SystemExit(f"unknown traffic parse mode: {mode}")
'
}

_service_traffic_rows() {
  _parse_service_traffic rows
}

_print_service_traffic() {
  echo "  traffic:"
  _service_traffic_rows | sed 's/^/    /'
}

_revision_has_100_percent_traffic() {
  local expected_revision="$1"
  _parse_service_traffic has_100 "$expected_revision"
}

_print_service_traffic

if ! _revision_has_100_percent_traffic "$TARGET_REVISION"; then
  echo "  updating traffic to route 100% to $TARGET_REVISION..."
  gcloud run services update-traffic "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --to-revisions="${TARGET_REVISION}=100"
fi

echo "  validating serving revision..."
_print_service_traffic

if ! _revision_has_100_percent_traffic "$TARGET_REVISION"; then
  echo "Traffic validation failed: $TARGET_REVISION is not serving 100% traffic."
  exit 1
fi

echo "  serving revision: $TARGET_REVISION"
echo ""

echo "[3/4] Resolving service URL..."
SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='value(status.url)')"

if [ -z "$SERVICE_URL" ]; then
  echo "Unable to resolve Cloud Run service URL."
  exit 1
fi

echo "  service URL: $SERVICE_URL"
echo ""

echo "[4/4] Deploy complete"
echo "  serving revision: $TARGET_REVISION"
echo "  SSE endpoint: $SERVICE_URL/sse?api_key=YOUR_API_KEY"
echo "  Streamable HTTP endpoint: $SERVICE_URL/mcp?api_key=YOUR_API_KEY"
echo ""
echo "=== Deploy complete ==="
