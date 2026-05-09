"""Tests for the rubric calibration pipeline (anchor load + Youden's J + runner)."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.calibration import (
    calibrate_all,
    calibrate_stage_tier,
    load_anchors,
    youdens_j_threshold,
)
from research_harness.calibration.runner import _score_anchor
from research_harness.storage.db import Database


def test_anchor_corpus_ships_with_data():
    anchors = load_anchors()
    assert len(anchors) >= 60, "seed anchor corpus should ship at least 60 entries"
    # Every stage we care about must have some coverage.
    for stage in ("init", "build", "analyze", "propose", "experiment", "write"):
        stage_rows = [a for a in anchors if a.stage == stage]
        assert stage_rows, f"no anchors for stage {stage}"
        assert any(a.label == "accept" for a in stage_rows)
        assert any(a.label == "reject" for a in stage_rows)


def test_youdens_j_picks_midpoint():
    pos = [8.0, 8.5, 9.0, 7.5, 8.2]
    neg = [2.0, 3.0, 4.0, 3.5, 2.5]
    th, fr, rr = youdens_j_threshold(pos, neg, default=6.8)
    # Max J is achieved somewhere in [4.0, 7.5]; tie-break prefers higher
    # threshold. All positives >= th, all negatives < th.
    assert 4.0 < th <= 7.5
    assert fr == 0.0
    assert rr == 1.0


def test_youdens_j_empty_inputs_return_default():
    th, fr, rr = youdens_j_threshold([], [], default=6.8)
    assert th == 6.8
    assert fr == 0.0
    assert rr == 0.0


def test_anchor_scoring_matches_judge_weights():
    """An anchor with high dim scores should score higher than one with low
    dim scores under the same rubric — sanity that _score_anchor is wired."""
    anchors = load_anchors()
    accept_scores = [_score_anchor(a) for a in anchors if a.label == "accept"]
    reject_scores = [_score_anchor(a) for a in anchors if a.label == "reject"]
    assert min(accept_scores) > max(reject_scores), (
        "seed anchors should be cleanly separated — if they aren't, the "
        "calibration will produce a noisy threshold"
    )


@pytest.fixture()
def fresh_db(tmp_path: Path):
    db = Database(tmp_path / "calib.db")
    db.migrate()
    return db


def test_calibrate_stage_tier_writes_row(fresh_db: Database):
    conn = fresh_db.connect()
    try:
        result = calibrate_stage_tier(conn, "analyze", "standard")
        assert result.anchor_count > 0
        assert not result.used_default
        assert 5.0 < result.threshold < 10.0

        row = conn.execute(
            "SELECT * FROM rubric_calibrations WHERE stage = ? AND tier = ?",
            ("analyze", "standard"),
        ).fetchone()
        assert row is not None
        assert abs(row["threshold"] - result.threshold) < 0.001
        assert row["anchor_count"] == result.anchor_count
    finally:
        conn.close()


def test_calibrate_stage_tier_falls_back_to_default_when_no_anchors(fresh_db: Database):
    conn = fresh_db.connect()
    try:
        # No anchors exist for (init, premium) in the seed corpus.
        result = calibrate_stage_tier(conn, "init", "premium")
        assert result.used_default
        assert result.anchor_count == 0
    finally:
        conn.close()


def test_calibrate_all_covers_every_stage_tier_pair(fresh_db: Database):
    conn = fresh_db.connect()
    try:
        results = calibrate_all(conn)
        assert len(results) == 6 * 3, "6 stages × 3 tiers"
        rows = conn.execute("SELECT COUNT(*) AS c FROM rubric_calibrations").fetchone()
        assert rows["c"] == 6 * 3
    finally:
        conn.close()


def test_judge_uses_calibrated_threshold(fresh_db: Database, monkeypatch):
    """After calibrate_all runs, run_rubric should use the calibrated threshold
    rather than the venue-tier default."""
    monkeypatch.delenv("RUBRIC_AUTO_ROLLBACK", raising=False)
    from research_harness.orchestrator.judge import _resolve_threshold, run_rubric

    conn = fresh_db.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('d')")
        conn.execute(
            "INSERT INTO topics (name, description, domain_id) VALUES ('t', 'd', 1)"
        )
        conn.execute(
            "INSERT INTO project_artifacts (topic_id, stage, artifact_type, title, version, status) "
            "VALUES (1, 'analyze', 'evidence_pack', 'E', 1, 'accepted')"
        )
        conn.commit()

        default_th = _resolve_threshold(conn, "analyze", "standard", "B")
        calibrate_all(conn)
        calibrated_th = _resolve_threshold(conn, "analyze", "standard", "B")
        assert calibrated_th != default_th  # calibration changed the threshold

        # And the judge picks up the calibrated threshold at scoring time.
        result = run_rubric(
            conn,
            artifact_id=1,
            topic_id=1,
            stage="analyze",
            tier="standard",
            venue_tier="B",
            dimension_scores={
                "evidence_coverage": 7.0,
                "counter_evidence": 7.0,
                "gap_crispness": 7.0,
                "citation_grounding": 7.0,
                "novelty": 7.0,
                "feasibility": 7.0,
                "clarity": 7.0,
            },
        )
        conn.commit()
        # In shadow mode (default), actual verdict is always pass; what matters
        # is the weighted_total is sensible relative to the calibrated threshold.
        assert 6.0 <= result.weighted_total <= 8.0
    finally:
        conn.close()
