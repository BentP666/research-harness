#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT_DIR}/dist"
OUT_FILE="${OUT_DIR}/research-harness-zotero-panel.xpi"
UPDATE_FILE="${OUT_DIR}/research-harness-zotero-update.json"

mkdir -p "${OUT_DIR}"
rm -f "${OUT_FILE}" "${UPDATE_FILE}"

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

python3 - "${OUT_FILE}" "${UPDATE_FILE}" <<'INNER_PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

xpi_path = Path(sys.argv[1])
update_path = Path(sys.argv[2])
manifest = json.loads(Path("manifest.json").read_text(encoding="utf-8"))
zotero = manifest["applications"]["zotero"]
version = manifest["version"]
base_url = f"https://github.com/Biajin-PKU/research-harness/releases/download/v{version}"
update_manifest = {
    "addons": {
        zotero["id"]: {
            "updates": [
                {
                    "version": version,
                    "update_link": f"{base_url}/{xpi_path.name}",
                    "applications": {
                        "zotero": {
                            "strict_min_version": zotero["strict_min_version"],
                            "strict_max_version": zotero["strict_max_version"],
                        }
                    },
                }
            ]
        }
    }
}
update_path.write_text(json.dumps(update_manifest, indent=2) + "\n", encoding="utf-8")
INNER_PY

echo "${OUT_FILE}"
echo "${UPDATE_FILE}"
