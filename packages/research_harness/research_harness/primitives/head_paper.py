"""Deterministic head-paper ranking — no LLM.

Score = citation_term × venue_quality × recency_decay

- current_year papers: citation_term = venue_quality
  (no citation history yet — venue is our best prior).
- else: citation_term = log(1 + cites) / log(1 + median_year_cites)
  (normalizes against the median for that year so 100 cites in 2016 and
   100 cites in 2024 are not treated identically).
- recency: exp(-(current_year - year) / 3.0)
  (a paper loses ~1/e of its ranking weight every 3 years).

Used by cs_harvest to trim a broad yearly harvest down to the top-N
"head" papers worth deep processing. Also useful anywhere a deterministic
quality proxy is preferred over LLM judgment.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

# CCF rank → weight. Values below carry the official CCF tiers plus a
# few common aliases (A*, A-STAR) so we're resilient to source formatting.
CCF_RANK_SCORE: dict[str, float] = {
    "A*": 1.0,
    "A+": 1.0,
    "A-STAR": 1.0,
    "CCF_A_STAR": 1.0,
    "A": 0.8,
    "CCF_A": 0.8,
    "B": 0.5,
    "CCF_B": 0.5,
    "C": 0.3,
    "CCF_C": 0.3,
}
UNRANKED_PRIOR = 0.4


@dataclass
class RankedPaper:
    paper_id: int
    score: float
    citation_term: float
    venue_q: float
    recency: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeadPaperRankOutput:
    ranked: list[RankedPaper]

    def to_dict(self) -> dict[str, Any]:
        return {"ranked": [r.to_dict() for r in self.ranked]}


HEAD_PAPER_RANK_SPEC = PrimitiveSpec(
    name="head_paper_rank",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Rank papers deterministically by citation × venue × recency. "
        "No LLM. Used to trim broad harvests to a publishable 'head' set."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "year": {"type": "integer"},
            "paper_ids": {"type": "array", "items": {"type": "integer"}},
            "current_year": {"type": "integer"},
            "target": {
                "type": "integer",
                "description": "Optional — trim output to top N.",
            },
        },
        "required": ["year", "paper_ids"],
    },
    output_type="HeadPaperRankOutput",
    requires_llm=False,
    idempotent=True,
)


def _venue_quality(conn: Any, venue_name: str) -> float:
    if not venue_name:
        return UNRANKED_PRIOR
    row = conn.execute(
        "SELECT ccf_rank, impact_factor FROM venue_ranks "
        "WHERE lower(canonical_name) = lower(?) LIMIT 1",
        (venue_name,),
    ).fetchone()
    if not row:
        return UNRANKED_PRIOR
    rank = (
        (row["ccf_rank"] or "").upper().strip()
        if hasattr(row, "keys")
        else ((row[0] or "").upper().strip())
    )
    if rank in CCF_RANK_SCORE:
        return CCF_RANK_SCORE[rank]
    impact = row["impact_factor"] if hasattr(row, "keys") else row[1]
    if impact is not None:
        return _if_percentile(conn, float(impact))
    return UNRANKED_PRIOR


def _if_percentile(conn: Any, value: float) -> float:
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN impact_factor <= ? THEN 1 ELSE 0 END) AS below "
        "FROM venue_ranks WHERE impact_factor IS NOT NULL",
        (value,),
    ).fetchone()
    if not row:
        return UNRANKED_PRIOR
    total = row["total"] if hasattr(row, "keys") else row[0]
    below = row["below"] if hasattr(row, "keys") else row[1]
    if not total:
        return UNRANKED_PRIOR
    return float(below) / float(total)


def _median_citations_for_year(conn: Any, year: int) -> float:
    """Median nonzero citation_count for `year`. Returns 1.0 if unavailable
    (so the normalizer degrades to log1p(cites))."""
    row = conn.execute(
        "SELECT citation_count FROM papers "
        "WHERE year = ? AND citation_count IS NOT NULL AND citation_count > 0 "
        "ORDER BY citation_count "
        "LIMIT 1 OFFSET ("
        "  SELECT COUNT(*) / 2 FROM papers "
        "  WHERE year = ? AND citation_count IS NOT NULL AND citation_count > 0"
        ")",
        (year, year),
    ).fetchone()
    if not row:
        return 1.0
    val = row["citation_count"] if hasattr(row, "keys") else row[0]
    return float(val or 1.0)


@register_primitive(HEAD_PAPER_RANK_SPEC)
def head_paper_rank(
    *,
    db: Database,
    year: int,
    paper_ids: list[int],
    current_year: int | None = None,
    target: int | None = None,
    **_: Any,
) -> HeadPaperRankOutput:
    if not paper_ids:
        return HeadPaperRankOutput(ranked=[])
    if current_year is None:
        from datetime import datetime, timezone

        current_year = datetime.now(timezone.utc).year

    conn = db.connect()
    conn.row_factory = _row_factory()
    try:
        placeholders = ",".join("?" * len(paper_ids))
        rows = conn.execute(
            f"SELECT id, year, venue, citation_count FROM papers "
            f"WHERE id IN ({placeholders})",
            list(paper_ids),
        ).fetchall()

        median_cites = _median_citations_for_year(conn, year)
        log_denom = math.log1p(median_cites) or 1.0

        ranked: list[RankedPaper] = []
        for r in rows:
            paper_year = r["year"] or current_year
            venue_q = _venue_quality(conn, r["venue"] or "")
            if paper_year == current_year:
                citation_term = venue_q
            else:
                citation_term = math.log1p(r["citation_count"] or 0) / log_denom
            recency = math.exp(-(current_year - paper_year) / 3.0)
            ranked.append(
                RankedPaper(
                    paper_id=int(r["id"]),
                    score=citation_term * venue_q * recency,
                    citation_term=citation_term,
                    venue_q=venue_q,
                    recency=recency,
                )
            )
    finally:
        conn.close()

    ranked.sort(key=lambda x: x.score, reverse=True)
    if target is not None:
        ranked = ranked[:target]
    return HeadPaperRankOutput(ranked=ranked)


def _row_factory():
    """sqlite3.Row-style row factory so we can access columns by name."""
    import sqlite3

    return sqlite3.Row
