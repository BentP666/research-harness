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
