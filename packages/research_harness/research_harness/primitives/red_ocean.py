"""Per-dimension red-ocean scoring — deterministic, no LLM.

Three scopes ("dimensions") are scored independently:

- research_area (the most common lookup) — set on research_areas row
- task_canonical — computed from normalized_claims.task_canonical
- method — computed from normalized_claims.method

Each dimension score is the clipped weighted sum of four sub-metrics:

  volume_pressure       (+0.30)  more papers in the scope vs peers
  method_convergence    (+0.30)  top-3 methods concentrate papers
  lab_concentration     (+0.25)  HHI on top affiliations
  gap_density_cap       (-0.15)  verified gaps offset the red-ocean signal

Formulas:
- volume_pressure = ((tanh(log2(papers_last_2y / max(median_peer, 1))) + 1) / 2)
  clipped to [0, 1]. Log-ratio vs peer median so a scope with twice the
  volume lands at ~0.66; half the volume at ~0.34.
- method_convergence = sum(top3 method paper counts) / total method entries
  in the scope. Clamped to [0, 1].
- lab_concentration = sum((share_i)²) over top-10 affiliations.
  Herfindahl-Hirschman Index. 1 = monopoly lab, 0.1 = 10 equal labs.
- gap_density = verified_open_gaps / max(papers, 1), capped at 0.2.
  Only counts gaps with confidence ≥ 0.5 OR cross_verified=1.

Final:
  score = clip(0, 1, 0.30*vp + 0.30*mc + 0.25*lc - 0.15*gdc)

compute_area_red_ocean also persists score + breakdown JSON back to
research_areas.red_ocean_score / red_ocean_breakdown. The task/method
helpers return a RedOceanScore; callers decide where to persist.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

W_VOLUME = 0.30
W_CONVERGE = 0.30
W_LAB = 0.25
W_GAP = 0.15  # NEGATIVE contribution (subtracted)

GAP_DENSITY_CAP = 0.20

# Per-dimension threshold for "red" — aligned with how opportunity_angle
# partitions the (area, task, method) cube.
RED_THRESHOLD = 0.7


def opportunity_angle(area_red: float, task_red: float, method_red: float) -> str:
    """Deterministic classification of the (area, task, method) red-state.

    Returns one of:
    - "new_task_mature_method": task is NOT red, method is red — lots of
      established method expertise looking for a less-crowded task
    - "novel_method_known_task": task is red, method is NOT red — a busy
      task that could use a fresh algorithmic angle
    - "frontier": neither task nor method is red — greenfield worth
      pursuing (highest-value label)
    - "red_ocean": both are red — avoid unless there's a strong
      differentiation reason
    """
    task_is_red = task_red >= RED_THRESHOLD
    method_is_red = method_red >= RED_THRESHOLD
    if not task_is_red and method_is_red:
        return "new_task_mature_method"
    if task_is_red and not method_is_red:
        return "novel_method_known_task"
    if not task_is_red and not method_is_red:
        return "frontier"
    return "red_ocean"


@dataclass
class RedOceanBreakdown:
    volume_pressure: float = 0.0
    method_convergence: float = 0.0
    lab_concentration: float = 0.0
    gap_density_cap: float = 0.0
    papers: int = 0
    peer_median: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


@dataclass
class RedOceanScore:
    scope_type: str
    scope_id: str
    score: float
    breakdown: RedOceanBreakdown = field(default_factory=RedOceanBreakdown)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "score": self.score,
            "breakdown": asdict(self.breakdown),
        }


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _volume_pressure(papers_in_scope: int, peer_median: int) -> float:
    """tanh-shaped log-ratio mapped to [0, 1]."""
    if peer_median <= 0:
        return 0.0 if papers_in_scope <= 0 else 1.0
    ratio = papers_in_scope / peer_median
    if ratio <= 0:
        return 0.0
    raw = math.tanh(math.log2(ratio))  # ∈ (-1, 1)
    return _clip((raw + 1.0) / 2.0)


def _method_convergence(method_counts: Iterable[int]) -> float:
    counts = sorted((c for c in method_counts if c > 0), reverse=True)
    total = sum(counts)
    if total <= 0:
        return 0.0
    top3 = sum(counts[:3])
    return _clip(top3 / total)


def _lab_concentration(lab_shares: Iterable[float]) -> float:
    """HHI = Σ share². `lab_shares` should already be fractions summing ≤ 1."""
    shares = [s for s in lab_shares if s > 0]
    if not shares:
        return 0.0
    return _clip(sum(s * s for s in shares))


def _gap_density(verified_gaps: int, papers: int) -> float:
    if papers <= 0:
        return 0.0
    raw = verified_gaps / papers
    return min(GAP_DENSITY_CAP, raw)


def _compose(bd: RedOceanBreakdown) -> float:
    return _clip(
        W_VOLUME * bd.volume_pressure
        + W_CONVERGE * bd.method_convergence
        + W_LAB * bd.lab_concentration
        - W_GAP * bd.gap_density_cap
    )


# ---------------------------------------------------------------------------
# Evidence loaders (pure SQL — no LLM)
# ---------------------------------------------------------------------------


def _papers_in_area(conn, research_area_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT paper_id FROM paper_research_areas WHERE research_area_id = ?",
        (research_area_id,),
    ).fetchall()
    return [int(r[0]) for r in rows]


def _peer_median_for_domain(conn, research_area_id: int) -> int:
    """Median paper count across sibling research_areas in the same domain.

    Excludes the target area itself (peer means ≠ self). Uses the lower
    median for even-sized sets so outliers don't inflate the baseline.
    """
    row = conn.execute(
        "SELECT domain_id FROM research_areas WHERE id = ?", (research_area_id,)
    ).fetchone()
    if not row:
        return 0
    domain_id = row[0]
    counts = conn.execute(
        "SELECT COUNT(*) AS cnt FROM paper_research_areas pra "
        "JOIN research_areas ra ON ra.id = pra.research_area_id "
        "WHERE ra.domain_id = ? AND pra.research_area_id != ? "
        "GROUP BY pra.research_area_id",
        (domain_id, research_area_id),
    ).fetchall()
    values = sorted(int(r[0]) for r in counts if int(r[0]) > 0)
    if not values:
        return 0
    # Lower median: for [1, 3] return 1 (not 2 or 3); for [1, 2, 3] return 2.
    return values[(len(values) - 1) // 2]


def _method_counts_for_papers(conn, paper_ids: list[int]) -> list[int]:
    if not paper_ids:
        return []
    ph = ",".join("?" * len(paper_ids))
    rows = conn.execute(
        f"SELECT method, COUNT(*) FROM normalized_claims "
        f"WHERE paper_id IN ({ph}) AND method != '' "
        f"GROUP BY method",
        paper_ids,
    ).fetchall()
    return [int(r[1]) for r in rows]


def _lab_shares_for_papers(conn, paper_ids: list[int]) -> list[float]:
    if not paper_ids:
        return []
    ph = ",".join("?" * len(paper_ids))
    # affiliations is stored as JSON array per paper; use the first affiliation
    # as the "primary lab" signal. Not perfect but good enough for HHI and
    # avoids the need for a separate normalized authorship table.
    rows = conn.execute(
        f"SELECT affiliations FROM papers WHERE id IN ({ph})",
        paper_ids,
    ).fetchall()
    labs: list[str] = []
    for r in rows:
        raw = r[0] if isinstance(r, tuple) else r["affiliations"]
        try:
            affs = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            affs = []
        if affs:
            labs.append(str(affs[0]).strip().lower())
    if not labs:
        return []
    counts = Counter(labs)
    total = sum(counts.values())
    if total <= 0:
        return []
    # Top-10 only
    top = counts.most_common(10)
    return [c / total for _, c in top]


def _verified_gaps_for_papers(conn, paper_ids: list[int]) -> int:
    """Count gaps with confidence ≥ 0.5 OR cross_verified = 1 for these papers.

    Gaps are attributed to papers via gaps.paper_id when available, else via
    gaps.topic_id join. If neither column exists yet (pre-Phase-4 migrations),
    returns 0 so the formula degrades gracefully.
    """
    if not paper_ids:
        return 0
    # Inspect schema once so we can run the right query
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(gaps)").fetchall()}
    except Exception:
        return 0
    if not cols:
        return 0
    paper_clause = "1=0"
    if "paper_id" in cols:
        ph = ",".join("?" * len(paper_ids))
        paper_clause = f"paper_id IN ({ph})"
    conf_clause_parts = []
    if "confidence" in cols:
        conf_clause_parts.append("confidence >= 0.5")
    if "cross_verified" in cols:
        conf_clause_parts.append("cross_verified = 1")
    if not conf_clause_parts:
        return 0
    conf_clause = " OR ".join(conf_clause_parts)
    sql = f"SELECT COUNT(*) FROM gaps WHERE {paper_clause} AND ({conf_clause})"
    params: list[Any] = list(paper_ids) if "paper_id" in cols else []
    try:
        row = conn.execute(sql, params).fetchone()
    except Exception:
        return 0
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


COMPUTE_AREA_RED_OCEAN_SPEC = PrimitiveSpec(
    name="compute_area_red_ocean",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Compute and persist red_ocean_score + breakdown for a research_area "
        "row. Pure SQL + math; no LLM."
    ),
    input_schema={
        "type": "object",
        "properties": {"research_area_id": {"type": "integer"}},
        "required": ["research_area_id"],
    },
    output_type="RedOceanScore",
    requires_llm=False,
    idempotent=True,
)


@register_primitive(COMPUTE_AREA_RED_OCEAN_SPEC)
def compute_area_red_ocean(
    *, db: Database, research_area_id: int, **_: Any
) -> RedOceanScore:
    conn = db.connect()
    try:
        paper_ids = _papers_in_area(conn, research_area_id)
        peer_median = _peer_median_for_domain(conn, research_area_id)
        method_counts = _method_counts_for_papers(conn, paper_ids)
        lab_shares = _lab_shares_for_papers(conn, paper_ids)
        verified_gaps = _verified_gaps_for_papers(conn, paper_ids)

        bd = RedOceanBreakdown(
            volume_pressure=_volume_pressure(len(paper_ids), peer_median),
            method_convergence=_method_convergence(method_counts),
            lab_concentration=_lab_concentration(lab_shares),
            gap_density_cap=_gap_density(verified_gaps, len(paper_ids)),
            papers=len(paper_ids),
            peer_median=peer_median,
        )
        score = _compose(bd)

        conn.execute(
            "UPDATE research_areas SET red_ocean_score = ?, "
            "red_ocean_breakdown = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (score, bd.to_json(), research_area_id),
        )
        conn.commit()
    finally:
        conn.close()

    return RedOceanScore(
        scope_type="research_area",
        scope_id=str(research_area_id),
        score=score,
        breakdown=bd,
    )


COMPUTE_TASK_RED_OCEAN_SPEC = PrimitiveSpec(
    name="compute_task_red_ocean",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Compute red-ocean score for a canonical task label scoped to a domain. "
        "Does not persist — caller decides where (usually as a report row)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task_canonical": {"type": "string"},
            "domain_id": {"type": "integer"},
        },
        "required": ["task_canonical", "domain_id"],
    },
    output_type="RedOceanScore",
    requires_llm=False,
    idempotent=True,
)


@register_primitive(COMPUTE_TASK_RED_OCEAN_SPEC)
def compute_task_red_ocean(
    *, db: Database, task_canonical: str, domain_id: int, **_: Any
) -> RedOceanScore:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT nc.paper_id FROM normalized_claims nc "
            "JOIN paper_domains pd ON pd.paper_id = nc.paper_id "
            "WHERE nc.task_canonical = ? AND pd.domain_id = ?",
            (task_canonical, domain_id),
        ).fetchall()
        paper_ids = [int(r[0]) for r in rows]

        peer_counts = conn.execute(
            "SELECT COUNT(DISTINCT nc.paper_id) AS c FROM normalized_claims nc "
            "JOIN paper_domains pd ON pd.paper_id = nc.paper_id "
            "WHERE pd.domain_id = ? AND nc.task_canonical IS NOT NULL "
            "GROUP BY nc.task_canonical",
            (domain_id,),
        ).fetchall()
        values = sorted(int(r[0]) for r in peer_counts if int(r[0]) > 0)
        peer_median = values[len(values) // 2] if values else 0

        method_counts = _method_counts_for_papers(conn, paper_ids)
        lab_shares = _lab_shares_for_papers(conn, paper_ids)
        verified_gaps = _verified_gaps_for_papers(conn, paper_ids)

        bd = RedOceanBreakdown(
            volume_pressure=_volume_pressure(len(paper_ids), peer_median),
            method_convergence=_method_convergence(method_counts),
            lab_concentration=_lab_concentration(lab_shares),
            gap_density_cap=_gap_density(verified_gaps, len(paper_ids)),
            papers=len(paper_ids),
            peer_median=peer_median,
        )
        score = _compose(bd)
    finally:
        conn.close()

    return RedOceanScore(
        scope_type="task",
        scope_id=task_canonical,
        score=score,
        breakdown=bd,
    )


COMPUTE_METHOD_RED_OCEAN_SPEC = PrimitiveSpec(
    name="compute_method_red_ocean",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Compute red-ocean score for a method name scoped to a research_area. "
        "Does not persist."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "method": {"type": "string"},
            "research_area_id": {"type": "integer"},
        },
        "required": ["method", "research_area_id"],
    },
    output_type="RedOceanScore",
    requires_llm=False,
    idempotent=True,
)


@register_primitive(COMPUTE_METHOD_RED_OCEAN_SPEC)
def compute_method_red_ocean(
    *, db: Database, method: str, research_area_id: int, **_: Any
) -> RedOceanScore:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT nc.paper_id FROM normalized_claims nc "
            "JOIN paper_research_areas pra ON pra.paper_id = nc.paper_id "
            "WHERE nc.method = ? AND pra.research_area_id = ?",
            (method, research_area_id),
        ).fetchall()
        paper_ids = [int(r[0]) for r in rows]

        peer_counts = conn.execute(
            "SELECT COUNT(DISTINCT nc.paper_id) AS c FROM normalized_claims nc "
            "JOIN paper_research_areas pra ON pra.paper_id = nc.paper_id "
            "WHERE pra.research_area_id = ? AND nc.method != '' "
            "GROUP BY nc.method",
            (research_area_id,),
        ).fetchall()
        values = sorted(int(r[0]) for r in peer_counts if int(r[0]) > 0)
        peer_median = values[len(values) // 2] if values else 0

        method_counts = _method_counts_for_papers(conn, paper_ids)
        lab_shares = _lab_shares_for_papers(conn, paper_ids)
        verified_gaps = _verified_gaps_for_papers(conn, paper_ids)

        bd = RedOceanBreakdown(
            volume_pressure=_volume_pressure(len(paper_ids), peer_median),
            method_convergence=_method_convergence(method_counts),
            lab_concentration=_lab_concentration(lab_shares),
            gap_density_cap=_gap_density(verified_gaps, len(paper_ids)),
            papers=len(paper_ids),
            peer_median=peer_median,
        )
        score = _compose(bd)
    finally:
        conn.close()

    return RedOceanScore(
        scope_type="method",
        scope_id=method,
        score=score,
        breakdown=bd,
    )
