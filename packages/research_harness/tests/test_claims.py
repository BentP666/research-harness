"""Tests for claim tracking and UngroundedClaimError."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.storage.db import Database


@pytest.fixture()
def db_with_artifact(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    db.migrate()
    conn = db.connect()
    conn.execute("INSERT INTO domains (name) VALUES ('d')")
    conn.execute(
        "INSERT INTO topics (name, description, domain_id) VALUES ('t', 'd', 1)"
    )
    conn.execute(
        "INSERT INTO orchestrator_runs (topic_id, mode, current_stage, stage_status) VALUES (1, 'standard', 'analyze', 'in_progress')"
    )
    conn.execute(
        "INSERT INTO project_artifacts (topic_id, stage, artifact_type, title, version, status) VALUES (1, 'analyze', 'claim_set', 'Claims', 1, 'accepted')"
    )
    conn.execute(
        "INSERT INTO papers (title, authors, year, venue) VALUES ('Test Paper', '[]', 2024, 'AAAI')"
    )
    conn.commit()
    conn.close()
    return db


def test_write_claim_with_citation(db_with_artifact: Database):
    from research_harness.orchestrator.claims import write_claim

    conn = db_with_artifact.connect()
    try:
        claim_id = write_claim(
            conn,
            artifact_id=1,
            topic_id=1,
            text="LLMs improve bidding",
            claim_type="empirical",
            citation_paper_ids=[1],
            evidence_quotes=["Section 4 shows 15% improvement"],
        )
        conn.commit()
        assert claim_id is not None

        row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        assert row["text"] == "LLMs improve bidding"

        cit = conn.execute(
            "SELECT * FROM claim_citations WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        assert cit["paper_id"] == 1
        assert "15%" in cit["evidence_quote"]
    finally:
        conn.close()


def test_ungrounded_claim_raises(db_with_artifact: Database):
    from research_harness.orchestrator.claims import UngroundedClaimError, write_claim

    conn = db_with_artifact.connect()
    try:
        with pytest.raises(UngroundedClaimError):
            write_claim(
                conn,
                artifact_id=1,
                topic_id=1,
                text="Unsupported claim",
                citation_paper_ids=[],
            )
    finally:
        conn.close()


def test_ungrounded_claim_none_citations(db_with_artifact: Database):
    from research_harness.orchestrator.claims import UngroundedClaimError, write_claim

    conn = db_with_artifact.connect()
    try:
        with pytest.raises(UngroundedClaimError):
            write_claim(
                conn,
                artifact_id=1,
                topic_id=1,
                text="Another unsupported claim",
            )
    finally:
        conn.close()
