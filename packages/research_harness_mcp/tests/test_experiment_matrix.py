"""Tests for Iteration 07b: experiment_matrix (migration 062)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_harness.storage.db import Database


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "matrix.db"
    db = Database(db_path)
    db.migrate()

    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test', 'active')"
        )
        conn.execute("INSERT INTO projects (id, topic_id, name) VALUES (1, 1, 'test')")
        conn.execute(
            "INSERT INTO papers (id, title, s2_id, arxiv_id, doi) VALUES (1, 'Paper', 's2-1', 'arxiv-1', 'doi-1')"
        )
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (1, 1)")
        conn.execute(
            """INSERT INTO goal_pool (id, topic_id, dataset, baseline, metric_name,
               baseline_metric, target_metric_delta, score, scoring_breakdown, priority_rank)
               VALUES (1, 1, 'apple', 'TimeLLM', 'MAPE', 15.2, 5.0, 0.8, '{}', 1)"""
        )
        conn.execute(
            """INSERT INTO method_atoms (id, topic_id, source_paper_id, atom_type, name,
               description, reuse_risk)
               VALUES (1, 1, 1, 'loss', 'TCL', 'Temporal contrastive loss', 'low')"""
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


def test_build_matrix_returns_cells(client: TestClient):
    r = client.post("/api/topics/1/experiment-matrix/build")
    assert r.status_code == 200, r.text
    cells = r.json()
    assert len(cells) == 1  # 1 goal × 1 atom
    assert cells[0]["status"] == "pending"
    assert cells[0]["goal_id"] == 1


def test_get_matrix_returns_cells(client: TestClient):
    client.post("/api/topics/1/experiment-matrix/build")
    r = client.get("/api/topics/1/experiment-matrix")
    assert r.status_code == 200
    cells = r.json()
    assert len(cells) == 1


def test_build_matrix_409_no_goals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "no_goals.db"
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
        r = tc.post("/api/topics/1/experiment-matrix/build")
        assert r.status_code == 409
    finally:
        http_api.DB_PATH = original
