from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from research_harness.eval.researchflowbench import validate_pilot20_task_pack
from research_harness.eval.researchflowbench.cost import (
    make_cost_latency_stub,
    validate_cost_latency_trace,
)
from research_harness.eval.researchflowbench.leakage import validate_leakage_audit
from research_harness.eval.researchflowbench.preflight import (
    validate_allowed_tools_preflight,
)
from research_harness.eval.researchflowbench.retrieval import (
    make_retrieval_provenance_rehearsal,
    validate_retrieval_provenance,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT20_ROOT = REPO_ROOT / ".research-harness/reports/researchflowbench_pilot20_v0"
FROZEN_PILOT5_PATHS = (
    ".research-harness/reports/researchflowbench_pilot5_v0/manifest.json",
    ".research-harness/reports/researchflowbench_pilot5_v0/runs/model_actual_cursor_full5_clean_20260520/",
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


def _task_dir(root: Path, task_prefix: str) -> Path:
    return next((root / "tasks").glob(f"{task_prefix}_*"))


def _failures(report: dict) -> set[str]:
    return set(report.get("failures") or [])


def test_valid_pilot20_allowed_tools_preflight_passes():
    report = validate_allowed_tools_preflight(_task_dir(PILOT20_ROOT, "T01"))

    assert report["preflight_pass"], report
    assert report["declared_allowed_tools"] == ["local_static_corpus"]
    assert report["runner_exposed_tools"] == ["local_static_corpus"]
    assert report["fixture_hashes"]["local_static_corpus"]


def test_undeclared_runner_tool_fails_preflight():
    report = validate_allowed_tools_preflight(
        _task_dir(PILOT20_ROOT, "T01"),
        runner_exposed_tools=["local_static_corpus", "external_search"],
    )

    assert not report["preflight_pass"]
    assert "runner_exposes_undeclared_tool" in _failures(report)


def test_missing_local_static_corpus_fixture_fails_preflight(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_dir = _task_dir(root, "T01")
    (task_dir / "tool_fixtures/local_static_corpus.jsonl").unlink()

    report = validate_allowed_tools_preflight(task_dir)

    assert not report["preflight_pass"]
    assert "local_static_corpus_fixture_missing" in _failures(report)


def test_visible_input_includes_gold_or_judge_path_fails_leakage(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_dir = _task_dir(root, "T01")
    visible_manifest_path = task_dir / "tool_fixtures/visible_input_manifest.json"
    visible_manifest = _load_json(visible_manifest_path)
    visible_manifest["visible_to_agent"] = [
        *visible_manifest["visible_to_agent"],
        "judge_bundle.json",
    ]
    _write_json(visible_manifest_path, visible_manifest)

    report = validate_leakage_audit(task_dir)

    assert not report["independent_audit_pass"]
    assert "hidden_path_visible" in _failures(report)


def test_gold_or_judge_hash_leaking_into_prompt_fails_leakage(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_dir = _task_dir(root, "T01")
    gold_hash = validate_leakage_audit(task_dir)["gold_bundle_hash"]
    prompt_path = task_dir / "prompt.md"
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8")
        + f"\nLeaked hidden hash: {gold_hash}\n",
        encoding="utf-8",
    )

    report = validate_leakage_audit(task_dir)

    assert not report["independent_audit_pass"]
    assert "gold_hash_leaked_into_visible_input" in _failures(report)


def test_t05_external_search_enabled_fails_preflight(tmp_path: Path):
    root = _copy_pack(tmp_path)
    task_dir = _task_dir(root, "T05")
    task_path = task_dir / "task.json"
    task = _load_json(task_path)
    task["allowed_tools"] = [*task["allowed_tools"], "external_search"]
    task["external_search_policy"] = "enabled_for_test"
    _write_json(task_path, task)

    report = validate_allowed_tools_preflight(task_dir)

    assert not report["preflight_pass"]
    assert "t05_external_search_enabled" in _failures(report)


def test_retrieval_sensitive_task_missing_retrieval_provenance_fails():
    report = validate_retrieval_provenance(_task_dir(PILOT20_ROOT, "T01"), trace=None)

    assert not report["retrieval_trace_complete"]
    assert "retrieval_provenance_missing" in _failures(report)


def test_incomplete_selected_rejected_candidate_trace_fails():
    trace = make_retrieval_provenance_rehearsal(_task_dir(PILOT20_ROOT, "T01"))
    trace.pop("selected_candidates")

    report = validate_retrieval_provenance(_task_dir(PILOT20_ROOT, "T01"), trace=trace)

    assert not report["retrieval_trace_complete"]
    assert "selected_candidates_missing" in _failures(report)


def test_cost_trace_silent_null_fails():
    trace = make_cost_latency_stub(
        task_id="rfb.test",
        baseline_id="B1.no_governance_workflow_agent",
        executor="codex_cli",
        provider="openai",
        model="gpt-5.4",
    )
    trace["token_usage"] = None
    trace["token_usage_unknown_reason"] = ""

    report = validate_cost_latency_trace(trace)

    assert not report["cost_trace_pass"]
    assert "token_usage_missing_without_reason" in _failures(report)


def test_cost_trace_explicit_unknown_reason_passes():
    trace = make_cost_latency_stub(
        task_id="rfb.test",
        baseline_id="B1.no_governance_workflow_agent",
        executor="codex_cli",
        provider="openai",
        model="gpt-5.4",
    )

    report = validate_cost_latency_trace(trace)

    assert report["cost_trace_pass"], report
    assert report["token_usage"] is None
    assert report["token_usage_unknown_reason"]


def test_new_runtime_validators_integrate_with_existing_pilot20_validator():
    deterministic_report = validate_pilot20_task_pack(PILOT20_ROOT)
    preflight_report = validate_allowed_tools_preflight(_task_dir(PILOT20_ROOT, "T01"))
    leakage_report = validate_leakage_audit(_task_dir(PILOT20_ROOT, "T01"))
    retrieval_trace = make_retrieval_provenance_rehearsal(
        _task_dir(PILOT20_ROOT, "T01")
    )
    retrieval_report = validate_retrieval_provenance(
        _task_dir(PILOT20_ROOT, "T01"), trace=retrieval_trace
    )

    assert deterministic_report.is_valid, deterministic_report.to_dict()
    assert preflight_report["preflight_pass"], preflight_report
    assert leakage_report["independent_audit_pass"], leakage_report
    assert retrieval_report["retrieval_trace_complete"], retrieval_report


def test_pilot5_frozen_files_remain_unmodified():
    result = subprocess.run(
        ["git", "status", "--short", "--", *FROZEN_PILOT5_PATHS],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout == ""
