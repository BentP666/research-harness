#!/usr/bin/env bash
# Load Research Harness personal secrets from macOS Keychain.
#
# This file is safe to commit: it contains only lookup logic, not secrets.
# Store/update values with:
#   scripts/rh-keychain-set.sh
#
# Source it from direnv or a shell before running RH:
#   source scripts/rh-env-keychain.sh

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "rh-env-keychain.sh must be sourced, not executed." >&2
  exit 2
fi

_rh_keychain_get() {
  local name="$1"
  local keychain="${RH_KEYCHAIN_PATH:-${HOME}/Library/Keychains/login.keychain-db}"

  if ! command -v /usr/bin/security >/dev/null 2>&1; then
    return 1
  fi

  /usr/bin/security find-generic-password \
    -a "${USER:-$(id -un)}" \
    -s "research-harness:${name}" \
    -w "$keychain" 2>/dev/null || true
}

_rh_export_secret() {
  local name="$1"
  local value

  value="$(_rh_keychain_get "$name")"
  if [[ -n "$value" ]]; then
    export "${name}=${value}"
  fi
}

_rh_export_secret S2_API_KEY

# RH supports both names; keep the legacy alias populated from the canonical key.
if [[ -n "${S2_API_KEY:-}" && -z "${SEMANTIC_SCHOLAR_API_KEY:-}" ]]; then
  export SEMANTIC_SCHOLAR_API_KEY="$S2_API_KEY"
fi

_rh_export_secret OPENALEX_API_KEY
_rh_export_secret FAL_KEY
_rh_export_secret ZOTERO_API_KEY
_rh_export_secret ZOTERO_LIBRARY_ID
_rh_export_secret ZOTERO_LIBRARY_TYPE

# OpenReview only needs an enable flag for the public conference mirrors.
export OPENREVIEW_ENABLE="${OPENREVIEW_ENABLE:-1}"

unset -f _rh_keychain_get
unset -f _rh_export_secret
