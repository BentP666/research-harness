#!/usr/bin/env bash
# Store/update Research Harness personal secrets in macOS Keychain.
# Values are read with terminal echo disabled and are never printed.

set -euo pipefail

KEYCHAIN_PATH="${RH_KEYCHAIN_PATH:-${HOME}/Library/Keychains/login.keychain-db}"
ACCOUNT="${USER:-$(id -un)}"

store_secret() {
  local name="$1"
  local label="$2"
  local comment="$3"
  local value

  read -r -s -p "${name} (leave blank to skip): " value
  printf "\n"

  if [[ -z "$value" ]]; then
    echo "${name}: skipped"
    return 0
  fi

  /usr/bin/security add-generic-password -U \
    -a "$ACCOUNT" \
    -s "research-harness:${name}" \
    -l "$label" \
    -j "$comment" \
    -w "$value" \
    "$KEYCHAIN_PATH" >/dev/null

  echo "${name}: stored"
}

if ! command -v /usr/bin/security >/dev/null 2>&1; then
  echo "macOS security CLI not found; Keychain storage is unavailable." >&2
  exit 1
fi

store_secret \
  S2_API_KEY \
  "Research Harness S2_API_KEY" \
  "Semantic Scholar API key for Research Harness"

store_secret \
  OPENALEX_API_KEY \
  "Research Harness OPENALEX_API_KEY" \
  "OpenAlex polite-pool key for Research Harness"

store_secret \
  FAL_KEY \
  "Research Harness FAL_KEY" \
  "fal.ai figure generation key for Research Harness"
