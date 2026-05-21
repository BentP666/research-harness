import pytest

from research_harness.semantic_governance.models import (
    EdgeType,
    GateDecision,
    GateVerdict,
    ReliabilityState,
    SemanticEdge,
    SemanticGovernanceBundle,
    SemanticObject,
    ValidityLedgerEntry,
)
from research_harness.semantic_governance.validators import validate_bundle


def test_semantic_object_requires_id_and_known_type():
    with pytest.raises(ValueError, match="object_id"):
        SemanticObject(object_id="", object_type="claim")

    with pytest.raises(ValueError, match="object_type"):
        SemanticObject(object_id="obj.x", object_type="legacy_unknown_type")


def test_semantic_edge_requires_canonical_source_and_target():
    with pytest.raises(ValueError, match="source_object_id"):
        SemanticEdge(
            edge_id="edge.missing_source",
            source_object_id="",
            target_object_id="obj.target",
            edge_type=EdgeType.DERIVED_FROM,
        )

    with pytest.raises(ValueError, match="target_object_id"):
        SemanticEdge(
            edge_id="edge.missing_target",
            source_object_id="obj.source",
            target_object_id="",
            edge_type=EdgeType.DERIVED_FROM,
        )


def test_validity_ledger_requires_evidence_ref():
    with pytest.raises(ValueError, match="evidence_ref"):
        ValidityLedgerEntry(
            entry_id="ledger.no_evidence",
            object_id="obj.claim",
            from_state=ReliabilityState.UNVERIFIED,
            to_state=ReliabilityState.BLOCKED,
            reason="No support",
            evidence_ref="",
        )


def test_strict_validator_rejects_pass_gate_without_evidence():
    obj = SemanticObject(object_id="obj.claim", object_type="claim")
    gate = GateDecision(
        gate_id="gate.pass_without_evidence",
        stage="write",
        verdict=GateVerdict.PASS,
        evidence_refs=(),
        target_object_ids=("obj.claim",),
    )
    bundle = SemanticGovernanceBundle(
        task_id="task.strict_gate",
        baseline_id="B5.full_rh",
        source_run_root="memory",
        objects=(obj,),
        edges=(),
        gate_decisions=(gate,),
    )

    report = validate_bundle(bundle, mode="strict")

    assert not report.is_valid
    assert any(d.code == "gate_pass_without_evidence" for d in report.diagnostics)


def test_model_to_dict_is_json_compatible():
    obj = SemanticObject(
        object_id="obj.claim",
        object_type="claim",
        reliability_state="span_supported",
        source_refs=("paper:2057",),
    )
    edge = SemanticEdge(
        edge_id="edge.1",
        source_object_id="ev.1",
        target_object_id="obj.claim",
        edge_type="supported_by",
    )

    payload = {"object": obj.to_dict(), "edge": edge.to_dict()}

    assert payload["object"]["object_type"] == "claim"
    assert payload["object"]["reliability_state"] == "span_supported"
    assert payload["object"]["source_refs"] == ["paper:2057"]
    assert payload["edge"]["edge_type"] == "supported_by"
