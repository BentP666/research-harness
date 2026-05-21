"""Validators for semantic governance bundles."""

from __future__ import annotations

from .graph import compute_rollback_cone
from .models import (
    Diagnostic,
    EdgeType,
    GateVerdict,
    ObjectType,
    ReliabilityState,
    SemanticGovernanceBundle,
    ValidationReport,
)

STRICT_REJECT_DIAGNOSTICS = {
    "legacy_type_mapping",
    "implicit_legacy_object",
    "raw_edge_direction_uncertain",
    "release_grade_judge_missing",
    "retrieval_trace_incomplete",
    "cost_unknown",
}


def validate_bundle(
    bundle: SemanticGovernanceBundle, mode: str = "legacy"
) -> ValidationReport:
    if mode not in {"legacy", "strict"}:
        raise ValueError("mode must be 'legacy' or 'strict'")

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_unique_objects(bundle))
    diagnostics.extend(_validate_edges(bundle, mode=mode))
    diagnostics.extend(_validate_gates(bundle, mode=mode))
    diagnostics.extend(_validate_verification_signals(bundle, mode=mode))
    diagnostics.extend(_validate_ledger(bundle, mode=mode))
    diagnostics.extend(_validate_rollback_cones(bundle))

    if mode == "strict":
        for diagnostic in bundle.diagnostics:
            if diagnostic.code in STRICT_REJECT_DIAGNOSTICS:
                diagnostics.append(
                    Diagnostic(
                        code="strict_rejects_legacy_diagnostic",
                        severity="error",
                        message=f"strict mode rejects legacy diagnostic {diagnostic.code}",
                        object_id=diagnostic.object_id,
                        source_ref=diagnostic.source_ref,
                        details={"legacy_code": diagnostic.code},
                    )
                )

    error_codes = {"error"}
    is_valid = not any(diagnostic.severity in error_codes for diagnostic in diagnostics)
    return ValidationReport(
        mode=mode,
        is_valid=is_valid,
        diagnostics=tuple(diagnostics),
        object_count=len(bundle.objects),
        edge_count=len(bundle.edges),
        gate_count=len(bundle.gate_decisions),
        verification_signal_count=len(bundle.verification_signals),
        ledger_entry_count=len(bundle.validity_ledger),
    )


def _validate_unique_objects(bundle: SemanticGovernanceBundle) -> list[Diagnostic]:
    seen: set[str] = set()
    diagnostics: list[Diagnostic] = []
    for obj in bundle.objects:
        if obj.object_id in seen:
            diagnostics.append(
                Diagnostic(
                    code="duplicate_object_id",
                    severity="error",
                    message=f"duplicate object_id {obj.object_id}",
                    object_id=obj.object_id,
                )
            )
        seen.add(obj.object_id)
    return diagnostics


def _validate_edges(bundle: SemanticGovernanceBundle, mode: str) -> list[Diagnostic]:
    object_ids = bundle.object_ids
    object_by_id = bundle.object_by_id()
    diagnostics: list[Diagnostic] = []
    for edge in bundle.edges:
        if edge.source_object_id not in object_ids:
            diagnostics.append(
                Diagnostic(
                    code="edge_source_missing",
                    severity="error",
                    message=f"edge source {edge.source_object_id} is not a semantic object",
                    object_id=edge.source_object_id,
                    source_ref=edge.source_ref,
                )
            )
            continue
        if edge.target_object_id not in object_ids:
            diagnostics.append(
                Diagnostic(
                    code="edge_target_missing",
                    severity="error",
                    message=f"edge target {edge.target_object_id} is not a semantic object",
                    object_id=edge.target_object_id,
                    source_ref=edge.source_ref,
                )
            )
            continue
        source = object_by_id[edge.source_object_id]
        target = object_by_id[edge.target_object_id]
        direction_code = _edge_direction_issue_code(
            edge.edge_type, source.object_type, target.object_type
        )
        if direction_code:
            diagnostics.append(
                Diagnostic(
                    code=direction_code,
                    severity="error" if mode == "strict" else "warning",
                    message=(
                        f"{edge.edge_type.value} edge direction should follow upstream evidence/input "
                        "→ downstream dependent semantics"
                    ),
                    object_id=edge.edge_id,
                    source_ref=edge.source_ref,
                    details={
                        "source_object_id": edge.source_object_id,
                        "source_object_type": source.object_type.value,
                        "target_object_id": edge.target_object_id,
                        "target_object_type": target.object_type.value,
                    },
                )
            )
    return diagnostics


