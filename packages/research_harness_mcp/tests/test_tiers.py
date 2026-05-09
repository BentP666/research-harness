"""Tests for quality tiers and venue/autonomy/tier API endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def _test_db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    from research_harness.storage.db import Database

    db = Database(db_path)
    db.migrate()

    from research_harness_mcp import http_api

    original_db_path = http_api.DB_PATH
    http_api.DB_PATH = db_path

    conn = db.connect()
    conn.execute("INSERT INTO domains (name) VALUES ('test-domain')")
    conn.execute(
        "INSERT INTO topics (name, description, domain_id) VALUES ('test-topic', 'desc', 1)"
    )
    conn.commit()
    conn.close()

    yield db_path
    http_api.DB_PATH = original_db_path


@pytest.fixture()
def client(_test_db):
    from research_harness_mcp.http_api import app

    return TestClient(app)


def test_tier_configs():
    from research_harness.tiers import ECONOMY, PREMIUM, STANDARD, get_tier

    assert ECONOMY.retries_after_rubric_miss == 0
    assert ECONOMY.judge_mode == "single"
    assert STANDARD.retries_after_rubric_miss == 1
    assert PREMIUM.retries_after_rubric_miss == 2
    assert PREMIUM.judge_mode == "dual_all"

    assert get_tier("economy") is ECONOMY
    assert get_tier("standard") is STANDARD
    assert get_tier("premium") is PREMIUM
    assert get_tier(None) is STANDARD
    assert get_tier("unknown") is STANDARD


def test_get_venues_empty(client: TestClient):
    resp = client.get("/api/venues")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_topic_autonomy_default(client: TestClient):
    resp = client.get("/api/topics/1/autonomy")
    assert resp.status_code == 200
    assert resp.json()["level"] == "L2"


def test_patch_topic_autonomy(client: TestClient):
    resp = client.patch("/api/topics/1/autonomy", json={"level": "L3"})
    assert resp.status_code == 200
    assert resp.json()["level"] == "L3"

    resp2 = client.get("/api/topics/1/autonomy")
    assert resp2.json()["level"] == "L3"


def test_patch_topic_autonomy_invalid(client: TestClient):
    resp = client.patch("/api/topics/1/autonomy", json={"level": "L5"})
    assert resp.status_code == 422


def test_get_topic_tier_default(client: TestClient):
    resp = client.get("/api/topics/1/tier")
    assert resp.status_code == 200
    data = resp.json()
    assert data["quality_tier"] == "standard"
    assert "config" in data
    assert data["config"]["retries"] == 1


def test_patch_topic_tier(client: TestClient):
    resp = client.patch("/api/topics/1/tier", json={"tier": "premium"})
    assert resp.status_code == 200
    assert resp.json()["quality_tier"] == "premium"

    resp2 = client.get("/api/topics/1/tier")
    assert resp2.json()["quality_tier"] == "premium"
    assert resp2.json()["config"]["retries"] == 2


def test_patch_topic_tier_invalid(client: TestClient):
    resp = client.patch("/api/topics/1/tier", json={"tier": "ultra"})
    assert resp.status_code == 422


def test_topic_not_found_autonomy(client: TestClient):
    resp = client.get("/api/topics/9999/autonomy")
    assert resp.status_code == 404


def test_topic_not_found_tier(client: TestClient):
    resp = client.get("/api/topics/9999/tier")
    assert resp.status_code == 404
