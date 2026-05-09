"""Tests for v2 Step 8 — workflow memory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from research_harness.memory import recall_similar_runs, summarize_past_topic
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Use fake embedding provider — no network.
    monkeypatch.setenv("RESEARCH_HARNESS_EMBEDDING_PROVIDER", "fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


def _insert_topic(
    db: Database,
    *,
    name: str,
    description: str,
    created_at: str | None = None,
    status: str = "active",
) -> int:
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, description, status, created_at or "2026-03-01"),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        conn.commit()
        return tid
    finally:
        conn.close()


def _record_provenance(db: Database, topic_id: int, success: int = 1) -> None:
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO provenance_records
            (primitive, category, started_at, finished_at, backend,
             topic_id, stage, input_hash, output_hash, cost_usd, success)
            VALUES ('test_primitive', 'analyze', '2026-03-01', '2026-03-01',
                    'local', ?, 'analyze', 'h1', 'h2', 0.01, ?)
            """,
            (topic_id, success),
        )
        conn.commit()
    finally:
        conn.close()


def _record_decision(
    db: Database, topic_id: int, stage: str = "analyze", choice: str = "advance"
) -> None:
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO decision_log
            (project_id, topic_id, stage, checkpoint, choice, reasoning)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (topic_id, topic_id, stage, "gate", choice, "because reasons"),
        )
        conn.commit()
    finally:
        conn.close()


def test_recall_returns_empty_on_empty_query(db):
    assert recall_similar_runs(db, "") == []
    assert recall_similar_runs(db, "   ") == []


def test_recall_ranks_by_lexical_overlap(db):
    t1 = _insert_topic(
        db,
        name="graph neural networks for molecules",
        description="GNN regression on QM9 dataset",
    )
    t2 = _insert_topic(
        db,
        name="large language model evaluation",
        description="LLM bench on MMLU and HELM",
    )
    _record_provenance(db, t1)
    _record_provenance(db, t2)

    hits = recall_similar_runs(
        db,
        "graph neural network regression on molecule datasets",
        min_age_days=0,
        max_age_days=None,
    )
    assert hits, "expected at least one hit"
    assert hits[0].topic_id == t1


def test_recall_excludes_current_topic(db):
    t1 = _insert_topic(db, name="topic alpha original", description="alpha stuff")
    t2 = _insert_topic(db, name="topic alpha partner", description="alpha stuff too")
    _record_provenance(db, t1)
    _record_provenance(db, t2)

    hits = recall_similar_runs(
        db,
        "alpha",
        exclude_topic_id=t1,
        min_age_days=0,
        max_age_days=None,
    )
    for h in hits:
        assert h.topic_id != t1


def test_recall_require_success_filter(db):
    t_ok = _insert_topic(db, name="clustering study", description="gmm on text")
    t_no = _insert_topic(db, name="clustering attempt", description="gmm on text")
    _record_provenance(db, t_ok, success=1)
    _record_provenance(db, t_no, success=0)

    hits_default = recall_similar_runs(
        db,
        "clustering",
        min_age_days=0,
        max_age_days=None,
        require_success=True,
    )
    assert {h.topic_id for h in hits_default} == {t_ok}

    hits_no_filter = recall_similar_runs(
        db,
        "clustering",
        min_age_days=0,
        max_age_days=None,
        require_success=False,
    )
    ids = {h.topic_id for h in hits_no_filter}
    assert t_ok in ids and t_no in ids


def test_recall_recency_window(db):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=10)).isoformat()
    old = (now - timedelta(days=400)).isoformat()
    t_recent = _insert_topic(
        db,
        name="recent vision paper",
        description="ViT scaling study",
        created_at=recent,
    )
    t_old = _insert_topic(
        db,
        name="old vision paper",
        description="ViT scaling study",
        created_at=old,
    )
    _record_provenance(db, t_recent)
    _record_provenance(db, t_old)

    hits = recall_similar_runs(
        db,
        "vision transformer scaling",
        min_age_days=0,
        max_age_days=90,
    )
    ids = {h.topic_id for h in hits}
    assert t_recent in ids
    assert t_old not in ids


def test_recall_hydrates_decision_highlights_on_top_hits(db):
    t1 = _insert_topic(
        db, name="retrieval augmented generation study", description="RAG bench"
    )
    _record_provenance(db, t1)
    _record_decision(db, t1, stage="analyze", choice="deepen")
    _record_decision(db, t1, stage="propose", choice="pivot")

    hits = recall_similar_runs(
        db,
        "retrieval augmented generation",
        min_age_days=0,
        max_age_days=None,
    )
    assert hits and hits[0].topic_id == t1
    assert hits[0].decision_highlights, "expected decision digest"
    assert "analyze/gate" in hits[0].decision_highlights[
        -1
    ] or "propose/gate" in " ".join(hits[0].decision_highlights)
    assert hits[0].provenance_success_count >= 1


def test_summarize_past_topic_returns_error_on_missing(db):
    assert summarize_past_topic(db, 9999)["error"].startswith("topic not found")


def test_summarize_past_topic_returns_digest(db):
    t = _insert_topic(db, name="x", description="y")
    _record_provenance(db, t)
    _record_decision(db, t)
    out = summarize_past_topic(db, t)
    assert out["name"] == "x"
    assert out["provenance_success_count"] == 1
    assert len(out["decision_highlights"]) == 1
