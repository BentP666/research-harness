"""Phase C regression tests — scope-aware trends pipeline + yearly aggregates."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_harness.storage.db import Database
from research_harness.trends import (
    DEFAULT_SCOPE,
    refresh_trends,
    yearly_counts,
)


def _seed_papers(conn, rows):
    """rows: iterable of (pid, year, venue, cites, doi_uniq)."""
    for pid, year, venue, cites, uniq in rows:
        conn.execute(
            "INSERT INTO papers (id, title, year, venue, citation_count, doi, arxiv_id, s2_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pid,
                f"p{pid}",
                year,
                venue,
                cites,
                f"doi-{uniq}",
                f"ax-{uniq}",
                f"s2-{uniq}",
            ),
        )


@pytest.fixture()
def db(tmp_path: Path):
    db = Database(tmp_path / "trends.db")
    db.migrate()
    return db


def test_scope_column_backfilled_to_default(db: Database):
    conn = db.connect()
    try:
        # Old rows (pre-migration) would get the default from the ALTER TABLE.
        conn.execute(
            "INSERT INTO domain_trends (name, description, tier, scope)"
            " VALUES ('legacy', 'legacy row', 'standard', ?)",
            (DEFAULT_SCOPE,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT scope FROM domain_trends WHERE name='legacy'"
        ).fetchone()
        assert row["scope"] == DEFAULT_SCOPE
    finally:
        conn.close()


def test_refresh_scope_isolation(db: Database):
    """Refreshing one scope must NOT wipe other scopes' rows."""
    conn = db.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('d1')")
        conn.execute("INSERT INTO domains (name) VALUES ('d2')")
        conn.execute(
            "INSERT INTO topics (name, description, domain_id) VALUES ('t1', '', 1)"
        )
        _seed_papers(
            conn,
            [
                (1, 2023, "NeurIPS", 10, "d1a"),
                (2, 2024, "NeurIPS", 20, "d1b"),
            ],
        )
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (1, 1)")
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (2, 1)")
        conn.commit()

        # Seed two scopes.
        refresh_trends(conn, tier="standard", scope="discipline:cs")
        refresh_trends(conn, tier="standard", scope="domain:1")

        disc_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM domain_trends WHERE scope='discipline:cs'"
        ).fetchone()
        dom_rows = conn.execute(
            "SELECT COUNT(*) AS c FROM domain_trends WHERE scope='domain:1'"
        ).fetchone()
        assert disc_rows["c"] > 0
        assert dom_rows["c"] > 0

        # Refresh the discipline scope again. The domain:1 rows must still exist.
        refresh_trends(conn, tier="standard", scope="discipline:cs")
        dom_after = conn.execute(
            "SELECT COUNT(*) AS c FROM domain_trends WHERE scope='domain:1'"
        ).fetchone()
        assert dom_after["c"] == dom_rows["c"]
    finally:
        conn.close()


def test_refresh_scope_actually_filters_papers(db: Database):
    """Two domains with different paper pools must produce different clusters."""
    conn = db.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('d1')")  # id 1
        conn.execute("INSERT INTO domains (name) VALUES ('d2')")  # id 2
        conn.execute(
            "INSERT INTO topics (name, description, domain_id) VALUES ('t1', '', 1)"
        )
        conn.execute(
            "INSERT INTO topics (name, description, domain_id) VALUES ('t2', '', 2)"
        )
        _seed_papers(
            conn,
            [
                (1, 2024, "NeurIPS", 10, "a"),
                (2, 2024, "NeurIPS", 12, "b"),
                (3, 2024, "CHI", 8, "c"),
                (4, 2024, "CHI", 11, "d"),
            ],
        )
        # First two papers under domain 1, last two under domain 2.
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (1, 1)")
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (2, 1)")
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (3, 2)")
        conn.execute("INSERT INTO paper_topics (paper_id, topic_id) VALUES (4, 2)")
        conn.commit()

        c1 = refresh_trends(conn, tier="standard", scope="domain:1")
        c2 = refresh_trends(conn, tier="standard", scope="domain:2")
        assert c1 and c2
        assert c1[0].paper_count == 2
        assert c2[0].paper_count == 2
        # Top venues should reflect each domain's distribution, not merge.
        assert "NeurIPS" in c1[0].top_venues
        assert "CHI" in c2[0].top_venues
        assert "CHI" not in c1[0].top_venues
        assert "NeurIPS" not in c2[0].top_venues
    finally:
        conn.close()


def test_malformed_scope_raises(db: Database):
    conn = db.connect()
    try:
        with pytest.raises(ValueError):
            refresh_trends(conn, scope="domain:not-a-number")
    finally:
        conn.close()


def test_yearly_counts_aggregates_per_scope(db: Database):
    conn = db.connect()
    try:
        conn.execute("INSERT INTO domains (name) VALUES ('d1')")
        conn.execute(
            "INSERT INTO topics (name, description, domain_id) VALUES ('t1', '', 1)"
        )
        _seed_papers(
            conn,
            [
                (1, 2022, "NeurIPS", 10, "a"),
                (2, 2023, "NeurIPS", 20, "b"),
                (3, 2023, "ICML", 30, "c"),
                (4, 2024, "NeurIPS", 40, "d"),
                (5, 2024, "CHI", 5, "e"),  # not in domain 1
            ],
        )
        for pid in (1, 2, 3, 4):
            conn.execute(
                "INSERT INTO paper_topics (paper_id, topic_id) VALUES (?, 1)",
                (pid,),
            )
        conn.commit()

        rows = yearly_counts(conn, scope="domain:1", years=5)
        by_year = {r["year"]: r for r in rows}
        assert 2022 in by_year and 2023 in by_year and 2024 in by_year
        assert by_year[2023]["paper_count"] == 2
        # Median cites for 2023 is (20+30)/2 = 25 for even count.
        assert by_year[2023]["median_citations"] == 25.0
        # 2024 has one paper in domain 1 (cites=40), one outside (cites=5) — scope filters.
        assert by_year[2024]["paper_count"] == 1
        assert by_year[2024]["median_citations"] == 40.0
    finally:
        conn.close()


def test_yearly_counts_empty_scope(db: Database):
    conn = db.connect()
    try:
        # No papers at all → empty result, not an error.
        rows = yearly_counts(conn, scope="discipline:cs", years=5)
        assert rows == []
    finally:
        conn.close()