def _validate_gates(bundle: SemanticGovernanceBundle, mode: str) -> list[Diagnostic]:
    object_ids = bundle.object_ids
    object_by_id = bundle.object_by_id()
    diagnostics: list[Diagnostic] = []
    for gate in bundle.gate_decisions:
        if (
            gate.verdict in {GateVerdict.PASS, GateVerdict.PASS_WITH_CAVEAT}
            and not gate.evidence_refs
        ):
            diagnostics.append(
                Diagnostic(
                    code="gate_pass_without_evidence",
                    severity="error",
                    message="pass/pass_with_caveat gate must cite evidence_refs",
                    object_id=gate.gate_id,
                    source_ref=gate.source_ref,
                )
            )
        for object_id in gate.target_object_ids + gate.invalidated_object_ids:
            if object_id not in object_ids:
                diagnostics.append(
                    Diagnostic(
                        code="gate_target_missing",
                        severity="error",
                        message=f"gate references missing object {object_id}",
                        object_id=object_id,
                        source_ref=gate.source_ref,
                    )
                )
            else:
                obj = object_by_id[object_id]
                if (
                    gate.verdict in {GateVerdict.PASS, GateVerdict.PASS_WITH_CAVEAT}
                    and obj.reliability_state in INVALID_PASS_TARGET_STATES
                ):
                    diagnostics.append(
                        Diagnostic(
                            code="gate_passes_invalid_target_state",
                            severity="error",
                            message=(
                                f"{gate.verdict.value} gate cannot pass target {object_id} "
                                f"in state {obj.reliability_state.value}"
                            ),
                            object_id=object_id,
                            source_ref=gate.source_ref,
                            details={
                                "gate_id": gate.gate_id,
                                "state": obj.reliability_state.value,
                            },
                        )
                    )
                if (
                    mode == "strict"
                    and object_id in gate.invalidated_object_ids
                    and obj.reliability_state not in VALID_INVALIDATED_STATES
                ):
                    diagnostics.append(
                        Diagnostic(
                            code="gate_invalidates_without_bad_state",
                            severity="error",
                            message=(
                                f"strict mode requires invalidated object {object_id} to carry a stale, "
                                "blocked, unsupported, contradicted, ambiguous, or review-needed state"
                            ),
                            object_id=object_id,
                            source_ref=gate.source_ref,
                            details={
                                "gate_id": gate.gate_id,
                                "state": obj.reliability_state.value,
                            },
                        )
                    )
        if gate.verdict == GateVerdict.BLOCK and not (
            gate.invalidated_object_ids or gate.criteria
        ):
            diagnostics.append(
                Diagnostic(
                    code="block_gate_without_reason",
                    severity="error",
                    message="block gate must identify invalidated objects or criteria/reasons",
                    object_id=gate.gate_id,
                    source_ref=gate.source_ref,
                )
            )
    return diagnostics


def _validate_verification_signals(
    bundle: SemanticGovernanceBundle, mode: str
) -> list[Diagnostic]:
    object_ids = bundle.object_ids
    diagnostics: list[Diagnostic] = []
    for signal in bundle.verification_signals:
        if mode == "strict" and not signal.target_object_ids:
            diagnostics.append(
                Diagnostic(
                    code="verification_signal_without_target",
                    severity="error",
                    message="strict mode requires every verification signal to target at least one object",
                    object_id=signal.signal_id,
                    source_ref=signal.source_ref,
                )
            )
        for object_id in signal.target_object_ids:
            if object_id not in object_ids:
                diagnostics.append(
                    Diagnostic(
                        code="verification_target_missing",
                        severity="error",
                        message=f"verification signal references missing object {object_id}",
                        object_id=object_id,
                        source_ref=signal.source_ref,
                    )
                )
    return diagnostics


def _validate_ledger(bundle: SemanticGovernanceBundle, mode: str) -> list[Diagnostic]:
    object_ids = bundle.object_ids
    gate_ids = {gate.gate_id for gate in bundle.gate_decisions}
    signal_ids = {signal.signal_id for signal in bundle.verification_signals}
    diagnostics: list[Diagnostic] = []
    for entry in bundle.validity_ledger:
        if entry.object_id not in object_ids:
            diagnostics.append(
                Diagnostic(
                    code="ledger_object_missing",
                    severity="error",
                    message=f"ledger entry references missing object {entry.object_id}",
                    object_id=entry.object_id,
                    source_ref=entry.evidence_ref,
                )
            )
        if not entry.evidence_ref:
            diagnostics.append(
                Diagnostic(
                    code="ledger_entry_without_evidence",
                    severity="error",
                    message="ledger entry must have evidence_ref",
                    object_id=entry.object_id,
                )
            )
        if entry.gate_id and entry.gate_id not in gate_ids:
            diagnostics.append(
                Diagnostic(
                    code="ledger_gate_missing",
                    severity="error",
                    message=f"ledger entry references missing gate {entry.gate_id}",
                    object_id=entry.object_id,
                    source_ref=entry.evidence_ref,
                    details={"entry_id": entry.entry_id, "gate_id": entry.gate_id},
                )
            )
        if entry.signal_id and entry.signal_id not in signal_ids:
            diagnostics.append(
                Diagnostic(
                    code="ledger_signal_missing",
                    severity="error",
                    message=f"ledger entry references missing verification signal {entry.signal_id}",
                    object_id=entry.object_id,
                    source_ref=entry.evidence_ref,
                    details={"entry_id": entry.entry_id, "signal_id": entry.signal_id},
                )
            )
    if mode == "strict":
        diagnostics.extend(_validate_strict_ledger_final_states(bundle))
    return diagnostics


