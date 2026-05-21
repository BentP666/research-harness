from collections import Counter
from pathlib import Path

from research_harness.semantic_governance.io import (
    discover_b5_task_bundles,
    load_combined_eval_summary,
)
from research_harness.semantic_governance.models import GateVerdict
from research_harness.semantic_governance.normalization import convert_b5_run
from research_harness.semantic_governance.validators import validate_bundle

RUN_ROOT = (
    Path(__file__).resolve().parents[3]
    / ".research-harness/reports/researchflowbench_pilot5_v0/runs/model_actual_cursor_full5_clean_20260520"
)


def test_discovers_exactly_five_b5_task_bundles_without_writing_run_root():
    before = sorted(p.relative_to(RUN_ROOT) for p in RUN_ROOT.rglob("*"))

    bundles = discover_b5_task_bundles(RUN_ROOT)

    after = sorted(p.relative_to(RUN_ROOT) for p in RUN_ROOT.rglob("*"))
    assert len(bundles) == 5
    assert [b.baseline_id for b in bundles] == ["B5.full_rh"] * 5
    assert before == after
    for bundle in bundles:
        assert bundle.object_graph.exists()
        assert bundle.gate_log.exists()
        assert bundle.verification_report.exists()
        assert bundle.run_trace.exists()
        assert bundle.agent_output.exists()


def test_b5_gate_verdicts_normalize_to_v01_contract():
    bundles = convert_b5_run(RUN_ROOT)

    verdicts = Counter(bundle.gate_decisions[0].verdict for bundle in bundles)

    assert verdicts == {
        GateVerdict.PASS: 2,
        GateVerdict.PASS_WITH_CAVEAT: 1,
        GateVerdict.BLOCK: 2,
    }

    by_task = {bundle.task_id: bundle for bundle in bundles}
    assert (
        by_task["rfb.smoke.literature.target_hunt.0001"].gate_decisions[0].verdict
        == GateVerdict.PASS
    )
    assert (
        by_task["rfb.smoke.synthesis.citation_supported_paragraph.0001"]
        .gate_decisions[0]
        .verdict
        == GateVerdict.PASS
    )
    assert (
        by_task["rfb.smoke.planning.novelty_calibration.0001"].gate_decisions[0].verdict
        == GateVerdict.PASS_WITH_CAVEAT
    )
    assert (
        by_task["rfb.smoke.governance.integrity_refusal.0001"].gate_decisions[0].verdict
        == GateVerdict.BLOCK
    )
    assert (
        by_task["rfb.smoke.cross_stage.upstream_error_propagation.0001"]
        .gate_decisions[0]
        .verdict
        == GateVerdict.BLOCK
    )


def test_b5_conversion_preserves_combined_summary_context_and_legacy_diagnostics():
    combined = load_combined_eval_summary(RUN_ROOT)
    bundles = convert_b5_run(RUN_ROOT, combined_eval_summary=combined)

    assert all(
        bundle.aggregate_context["combined_summary_schema_version"] == "0.2.0"
        for bundle in bundles
    )
    assert all(
        bundle.aggregate_context["combined_row"]["combined_verdict"]["combined_pass"]
        is True
        for bundle in bundles
    )

    codes = {diagnostic.code for bundle in bundles for diagnostic in bundle.diagnostics}
    assert "legacy_type_mapping" in codes
    assert "release_grade_judge_missing" in codes
    assert "retrieval_trace_incomplete" in codes
    assert "cost_unknown" in codes

    legacy_reports = [validate_bundle(bundle, mode="legacy") for bundle in bundles]
    strict_reports = [validate_bundle(bundle, mode="strict") for bundle in bundles]
    assert all(report.is_valid for report in legacy_reports)
    assert not any(report.is_valid for report in strict_reports)
