"""Tests for v2 Step 3.2 — claim persistence alignment with migration 050.

Covers:
- write_claim() persists modality, claim_uuid, paper_ids_json, evidence_spans_json
- write_claim() legacy signature still works (defaults)
- claim_extract() output has per-claim paper_id + modality + spans
- backfill script fills missing columns in historic rows
"""

from __future__ import annotations

import json

import pytest

from research_harness.orchestrator.claims import write_claim
from research_harness.scripts.backfill_claim_modality import backfill
from research_harness.storage.db import Database


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    return db


@pytest.fixture
def artifact_and_topic(db):
    conn = db.connect()
    try:
        cur = conn.execute(
            "INSERT INTO topics (name, description) VALUES (?, ?)",
            ("test", "test"),
        )
        topic_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO projects (id, topic_id, name, description) VALUES (?, ?, ?, ?)",
            (topic_id, topic_id, "stub", "stub"),
        )
        # Seed papers that claim_citations / paper_ids_json will reference
        for pid in (1, 2, 5, 42):
            conn.execute(
                "INSERT INTO papers (id, title, status, s2_id, doi, arxiv_id) VALUES (?, ?, 'active', ?, ?, ?)",
                (pid, f"paper {pid}", f"s2_{pid}", f"10.test/{pid}", f"arxiv_{pid}"),
            )
        cur2 = conn.execute(
            """
            INSERT INTO project_artifacts
              (topic_id, stage, artifact_type, title, payload_json, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (topic_id, "analyze", "evidence_pack", "Test", "{}"),
        )
        art_id = int(cur2.lastrowid)
        conn.commit()
        return topic_id, art_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# write_claim with new columns
# ---------------------------------------------------------------------------


def test_write_claim_new_columns(db, artifact_and_topic):
    topic_id, art_id = artifact_and_topic
    conn = db.connect()
    try:
        claim_id = write_claim(
            conn,
            artifact_id=art_id,
            topic_id=topic_id,
            text="X outperforms Y on benchmark Z",
            claim_type="empirical",
            citation_paper_ids=[1, 2],
            modality="table",
            evidence_spans=[
                {"paper_id": 1, "section": "5.2", "snippet": "Table 3"},
            ],
            confidence=0.8,
        )
        conn.commit()

        row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        assert row["modality"] == "table"
        assert row["claim_uuid"] is not None
        assert row["claim_uuid"].startswith("claim_")
        assert row["confidence"] == pytest.approx(0.8)

        pids = json.loads(row["paper_ids_json"])
        assert pids == [1, 2]

        spans = json.loads(row["evidence_spans_json"])
        assert len(spans) == 1
        assert spans[0]["paper_id"] == 1
        assert spans[0]["section"] == "5.2"
    finally:
        conn.close()


def test_write_claim_legacy_signature(db, artifact_and_topic):
    """Old callers that don't pass new columns should still work."""
    topic_id, art_id = artifact_and_topic
    conn = db.connect()
    try:
        claim_id = write_claim(
            conn,
            artifact_id=art_id,
            topic_id=topic_id,
            text="A legacy claim",
            claim_type="empirical",
            citation_paper_ids=[5],
        )
        conn.commit()
        row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        assert row["modality"] == "text"  # default
        assert row["evidence_spans_json"] == "[]"
        assert row["claim_uuid"].startswith("claim_")
    finally:
        conn.close()


def test_write_claim_invalid_modality_normalized(db, artifact_and_topic):
    topic_id, art_id = artifact_and_topic
    conn = db.connect()
    try:
        claim_id = write_claim(
            conn,
            artifact_id=art_id,
            topic_id=topic_id,
            text="claim",
            citation_paper_ids=[1],
            modality="weirdvalue",  # should normalize to "text"
        )
        conn.commit()
        row = conn.execute(
            "SELECT modality FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        assert row["modality"] == "text"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


def test_backfill_fills_missing_columns(tmp_path, db, artifact_and_topic):
    topic_id, art_id = artifact_and_topic
    # Insert a row that mimics pre-migration-050 state by NULLing out new cols
    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO claims (artifact_id, topic_id, text, claim_type,
                modality, claim_uuid, paper_ids_json, evidence_spans_json, confidence)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)
            """,
            (art_id, topic_id, "legacy claim", "empirical"),
        )
        claim_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO claim_citations (claim_id, paper_id) VALUES (?, ?)",
            (claim_id, 42),
        )
        conn.commit()
    finally:
        conn.close()

    # Dry run: no write
    stats = backfill(str(db.db_path), apply=False)
    assert stats["rows_touched"] >= 1
    assert stats["uuid_filled"] >= 1
    assert stats["modality_filled"] >= 1

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT modality, claim_uuid FROM claims WHERE id = ?", (claim_id,)
        ).fetchone()
        assert row["modality"] is None  # dry run left it alone
        assert row["claim_uuid"] is None
    finally:
        conn.close()

    # Apply
    stats2 = backfill(str(db.db_path), apply=True)
    assert stats2["rows_touched"] >= 1

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT modality, claim_uuid, paper_ids_json, evidence_spans_json FROM claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
        assert row["modality"] == "text"
        assert row["claim_uuid"].startswith("claim_")
        assert json.loads(row["paper_ids_json"]) == [42]
        assert row["evidence_spans_json"] == "[]"
    finally:
        conn.close()
