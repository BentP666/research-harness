"""Opportunity lookup helpers for RH Discovery 1.0 surfaces."""

from __future__ import annotations

from typing import Any

from .models import OpportunityBrief, slugify_topic_name
from .report import DiscoverReport, build_sample_weekly_report
from .issues import load_latest_discover_report


def opportunity_slug(brief: OpportunityBrief) -> str:
    """Return the stable public slug for an OpportunityBrief."""

    if brief.rh_handoff and brief.rh_handoff.topic_name.strip():
        return slugify_topic_name(brief.rh_handoff.topic_name)
    return slugify_topic_name(brief.title)


def load_opportunity_report(
    *,
    sample: bool = True,
    cadence: str | None = "weekly",
) -> DiscoverReport:
    """Load the report backing opportunity list/detail pages."""

    if sample:
        return build_sample_weekly_report()
    return load_latest_discover_report(cadence=cadence)


def list_opportunity_cards(report: DiscoverReport) -> list[dict[str, Any]]:
    """Flatten report briefs into card payloads for the Discovery frontend."""

    cards: list[dict[str, Any]] = []
    for brief in report.briefs:
        payload = brief.to_dict()
        cards.append({"slug": opportunity_slug(brief), **payload})
    return cards


def find_opportunity(report: DiscoverReport, slug: str) -> OpportunityBrief:
    """Find one opportunity by public slug."""

    normalized = slugify_topic_name(slug)
    for brief in report.briefs:
        if opportunity_slug(brief) == normalized:
            return brief
    raise KeyError(slug)
