#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://zenos-naruvia.web.app/installers/claude-code-helper}"
INSTALL_DIR="${HOME}/.zenos/claude-code-helper"
SAFE_WORKSPACE="${HOME}/.zenos/claude-code-helper/workspace"

echo "Installing Claude Code helper to ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}"
mkdir -p "${SAFE_WORKSPACE}"

curl -fsSL "${BASE_URL}/server.mjs" -o "${INSTALL_DIR}/server.mjs"
curl -fsSL "${BASE_URL}/package.json" -o "${INSTALL_DIR}/package.json"

cat > "${INSTALL_DIR}/start-secure.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN:-}"
ZENOS_API_KEY="${ZENOS_API_KEY:-}"
ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://zenos-naruvia.web.app}"
SAFE_WORKSPACE="${SAFE_WORKSPACE:-$HOME/.zenos/claude-code-helper/workspace}"
if [[ -z "${LOCAL_HELPER_TOKEN}" ]]; then
  echo "ERROR: LOCAL_HELPER_TOKEN is required."
  echo "Example:"
  echo "  ZENOS_API_KEY=your_user_key LOCAL_HELPER_TOKEN=your_token ALLOWED_ORIGINS=https://zenos-naruvia.web.app ${INSTALL_DIR}/start-secure.sh"
  exit 1
fi
if [[ -z "${ZENOS_API_KEY}" ]]; then
  echo "ERROR: ZENOS_API_KEY is required."
  echo "Example:"
  echo "  ZENOS_API_KEY=your_user_key LOCAL_HELPER_TOKEN=your_token ALLOWED_ORIGINS=https://zenos-naruvia.web.app ${INSTALL_DIR}/start-secure.sh"
  exit 1
fi
mkdir -p "${SAFE_WORKSPACE}"
DEFAULT_CWD="${DEFAULT_CWD:-${SAFE_WORKSPACE}}"
ALLOWED_CWDS="${ALLOWED_CWDS:-${SAFE_WORKSPACE}}"
HELPER_TOOLS="${HELPER_TOOLS:-}"
PORT="${PORT:-4317}" \
ZENOS_API_KEY="${ZENOS_API_KEY}" \
LOCAL_HELPER_TOKEN="${LOCAL_HELPER_TOKEN}" \
ALLOWED_ORIGINS="${ALLOWED_ORIGINS}" \
DEFAULT_CWD="${DEFAULT_CWD}" \
ALLOWED_CWDS="${ALLOWED_CWDS}" \
HELPER_TOOLS="${HELPER_TOOLS}" \
node server.mjs
EOF
chmod +x "${INSTALL_DIR}/start-secure.sh"

cat <<EOF
✅ Installed.

Next:
1) Login Claude Code CLI (once):
   claude login

2) Start helper (secure mode, user key + token required):
   ZENOS_API_KEY=your_user_key LOCAL_HELPER_TOKEN=your_token ALLOWED_ORIGINS=https://zenos-naruvia.web.app ${INSTALL_DIR}/start-secure.sh

Security defaults:
- Bind host: 127.0.0.1
- Allowed origin: https://zenos-naruvia.web.app
- Allowed cwd: ${SAFE_WORKSPACE}
- Tools: disabled by default (text discussion only)
EOF
