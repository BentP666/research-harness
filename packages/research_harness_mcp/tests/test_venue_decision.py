"""Tests for Iteration 08: venue_decision + style_kit (migration 063)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


_MOCK_FIELD_BRIEF = {
    "brief": {
        "datasets": [],
        "baselines": [],
        "narrative_patterns": [],
        "open_challenges": [],
        "compute_bands": [],
        "venue_options": [
            {"name": "EMNLP", "deadline": "2026-06-15", "acceptance_rate": 0.25},
            {"name": "NeurIPS", "deadline": "2026-05-20", "acceptance_rate": 0.20},
        ],
        "saturation_score": 0.4,
    },
    "meta": {"stale": False, "built_at": "2026-04-25", "paper_count_at_build": 10},
}


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "venue.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test', 'active')"
        )
        conn.execute("INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'test')")
        conn.execute(
            """INSERT INTO topic_intake_profile
               (topic_id, persona, domain_confidence, topic_confidence,
                venue_constraint, target_venue, compute_budget)
               VALUES (1, 'p3_topic_weak', 80, 60, 'preferred', 'EMNLP', 'single_gpu')"""
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


_FB_PATCH = "research_harness.primitives.field_brief_impl.get_latest_field_brief"


def test_venue_decision_preferred_match(client: TestClient):
    with patch(_FB_PATCH, return_value=_MOCK_FIELD_BRIEF):
        r = client.post("/api/topics/1/venue-decision")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["decided_venue"] == "EMNLP"
    assert "source_venues" in data


def test_venue_decision_get(client: TestClient):
    with patch(_FB_PATCH, return_value=_MOCK_FIELD_BRIEF):
        client.post("/api/topics/1/venue-decision")
    r = client.get("/api/topics/1/venue-decision")
    assert r.status_code == 200
    assert r.json()["decided_venue"] == "EMNLP"


def test_venue_decision_409_no_intake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "no_intake.db"
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test', 'active')"
        )
        conn.execute("INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'test')")
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    try:
        tc = TestClient(http_api.app)
        r = tc.post("/api/topics/1/venue-decision")
        assert r.status_code == 409
    finally:
        http_api.DB_PATH = original


def test_style_kit_409_insufficient_papers(client: TestClient):
    with patch(_FB_PATCH, return_value=_MOCK_FIELD_BRIEF):
        client.post("/api/topics/1/venue-decision")

    r = client.post("/api/topics/1/venue-style-kit")
    assert r.status_code == 409
    assert "need at least" in r.json()["detail"].lower()
