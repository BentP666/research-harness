"""v2 Step 5.1 — bounded claim verification.

Cross-claim consistency detection with:
- Deterministic prefilter: group claims by shared (task, dataset, metric)
  buckets so only comparable claims are compared.
- Hard cap on LLM pair-checks per topic (default 200). Budget is split
  across groups proportionally so large buckets don't starve small ones.
- Modality-aware confidence: figure/table/equation-supported claims get
  ``needs_human_review=True`` regardless of scores.
- Advisory mode by default (scores logged, no gate blocking). Strict mode
  opt-in via env flag.

This is Step 5.1 of the rh optimization v2 plan; the advisory artifact
surfaced here feeds the frontend claim-verification dashboard in Step 6.2.
"""

from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from ..storage.db import Database

logger = logging.getLogger(__name__)


DEFAULT_PAIR_BUDGET = 200
STRICT_CONSISTENCY_THRESHOLD = 0.3


@dataclass
class NormalizedClaimRow:
    id: int
    topic_id: int
    paper_id: int
    claim_text: str
    method: str
    dataset: str
    metric: str
    task: str
    task_canonical: str
    modality: str
    confidence: float


@dataclass
class ContradictionCandidate:
    claim_a: NormalizedClaimRow
    claim_b: NormalizedClaimRow
    same_task: bool
    same_dataset: bool
    same_metric: bool


@dataclass
class PairResult:
    claim_a_id: int
    claim_b_id: int
    contradicts: bool
    reason: str
    confidence: float


@dataclass
class ClaimVerificationResult:
    topic_id: int
    total_claims: int
    pairs_considered: int
    pairs_checked: int
    contradictions_found: int
    pair_results: list[PairResult] = field(default_factory=list)
    flagged_for_human_review: list[int] = field(default_factory=list)
    advisory: bool = True
    strict_block: bool = False


# ---------------------------------------------------------------------------
# Load claims
# ---------------------------------------------------------------------------