def _validate_rollback_cones(bundle: SemanticGovernanceBundle) -> list[Diagnostic]:
    object_ids = bundle.object_ids
    diagnostics: list[Diagnostic] = []
    for cone in bundle.rollback_cones:
        if cone.trigger_object_id not in object_ids:
            diagnostics.append(
                Diagnostic(
                    code="rollback_trigger_missing",
                    severity="error",
                    message=f"rollback trigger {cone.trigger_object_id} is missing",
                    object_id=cone.trigger_object_id,
                )
            )
        for object_id in cone.affected_object_ids:
            if object_id not in object_ids:
                diagnostics.append(
                    Diagnostic(
                        code="rollback_affected_missing",
                        severity="error",
                        message=f"rollback affected object {object_id} is missing",
                        object_id=object_id,
                    )
                )
        expected_affected = set(
            compute_rollback_cone(bundle, cone.trigger_object_id).affected_object_ids
        )
        declared_affected = set(cone.affected_object_ids)
        missing_downstream = sorted(expected_affected - declared_affected)
        if missing_downstream:
            diagnostics.append(
                Diagnostic(
                    code="rollback_cone_missing_downstream",
                    severity="error",
                    message="rollback cone omits transitive downstream affected objects",
                    object_id=cone.trigger_object_id,
                    details={"missing_downstream_object_ids": missing_downstream},
                )
            )
    return diagnostics


SUPPORT_INPUT_OBJECT_TYPES = {
    ObjectType.PAPER,
    ObjectType.EVIDENCE_SPAN,
    ObjectType.CITATION_LINK,
    ObjectType.BASELINE,
    ObjectType.EXPERIMENT,
    ObjectType.METRIC,
    ObjectType.CODE_ARTIFACT,
    ObjectType.RUN_TRACE,
}

DEPENDENT_OBJECT_TYPES = {
    ObjectType.CLAIM,
    ObjectType.SECTION_DRAFT,
    ObjectType.REVIEW_ISSUE,
    ObjectType.GATE_DECISION,
    ObjectType.ROLLBACK_EVENT,
}

SUPPORT_EDGE_TYPES = {
    EdgeType.SUPPORTED_BY,
    EdgeType.PARTIALLY_SUPPORTED_BY,
    EdgeType.CONTRADICTED_BY,
    EdgeType.COMPARES_TO,
}

INVALID_PASS_TARGET_STATES = {
    ReliabilityState.UNSUPPORTED,
    ReliabilityState.CONTRADICTED,
    ReliabilityState.STALE,
    ReliabilityState.BLOCKED,
}

VALID_INVALIDATED_STATES = {
    ReliabilityState.UNSUPPORTED,
    ReliabilityState.CONTRADICTED,
    ReliabilityState.AMBIGUOUS,
    ReliabilityState.NEEDS_HUMAN_REVIEW,
    ReliabilityState.STALE,
    ReliabilityState.BLOCKED,
}


def _edge_direction_issue_code(
    edge_type: EdgeType, source_type: ObjectType, target_type: ObjectType
) -> str:
    if (
        edge_type in SUPPORT_EDGE_TYPES
        and source_type in DEPENDENT_OBJECT_TYPES
        and target_type in SUPPORT_INPUT_OBJECT_TYPES
    ):
        return "edge_direction_inconsistent"
    if edge_type == EdgeType.DERIVED_FROM and source_type == ObjectType.GATE_DECISION:
        return "edge_direction_inconsistent"
    return ""


def _validate_strict_ledger_final_states(
    bundle: SemanticGovernanceBundle,
) -> list[Diagnostic]:
    object_by_id = bundle.object_by_id()
    latest_by_object: dict[str, str] = {}
    for entry in bundle.validity_ledger:
        latest_by_object[entry.object_id] = entry.to_state.value

    diagnostics: list[Diagnostic] = []
    for object_id, ledger_state in latest_by_object.items():
        obj = object_by_id.get(object_id)
        if obj is None:
            continue
        if obj.reliability_state.value != ledger_state:
            diagnostics.append(
                Diagnostic(
                    code="ledger_final_state_mismatch",
                    severity="error",
                    message=(
                        f"strict mode requires object {object_id} state {obj.reliability_state.value} "
                        f"to match latest ledger state {ledger_state}"
                    ),
                    object_id=object_id,
                    details={
                        "object_state": obj.reliability_state.value,
                        "ledger_state": ledger_state,
                    },
                )
            )
    return diagnostics
