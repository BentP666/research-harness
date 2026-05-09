"""Per-stage, per-tier rubric definitions for research quality scoring."""

from __future__ import annotations

from typing import Any

from . import analyze, build, experiment, init, propose, write

_STAGE_MODULES = {
    "init": init,
    "build": build,
    "analyze": analyze,
    "propose": propose,
    "experiment": experiment,
    "write": write,
}

THRESHOLDS_BY_VENUE_TIER: dict[str, float] = {
    "A": 7.8,
    "B": 6.8,
    "workshop": 5.5,
}


def get_rubric(stage: str, tier: str = "standard") -> dict[str, Any]:
    mod = _STAGE_MODULES.get(stage)
    if mod is None:
        raise ValueError(f"Unknown stage: {stage}")
    rubrics: dict[str, dict[str, Any]] = mod.RUBRICS
    key = tier.lower()
    if key not in rubrics:
        raise ValueError(f"Unknown tier '{tier}' for stage '{stage}'")
    return rubrics[key]


def get_threshold(venue_tier: str) -> float:
    return THRESHOLDS_BY_VENUE_TIER.get(venue_tier, 6.8)
