"""Retrieval-provenance validator for ResearchFlowBench runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._runtime_common import (
    RETRIEVAL_SENSITIVE_TASK_NOS,
    load_json,
    load_jsonl,
    local_corpus_path,
    sha256_file,
    sha256_json,
    task_no_from_task,
    visible_manifest_path,
)


def make_retrieval_provenance_rehearsal(
    task_dir: str | Path,
    *,
    baseline_id: str = "schema_dry_run",
) -> dict[str, Any]:
    """Create a model-free retrieval trace from the local static corpus."""

    task_path = Path(task_dir)
    task = load_json(task_path / "task.json")
    input_bundle = load_json(task_path / "input_bundle.json")
    records = load_jsonl(local_corpus_path(task_path))
    candidate_ids = [
        str(record.get("record_id") or "")
        for record in records
        if record.get("record_id")
    ]
    selected_candidates = [
        str(item) for item in input_bundle.get("visible_local_corpus_record_ids", [])
    ]
    rejected_candidates = [
        candidate_id
        for candidate_id in candidate_ids
        if candidate_id not in selected_candidates
    ]
    evidence_ids_used = [
        candidate_id
        for candidate_id in selected_candidates
        if candidate_id.startswith("evidence.")
    ]

    return {
        "schema_version": "researchflowbench.retrieval_provenance.v0.1",
        "task_id": str(task.get("task_id") or ""),
        "baseline_id": baseline_id,
        "corpus_snapshot_id": str(
            task.get("source_snapshot_id") or "pilot20_local_static_corpus_v0"
        ),
        "corpus_snapshot_hash": sha256_file(local_corpus_path(task_path)),
        "queries": [
            {
                "query_id": f"{task_no_from_task(task).lower()}.static_rehearsal",
                "mode": "local_static_corpus_fixture",
                "source": "input_bundle.visible_local_corpus_record_ids",
            }
        ],
        "declared_no_query_mode": False,
        "candidate_set": [
            {
                "candidate_id": candidate_id,
                "candidate_hash": sha256_json(record),
                "rank": index,
            }
            for index, (candidate_id, record) in enumerate(
                zip(candidate_ids, records, strict=True), 1
            )
        ],
        "candidate_ids": candidate_ids,
        "candidate_hashes": {
            str(record.get("record_id")): sha256_json(record) for record in records
        },
        "selected_candidates": selected_candidates,
        "rejected_candidates": rejected_candidates,
        "evidence_ids_used": evidence_ids_used,
        "retrieval_tool_calls": [
            {
                "tool_name": "local_static_corpus",
                "fixture_path": "tool_fixtures/local_static_corpus.jsonl",
                "call_mode": "static_rehearsal_no_model",
            }
        ],
        "retrieval_trace_complete": True,
        "failures": [],
    }


def validate_retrieval_provenance(
    task_dir: str | Path,
    *,
    trace: dict[str, Any] | None,
    baseline_id: str = "schema_dry_run",
) -> dict[str, Any]:
    """Validate retrieval trace completeness for retrieval-sensitive tasks."""

    task_path = Path(task_dir)
    task = load_json(task_path / "task.json")
    task_id = str(task.get("task_id") or "")
    sensitive = task_no_from_task(task) in RETRIEVAL_SENSITIVE_TASK_NOS
    if trace is None:
        failures = ["retrieval_provenance_missing"] if sensitive else []
        return {
            "schema_version": "researchflowbench.retrieval_provenance.v0.1",
            "task_id": task_id,
            "baseline_id": baseline_id,
            "status": "missing" if sensitive else "not_applicable",
            "retrieval_trace_complete": not failures,
            "failures": failures,
        }

    failures: list[str] = []
    for field_name in ("corpus_snapshot_id", "corpus_snapshot_hash"):
        if not trace.get(field_name):
            failures.append(f"{field_name}_missing")
    if not trace.get("queries") and not trace.get("declared_no_query_mode"):
        failures.append("queries_missing")
    candidate_ids = [str(item) for item in trace.get("candidate_ids", [])]
    if not trace.get("candidate_set") or not candidate_ids:
        failures.append("candidate_set_missing")
    if "selected_candidates" not in trace:
        failures.append("selected_candidates_missing")
    if "rejected_candidates" not in trace:
        failures.append("rejected_candidates_missing")
    if "evidence_ids_used" not in trace:
        failures.append("evidence_ids_used_missing")
    if not trace.get("retrieval_tool_calls"):
        failures.append("retrieval_tool_calls_missing")
    if trace.get("retrieval_trace_complete") is not True:
        failures.append("retrieval_trace_complete_false")

    selected = {str(item) for item in trace.get("selected_candidates", [])}
    rejected = {str(item) for item in trace.get("rejected_candidates", [])}
    candidate_set = set(candidate_ids)
    if selected - candidate_set:
        failures.append("selected_candidate_not_in_candidate_set")
    if rejected - candidate_set:
        failures.append("rejected_candidate_not_in_candidate_set")

    corpus_path = local_corpus_path(task_path)
    visible_manifest = load_json(visible_manifest_path(task_path))
    manifest_hash = dict(visible_manifest.get("file_hashes_sha256") or {}).get(
        "tool_fixtures/local_static_corpus.jsonl"
    )
    actual_hash = sha256_file(corpus_path) if corpus_path.exists() else ""
    if trace.get("corpus_snapshot_hash") != actual_hash or manifest_hash != actual_hash:
        failures.append("local_static_corpus_hash_mismatch")

    result = dict(trace)
    result["schema_version"] = str(
        result.get("schema_version") or "researchflowbench.retrieval_provenance.v0.1"
    )
    result["task_id"] = str(result.get("task_id") or task_id)
    result["baseline_id"] = str(result.get("baseline_id") or baseline_id)
    result["retrieval_trace_complete"] = not failures
    result["failures"] = sorted(set(failures))
    return result
