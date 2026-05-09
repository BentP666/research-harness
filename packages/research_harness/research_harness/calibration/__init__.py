"""Rubric threshold calibration — Youden's J on a labeled anchor corpus.

The anchors ship with 60 seed entries (5 accept + 5 reject × 6 stages, all
`standard` tier). They are synthetic-but-realistic: scores chosen by hand
to reflect the behaviour a real accepted top-venue paper vs. a rejected /
preprint-only paper would score on the rubric.

To replace with real labeled data, overwrite ``anchors.jsonl`` with one JSON
object per line carrying ``stage``, ``tier``, ``label`` ("accept"|"reject"),
``dimension_scores`` (keyed by the rubric dimension name), plus optional
``paper_title`` / ``venue`` / ``year`` / ``note`` fields.
"""

from __future__ import annotations

from .anchors import Anchor, load_anchors
from .roc import youdens_j_threshold
from .runner import CalibrationResult, calibrate_all, calibrate_stage_tier

__all__ = [
    "Anchor",
    "CalibrationResult",
    "calibrate_all",
    "calibrate_stage_tier",
    "load_anchors",
    "youdens_j_threshold",
]
