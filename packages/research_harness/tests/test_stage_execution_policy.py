"""Tests for v2 Step 3.1 — pre-execution planner and stage budget wiring.

Covers:
- should_execute() returns should_run=True when stage hasn't run yet
- should_execute() returns skip for fresh_artifact_present
- should_execute() returns skip for resumed_past_stage
- check_stage_budget() respects DEFAULT_STAGE_BUDGETS without DB config
- check_stage_budget() picks up stage_budgets rows when present
"""

from __future__ import annotations

import pytest

from research_harness.auto_runner.stage_policy import (
    ExecutionDecision,
    should_execute,
)
from research_harness.storage.db import Database
from research_harness.token_accounting import (
    DEFAULT_STAGE_BUDGETS,
    check_stage_budget,
)


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    # Point the token_accounting module-level DB to this test DB.
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    return db


@pytest.fixture
def topic_id(db):
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)",
            ("test-topic", "Test topic"),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        conn.commit()
        return tid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# should_execute
# ---------------------------------------------------------------------------


def test_should_execute_runs_when_stage_fresh(db, topic_id):
    """No artifacts yet -> should run."""
    decision = should_execute(db=db, topic_id=topic_id, stage="analyze")
    assert isinstance(decision, ExecutionDecision)
    assert decision.should_run is True
    assert decision.reason == "run"


def test_should_execute_skips_when_required_artifacts_fresh(db, topic_id):
    """init stage requires topic_brief; if present and non-stale, skip."""
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO project_artifacts
              (topic_id, stage, artifact_type, title, payload_json, status, stale)
            VALUES (?, 'init', 'topic_brief', 'Test', '{"scope":"x"}', 'active', 0)
            """,
            (topic_id,),
        )
        conn.commit()
    finally:
        conn.close()

    decision = should_execute(db=db, topic_id=topic_id, stage="init")
    assert decision.should_run is False
    assert decision.reason == "fresh_artifact_present"


def test_should_execute_does_not_skip_when_artifact_stale(db, topic_id):
    """Stale artifact means the stage needs re-execution."""
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO project_artifacts
              (topic_id, stage, artifact_type, title, payload_json, status, stale, stale_reason)
            VALUES (?, 'init', 'topic_brief', 'Test', '{"scope":"x"}', 'active', 1, 'test')
            """,
            (topic_id,),
        )
        conn.commit()
    finally:
        conn.close()

    decision = should_execute(db=db, topic_id=topic_id, stage="init")
    assert decision.should_run is True


def test_should_execute_resumed_past_stage(db, topic_id):
    """If checkpoint is already at a later stage, skip earlier ones."""
    decision = should_execute(
        db=db,
        topic_id=topic_id,
        stage="init",
        current_checkpoint_stage="analyze",
    )
    assert decision.should_run is False
    assert decision.reason == "resumed_past_stage"


def test_should_execute_unknown_stage_defaults_to_run(db, topic_id):
    """Unknown stage names pass through as run."""
    decision = should_execute(db=db, topic_id=topic_id, stage="nonexistent")
    assert decision.should_run is True


# ---------------------------------------------------------------------------
# check_stage_budget
# ---------------------------------------------------------------------------


def test_check_stage_budget_default_budgets_no_spend(db, topic_id):
    """No spend recorded -> ok with no warning."""
    # migration 049 creates stage_budgets; budget lookup misses, defaults apply
    result = check_stage_budget(topic_id=topic_id, stage="gap_detect")
    assert result.ok is True
    assert result.warning is None
    soft, hard = DEFAULT_STAGE_BUDGETS["gap_detect"]
    assert result.soft_warn_tokens == soft
    assert result.hard_cap_tokens == hard


def test_check_stage_budget_unknown_stage(db, topic_id):
    """Stage with no default and no DB row -> ok, untracked."""
    result = check_stage_budget(topic_id=topic_id, stage="totally_unknown")
    assert result.ok is True
    assert result.warning is None


def test_check_stage_budget_db_override(db, topic_id):
    """stage_budgets row overrides the defaults."""
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO stage_budgets (stage, topic_id, soft_warn_tokens, hard_cap_tokens)
            VALUES (?, ?, ?, ?)
            """,
            ("gap_detect", topic_id, 100, 200),
        )
        conn.commit()
    finally:
        conn.close()

    result = check_stage_budget(topic_id=topic_id, stage="gap_detect")
    assert result.soft_warn_tokens == 100
    assert result.hard_cap_tokens == 200
