"""End-to-end chain scenarios — drive the OrchestratorService state
machine against fixture topics and verify the boolean assertions.

Two scenarios (as required by the test plan):

1. **autonomous survey chain** (pre_merge tier)
   init → build → analyze
   Scripts the artifacts a real autonomous run would produce. Asserts
   that transitions are legal, artifacts satisfy the schema gate, and
   no silent failures landed in the DB.

2. **supervised loopback chain** (pre_merge tier)
   init → build → analyze → build (loopback) → analyze → propose
   Models the coverage_gate rejecting analyze once, causing a loopback
   to build for more evidence, then a second analyze that passes.
   Asserts STAGE_GRAPH allows the loopback edge and assert_transition_legal
   accepts every event, including the loopback.

These scenarios DO NOT invoke the auto_runner loop or any live LLM.
They bypass the subprocess path by calling OrchestratorService directly
with pre-shaped payloads. Phase 3-6 (nightly) runs the full live chain.
"""

from __future__ import annotations

import pytest

from research_harness.orchestrator.service import OrchestratorService

from ..assertions import boolean_suite as bs
from ..fixtures import load_topic


def _ok(result: bs.AssertionResult, context: str = "") -> None:
    """Helper: raise AssertionError with detail + evidence on failure."""
    if result.passed:
        return
    raise AssertionError(
        f"[{context}] {result.name} failed: {result.detail}\n"
        f"evidence: {result.evidence}"
    )


# ---------------------------------------------------------------------------
# Scenario 1: autonomous survey (init → build → analyze)
# ---------------------------------------------------------------------------


@pytest.mark.pre_merge
def test_e2e_autonomous_survey_chain_to_analyze(db):
    """Exercise init → build → analyze and validate with boolean suite."""
    loaded = load_topic(db, "small_tfr")
    topic_id = loaded.topic_id
    svc = OrchestratorService(db)

    # init
    svc.init_run(topic_id, mode="standard")
    svc.record_artifact(
        topic_id=topic_id,
        stage="init",
        artifact_type="topic_brief",
        title="Topic brief for small TFR bench",
        payload={
            "scope": loaded.spec["scope"],
            "venue_target": loaded.spec["venue_target"],
        },
    )

    # init → build
    r = svc.transition_to(
        topic_id, "build", rationale="topic_brief recorded, start retrieval"
    )
    assert r["success"], r
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="literature_map",
        payload={
            "clusters": [
                {"name": "classical", "paper_ids": list(loaded.paper_ids[:2])},
                {"name": "foundation-models", "paper_ids": list(loaded.paper_ids[2:])},
            ]
        },
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="paper_pool_snapshot",
        payload={"paper_count": len(loaded.paper_ids)},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="citation_expansion_report",
        payload={"seeds": len(loaded.paper_ids), "added": 0},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="acquisition_report",
        payload={
            "searched": 8,
            "ingested": 5,
            "skipped": 2,
            "failed": 1,
        },
    )

    # build → analyze
    r = svc.transition_to(topic_id, "analyze", rationale="minimum corpus met")
    assert r["success"], r
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="evidence_pack",
        payload={"claims": [{"id": "c1", "text": "transformers scale on forecasting"}]},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="claim_candidate_set",
        payload={"candidates": ["c1"]},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="direction_proposal",
        payload={
            "research_question": "Can a reasoning-augmented LLM close the calibration gap on Monash?",
            "hypothesis": "yes, with CoT prompting",
        },
    )

    # Now run the boolean suite.
    transition = bs.assert_transition_legal(db, topic_id)
    paper_count = bs.assert_paper_count_conserved(db, topic_id)
    gate_reason = bs.assert_gate_has_reason(db, topic_id)
    no_traceback = bs.assert_no_unexplained_traceback(db, topic_id)
    artifacts = bs.assert_artifacts_present_and_valid(db, topic_id)
    llm_audit = bs.assert_llm_route_audited(db, topic_id)

    _ok(transition, "autonomous survey")
    _ok(paper_count, "autonomous survey")
    _ok(gate_reason, "autonomous survey")
    _ok(no_traceback, "autonomous survey")
    _ok(artifacts, "autonomous survey")
    _ok(llm_audit, "autonomous survey")


# ---------------------------------------------------------------------------
# Scenario 2: supervised loopback (analyze → build → analyze → propose)
# ---------------------------------------------------------------------------


