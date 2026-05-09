"""Goal Pool primitive — proposes research goals from field_brief + intake_profile,
scores them with a pure deterministic function, and persists to DB.

Scoring is NOT LLM-based — it uses weighted factors derived from field_brief and
intake_profile data. LLM is only used to propose candidate goals.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class GoalCandidate(BaseModel):
    dataset: str
    baseline: str
    metric_name: str
    baseline_metric: float
    target_metric_delta: float
    target_venue: str | None = None
    time_window_days: int | None = None


class ScoringBreakdown(BaseModel):
    headroom: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    venue_fit: float = Field(ge=0, le=1)
    compute_fit: float = Field(ge=0, le=1)


class Goal(BaseModel):
    id: int | None = None
    dataset: str
    baseline: str
    metric_name: str
    baseline_metric: float
    target_metric_delta: float
    target_venue: str | None = None
    time_window_days: int | None = None
    score: float
    scoring_breakdown: ScoringBreakdown
    status: str = "active"
    priority_rank: int = 0


# ---------------------------------------------------------------------------
# Transient retry (same as field_brief_impl)
# ---------------------------------------------------------------------------

_TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)


def _call_with_transient_retry(chat_fn, prompt: str, *, retries: int = 1) -> str:
    last_err: BaseException | None = None
    for attempt in range(1 + retries):
        try:
            return chat_fn(prompt)
        except _TRANSIENT_ERRORS as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
        except Exception as exc:
            err_str = str(exc).lower()
            if any(
                k in err_str for k in ("timeout", "connection", "502", "503", "504")
            ):
                last_err = exc
                if attempt < retries:
                    time.sleep(2 ** (attempt + 1))
                    continue
            raise
    raise RuntimeError(
        f"LLM call failed after {1 + retries} attempts: {last_err}"
    ) from last_err


# ---------------------------------------------------------------------------
# Pure scoring function (NO LLM)
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "headroom": 0.35,
    "feasibility": 0.25,
    "evidence_coverage": 0.20,
    "venue_fit": 0.10,
    "compute_fit": 0.10,
}

_COMPUTE_RANK = {"cpu_only": 0, "single_gpu": 1, "multi_gpu": 2, "cluster": 3}
_GPU_RANK = {"cpu": 0, "low": 1, "medium": 2, "high": 3}


def score_goal(
    candidate: dict[str, Any],
    field_brief: dict[str, Any],
    intake: dict[str, Any],
) -> tuple[float, ScoringBreakdown]:
    """Pure deterministic scoring. Returns (score, breakdown)."""

    baseline_metric = candidate.get("baseline_metric") or 1.0
    delta = abs(candidate.get("target_metric_delta") or 0)
    headroom = min(delta / max(abs(baseline_metric), 1e-6), 1.0)

    challenges = field_brief.get("open_challenges") or []
    saturated_count = sum(1 for c in challenges if c.get("maturity") == "saturated")
    total_challenges = max(len(challenges), 1)
    feasibility = 1.0 - (saturated_count / total_challenges) * 0.7

    baselines_in_brief = field_brief.get("baselines") or []
    candidate_baseline = candidate.get("baseline", "").lower()
    matching = sum(
        1
        for b in baselines_in_brief
        if candidate_baseline in (b.get("name") or "").lower()
        or (b.get("name") or "").lower() in candidate_baseline
    )
    evidence_coverage = min(matching / max(len(baselines_in_brief), 1), 1.0)
    evidence_coverage = max(evidence_coverage, 0.3)

    venue_options = field_brief.get("venue_options") or []
    venue_names = [v.get("name", "").lower() for v in venue_options]
    target_venue = (candidate.get("target_venue") or "").lower()
    venue_fit = (
        1.0 if target_venue and any(target_venue in v for v in venue_names) else 0.3
    )

    compute_budget = intake.get("compute_budget", "cpu_only")
    budget_rank = _COMPUTE_RANK.get(compute_budget, 0)
    datasets_in_brief = field_brief.get("datasets") or []
    candidate_dataset = candidate.get("dataset", "").lower()
    gpu_needed = 0
    for ds in datasets_in_brief:
        if candidate_dataset in (ds.get("name") or "").lower():
            gpu_needed = _GPU_RANK.get(ds.get("gpu_req", "cpu"), 0)
            break
    compute_fit = 1.0 if budget_rank >= gpu_needed else 0.0

    breakdown = ScoringBreakdown(
        headroom=round(headroom, 4),
        feasibility=round(feasibility, 4),
        evidence_coverage=round(evidence_coverage, 4),
        venue_fit=round(venue_fit, 4),
        compute_fit=round(compute_fit, 4),
    )

    score = sum(_WEIGHTS[k] * getattr(breakdown, k) for k in _WEIGHTS)

    return round(score, 4), breakdown


# ---------------------------------------------------------------------------
# LLM candidate proposal
# ---------------------------------------------------------------------------

_PROPOSE_PROMPT = """\
You are a research goal planner. Given a Field Brief and researcher constraints,
propose {n} concrete research goals. Each goal targets improving a specific
baseline on a specific dataset.

