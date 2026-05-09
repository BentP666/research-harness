"""Tests for gap_cross_verify primitive (no LLM — fresh_descriptions injected)."""

from __future__ import annotations

import pytest

from research_harness.primitives.gap_cross_verify import (
    _jaccard,
    _tokenize,
    gap_cross_verify,
)
from research_harness.storage.db import Database


@pytest.fixture()
def topic_with_gaps(tmp_path):
    d = Database(tmp_path / "gcv.db")
    d.migrate()
    conn = d.connect()
    try:
        conn.execute("INSERT INTO topics (name) VALUES ('t1')")
        topic_id = conn.execute("SELECT id FROM topics").fetchone()[0]
        descs = [
            "No benchmark exists for cold-start graph neural networks",
            "Missing ablation on pretraining data size for LLM distillation",
            "Wording inconsistency between Table 1 and Section 3",
        ]
        for i, desc in enumerate(descs):
            conn.execute(
                "INSERT INTO gaps (topic_id, description, severity, confidence) "
                "VALUES (?, ?, 'medium', 0.7)",
                (topic_id, desc),
            )
        conn.commit()
        yield d, topic_id, descs
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tokenization + Jaccard
# ---------------------------------------------------------------------------


def test_tokenize_strips_stopwords_and_short():
    toks = _tokenize("The benchmark of the cold-start graph neural network is")
    assert "benchmark" in toks
    assert "cold-start" in toks
    assert "graph" in toks
    # stopwords removed
    assert "the" not in toks
    assert "of" not in toks
    assert "is" not in toks


def test_jaccard_identical_is_one():
    s = "benchmark for cold-start graph neural networks"
    assert _jaccard(s, s) == 1.0


def test_jaccard_disjoint_is_zero():
    assert _jaccard("foo bar baz", "alpha beta gamma") == 0.0


def test_jaccard_partial_overlap():
    a = "benchmark for cold-start graph neural networks"
    b = "cold-start graph neural network survey"  # high overlap
    score = _jaccard(a, b)
    assert 0.3 < score < 1.0


# ---------------------------------------------------------------------------
# gap_cross_verify end-to-end
# ---------------------------------------------------------------------------


def test_cross_verify_marks_high_overlap_gaps(topic_with_gaps):
    db, topic_id, descs = topic_with_gaps
    # Fresh run re-finds gaps 0 and 1 with different wording, misses gap 2
    fresh = [
        "Benchmark missing for cold-start graph neural networks",
        "Pretraining data size ablation absent for LLM distillation",
        "Totally unrelated gap about reinforcement learning environments",
    ]
    out = gap_cross_verify(
        db=db,
        topic_id=topic_id,
        fresh_descriptions=fresh,
        min_jaccard=0.5,
    )
    assert out.sample_size == 3
    assert out.verified_count == 2

    # DB updated
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT description, cross_verified, cross_check_runs "
            "FROM gaps WHERE topic_id = ? ORDER BY id",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()
    verified = {r["description"]: r["cross_verified"] for r in rows}
    runs = {r["description"]: r["cross_check_runs"] for r in rows}
    assert verified[descs[0]] == 1
    assert verified[descs[1]] == 1
    assert verified[descs[2]] == 0
    # Every sampled gap got its run counter incremented
    assert all(v == 1 for v in runs.values())


def test_cross_verify_no_match_below_threshold(topic_with_gaps):
    db, topic_id, descs = topic_with_gaps
    fresh = ["Completely different topic about quantum computing devices"]
    out = gap_cross_verify(
        db=db, topic_id=topic_id, fresh_descriptions=fresh, min_jaccard=0.6
    )
    assert out.verified_count == 0
    conn = db.connect()
    try:
        cross = conn.execute(
            "SELECT SUM(cross_verified) FROM gaps WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    assert cross == 0


def test_cross_verify_preserves_previously_verified(topic_with_gaps):
    db, topic_id, descs = topic_with_gaps
    # Round 1: all three verified
    gap_cross_verify(
        db=db,
        topic_id=topic_id,
        fresh_descriptions=descs,
        min_jaccard=0.5,
    )
    # Round 2: fresh set only matches gap 0; verify the existing
    # flag is NOT cleared for the other two
    gap_cross_verify(
        db=db,
        topic_id=topic_id,
        fresh_descriptions=[descs[0]],
        min_jaccard=0.5,
    )
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT cross_verified, cross_check_runs FROM gaps "
            "WHERE topic_id = ? ORDER BY id",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()
    # All three remain verified (sticky)
    assert all(r["cross_verified"] == 1 for r in rows)
    # And ran twice
    assert all(r["cross_check_runs"] == 2 for r in rows)


def test_cross_verify_empty_topic_returns_zero(tmp_path):
    d = Database(tmp_path / "empty.db")
    d.migrate()
    conn = d.connect()
    try:
        conn.execute("INSERT INTO topics (name) VALUES ('empty')")
        topic_id = conn.execute("SELECT id FROM topics").fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    out = gap_cross_verify(db=d, topic_id=topic_id, fresh_descriptions=["x"])
    assert out.sample_size == 0
    assert out.verified_count == 0