@pytest.mark.pre_merge
def test_e2e_supervised_loopback_analyze_to_build(db):
    """Force an analyze → build loopback and verify the state machine
    records it, STAGE_GRAPH allows it, and assert_transition_legal accepts it."""
    loaded = load_topic(db, "loopback_evidence")
    topic_id = loaded.topic_id
    svc = OrchestratorService(db)

    svc.init_run(topic_id, mode="strict")
    svc.record_artifact(
        topic_id=topic_id,
        stage="init",
        artifact_type="topic_brief",
        payload={
            "scope": loaded.spec["scope"],
            "venue_target": loaded.spec["venue_target"],
        },
    )
    svc.transition_to(topic_id, "build", rationale="init complete")
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="literature_map",
        payload={
            "clusters": [{"name": "default", "paper_ids": list(loaded.paper_ids)}]
        },
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="paper_pool_snapshot",
        payload={"paper_count": len(loaded.paper_ids)},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="citation_expansion_report",
        payload={"seeds": 5, "added": 0},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="acquisition_report",
        payload={"searched": 5, "ingested": 5, "skipped": 0, "failed": 0},
    )

    # First analyze — stale seed causes coverage_gate to reject
    svc.transition_to(topic_id, "analyze", rationale="attempt first analyze")
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="evidence_pack",
        payload={"claims": [], "rejection_reason": "stale-seed detected"},
    )
    # Loopback: analyze → build (allowed by STAGE_GRAPH)
    r = svc.transition_to(
        topic_id,
        "build",
        rationale="coverage_gate: add more recent papers to replace stale fixture-lb-005",
    )
    assert r["success"], r

    # Second build attempt: add richer acquisition_report, update pool
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="acquisition_report",
        payload={"searched": 12, "ingested": 7, "skipped": 3, "failed": 2},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="paper_pool_snapshot",
        payload={"paper_count": 12},
    )

    # Second analyze — passes
    svc.transition_to(topic_id, "analyze", rationale="retry after backfill")
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="evidence_pack",
        payload={"claims": [{"id": "c1", "text": "after-backfill claim"}]},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="claim_candidate_set",
        payload={"candidates": ["c1"]},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="direction_proposal",
        payload={"research_question": "Is freshness-weighted retrieval sufficient?"},
    )

    # analyze → propose
    svc.transition_to(topic_id, "propose", rationale="evidence coverage now adequate")
    svc.record_artifact(
        topic_id=topic_id,
        stage="propose",
        artifact_type="adversarial_resolution",
        payload={"outcome": "accepted", "rounds": 1},
    )
    svc.record_artifact(
        topic_id=topic_id,
        stage="propose",
        artifact_type="study_spec",
        payload={"methodology": "ablation + stress tests", "baselines": ["Informer"]},
    )

    # Verify
    transition = bs.assert_transition_legal(db, topic_id)
    paper_count = bs.assert_paper_count_conserved(db, topic_id)
    no_traceback = bs.assert_no_unexplained_traceback(db, topic_id)

    _ok(transition, "loopback chain")
    _ok(paper_count, "loopback chain")
    _ok(no_traceback, "loopback chain")

    # Count the loopback edge explicitly — defining feature of this test
    conn = db.connect()
    try:
        loopback_events = conn.execute(
            """
            SELECT COUNT(*) AS n FROM orchestrator_stage_events
            WHERE topic_id = ? AND from_stage = 'analyze' AND to_stage = 'build'
            """,
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()
    assert loopback_events["n"] == 1, "expected exactly one analyze→build loopback"


# ---------------------------------------------------------------------------
# Negative assertion: proves the suite catches what it claims to catch
# ---------------------------------------------------------------------------


@pytest.mark.pre_merge
def test_e2e_assertion_suite_catches_paper_count_drift(db):
    """Sanity check: if an acquisition_report reports searched != ingested+skipped+failed,
    assert_paper_count_conserved MUST fail. If this test ever passes with
    passed=True, the assertion has regressed."""
    loaded = load_topic(db, "small_tfr")
    topic_id = loaded.topic_id
    svc = OrchestratorService(db)
    svc.init_run(topic_id, mode="standard")
    svc.transition_to(topic_id, "build", rationale="skip init for this check")
    svc.record_artifact(
        topic_id=topic_id,
        stage="build",
        artifact_type="acquisition_report",
        payload={"searched": 10, "ingested": 3, "skipped": 1, "failed": 1},
    )
    result = bs.assert_paper_count_conserved(db, topic_id)
    assert not result.passed, f"expected drift detection, got {result.detail}"
    assert result.evidence["delta"] == 5