def _load_normalized_claims(db: Database, topic_id: int) -> list[NormalizedClaimRow]:
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT id, topic_id, paper_id, claim_text, method, dataset, metric,
                   task, COALESCE(task_canonical, '') AS task_canonical,
                   COALESCE(modality, 'text') AS modality, confidence
            FROM normalized_claims
            WHERE topic_id = ?
            """,
            (topic_id,),
        ).fetchall()
        return [
            NormalizedClaimRow(
                id=int(r["id"]),
                topic_id=int(r["topic_id"]),
                paper_id=int(r["paper_id"]),
                claim_text=r["claim_text"] or "",
                method=r["method"] or "",
                dataset=r["dataset"] or "",
                metric=r["metric"] or "",
                task=r["task"] or "",
                task_canonical=r["task_canonical"] or "",
                modality=r["modality"] or "text",
                confidence=float(r["confidence"] or 0.0),
            )
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Deterministic prefilter
# ---------------------------------------------------------------------------


def _group_key(claim: NormalizedClaimRow) -> str:
    """Bucket claims that are comparable (same task + dataset + metric).

    Falls back to the original ``task`` field when ``task_canonical`` is
    empty (pre-Phase-2 rows).
    """
    task = (claim.task_canonical or claim.task).strip().lower()
    return "|".join(
        [
            task or "_",
            claim.dataset.strip().lower() or "_",
            claim.metric.strip().lower() or "_",
        ]
    )


def _enumerate_candidate_pairs(
    claims: list[NormalizedClaimRow],
    *,
    pair_budget: int,
) -> tuple[list[ContradictionCandidate], int]:
    """Produce up to ``pair_budget`` pairs, split proportionally across
    groups so large buckets do not monopolize the budget.

    Returns (selected_pairs, total_pairs_considered).
    """
    groups: dict[str, list[NormalizedClaimRow]] = {}
    for c in claims:
        groups.setdefault(_group_key(c), []).append(c)

    # Compute total pair count per group and across all groups
    per_group_total = {k: max(0, len(v) * (len(v) - 1) // 2) for k, v in groups.items()}
    total_considered = sum(per_group_total.values())
    if total_considered == 0 or pair_budget <= 0:
        return [], total_considered

    # Cheap, deterministic case: take all pairs up to budget in group order.
    if total_considered <= pair_budget:
        selected: list[ContradictionCandidate] = []
        for group_claims in groups.values():
            for a, b in itertools.combinations(group_claims, 2):
                selected.append(
                    ContradictionCandidate(
                        claim_a=a,
                        claim_b=b,
                        same_task=_norm_equal(
                            a.task_canonical or a.task, b.task_canonical or b.task
                        ),
                        same_dataset=_norm_equal(a.dataset, b.dataset),
                        same_metric=_norm_equal(a.metric, b.metric),
                    )
                )
        return selected, total_considered

    # Scaled allocation: give each group floor(budget * share). Remainder
    # goes to the largest group(s) to use the full budget.
    allocations: dict[str, int] = {}
    remaining = pair_budget
    for key, n_pairs in sorted(per_group_total.items(), key=lambda kv: -kv[1]):
        share = int(pair_budget * (n_pairs / total_considered))
        allocations[key] = min(share, n_pairs)
        remaining -= allocations[key]
    # Hand remaining slots to groups in largest-first order until exhausted.
    for key in sorted(per_group_total, key=lambda k: -per_group_total[k]):
        if remaining <= 0:
            break
        room = per_group_total[key] - allocations[key]
        if room <= 0:
            continue
        give = min(remaining, room)
        allocations[key] += give
        remaining -= give

    selected_pairs: list[ContradictionCandidate] = []
    for key, group_claims in groups.items():
        quota = allocations.get(key, 0)
        if quota <= 0:
            continue
        taken = 0
        for a, b in itertools.combinations(group_claims, 2):
            if taken >= quota:
                break
            selected_pairs.append(
                ContradictionCandidate(
                    claim_a=a,
                    claim_b=b,
                    same_task=_norm_equal(
                        a.task_canonical or a.task, b.task_canonical or b.task
                    ),
                    same_dataset=_norm_equal(a.dataset, b.dataset),
                    same_metric=_norm_equal(a.metric, b.metric),
                )
            )
            taken += 1

    return selected_pairs, total_considered


def _norm_equal(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower() and bool(a.strip())


# ---------------------------------------------------------------------------
# LLM pair check (stubbable for tests)
# ---------------------------------------------------------------------------

_DEFAULT_PAIR_PROMPT = (
    "You are an adversarial reviewer checking two claims for contradiction.\n"
    'Return strict JSON: {{"contradicts": true|false, "reason": "<text>"}}.\n\n'
    "Claim A: {a}\nClaim B: {b}\n\n"
    "Two claims contradict only if they make mutually-exclusive statements "
    "about the SAME method on the SAME task/dataset. If they measure different "
    "aspects or use different baselines, they DO NOT contradict. Be strict."
)


def _llm_pair_check(pair: ContradictionCandidate) -> PairResult:
    """LLM pair check. Separated so tests can monkeypatch it without an API call."""
    from . import llm_primitives

    prompt = _DEFAULT_PAIR_PROMPT.format(
        a=pair.claim_a.claim_text, b=pair.claim_b.claim_text
    )
    try:
        client = llm_primitives._get_client(None, tier="light")
        raw = llm_primitives._client_chat(client, prompt)
        parsed = llm_primitives._parse_json(raw, primitive="claim_verification")
        contradicts = bool(parsed.get("contradicts", False))
        reason = str(parsed.get("reason", "")).strip()[:500]
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=contradicts,
            reason=reason,
            confidence=0.7 if contradicts else 0.5,
        )
    except Exception as exc:
        logger.warning("claim pair check failed: %s", exc)
        return PairResult(
            claim_a_id=pair.claim_a.id,
            claim_b_id=pair.claim_b.id,
            contradicts=False,
            reason=f"check_failed: {exc}",
            confidence=0.0,
        )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist_contradictions(
    db: Database,
    topic_id: int,
    results: list[PairResult],
    pairs: list[ContradictionCandidate],
) -> None:
    conn = db.connect()
    try:
        by_ids = {(p.claim_a.id, p.claim_b.id): p for p in pairs}
        for r in results:
            if not r.contradicts:
                continue
            p = by_ids.get((r.claim_a_id, r.claim_b_id))
            if p is None:
                continue
            conn.execute(
                """
                INSERT INTO contradictions (
                    topic_id, claim_a_id, claim_b_id, same_task, same_dataset,
                    same_metric, confidence, conflict_reason, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'candidate')
                """,
                (
                    topic_id,
                    r.claim_a_id,
                    r.claim_b_id,
                    int(p.same_task),
                    int(p.same_dataset),
                    int(p.same_metric),
                    float(r.confidence),
                    r.reason,
                ),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_claims(
    db: Database,
    topic_id: int,
    *,
    pair_budget: int | None = None,
    pair_check_fn: Any = None,
    persist: bool = True,
) -> ClaimVerificationResult:
    """Run bounded cross-claim consistency verification for a topic.

    Args:
        db: Database
        topic_id: Topic
        pair_budget: Hard cap on LLM pair checks. Defaults to DEFAULT_PAIR_BUDGET.
        pair_check_fn: Test hook for stubbing the LLM call; signature
            (pair: ContradictionCandidate) -> PairResult.
        persist: If True, write contradiction rows to DB.

    Returns:
        ClaimVerificationResult with counts, flags, and per-pair results.
    """
    budget = pair_budget or DEFAULT_PAIR_BUDGET
    claims = _load_normalized_claims(db, topic_id)

    if not claims:
        return ClaimVerificationResult(
            topic_id=topic_id,
            total_claims=0,
            pairs_considered=0,
            pairs_checked=0,
            contradictions_found=0,
            advisory=True,
        )

    # Flag claims whose evidence is non-textual: these always get human review.
    flagged = [c.id for c in claims if c.modality in {"figure", "table", "equation"}]

    pairs, considered = _enumerate_candidate_pairs(claims, pair_budget=budget)

    checker = pair_check_fn or _llm_pair_check
    results: list[PairResult] = []
    for pair in pairs:
        results.append(checker(pair))

    contradictions = sum(1 for r in results if r.contradicts)

    if persist and contradictions:
        _persist_contradictions(db, topic_id, results, pairs)

    strict_mode = os.environ.get("RESEARCH_HARNESS_CLAIM_VERIFY_STRICT") == "1"
    strict_block = False
    if strict_mode and claims:
        ratio = contradictions / max(len(claims), 1)
        if 1.0 - ratio < STRICT_CONSISTENCY_THRESHOLD:
            strict_block = True

    return ClaimVerificationResult(
        topic_id=topic_id,
        total_claims=len(claims),
        pairs_considered=considered,
        pairs_checked=len(results),
        contradictions_found=contradictions,
        pair_results=results,
        flagged_for_human_review=flagged,
        advisory=not strict_mode,
        strict_block=strict_block,
    )
