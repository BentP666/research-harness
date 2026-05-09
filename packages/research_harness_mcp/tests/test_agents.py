"""Tests for agent registry, pairings, presets, user preferences, and demo replay."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def _test_db(tmp_path: Path):
    """Set up a fresh DB with migrations applied, patch get_db to use it."""
    db_path = tmp_path / "test.db"
    from research_harness.storage.db import Database

    db = Database(db_path)
    db.migrate()

    from research_harness_mcp import http_api

    original_db_path = http_api.DB_PATH
    http_api.DB_PATH = db_path
    yield db_path
    http_api.DB_PATH = original_db_path


@pytest.fixture()
def client(_test_db):
    from research_harness_mcp.http_api import app

    return TestClient(app)


# ---- Agent CRUD ----


def test_create_agent(client: TestClient):
    resp = client.post(
        "/api/agents",
        json={
            "nickname": "my-opus",
            "provider": "anthropic",
            "model": "claude-opus-4-7",
            "api_key_env": "ANTHROPIC_API_KEY",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["nickname"] == "my-opus"
    assert data["provider_family"] == "anthropic"
    assert data["status"] == "active"


def test_create_agent_duplicate(client: TestClient):
    payload = {
        "nickname": "dup",
        "provider": "anthropic",
        "model": "claude-opus-4-7",
        "api_key_env": "KEY",
    }
    client.post("/api/agents", json=payload)
    resp = client.post("/api/agents", json={**payload, "nickname": "dup2"})
    assert resp.status_code == 409


def test_list_agents(client: TestClient):
    client.post(
        "/api/agents",
        json={
            "nickname": "a1",
            "provider": "anthropic",
            "model": "m1",
            "api_key_env": "K",
        },
    )
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_agent(client: TestClient):
    r = client.post(
        "/api/agents",
        json={
            "nickname": "lookup",
            "provider": "openai",
            "model": "gpt-5",
            "api_key_env": "K",
        },
    )
    agent_id = r.json()["id"]
    resp = client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "lookup"


def test_patch_agent(client: TestClient):
    r = client.post(
        "/api/agents",
        json={
            "nickname": "patchme",
            "provider": "google",
            "model": "gemini-2.5",
            "api_key_env": "K",
        },
    )
    agent_id = r.json()["id"]
    resp = client.patch(f"/api/agents/{agent_id}", json={"status": "paused"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"


def test_delete_agent(client: TestClient):
    r = client.post(
        "/api/agents",
        json={
            "nickname": "deleteme",
            "provider": "kimi",
            "model": "kimi-k2",
            "api_key_env": "K",
        },
    )
    agent_id = r.json()["id"]
    resp = client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 204
    resp2 = client.get(f"/api/agents/{agent_id}")
    assert resp2.status_code == 404


# ---- Pairings ----


def _make_pair_agents(client: TestClient):
    gen = client.post(
        "/api/agents",
        json={
            "nickname": "gen-opus",
            "provider": "anthropic",
            "model": "opus-4",
            "api_key_env": "ANTHROPIC_API_KEY",
        },
    ).json()
    judge = client.post(
        "/api/agents",
        json={
            "nickname": "judge-gpt",
            "provider": "openai",
            "model": "gpt-5",
            "api_key_env": "OPENAI_API_KEY",
        },
    ).json()
    return gen["id"], judge["id"]


def test_create_pairing_success(client: TestClient):
    gen_id, judge_id = _make_pair_agents(client)
    resp = client.post(
        "/api/agents/pairings",
        json={
            "name": "my-pair",
            "generator_agent_id": gen_id,
            "judge_agent_id": judge_id,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-pair"


def test_create_pairing_same_family_rejected(client: TestClient):
    a1 = client.post(
        "/api/agents",
        json={
            "nickname": "same-fam-1",
            "provider": "openai",
            "model": "gpt-5-turbo",
            "api_key_env": "K",
        },
    ).json()
    a2 = client.post(
        "/api/agents",
        json={
            "nickname": "same-fam-2",
            "provider": "chatgpt",
            "model": "chatgpt-5",
            "api_key_env": "K",
        },
    ).json()
    resp = client.post(
        "/api/agents/pairings",
        json={
            "name": "bad-pair",
            "generator_agent_id": a1["id"],
            "judge_agent_id": a2["id"],
        },
    )
    assert resp.status_code == 422
    assert "provider families" in resp.json()["detail"].lower()


def test_list_pairings(client: TestClient):
    gen_id, judge_id = _make_pair_agents(client)
    client.post(
        "/api/agents/pairings",
        json={"name": "p1", "generator_agent_id": gen_id, "judge_agent_id": judge_id},
    )
    resp = client.get("/api/agents/pairings")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# ---- Presets ----


def test_list_presets(client: TestClient):
    resp = client.get("/api/agents/presets")
    assert resp.status_code == 200
    presets = resp.json()
    assert len(presets) == 3
    assert presets[0]["id"] == "heavy"


# ---- User preferences ----


def test_get_default_preferences(client: TestClient):
    resp = client.get("/api/user/preferences")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_quality_tier"] == "standard"
    assert data["onboarding_complete"] == 0


def test_patch_preferences(client: TestClient):
    resp = client.patch(
        "/api/user/preferences",
        json={"default_venue_tier": "A", "onboarding_complete": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_venue_tier"] == "A"
    assert data["onboarding_complete"] == 1

    resp2 = client.get("/api/user/preferences")
    assert resp2.json()["default_venue_tier"] == "A"


# ---- Demo replay ----


def test_demo_replay_list(client: TestClient):
    resp = client.get("/api/demo/replay")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    assert len(entries) >= 1


def test_demo_replay_miss(client: TestClient):
    resp = client.post(
        "/api/demo/replay",
        json={"stage": "init", "primitive": "topic_frame", "prompt": "nonexistent"},
    )
    assert resp.status_code == 404
