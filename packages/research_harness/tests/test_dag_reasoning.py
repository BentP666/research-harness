"""Tests for v2 Step 10 — opt-in DAG gap detection pilot."""

from __future__ import annotations

import pytest

from research_harness.execution.dag_reasoning import (
    DAGGap,
    _dedup_gaps,
    _kmeans_cluster,
    _partition_papers,
    gap_detect_dag,
    is_dag_enabled,
)
from research_harness.primitives.types import Gap, GapDetectOutput
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_HARNESS_EMBEDDING_PROVIDER", "fake")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


def _seed_topic_with_papers(db: Database, n: int = 6) -> int:
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)",
            ("dag-topic", "test"),
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        for i in range(n):
            conn.execute(
                "INSERT INTO papers (id, title, status, s2_id, doi, arxiv_id, year) "
                "VALUES (?, ?, 'active', ?, ?, ?, ?)",
                (
                    100 + i,
                    f"Paper about {'vision' if i % 2 == 0 else 'language'} topic {i}",
                    f"s2_dag_{i}",
                    f"10.dag/{i}",
                    f"arxiv_dag_{i}",
                    2025 - (i % 3),
                ),
            )
            conn.execute(
                "INSERT INTO paper_annotations (paper_id, section, content) "
                "VALUES (?, 'abstract', ?)",
                (
                    100 + i,
                    f"Abstract talking about {'images' if i % 2 == 0 else 'text'}",
                ),
            )
            conn.execute(
                "INSERT INTO paper_topics (paper_id, topic_id) VALUES (?, ?)",
                (100 + i, tid),
            )
        conn.commit()
        return tid
    finally:
        conn.close()


def test_is_dag_enabled_respects_env(monkeypatch):
    monkeypatch.delenv("RESEARCH_HARNESS_GAP_DAG", raising=False)
    assert is_dag_enabled() is False
    monkeypatch.setenv("RESEARCH_HARNESS_GAP_DAG", "0")
    assert is_dag_enabled() is False
    monkeypatch.setenv("RESEARCH_HARNESS_GAP_DAG", "1")
    assert is_dag_enabled() is True


def test_kmeans_handles_small_inputs():
    # k>n should not explode.
    assignments = _kmeans_cluster([[1.0, 0.0]], k=4)
    assert assignments == [0]
    # k<=1 is a no-op.
    assignments = _kmeans_cluster([[1.0, 0.0], [0.0, 1.0]], k=1)
    assert assignments == [0, 0]


def test_kmeans_separates_two_clusters():
    vecs = [
        [1.0, 0.0, 0.0],
        [0.99, 0.01, 0.0],
        [0.0, 1.0, 0.0],
        [0.01, 0.99, 0.0],
    ]
    assignments = _kmeans_cluster(vecs, k=2, seed=7)
    # Two distinct cluster labels used.
    assert len(set(assignments)) == 2
    # Vectors 0,1 in one cluster; vectors 2,3 in the other.
    assert assignments[0] == assignments[1]
    assert assignments[2] == assignments[3]
    assert assignments[0] != assignments[2]


def test_partition_papers_splits_into_buckets(db):
    tid = _seed_topic_with_papers(db, n=8)
    papers = [{"id": 100 + i, "title": f"t{i}", "abstract": f"a{i}"} for i in range(8)]
    buckets = _partition_papers(db, papers, k=3)
    assert 1 <= len(buckets) <= 3
    total = sum(len(b) for b in buckets)
    assert total == 8
    _ = tid


def test_dedup_merges_by_description():
    gaps = [
        DAGGap(
            description="No cross-domain benchmarks exist",
            severity="medium",
            confidence=0.5,
            sources=["cluster:0"],
        ),
        DAGGap(
            description="no cross-domain benchmarks  exist",
            severity="high",
            confidence=0.8,
            sources=["cluster:1"],
        ),
        DAGGap(
            description="Another gap",
            severity="low",
            confidence=0.3,
            sources=["cluster:2"],
        ),
    ]
    merged = _dedup_gaps(gaps)
    assert len(merged) == 2
    first = next(g for g in merged if "cross-domain" in g.description.lower())
    assert first.confidence == pytest.approx(0.8)
    assert first.severity == "high"
    assert sorted(first.sources) == ["cluster:0", "cluster:1"]


def test_gap_detect_dag_persists_with_stub_leaf(db):
    tid = _seed_topic_with_papers(db, n=6)

    calls: list[int] = []

    def stub_leaf(*, db, topic_id, focus, _paper_ids=None):
        calls.append(len(_paper_ids or []))
        return GapDetectOutput(
            gaps=[
                Gap(
                    gap_id="",
                    description=f"Gap from {focus}",
                    gap_type="benchmark",
                    severity="medium",
                    related_paper_ids=_paper_ids or [],
                    confidence=0.6,
                )
            ],
            papers_analyzed=len(_paper_ids or []),
        )

    result = gap_detect_dag(
        db=db,
        topic_id=tid,
        focus="initial",
        cluster_count=3,
        persist=True,
        leaf_fn=stub_leaf,
    )
    assert result.cluster_count >= 1
    assert result.papers_analyzed == 6
    assert len(result.gaps) >= 1
    assert calls, "stub leaf should have been invoked per cluster"

    # Gaps were persisted.
    conn = db.connect()
    try:
        rows = conn.execute("SELECT id FROM gaps WHERE topic_id = ?", (tid,)).fetchall()
        assert len(rows) >= 1
    finally:
        conn.close()


def test_gap_detect_dag_handles_empty_topic(db):
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES ('empty-dag', 't')"
        )
        tid = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (tid, tid, "stub", "stub"),
        )
        conn.commit()
    finally:
        conn.close()

    called = {"n": 0}

    def stub_leaf(**kwargs):
        called["n"] += 1
        return GapDetectOutput(gaps=[], papers_analyzed=0)

    result = gap_detect_dag(
        db=db, topic_id=tid, focus="", cluster_count=3, leaf_fn=stub_leaf
    )
    assert result.gaps == []
    assert result.cluster_count == 0
    assert called["n"] == 0
