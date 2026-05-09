"""Smoke tests for PR 1 audit drilldown endpoints (migration 055)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_harness.primitives.types import PrimitiveResult
from research_harness.provenance.recorder import ProvenanceRecorder
from research_harness.storage.db import Database


@pytest.fixture()
def client(tmp_path: Path):
    db_path = tmp_path / "audit.db"
    db = Database(db_path)
    db.migrate()

    # Seed a topic and a handful of provenance rows (2 ran, 1 skipped) so the
    # drilldown endpoints have something to return.
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO topics (id, name, status) VALUES (1, 'test topic', 'active')"
        )
        conn.commit()
    finally:
        conn.close()

    rec = ProvenanceRecorder(db)
    for i, primitive in enumerate(["claim_extract", "gap_detect"]):
        rec.record(
            result=PrimitiveResult(
                primitive=primitive,
                success=True,
                output={"ok": True},
                started_at=f"2026-04-24T12:00:{i:02d}",
                finished_at=f"2026-04-24T12:00:{i + 1:02d}",
                backend="test",
                model_used="sonnet-4.6",
                cost_usd=0.01,
                prompt_tokens=100,
                completion_tokens=50,
            ),
            input_kwargs={},
            topic_id=1,
            stage="analyze",
            actor="auto_runner",
            origin="auto",
        )
    rec.record(
        result=PrimitiveResult(
            primitive="paper_acquire",
            success=True,
            output=None,
            started_at="2026-04-24T11:00:00",
            finished_at="2026-04-24T11:00:00",
            backend="test",
            model_used="none",
            cost_usd=0.0,
        ),
        input_kwargs={},
        topic_id=1,
        stage="analyze",
        skipped=True,
        skip_reason="gate_already_passed",
    )

    from research_harness_mcp import http_api

    original = http_api.DB_PATH
    http_api.DB_PATH = db_path
    try:
        yield TestClient(http_api.app)
    finally:
        http_api.DB_PATH = original


def test_primitives_endpoint_returns_rows(client: TestClient):
    r = client.get("/api/topics/1/primitives?stage=analyze")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "analyze"
    prims = body["primitives"]
    assert len(prims) == 3

    ran = [p for p in prims if not p["skipped"]]
    skipped = [p for p in prims if p["skipped"]]
    assert {p["primitive"] for p in ran} == {"claim_extract", "gap_detect"}
    assert skipped[0]["skip_reason"] == "gate_already_passed"
    # Audit columns surface in the payload
    assert ran[0]["actor"] == "auto_runner"
    assert ran[0]["origin"] == "auto"


def test_primitives_endpoint_rejects_unknown_stage(client: TestClient):
    r = client.get("/api/topics/1/primitives?stage=bogus")
    assert r.status_code == 400


def test_primitives_endpoint_404_for_missing_topic(client: TestClient):
    r = client.get("/api/topics/9999/primitives?stage=analyze")
    assert r.status_code == 404


def test_stage_policy_endpoint_serializes_policy(client: TestClient):
    r = client.get("/api/topics/1/stage-policy/analyze")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "analyze"
    policy = body["policy"]
    assert policy["name"] == "analyze"
    assert "claim_extract" in policy["tools"]
    assert "risk_level" in policy
    assert "invariant_violations" in body
    assert "loopback_state" in body
    assert body["loopback_state"]["rounds_used"] == 0


def test_stage_summary_endpoint_counts_ran_and_skipped(client: TestClient):
    r = client.get("/api/topics/1/stage-summary/analyze")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["primitives_ran"] == 2
    assert body["primitives_skipped"] == 1
    assert body["primitives_planned"] > 0  # STAGE_POLICIES has tools[]
    assert body["total_tokens"] == 300  # 2 * (100 + 50)
    assert body["total_cost_usd"] > 0
