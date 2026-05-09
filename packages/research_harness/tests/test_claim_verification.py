"""Tests for v2 Step 5.1 — bounded claim verification.

Covers:
- Deterministic prefilter groups claims by (task, dataset, metric)
- Pair budget is respected (hard cap 200, honored here as smaller values)
- Pair check function is called once per pair
- Contradictions persist to DB when persist=True
- Figure/table modality claims are flagged for human review
- Empty topic returns zero counts
"""

from __future__ import annotations

import pytest

from research_harness.execution.claim_verification import (
    ClaimVerificationResult,
    ContradictionCandidate,
    NormalizedClaimRow,
    PairResult,
    _enumerate_candidate_pairs,
    _group_key,
    verify_claims,
)
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


@pytest.fixture
def topic_with_claims(db):
    """Create a topic + 5 normalized claims across 2 groups:
    Group A (task=cls, dataset=imagenet, metric=acc): claims 1, 2, 3
    Group B (task=seg, dataset=coco, metric=iou): claims 4, 5
    """
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)", ("t", "t")
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (topic_id, topic_id, "stub", "stub"),
        )
        # Seed papers
        for pid in (10, 11, 12, 13, 14):
            conn.execute(
                "INSERT INTO papers (id, title, status, s2_id, doi, arxiv_id) VALUES (?, ?, 'active', ?, ?, ?)",
                (pid, f"paper {pid}", f"s2_{pid}", f"10.test/{pid}", f"arxiv_{pid}"),
            )

        claims = [
            # Group A
            (10, "X is 95% acc on ImageNet", "cls", "imagenet", "acc"),
            (11, "X is 60% acc on ImageNet", "cls", "imagenet", "acc"),
            (12, "X is 90% acc on ImageNet", "cls", "imagenet", "acc"),
            # Group B
            (13, "Y reaches 0.8 IoU on COCO", "seg", "coco", "iou"),
            (14, "Y reaches 0.5 IoU on COCO", "seg", "coco", "iou"),
        ]
        for paper_id, text, task, dataset, metric in claims:
            conn.execute(
                """
                INSERT INTO normalized_claims
                (topic_id, paper_id, claim_text, method, dataset, metric, task, value, direction, confidence, modality)
                VALUES (?, ?, ?, '', ?, ?, ?, '', 'higher_better', 0.8, 'text')
                """,
                (topic_id, paper_id, text, dataset, metric, task),
            )
        conn.commit()
        return topic_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Prefilter
# ---------------------------------------------------------------------------


def test_group_key_uses_task_canonical_fallback():
    c = NormalizedClaimRow(
        id=1,
        topic_id=1,
        paper_id=1,
        claim_text="t",
        method="",
        dataset="ImageNet",
        metric="Acc",
        task="cls",
        task_canonical="",
        modality="text",
        confidence=0.5,
    )
    assert _group_key(c) == "cls|imagenet|acc"


def test_enumerate_pairs_within_group_only(topic_with_claims, db):
    from research_harness.execution.claim_verification import _load_normalized_claims

    claims = _load_normalized_claims(db, topic_with_claims)
    pairs, considered = _enumerate_candidate_pairs(claims, pair_budget=100)
    # Group A has 3 claims (3 pairs). Group B has 2 claims (1 pair). Total=4.
    assert considered == 4
    assert len(pairs) == 4
    # All pairs must be intra-group
    for p in pairs:
        key_a = _group_key(p.claim_a)
        key_b = _group_key(p.claim_b)
        assert key_a == key_b


def test_enumerate_pairs_respects_small_budget(topic_with_claims, db):
    from research_harness.execution.claim_verification import _load_normalized_claims

    claims = _load_normalized_claims(db, topic_with_claims)
    pairs, considered = _enumerate_candidate_pairs(claims, pair_budget=2)
    assert considered == 4
    assert len(pairs) == 2


# ---------------------------------------------------------------------------
# verify_claims integration
# ---------------------------------------------------------------------------


