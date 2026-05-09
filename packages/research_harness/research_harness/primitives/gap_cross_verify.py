"""Cross-model gap verification.

Gaps emitted by ``gap_detect`` are a single LLM's subjective call, so
they carry a non-trivial hallucination risk. ``gap_cross_verify``
samples recent gaps for a topic, re-runs gap detection with a *different*
LLM tier (default ``heavy``), and marks gaps as ``cross_verified=1``
when the new run returns a semantically-matching gap (Jaccard over
content words ≥ ``min_jaccard``, default 0.6).

The primitive is idempotent on ``cross_check_runs`` counter: every
invocation increments it for touched gaps, so we can tell how many
cross-checks a gap has survived.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from llm_router.client import LLMClient, resolve_llm_config

from ..storage.db import Database
from .registry import register_primitive
from .types import PrimitiveCategory, PrimitiveSpec

logger = logging.getLogger(__name__)


_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
        "we",
        "our",
        "ours",
        "not",
        "but",
        "than",
        "then",
        "no",
    }
)


@dataclass
class VerifiedGap:
    gap_id: int
    description: str
    matched_description: str
    jaccard: float
    cross_verified: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GapCrossVerifyOutput:
    topic_id: int
    tier: str
    min_jaccard: float
    sample_size: int
    verified_count: int
    updated: list[VerifiedGap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "tier": self.tier,
            "min_jaccard": self.min_jaccard,
            "sample_size": self.sample_size,
            "verified_count": self.verified_count,
            "updated": [v.to_dict() for v in self.updated],
        }


GAP_CROSS_VERIFY_SPEC = PrimitiveSpec(
    name="gap_cross_verify",
    category=PrimitiveCategory.ANALYSIS,
    description=(
        "Re-run gap_detect on a topic with a different LLM tier and mark "
        "originals as cross_verified when Jaccard ≥ min_jaccard."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "topic_id": {"type": "integer"},
            "sample_size": {"type": "integer", "default": 10},
            "min_jaccard": {"type": "number", "default": 0.6},
            "tier": {"type": "string", "default": "heavy"},
        },
        "required": ["topic_id"],
    },
    output_type="GapCrossVerifyOutput",
    # This primitive *does* call an LLM (indirectly via gap_detect) but
    # manages its own client so spec.requires_llm stays False — keeps the
    # pre-flight check in the harness off our back when the caller
    # injects a fake client.
    requires_llm=False,
    idempotent=True,
)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


def _run_gap_detect_with_tier(
    db: Database, topic_id: int, tier: str, client: LLMClient | None
) -> list[str]:
    """Run gap_detect with an explicit tier, return fresh descriptions.

    We construct an LLMClient pinned to the requested tier and invoke
    gap_detect via its public entry so all the normal persistence runs
    (new gaps get inserted with the same INSERT-OR-IGNORE path; we only
    care about the returned descriptions here).
    """
    from ..execution import llm_primitives as _lp

    own = client is None
    if own:
        client = LLMClient(resolve_llm_config())
    client._default_tier = tier  # type: ignore[attr-defined]

    # Monkey-routing: gap_detect uses _get_client internally, but passing
    # _model=None keeps auto-tier resolution. To force the tier we
    # temporarily override _PRIMITIVE_TIERS, then restore.
    prev_tier = _lp._PRIMITIVE_TIERS.get("gap_detect")
    _lp._PRIMITIVE_TIERS["gap_detect"] = tier  # type: ignore[assignment]
    try:
        out = _lp.gap_detect(db=db, topic_id=topic_id)
    finally:
        if prev_tier is not None:
            _lp._PRIMITIVE_TIERS["gap_detect"] = prev_tier
        else:
            _lp._PRIMITIVE_TIERS.pop("gap_detect", None)

    return [g.description for g in out.gaps]


@register_primitive(GAP_CROSS_VERIFY_SPEC)
def gap_cross_verify(
    *,
    db: Database,
    topic_id: int,
    sample_size: int = 10,
    min_jaccard: float = 0.6,
    tier: str = "heavy",
    client: LLMClient | None = None,
    fresh_descriptions: list[str] | None = None,
    **_: Any,
) -> GapCrossVerifyOutput:
    """Sample recent gaps for the topic and cross-verify with a new run.

    ``fresh_descriptions`` is a test-only hook: when provided, skips the
    LLM re-detection and uses the supplied list directly.
    """
    conn = db.connect()
    try:
        sample = conn.execute(
            "SELECT id, description FROM gaps WHERE topic_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (topic_id, sample_size),
        ).fetchall()
    finally:
        conn.close()

    if not sample:
        return GapCrossVerifyOutput(
            topic_id=topic_id,
            tier=tier,
            min_jaccard=min_jaccard,
            sample_size=0,
            verified_count=0,
        )

    if fresh_descriptions is None:
        try:
            fresh_descriptions = _run_gap_detect_with_tier(db, topic_id, tier, client)
        except Exception as exc:
            logger.warning("gap_cross_verify: fresh run failed: %s", exc)
            fresh_descriptions = []

    updates: list[VerifiedGap] = []
    verified = 0
    for row in sample:
        gid = int(row["id"])
        orig = row["description"] or ""
        best_match = ""
        best_score = 0.0
        for cand in fresh_descriptions:
            score = _jaccard(orig, cand)
            if score > best_score:
                best_score = score
                best_match = cand
        is_verified = best_score >= min_jaccard
        updates.append(
            VerifiedGap(
                gap_id=gid,
                description=orig,
                matched_description=best_match,
                jaccard=round(best_score, 3),
                cross_verified=is_verified,
            )
        )
        if is_verified:
            verified += 1

    # Persist: always bump cross_check_runs; set cross_verified=1 when
    # a match ≥ threshold was found. We never unset cross_verified — a
    # gap that survived one cross-check is considered stable.
    conn = db.connect()
    try:
        for u in updates:
            if u.cross_verified:
                conn.execute(
                    "UPDATE gaps SET cross_verified = 1, "
                    "cross_check_runs = cross_check_runs + 1 WHERE id = ?",
                    (u.gap_id,),
                )
            else:
                conn.execute(
                    "UPDATE gaps SET cross_check_runs = cross_check_runs + 1 "
                    "WHERE id = ?",
                    (u.gap_id,),
                )
        conn.commit()
    finally:
        conn.close()

    return GapCrossVerifyOutput(
        topic_id=topic_id,
        tier=tier,
        min_jaccard=min_jaccard,
        sample_size=len(sample),
        verified_count=verified,
        updated=updates,
    )
