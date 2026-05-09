"""Tests for deterministic head_paper_rank primitive."""

from __future__ import annotations

import pytest

from research_harness.primitives.head_paper import (
    CCF_RANK_SCORE,
    UNRANKED_PRIOR,
    head_paper_rank,
)
from research_harness.storage.db import Database


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "hp.db")
    d.migrate()
    return d


def _seed_venue(
    conn, canonical_name: str, ccf_rank: str | None = None, impact: float | None = None
):
    conn.execute(
        "INSERT INTO venue_ranks (canonical_name, ccf_rank, impact_factor, source_snapshot) "
        "VALUES (?, ?, ?, 'test')",
        (canonical_name, ccf_rank, impact),
    )


def _seed_paper(conn, pid: int, year: int, venue: str, cites: int | None) -> None:
    # Use distinct arxiv_id/s2_id per paper to avoid UNIQUE violations
    conn.execute(
        "INSERT INTO papers (id, title, authors, year, venue, abstract, "
        "citation_count, s2_id, arxiv_id, doi) "
        "VALUES (?, ?, '[]', ?, ?, '', ?, ?, ?, ?)",
        (
            pid,
            f"paper {pid}",
            year,
            venue,
            cites,
            f"s2_{pid}",
            f"arxiv_{pid}",
            f"10.test/{pid}",
        ),
    )


def test_empty_input_returns_empty(db):
    out = head_paper_rank(db=db, year=2024, paper_ids=[])
    assert out.ranked == []


def test_orders_by_citation_when_venue_equal(db):
    conn = db.connect()
    try:
        _seed_venue(conn, "nips", ccf_rank="A")
        for pid, cites in [(1, 10), (2, 200), (3, 50)]:
            _seed_paper(conn, pid, 2022, "nips", cites)
        conn.commit()
    finally:
        conn.close()

    out = head_paper_rank(db=db, year=2022, paper_ids=[1, 2, 3], current_year=2024)
    ids = [r.paper_id for r in out.ranked]
    # Paper 2 (200 cites) > paper 3 (50 cites) > paper 1 (10 cites)
    assert ids == [2, 3, 1]


def test_current_year_falls_back_to_venue_quality(db):
    conn = db.connect()
    try:
        _seed_venue(conn, "nips", ccf_rank="A")
        _seed_venue(conn, "obscure workshop", ccf_rank=None)
        _seed_paper(conn, 1, 2026, "nips", None)  # 0 cites, but A venue
        _seed_paper(conn, 2, 2026, "obscure workshop", None)  # 0 cites, unranked
        conn.commit()
    finally:
        conn.close()

    out = head_paper_rank(db=db, year=2026, paper_ids=[1, 2], current_year=2026)
    assert out.ranked[0].paper_id == 1
    # A-rank venue (0.8) vs unranked prior (0.4)
    assert out.ranked[0].venue_q == CCF_RANK_SCORE["A"]
    assert out.ranked[1].venue_q == UNRANKED_PRIOR


def test_unknown_venue_gets_prior(db):
    conn = db.connect()
    try:
        _seed_paper(conn, 1, 2022, "somewhere not in table", 100)
        conn.commit()
    finally:
        conn.close()

    out = head_paper_rank(db=db, year=2022, paper_ids=[1], current_year=2024)
    assert out.ranked[0].venue_q == UNRANKED_PRIOR


def test_target_trims_to_top_n(db):
    conn = db.connect()
    try:
        _seed_venue(conn, "nips", ccf_rank="A")
        for pid, cites in [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]:
            _seed_paper(conn, pid, 2022, "nips", cites)
        conn.commit()
    finally:
        conn.close()

    out = head_paper_rank(
        db=db, year=2022, paper_ids=[1, 2, 3, 4, 5], current_year=2024, target=2
    )
    assert len(out.ranked) == 2
    assert [r.paper_id for r in out.ranked] == [5, 4]


def test_recency_favours_recent_when_cites_similar(db):
    conn = db.connect()
    try:
        _seed_venue(conn, "nips", ccf_rank="A")
        _seed_paper(conn, 1, 2018, "nips", 100)
        _seed_paper(conn, 2, 2024, "nips", 100)
        conn.commit()
    finally:
        conn.close()

    out = head_paper_rank(db=db, year=2024, paper_ids=[1, 2], current_year=2024)
    # Both have same citation_count but paper 2 is much fresher → should
    # come first after recency decay
    assert out.ranked[0].paper_id == 2
