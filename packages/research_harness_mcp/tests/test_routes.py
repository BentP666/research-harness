"""Regression tests for HTTP route ordering bugs.

Some literal sub-paths under /api/domains were being swallowed by the
{domain_id:int} parameterized route because they were declared after it
in the file. Pin them down here so they don't regress.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "routes.db"
    from research_harness.storage.db import Database

    Database(db_path).migrate()

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


def test_domain_trends_get_not_swallowed_by_domain_id(client: TestClient):
    """GET /api/domains/trends must hit the trends endpoint, not be parsed as
    domain_id="trends" (which would 422)."""
    r = client.get("/api/domains/trends")
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_domain_trends_with_query_params(client: TestClient):
    r = client.get("/api/domains/trends?tier=standard&limit=5")
    assert r.status_code == 200, r.text


def test_domain_id_route_still_works_for_real_ids(client: TestClient):
    """Sanity: parameterized route is intact for real numeric ids."""
    r = client.get("/api/domains/999999")
    # 404 is expected (domain doesn't exist) — what matters is NOT 422.
    assert r.status_code == 404, r.text


def test_discover_weekly_sample_endpoint(client: TestClient):
    r = client.get("/api/discover/weekly?sample=true&generated_at=2026-05-10")

    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["product"] == "RH Discover"
    assert payload["generated_at"] == "2026-05-10"
    assert len(payload["briefs"]) >= 3
    assert payload["briefs"][0]["rh_handoff"]["initial_queries"]


def test_discover_sources_endpoint(client: TestClient):
    r = client.get("/api/discover/sources")

    assert r.status_code == 200, r.text
    payload = r.json()
    families = {source["family"] for source in payload}
    assert {"papers", "blogs", "repos_models", "social"} <= families


def test_discover_issue_archive_and_latest_endpoint(client: TestClient):
    archive = client.get("/api/discover/issues?cadence=weekly")
    latest = client.get("/api/discover/issues/latest?cadence=weekly")
    weekly = client.get("/api/discover/weekly?sample=false")

    assert archive.status_code == 200, archive.text
    issues = archive.json()
    assert any(issue["issue_id"] == "demo-weekly" for issue in issues)

    assert latest.status_code == 200, latest.text
    assert latest.json()["issue_id"] == issues[0]["issue_id"]
    assert latest.json()["briefs"][0]["rh_handoff"]["initial_queries"]

    assert weekly.status_code == 200, weekly.text
    assert weekly.json()["issue_id"] == latest.json()["issue_id"]


def test_discover_opportunities_list_detail_and_handoff(client: TestClient):
    opportunities = client.get("/api/discover/opportunities?sample=true")

    assert opportunities.status_code == 200, opportunities.text
    payload = opportunities.json()
    assert payload["issue_id"].startswith("sample-weekly-")
    assert payload["opportunities"]
    first = payload["opportunities"][0]
    assert first["slug"]
    assert first["readiness"]["goalability"] >= 0.0
    assert first["goal_previews"]

    detail = client.get(f"/api/discover/opportunities/{first['slug']}?sample=true")
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["slug"] == first["slug"]
    assert detail_payload["brief"]["rh_handoff"]["initial_queries"]

    handoff = client.post(
        f"/api/discover/opportunities/{first['slug']}/handoff?sample=true",
        json={
            "user_profile": {
                "level": "masters",
                "compute_budget": "cpu_only",
                "deadline_days": 90,
            },
            "selected_goal_preview_ids": [first["goal_previews"][0]["id"]],
        },
    )
    assert handoff.status_code == 200, handoff.text
    handoff_payload = handoff.json()
    assert handoff_payload["created"] is True
    assert handoff_payload["topic_id"] > 0
    assert handoff_payload["topic_name"] == first["rh_handoff"]["topic_name"]
    assert handoff_payload["goal_seeds"][0]["id"] == first["goal_previews"][0]["id"]
    assert handoff_payload["next_url"] == f"/topics/{handoff_payload['topic_id']}"

    topic = client.get(f"/api/topics/{handoff_payload['topic_id']}")
    assert topic.status_code == 200, topic.text
    assert "RH Discovery handoff" in topic.json()["description"]
