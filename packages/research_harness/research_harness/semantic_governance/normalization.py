"""B5 → Semantic Governance v0.1 normalization.

The converter is read-only. It consumes Pilot-5 B5 governance files and returns
in-memory bundles; callers may decide whether to write derived demo outputs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .graph import compute_rollback_cone
from .io import (
    B5TaskBundlePaths,
    combined_row_for_task,
    discover_b5_task_bundles,
    load_combined_eval_summary,
    load_json,
)
from .models import (
    Diagnostic,
    EdgeType,
    GateDecision,
    GateVerdict,
    ObjectType,
    ReliabilityState,
    RunTrace,
    SemanticEdge,
    SemanticGovernanceBundle,
    SemanticObject,
    ValidityLedgerEntry,
    VerificationSignal,
)


LEGACY_GATE_VERDICT_MAP = {
    "advance": GateVerdict.PASS,
    "advance_with_caveats": GateVerdict.PASS_WITH_CAVEAT,
    "block": GateVerdict.BLOCK,
}

POSITIVE_RESULT_LABELS = {"ok", "pass", "passed", "mitigated", "true"}
NEGATIVE_RESULT_LABELS = {"fail", "failed", "false", "blocked", "error"}
UNCERTAIN_RESULT_LABELS = {
    "warn",
    "warning",
    "conditional",
    "conditionally_pass",
    "unknown",
    "n/a",
}


def convert_b5_run(
    run_root: Path | str,
    combined_eval_summary: dict[str, Any] | None = None,
    baseline_id: str = "B5.full_rh",
) -> list[SemanticGovernanceBundle]:
    root = Path(run_root)
    combined = (
        combined_eval_summary
        if combined_eval_summary is not None
        else load_combined_eval_summary(root)
    )
    return [
        convert_b5_task_bundle(paths, root, combined)
        for paths in discover_b5_task_bundles(root, baseline_id=baseline_id)
    ]


def convert_b5_task_bundle(
    paths: B5TaskBundlePaths,
    run_root: Path | str,
    combined_eval_summary: dict[str, Any] | None = None,
) -> SemanticGovernanceBundle:
    root = Path(run_root)
    object_graph = _dict(load_json(paths.object_graph))
    gate_log = _dict(load_json(paths.gate_log))
    verification_report = _dict(load_json(paths.verification_report))
    run_trace_raw = _dict(load_json(paths.run_trace))

    diagnostics: list[Diagnostic] = []
    objects, object_lookup, object_diagnostics = _normalize_objects(paths, object_graph)
    diagnostics.extend(object_diagnostics)

    edges, implicit_objects, edge_diagnostics = _normalize_edges(
        paths, object_graph, object_lookup
    )
    diagnostics.extend(edge_diagnostics)
    for obj in implicit_objects:
        if obj.object_id not in object_lookup:
            objects.append(obj)
            object_lookup[obj.object_id] = obj

    gate, gate_object, gate_edges, gate_ledger, gate_diagnostics = _normalize_gate(
        paths,
        gate_log,
        verification_report,
        object_graph,
        object_lookup,
    )
    objects.append(gate_object)
    object_lookup[gate_object.object_id] = gate_object
    edges.extend(gate_edges)
    diagnostics.extend(gate_diagnostics)

    verification_signals = _normalize_verification(
        paths, verification_report, gate.gate_id
    )
    ledger = list(gate_ledger)
    ledger.extend(_ledger_from_verification(paths, verification_signals, gate))

    run_trace, trace_diagnostics = _normalize_run_trace(paths, run_trace_raw)
    diagnostics.extend(trace_diagnostics)

    diagnostics.append(
        Diagnostic(
            code="release_grade_judge_missing",
            severity="warning",
            message="B5 smoke freeze has no human-adjudicated release-grade judge packet.",
            source_ref="handoff_for_next_session.md#caveats",
        )
    )

    aggregate_context = _aggregate_context(
        combined_eval_summary or {}, paths.task_id, paths.baseline_id
    )
    source_files = paths.source_files(root)

    provisional_bundle = SemanticGovernanceBundle(
        task_id=paths.task_id,
        baseline_id=paths.baseline_id,
        source_run_root=str(root),
        objects=tuple(objects),
        edges=tuple(edges),
        gate_decisions=(gate,),
        verification_signals=tuple(verification_signals),
        validity_ledger=tuple(ledger),
        run_trace=run_trace,
        diagnostics=tuple(diagnostics),
        source_files=source_files,
        aggregate_context=aggregate_context,
    )

    rollback_cones = _derive_rollback_cones(provisional_bundle, gate, edges)
    return SemanticGovernanceBundle(
        task_id=provisional_bundle.task_id,
        baseline_id=provisional_bundle.baseline_id,
        source_run_root=provisional_bundle.source_run_root,
        objects=provisional_bundle.objects,
        edges=provisional_bundle.edges,
        gate_decisions=provisional_bundle.gate_decisions,
        verification_signals=provisional_bundle.verification_signals,
        validity_ledger=provisional_bundle.validity_ledger,
        rollback_cones=tuple(rollback_cones),
        run_trace=provisional_bundle.run_trace,
        diagnostics=provisional_bundle.diagnostics,
        source_files=provisional_bundle.source_files,
        aggregate_context=provisional_bundle.aggregate_context,
    )


def _normalize_objects(
    paths: B5TaskBundlePaths,
    object_graph: dict[str, Any],
) -> tuple[list[SemanticObject], dict[str, SemanticObject], list[Diagnostic]]:
    objects: list[SemanticObject] = []
    diagnostics: list[Diagnostic] = []
    for index, raw in enumerate(object_graph.get("objects", [])):
        raw_obj = _dict(raw)
        raw_id = str(raw_obj.get("id") or raw_obj.get("object_id") or "")
        source_ref = f"{_rel(paths.object_graph)}#/objects/{index}"
        object_type = _map_object_type(raw_obj)
        raw_type = str(raw_obj.get("type", ""))
        if raw_type and raw_type != object_type.value:
            diagnostics.append(
                Diagnostic(
                    code="legacy_type_mapping",
                    severity="info",
                    message=f"Mapped B5 raw type {raw_type!r} to semantic type {object_type.value!r}.",
                    object_id=raw_id,
                    source_ref=source_ref,
                    details={"raw_type": raw_type, "semantic_type": object_type.value},
                )
            )
        state = _initial_reliability_state(raw_obj, object_type)
        source_refs = _source_refs_for_raw_object(raw_obj)
        risk_flags = _risk_flags_for_raw_object(raw_obj)
        obj = SemanticObject(
            object_id=raw_id,
            object_type=object_type,
            subtype=raw_type,
            raw_id=raw_id,
            source_ref=source_ref,
            reliability_state=state,
            fields={
                key: value
                for key, value in raw_obj.items()
                if key not in {"id", "type"}
            },
            source_refs=source_refs,
            risk_flags=risk_flags,
        )
        objects.append(obj)
    lookup = {obj.object_id: obj for obj in objects}
    return objects, lookup, diagnostics


def _normalize_edges(
    paths: B5TaskBundlePaths,
    object_graph: dict[str, Any],
    object_lookup: dict[str, SemanticObject],
) -> tuple[list[SemanticEdge], list[SemanticObject], list[Diagnostic]]:
    edges: list[SemanticEdge] = []
    diagnostics: list[Diagnostic] = []
    implicit_lookup: dict[str, SemanticObject] = {}
    for index, raw in enumerate(object_graph.get("edges", [])):
        raw_edge = _dict(raw)
        raw_source = str(raw_edge.get("from") or raw_edge.get("source") or "")
        raw_target = str(raw_edge.get("to") or raw_edge.get("target") or "")
        raw_relation = str(raw_edge.get("relation") or raw_edge.get("rel") or "")
        source_ref = f"{_rel(paths.object_graph)}#/edges/{index}"
        for endpoint in (raw_source, raw_target):
            if endpoint not in object_lookup and endpoint not in implicit_lookup:
                parent = _parent_id(endpoint)
                implicit_type = _implicit_type_for_id(endpoint)
                implicit = SemanticObject(
                    object_id=endpoint,
                    object_type=implicit_type,
                    subtype="implicit_legacy_object",
                    raw_id=endpoint,
                    source_ref=source_ref,
                    reliability_state=ReliabilityState.UNVERIFIED,
                    fields={
                        "parent_object_id": parent,
                        "reason": "edge endpoint references a legacy subfield",
                    },
                    risk_flags=("implicit_legacy_object",),
                )
                implicit_lookup[endpoint] = implicit
                diagnostics.append(
                    Diagnostic(
                        code="implicit_legacy_object",
                        severity="warning",
                        message="Created virtual object for B5 edge endpoint that was not declared in object_graph.objects.",
                        object_id=endpoint,
                        source_ref=source_ref,
                        details={"parent_object_id": parent},
                    )
                )
        edge_type, direction, note = _map_edge(
            raw_relation, raw_source, raw_target, object_lookup | implicit_lookup
        )
        if direction == "reverse":
            source_id, target_id = raw_target, raw_source
        else:
            source_id, target_id = raw_source, raw_target
        if note:
            diagnostics.append(
                Diagnostic(
                    code="raw_edge_direction_uncertain",
                    severity="warning",
                    message=note,
                    object_id=f"{raw_source}->{raw_target}",
                    source_ref=source_ref,
                    details={
                        "raw_relation": raw_relation,
                        "canonical_edge_type": edge_type.value,
                    },
                )
            )
        edges.append(
            SemanticEdge(
                edge_id=f"edge.{index + 1}.{_slug(raw_source)}.{_slug(raw_target)}",
                source_object_id=source_id,
                target_object_id=target_id,
                edge_type=edge_type,
                raw_relation=raw_relation,
                raw_source_id=raw_source,
                raw_target_id=raw_target,
                canonicalization_notes=note
                or "B5 edge interpreted as upstream support/input to downstream dependent.",
                source_ref=source_ref,
                meta={
                    key: value
                    for key, value in raw_edge.items()
                    if key not in {"from", "to", "source", "target", "relation", "rel"}
                },
            )
        )
    return edges, list(implicit_lookup.values()), diagnostics


def _normalize_gate(
    paths: B5TaskBundlePaths,
    gate_log: dict[str, Any],
    verification_report: dict[str, Any],
    object_graph: dict[str, Any],
    object_lookup: dict[str, SemanticObject],
) -> tuple[
    GateDecision,
    SemanticObject,
    list[SemanticEdge],
    list[ValidityLedgerEntry],
    list[Diagnostic],
]:
    diagnostics: list[Diagnostic] = []
    raw_verdict = str(gate_log.get("advance_or_block", ""))
    verdict = LEGACY_GATE_VERDICT_MAP.get(raw_verdict, GateVerdict.NEEDS_REVIEW)
    if raw_verdict not in LEGACY_GATE_VERDICT_MAP:
        diagnostics.append(
            Diagnostic(
                code="unknown_b5_gate_verdict",
                severity="warning",
                message=f"Unknown B5 gate verdict {raw_verdict!r}; mapped to needs_review.",
                source_ref=f"{_rel(paths.gate_log)}#/advance_or_block",
            )
        )
    gate_id = f"gate.{paths.task_id}"
    reasons = tuple(str(item) for item in _list(gate_log.get("reasons")))
    missing_evidence = tuple(
        str(item) for item in _list(gate_log.get("missing_evidence"))
    )
    risks = tuple(str(item) for item in _list(verification_report.get("risks")))
    evidence_refs = tuple(
        f"{_rel(paths.gate_log)}#/reasons/{index}" for index, _ in enumerate(reasons)
    ) + tuple(
        f"{_rel(paths.verification_report)}#/checks/{index}"
        for index, _ in enumerate(_list(verification_report.get("checks")))
    )
    invalidated_ids = _resolve_refs(
        _list(gate_log.get("invalidated_objects")), object_lookup
    )
    preserved_refs = _preserved_refs(gate_log, object_graph, object_lookup)
    if verdict == GateVerdict.BLOCK:
        target_ids = invalidated_ids or tuple(object_lookup)
    else:
        target_ids = _resolve_refs(
            _list(gate_log.get("preserved_objects")), object_lookup
        ) or tuple(object_lookup)

    gate = GateDecision(
        gate_id=gate_id,
        stage=_stage_from_task(paths.task_id, object_lookup),
        verdict=verdict,
        criteria=reasons + tuple(f"missing: {item}" for item in missing_evidence),
        evidence_refs=evidence_refs,
        target_object_ids=target_ids,
        invalidated_object_ids=invalidated_ids,
        preserved_object_refs=preserved_refs,
        raw_verdict=raw_verdict,
        source_ref=str(_rel(paths.gate_log)),
        risk_flags=risks,
    )
    gate_state = (
        ReliabilityState.BLOCKED
        if verdict == GateVerdict.BLOCK
        else ReliabilityState.PASSED
    )
    gate_obj = SemanticObject(
        object_id=gate_id,
        object_type=ObjectType.GATE_DECISION,
        subtype="b5_gate_log",
        raw_id=gate_id,
        source_ref=str(_rel(paths.gate_log)),
        reliability_state=gate_state,
        fields={
            "raw_verdict": raw_verdict,
            "reasons": list(reasons),
            "missing_evidence": list(missing_evidence),
        },
        risk_flags=risks,
    )

    edges: list[SemanticEdge] = []
    for index, object_id in enumerate(target_ids):
        edge_type = (
            EdgeType.INVALIDATES if object_id in invalidated_ids else EdgeType.VERIFIES
        )
        edges.append(
            SemanticEdge(
                edge_id=f"edge.gate.{index + 1}.{_slug(object_id)}",
                source_object_id=object_id,
                target_object_id=gate_id,
                edge_type=edge_type,
                raw_relation="gate_target",
                source_ref=str(_rel(paths.gate_log)),
                canonicalization_notes="Gate decision depends on target object state.",
            )
        )

    ledger: list[ValidityLedgerEntry] = []
    evidence_ref = evidence_refs[0] if evidence_refs else str(_rel(paths.gate_log))
    ledger.append(
        ValidityLedgerEntry(
            entry_id=f"ledger.{_slug(gate_id)}.gate",
            object_id=gate_id,
            from_state=ReliabilityState.UNVERIFIED,
            to_state=gate_state,
            reason=f"B5 gate verdict {raw_verdict}",
            evidence_ref=evidence_ref,
            gate_id=gate_id,
        )
    )
    for index, object_id in enumerate(invalidated_ids):
        ledger.append(
            ValidityLedgerEntry(
                entry_id=f"ledger.{_slug(object_id)}.invalidated.{index + 1}",
                object_id=object_id,
                from_state=ReliabilityState.UNVERIFIED,
                to_state=ReliabilityState.BLOCKED,
                reason="B5 gate marked object invalidated/blocked.",
                evidence_ref=evidence_ref,
                gate_id=gate_id,
            )
        )
    if verdict in {GateVerdict.PASS, GateVerdict.PASS_WITH_CAVEAT}:
        target_state = (
            ReliabilityState.PASSED
            if verdict == GateVerdict.PASS
            else ReliabilityState.PARTIALLY_SUPPORTED
        )
        for index, object_id in enumerate(target_ids):
            if object_id == gate_id:
                continue
            ledger.append(
                ValidityLedgerEntry(
                    entry_id=f"ledger.{_slug(object_id)}.gate_pass.{index + 1}",
                    object_id=object_id,
                    from_state=ReliabilityState.UNVERIFIED,
                    to_state=target_state,
                    reason="B5 gate allowed advancement for this target under legacy smoke criteria.",
                    evidence_ref=evidence_ref,
                    gate_id=gate_id,
                )
            )
    return gate, gate_obj, edges, ledger, diagnostics


def _normalize_verification(
    paths: B5TaskBundlePaths, verification_report: dict[str, Any], gate_id: str
) -> list[VerificationSignal]:
    signals: list[VerificationSignal] = []
    risks = tuple(str(item) for item in _list(verification_report.get("risks")))
    for index, raw in enumerate(_list(verification_report.get("checks"))):
        check = _dict(raw)
        check_id = str(check.get("check") or check.get("name") or f"check_{index + 1}")
        passed, label = _normalize_check_result(check)
        signal_type = (
            "gate_consistency"
            if any(
                term in check_id.lower()
                for term in ("gate", "risk", "rollback", "coherence")
            )
            else "deterministic"
        )
        signals.append(
            VerificationSignal(
                signal_id=f"verify.{_slug(paths.task_id)}.{index + 1}",
                check_id=check_id,
                passed=passed,
                label=label,
                evidence_summary=str(
                    check.get("detail")
                    or check.get("notes")
                    or check.get("result")
                    or ""
                ),
                target_object_ids=(gate_id,),
                signal_type=signal_type,
                source_ref=f"{_rel(paths.verification_report)}#/checks/{index}",
                risk_flags=risks,
            )
        )
    return signals


def _normalize_run_trace(
    paths: B5TaskBundlePaths, run_trace_raw: dict[str, Any]
) -> tuple[RunTrace, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    model_manifest = _dict(run_trace_raw.get("model_manifest"))
    tool_manifest = _dict(run_trace_raw.get("tool_manifest"))
    budget_manifest = _dict(run_trace_raw.get("budget_manifest"))
    trace = _dict(run_trace_raw.get("trace"))
    cost_trace = _dict(trace.get("cost_trace"))
    retrieved_sources = _list(trace.get("retrieved_sources"))
    token_usage = budget_manifest.get("token_usage")
    risk_flags: list[str] = []
    if token_usage is None or cost_trace.get("estimated_tokens") is None:
        risk_flags.append("cost_unknown")
        diagnostics.append(
            Diagnostic(
                code="cost_unknown",
                severity="warning",
                message="B5 cursor_agent run trace has null token/cost fields.",
                source_ref=f"{_rel(paths.run_trace)}#/budget_manifest",
            )
        )
    if not retrieved_sources:
        risk_flags.append("retrieval_trace_incomplete")
        diagnostics.append(
            Diagnostic(
                code="retrieval_trace_incomplete",
                severity="warning",
                message="B5 run_trace retrieved_sources is empty; provenance is self-reported/incomplete.",
                source_ref=f"{_rel(paths.run_trace)}#/trace/retrieved_sources",
            )
        )
    return (
        RunTrace(
            trace_id=str(run_trace_raw.get("run_id") or f"trace.{paths.task_id}"),
            provider=str(model_manifest.get("provider", "")),
            model=str(model_manifest.get("model", "")),
            runner=str(model_manifest.get("runner", "")),
            allowed_tools=tuple(
                str(item) for item in _list(tool_manifest.get("tools"))
            ),
            gold_visible=tool_manifest.get("gold_visible"),
            judge_visible=tool_manifest.get("judge_visible"),
            wall_clock_seconds=budget_manifest.get("wall_clock_seconds"),
            token_usage=token_usage,
            cost_trace=cost_trace,
            retrieved_sources_count=len(retrieved_sources),
            started_at=str(run_trace_raw.get("started_at", "")),
            finished_at=str(run_trace_raw.get("finished_at", "")),
            risk_flags=tuple(risk_flags),
            raw_ref=str(_rel(paths.run_trace)),
        ),
        diagnostics,
    )


def _ledger_from_verification(
    paths: B5TaskBundlePaths,
    verification_signals: list[VerificationSignal],
    gate: GateDecision,
) -> list[ValidityLedgerEntry]:
    entries: list[ValidityLedgerEntry] = []
    for index, signal in enumerate(verification_signals):
        if signal.passed is False:
            to_state = ReliabilityState.BLOCKED
        elif signal.passed is None:
            to_state = ReliabilityState.NEEDS_HUMAN_REVIEW
        else:
            continue
        entries.append(
            ValidityLedgerEntry(
                entry_id=f"ledger.{_slug(signal.signal_id)}",
                object_id=gate.gate_id,
                from_state=ReliabilityState.UNVERIFIED,
                to_state=to_state,
                reason=f"Verification check {signal.check_id!r} label={signal.label!r}",
                evidence_ref=signal.source_ref
                or f"{_rel(paths.verification_report)}#/checks/{index}",
                gate_id=gate.gate_id,
                signal_id=signal.signal_id,
            )
        )
    return entries


def _derive_rollback_cones(
    bundle: SemanticGovernanceBundle,
    gate: GateDecision,
    edges: list[SemanticEdge],
) -> list[Any]:
    triggers: list[str] = []
    invalidated = set(gate.invalidated_object_ids)
    for edge in edges:
        if (
            edge.target_object_id in invalidated
            and edge.source_object_id not in invalidated
        ):
            if (
                edge.edge_type
                in {
                    EdgeType.INVALIDATES,
                    EdgeType.CONTRADICTED_BY,
                    EdgeType.DERIVED_FROM,
                }
                or "contamin" in edge.raw_relation
            ):
                triggers.append(edge.source_object_id)
    triggers.extend(gate.invalidated_object_ids)
    cones = []
    seen: set[str] = set()
    for trigger in triggers:
        if trigger in seen or trigger not in bundle.object_ids:
            continue
        seen.add(trigger)
        cones.append(compute_rollback_cone(bundle, trigger))
    return cones


def _aggregate_context(
    combined_eval_summary: dict[str, Any], task_id: str, baseline_id: str
) -> dict[str, Any]:
    if not combined_eval_summary:
        return {}
    row = combined_row_for_task(combined_eval_summary, task_id, baseline_id)
    return {
        "combined_summary_schema_version": combined_eval_summary.get("schema_version"),
        "process_gate_threshold": combined_eval_summary.get("process_gate_threshold"),
        "combined_row": row,
    }


def _map_object_type(raw_obj: dict[str, Any]) -> ObjectType:
    raw_type = str(raw_obj.get("type", "")).lower()
    stage = str(raw_obj.get("stage", "")).lower()
    if raw_type == "paper":
        return ObjectType.PAPER
    if raw_type in {"candidate_paper", "distractor", "prior_card"}:
        return ObjectType.PAPER
    if raw_type in {"evidence_span", "input_evidence"}:
        return ObjectType.EVIDENCE_SPAN
    if raw_type in {"claim", "proposal", "novelty_verdict"}:
        return ObjectType.CLAIM
    if raw_type in {"draft"}:
        return ObjectType.SECTION_DRAFT
    if raw_type == "stage_output":
        if stage == "literature":
            return ObjectType.BASELINE
        if stage == "writing":
            return ObjectType.SECTION_DRAFT
        return ObjectType.CLAIM
    if raw_type in {"artifact_request"}:
        return ObjectType.CODE_ARTIFACT
    if raw_type == "task":
        return ObjectType.CODE_ARTIFACT
    return ObjectType.CODE_ARTIFACT


def _implicit_type_for_id(object_id: str) -> ObjectType:
    lowered = object_id.lower()
    if "gap_claim" in lowered or "claim" in lowered:
        return ObjectType.CLAIM
    if "baseline" in lowered or "prior" in lowered:
        return ObjectType.BASELINE
    if "draft" in lowered or "section" in lowered:
        return ObjectType.SECTION_DRAFT
    if lowered.startswith("ev.") or "evidence" in lowered:
        return ObjectType.EVIDENCE_SPAN
    return ObjectType.CLAIM


def _initial_reliability_state(
    raw_obj: dict[str, Any], object_type: ObjectType
) -> ReliabilityState:
    status = str(raw_obj.get("status", "")).lower()
    if status in {"invalidated", "blocked"}:
        return ReliabilityState.BLOCKED
    if object_type in {ObjectType.PAPER, ObjectType.EVIDENCE_SPAN, ObjectType.BASELINE}:
        return ReliabilityState.RETRIEVED
    return ReliabilityState.UNVERIFIED


def _source_refs_for_raw_object(raw_obj: dict[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    fields = _dict(raw_obj.get("fields"))
    for container in (raw_obj, fields):
        for key in ("paper_id", "ref"):
            if key in container and container[key] not in (None, ""):
                refs.append(f"paper:{container[key]}")
        for key in ("evidence_id", "citation_link_id", "baseline_id"):
            if key in container and container[key] not in (None, ""):
                refs.append(f"{key}:{container[key]}")
    return tuple(_dedupe(refs))


def _risk_flags_for_raw_object(raw_obj: dict[str, Any]) -> tuple[str, ...]:
    flags: list[str] = []
    status = str(raw_obj.get("status", "")).lower()
    if status == "invalidated":
        flags.append("raw_invalidated")
    if raw_obj.get("reason"):
        flags.append("legacy_reason_present")
    return tuple(flags)


def _map_edge(
    raw_relation: str,
    raw_source: str,
    raw_target: str,
    lookup: dict[str, SemanticObject],
) -> tuple[EdgeType, str, str]:
    rel = raw_relation.lower()
    direction = "as_is"
    note = ""
    if "contradict" in rel:
        edge_type = EdgeType.CONTRADICTED_BY
    elif "invalid" in rel or "contamin" in rel:
        edge_type = EdgeType.INVALIDATES
    elif "support" in rel and "partial" in rel:
        edge_type = EdgeType.PARTIALLY_SUPPORTED_BY
    elif "support" in rel or "permits_binding" in rel:
        edge_type = EdgeType.SUPPORTED_BY
    elif "cite" in rel:
        edge_type = EdgeType.CITES
    elif any(
        term in rel
        for term in (
            "overlap",
            "align",
            "different",
            "mutually_exclusive",
            "weak_year",
            "comparator",
        )
    ):
        edge_type = EdgeType.COMPARES_TO
    elif any(term in rel for term in ("required", "requested", "consumes")):
        edge_type = EdgeType.CONSUMES
    elif "verify" in rel or "check" in rel:
        edge_type = EdgeType.VERIFIES
    elif "amplification" in rel or "derived" in rel:
        edge_type = EdgeType.DERIVED_FROM
    else:
        edge_type = EdgeType.DERIVED_FROM
        note = "B5 relation was not in the v0.1 vocabulary; kept as derived_from with raw relation preserved."

    source_obj = lookup.get(raw_source)
    target_obj = lookup.get(raw_target)
    if source_obj and target_obj:
        if (
            source_obj.object_type in {ObjectType.CLAIM, ObjectType.SECTION_DRAFT}
            and target_obj.object_type
            in {ObjectType.PAPER, ObjectType.EVIDENCE_SPAN, ObjectType.BASELINE}
            and edge_type
            in {
                EdgeType.SUPPORTED_BY,
                EdgeType.PARTIALLY_SUPPORTED_BY,
                EdgeType.CONTRADICTED_BY,
                EdgeType.COMPARES_TO,
            }
        ):
            direction = "reverse"
            note = (
                note
                or "Raw B5 edge pointed dependent→evidence; canonical dependency direction is evidence/input→dependent."
            )
    return edge_type, direction, note


def _resolve_refs(
    raw_refs: list[Any], object_lookup: dict[str, SemanticObject]
) -> tuple[str, ...]:
    resolved: list[str] = []
    for raw in raw_refs:
        text = str(raw)
        candidates = [text, f"obj.{text}"]
        candidates.extend(
            object_id for object_id in object_lookup if object_id.endswith(f".{text}")
        )
        for candidate in candidates:
            if candidate in object_lookup:
                resolved.append(candidate)
                break
    return tuple(_dedupe(resolved))


def _preserved_refs(
    gate_log: dict[str, Any],
    object_graph: dict[str, Any],
    object_lookup: dict[str, SemanticObject],
) -> tuple[str, ...]:
    preserved: list[str] = [
        str(item) for item in _list(gate_log.get("preserved_objects"))
    ]
    preserved.extend(
        _resolve_refs(_list(gate_log.get("preserved_objects")), object_lookup)
    )
    invalidated = set(
        _resolve_refs(_list(gate_log.get("invalidated_objects")), object_lookup)
    )
    for raw_edge in _list(object_graph.get("edges")):
        edge = _dict(raw_edge)
        relation = str(edge.get("relation") or edge.get("rel") or "").lower()
        source = str(edge.get("from") or edge.get("source") or "")
        target = str(edge.get("to") or edge.get("target") or "")
        if (
            "supports_included_baseline" in relation
            or "supports" in relation
            and "included" in relation
        ):
            if source not in invalidated:
                preserved.append(source)
            if target not in invalidated:
                preserved.append(target)
    for obj in object_lookup.values():
        if obj.object_id not in invalidated and obj.object_type in {
            ObjectType.EVIDENCE_SPAN,
            ObjectType.PAPER,
            ObjectType.BASELINE,
        }:
            if any(obj.object_id in item for item in preserved) or any(
                ref in " ".join(preserved) for ref in obj.source_refs
            ):
                preserved.append(obj.object_id)
            for ref in obj.source_refs:
                if any(ref.split(":", 1)[-1] in item for item in preserved):
                    preserved.append(ref)
    return tuple(_dedupe(preserved))


def _normalize_check_result(check: dict[str, Any]) -> tuple[bool | None, str]:
    if "pass" in check:
        passed = bool(check.get("pass"))
        return passed, "pass" if passed else "fail"
    if "passed" in check:
        passed = bool(check.get("passed"))
        return passed, "pass" if passed else "fail"
    label = str(check.get("result") or check.get("verdict") or "unknown").lower()
    if label in POSITIVE_RESULT_LABELS:
        return True, label
    if label in NEGATIVE_RESULT_LABELS:
        return False, label
    if label in UNCERTAIN_RESULT_LABELS or "warn" in label:
        return None, label
    return None, label


def _stage_from_task(task_id: str, object_lookup: dict[str, SemanticObject]) -> str:
    if ".literature." in task_id:
        return "literature"
    if ".synthesis." in task_id:
        return "writing"
    if ".planning." in task_id:
        return "planning"
    if ".governance." in task_id:
        return "governance"
    if ".cross_stage." in task_id:
        return "rollback"
    stages = {
        str(obj.fields.get("stage"))
        for obj in object_lookup.values()
        if obj.fields.get("stage")
    }
    return sorted(stages)[0] if stages else "unknown"


def _parent_id(object_id: str) -> str:
    if "." not in object_id:
        return ""
    return object_id.rsplit(".", 1)[0]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "item"


def _rel(path: Path) -> str:
    return path.name


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
