"""Tests for candidate_seed + upsert + recommendations_generate pipeline."""

from __future__ import annotations


import pytest

from research_harness.primitives.candidate_seed import (
    CandidateDraft,
    seed_candidates,
    upsert_candidate,
)
from research_harness.primitives.recommend import recommendations_generate
from research_harness.storage.db import Database


@pytest.fixture()
def seeded(tmp_path):
    """Topic with 2 papers, 2 gaps (high+medium), 1 contradiction."""
    d = Database(tmp_path / "seed.db")
    d.migrate()
    conn = d.connect()
    try:
        # Domain + research_area
        conn.execute("INSERT INTO domains (name) VALUES ('cs.LG')")
        domain_id = conn.execute("SELECT id FROM domains").fetchone()[0]
        conn.execute(
            "INSERT INTO research_areas (domain_id, name, slug, source) "
            "VALUES (?, 'area-X', 'area-x', 'llm')",
            (domain_id,),
        )
        area_id = conn.execute("SELECT id FROM research_areas").fetchone()[0]

        # Topic with 2 papers
        conn.execute("INSERT INTO topics (name) VALUES ('paper-being-written')")
        topic_id = conn.execute("SELECT id FROM topics").fetchone()[0]
        for pid, venue in [(1, "nips"), (2, "icml")]:
            conn.execute(
                "INSERT INTO papers (id, title, authors, year, venue, "
                "affiliations, abstract, arxiv_id, s2_id, doi) "
                "VALUES (?, 'p', '[]', 2024, ?, '[]', '', ?, ?, ?)",
                (pid, venue, f"ax{pid}", f"s{pid}", f"10.t/{pid}"),
            )
            conn.execute(
                "INSERT INTO paper_topics (paper_id, topic_id, relevance) "
                "VALUES (?, ?, 'high')",
                (pid, topic_id),
            )
            conn.execute(
                "INSERT INTO paper_domains (paper_id, domain_id, is_primary) "
                "VALUES (?, ?, 1)",
                (pid, domain_id),
            )
            conn.execute(
                "INSERT INTO paper_research_areas "
                "(paper_id, research_area_id, is_primary) VALUES (?, ?, 1)",
                (pid, area_id),
            )

        # 2 gaps: one high, one low (low is below default min_severity=medium)
        conn.execute(
            "INSERT INTO gaps (topic_id, description, severity, "
            "related_paper_ids) "
            "VALUES (?, 'No benchmark for cold-start GNN', 'high', '[1,2]')",
            (topic_id,),
        )
        conn.execute(
            "INSERT INTO gaps (topic_id, description, severity, "
            "related_paper_ids) "
            "VALUES (?, 'Minor wording issue in Table 1', 'low', '[1]')",
            (topic_id,),
        )
        # 1 contradiction
        conn.execute(
            "INSERT INTO normalized_claims (topic_id, paper_id, claim_text, method, task) "
            "VALUES (?, 1, 'GNN > baseline by 5pp', 'GNN', 'node classification')",
            (topic_id,),
        )
        conn.execute(
            "INSERT INTO normalized_claims (topic_id, paper_id, claim_text, method, task) "
            "VALUES (?, 2, 'GNN = baseline (null diff)', 'GNN', 'node classification')",
            (topic_id,),
        )
        claim_a, claim_b = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM normalized_claims ORDER BY id"
            ).fetchall()
        ]
        conn.execute(
            "INSERT INTO contradictions (topic_id, claim_a_id, claim_b_id, "
            "conflict_reason, status) "
            "VALUES (?, ?, ?, 'disagreement on gain', 'candidate')",
            (topic_id, claim_a, claim_b),
        )
        conn.commit()
        yield d, {"topic_id": topic_id, "domain_id": domain_id, "area_id": area_id}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# seed_candidates
# ---------------------------------------------------------------------------


def test_seed_candidates_yields_gap_and_contradiction(seeded):
    db, ids = seeded
    drafts = seed_candidates(db=db, scope=f"topic:{ids['topic_id']}")
    families = [d.primary_signal_family for d in drafts]
    assert "gap" in families
    assert "contradiction" in families
    # High-severity gap should emit, low should not (default min=medium)
    assert any("cold-start" in d.pitch for d in drafts)
    assert not any("wording" in d.pitch for d in drafts)


def test_seed_candidates_attaches_taxonomy(seeded):
    db, ids = seeded
    drafts = seed_candidates(db=db, scope=f"topic:{ids['topic_id']}")
    assert all(d.primary_domain_id == ids["domain_id"] for d in drafts)
    assert all(d.research_area_ids == [ids["area_id"]] for d in drafts)


def test_seed_candidates_min_severity_low_includes_all(seeded):
    db, ids = seeded
    drafts = seed_candidates(
        db=db, scope=f"topic:{ids['topic_id']}", min_gap_severity="low"
    )
    pitches = " ".join(d.pitch for d in drafts)
    assert "wording" in pitches
    assert "cold-start" in pitches


