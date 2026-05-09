"""Tests for Iteration 05: goal_pool scoring (pure function) + endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from research_harness.primitives.goal_pool_impl import score_goal
from research_harness.storage.db import Database


# ---------------------------------------------------------------------------
# Pure scoring function tests (no DB, no LLM)
# ---------------------------------------------------------------------------

_FIELD_BRIEF = {
    "datasets": [
        {"name": "apple_stock", "size": "1000", "license": "MIT", "gpu_req": "cpu"},
        {"name": "NYC_Taxi", "size": "5000", "license": None, "gpu_req": "medium"},
    ],
    "baselines": [
        {
            "name": "TimeLLM",
            "paper_id": None,
            "metric_name": "MAPE",
            "metric_value": 15.2,
        },
        {
            "name": "Chronos",
            "paper_id": None,
            "metric_name": "MAPE",
            "metric_value": 18.0,
        },
    ],
    "narrative_patterns": ["reasoning-enhanced forecasting"],
    "open_challenges": [
        {"problem": "chaotic series", "maturity": "niche"},
        {"problem": "multi-horizon", "maturity": "hot"},
    ],
    "compute_bands": ["CPU-only", "1xA100"],
    "venue_options": [
        {"name": "EMNLP", "deadline": "2026-06-15", "acceptance_rate": 0.25},
    ],
    "saturation_score": 0.42,
}

_INTAKE_CPU = {
    "persona": "p3_topic_weak",
    "compute_budget": "cpu_only",
    "target_venue": "EMNLP",
    "time_to_deadline_days": 120,
}

_INTAKE_GPU = {
    "persona": "p3_topic_weak",
    "compute_budget": "multi_gpu",
    "target_venue": "NeurIPS",
    "time_to_deadline_days": 120,
}


def test_score_headroom_high():
    candidate = {
        "dataset": "apple_stock",
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 10.0,
    }
    score, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_CPU)
    assert bd.headroom > 0.5
    assert 0 <= score <= 1


def test_score_headroom_low():
    candidate = {
        "dataset": "apple_stock",
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 0.1,
    }
    score, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_CPU)
    assert bd.headroom < 0.1


def test_score_compute_fit_pass():
    candidate = {
        "dataset": "apple_stock",  # cpu
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 5.0,
    }
    _, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_CPU)
    assert bd.compute_fit == 1.0


def test_score_compute_fit_fail():
    candidate = {
        "dataset": "NYC_Taxi",  # medium GPU
        "baseline": "Chronos",
        "metric_name": "MAPE",
        "baseline_metric": 18.0,
        "target_metric_delta": 5.0,
    }
    _, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_CPU)
    assert bd.compute_fit == 0.0


def test_score_venue_fit_match():
    candidate = {
        "dataset": "apple_stock",
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 5.0,
        "target_venue": "EMNLP",
    }
    _, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_CPU)
    assert bd.venue_fit == 1.0


def test_score_venue_fit_mismatch():
    candidate = {
        "dataset": "apple_stock",
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 5.0,
        "target_venue": "NeurIPS",
    }
    _, bd = score_goal(candidate, _FIELD_BRIEF, _INTAKE_GPU)
    assert bd.venue_fit == 0.3


# ---------------------------------------------------------------------------
# Endpoint tests (mock LLM)
# ---------------------------------------------------------------------------

_MOCK_LLM_CANDIDATES = [
    {
        "dataset": "apple_stock",
        "baseline": "TimeLLM",
        "metric_name": "MAPE",
        "baseline_metric": 15.2,
        "target_metric_delta": 5.0,
        "target_venue": "EMNLP",
        "time_window_days": 90,
    },
    {
        "dataset": "NYC_Taxi",
        "baseline": "Chronos",
        "metric_name": "MAPE",
        "baseline_metric": 18.0,
        "target_metric_delta": 3.0,
        "target_venue": "EMNLP",
        "time_window_days": 120,
    },
    {
        "dataset": "solar_daily",
        "baseline": "GPT-4",
        "metric_name": "MAE",
        "baseline_metric": 0.5,
        "target_metric_delta": 0.1,
        "target_venue": "EMNLP",
    },
]


_VALID_FIELD_BRIEF = {
    "datasets": [
        {"name": "apple_stock", "size": "1000", "license": "MIT", "gpu_req": "cpu"},
    ],
    "baselines": [
        {
            "name": "TimeLLM",
            "paper_id": None,
            "metric_name": "MAPE",
            "metric_value": 15.2,
        },
    ],
    "narrative_patterns": ["reasoning-enhanced forecasting"],
    "open_challenges": [{"problem": "chaotic series", "maturity": "niche"}],
    "compute_bands": ["CPU-only"],
    "venue_options": [
        {"name": "EMNLP", "deadline": "2026-06-15", "acceptance_rate": 0.25}
    ],
    "saturation_score": 0.42,
}


def _mock_fb_retry(chat_fn, prompt, *, retries=1):
    return json.dumps(_VALID_FIELD_BRIEF)


def _mock_goal_retry(chat_fn, prompt, *, retries=1):
    return json.dumps(_MOCK_LLM_CANDIDATES)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "goal.db"
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
        conn.execute(
            """INSERT INTO topic_intake_profile
               (topic_id, persona, domain_confidence, topic_confidence,
                venue_constraint, target_venue, compute_budget, time_to_deadline_days)
               VALUES (1, 'p3_topic_weak', 80, 60, 'preferred', 'EMNLP', 'single_gpu', 120)"""
        )
        conn.commit()
    finally:
        conn.close()

    # Build a field_brief first
    with patch(
        "research_harness.primitives.field_brief_impl._call_with_transient_retry",
        side_effect=_mock_fb_retry,
    ):
        from research_harness.primitives.field_brief_impl import build_field_brief

        build_field_brief(1, db)

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


def test_post_returns_goals(client: TestClient):
    with patch(
        "research_harness.primitives.goal_pool_impl._call_with_transient_retry",
        side_effect=_mock_goal_retry,
    ):
        r = client.post("/api/topics/1/goal-pool")
    assert r.status_code == 200, r.text
    goals = r.json()
    assert isinstance(goals, list)
    assert len(goals) <= 5
    assert all("score" in g for g in goals)
    assert all("scoring_breakdown" in g for g in goals)


def test_get_returns_by_priority(client: TestClient):
    with patch(
        "research_harness.primitives.goal_pool_impl._call_with_transient_retry",
        side_effect=_mock_goal_retry,
    ):
        client.post("/api/topics/1/goal-pool")

    r = client.get("/api/topics/1/goals")
    assert r.status_code == 200, r.text
    goals = r.json()
    ranks = [g["priority_rank"] for g in goals]
    assert ranks == sorted(ranks)


def test_patch_updates_status(client: TestClient):
    with patch(
        "research_harness.primitives.goal_pool_impl._call_with_transient_retry",
        side_effect=_mock_goal_retry,
    ):
        client.post("/api/topics/1/goal-pool")

    goals = client.get("/api/topics/1/goals").json()
    goal_id = goals[0]["id"]

    r = client.patch(f"/api/topics/1/goals/{goal_id}", json={"status": "done"})
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_post_409_when_field_brief_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_path = tmp_path / "no_fb.db"
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
                venue_constraint, compute_budget)
               VALUES (1, 'p3_topic_weak', 80, 60, 'open', 'cpu_only')"""
        )
        conn.commit()
    finally:
        conn.close()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    monkeypatch.setenv("RESEARCH_HARNESS_DB_PATH", str(db_path))
    try:
        tc = TestClient(http_api.app)
        r = tc.post("/api/topics/1/goal-pool")
        assert r.status_code == 409
        assert "field brief" in r.json()["detail"].lower()
    finally:
        http_api.DB_PATH = original
