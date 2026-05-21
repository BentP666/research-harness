"""Leakage-audit validator for ResearchFlowBench visible/hidden splits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._runtime_common import load_json, sha256_file, visible_manifest_path

HIDDEN_BUNDLE_PATHS = frozenset({"gold_bundle.json", "judge_bundle.json"})
HIDDEN_FIELD_SENTINELS = frozenset(
    {
        "gold_evidence",
        "outcome_oracle",
        "process_oracle",
        "deterministic_prechecks",
        "task_specific_checks",
        "hard_gates",
        "llm_rubric_status",
    }
)


def validate_leakage_audit(
    task_dir: str | Path,
    *,
    baseline_id: str = "schema_dry_run",
    run_id: str = "schema_dry_run",
) -> dict[str, Any]:
    """Independently scan visible task inputs for hidden gold/judge leaks."""

    task_path = Path(task_dir)
    task = load_json(task_path / "task.json")
    contract = load_json(task_path / "tool_fixtures/allowed_tools_contract.json")
    visible_manifest = load_json(visible_manifest_path(task_path))
    gold_bundle_path = task_path / "gold_bundle.json"
    judge_bundle_path = task_path / "judge_bundle.json"
    gold_hash = sha256_file(gold_bundle_path)
    judge_hash = sha256_file(judge_bundle_path)
    prompt_hash = sha256_file(task_path / "prompt.md")
    input_hash = sha256_file(task_path / "input_bundle.json")

    visible_allowlist = [
        str(item) for item in visible_manifest.get("visible_to_agent", [])
    ]
    hidden_denylist = [
        str(item) for item in visible_manifest.get("judge_only_hidden", [])
    ]
    visible_set = set(visible_allowlist)
    hidden_set = set(hidden_denylist)
    prompt_text = (task_path / "prompt.md").read_text(encoding="utf-8")
    input_text = (task_path / "input_bundle.json").read_text(encoding="utf-8")
    visible_text = f"{prompt_text}\n{input_text}"
    canaries = _extract_canaries(gold_bundle_path, judge_bundle_path)

    failures: list[str] = []
    if visible_set & hidden_set or visible_set & set(HIDDEN_BUNDLE_PATHS):
        failures.append("hidden_path_visible")
    if not set(HIDDEN_BUNDLE_PATHS).issubset(hidden_set):
        failures.append("hidden_denylist_incomplete")
    if any(hidden_path in visible_text for hidden_path in HIDDEN_BUNDLE_PATHS):
        failures.append("hidden_path_leaked_into_visible_input")
    if any(sentinel in visible_text for sentinel in HIDDEN_FIELD_SENTINELS):
        failures.append("hidden_field_leaked_into_visible_input")
    gold_hash_absent = gold_hash not in visible_text
    judge_hash_absent = judge_hash not in visible_text
    if not gold_hash_absent:
        failures.append("gold_hash_leaked_into_visible_input")
    if not judge_hash_absent:
        failures.append("judge_hash_leaked_into_visible_input")
    leaked_canaries = sorted(
        canary for canary in canaries if canary and canary in visible_text
    )
    if leaked_canaries:
        failures.append("canary_leaked_into_visible_input")
    if contract.get("gold_visible") is not False:
        failures.append("self_reported_gold_visibility_not_false")
    if contract.get("judge_visible") is not False:
        failures.append("self_reported_judge_visibility_not_false")

    return {
        "schema_version": "researchflowbench.leakage_audit.v0.1",
        "run_id": run_id,
        "task_id": str(task.get("task_id") or ""),
        "baseline_id": baseline_id,
        "prompt_used_hash": prompt_hash,
        "input_bundle_hash": input_hash,
        "gold_bundle_hash": gold_hash,
        "judge_bundle_hash": judge_hash,
        "visible_file_allowlist": visible_allowlist,
        "hidden_file_denylist": hidden_denylist,
        "canary_strings_checked": canaries,
        "gold_hash_absent_from_prompt": gold_hash_absent,
        "judge_hash_absent_from_prompt": judge_hash_absent,
        "runtime_visibility_log": {
            "visible_files_scanned": ["prompt.md", "input_bundle.json"],
            "hidden_paths_visible": sorted(
                visible_set & (hidden_set | set(HIDDEN_BUNDLE_PATHS))
            ),
            "leaked_canaries": leaked_canaries,
        },
        "self_reported_gold_visible": contract.get("gold_visible"),
        "self_reported_judge_visible": contract.get("judge_visible"),
        "independent_audit_pass": not failures,
        "failures": sorted(set(failures)),
    }


def _extract_canaries(*paths: Path) -> list[str]:
    canaries: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for key in ("canary", "canary_string", "canary_strings", "leakage_canaries"):
            value = payload.get(key)
            if isinstance(value, str):
                canaries.add(value)
            elif isinstance(value, list):
                canaries.update(str(item) for item in value if item)
    return sorted(canaries)
