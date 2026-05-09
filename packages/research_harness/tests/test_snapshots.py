"""Tests for stage snapshots and rollback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def db_with_topic(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    conn.execute("INSERT INTO domains (name) VALUES ('test-domain')")
    conn.execute(
        "INSERT INTO topics (name, description, domain_id) VALUES ('test-topic', 'desc', 1)"
    )
    conn.execute(
        """
        INSERT INTO orchestrator_runs (topic_id, mode, current_stage, stage_status)
        VALUES (1, 'standard', 'analyze', 'in_progress')
        """
    )
    conn.execute(
        """
        INSERT INTO project_artifacts (topic_id, stage, artifact_type, title, version, status)
        VALUES (1, 'build', 'paper_list', 'Papers', 1, 'accepted')
        """
    )
    conn.execute(
        """
        INSERT INTO project_artifacts (topic_id, stage, artifact_type, title, version, status)
        VALUES (1, 'analyze', 'analysis', 'Analysis', 1, 'accepted')
        """
    )
    conn.commit()
    conn.close()
    return db


def test_create_snapshot(db_with_topic: Database):
    from research_harness.orchestrator.snapshots import create_snapshot

    conn = db_with_topic.connect()
    try:
        snap_id = create_snapshot(conn, topic_id=1, stage="build", run_id=1)
        conn.commit()
        assert snap_id is not None

        row = conn.execute(
            "SELECT * FROM stage_snapshots WHERE id = ?", (snap_id,)
        ).fetchone()
        assert row["stage"] == "build"
        data = json.loads(row["artifact_snapshot"])
        assert "artifacts" in data
        assert len(data["artifacts"]) >= 1
    finally:
        conn.close()


def test_rollback_marks_stale(db_with_topic: Database):
    from research_harness.orchestrator.snapshots import (
        create_snapshot,
        rollback_to_stage,
    )

    conn = db_with_topic.connect()
    try:
        create_snapshot(conn, topic_id=1, stage="build", run_id=1)
        conn.commit()

        result = rollback_to_stage(conn, topic_id=1, to_stage="build", reason="test")
        assert result["success"] is True
        assert result["to_stage"] == "build"

        stale = conn.execute(
            "SELECT COUNT(*) FROM project_artifacts WHERE topic_id = 1 AND stale = 1"
        ).fetchone()[0]
        assert stale >= 1

        run = conn.execute(
            "SELECT current_stage FROM orchestrator_runs WHERE topic_id = 1"
        ).fetchone()
        assert run["current_stage"] == "build"

        log = conn.execute("SELECT * FROM rollback_log WHERE topic_id = 1").fetchall()
        assert len(log) == 1
        assert log[0]["reason"] == "test"
    finally:
        conn.close()


def test_rollback_no_snapshot(db_with_topic: Database):
    from research_harness.orchestrator.snapshots import rollback_to_stage

    conn = db_with_topic.connect()
    try:
        result = rollback_to_stage(
            conn, topic_id=1, to_stage="propose", reason="no snap"
        )
        assert result["success"] is False
        assert "No snapshot" in result["error"]
    finally:
        conn.close()
