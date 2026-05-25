from pathlib import Path

from research_harness.semantic_governance.graph import compute_rollback_cone
from research_harness.semantic_governance.models import RollbackAction
from research_harness.semantic_governance.normalization import convert_b5_run

RUN_ROOT = (
    Path(__file__).resolve().parent
    / "fixtures/researchflowbench/pilot5_b5_synthetic_run"
)


def test_cross_stage_upstream_error_rollback_cone_includes_downstream_and_gate():
    bundles = {bundle.task_id: bundle for bundle in convert_b5_run(RUN_ROOT)}
    bundle = bundles["rfb.smoke.cross_stage.upstream_error_propagation.0001"]

    cone = compute_rollback_cone(bundle, "obj.literature_outputs.baseline_map_omitted")

    assert "obj.planning_outputs" in cone.affected_object_ids
    assert "obj.draft_section" in cone.affected_object_ids
    assert bundle.gate_decisions[0].gate_id in cone.affected_object_ids
    assert {"ev.X3", "ev.X4"}.issubset(set(cone.preserved_object_refs))
    assert any("2233" in ref for ref in cone.preserved_object_refs)
    assert any("2260" in ref for ref in cone.preserved_object_refs)
    assert any("2057" in ref for ref in cone.preserved_object_refs)
    assert set(cone.required_actions).issubset(set(RollbackAction))


def test_block_verdict_creates_rollback_cone_but_not_outcome_failure():
    bundles = {bundle.task_id: bundle for bundle in convert_b5_run(RUN_ROOT)}
    bundle = bundles["rfb.smoke.governance.integrity_refusal.0001"]

    assert bundle.gate_decisions[0].verdict.value == "block"
    assert (
        bundle.aggregate_context.get("combined_row", {})
        .get("outcome_verdict", {})
        .get("pass", True)
        is True
    )
    assert bundle.rollback_cones
    assert set(bundle.gate_decisions[0].invalidated_object_ids) == {
        "obj.claim_47pct",
        "obj.req_log",
    }
