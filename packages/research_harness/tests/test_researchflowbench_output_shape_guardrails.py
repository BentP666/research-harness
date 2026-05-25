from __future__ import annotations

import pytest

from research_harness.eval.researchflowbench.output_shape import (
    COMMON_RUNNER_ARTIFACTS,
    validate_output_shape,
)


B1 = "B1.no_governance_workflow_agent"
B2 = "B2.retrieval_only_citation_list_agent"
B3 = "B3.citation_verifier_only"
B4 = "B4.generic_trace_only"
B5 = "B5.full_rh"


def _violation_families(report) -> set[str]:
    return {violation.family for violation in report.violations}


def _violation_codes(report) -> set[str]:
    return {violation.code for violation in report.violations}


def test_b1_rejects_graph_gate_ledger_and_rollback_shape():
    report = validate_output_shape(
        B1,
        agent_output={
            "answer": {"diagnosis": "direct visible-record answer"},
            "confidence": 0.72,
            "object_graph": {"nodes": []},
            "semantic_objects": [{"id": "claim.1", "object_type": "claim"}],
            "gate_decision": {"verdict": "pass_with_caveat"},
            "validity_ledger": [{"object_id": "claim.1", "state": "valid"}],
            "rollback_cone": {"affected_objects": ["claim.1"]},
            "rollback_actions": ["mark_downstream_stale"],
        },
    )

    assert not report.shape_pass
    assert {
        "semantic_object_graph",
        "gate",
        "validity_ledger",
        "rollback",
    }.issubset(_violation_families(report))


def test_b2_allows_citation_candidate_lists_but_rejects_rh_governance():
    positive = validate_output_shape(
        B2,
        agent_output={
            "answer": {"diagnosis": "source R1 is the closest match"},
            "citation_list": [{"record_id": "R1", "rank": 1}],
            "candidate_ranking": [
                {"record_id": "R1", "role": "selected"},
                {"record_id": "R2", "role": "distractor"},
            ],
            "retrieval_summary": {
                "external_search_used": False,
                "selected_record_ids": ["R1"],
                "rejected_record_ids": ["R2"],
            },
        },
    )

    assert positive.shape_pass, positive.to_dict()
    assert "retrieval_list" in positive.allowed_capabilities_detected

    negative = validate_output_shape(
        B2,
        agent_output={
            "answer": {"diagnosis": "source R1 is the closest match"},
            "citation_list": [{"record_id": "R1", "rank": 1}],
            "candidate_ranking": [{"record_id": "R1", "role": "selected"}],
            "object_graph": {"nodes": [{"id": "claim.1"}], "edges": []},
            "gate_decision": {"verdict": "block"},
            "validity_ledger": [{"object_id": "claim.1", "state": "stale"}],
            "rollback_actions": ["invalidate_claim"],
            "retrieval_summary": {"external_search_used": True},
        },
    )

    assert not negative.shape_pass
    assert {
        "semantic_object_graph",
        "gate",
        "validity_ledger",
        "rollback",
    }.issubset(_violation_families(negative))
    assert "external_search" in _violation_families(negative)


def test_b3_allows_span_citation_support_matrix_but_rejects_graph_gate_rollback():
    positive = validate_output_shape(
        B3,
        agent_output={
            "final_answer": {"diagnosis": "claim is only partially supported"},
            "span_support_matrix": [
                {
                    "claim_span": "C1",
                    "evidence_id": "R1",
                    "support_label": "partially_supported",
                }
            ],
            "citation_support_report": {
                "clauses": [{"id": "C1", "support_label": "ambiguous"}]
            },
            "rewrite_suggestions": ["Hedge the unsupported clause."],
        },
    )

    assert positive.shape_pass, positive.to_dict()
    assert "citation_verification" in positive.allowed_capabilities_detected

    negative = validate_output_shape(
        B3,
        agent_output={
            "span_support_matrix": [
                {
                    "claim_span": "C1",
                    "evidence_id": "R1",
                    "support_label": "supported",
                }
            ],
            "dependency_graph": {"edges": [{"source": "C1", "target": "S1"}]},
            "object_graph": {"nodes": [{"id": "C1"}]},
            "gate_log": [{"event": "formal_gate"}],
            "rollback_cone": {"affected_downstream": ["S1"]},
        },
    )

    assert not negative.shape_pass
    assert {
        "dependency_graph",
        "semantic_object_graph",
        "gate",
        "rollback",
    }.issubset(_violation_families(negative))


