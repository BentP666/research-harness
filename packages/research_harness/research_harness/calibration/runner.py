"""Calibration runner — computes thresholds from the anchor corpus and writes
them to ``rubric_calibrations``.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from ..orchestrator.judge import _compute_weighted_total
from ..rubrics import get_rubric, get_threshold
from .anchors import Anchor, load_anchors
from .roc import youdens_j_threshold

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    stage: str
    tier: str
    threshold: float
    anchor_count: int
    false_rollback_rate: float
    reject_rate: float
    used_default: bool  # True if no anchors were found for (stage, tier)


def _score_anchor(anchor: Anchor) -> float:
    rubric = get_rubric(anchor.stage, anchor.tier)
    return _compute_weighted_total(anchor.dimension_scores, rubric["dimensions"])


def calibrate_stage_tier(
    conn: sqlite3.Connection,
    stage: str,
    tier: str = "standard",
    anchors: list[Anchor] | None = None,
    venue_tier: str = "B",
) -> CalibrationResult:
    """Calibrate one (stage, tier) combination and write to DB."""
    if anchors is None:
        anchors = load_anchors()

    matching = [a for a in anchors if a.stage == stage and a.tier == tier]
    default_threshold = get_threshold(venue_tier)

    if not matching:
        result = CalibrationResult(
            stage=stage,
            tier=tier,
            threshold=default_threshold,
            anchor_count=0,
            false_rollback_rate=0.0,
            reject_rate=0.0,
            used_default=True,
        )
    else:
        positives = [_score_anchor(a) for a in matching if a.label == "accept"]
        negatives = [_score_anchor(a) for a in matching if a.label == "reject"]
        threshold, false_rollback, reject_rate = youdens_j_threshold(
            positives, negatives, default_threshold
        )
        result = CalibrationResult(
            stage=stage,
            tier=tier,
            threshold=threshold,
            anchor_count=len(matching),
            false_rollback_rate=false_rollback,
            reject_rate=reject_rate,
            used_default=False,
        )

    conn.execute(
        """
        INSERT INTO rubric_calibrations
            (stage, tier, threshold, false_rollback_rate, reject_rate, anchor_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(stage, tier) DO UPDATE SET
            threshold = excluded.threshold,
            false_rollback_rate = excluded.false_rollback_rate,
            reject_rate = excluded.reject_rate,
            anchor_count = excluded.anchor_count,
            calibrated_at = datetime('now')
        """,
        (
            result.stage,
            result.tier,
            result.threshold,
            result.false_rollback_rate,
            result.reject_rate,
            result.anchor_count,
        ),
    )
    conn.commit()
    return result


_STAGES = ("init", "build", "analyze", "propose", "experiment", "write")
_TIERS = ("economy", "standard", "premium")


def calibrate_all(
    conn: sqlite3.Connection,
    anchors: list[Anchor] | None = None,
) -> list[CalibrationResult]:
    """Calibrate every (stage, tier) pair and return the results."""
    if anchors is None:
        anchors = load_anchors()
    results: list[CalibrationResult] = []
    for stage in _STAGES:
        for tier in _TIERS:
            try:
                results.append(calibrate_stage_tier(conn, stage, tier, anchors=anchors))
            except ValueError as exc:
                logger.warning("skipping %s/%s: %s", stage, tier, exc)
    return results
