"""Output-shape guardrails for ResearchFlowBench baseline contracts.

These validators classify baseline/agent-side output shape only. Common runner
audit files are explicitly ignored for capability detection so shared execution
infrastructure is never credited as B2/B4/B5 capability.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping


B1_BASELINE_ID = "B1.no_governance_workflow_agent"
B2_BASELINE_ID = "B2.retrieval_only_citation_list_agent"
B3_BASELINE_ID = "B3.citation_verifier_only"
B4_BASELINE_ID = "B4.generic_trace_only"
B5_BASELINE_ID = "B5.full_rh"

COMMON_RUNNER_ARTIFACTS = frozenset(
    {
        "allowed_tools_preflight.json",
        "leakage_audit_report.json",
        "retrieval_trace.json",
        "cost_latency_trace.json",
        "run_trace.json",
        "parse_metadata.json",
        "eval_report.json",
        "executor_config.json",
        "prompt_input.md",
        "prompt_used.md",
        "raw_response.txt",
        "raw_stdout.txt",
        "raw_stderr.txt",
        "codex_stdout.txt",
        "codex_stderr.txt",
    }
)

_SEMANTIC_OBJECT_KEYS = frozenset(
    {
        "object_graph",
        "semantic_objects",
        "semantic_object",
        "semantic_nodes",
        "semantic_edges",
        "typed_objects",
        "object_type",
        "semantic_object_type",
    }
)
_DEPENDENCY_KEYS = frozenset({"dependency_graph", "derived_from", "invalidates"})
_GATE_KEYS = frozenset({"gate_decision", "gate_log", "gate_verdict", "formal_gate"})
_VALIDITY_KEYS = frozenset(
    {
        "validity_ledger",
        "state_transition_ledger",
        "transition_history",
        "before_state",
        "after_state",
    }
)
_ROLLBACK_KEYS = frozenset(
    {
        "rollback_cone",
        "rollback_event",
        "rollback_actions",
        "rollback_not_applicable",
        "affected_downstream",
        "affected_objects",
        "preserved_objects",
        "stale_root",
    }
)
_HUMAN_GOVERNANCE_KEYS = frozenset(
    {
        "human_review_queue",
        "human_calibration",
        "adjudication_log",
        "calibration_manifest",
    }
)
_RETRIEVAL_KEYS = frozenset(
    {
        "citation_list",
        "candidate_ranking",
        "retrieval_summary",
        "selected_record_ids",
        "rejected_record_ids",
        "omitted_context_record_ids",
    }
)
_CITATION_VERIFICATION_KEYS = frozenset(
    {
        "span_support_matrix",
        "citation_support_report",
        "clause_support_report",
        "clause_support_map",
        "support_label",
        "recommended_rewrite",
        "rewrite_suggestions",
    }
)
_GENERIC_TRACE_KEYS = frozenset(
    {
        "generic_trace",
        "event_log",
        "artifact_manifest",
        "input_output_lineage",
        "hash_manifest",
        "tool_use_summary",
    }
)
_RH_VERIFICATION_KEYS = frozenset({"verification_report"})
_SCIENTIFIC_STATE_KEYS = frozenset({"semantic_states"})
_SCIENTIFIC_STATE_VALUES = frozenset(
    {
        "retrieved",
        "span_supported",
        "partially_supported",
        "stale",
        "blocked",
        "passed",
        "needs_human_review",
    }
)
_EXTERNAL_SEARCH_KEYS = frozenset(
    {
        "external_search_used",
        "external_search",
        "web_search",
        "browser_network_search",
        "paper_search",
    }
)
_HIDDEN_LEAK_KEYS = frozenset(
    {
        "gold_bundle",
        "gold_bundle_path",
        "judge_bundle",
        "judge_bundle_path",
        "gold_hash",
        "judge_hash",
        "canary",
        "canary_string",
        "hidden_label",
    }
)

_SIDECAR_FAMILIES = {
    "object_graph.json": "semantic_object_graph",
    "semantic_objects.json": "semantic_object_graph",
    "gate_log.json": "gate",
    "validity_ledger.json": "validity_ledger",
    "state_transition_ledger.json": "validity_ledger",
    "rollback_cone.json": "rollback",
    "rollback_event.json": "rollback",
    "citation_list.json": "retrieval_list",
    "candidate_ranking.json": "retrieval_list",
    "retrieval_summary.json": "retrieval_list",
    "span_support_matrix.json": "citation_verification",
    "citation_support_report.json": "citation_verification",
    "clause_support_report.json": "citation_verification",
    "generic_trace.json": "generic_trace",
    "event_log.jsonl": "generic_trace",
    "artifact_manifest.json": "generic_trace",
    "input_output_lineage.json": "generic_trace",
    "hash_manifest.json": "generic_trace",
    "verification_report.json": "rh_verification",
}

_FORBIDDEN_FAMILIES_BY_BASELINE = {
    B1_BASELINE_ID: frozenset(
        {
            "semantic_object_graph",
            "dependency_graph",
            "gate",
            "validity_ledger",
            "rollback",
            "retrieval_list",
            "citation_verification",
            "generic_trace",
            "human_governance",
            "rh_verification",
            "scientific_semantic_state",
        }
    ),
    B2_BASELINE_ID: frozenset(
        {
            "semantic_object_graph",
            "dependency_graph",
            "gate",
            "validity_ledger",
            "rollback",
            "human_governance",
            "rh_verification",
            "scientific_semantic_state",
        }
    ),
    B3_BASELINE_ID: frozenset(
        {
            "semantic_object_graph",
            "dependency_graph",
            "gate",
            "validity_ledger",
            "rollback",
            "retrieval_list",
            "generic_trace",
            "human_governance",
            "rh_verification",
            "scientific_semantic_state",
        }
    ),
    B4_BASELINE_ID: frozenset(
        {
            "semantic_object_graph",
            "dependency_graph",
            "gate",
            "validity_ledger",
            "rollback",
            "retrieval_list",
            "citation_verification",
            "human_governance",
            "rh_verification",
            "scientific_semantic_state",
        }
    ),
    B5_BASELINE_ID: frozenset(),
}


@dataclass(frozen=True)
class OutputShapeViolation:
    """Single output-shape contract violation."""

    code: str
    family: str
    message: str
    path: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutputShapeReport:
    """Baseline output-shape validation result."""

    baseline_id: str
    shape_pass: bool
    violations: tuple[OutputShapeViolation, ...] = ()
    allowed_capabilities_detected: tuple[str, ...] = ()
    common_runner_artifacts_ignored_for_capability: tuple[str, ...] = ()
    scanned_artifacts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["violations"] = [violation.to_dict() for violation in self.violations]
        return payload


@dataclass(frozen=True)
class _ScanHit:
    family: str
    path: str
    key: str
    value: Any


def validate_output_shape(
    baseline_id: str,
    *,
    agent_output: Mapping[str, Any] | None = None,
    sidecars: Mapping[str, Any] | None = None,
) -> OutputShapeReport:
    """Validate a baseline's agent-side output shape.

    Args:
        baseline_id: Baseline contract ID, e.g. ``B2.retrieval_only...``.
        agent_output: Parsed ``agent_output.json`` payload.
        sidecars: Parsed baseline-specific sidecars keyed by filename. Common
            runner audit artifact filenames are ignored for capability credit.
    """

    sidecar_payloads = dict(sidecars or {})
    common_runner_artifacts = tuple(
        sorted(name for name in sidecar_payloads if name in COMMON_RUNNER_ARTIFACTS)
    )
    artifacts_to_scan: dict[str, Any] = {}
    if agent_output is not None:
        artifacts_to_scan["agent_output.json"] = dict(agent_output)
    for filename, payload in sidecar_payloads.items():
        if filename not in COMMON_RUNNER_ARTIFACTS:
            artifacts_to_scan[filename] = payload

    hits = _scan_artifacts(artifacts_to_scan)
    violations = _forbidden_family_violations(baseline_id, hits)
    violations.extend(_sidecar_filename_violations(baseline_id, artifacts_to_scan))
    violations.extend(_external_search_violations(baseline_id, hits))
    violations.extend(_hidden_leak_violations(hits))
    if baseline_id == B5_BASELINE_ID:
        violations.extend(_b5_required_component_violations(artifacts_to_scan))

    capabilities = _allowed_capabilities_detected(
        baseline_id=baseline_id,
        artifacts=artifacts_to_scan,
        hits=hits,
        violations=violations,
    )

    deduped_violations = tuple(_dedupe_violations(violations))
    return OutputShapeReport(
        baseline_id=baseline_id,
        shape_pass=not deduped_violations,
        violations=deduped_violations,
        allowed_capabilities_detected=tuple(sorted(capabilities)),
        common_runner_artifacts_ignored_for_capability=common_runner_artifacts,
        scanned_artifacts=tuple(sorted(artifacts_to_scan)),
    )


def validate_output_shape_dir(
    run_dir: str | Path,
    *,
    baseline_id: str,
) -> OutputShapeReport:
    """Load known JSON sidecars from a run directory and validate shape."""

    run_path = Path(run_dir)
    agent_output_path = run_path / "agent_output.json"
    agent_output = _load_json(agent_output_path) if agent_output_path.exists() else None
    sidecars: dict[str, Any] = {}
    for path in sorted(run_path.iterdir()):
        if path.name == "agent_output.json" or not path.is_file():
            continue
        if path.suffix == ".json":
            sidecars[path.name] = _load_json(path)
        elif path.suffix == ".jsonl":
            sidecars[path.name] = _load_jsonl(path)
    return validate_output_shape(
        baseline_id,
        agent_output=agent_output,
        sidecars=sidecars,
    )


def _scan_artifacts(artifacts: Mapping[str, Any]) -> list[_ScanHit]:
    hits: list[_ScanHit] = []
    for artifact_name, payload in artifacts.items():
        hits.extend(_scan_value(payload, artifact_name))
        family = _SIDECAR_FAMILIES.get(artifact_name)
        if family:
            hits.append(
                _ScanHit(
                    family=family,
                    path=artifact_name,
                    key=artifact_name,
                    value=payload,
                )
            )
    return hits


def _scan_value(value: Any, path: str) -> list[_ScanHit]:
    hits: list[_ScanHit] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized_key = str(key)
            child_path = f"{path}.{normalized_key}"
            family = _family_for_key(normalized_key)
            if family:
                hits.append(
                    _ScanHit(
                        family=family,
                        path=child_path,
                        key=normalized_key,
                        value=child,
                    )
                )
            state_family = _scientific_state_family(normalized_key, child)
            if state_family:
                hits.append(
                    _ScanHit(
                        family=state_family,
                        path=child_path,
                        key=normalized_key,
                        value=child,
                    )
                )
            hits.extend(_scan_value(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_scan_value(child, f"{path}[{index}]"))
    return hits


def _family_for_key(key: str) -> str:
    normalized = key.lower()
    if normalized in _SEMANTIC_OBJECT_KEYS:
        return "semantic_object_graph"
    if normalized in _DEPENDENCY_KEYS:
        return "dependency_graph"
    if normalized in _GATE_KEYS:
        return "gate"
    if normalized in _VALIDITY_KEYS:
        return "validity_ledger"
    if normalized in _ROLLBACK_KEYS:
        return "rollback"
    if normalized in _HUMAN_GOVERNANCE_KEYS:
        return "human_governance"
    if normalized in _RETRIEVAL_KEYS:
        return "retrieval_list"
    if normalized in _CITATION_VERIFICATION_KEYS:
        return "citation_verification"
    if normalized in _GENERIC_TRACE_KEYS:
        return "generic_trace"
    if normalized in _RH_VERIFICATION_KEYS:
        return "rh_verification"
    if normalized in _SCIENTIFIC_STATE_KEYS:
        return "scientific_semantic_state"
    if normalized in _EXTERNAL_SEARCH_KEYS:
        return "external_search"
    if normalized in _HIDDEN_LEAK_KEYS:
        return "hidden_judge_or_gold"
    return ""


def _scientific_state_family(key: str, value: Any) -> str:
    normalized = key.lower()
    if normalized not in {"state", "status", "semantic_state"}:
        return ""
    if isinstance(value, str) and value.lower() in _SCIENTIFIC_STATE_VALUES:
        return "scientific_semantic_state"
    return ""


def _forbidden_family_violations(
    baseline_id: str,
    hits: list[_ScanHit],
) -> list[OutputShapeViolation]:
    forbidden = _FORBIDDEN_FAMILIES_BY_BASELINE.get(baseline_id, frozenset())
    return [
        OutputShapeViolation(
            code="baseline_forbidden_output_shape",
            family=hit.family,
            message=(
                f"{baseline_id} output shape forbids {hit.family} capability "
                "in baseline/agent-side artifacts"
            ),
            path=hit.path,
            details={"key": hit.key},
        )
        for hit in hits
        if hit.family in forbidden
    ]


def _sidecar_filename_violations(
    baseline_id: str,
    artifacts: Mapping[str, Any],
) -> list[OutputShapeViolation]:
    forbidden = _FORBIDDEN_FAMILIES_BY_BASELINE.get(baseline_id, frozenset())
    violations: list[OutputShapeViolation] = []
    for filename in artifacts:
        family = _SIDECAR_FAMILIES.get(filename)
        if family and family in forbidden:
            violations.append(
                OutputShapeViolation(
                    code="baseline_forbidden_output_sidecar",
                    family=family,
                    message=f"{baseline_id} forbids baseline-side sidecar {filename}",
                    path=filename,
                    details={"filename": filename},
                )
            )
    return violations


def _external_search_violations(
    baseline_id: str,
    hits: list[_ScanHit],
) -> list[OutputShapeViolation]:
    if baseline_id not in {
        B1_BASELINE_ID,
        B2_BASELINE_ID,
        B3_BASELINE_ID,
        B4_BASELINE_ID,
        B5_BASELINE_ID,
    }:
        return []
    violations: list[OutputShapeViolation] = []
    for hit in hits:
        if hit.family == "external_search" and _external_search_claims_use(hit.value):
            violations.append(
                OutputShapeViolation(
                    code="external_search_forbidden",
                    family="external_search",
                    message=f"{baseline_id} v0 output must not claim external search use",
                    path=hit.path,
                    details={"key": hit.key},
                )
            )
    return violations


def _external_search_claims_use(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.lower() in {"true", "used", "enabled", "yes", "performed"}
    if isinstance(value, list):
        return any(_external_search_claims_use(item) for item in value)
    if isinstance(value, Mapping):
        return any(_external_search_claims_use(item) for item in value.values())
    return False


def _hidden_leak_violations(hits: list[_ScanHit]) -> list[OutputShapeViolation]:
    return [
        OutputShapeViolation(
            code="hidden_judge_or_gold_leak",
            family="hidden_judge_or_gold",
            message="baseline/agent-side output must not expose hidden gold/judge data",
            path=hit.path,
            details={"key": hit.key},
        )
        for hit in hits
        if hit.family == "hidden_judge_or_gold"
    ]


def _b5_required_component_violations(
    artifacts: Mapping[str, Any],
) -> list[OutputShapeViolation]:
    checks = {
        "typed_objects": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "semantic_objects"),
                ("agent_output.json", "object_graph", "objects"),
                ("agent_output.json", "object_graph", "nodes"),
                ("object_graph.json", "objects"),
                ("object_graph.json", "nodes"),
            ),
        ),
        "graph_edges": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "object_graph", "edges"),
                ("object_graph.json", "edges"),
            ),
        ),
        "gate_surface": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "gate_decision"),
                ("agent_output.json", "gate_log"),
                ("gate_log.json",),
            ),
        ),
        "verification_surface": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "verification_report", "checks"),
                ("verification_report.json", "checks"),
            ),
        ),
        "validity_surface": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "validity_ledger"),
                ("agent_output.json", "state_transition_ledger"),
                ("validity_ledger.json",),
                ("state_transition_ledger.json",),
            ),
        ),
        "rollback_surface": _has_any_meaningful_path(
            artifacts,
            (
                ("agent_output.json", "rollback_cone"),
                ("agent_output.json", "rollback_event"),
                ("agent_output.json", "rollback_actions"),
                ("agent_output.json", "rollback_not_applicable"),
                ("rollback_cone.json",),
                ("rollback_event.json",),
            ),
        ),
        "object_graph_sidecar": _meaningful_artifact(artifacts, "object_graph.json"),
        "gate_log_sidecar": _meaningful_artifact(artifacts, "gate_log.json"),
        "verification_report_sidecar": _meaningful_artifact(
            artifacts, "verification_report.json"
        ),
    }
    return [
        OutputShapeViolation(
            code="b5_required_component_missing",
            family="full_rh_governance",
            message=f"B5.full_rh is missing required RH output-shape component: {name}",
            path=name,
            details={"component": name},
        )
        for name, present in checks.items()
        if not present
    ]


def _allowed_capabilities_detected(
    *,
    baseline_id: str,
    artifacts: Mapping[str, Any],
    hits: list[_ScanHit],
    violations: list[OutputShapeViolation],
) -> set[str]:
    families = {hit.family for hit in hits}
    capabilities: set[str] = set()
    if "retrieval_list" in families and baseline_id == B2_BASELINE_ID:
        capabilities.add("retrieval_list")
    if "citation_verification" in families and baseline_id == B3_BASELINE_ID:
        capabilities.add("citation_verification")
    if "generic_trace" in families and baseline_id == B4_BASELINE_ID:
        capabilities.add("generic_trace")
    if baseline_id == B5_BASELINE_ID and not any(
        violation.code == "b5_required_component_missing" for violation in violations
    ):
        if artifacts:
            capabilities.add("full_rh_governance")
    return capabilities


def _has_any_meaningful_path(
    artifacts: Mapping[str, Any],
    paths: tuple[tuple[str, ...], ...],
) -> bool:
    return any(_payload_is_meaningful(_get_path(artifacts, path)) for path in paths)


def _meaningful_artifact(artifacts: Mapping[str, Any], filename: str) -> bool:
    return filename in artifacts and _payload_is_meaningful(artifacts[filename])


def _get_path(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _payload_is_meaningful(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_payload_is_meaningful(child) for child in value.values())
    if isinstance(value, list):
        return any(_payload_is_meaningful(child) for child in value)
    return True


def _dedupe_violations(
    violations: list[OutputShapeViolation],
) -> list[OutputShapeViolation]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[OutputShapeViolation] = []
    for violation in violations:
        key = (violation.code, violation.family, violation.path)
        if key not in seen:
            deduped.append(violation)
            seen.add(key)
    return deduped


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"_payload": payload}
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
            else:
                records.append({"_payload": payload})
    return records