def test_b4_allows_generic_trace_but_rejects_scientific_states_gates_rollback():
    positive = validate_output_shape(
        B4,
        agent_output={
            "answer": {"diagnosis": "record R1 was inspected before output"},
            "generic_trace": [
                {"event_type": "read_input", "record_id": "R1"},
                {"event_type": "emit_output", "artifact_id": "answer"},
            ],
            "artifact_manifest": [{"artifact": "answer", "hash": "sha256:test"}],
            "input_output_lineage": [{"input": "R1", "output": "answer"}],
        },
    )

    assert positive.shape_pass, positive.to_dict()
    assert "generic_trace" in positive.allowed_capabilities_detected

    negative = validate_output_shape(
        B4,
        agent_output={
            "generic_trace": [{"event_type": "inspect_record", "record_id": "R1"}],
            "semantic_objects": [
                {"id": "claim.1", "object_type": "claim", "state": "stale"}
            ],
            "semantic_states": [{"object_id": "claim.1", "state": "blocked"}],
            "gate_decision": {"verdict": "needs_review"},
            "validity_ledger": [{"object_id": "claim.1", "state": "stale"}],
            "rollback_event": {"stale_root": "claim.1"},
        },
    )

    assert not negative.shape_pass
    assert {
        "semantic_object_graph",
        "scientific_semantic_state",
        "gate",
        "validity_ledger",
        "rollback",
    }.issubset(_violation_families(negative))


def test_b5_requires_full_rh_artifacts_and_rejects_common_runner_audits_only():
    strict_b5 = validate_output_shape(
        B5,
        agent_output={
            "final_answer": {"diagnosis": "full RH governance output"},
            "semantic_objects": [{"id": "claim.1", "object_type": "claim"}],
            "object_graph": {
                "nodes": [{"id": "claim.1"}, {"id": "evidence.1"}],
                "edges": [
                    {
                        "source": "evidence.1",
                        "target": "claim.1",
                        "relation": "supports",
                    }
                ],
            },
            "gate_decision": {"verdict": "pass_with_caveat"},
            "verification_report": {"checks": [{"id": "support", "status": "passed"}]},
            "validity_ledger": [{"object_id": "claim.1", "state": "valid"}],
            "rollback_cone": {"rollback_not_applicable": True},
        },
        sidecars={
            "object_graph.json": {"nodes": [{"id": "claim.1"}], "edges": []},
            "gate_log.json": [{"event": "gate_evaluated"}],
            "verification_report.json": {"checks": [{"id": "support"}]},
            "validity_ledger.json": [{"object_id": "claim.1"}],
            "rollback_cone.json": {"rollback_not_applicable": True},
        },
    )
    assert strict_b5.shape_pass, strict_b5.to_dict()
    assert "full_rh_governance" in strict_b5.allowed_capabilities_detected

    common_audits_only = validate_output_shape(
        B5,
        agent_output={"final_answer": {"diagnosis": "answer without governance"}},
        sidecars={name: {"status": "pass"} for name in COMMON_RUNNER_ARTIFACTS},
    )

    assert not common_audits_only.shape_pass
    assert "b5_required_component_missing" in _violation_codes(common_audits_only)
    assert set(
        common_audits_only.common_runner_artifacts_ignored_for_capability
    ) == set(COMMON_RUNNER_ARTIFACTS)


@pytest.mark.parametrize("baseline_id", [B1, B2, B3])
def test_common_runner_run_trace_is_capability_neutral(baseline_id: str):
    report = validate_output_shape(
        baseline_id,
        agent_output={"answer": {"diagnosis": "plain answer"}},
        sidecars={
            "run_trace.json": {
                "events": [{"event_type": "emit_output"}],
                "generic_trace": [{"event_type": "emit_output"}],
            },
            "retrieval_trace.json": {
                "status": "not_applicable",
                "citation_list": [{"record_id": "R1"}],
            },
            "allowed_tools_preflight.json": {"preflight_pass": True},
            "leakage_audit_report.json": {"independent_audit_pass": True},
            "cost_latency_trace.json": {"cost_trace_pass": True},
            "eval_report.json": {"outcome": "not_scored"},
            "parse_metadata.json": {"parser": "json"},
            "executor_config.json": {"executor": "codex_cli"},
        },
    )

    assert report.shape_pass, report.to_dict()
    assert set(report.common_runner_artifacts_ignored_for_capability) == {
        "allowed_tools_preflight.json",
        "cost_latency_trace.json",
        "eval_report.json",
        "executor_config.json",
        "leakage_audit_report.json",
        "parse_metadata.json",
        "retrieval_trace.json",
        "run_trace.json",
    }
    assert "retrieval_list" not in report.allowed_capabilities_detected
    assert "generic_trace" not in report.allowed_capabilities_detected
    assert "full_rh_governance" not in report.allowed_capabilities_detected