def test_verify_claims_uses_pair_check_fn(topic_with_claims, db):
    """A stub pair_check_fn marks ALL pairs as contradicting to verify the
    result plumbing."""
    calls: list[ContradictionCandidate] = []

    def stub(pair: ContradictionCandidate) -> PairResult:
        calls.append(pair)
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=True,
            reason="stubbed contradiction",
            confidence=0.9,
        )

    result = verify_claims(
        db,
        topic_with_claims,
        pair_budget=10,
        pair_check_fn=stub,
        persist=False,
    )

    assert isinstance(result, ClaimVerificationResult)
    assert result.total_claims == 5
    assert result.pairs_considered == 4
    assert result.pairs_checked == 4
    assert result.contradictions_found == 4
    assert len(calls) == 4


def test_verify_claims_empty_topic_returns_zero(db):
    """No normalized_claims -> returns zero with no LLM calls."""
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)", ("empty", "empty")
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (topic_id, topic_id, "stub", "stub"),
        )
        conn.commit()
    finally:
        conn.close()

    called = {"n": 0}

    def stub(pair: ContradictionCandidate) -> PairResult:
        called["n"] += 1
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=False,
            reason="",
            confidence=0.0,
        )

    result = verify_claims(db, topic_id, pair_check_fn=stub, persist=False)
    assert result.total_claims == 0
    assert result.pairs_considered == 0
    assert result.pairs_checked == 0
    assert called["n"] == 0


def test_verify_claims_persists_contradictions(topic_with_claims, db):
    def stub(pair: ContradictionCandidate) -> PairResult:
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=True,
            reason="stub",
            confidence=0.8,
        )

    result = verify_claims(
        db, topic_with_claims, pair_budget=10, pair_check_fn=stub, persist=True
    )
    assert result.contradictions_found == 4

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT claim_a_id, claim_b_id, conflict_reason FROM contradictions WHERE topic_id = ?",
            (topic_with_claims,),
        ).fetchall()
        assert len(rows) == 4
    finally:
        conn.close()


def test_verify_claims_flags_figure_modality(db):
    """Claims with modality in {figure, table, equation} are flagged for human."""
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)", ("fig", "fig")
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (topic_id, topic_id, "stub", "stub"),
        )
        for pid in (1, 2, 3):
            conn.execute(
                "INSERT INTO papers (id, title, status, s2_id, doi, arxiv_id) VALUES (?, ?, 'active', ?, ?, ?)",
                (pid, f"p{pid}", f"s2_fig_{pid}", f"10.fig/{pid}", f"arxiv_fig_{pid}"),
            )
        # One text, one figure, one table
        conn.execute(
            """INSERT INTO normalized_claims
            (topic_id, paper_id, claim_text, method, dataset, metric, task, value, direction, confidence, modality)
            VALUES (?, 1, 'c1', '', 'x', 'acc', 't', '', 'higher_better', 0.8, 'text')""",
            (topic_id,),
        )
        conn.execute(
            """INSERT INTO normalized_claims
            (topic_id, paper_id, claim_text, method, dataset, metric, task, value, direction, confidence, modality)
            VALUES (?, 2, 'c2', '', 'x', 'acc', 't', '', 'higher_better', 0.8, 'figure')""",
            (topic_id,),
        )
        conn.execute(
            """INSERT INTO normalized_claims
            (topic_id, paper_id, claim_text, method, dataset, metric, task, value, direction, confidence, modality)
            VALUES (?, 3, 'c3', '', 'x', 'acc', 't', '', 'higher_better', 0.8, 'table')""",
            (topic_id,),
        )
        conn.commit()
    finally:
        conn.close()

    def stub(pair):
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=False,
            reason="",
            confidence=0.0,
        )

    result = verify_claims(db, topic_id, pair_check_fn=stub, persist=False)
    assert len(result.flagged_for_human_review) == 2
