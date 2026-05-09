#!/usr/bin/env bash
# Launch the Research Harness MCP server with personal secrets loaded from
# macOS Keychain. This avoids writing API keys into ~/.codex/config.toml.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=scripts/rh-env-keychain.sh
source "$SCRIPT_DIR/rh-env-keychain.sh"

PYTHON_BIN="${RESEARCH_HARNESS_PYTHON:-python3}"

exec "$PYTHON_BIN" -m research_harness_mcp "$@"
