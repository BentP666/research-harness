#!/usr/bin/env bash
# Standard Codex verification entrypoint for Research Harness.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/codex-check.sh [--quick|--full|--python|--web|--mcp]

Modes:
  --quick   Validate Codex/RH workflow metadata only (default).
  --full    Run quick checks plus Python, web, and MCP smoke checks.
  --python  Run Python package tests when pytest is available.
  --web     Run web lint/tests when npm dependencies are available.
  --mcp     Run lightweight Research Harness MCP wrapper checks.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${RESEARCH_HARNESS_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

MODE="${1:---quick}"
case "$MODE" in
  --quick|--full|--python|--web|--mcp) ;;
  -h|--help) usage; exit 0 ;;
  *) echo "Unknown mode: $MODE" >&2; usage >&2; exit 2 ;;
esac

run_step() {
  local name="$1"
  shift
  printf '\n==> %s\n' "$name"
  "$@"
}

run_quick() {
  run_step "Codex/RH workflow metadata" "$PYTHON_BIN" scripts/codex_skill_manifest_check.py
}

run_python() {
  if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import pytest  # noqa: F401
PY
  then
    echo "SKIP: pytest is not importable in this Python environment" >&2
    return 0
  fi

  run_step "Python smoke tests" \
    "$PYTHON_BIN" -m pytest packages/research_harness/tests/test_db.py \
      packages/research_harness_mcp/tests/test_routes.py \
      -q --tb=short
}

run_web() {
  if [[ ! -d web/node_modules ]]; then
    echo "SKIP: web/node_modules is missing; run npm install in web/ first" >&2
    return 0
  fi

  run_step "Web lint" npm --prefix web run lint
  run_step "Web tests" npm --prefix web run test
}

run_mcp() {
  if [[ ! -x scripts/rh-mcp-keychain.sh ]]; then
    echo "FAIL: scripts/rh-mcp-keychain.sh is missing or not executable" >&2
    return 1
  fi

  run_step "Research Harness MCP import smoke" \
    "$PYTHON_BIN" - <<'PY'
import importlib.util
import sys

if importlib.util.find_spec("research_harness_mcp") is None:
    print("SKIP: research_harness_mcp is not importable in this Python environment", file=sys.stderr)
    raise SystemExit(0)

print("research_harness_mcp importable")
PY
}

case "$MODE" in
  --quick)
    run_quick
    ;;
  --python)
    run_quick
    run_python
    ;;
  --web)
    run_quick
    run_web
    ;;
  --mcp)
    run_quick
    run_mcp
    ;;
  --full)
    run_quick
    run_python
    run_web
    run_mcp
    ;;
esac

printf '\nCodex check completed: %s\n' "$MODE"
