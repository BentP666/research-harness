from research_harness.semantic_governance.models import (
    Diagnostic,
    EdgeType,
    GateDecision,
    GateVerdict,
    ObjectType,
    ReliabilityState,
    RollbackAction,
    RollbackCone,
    SemanticEdge,
    SemanticGovernanceBundle,
    SemanticObject,
    ValidityLedgerEntry,
    VerificationSignal,
)
from research_harness.semantic_governance.validators import validate_bundle


def _native_strict_bundle() -> SemanticGovernanceBundle:
    evidence = SemanticObject(
        object_id="evidence.supporting_span",
        object_type=ObjectType.EVIDENCE_SPAN,
        reliability_state=ReliabilityState.SPAN_SUPPORTED,
        source_ref="native_fixture#/objects/evidence",
    )
    claim = SemanticObject(
        object_id="claim.supported",
        object_type=ObjectType.CLAIM,
        reliability_state=ReliabilityState.PASSED,
        source_ref="native_fixture#/objects/claim",
    )
    gate_object = SemanticObject(
        object_id="gate.native",
        object_type=ObjectType.GATE_DECISION,
        reliability_state=ReliabilityState.PASSED,
        source_ref="native_fixture#/gate",
    )
    return SemanticGovernanceBundle(
        task_id="rfb.native.strict_fixture.0001",
        baseline_id="B5.full_rh",
        source_run_root="memory://native_strict_fixture",
        objects=(evidence, claim, gate_object),
        edges=(
            SemanticEdge(
                edge_id="edge.evidence_to_claim",
                source_object_id=evidence.object_id,
                target_object_id=claim.object_id,
                edge_type=EdgeType.SUPPORTED_BY,
            ),
            SemanticEdge(
                edge_id="edge.claim_to_gate",
                source_object_id=claim.object_id,
                target_object_id=gate_object.object_id,
                edge_type=EdgeType.VERIFIES,
            ),
        ),
        gate_decisions=(
            GateDecision(
                gate_id=gate_object.object_id,
                stage="synthesis",
                verdict=GateVerdict.PASS,
                evidence_refs=("native_fixture#/evidence/supporting_span",),
                target_object_ids=(claim.object_id,),
            ),
        ),
        verification_signals=(
            VerificationSignal(
                signal_id="verify.native.support",
                check_id="support_state",
                passed=True,
                label="pass",
                target_object_ids=(claim.object_id,),
                source_ref="native_fixture#/checks/support_state",
            ),
        ),
        validity_ledger=(
            ValidityLedgerEntry(
                entry_id="ledger.claim.passed",
                object_id=claim.object_id,
                from_state=ReliabilityState.UNVERIFIED,
                to_state=ReliabilityState.PASSED,
                reason="Native strict fixture support check passed.",
                evidence_ref="native_fixture#/checks/support_state",
                gate_id=gate_object.object_id,
                signal_id="verify.native.support",
            ),
            ValidityLedgerEntry(
                entry_id="ledger.gate.passed",
                object_id=gate_object.object_id,
                from_state=ReliabilityState.UNVERIFIED,
                to_state=ReliabilityState.PASSED,
                reason="Native strict fixture gate passed.",
                evidence_ref="native_fixture#/gate",
                gate_id=gate_object.object_id,
            ),
        ),
    )


def _diagnostic_codes(
    bundle: SemanticGovernanceBundle, mode: str = "strict"
) -> set[str]:
    return {
        diagnostic.code for diagnostic in validate_bundle(bundle, mode=mode).diagnostics
    }


def test_native_semantic_governance_fixture_passes_strict_mode():
    report = validate_bundle(_native_strict_bundle(), mode="strict")

    assert report.is_valid
    assert report.to_dict()["mode"] == "strict"


def test_duplicate_object_ids_remain_deterministic_errors():
    bundle = _native_strict_bundle()
    duplicate_bundle = SemanticGovernanceBundle(
        task_id=bundle.task_id,
        baseline_id=bundle.baseline_id,
        source_run_root=bundle.source_run_root,
        objects=bundle.objects + (bundle.objects[0],),
        edges=bundle.edges,
        gate_decisions=bundle.gate_decisions,
    )

    assert "duplicate_object_id" in _diagnostic_codes(duplicate_bundle)


