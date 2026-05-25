#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT_DIR}/dist"
OUT_FILE="${OUT_DIR}/research-harness-zotero-panel.xpi"

mkdir -p "${OUT_DIR}"
rm -f "${OUT_FILE}"

cd "${ROOT_DIR}"

for icon in content/icons/rh-icon-16.png content/icons/rh-icon-20.png content/icons/rh-icon-32.png content/icons/rh-icon-48.png content/icons/rh-icon-96.png; do
  if [[ ! -s "${icon}" ]]; then
    echo "Missing required icon asset: ${icon}" >&2
    exit 1
  fi
done

zip -qr "${OUT_FILE}" \
  manifest.json \
  bootstrap.js \
  prefs.js \
  content \
  locale

echo "${OUT_FILE}"
