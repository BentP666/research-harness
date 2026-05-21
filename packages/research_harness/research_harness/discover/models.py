"""RH Discover OpportunityBrief contract.

This module is intentionally independent from RH Core storage and
orchestration. The boundary between Discover and Core is the
``OpportunityBrief`` payload: Discover can move quickly while Core consumes a
stable, explicit handoff contract.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SignalType = Literal["paper", "blog", "product", "repo", "model", "benchmark", "news"]
SignalImportance = Literal["act_now", "watch", "horizon"]
TrendWindow = Literal["24h", "7d", "1y", "3y", "5y"]
Saturation = Literal["low", "medium", "high"]
ComputeNeed = Literal["low", "medium", "high"]

DEFAULT_SUGGESTED_PRIMITIVES = ("paper_search", "paper_ingest", "gap_detect")
_SIGNAL_TYPES = {"paper", "blog", "product", "repo", "model", "benchmark", "news"}
_SIGNAL_IMPORTANCE = {"act_now", "watch", "horizon"}
_TREND_WINDOWS = {"24h", "7d", "1y", "3y", "5y"}
_SATURATION = {"low", "medium", "high"}
_COMPUTE_NEEDS = {"low", "medium", "high"}


def _validate_unit_interval(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


@dataclass(frozen=True)
class DiscoverSignal:
    """A research or technology signal that may indicate a direction."""

    type: SignalType
    title: str
    url: str
    published_at: str = ""
    importance: SignalImportance = "watch"
    reason: str = ""

    def __post_init__(self) -> None:
        if self.type not in _SIGNAL_TYPES:
            raise ValueError(f"unsupported signal type: {self.type!r}")
        if self.importance not in _SIGNAL_IMPORTANCE:
            raise ValueError(f"unsupported signal importance: {self.importance!r}")
        if not self.title.strip():
            raise ValueError("signal title is required")
        if not self.url.strip():
            raise ValueError("signal url is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrendContext:
    """Lightweight trend context for the brief."""

    window: TrendWindow = "7d"
    growth_summary: str = ""
    saturation: Saturation = "medium"

    def __post_init__(self) -> None:
        if self.window not in _TREND_WINDOWS:
            raise ValueError(f"unsupported trend window: {self.window!r}")
        if self.saturation not in _SATURATION:
            raise ValueError(f"unsupported trend saturation: {self.saturation!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SeedPaper:
    """A paper candidate for RH Core ingestion after handoff."""

    title: str
    doi: str | None = None
    arxiv_id: str | None = None
    url: str = ""
    year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FitScore:
    """Editorial scoring stub.

    Values are 0..1. The first scaffold keeps defaults neutral (0.0) so the CLI
    does not imply measured precision before we have validated the scoring
    method.
    """

    trend: float = 0.0
    novelty: float = 0.0
    feasibility: float = 0.0
    user_fit: float = 0.0
    risk: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in self.to_dict().items():
            _validate_unit_interval(f"fit_score.{field_name}", value)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class GoalPreview:
    """A lightweight, measurable research-goal seed for Discovery.

    Discovery owns goal previews as an execution-readiness signal. RH Core still
    owns persisted ``goal_pool`` rows after a user chooses to hand off an
    opportunity.
    """

    title: str
    dataset: str | None = None
    baseline: str | None = None
    metric_name: str | None = None
    target_metric_delta: float | None = None
    time_window_days: int | None = None
    compute_need: ComputeNeed = "medium"
    feasibility: float = 0.0
    evidence_strength: float = 0.0
    risk: float = 0.0
    first_steps: list[str] = field(default_factory=list)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("goal_preview.title is required")
        if self.compute_need not in _COMPUTE_NEEDS:
            raise ValueError(
                f"unsupported goal_preview.compute_need: {self.compute_need!r}"
            )
        _validate_unit_interval("goal_preview.feasibility", self.feasibility)
        _validate_unit_interval(
            "goal_preview.evidence_strength", self.evidence_strength
        )
        _validate_unit_interval("goal_preview.risk", self.risk)
        if self.time_window_days is not None and self.time_window_days <= 0:
            raise ValueError("goal_preview.time_window_days must be positive")
        normalized_steps = [step.strip() for step in self.first_steps if step.strip()]
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "first_steps", normalized_steps)
        object.__setattr__(
            self,
            "id",
            self.id.strip() if self.id.strip() else slugify_topic_name(self.title),
        )

    @property
    def goalability(self) -> float:
        """Estimate whether this preview can become a measurable RH Core goal."""

        signals = [
            bool(self.dataset and self.dataset.strip()),
            bool(self.baseline and self.baseline.strip()),
            bool(self.metric_name and self.metric_name.strip()),
            self.target_metric_delta is not None,
            bool(self.first_steps),
        ]
        return round(sum(1 for signal in signals if signal) / len(signals), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "dataset": self.dataset,
            "baseline": self.baseline,
            "metric_name": self.metric_name,
            "target_metric_delta": self.target_metric_delta,
            "time_window_days": self.time_window_days,
            "compute_need": self.compute_need,
            "feasibility": self.feasibility,
            "evidence_strength": self.evidence_strength,
            "risk": self.risk,
            "first_steps": list(self.first_steps),
            "goalability": self.goalability,
        }


@dataclass(frozen=True)
class OpportunityReadiness:
    """Editorial readiness signals for turning an opportunity into RH work."""

    evidence: float = 0.0
    novelty: float = 0.0
    feasibility: float = 0.0
    goalability: float = 0.0
    handoff_readiness: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in self.to_dict().items():
            _validate_unit_interval(f"readiness.{field_name}", value)

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class RhHandoff:
    """Minimal bridge from RH Discover into RH Core."""

    topic_name: str
    initial_queries: list[str]
    suggested_primitives: list[str] = field(
        default_factory=lambda: list(DEFAULT_SUGGESTED_PRIMITIVES)
    )

    def __post_init__(self) -> None:
        if not self.topic_name.strip():
            raise ValueError("rh_handoff.topic_name is required")
        if not self.suggested_primitives:
            raise ValueError("rh_handoff.suggested_primitives is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityBrief:
    """Stable output contract produced by RH Discover."""

    title: str
    summary: str
    why_now: str
    signals: list[DiscoverSignal]
    trend_context: TrendContext = field(default_factory=TrendContext)
    seed_papers: list[SeedPaper] = field(default_factory=list)
    fit_score: FitScore = field(default_factory=FitScore)
    goal_previews: list[GoalPreview] = field(default_factory=list)
    readiness: OpportunityReadiness | None = None
    risks: list[str] = field(default_factory=list)
    recommended_next_steps: list[str] = field(default_factory=list)
    rh_handoff: RhHandoff | None = None

    def validate(self) -> None:
        """Enforce RH Discover guardrails.

        A brief is allowed to be rough, but it cannot be "just news": it must
        contain a why-now rationale, at least one evidence signal, a next
        research action, and a concrete RH handoff query.
        """

        missing: list[str] = []
        if not self.title.strip():
            missing.append("title")
        if not self.summary.strip():
            missing.append("summary")
        if not self.why_now.strip():
            missing.append("why_now")
        if not self.signals:
            missing.append("signals")
        if not self.recommended_next_steps:
            missing.append("recommended_next_steps")
        if self.rh_handoff is None or not self.rh_handoff.initial_queries:
            missing.append("rh_handoff.initial_queries")
        if missing:
            raise ValueError(
                "RH Discover item is only news, not a research opportunity; "
                f"missing: {', '.join(missing)}"
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "title": self.title,
            "summary": self.summary,
            "why_now": self.why_now,
            "signals": [signal.to_dict() for signal in self.signals],
            "trend_context": self.trend_context.to_dict(),
            "seed_papers": [paper.to_dict() for paper in self.seed_papers],
            "fit_score": self.fit_score.to_dict(),
            "goal_previews": [goal.to_dict() for goal in self.goal_previews],
            "readiness": (
                self.readiness.to_dict()
                if self.readiness
                else infer_opportunity_readiness(self).to_dict()
            ),
            "risks": list(self.risks),
            "recommended_next_steps": list(self.recommended_next_steps),
            "rh_handoff": self.rh_handoff.to_dict() if self.rh_handoff else None,
        }


def infer_opportunity_readiness(brief: OpportunityBrief) -> OpportunityReadiness:
    """Infer conservative readiness when editors have not supplied it."""

    evidence = min(len(brief.signals) / 2, 1.0)
    novelty = brief.fit_score.novelty or 0.5
    if brief.goal_previews:
        feasibility = sum(goal.feasibility for goal in brief.goal_previews) / len(
            brief.goal_previews
        )
        goalability = sum(goal.goalability for goal in brief.goal_previews) / len(
            brief.goal_previews
        )
    else:
        feasibility = brief.fit_score.feasibility
        goalability = 0.0
    handoff_base = 0.5 if brief.rh_handoff and brief.rh_handoff.initial_queries else 0.0
    handoff_readiness = min(handoff_base + (0.5 * goalability), 1.0)
    return OpportunityReadiness(
        evidence=round(evidence, 4),
        novelty=round(novelty, 4),
        feasibility=round(feasibility, 4),
        goalability=round(goalability, 4),
        handoff_readiness=round(handoff_readiness, 4),
    )


def slugify_topic_name(title: str) -> str:
    """Convert a human title into a stable RH topic slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled-opportunity"


