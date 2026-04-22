#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://zenos-naruvia.web.app/installers/claude-code-helper}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.zenos/claude-code-helper}"
SAFE_WORKSPACE="${SAFE_WORKSPACE:-$HOME/.zenos/claude-code-helper/workspace}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://zenos-naruvia.web.app}"
LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN:-}"
ZENOS_API_KEY="${ZENOS_API_KEY:-}"
ZENOS_PROJECT="${ZENOS_PROJECT:-Paceriz}"
PORT="${PORT:-4317}"
LOG_CLAUDE_IO="${LOG_CLAUDE_IO:-1}"
AUTO_INSTALL_NODE="${AUTO_INSTALL_NODE:-1}"
AUTO_START="${AUTO_START:-0}"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: Missing required command: $cmd" >&2
    exit 1
  fi
}

generate_token() {
  python3 - <<'PY'
import secrets
print("mk-" + secrets.token_hex(12))
PY
}

ensure_node() {
  if command -v node >/dev/null 2>&1; then
    return
  fi
  if [[ "$AUTO_INSTALL_NODE" != "1" ]]; then
    echo "ERROR: Node.js is not installed." >&2
    exit 1
  fi
  if command -v brew >/dev/null 2>&1; then
    echo "Node.js not found. Installing via Homebrew..."
    brew install node
    return
  fi
  cat >&2 <<'EOF'
ERROR: Node.js is not installed, and Homebrew is not available for auto-install.
Install one of these first, then rerun:
  1. Homebrew: https://brew.sh
  2. Node.js LTS pkg: https://nodejs.org
EOF
  exit 1
}

ensure_claude() {
  if command -v claude >/dev/null 2>&1; then
    return
  fi
  cat >&2 <<'EOF'
ERROR: Claude Code CLI is not installed.
Install Claude Code CLI first, confirm `claude --version` works, then rerun this installer.
EOF
  exit 1
}

download_asset() {
  local name="$1"
  echo "Downloading ${name}..."
  curl -fsSL "${BASE_URL}/${name}" -o "${INSTALL_DIR}/${name}"
}

write_helper_env() {
  cat > "${INSTALL_DIR}/helper.env" <<EOF
ALLOWED_ORIGINS="${ALLOWED_ORIGINS}"
LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN}"
SAFE_WORKSPACE="${SAFE_WORKSPACE}"
PORT="${PORT}"
LOG_CLAUDE_IO="${LOG_CLAUDE_IO}"
ZENOS_PROJECT="${ZENOS_PROJECT}"
EOF
}

write_doctor_script() {
  cat > "${INSTALL_DIR}/doctor.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "Install dir: $(pwd)"
echo "Node: $(command -v node || echo missing)"
if command -v node >/dev/null 2>&1; then
  echo "Node version: $(node --version)"
fi
echo "Claude: $(command -v claude || echo missing)"
if command -v claude >/dev/null 2>&1; then
  echo "Claude version: $(claude --version)"
fi
echo "Files:"
for file in server.mjs package.json runtime-state.mjs helper.env start-secure.sh; do
  if [[ -f "$file" ]]; then
    echo "  ✓ $file"
  else
    echo "  ✗ $file"
  fi
done
EOF
  chmod +x "${INSTALL_DIR}/doctor.sh"
}

write_start_script() {
  cat > "${INSTALL_DIR}/start-secure.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f "./helper.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "./helper.env"
  set +a
fi

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js is not installed. Rerun the installer or install Node.js first." >&2
  exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: Claude Code CLI is not installed. Install it first." >&2
  exit 1
fi

LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN:-}"
ZENOS_API_KEY="${ZENOS_API_KEY:-}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://zenos-naruvia.web.app}"
SAFE_WORKSPACE="${SAFE_WORKSPACE:-$HOME/.zenos/claude-code-helper/workspace}"
PORT="${PORT:-4317}"
LOG_CLAUDE_IO="${LOG_CLAUDE_IO:-1}"
ZENOS_PROJECT="${ZENOS_PROJECT:-Paceriz}"

if [[ -z "${LOCAL_HELPER_TOKEN}" ]]; then
  echo "ERROR: LOCAL_HELPER_TOKEN is missing. Re-run the installer." >&2
  exit 1
fi

if [[ -z "${ZENOS_API_KEY}" ]]; then
  read -r -s -p "Enter ZENOS_API_KEY: " ZENOS_API_KEY
  echo
fi

if [[ -z "${ZENOS_API_KEY}" ]]; then
  echo "ERROR: ZENOS_API_KEY is required." >&2
  exit 1
fi

mkdir -p "${SAFE_WORKSPACE}"

echo "Starting Claude Code helper..."
echo "  URL: http://127.0.0.1:${PORT}"
echo "  Token: ${LOCAL_HELPER_TOKEN}"
echo "  Workspace: ${SAFE_WORKSPACE}"
echo "  Claude: $(claude --version)"

exec env \
  PORT="${PORT}" \
  ZENOS_API_KEY="${ZENOS_API_KEY}" \
  ZENOS_PROJECT="${ZENOS_PROJECT}" \
  LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN}" \
  ALLOWED_ORIGINS="${ALLOWED_ORIGINS}" \
  DEFAULT_CWD="${SAFE_WORKSPACE}" \
  ALLOWED_CWDS="${SAFE_WORKSPACE}" \
  LOG_CLAUDE_IO="${LOG_CLAUDE_IO}" \
  node server.mjs
EOF
  chmod +x "${INSTALL_DIR}/start-secure.sh"
}

require_cmd curl
require_cmd python3

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: This installer currently targets macOS only." >&2
  exit 1
fi

ensure_node
ensure_claude

if [[ -z "${LOCAL_HELPER_TOKEN}" ]]; then
  LOCAL_HELPER_TOKEN="$(generate_token)"
fi

echo "Installing Claude Code helper to ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}" "${SAFE_WORKSPACE}"

download_asset "server.mjs"
download_asset "package.json"
download_asset "runtime-state.mjs"
write_helper_env
write_doctor_script
write_start_script

cat <<EOF
✅ Installed.

Install dir:
  ${INSTALL_DIR}

Helper defaults:
  URL: http://127.0.0.1:${PORT}
  Token: ${LOCAL_HELPER_TOKEN}
  Workspace: ${SAFE_WORKSPACE}
  Allowed origins: ${ALLOWED_ORIGINS}

Quick checks:
  ${INSTALL_DIR}/doctor.sh

Start helper:
  ZENOS_API_KEY=your_user_key ${INSTALL_DIR}/start-secure.sh
EOF

if [[ "$AUTO_START" == "1" ]]; then
  if [[ -z "${ZENOS_API_KEY}" ]]; then
    echo ""
    echo "AUTO_START=1 was set but ZENOS_API_KEY is empty."
    echo "Run this next:"
    echo "  ZENOS_API_KEY=your_user_key ${INSTALL_DIR}/start-secure.sh"
    exit 0
  fi
  echo ""
  echo "AUTO_START=1 detected. Launching helper now..."
  exec env ZENOS_API_KEY="${ZENOS_API_KEY}" "${INSTALL_DIR}/start-secure.sh"
fi
