"""Execution/reproducibility triage validators for ResearchFlowBench.

The ER01 validator is intentionally deterministic and read-only. It consumes
synthetic fixture logs, classifies attempt-level execution validity, rejects
decoy summaries that count quarantined attempts, and preserves missing
cost/latency values as explicit unknowns instead of zero-filling them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from ._runtime_common import load_json


VALID_FINAL_RESULT = "valid_final_result"
ARCHIVED_INVALID_ATTEMPT = "archived_invalid_attempt"
INCOMPLETE_FAILED_ATTEMPT = "incomplete_failed_attempt"
METRIC_INVALID_PROVENANCE_MISMATCH = "metric_invalid_provenance_mismatch"
PRESERVED_AUDIT_RECORD = "preserved_audit_record"

_COST_LATENCY_FIELDS = ("wall_clock_seconds", "token_usage", "estimated_cost")
_RETRY_LINEAGE_KEYS = (
    "retry_lineage",
    "retry_parent_id",
    "parent_attempt_id",
    "previous_attempt_ids",
    "retry_ordinal",
    "retry_reason",
)


@dataclass(frozen=True)
class ExecutionAttemptDecision:
    """Attempt-level ER01 quarantine and inclusion decision."""

    attempt_id: str
    source_log: str
    status: str
    include_in_final_counts: bool
    preserve_as_audit_record: bool
    evidence_paths: tuple[str, ...] = ()
    hard_failures: tuple[str, ...] = ()
    cost_latency: dict[str, Any] = field(default_factory=dict)
    retry_lineage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionReproReport:
    """Fixture-level ER01 execution/reproducibility validation report."""

    task_id: str
    valid_final_count: int
    valid_final_attempt_ids: tuple[str, ...]
    excluded_attempt_ids: tuple[str, ...]
    attempts: tuple[ExecutionAttemptDecision, ...]
    decoy_summary_valid_for_scoring: bool
    metric_provenance_pass: bool
    metric_provenance_mismatches: tuple[str, ...]
    provenance_mismatch_details: tuple[dict[str, Any], ...]
    axis_decisions: dict[str, bool]
    source_logs: tuple[str, ...]
    invalid_decoy_summary_rows: tuple[str, ...] = ()
    validation_issues: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ("synthetic fixture only; no model execution",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_er01_execution_repro(
    log_paths: Iterable[str | Path],
) -> ExecutionReproReport:
    """Validate ER01 failed-run quarantine triage over synthetic fixture logs.

    Args:
        log_paths: Paths to synthetic ER01 fixture log JSON files. The validator
            reads them only; it does not write, mutate, run models, or call APIs.
    """

    paths = tuple(Path(path) for path in log_paths)
    payloads = tuple((path, load_json(path)) for path in paths)

    task_ids = sorted(
        {
            str(payload.get("task_id") or "")
            for _, payload in payloads
            if payload.get("task_id")
        }
    )
    task_id = task_ids[0] if task_ids else ""
    validation_issues: list[str] = []
    if len(task_ids) > 1:
        validation_issues.append("multiple_task_ids_in_log_set")

    mismatch_details: list[dict[str, Any]] = []
    mismatch_attempt_ids: set[str] = set()
    hash_owners_by_source: dict[str, dict[str, str]] = {}
    final_hashes_by_source: dict[str, set[str]] = {}

    for path, payload in payloads:
        source_log = _display_path(path)
        hash_owners = _hash_owners(payload)
        final_hashes = _final_attempt_hashes(payload, hash_owners)
        hash_owners_by_source[source_log] = hash_owners
        final_hashes_by_source[source_log] = final_hashes
        for detail in _metric_provenance_mismatch_details(
            payload=payload,
            source_log=source_log,
            hash_owners=hash_owners,
            final_hashes=final_hashes,
        ):
            mismatch_details.append(detail)
            mismatch_attempt_ids.add(str(detail["reported_attempt_id"]))

    attempts: list[ExecutionAttemptDecision] = []
    for path, payload in payloads:
        source_log = _display_path(path)
        if payload.get("synthetic") is not True:
            validation_issues.append(f"non_synthetic_log:{source_log}")
        manifest = _mapping(payload.get("run_manifest"))
        if manifest.get("model_execution_performed") is True:
            validation_issues.append(f"model_execution_performed:{source_log}")
        for index, attempt in enumerate(_attempts(payload)):
            attempts.append(
                _classify_attempt(
                    attempt=attempt,
                    attempt_index=index,
                    manifest=manifest,
                    source_log=source_log,
                    mismatch_attempt_ids=mismatch_attempt_ids,
                )
            )

    valid_final_ids = tuple(
        sorted(
            attempt.attempt_id
            for attempt in attempts
            if attempt.include_in_final_counts
        )
    )
    excluded_attempt_ids = tuple(
        sorted(
            attempt.attempt_id
            for attempt in attempts
            if not attempt.include_in_final_counts
        )
    )
    invalid_decoy_rows = tuple(
        sorted(
            _invalid_decoy_summary_rows(
                payloads=payloads,
                valid_final_attempt_ids=set(valid_final_ids),
                invalid_attempt_ids=set(excluded_attempt_ids),
                mismatch_details=mismatch_details,
            )
        )
    )
    metric_provenance_pass = not mismatch_attempt_ids
    outcome_pass = len(valid_final_ids) == 1
    process_pass = (
        metric_provenance_pass
        and all(
            attempt.include_in_final_counts or attempt.preserve_as_audit_record
            for attempt in attempts
        )
        and not validation_issues
    )
    provenance_pass = metric_provenance_pass
    axis_decisions = {
        "outcome_pass": outcome_pass,
        "process_pass": process_pass,
        "provenance_pass": provenance_pass,
        "combined_pass": outcome_pass and process_pass and provenance_pass,
    }

    return ExecutionReproReport(
        task_id=task_id,
        valid_final_count=len(valid_final_ids),
        valid_final_attempt_ids=valid_final_ids,
        excluded_attempt_ids=excluded_attempt_ids,
        attempts=tuple(attempts),
        decoy_summary_valid_for_scoring=not invalid_decoy_rows,
        metric_provenance_pass=metric_provenance_pass,
        metric_provenance_mismatches=tuple(sorted(mismatch_attempt_ids)),
        provenance_mismatch_details=tuple(
            sorted(
                mismatch_details,
                key=lambda detail: (
                    str(detail.get("reported_attempt_id") or ""),
                    str(detail.get("cited_hash_field") or ""),
                ),
            )
        ),
        axis_decisions=axis_decisions,
        source_logs=tuple(_display_path(path) for path in paths),
        invalid_decoy_summary_rows=invalid_decoy_rows,
        validation_issues=tuple(sorted(set(validation_issues))),
    )


def _classify_attempt(
    *,
    attempt: Mapping[str, Any],
    attempt_index: int,
    manifest: Mapping[str, Any],
    source_log: str,
    mismatch_attempt_ids: set[str],
) -> ExecutionAttemptDecision:
    attempt_id = str(attempt.get("attempt_id") or f"attempt_index_{attempt_index}")
    hard_failures = tuple(
        sorted(str(item) for item in attempt.get("hard_failures") or [])
    )
    status = str(attempt.get("attempt_status") or "")
    returncode = attempt.get("returncode")
    parse_ok = attempt.get("parse_ok")
    final_attempt_id = str(manifest.get("final_attempt_id") or "")
    archived_attempt_ids = {
        str(item) for item in manifest.get("archived_attempt_ids") or []
    }
    incomplete_attempt_ids = {
        str(item) for item in manifest.get("incomplete_attempt_ids") or []
    }

    evidence_paths = [
        f"{source_log}#attempts/{attempt_index}",
    ]
    include_in_final_counts = False
    preserve_as_audit_record = False

    if (
        attempt_id in mismatch_attempt_ids
        or "metric_provenance_mismatch" in hard_failures
    ):
        er_status = METRIC_INVALID_PROVENANCE_MISMATCH
        preserve_as_audit_record = True
        evidence_paths.append(f"{source_log}#summary_metric_row_decoy")
    elif (
        status == "incomplete"
        or attempt_id in incomplete_attempt_ids
        or returncode not in (None, 0)
        or parse_ok is False
        or "parse_failed" in hard_failures
        or "nonzero_returncode" in hard_failures
    ):
        er_status = INCOMPLETE_FAILED_ATTEMPT
        preserve_as_audit_record = True
    elif (
        status == "archived"
        or attempt_id in archived_attempt_ids
        or attempt.get("quarantined") is True
        or attempt.get("valid_experiment_result") is False
    ):
        er_status = ARCHIVED_INVALID_ATTEMPT
        preserve_as_audit_record = True
    elif (
        attempt_id == final_attempt_id
        and status == "final"
        and attempt.get("valid_experiment_result") is True
        and attempt.get("quarantined") is False
        and returncode == 0
        and parse_ok is True
        and not hard_failures
    ):
        er_status = VALID_FINAL_RESULT
        include_in_final_counts = True
    else:
        er_status = PRESERVED_AUDIT_RECORD
        preserve_as_audit_record = True

    return ExecutionAttemptDecision(
        attempt_id=attempt_id,
        source_log=source_log,
        status=er_status,
        include_in_final_counts=include_in_final_counts,
        preserve_as_audit_record=preserve_as_audit_record,
        evidence_paths=tuple(evidence_paths),
        hard_failures=hard_failures,
        cost_latency=_cost_latency(attempt),
        retry_lineage=_retry_lineage(attempt),
    )


def _metric_provenance_mismatch_details(
    *,
    payload: Mapping[str, Any],
    source_log: str,
    hash_owners: Mapping[str, str],
    final_hashes: set[str],
) -> list[dict[str, Any]]:
    row = _mapping(payload.get("summary_metric_row_decoy"))
    if not row:
        return []
    manifest = _mapping(payload.get("run_manifest"))
    final_attempt_id = str(manifest.get("final_attempt_id") or "")
    reported_attempt_id = str(row.get("reported_attempt_id") or final_attempt_id)
    details: list[dict[str, Any]] = []
    for key, value in row.items():
        if not key.startswith("cited_") or not key.endswith("_hash"):
            continue
        cited_hash = str(value or "")
        owner_attempt_id = str(hash_owners.get(cited_hash) or "")
        if cited_hash and cited_hash not in final_hashes:
            details.append(
                {
                    "source_log": source_log,
                    "row_id": str(row.get("row_id") or ""),
                    "reported_attempt_id": reported_attempt_id,
                    "expected_final_attempt_id": final_attempt_id,
                    "cited_hash_field": str(key),
                    "cited_hash": cited_hash,
                    "cited_hash_owner_attempt_id": owner_attempt_id,
                    "evidence_path": f"{source_log}#summary_metric_row_decoy.{key}",
                }
            )
    return details


def _invalid_decoy_summary_rows(
    *,
    payloads: tuple[tuple[Path, dict[str, Any]], ...],
    valid_final_attempt_ids: set[str],
    invalid_attempt_ids: set[str],
    mismatch_details: list[dict[str, Any]],
) -> list[str]:
    invalid_rows: list[str] = []
    for path, payload in payloads:
        source_log = _display_path(path)
        summary = _mapping(payload.get("decoy_summary_row"))
        if summary:
            row_id = str(summary.get("row_id") or f"{source_log}#decoy_summary_row")
            claimed_ids = {
                str(item)
                for item in summary.get("claimed_valid_final_attempt_ids") or []
            }
            claimed_count = summary.get("claimed_valid_final_count")
            if claimed_count is None:
                claimed_count = summary.get("valid_final_count_claim")
            if summary.get("why_invalid"):
                invalid_rows.append(row_id)
            elif claimed_ids and (claimed_ids & invalid_attempt_ids):
                invalid_rows.append(row_id)
            elif claimed_ids and not claimed_ids.issubset(valid_final_attempt_ids):
                invalid_rows.append(row_id)
            elif claimed_count is not None:
                try:
                    if int(claimed_count) != len(
                        claimed_ids or valid_final_attempt_ids
                    ):
                        invalid_rows.append(row_id)
                except (TypeError, ValueError):
                    invalid_rows.append(row_id)
        metric_summary = _mapping(payload.get("summary_metric_row_decoy"))
        if metric_summary and any(
            detail["source_log"] == source_log for detail in mismatch_details
        ):
            invalid_rows.append(
                str(
                    metric_summary.get("row_id")
                    or f"{source_log}#summary_metric_row_decoy"
                )
            )
    return invalid_rows


def _hash_owners(payload: Mapping[str, Any]) -> dict[str, str]:
    owners: dict[str, str] = {}
    for attempt in _attempts(payload):
        attempt_id = str(attempt.get("attempt_id") or "")
        if not attempt_id:
            continue
        for synthetic_hash in _collect_synthetic_hashes(attempt):
            owners.setdefault(synthetic_hash, attempt_id)
    return owners


def _final_attempt_hashes(
    payload: Mapping[str, Any],
    hash_owners: Mapping[str, str],
) -> set[str]:
    final_attempt_id = str(
        _mapping(payload.get("run_manifest")).get("final_attempt_id") or ""
    )
    return {
        hash_value
        for hash_value, owner in hash_owners.items()
        if owner == final_attempt_id
    }


def _collect_synthetic_hashes(value: Any) -> set[str]:
    hashes: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) == "synthetic_hash" and child:
                hashes.add(str(child))
            hashes.update(_collect_synthetic_hashes(child))
    elif isinstance(value, list):
        for child in value:
            hashes.update(_collect_synthetic_hashes(child))
    return hashes


def _cost_latency(attempt: Mapping[str, Any]) -> dict[str, Any]:
    trace = _mapping(_mapping(attempt.get("sidecars")).get("cost_latency_trace.json"))
    if not trace:
        return {
            "wall_clock_seconds": None,
            "wall_clock_seconds_unknown_reason": "cost_latency_trace_missing",
            "token_usage": None,
            "token_usage_unknown_reason": "cost_latency_trace_missing",
            "estimated_cost": None,
            "estimated_cost_unknown_reason": "cost_latency_trace_missing",
        }

    cost_latency: dict[str, Any] = {}
    for field_name in _COST_LATENCY_FIELDS:
        cost_latency[field_name] = trace.get(field_name)
        reason_key = f"{field_name}_unknown_reason"
        alternate_reason_key = (
            "wall_clock_unknown_reason"
            if field_name == "wall_clock_seconds"
            else reason_key
        )
        cost_latency[reason_key] = trace.get(reason_key) or trace.get(
            alternate_reason_key
        )
        if cost_latency[field_name] is None and not cost_latency[reason_key]:
            cost_latency[reason_key] = f"{field_name}_unknown"
    return cost_latency


def _retry_lineage(attempt: Mapping[str, Any]) -> dict[str, Any]:
    lineage: dict[str, Any] = {}
    explicit_lineage = attempt.get("retry_lineage")
    if isinstance(explicit_lineage, Mapping):
        lineage.update({str(key): value for key, value in explicit_lineage.items()})
    for key in _RETRY_LINEAGE_KEYS:
        if key == "retry_lineage":
            continue
        if key in attempt:
            lineage[key] = attempt[key]
    run_trace = _mapping(_mapping(attempt.get("sidecars")).get("run_trace.json"))
    for key in _RETRY_LINEAGE_KEYS:
        if key in run_trace and key not in lineage:
            lineage[key] = run_trace[key]
    return lineage


def _attempts(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        attempt
        for attempt in payload.get("attempts") or []
        if isinstance(attempt, Mapping)
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