def build_opportunity_brief(
    *,
    title: str,
    summary: str,
    why_now: str,
    signals: list[DiscoverSignal],
    seed_papers: list[SeedPaper] | None = None,
    trend_context: TrendContext | None = None,
    fit_score: FitScore | None = None,
    goal_previews: list[GoalPreview] | None = None,
    readiness: OpportunityReadiness | None = None,
    risks: list[str] | None = None,
    recommended_next_steps: list[str],
    initial_queries: list[str],
    topic_name: str | None = None,
    suggested_primitives: list[str] | None = None,
) -> OpportunityBrief:
    """Build and validate an OpportunityBrief with conservative defaults."""

    normalized_next_steps = [
        step.strip() for step in recommended_next_steps if step and step.strip()
    ]
    normalized_queries = [query.strip() for query in initial_queries if query.strip()]
    normalized_primitives = [
        primitive.strip()
        for primitive in (suggested_primitives or list(DEFAULT_SUGGESTED_PRIMITIVES))
        if primitive.strip()
    ]

    brief = OpportunityBrief(
        title=title.strip(),
        summary=summary.strip(),
        why_now=why_now.strip(),
        signals=signals,
        trend_context=trend_context or TrendContext(),
        seed_papers=seed_papers or [],
        fit_score=fit_score or FitScore(),
        goal_previews=goal_previews or [],
        readiness=readiness,
        risks=risks or [],
        recommended_next_steps=normalized_next_steps,
        rh_handoff=RhHandoff(
            topic_name=(
                topic_name.strip() if topic_name else slugify_topic_name(title)
            ),
            initial_queries=normalized_queries,
            suggested_primitives=normalized_primitives,
        ),
    )
    brief.validate()
    return brief


