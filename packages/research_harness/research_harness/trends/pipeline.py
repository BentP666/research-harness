"""Trends pipeline — cluster papers, compute features, score publishability.

Scope model (Phase C)
---------------------
Every trend cluster belongs to one ``scope`` string:

  - ``discipline:cs``   — everything in the paper pool
  - ``domain:<id>``     — papers linked to any topic in that domain
  - ``topic:<id>``      — papers linked to that topic

Scopes are stored as a single text column; the filter is applied to both the
SELECT and the DELETE/INSERT so refreshes don't nuke unrelated scopes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = "discipline:cs"


@dataclass
class TrendCluster:
    name: str
    description: str
    velocity_yoy: float
    citation_median: float
    top_venues: list[str]
    publishability_score: float
    why: str
    seed_papers: list[dict[str, Any]]
    # Number of papers in the cluster — coverage chip on the UI.
    paper_count: int = 0


def compute_publishability(
    velocity: float,
    citation_median: float,
    venue_quality: float,
    eps: float = 0.1,
) -> float:
    """Weighted product with ε-floor per spec §15 Q7.

    Inputs are expected in 0..1 range (normalized velocity / citation_median /
    venue_quality). Returns a 0..10 score so it aligns with the editorial seed
    values in ``data/domain_trends_seed.json``.

    Product semantics matter here: if any factor is near zero the whole score
    drags to zero — that is the gate we want. A weighted sum would let one
    strong factor paper over a dead one (e.g. hot velocity in a venue nobody
    reads), which defeats the purpose of the score.
    """
    v = max(velocity, eps)
    c = max(citation_median, eps)
    q = max(venue_quality, eps)
    return round(v * c * q * 10.0, 2)


def _scope_where(scope: str) -> tuple[str, list[Any]]:
    """Return (SQL fragment, params) for filtering `papers p` by scope.

    Caller is responsible for the leading WHERE/AND glue.
    """
    if scope.startswith("domain:"):
        try:
            did = int(scope.split(":", 1)[1])
        except (ValueError, IndexError):
            raise ValueError(f"malformed scope: {scope!r}")
        return (
            "p.id IN (SELECT pt.paper_id FROM paper_topics pt "
            "JOIN topics t ON t.id = pt.topic_id WHERE t.domain_id = ?)",
            [did],
        )
    if scope.startswith("topic:"):
        try:
            tid = int(scope.split(":", 1)[1])
        except (ValueError, IndexError):
            raise ValueError(f"malformed scope: {scope!r}")
        return (
            "p.id IN (SELECT pt.paper_id FROM paper_topics pt WHERE pt.topic_id = ?)",
            [tid],
        )
    # discipline:<name> — no filter today (v1 is CS-only); keep the scope
    # string so we can add real discipline tags later.
    return ("", [])


def refresh_trends(
    conn: sqlite3.Connection,
    tier: str = "standard",
    scope: str = DEFAULT_SCOPE,
    dry_run: bool = False,
) -> list[TrendCluster]:
    """Run the trends pipeline for a single scope.

    In stub mode (no sentence-transformers), generates a single "Research
    Landscape Overview" cluster from the paper distribution inside the scope.
    Real semantic clustering is deferred to v0.4.
    """
    where, params = _scope_where(scope)
    base_sql = "SELECT p.id, p.title, p.year, p.venue, p.citation_count FROM papers p"
    sql = f"{base_sql} WHERE {where}" if where else base_sql
    sql += " ORDER BY p.year DESC LIMIT 5000"

    papers = conn.execute(sql, params).fetchall()

    if not papers:
        return _seed_trends(conn, tier, scope, dry_run)

    venue_counts: dict[str, int] = {}
    year_counts: dict[int, int] = {}
    for p in papers:
        venue = p["venue"] or "unknown"
        venue_counts[venue] = venue_counts.get(venue, 0) + 1
        year = p["year"] or 2024
        year_counts[year] = year_counts.get(year, 0) + 1

    top_venues = sorted(venue_counts, key=venue_counts.get, reverse=True)[:5]  # type: ignore[arg-type]

    max_year = max(year_counts) if year_counts else 2024
    prev_year = max_year - 1
    current = year_counts.get(max_year, 0)
    previous = year_counts.get(prev_year, 1)
    velocity = round((current - previous) / max(previous, 1) * 100, 1)

    citations = [p["citation_count"] or 0 for p in papers if p["citation_count"]]
    citation_med = sorted(citations)[len(citations) // 2] if citations else 0.0

    cluster = TrendCluster(
        name=f"{_scope_label(scope)} — Landscape Overview",
        description=f"{len(papers)} papers across {len(venue_counts)} venues",
        velocity_yoy=velocity,
        citation_median=float(citation_med),
        top_venues=top_venues,
        publishability_score=compute_publishability(
            abs(velocity) / 100, citation_med / 100, len(top_venues) / 5
        ),
        why=f"Derived from the {len(papers)}-paper pool for {scope}",
        seed_papers=[
            {"id": p["id"], "title": p["title"], "year": p["year"]} for p in papers[:10]
        ],
        paper_count=len(papers),
    )

    clusters = [cluster]

    if not dry_run:
        _write_trends(conn, clusters, tier, scope)

    return clusters


def _scope_label(scope: str) -> str:
    if scope.startswith("discipline:"):
        return scope.split(":", 1)[1].upper()
    if scope.startswith("domain:"):
        return f"Domain #{scope.split(':', 1)[1]}"
    if scope.startswith("topic:"):
        return f"Topic #{scope.split(':', 1)[1]}"
    return scope


def _seed_trends(
    conn: sqlite3.Connection,
    tier: str,
    scope: str,
    dry_run: bool,
) -> list[TrendCluster]:
    """Generate trends from bundled seed data when no papers exist in the scope.
    The seed set is discipline-level editorial content; we label every entry
    with the current scope so the fallback is still scoped end-to-end.
    """
    from pathlib import Path

    seed_path = Path(__file__).parent.parent / "data" / "domain_trends_seed.json"
    if not seed_path.exists():
        return []

    with open(seed_path, encoding="utf-8") as f:
        seed_data = json.load(f)

    clusters = []
    for entry in seed_data:
        seed_papers = entry.get("seed_papers", [])
        clusters.append(
            TrendCluster(
                name=entry["name"],
                description=entry["description"],
                velocity_yoy=entry.get("velocity_yoy", 0),
                citation_median=entry.get("citation_median", 0),
                top_venues=entry.get("top_venues", []),
                publishability_score=entry.get("publishability_score", 0),
                why=entry.get("why", ""),
                seed_papers=seed_papers,
                paper_count=len(seed_papers),
            )
        )

    if not dry_run:
        _write_trends(conn, clusters, tier, scope)

    return clusters


def _write_trends(
    conn: sqlite3.Connection,
    clusters: list[TrendCluster],
    tier: str,
    scope: str,
) -> None:
    """Delete AND insert by (tier, scope) — a refresh for one scope must NOT
    wipe other scopes' rows."""
    conn.execute(
        "DELETE FROM domain_trends WHERE tier = ? AND scope = ?",
        (tier, scope),
    )
    for c in clusters:
        conn.execute(
            """
            INSERT INTO domain_trends (name, description, velocity_yoy, citation_median,
                top_venues, publishability_score, why, seed_papers, tier, scope)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c.name,
                c.description,
                c.velocity_yoy,
                c.citation_median,
                json.dumps(c.top_venues),
                c.publishability_score,
                c.why,
                json.dumps(c.seed_papers),
                tier,
                scope,
            ),
        )
    conn.commit()


def yearly_counts(
    conn: sqlite3.Connection,
    scope: str = DEFAULT_SCOPE,
    years: int = 5,
) -> list[dict[str, Any]]:
    """Aggregate yearly facts for the given scope — used by sparklines and
    the cluster-detail line chart.

    Returns rows of shape ``{year, paper_count, median_citations,
    top_venue_count}`` for the most recent ``years`` complete years.
    """
    where, params = _scope_where(scope)
    year_filter = "p.year IS NOT NULL"
    conditions = [year_filter]
    if where:
        conditions.append(where)
    where_sql = " AND ".join(conditions)

    # Pull raw paper-year rows; aggregate in Python to compute median
    # (SQLite has no native median function).
    sql = (
        "SELECT p.year AS year, p.venue AS venue, p.citation_count AS citation_count "
        f"FROM papers p WHERE {where_sql}"
    )
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return []

    years_present = sorted({r["year"] for r in rows if r["year"] is not None})
    keep = years_present[-years:] if years > 0 else years_present

    out: list[dict[str, Any]] = []
    for y in keep:
        y_rows = [r for r in rows if r["year"] == y]
        cites = sorted(
            r["citation_count"] or 0 for r in y_rows if r["citation_count"] is not None
        )
        median = 0.0
        if cites:
            mid = len(cites) // 2
            median = float(
                cites[mid] if len(cites) % 2 else (cites[mid - 1] + cites[mid]) / 2
            )
        venue_set = {r["venue"] for r in y_rows if r["venue"]}
        out.append(
            {
                "year": y,
                "paper_count": len(y_rows),
                "median_citations": round(median, 2),
                "top_venue_count": len(venue_set),
            }
        )
    return out
