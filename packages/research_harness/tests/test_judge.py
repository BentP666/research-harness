"""Tests for judge engine (run_rubric, shadow mode, verdict logic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def db_with_artifact(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    conn.execute("INSERT INTO domains (name) VALUES ('d')")
    conn.execute(
        "INSERT INTO topics (name, description, domain_id) VALUES ('t', 'd', 1)"
    )
    conn.execute(
        "INSERT INTO orchestrator_runs (topic_id, mode, current_stage, stage_status) "
        "VALUES (1, 'standard', 'analyze', 'in_progress')"
    )
    conn.execute(
        "INSERT INTO project_artifacts (topic_id, stage, artifact_type, title, version, status) "
        "VALUES (1, 'analyze', 'evidence_pack', 'Evidence', 1, 'accepted')"
    )
    conn.commit()
    conn.close()
    return db


def test_run_rubric_pass(db_with_artifact: Database):
    from research_harness.orchestrator.judge import run_rubric

    conn = db_with_artifact.connect()
    try:
        scores = {
            "evidence_coverage": 8.0,
            "counter_evidence": 7.5,
            "gap_crispness": 8.0,
            "citation_grounding": 9.0,
            "novelty": 7.0,
            "feasibility": 8.0,
            "clarity": 7.5,
        }
        result = run_rubric(
            conn,
            artifact_id=1,
            topic_id=1,
            stage="analyze",
            tier="standard",
            venue_tier="B",
            dimension_scores=scores,
        )
        conn.commit()
        assert result.verdict == "pass"
        assert result.weighted_total >= 6.8

        row = conn.execute("SELECT * FROM rubric_scores WHERE topic_id = 1").fetchone()
        assert row is not None
        assert row["verdict"] == "pass"
        assert row["rubric_version"] == "analyze@v1"
    finally:
        conn.close()


def test_run_rubric_shadow_rollback(db_with_artifact: Database, monkeypatch):
    monkeypatch.setenv("RUBRIC_AUTO_ROLLBACK", "false")
    import importlib

    import research_harness.orchestrator.judge as judge_mod

    importlib.reload(judge_mod)
    try:
        conn = db_with_artifact.connect()
        try:
            scores = {
                "evidence_coverage": 3.0,
                "counter_evidence": 2.0,
                "gap_crispness": 3.0,
                "citation_grounding": 0.0,
                "novelty": 2.0,
                "feasibility": 3.0,
                "clarity": 2.0,
            }
            result = judge_mod.run_rubric(
                conn,
                artifact_id=1,
                topic_id=1,
                stage="analyze",
                tier="standard",
                venue_tier="B",
                dimension_scores=scores,
            )
            conn.commit()
            assert result.verdict == "pass"
            assert result.shadow_verdict == "rollback"
            assert result.weighted_total < 6.8

            row = conn.execute(
                "SELECT * FROM rubric_scores WHERE topic_id = 1"
            ).fetchone()
            assert row["shadow_verdict"] == "rollback"
        finally:
            conn.close()
    finally:
        monkeypatch.delenv("RUBRIC_AUTO_ROLLBACK", raising=False)
        importlib.reload(judge_mod)


def test_run_rubric_live_rollback(db_with_artifact: Database, monkeypatch):
    monkeypatch.setenv("RUBRIC_AUTO_ROLLBACK", "true")
    import importlib

    import research_harness.orchestrator.judge as judge_mod

    importlib.reload(judge_mod)
    try:
        conn = db_with_artifact.connect()
        try:
            scores = {
                "evidence_coverage": 3.0,
                "counter_evidence": 2.0,
                "gap_crispness": 3.0,
                "citation_grounding": 0.0,
                "novelty": 2.0,
                "feasibility": 3.0,
                "clarity": 2.0,
            }
            result = judge_mod.run_rubric(
                conn,
                artifact_id=1,
                topic_id=1,
                stage="analyze",
                tier="standard",
                venue_tier="B",
                dimension_scores=scores,
            )
            conn.commit()
            assert result.verdict == "rollback"
            assert result.shadow_verdict is None
        finally:
            conn.close()
    finally:
        monkeypatch.delenv("RUBRIC_AUTO_ROLLBACK", raising=False)
        importlib.reload(judge_mod)


def test_zero_citation_grounding_drags_total(db_with_artifact: Database, monkeypatch):
    """Low citation_grounding should drag the weighted total below threshold.

    In shadow mode (the default) the user-facing verdict stays "pass" but the
    shadow_verdict records what would have happened live — that's the value
    we assert on here.
    """
    monkeypatch.delenv("RUBRIC_AUTO_ROLLBACK", raising=False)
    import importlib

    import research_harness.orchestrator.judge as judge_mod

    importlib.reload(judge_mod)
    try:
        conn = db_with_artifact.connect()
        try:
            scores = {
                "evidence_coverage": 8.0,
                "counter_evidence": 8.0,
                "gap_crispness": 8.0,
                "citation_grounding": 0.0,
                "novelty": 8.0,
                "feasibility": 8.0,
                "clarity": 8.0,
            }
            result = judge_mod.run_rubric(
                conn,
                artifact_id=1,
                topic_id=1,
                stage="analyze",
                tier="standard",
                venue_tier="B",
                dimension_scores=scores,
            )
            conn.commit()
            assert result.weighted_total < 6.8
            assert result.shadow_verdict in ("rollback", "retry_recommended")
        finally:
            conn.close()
    finally:
        importlib.reload(judge_mod)


def test_needs_dual_judge():
    from research_harness.orchestrator.judge import needs_dual_judge

    assert needs_dual_judge("premium", "coverage_gate") is True
    assert needs_dual_judge("premium", "approval_gate") is True
    assert needs_dual_judge("standard", "approval_gate") is True
    assert needs_dual_judge("standard", "coverage_gate") is False
    assert needs_dual_judge("economy", "approval_gate") is False


def test_retry_budget():
    from research_harness.orchestrator.judge import get_retry_budget

    assert get_retry_budget("economy") == 0
    assert get_retry_budget("standard") == 1
    assert get_retry_budget("premium") == 2
