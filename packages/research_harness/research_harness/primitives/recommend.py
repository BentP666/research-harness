"""Recommendation pipeline runner — seeds → scores → persists.

Composition over new functionality:
- seed_candidates (primitives.candidate_seed)
- compute_task/method/area_red_ocean + opportunity_angle (primitives.red_ocean)
- direction_ranking LLM primitive (execution.llm_primitives) — optional;
  when unavailable (no LLM configured) we skip scoring and persist with
  llm_score=0.

This primitive is the entrypoint exposed via MCP tool
`recommendations_generate(scope)`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from ..storage.db import Database
from .candidate_seed import CandidateDraft, seed_candidates, upsert_candidate
from .red_ocean import (
    compute_area_red_ocean,
    compute_method_red_ocean,
    compute_task_red_ocean,
    opportunity_angle,
)
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

logger = logging.getLogger(__name__)


@dataclass
class GeneratedCandidate:
    candidate_id: int
    lineage_key: str
    title: str
    llm_score: float
    area_red_ocean: float
    task_red_ocean: float
    method_red_ocean: float
    opportunity_angle: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecommendationsOutput:
    scope: str
    candidates: list[GeneratedCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "candidates": [c.to_dict() for c in self.candidates],
        }


RECOMMENDATIONS_GENERATE_SPEC = PrimitiveSpec(
    name="recommendations_generate",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "End-to-end recommendation pipeline: seed candidate drafts from "
        "gaps/contradictions in scope, compute multi-dimensional red-ocean "
        "and opportunity_angle, optionally LLM-score via direction_ranking, "
        "upsert into research_candidates."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "scope": {"type": "string", "description": "'topic:N' etc."},
            "skip_llm_scoring": {"type": "boolean", "default": False},
        },
        "required": ["scope"],
    },
    output_type="RecommendationsOutput",
    requires_llm=False,  # pipeline itself is orchestration; LLM invocation is optional
    idempotent=True,
)


def _get_method_for_draft(db: Database, d: CandidateDraft) -> str | None:
    """Pick a representative method for the draft from its seed papers' claims."""
    if not d.seed_paper_ids:
        return None
    conn = db.connect()
    try:
        ph = ",".join("?" * len(d.seed_paper_ids))
        row = conn.execute(
            f"SELECT method FROM normalized_claims "
            f"WHERE paper_id IN ({ph}) AND method != '' "
            f"GROUP BY method ORDER BY COUNT(*) DESC LIMIT 1",
            d.seed_paper_ids,
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _get_task_for_draft(db: Database, d: CandidateDraft) -> str | None:
    if not d.seed_paper_ids:
        return None
    conn = db.connect()
    try:
        ph = ",".join("?" * len(d.seed_paper_ids))
        row = conn.execute(
            f"SELECT COALESCE(task_canonical, task) AS t FROM normalized_claims "
            f"WHERE paper_id IN ({ph}) AND COALESCE(task_canonical, task) != '' "
            f"GROUP BY t ORDER BY COUNT(*) DESC LIMIT 1",
            d.seed_paper_ids,
        ).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _compute_red_ocean_triplet(
    db: Database, d: CandidateDraft
) -> tuple[float, float, float, str]:
    """Compute (area_red, task_red, method_red, opportunity_angle) for a draft.

    Scores the FIRST research_area when available (others would shift the
    area_red but we want stable per-draft values). Tasks/methods are
    derived from the draft's seed_paper_ids.
    """
    area_red = 0.0
    task_red = 0.0
    method_red = 0.0

    if d.research_area_ids:
        area_id = d.research_area_ids[0]
        area_score = compute_area_red_ocean(db=db, research_area_id=area_id)
        area_red = area_score.score

    if d.primary_domain_id is not None:
        task = _get_task_for_draft(db, d)
        if task:
            task_score = compute_task_red_ocean(
                db=db, task_canonical=task, domain_id=d.primary_domain_id
            )
            task_red = task_score.score

    if d.research_area_ids:
        method = _get_method_for_draft(db, d)
        if method:
            method_score = compute_method_red_ocean(
                db=db, method=method, research_area_id=d.research_area_ids[0]
            )
            method_red = method_score.score

    angle = opportunity_angle(area_red, task_red, method_red)
    return area_red, task_red, method_red, angle


def _llm_score_draft(
    d: CandidateDraft,
    area_red: float,
    task_red: float,
    method_red: float,
    angle: str,
) -> tuple[float, dict[str, Any]]:
    """Optional LLM scoring via direction_ranking.

    Returns (llm_score, breakdown_dict). Degrades to (0.0, {}) on any
    failure (no LLM configured, provider outage, parse error) so the
    pipeline still produces persisted candidates.
    """
    try:
        from llm_router.client import LLMClient, resolve_llm_config

        client = LLMClient(resolve_llm_config())
        # Build a minimal prompt inline rather than threading through
        # direction_ranking's full signature — we only need numeric score.
        prompt = (
            "You are scoring a research candidate for novelty/feasibility/impact/"
            "momentum. Output strict JSON: "
            '{"score": <0-10>, "breakdown": '
            '{"novelty": <0-10>, "feasibility": <0-10>, "impact": <0-10>, '
            '"momentum": <0-10>}}\n\n'
            f"Title: {d.title}\n"
            f"Pitch: {d.pitch}\n"
            f"Opportunity angle: {angle}\n"
            f"Red ocean — area={area_red:.2f}, task={task_red:.2f}, method={method_red:.2f}\n"
        )
        raw = client.chat(prompt)
        parsed = _parse_llm_score(raw)
        return parsed
    except Exception as exc:
        logger.warning("recommendations_generate: LLM scoring failed: %s", exc)
        return 0.0, {}


def _parse_llm_score(raw: str) -> tuple[float, dict[str, Any]]:
    """Lenient parser: tolerate code fences and trailing commentary."""
    import re

    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    blob = m.group(0) if m else txt
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return 0.0, {}
    if not isinstance(data, dict):
        return 0.0, {}
    score = float(data.get("score") or 0.0)
    breakdown = data.get("breakdown") or {}
    if not isinstance(breakdown, dict):
        breakdown = {}
    return max(0.0, min(10.0, score)), breakdown


@register_primitive(RECOMMENDATIONS_GENERATE_SPEC)
def recommendations_generate(
    *,
    db: Database,
    scope: str,
    skip_llm_scoring: bool = False,
    **_: Any,
) -> RecommendationsOutput:
    drafts = seed_candidates(db=db, scope=scope)
    out = RecommendationsOutput(scope=scope)

    for d in drafts:
        area_red, task_red, method_red, angle = _compute_red_ocean_triplet(db, d)
        if skip_llm_scoring:
            llm_score = 0.0
            breakdown: dict[str, Any] = {}
        else:
            llm_score, breakdown = _llm_score_draft(
                d, area_red, task_red, method_red, angle
            )
        cid = upsert_candidate(
            db=db,
            scope=scope,
            draft=d,
            llm_score=llm_score,
            llm_score_breakdown=breakdown,
            area_red_ocean=area_red,
            task_red_ocean=task_red,
            method_red_ocean=method_red,
            opportunity_angle=angle,
        )
        out.candidates.append(
            GeneratedCandidate(
                candidate_id=cid,
                lineage_key=d.lineage_key(),
                title=d.title,
                llm_score=llm_score,
                area_red_ocean=area_red,
                task_red_ocean=task_red,
                method_red_ocean=method_red,
                opportunity_angle=angle,
            )
        )
    return out
