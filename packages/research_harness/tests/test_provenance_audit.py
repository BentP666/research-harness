"""Tests for migration 055 audit-substrate columns on provenance_records + decision_log."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_harness.primitives.types import PrimitiveResult
from research_harness.provenance.recorder import ProvenanceRecorder
from research_harness.storage.db import Database


@pytest.fixture()
def db() -> Database:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.db"
        d = Database(path)
        d.migrate()
        # Seed a topic so provenance_records FK (topic_id → topics.id) holds
        conn = d.connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO topics (id, name, status) "
                "VALUES (1, 'test topic', 'active')"
            )
            conn.commit()
        finally:
            conn.close()
        yield d


def _make_result(primitive: str = "claim_extract") -> PrimitiveResult:
    return PrimitiveResult(
        primitive=primitive,
        success=True,
        output={"foo": "bar"},
        started_at="2026-04-24T12:00:00",
        finished_at="2026-04-24T12:00:01",
        backend="test",
        model_used="test-model",
        cost_usd=0.01,
        error="",
        prompt_tokens=100,
        completion_tokens=50,
    )


def test_audit_columns_exist(db: Database) -> None:
    conn = db.connect()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(provenance_records)")}
        assert {
            "actor",
            "origin",
            "retry_ordinal",
            "cache_hit",
            "parallel_group",
            "skipped",
            "skip_reason",
        }.issubset(cols)

        dcols = {r[1] for r in conn.execute("PRAGMA table_info(decision_log)")}
        assert {"actor", "origin"}.issubset(dcols)
    finally:
        conn.close()


def test_recorder_persists_actor_and_origin(db: Database) -> None:
    rec = ProvenanceRecorder(db)
    rid = rec.record(
        result=_make_result(),
        input_kwargs={"x": 1},
        topic_id=1,
        stage="analyze",
        actor="auto_runner",
        origin="auto",
    )
    fetched = rec.get(rid)
    assert fetched is not None
    assert fetched.actor == "auto_runner"
    assert fetched.origin == "auto"


def test_recorder_defaults_for_legacy_callers(db: Database) -> None:
    """Callers that do not pass audit kwargs still work; columns are NULL / 0."""
    rec = ProvenanceRecorder(db)
    rid = rec.record(
        result=_make_result(),
        input_kwargs={},
        topic_id=1,
        stage="analyze",
    )
    fetched = rec.get(rid)
    assert fetched is not None
    assert fetched.actor is None
    assert fetched.origin is None
    assert fetched.retry_ordinal == 0
    assert fetched.cache_hit is False
    assert fetched.skipped is False
    assert fetched.skip_reason is None


def test_retry_ordinal_and_cache_hit_round_trip(db: Database) -> None:
    rec = ProvenanceRecorder(db)
    rid = rec.record(
        result=_make_result(),
        input_kwargs={},
        topic_id=1,
        stage="build",
        retry_ordinal=2,
        cache_hit=True,
    )
    fetched = rec.get(rid)
    assert fetched is not None
    assert fetched.retry_ordinal == 2
    assert fetched.cache_hit is True


def test_skipped_row_round_trip(db: Database) -> None:
    rec = ProvenanceRecorder(db)
    rid = rec.record(
        result=_make_result("paper_acquire"),
        input_kwargs={},
        topic_id=1,
        stage="build",
        skipped=True,
        skip_reason="gate_already_passed",
    )
    fetched = rec.get(rid)
    assert fetched is not None
    assert fetched.skipped is True
    assert fetched.skip_reason == "gate_already_passed"


def test_index_created(db: Database) -> None:
    conn = db.connect()
    try:
        idx_names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='provenance_records'"
            )
        }
        assert "idx_prov_topic_stage" in idx_names
    finally:
        conn.close()


def test_decision_log_accepts_actor_origin(db: Database) -> None:
    """OrchestratorService.record_decision must persist actor/origin."""
    from research_harness.orchestrator.service import OrchestratorService

    svc = OrchestratorService(db=db)
    out = svc.record_decision(
        topic_id=1,
        stage="analyze",
        checkpoint="pre_execute",
        choice="skip_gate_already_passed",
        reasoning="gate passed",
        actor="auto_runner",
        origin="auto",
    )
    assert out["success"] is True

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT actor, origin FROM decision_log WHERE id = ?",
            (out["decision_id"],),
        ).fetchone()
        assert row is not None
        assert row["actor"] == "auto_runner"
        assert row["origin"] == "auto"
    finally:
        conn.close()
