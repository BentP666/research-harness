"""Quality-tier configuration (Economy / Standard / Premium).

Each tier is a frozen config bundle. Primitives accept a ``tier`` kwarg and
resolve defaults from ``topic.quality_tier`` when omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TierName = Literal["economy", "standard", "premium"]


@dataclass(frozen=True)
class TierConfig:
    name: TierName
    judge_mode: Literal["single", "dual_gate", "dual_all"]
    retries_after_rubric_miss: int
    roles: tuple[str, ...]
    trends_years: int
    trends_top_venues: int
    trends_top_clusters: int
    rubric_dimensions: int
    topic_candidate_clusters: int
    cost_estimate_usd: str


ECONOMY = TierConfig(
    name="economy",
    judge_mode="single",
    retries_after_rubric_miss=0,
    roles=("generator", "judge"),
    trends_years=3,
    trends_top_venues=30,
    trends_top_clusters=20,
    rubric_dimensions=3,
    topic_candidate_clusters=10,
    cost_estimate_usd="$3–8",
)

STANDARD = TierConfig(
    name="standard",
    judge_mode="dual_gate",
    retries_after_rubric_miss=1,
    roles=("generator", "judge", "challenger"),
    trends_years=5,
    trends_top_venues=50,
    trends_top_clusters=50,
    rubric_dimensions=7,
    topic_candidate_clusters=30,
    cost_estimate_usd="$15–30",
)

PREMIUM = TierConfig(
    name="premium",
    judge_mode="dual_all",
    retries_after_rubric_miss=2,
    roles=("generator", "judge", "challenger"),
    trends_years=5,
    trends_top_venues=100,
    trends_top_clusters=100,
    rubric_dimensions=10,
    topic_candidate_clusters=50,
    cost_estimate_usd="$60–150",
)

TIERS: dict[TierName, TierConfig] = {
    "economy": ECONOMY,
    "standard": STANDARD,
    "premium": PREMIUM,
}


def get_tier(name: str | None = None) -> TierConfig:
    if name is None:
        name = "standard"
    return TIERS.get(name, STANDARD)  # type: ignore[arg-type]
