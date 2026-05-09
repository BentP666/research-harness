"""Tests for Iteration 09: retrieval_log cross-stage (migration 061)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "retrieval.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test topic', 'active')"
        )
        conn.execute(
            "INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'test project')"
        )
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


@pytest.fixture()
def db_path(client: TestClient) -> Path:
    from research_harness_mcp import http_api

    return http_api.DB_PATH


def _mock_search(api, *, query, topic_id=None, max_results=50):
    return {"papers": [{"id": 1, "title": "Fake Paper"}]}


def test_search_without_retrieval_fields_no_log(client: TestClient, db_path: Path):
    """Old-style search (no stage/trigger_reason) should NOT write a log entry."""
    with patch(
        "research_harness_mcp.http_api._search_papers_impl",
        side_effect=_mock_search,
    ):
        r = client.post("/api/papers/search", json={"query": "time series"})
    assert r.status_code == 200

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM retrieval_log").fetchone()[0]
    conn.close()
    assert count == 0


def test_search_with_retrieval_fields_writes_log(client: TestClient, db_path: Path):
    """Search with all 3 fields should write a retrieval_log entry."""
    with patch(
        "research_harness_mcp.http_api._search_papers_impl",
        side_effect=_mock_search,
    ):
        r = client.post(
            "/api/papers/search",
            json={
                "query": "time series reasoning",
                "topic_id": 1,
                "stage": "analyze",
                "trigger_reason": "missing_evidence",
            },
        )
    assert r.status_code == 200

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM retrieval_log WHERE topic_id = 1").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["stage"] == "analyze"
    assert rows[0]["trigger_reason"] == "missing_evidence"
    assert rows[0]["query"] == "time series reasoning"
    assert rows[0]["results_count"] == 1


def test_search_invalid_reason_no_log(client: TestClient, db_path: Path):
    """Invalid trigger_reason should be silently ignored (no log written)."""
    with patch(
        "research_harness_mcp.http_api._search_papers_impl",
        side_effect=_mock_search,
    ):
        r = client.post(
            "/api/papers/search",
            json={
                "query": "test",
                "topic_id": 1,
                "stage": "analyze",
                "trigger_reason": "invalid_reason",
            },
        )
    assert r.status_code == 200

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM retrieval_log").fetchone()[0]
    conn.close()
    assert count == 0


def test_get_retrieval_log(client: TestClient, db_path: Path):
    """GET /api/topics/{id}/retrieval-log returns entries."""
    # Manually insert some log entries
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO retrieval_log (topic_id, stage, trigger_reason, query, results_count)
           VALUES (1, 'analyze', 'missing_evidence', 'query A', 5)"""
    )
    conn.execute(
        """INSERT INTO retrieval_log (topic_id, stage, trigger_reason, query, results_count)
           VALUES (1, 'experiment', 'weak_baseline', 'query B', 3)"""
    )
    conn.commit()
    conn.close()

    r = client.get("/api/topics/1/retrieval-log")
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 2
    assert entries[0]["stage"] in ("analyze", "experiment")


def test_get_retrieval_log_404_missing_topic(client: TestClient):
    r = client.get("/api/topics/9999/retrieval-log")
    assert r.status_code == 404


def test_all_five_reasons_writable(client: TestClient, db_path: Path):
    """All 5 trigger_reason values should be writable."""
    reasons = [
        "missing_evidence",
        "weak_baseline",
        "new_atom_idea",
        "venue_pattern",
        "user_request",
    ]
    for reason in reasons:
        with patch(
            "research_harness_mcp.http_api._search_papers_impl",
            side_effect=_mock_search,
        ):
            r = client.post(
                "/api/papers/search",
                json={
                    "query": f"test {reason}",
                    "topic_id": 1,
                    "stage": "build",
                    "trigger_reason": reason,
                },
            )
        assert r.status_code == 200

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM retrieval_log WHERE topic_id = 1"
    ).fetchone()[0]
    conn.close()
    assert count == 5
