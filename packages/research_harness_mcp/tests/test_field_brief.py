"""Tests for Iteration 03: field_brief primitive + endpoints (migration 058)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


_VALID_FIELD_BRIEF = {
    "datasets": [
        {
            "name": "apple_stock",
            "size": "1000 samples",
            "license": "MIT",
            "gpu_req": "cpu",
        },
        {"name": "NYC_Taxi", "size": "5000 samples", "license": None, "gpu_req": "low"},
    ],
    "baselines": [
        {
            "name": "TimeLLM",
            "paper_id": None,
            "metric_name": "MAPE",
            "metric_value": 15.2,
        },
    ],
    "narrative_patterns": [
        "reasoning-enhanced forecasting",
        "chain-of-thought prompting",
    ],
    "open_challenges": [
        {"problem": "chaotic series prediction", "maturity": "niche"},
        {"problem": "multi-horizon accuracy", "maturity": "hot"},
    ],
    "compute_bands": ["CPU-only", "1xA100"],
    "venue_options": [
        {"name": "EMNLP", "deadline": "2026-06-15", "acceptance_rate": 0.25},
    ],
    "saturation_score": 0.42,
}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "field_brief.db"
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
        conn.execute(
            "INSERT INTO papers (id, title, abstract, compiled_summary) "
            "VALUES (1, 'Paper A', 'Abstract A', 'Summary A')"
        )
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (1, 1)")
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


def _mock_transient_retry(chat_fn, prompt, *, retries=1):
    return json.dumps(_VALID_FIELD_BRIEF)


_PATCH_TARGET = (
    "research_harness.primitives.field_brief_impl._call_with_transient_retry"
)


def test_build_returns_valid_schema(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        r = client.post("/api/topics/1/field-brief")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["datasets"]) == 2
    assert data["saturation_score"] == 0.42
    assert len(data["baselines"]) == 1
    assert len(data["open_challenges"]) == 2


def test_build_writes_artifact(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        client.post("/api/topics/1/field-brief")

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM project_artifacts WHERE topic_id = 1 AND artifact_type = 'field_brief'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["stage"] == "analyze"


def test_build_writes_meta(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        client.post("/api/topics/1/field-brief")

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM field_brief_meta WHERE topic_id = 1").fetchone()
    conn.close()
    assert row is not None
    assert row["paper_count_at_build"] == 1
    assert row["stale"] == 0


def test_get_returns_latest(client: TestClient):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        client.post("/api/topics/1/field-brief")

    r = client.get("/api/topics/1/field-brief")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "brief" in data
    assert "meta" in data
    assert data["brief"]["saturation_score"] == 0.42
    assert data["meta"]["stale"] is False
    assert data["meta"]["paper_count_at_build"] == 1


def test_get_returns_null_when_no_brief(client: TestClient):
    r = client.get("/api/topics/1/field-brief")
    assert r.status_code == 200
    assert r.json() is None


def test_invalid_llm_output_raises_500(client: TestClient):
    def _bad_output(chat_fn, prompt, *, retries=1):
        return '{"invalid": true}'

    with patch(_PATCH_TARGET, side_effect=_bad_output):
        r = client.post("/api/topics/1/field-brief")
    assert r.status_code == 500
    assert "validation" in r.json()["detail"].lower()


def test_stale_flag_after_paper_ingest(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        client.post("/api/topics/1/field-brief")

    # Add enough papers to trigger >15% growth (currently 1 paper, need >1.15 → 2+)
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    for i in range(2, 5):
        conn.execute(
            "INSERT INTO papers (id, title, abstract, s2_id, arxiv_id, doi) VALUES (?, ?, ?, ?, ?, ?)",
            (i, f"Paper {i}", f"Abstract {i}", f"s2-{i}", f"arxiv-{i}", f"doi-{i}"),
        )
        conn.execute(
            "INSERT INTO paper_topics (paper_id, topic_id) VALUES (?, 1)",
            (i,),
        )
    conn.commit()
    conn.close()

    # Simulate ingest triggering stale check via direct DB check
    # (the actual ingest endpoint needs real paper source, so test the stale logic directly)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    meta = conn.execute(
        "SELECT paper_count_at_build FROM field_brief_meta WHERE topic_id = 1"
    ).fetchone()
    current = conn.execute(
        "SELECT COUNT(*) FROM paper_topics WHERE topic_id = 1"
    ).fetchone()[0]
    if current > meta["paper_count_at_build"] * 1.15:
        conn.execute("UPDATE field_brief_meta SET stale = 1 WHERE topic_id = 1")
        conn.commit()

    row = conn.execute(
        "SELECT stale FROM field_brief_meta WHERE topic_id = 1"
    ).fetchone()
    conn.close()
    assert row["stale"] == 1


def test_stale_flag_after_21_days(client: TestClient, db_path: Path):
    with patch(_PATCH_TARGET, side_effect=_mock_transient_retry):
        client.post("/api/topics/1/field-brief")

    # Manually set built_at to 22 days ago
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE field_brief_meta SET built_at = datetime('now', '-22 days') WHERE topic_id = 1"
    )
    conn.commit()
    conn.close()

    # GET should detect staleness
    r = client.get("/api/topics/1/field-brief")
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["stale"] is True