def test_strict_validator_rejects_reversed_evidence_support_edges():
    evidence = SemanticObject(object_id="evidence.1", object_type="evidence_span")
    claim = SemanticObject(object_id="claim.1", object_type="claim")
    gate = SemanticObject(
        object_id="gate.1", object_type="gate_decision", reliability_state="passed"
    )
    bundle = SemanticGovernanceBundle(
        task_id="task.reversed_edge",
        baseline_id="B5.full_rh",
        source_run_root="memory",
        objects=(evidence, claim, gate),
        edges=(
            SemanticEdge(
                edge_id="edge.reversed",
                source_object_id=claim.object_id,
                target_object_id=evidence.object_id,
                edge_type=EdgeType.SUPPORTED_BY,
            ),
        ),
        gate_decisions=(
            GateDecision(
                gate_id=gate.object_id,
                stage="synthesis",
                verdict=GateVerdict.PASS,
                evidence_refs=("native_fixture#/edge",),
                target_object_ids=(claim.object_id,),
            ),
        ),
    )

    assert "edge_direction_inconsistent" in _diagnostic_codes(bundle)


def test_pass_gate_rejects_blocked_target_state():
    claim = SemanticObject(
        object_id="claim.blocked",
        object_type="claim",
        reliability_state=ReliabilityState.BLOCKED,
    )
    gate = SemanticObject(
        object_id="gate.pass", object_type="gate_decision", reliability_state="passed"
    )
    bundle = SemanticGovernanceBundle(
        task_id="task.gate_state",
        baseline_id="B5.full_rh",
        source_run_root="memory",
        objects=(claim, gate),
        edges=(),
        gate_decisions=(
            GateDecision(
                gate_id=gate.object_id,
                stage="write",
                verdict=GateVerdict.PASS,
                evidence_refs=("native_fixture#/gate",),
                target_object_ids=(claim.object_id,),
            ),
        ),
    )

    assert "gate_passes_invalid_target_state" in _diagnostic_codes(bundle)


def test_ledger_references_gate_signal_and_final_state_consistently():
    bundle = _native_strict_bundle()
    bad_entry = ValidityLedgerEntry(
        entry_id="ledger.bad_refs",
        object_id="claim.supported",
        from_state=ReliabilityState.UNVERIFIED,
        to_state=ReliabilityState.BLOCKED,
        reason="Invalid references and final state for contract hardening test.",
        evidence_ref="native_fixture#/bad",
        gate_id="gate.missing",
        signal_id="signal.missing",
    )
    bad_bundle = SemanticGovernanceBundle(
        task_id=bundle.task_id,
        baseline_id=bundle.baseline_id,
        source_run_root=bundle.source_run_root,
        objects=bundle.objects,
        edges=bundle.edges,
        gate_decisions=bundle.gate_decisions,
        verification_signals=bundle.verification_signals,
        validity_ledger=bundle.validity_ledger + (bad_entry,),
    )

    codes = _diagnostic_codes(bad_bundle)

    assert "ledger_gate_missing" in codes
    assert "ledger_signal_missing" in codes
    assert "ledger_final_state_mismatch" in codes


def test_rollback_cone_must_cover_transitive_downstream_objects():
    evidence = SemanticObject(object_id="evidence.trigger", object_type="evidence_span")
    claim = SemanticObject(object_id="claim.downstream", object_type="claim")
    draft = SemanticObject(object_id="draft.downstream", object_type="section_draft")
    bundle = SemanticGovernanceBundle(
        task_id="task.rollback_coverage",
        baseline_id="B5.full_rh",
        source_run_root="memory",
        objects=(evidence, claim, draft),
        edges=(
            SemanticEdge(
                "edge.1", evidence.object_id, claim.object_id, EdgeType.INVALIDATES
            ),
            SemanticEdge(
                "edge.2", claim.object_id, draft.object_id, EdgeType.DERIVED_FROM
            ),
        ),
        gate_decisions=(),
        rollback_cones=(
            RollbackCone(
                trigger_object_id=evidence.object_id,
                affected_object_ids=(claim.object_id,),
                required_actions=(RollbackAction.REVALIDATE,),
            ),
        ),
    )

    assert "rollback_cone_missing_downstream" in _diagnostic_codes(bundle)


def test_strict_mode_rejects_legacy_only_diagnostics_on_otherwise_native_bundle():
    bundle = _native_strict_bundle()
    legacy_diag_bundle = SemanticGovernanceBundle(
        task_id=bundle.task_id,
        baseline_id=bundle.baseline_id,
        source_run_root=bundle.source_run_root,
        objects=bundle.objects,
        edges=bundle.edges,
        gate_decisions=bundle.gate_decisions,
        verification_signals=bundle.verification_signals,
        validity_ledger=bundle.validity_ledger,
        diagnostics=(
            Diagnostic(
                code="implicit_legacy_object",
                severity="warning",
                message="Legacy virtual object should not be accepted by strict-native fixtures.",
            ),
        ),
    )

    assert "strict_rejects_legacy_diagnostic" in _diagnostic_codes(legacy_diag_bundle)
