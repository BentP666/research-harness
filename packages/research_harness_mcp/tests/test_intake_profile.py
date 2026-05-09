"""Tests for Iteration 01: intake_profile endpoints (migration 057)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


_VALID_BODY = {
    "persona": "p3_topic_weak",
    "domain_confidence": 80,
    "topic_confidence": 60,
    "venue_constraint": "preferred",
    "target_venue": "EMNLP",
    "compute_budget": "single_gpu",
    "time_to_deadline_days": 120,
    "seed_present": 0,
    "raw_notes": "TFRBench replication",
}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "intake.db"
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
def db_path(client: TestClient, tmp_path: Path) -> Path:
    """Return the DB path used by the current client fixture."""
    from research_harness_mcp import http_api

    return http_api.DB_PATH


def test_put_intake_profile_creates_record(client: TestClient):
    r = client.put("/api/topics/1/intake-profile", json=_VALID_BODY)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["persona"] == "p3_topic_weak"
    assert data["domain_confidence"] == 80
    assert data["topic_confidence"] == 60
    assert data["venue_constraint"] == "preferred"
    assert data["target_venue"] == "EMNLP"
    assert data["compute_budget"] == "single_gpu"
    assert data["time_to_deadline_days"] == 120

    r2 = client.get("/api/topics/1/intake-profile")
    assert r2.status_code == 200
    assert r2.json()["persona"] == "p3_topic_weak"


def test_put_invalid_persona_400(client: TestClient):
    body = {**_VALID_BODY, "persona": "p5_invalid"}
    r = client.put("/api/topics/1/intake-profile", json=body)
    assert r.status_code == 422


def test_put_invalid_compute_budget_400(client: TestClient):
    body = {**_VALID_BODY, "compute_budget": "quantum"}
    r = client.put("/api/topics/1/intake-profile", json=body)
    assert r.status_code == 422


def test_get_404_when_topic_missing(client: TestClient):
    r = client.get("/api/topics/9999/intake-profile")
    assert r.status_code == 404


def test_put_writes_artifact(client: TestClient, db_path: Path):
    client.put("/api/topics/1/intake-profile", json=_VALID_BODY)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM project_artifacts WHERE topic_id = 1 AND artifact_type = 'intake_profile'"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["stage"] == "init"


def test_put_updates_existing(client: TestClient):
    client.put("/api/topics/1/intake-profile", json=_VALID_BODY)

    updated = {**_VALID_BODY, "persona": "p4_topic_strong", "domain_confidence": 95}
    r = client.put("/api/topics/1/intake-profile", json=updated)
    assert r.status_code == 200
    data = r.json()
    assert data["persona"] == "p4_topic_strong"
    assert data["domain_confidence"] == 95

    r2 = client.get("/api/topics/1/intake-profile")
    assert r2.json()["persona"] == "p4_topic_strong"
