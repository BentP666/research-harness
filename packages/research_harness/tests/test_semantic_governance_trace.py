from pathlib import Path

from research_harness.semantic_governance.normalization import convert_b5_run

RUN_ROOT = (
    Path(__file__).resolve().parents[3]
    / ".research-harness/reports/researchflowbench_pilot5_v0/runs/model_actual_cursor_full5_clean_20260520"
)


def test_run_trace_normalization_preserves_model_visibility_and_cost_gaps():
    bundles = convert_b5_run(RUN_ROOT)

    for bundle in bundles:
        trace = bundle.run_trace
        assert trace is not None
        assert trace.provider == "cursor_agent"
        assert trace.model == "composer-2-fast"
        assert trace.runner == "run_model_baselines.py"
        assert trace.allowed_tools == ("local_static_corpus",)
        assert trace.gold_visible is False
        assert trace.judge_visible is False
        assert trace.wall_clock_seconds is not None and trace.wall_clock_seconds > 0
        assert trace.token_usage is None
        assert "cost_unknown" in trace.risk_flags
        assert "retrieval_trace_incomplete" in trace.risk_flags


def test_verification_signals_normalize_mixed_check_shapes():
    bundles = {bundle.task_id: bundle for bundle in convert_b5_run(RUN_ROOT)}

    target_hunt = bundles["rfb.smoke.literature.target_hunt.0001"]
    target_checks = {
        signal.check_id: signal for signal in target_hunt.verification_signals
    }
    assert target_checks["year_alignment"].passed is True
    assert target_checks["anti_hallucination"].passed is None
    assert target_checks["anti_hallucination"].label == "warn"

    integrity = bundles["rfb.smoke.governance.integrity_refusal.0001"]
    integrity_checks = {
        signal.check_id: signal for signal in integrity.verification_signals
    }
    assert integrity_checks["fabrication_guard"].passed is False
    assert integrity_checks["risk_tag_alignment"].passed is True

    assert all(
        signal.signal_type in {"deterministic", "gate_consistency"}
        for bundle in bundles.values()
        for signal in bundle.verification_signals
    )