Return ONLY valid JSON — a list of objects:
[
  {{
    "dataset": str,
    "baseline": str,
    "metric_name": str,
    "baseline_metric": float,
    "target_metric_delta": float,
    "target_venue": str or null,
    "time_window_days": int or null
  }}
]

Rules:
- target_metric_delta is the improvement you think is achievable (positive = better)
- Pick datasets and baselines from the field brief when possible
- Consider the researcher's compute budget and deadline
- Be realistic — don't propose goals that require cluster compute for a CPU-only researcher

Field Brief:
{field_brief}

Researcher Constraints:
- Compute: {compute_budget}
- Deadline: {deadline_days} days
- Venue preference: {venue}
"""


def _llm_propose_candidates(
    field_brief: dict[str, Any],
    intake: dict[str, Any],
    n: int = 10,
    db: Any = None,
) -> list[dict[str, Any]]:
    prompt = _PROPOSE_PROMPT.format(
        n=n,
        field_brief=json.dumps(field_brief, indent=2, ensure_ascii=False)[:3000],
        compute_budget=intake.get("compute_budget", "unknown"),
        deadline_days=intake.get("time_to_deadline_days", "unknown"),
        venue=intake.get("target_venue") or "open",
    )

    from research_harness.execution.llm_primitives import _get_client, _client_chat

    client = _get_client(None, tier="light", task_name="goal_propose")
    raw = _call_with_transient_retry(lambda p: _client_chat(client, p), prompt)

    from research_harness.execution.llm_primitives import _parse_json

    parsed = _parse_json(raw, primitive="goal_propose")

    if isinstance(parsed, dict) and "goals" in parsed:
        candidates = parsed["goals"]
    elif isinstance(parsed, list):
        candidates = parsed
    elif isinstance(parsed, dict):
        candidates = [parsed]
    else:
        raise RuntimeError(
            f"LLM returned unexpected format for goal candidates: {type(parsed)}"
        )

    validated = []
    for c in candidates:
        try:
            gc = GoalCandidate.model_validate(c)
            validated.append(gc.model_dump())
        except ValidationError:
            logger.warning("Skipping invalid goal candidate: %s", c)
            continue

    if not validated:
        raise RuntimeError("LLM returned 0 valid goal candidates")

    return validated


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def build_goal_pool(
    topic_id: int,
    db: Any,
    max_goals: int = 5,
) -> list[Goal]:
    """Build a scored goal pool for a topic.

    Requires: field_brief + intake_profile already exist.
    """
    from research_harness.primitives.field_brief_impl import get_latest_field_brief

    fb_result = get_latest_field_brief(topic_id, db)
    if fb_result is None:
        raise RuntimeError(
            "Field brief not found for this topic. Generate a field brief first."
        )
    field_brief = fb_result["brief"]

    conn = db.connect()
    try:
        intake_row = conn.execute(
            "SELECT * FROM topic_intake_profile WHERE topic_id = ?",
            (topic_id,),
        ).fetchone()
    finally:
        conn.close()

    if not intake_row:
        raise RuntimeError(
            "Intake profile not found for this topic. Complete the onboarding wizard first."
        )
    intake = dict(intake_row)

    raw_candidates = _llm_propose_candidates(field_brief, intake, n=10, db=db)

    scored: list[tuple[float, ScoringBreakdown, dict[str, Any]]] = []
    for c in raw_candidates:
        s, breakdown = score_goal(c, field_brief, intake)
        if breakdown.evidence_coverage >= 0.3 and breakdown.compute_fit >= 0.5:
            scored.append((s, breakdown, c))

    scored.sort(key=lambda x: -x[0])
    top = scored[:max_goals]

    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM goal_pool WHERE topic_id = ?", (topic_id,))
        goals: list[Goal] = []
        for rank, (s, breakdown, c) in enumerate(top, 1):
            cur = conn.execute(
                """INSERT INTO goal_pool
                   (topic_id, dataset, baseline, metric_name, baseline_metric,
                    target_metric_delta, target_venue, time_window_days,
                    score, scoring_breakdown, status, priority_rank)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
                (
                    topic_id,
                    c["dataset"],
                    c["baseline"],
                    c["metric_name"],
                    c["baseline_metric"],
                    c["target_metric_delta"],
                    c.get("target_venue"),
                    c.get("time_window_days"),
                    s,
                    breakdown.model_dump_json(),
                    rank,
                ),
            )
            goals.append(
                Goal(
                    id=cur.lastrowid,
                    dataset=c["dataset"],
                    baseline=c["baseline"],
                    metric_name=c["metric_name"],
                    baseline_metric=c["baseline_metric"],
                    target_metric_delta=c["target_metric_delta"],
                    target_venue=c.get("target_venue"),
                    time_window_days=c.get("time_window_days"),
                    score=s,
                    scoring_breakdown=breakdown,
                    status="active",
                    priority_rank=rank,
                )
            )
        conn.commit()
    finally:
        conn.close()

    from research_harness.orchestrator import OrchestratorService

    svc = OrchestratorService(db)
    svc.record_artifact(
        topic_id=topic_id,
        stage="analyze",
        artifact_type="goal_pool",
        title="Goal Pool",
        payload={"goals": [g.model_dump() for g in goals]},
    )

    return goals
