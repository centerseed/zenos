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
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,MCP_TRANSPORT=$MCP_TRANSPORT"
)

if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
  DEPLOY_CMD+=(--allow-unauthenticated)
fi

gcloud "${DEPLOY_CMD[@]}"

echo ""
echo "[2/3] Resolving service URL..."
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

echo "[3/3] Deploy complete"
echo "  SSE endpoint: $SERVICE_URL/sse?api_key=YOUR_API_KEY"
echo "  Streamable HTTP endpoint: $SERVICE_URL/mcp?api_key=YOUR_API_KEY"
echo ""
echo "=== Deploy complete ==="
