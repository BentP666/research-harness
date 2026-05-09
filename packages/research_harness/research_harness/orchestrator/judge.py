"""Rubric scoring judge engine.

Routes to single or dual judge based on tier + gate kind, produces structured
scores, and writes to rubric_scores table.

Shadow vs live mode is resolved at call time in this priority:
  1. ``user_preferences.auto_rollback_live`` row (if present) — set from the UI
  2. ``RUBRIC_AUTO_ROLLBACK`` env var — for CI / script overrides
  3. Default: shadow mode ON (safe default — spec §7.3 demands shadow window
     before enabling auto-rollback).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from ..rubrics import get_rubric, get_threshold

logger = logging.getLogger(__name__)

_ENV_DEFAULT = "false"  # shadow mode on by default; spec §7.3


def _env_live_mode() -> bool | None:
    """Read RUBRIC_AUTO_ROLLBACK env var. Returns None if unset, bool otherwise."""
    raw = os.environ.get("RUBRIC_AUTO_ROLLBACK")
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes")


def _pref_live_mode(conn: sqlite3.Connection | None) -> bool | None:
    """Read user_preferences.auto_rollback_live. Returns None if column missing
    (old DB before migration 041) or no preferences row exists yet."""
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT auto_rollback_live FROM user_preferences ORDER BY id LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    val = row["auto_rollback_live"] if hasattr(row, "keys") else row[0]
    if val is None:
        return None
    try:
        return bool(int(val))
    except (TypeError, ValueError):
        return str(val).strip().lower() in ("1", "true", "yes")


def resolve_shadow_mode(conn: sqlite3.Connection | None = None) -> bool:
    """Return True if shadow mode is active (auto-rollback disabled)."""
    pref = _pref_live_mode(conn)
    if pref is not None:
        return not pref
    env = _env_live_mode()
    if env is not None:
        return not env
    return _ENV_DEFAULT not in ("1", "true", "yes")


# Back-compat alias: module-level SHADOW_MODE is still read by some call sites
# that don't have a connection handy. Honors env, ignores the DB preference.
SHADOW_MODE = os.environ.get("RUBRIC_AUTO_ROLLBACK", _ENV_DEFAULT).lower() not in (
    "1",
    "true",
    "yes",
)

DUAL_JUDGE_GATES = {"approval_gate", "adversarial_gate", "review_gate"}


def _resolve_threshold(
    conn: sqlite3.Connection | None,
    stage: str,
    tier: str,
    venue_tier: str,
) -> float:
    """Prefer calibrated threshold from rubric_calibrations; fall back to the
    venue-tier default from the rubrics module."""
    default = get_threshold(venue_tier)
    if conn is None:
        return default
    try:
        row = conn.execute(
            "SELECT threshold FROM rubric_calibrations WHERE stage = ? AND tier = ?",
            (stage, tier),
        ).fetchone()
    except sqlite3.OperationalError:
        return default
    if not row:
        return default
    val = row["threshold"] if hasattr(row, "keys") else row[0]
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


@dataclass
class JudgeResult:
    dimension_scores: dict[str, float]
    weighted_total: float
    verdict: str
    shadow_verdict: str | None
    critique: dict[str, str] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    rubric_version: str = ""
    judge_model: str = ""


def _compute_weighted_total(
    dimension_scores: dict[str, float],
    rubric_dims: list[dict[str, Any]],
) -> float:
    total = 0.0
    weight_sum = 0.0
    for dim in rubric_dims:
        name = dim["name"]
        weight = dim["weight"]
        if weight <= 0:
            continue
        score = dimension_scores.get(name, 0.0)
        total += score * weight
        weight_sum += weight
    if weight_sum > 0:
        return round(total / weight_sum, 2)
    return 0.0


def _determine_verdict(
    weighted_total: float,
    threshold: float,
) -> str:
    if weighted_total >= threshold:
        return "pass"
    if weighted_total >= threshold - 1.0:
        return "retry_recommended"
    return "rollback"


def run_rubric(
    conn: sqlite3.Connection,
    artifact_id: int,
    topic_id: int,
    stage: str,
    tier: str = "standard",
    venue_tier: str = "B",
    gate_type: str | None = None,
    dimension_scores: dict[str, float] | None = None,
    critique: dict[str, str] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    judge_agent_id: int | None = None,
    judge_model: str = "",
) -> JudgeResult:
    """Score an artifact against the rubric for its stage and tier.

    If dimension_scores is provided, uses those directly (for testing or
    pre-computed scores). Otherwise, callers are expected to obtain scores
    from the LLM judge and pass them in.
    """
    rubric = get_rubric(stage, tier)
    threshold = _resolve_threshold(conn, stage, tier, venue_tier)
    rubric_version = f"{stage}@v1"

    if dimension_scores is None:
        dimension_scores = {}

    weighted_total = _compute_weighted_total(dimension_scores, rubric["dimensions"])
    raw_verdict = _determine_verdict(weighted_total, threshold)

    shadow = resolve_shadow_mode(conn)
    if shadow:
        shadow_verdict = raw_verdict if raw_verdict != "pass" else None
        actual_verdict = "pass"
    else:
        shadow_verdict = None
        actual_verdict = raw_verdict

    result = JudgeResult(
        dimension_scores=dimension_scores,
        weighted_total=weighted_total,
        verdict=actual_verdict,
        shadow_verdict=shadow_verdict,
        critique=critique or {},
        evidence_refs=evidence_refs or [],
        rubric_version=rubric_version,
        judge_model=judge_model,
    )

    conn.execute(
        """
        INSERT INTO rubric_scores
            (topic_id, artifact_id, stage, tier, judge_agent_id,
             dimension_scores, weighted_total, verdict, shadow_verdict,
             critique, evidence_refs, rubric_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            topic_id,
            artifact_id,
            stage,
            tier,
            judge_agent_id,
            json.dumps(dimension_scores),
            weighted_total,
            actual_verdict,
            shadow_verdict,
            json.dumps(critique or {}),
            json.dumps(evidence_refs or []),
            rubric_version,
        ),
    )

    if shadow_verdict:
        logger.info(
            "Shadow verdict for artifact %d: %s (would have %s, threshold=%.1f, score=%.2f)",
            artifact_id,
            shadow_verdict,
            shadow_verdict,
            threshold,
            weighted_total,
        )

    return result


def needs_dual_judge(tier: str, gate_type: str | None) -> bool:
    if tier == "premium":
        return True
    if tier == "standard" and gate_type in DUAL_JUDGE_GATES:
        return True
    return False


def get_retry_budget(tier: str) -> int:
    if tier == "economy":
        return 0
    if tier == "standard":
        return 1
    return 2
