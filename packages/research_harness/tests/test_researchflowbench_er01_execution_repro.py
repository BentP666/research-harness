from __future__ import annotations

import hashlib
import json
from pathlib import Path

from research_harness.eval.researchflowbench import validate_er01_execution_repro


PUBLIC_FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures/researchflowbench/er01"
)
FIXTURE_LOGS = (
    PUBLIC_FIXTURE_ROOT / "success_like_log.json",
    PUBLIC_FIXTURE_ROOT / "failed_run_log.json",
    PUBLIC_FIXTURE_ROOT / "metric_pass_provenance_fail_log.json",
)
PRIVATE_FIXTURE_MARKERS = (
    ".research-harness",
    "rfb_er01_fixture_v0_20260521",
    "source_artifacts_preserved",
    "artifact_id",
    "dependency_artifact",
    "recorded_artifact",
)


def _attempts_by_id(report):
    return {attempt.attempt_id: attempt for attempt in report.attempts}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_er01_public_fixtures_are_repo_local_and_private_reference_free():
    for path in FIXTURE_LOGS:
        assert path.is_file()
        assert path.parent == PUBLIC_FIXTURE_ROOT
        assert ".research-harness" not in str(path)

        fixture_text = path.read_text(encoding="utf-8")
        for marker in PRIVATE_FIXTURE_MARKERS:
            assert marker not in fixture_text


def test_er01_fixture_classifies_attempts_and_counts_only_valid_final():
    report = validate_er01_execution_repro(FIXTURE_LOGS)

    assert report.task_id == "RFB-ER01.failed_run_quarantine_triage.0001"
    assert report.valid_final_count == 1
    assert report.valid_final_attempt_ids == ("attempt_final_success",)
    assert report.excluded_attempt_ids == (
        "attempt_archived_external_search",
        "attempt_archived_metric_source",
        "attempt_final_provenance_expected",
        "attempt_incomplete_parse_failure",
    )
    assert not report.decoy_summary_valid_for_scoring

    attempts = _attempts_by_id(report)
    assert attempts["attempt_final_success"].status == "valid_final_result"
    assert attempts["attempt_final_success"].include_in_final_counts

    assert (
        attempts["attempt_archived_external_search"].status
        == "archived_invalid_attempt"
    )
    assert not attempts["attempt_archived_external_search"].include_in_final_counts
    assert attempts["attempt_archived_external_search"].preserve_as_audit_record

    assert (
        attempts["attempt_incomplete_parse_failure"].status
        == "incomplete_failed_attempt"
    )
    assert not attempts["attempt_incomplete_parse_failure"].include_in_final_counts
    assert attempts["attempt_incomplete_parse_failure"].preserve_as_audit_record

    assert (
        attempts["attempt_final_provenance_expected"].status
        == "metric_invalid_provenance_mismatch"
    )
    assert not attempts["attempt_final_provenance_expected"].include_in_final_counts
    assert attempts["attempt_final_provenance_expected"].preserve_as_audit_record

    assert (
        attempts["attempt_archived_metric_source"].status == "archived_invalid_attempt"
    )
    assert not attempts["attempt_archived_metric_source"].include_in_final_counts
    assert attempts["attempt_archived_metric_source"].preserve_as_audit_record


def test_er01_metric_pass_provenance_fail_blocks_process_and_combined_axes():
    report = validate_er01_execution_repro(FIXTURE_LOGS)

    assert not report.metric_provenance_pass
    assert report.metric_provenance_mismatches == ("attempt_final_provenance_expected",)
    assert report.axis_decisions == {
        "outcome_pass": True,
        "process_pass": False,
        "provenance_pass": False,
        "combined_pass": False,
    }

    mismatch = report.provenance_mismatch_details[0]
    assert mismatch["reported_attempt_id"] == "attempt_final_provenance_expected"
    assert mismatch["expected_final_attempt_id"] == "attempt_final_provenance_expected"
    assert mismatch["cited_hash_owner_attempt_id"] == "attempt_archived_metric_source"


def test_er01_missing_cost_latency_remains_unknown_not_zero_filled():
    report = validate_er01_execution_repro(FIXTURE_LOGS)
    attempts = _attempts_by_id(report)

    success_cost = attempts["attempt_final_success"].cost_latency
    assert success_cost["wall_clock_seconds"] == 1.25
    assert success_cost["token_usage"] is None
    assert success_cost["token_usage_unknown_reason"] == (
        "synthetic fixture; no model execution"
    )
    assert success_cost["estimated_cost"] is None
    assert success_cost["estimated_cost_unknown_reason"] == (
        "synthetic fixture; no paid API or model execution"
    )

    archived_cost = attempts["attempt_archived_external_search"].cost_latency
    assert archived_cost["wall_clock_seconds"] is None
    assert archived_cost["token_usage"] is None
    assert archived_cost["estimated_cost"] is None
    assert archived_cost["wall_clock_seconds_unknown_reason"] == (
        "cost_latency_trace_missing"
    )
    assert archived_cost["token_usage_unknown_reason"] == "cost_latency_trace_missing"
    assert (
        archived_cost["estimated_cost_unknown_reason"] == "cost_latency_trace_missing"
    )


def test_er01_retry_lineage_is_preserved_when_present(tmp_path: Path):
    source_payload = json.loads(FIXTURE_LOGS[0].read_text(encoding="utf-8"))
    retry_lineage = {
        "parent_attempt_id": "attempt_initial_failed",
        "previous_attempt_ids": ["attempt_initial_failed"],
        "retry_ordinal": 1,
        "retry_reason": "synthetic_retry_path",
    }
    source_payload["attempts"][0]["retry_lineage"] = retry_lineage
    retry_log = tmp_path / "success_like_retry_log.json"
    retry_log.write_text(json.dumps(source_payload, indent=2) + "\n", encoding="utf-8")

    report = validate_er01_execution_repro([retry_log])

    attempt = _attempts_by_id(report)["attempt_final_success"]
    assert attempt.status == "valid_final_result"
    assert attempt.retry_lineage == retry_lineage


def test_er01_validator_does_not_mutate_synthetic_fixture_logs():
    before = {path: _sha256(path) for path in FIXTURE_LOGS}

    validate_er01_execution_repro(FIXTURE_LOGS)

    after = {path: _sha256(path) for path in FIXTURE_LOGS}
    assert after == before
