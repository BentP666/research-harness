from __future__ import annotations

import json
import shutil
from pathlib import Path

from research_harness.eval.researchflowbench import validate_pilot20_task_pack

PILOT20_ROOT = (
    Path(__file__).resolve().parent
    / "fixtures/researchflowbench/pilot20_v0_synthetic_task_pack"
)


def _copy_pack(tmp_path: Path) -> Path:
    target = tmp_path / "researchflowbench_pilot20_v0"
    shutil.copytree(PILOT20_ROOT, target)
    return target


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_current_pilot20_task_pack_satisfies_deterministic_contracts():
    report = validate_pilot20_task_pack(PILOT20_ROOT)

    assert report.is_valid, report.to_dict()
    assert report.checked_task_count == 5
    assert report.checked_file_count >= 50


def test_visible_manifest_rejects_gold_and_judge_visibility_leaks(tmp_path: Path):
    root = _copy_pack(tmp_path)
    manifest_path = (
        root
        / "tasks/T01_full_context_citation_eval/tool_fixtures/visible_input_manifest.json"
    )
    manifest = _load_json(manifest_path)
    manifest["visible_to_agent"] = [*manifest["visible_to_agent"], "gold_bundle.json"]
    _write_json(manifest_path, manifest)

    report = validate_pilot20_task_pack(root)

    assert "visible_manifest_exposes_hidden_file" in _codes(report)


def test_visible_manifest_and_pack_manifest_hashes_are_checked(tmp_path: Path):
    root = _copy_pack(tmp_path)
    prompt_path = root / "tasks/T01_full_context_citation_eval/prompt.md"
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8") + "\nHash mismatch sentinel.\n",
        encoding="utf-8",
    )

    report = validate_pilot20_task_pack(root)
    codes = _codes(report)

    assert "visible_file_hash_mismatch" in codes
    assert "manifest_file_hash_mismatch" in codes


def test_pilot20_contract_rejects_missing_gold_asset_reference(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_path = root / "tasks/T05_false_novelty_baseline_gap/task.json"
    task = _load_json(task_path)
    task["gold_asset_ids"] = [*task["gold_asset_ids"], "baseline.nonexistent_prior"]
    _write_json(task_path, task)

    report = validate_pilot20_task_pack(root)

    assert "task_gold_asset_missing" in _codes(report)


def test_pilot20_contract_rejects_missing_stage_required_semantic_object(
    tmp_path: Path,
):
    root = _copy_pack(tmp_path)
    task_path = root / "tasks/T04_evidence_stale_propagation/task.json"
    task = _load_json(task_path)
    task["expected_semantic_objects"] = [
        item for item in task["expected_semantic_objects"] if item != "rollback_event"
    ]
    _write_json(task_path, task)

    report = validate_pilot20_task_pack(root)

    assert "task_required_semantic_object_missing" in _codes(report)


def test_t05_v0_external_search_must_remain_disabled(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_path = root / "tasks/T05_false_novelty_baseline_gap/task.json"
    task = _load_json(task_path)
    task["external_search_policy"] = "allowed"
    task["allowed_tools"] = [*task["allowed_tools"], "external_search"]
    _write_json(task_path, task)

    report = validate_pilot20_task_pack(root)

    assert "t05_external_search_enabled" in _codes(report)