def render_opportunity_brief_markdown(brief: OpportunityBrief) -> str:
    """Render a brief for weekly/manual content validation."""

    payload = brief.to_dict()
    signal_lines = [
        f"- **{signal['type']}**: [{signal['title']}]({signal['url']})"
        f" — {signal['importance']}; {signal['reason']}"
        for signal in payload["signals"]
    ]
    seed_lines = [
        f"- {paper['title']} ({paper.get('year') or 'n.d.'})"
        for paper in payload["seed_papers"]
    ]
    query_lines = [f"- `{query}`" for query in payload["rh_handoff"]["initial_queries"]]
    next_step_lines = [f"- {step}" for step in payload["recommended_next_steps"]]
    risk_lines = [f"- {risk}" for risk in payload["risks"]] or ["- Not assessed yet."]

    return "\n".join(
        [
            f"# {payload['title']}",
            "",
            payload["summary"],
            "",
            "## Why now",
            payload["why_now"],
            "",
            "## Signals",
            *signal_lines,
            "",
            "## Seed papers",
            *(seed_lines or ["- No seed papers yet."]),
            "",
            "## Risks",
            *risk_lines,
            "",
            "## Recommended next steps",
            *next_step_lines,
            "",
            "## RH Handoff",
            f"- Topic: `{payload['rh_handoff']['topic_name']}`",
            "- Initial queries:",
            *query_lines,
            "- Suggested primitives: "
            + ", ".join(payload["rh_handoff"]["suggested_primitives"]),
            "",
        ]
    )