def test_seed_candidates_invalid_scope_raises():
    d = Database(":memory:")
    d.migrate()
    with pytest.raises(ValueError):
        seed_candidates(db=d, scope="nonsense")


def test_lineage_key_stable_across_recreation():
    """Same draft fields → same lineage_key, regardless of object identity."""
    a = CandidateDraft(
        scope="topic:1",
        title="X",
        pitch="Some gap",
        primary_signal_family="gap",
        primary_signal_id=1,
    )
    b = CandidateDraft(
        scope="topic:1",
        title="X",
        pitch="Some gap",
        primary_signal_family="gap",
        primary_signal_id=1,
    )
    assert a.lineage_key() == b.lineage_key()


def test_evidence_signature_changes_on_new_evidence():
    a = CandidateDraft(
        scope="topic:1",
        title="X",
        pitch="G",
        primary_signal_family="gap",
        primary_signal_id=1,
        evidence_gap_ids=[1],
    )
    b = CandidateDraft(
        scope="topic:1",
        title="X",
        pitch="G",
        primary_signal_family="gap",
        primary_signal_id=1,
        evidence_gap_ids=[1, 2],  # new evidence
    )
    assert a.lineage_key() == b.lineage_key()  # stable
    assert a.evidence_signature() != b.evidence_signature()  # changes


# ---------------------------------------------------------------------------
# upsert_candidate
# ---------------------------------------------------------------------------


def test_upsert_creates_new_row(seeded):
    db, ids = seeded
    d = CandidateDraft(
        scope=f"topic:{ids['topic_id']}",
        title="T",
        pitch="p",
        primary_signal_family="gap",
        primary_signal_id=42,
        primary_domain_id=ids["domain_id"],
    )
    cid = upsert_candidate(db=db, scope=d.scope, draft=d, llm_score=7.5)
    assert cid > 0

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT title, llm_score, lineage_key FROM research_candidates "
            "WHERE id = ?",
            (cid,),
        ).fetchone()
    finally:
        conn.close()
    assert row["title"] == "T"
    assert float(row["llm_score"]) == 7.5
    assert row["lineage_key"] == d.lineage_key()


def test_upsert_idempotent_when_evidence_unchanged(seeded):
    db, ids = seeded
    d = CandidateDraft(
        scope=f"topic:{ids['topic_id']}",
        title="T",
        pitch="p",
        primary_signal_family="gap",
        primary_signal_id=42,
        evidence_gap_ids=[1],
    )
    cid1 = upsert_candidate(db=db, scope=d.scope, draft=d, llm_score=5.0)
    cid2 = upsert_candidate(db=db, scope=d.scope, draft=d, llm_score=9.9)
    assert cid1 == cid2

    conn = db.connect()
    try:
        score = conn.execute(
            "SELECT llm_score FROM research_candidates WHERE id = ?", (cid1,)
        ).fetchone()[0]
    finally:
        conn.close()
    # second upsert was a no-op because evidence_signature unchanged
    assert float(score) == 5.0


def test_upsert_updates_on_new_evidence_preserves_status(seeded):
    db, ids = seeded
    base = CandidateDraft(
        scope=f"topic:{ids['topic_id']}",
        title="T",
        pitch="p",
        primary_signal_family="gap",
        primary_signal_id=42,
        evidence_gap_ids=[1],
    )
    cid = upsert_candidate(db=db, scope=base.scope, draft=base, llm_score=5.0)

    # Simulate user dismissing
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE research_candidates SET status = 'dismissed' WHERE id = ?",
            (cid,),
        )
        conn.commit()
    finally:
        conn.close()

    # New evidence arrives
    updated = CandidateDraft(
        scope=base.scope,
        title="T",
        pitch="p",
        primary_signal_family="gap",
        primary_signal_id=42,
        evidence_gap_ids=[1, 2],  # added evidence
    )
    cid2 = upsert_candidate(db=db, scope=updated.scope, draft=updated, llm_score=8.0)
    assert cid2 == cid

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT status, llm_score, evidence_signature "
            "FROM research_candidates WHERE id = ?",
            (cid,),
        ).fetchone()
    finally:
        conn.close()
    # Status preserved across evidence update
    assert row["status"] == "dismissed"
    assert float(row["llm_score"]) == 8.0


# ---------------------------------------------------------------------------
# recommendations_generate end-to-end (LLM skipped)
# ---------------------------------------------------------------------------


def test_recommendations_generate_end_to_end(seeded):
    db, ids = seeded
    out = recommendations_generate(
        db=db, scope=f"topic:{ids['topic_id']}", skip_llm_scoring=True
    )
    # Should produce ≥2 candidates: one from high-severity gap + one from contradiction
    assert len(out.candidates) >= 2

    # Every candidate persisted
    conn = db.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM research_candidates WHERE scope = ?",
            (f"topic:{ids['topic_id']}",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == len(out.candidates)

    # opportunity_angle populated; no LLM score when skipped
    for c in out.candidates:
        assert c.opportunity_angle in {
            "new_task_mature_method",
            "novel_method_known_task",
            "frontier",
            "red_ocean",
        }
        assert c.llm_score == 0.0
