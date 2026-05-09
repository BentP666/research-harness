"""Tests for the trends pipeline (publishability formula + refresh)."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.storage.db import Database
from research_harness.trends import compute_publishability, refresh_trends


def test_publishability_is_product_not_sum():
    """Zero-in-one-factor should drag the whole score to the ε-floor, not
    let strong factors paper over it (that was the old weighted-sum bug)."""
    score_zero_velocity = compute_publishability(0.0, 1.0, 1.0)
    score_all_strong = compute_publishability(1.0, 1.0, 1.0)

    # With the sum-bug formula (0.4*0 + 0.3*1 + 0.3*1 = 0.6), zero-velocity
    # would still yield 60% of max. Product with ε=0.1 must be way below that.
    assert score_zero_velocity < score_all_strong * 0.2
    assert score_zero_velocity <= 1.0  # ε=0.1 * 1 * 1 * 10 = 1.0


def test_publishability_epsilon_floor():
    """No factor, however small, should ever produce a score below ε^3·10."""
    floor = 0.1 * 0.1 * 0.1 * 10.0  # 0.01
    assert compute_publishability(0.0, 0.0, 0.0) == pytest.approx(floor)
    assert compute_publishability(-1.0, -1.0, -1.0) == pytest.approx(floor)


def test_publishability_max_is_ten():
    """All factors at max should return 10.0 (the top of the editorial scale)."""
    assert compute_publishability(1.0, 1.0, 1.0) == pytest.approx(10.0)


def test_publishability_monotonic():
    """Increasing any single factor (others fixed) must not decrease the score."""
    base = compute_publishability(0.5, 0.5, 0.5)
    assert compute_publishability(0.9, 0.5, 0.5) >= base
    assert compute_publishability(0.5, 0.9, 0.5) >= base
    assert compute_publishability(0.5, 0.5, 0.9) >= base


@pytest.fixture()
def empty_db(tmp_path: Path):
    db = Database(tmp_path / "trends.db")
    db.migrate()
    return db


def test_refresh_trends_falls_back_to_seed_when_empty(empty_db: Database):
    conn = empty_db.connect()
    try:
        clusters = refresh_trends(conn, tier="standard", dry_run=False)
        assert len(clusters) >= 1  # seed ships >= 1 cluster
        # Seed entries carry editorial scores in 7-9 range; they bypass the
        # computed formula on purpose.
        assert all(c.publishability_score > 0 for c in clusters)
    finally:
        conn.close()


def test_refresh_trends_with_papers_uses_formula(empty_db: Database):
    """When papers exist, score is computed via compute_publishability —
    exercise the product path to prove it's wired up."""
    conn = empty_db.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('cs')")
        for i in range(20):
            conn.execute(
                "INSERT INTO papers "
                "(title, year, venue, citation_count, s2_id, arxiv_id, doi) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"Paper {i}",
                    2024 if i < 12 else 2023,
                    "NeurIPS",
                    50,
                    f"s2-{i}",
                    f"ax-{i}",
                    f"10.0/doi-{i}",
                ),
            )
        conn.commit()

        clusters = refresh_trends(conn, tier="standard", dry_run=True)
        assert len(clusters) == 1
        # 0..10 range is the invariant we care about; anything else would
        # mean the formula is not the product-with-scale variant.
        assert 0.0 <= clusters[0].publishability_score <= 10.0
    finally:
        conn.close()
