"""RH Discover: signal-to-direction incubation surface."""

from __future__ import annotations

from .models import (
    DiscoverSignal,
    FitScore,
    GoalPreview,
    OpportunityBrief,
    OpportunityReadiness,
    RhHandoff,
    SeedPaper,
    TrendContext,
    build_opportunity_brief,
    infer_opportunity_readiness,
    render_opportunity_brief_markdown,
    slugify_topic_name,
)
from .report import (
    DiscoverReport,
    build_sample_weekly_report,
    render_discover_report_html,
    render_discover_report_markdown,
)
from .issues import (
    DiscoverIssueSummary,
    default_issue_dir,
    discover_report_from_dict,
    list_discover_issues,
    load_discover_issue,
    load_discover_report_from_file,
    load_latest_discover_report,
)
from .samples import load_sample_briefs
from .schema import opportunity_brief_schema
from .sources import SourceDefinition, list_source_definitions
from .opportunities import (
    find_opportunity,
    list_opportunity_cards,
    load_opportunity_report,
    opportunity_slug,
)
from .evidence import (
    DiscoveryEvidenceProblemSpec,
    EvidenceRecord,
    build_evidence_manifest,
    collect_discovery_evidence,
    default_evidence_problem_specs,
    load_evidence_manifest,
    validate_evidence_manifest,
    write_evidence_manifest,
)

__all__ = [
    "DiscoverSignal",
    "DiscoveryEvidenceProblemSpec",
    "DiscoverReport",
    "DiscoverIssueSummary",
    "EvidenceRecord",
    "FitScore",
    "GoalPreview",
    "OpportunityBrief",
    "OpportunityReadiness",
    "RhHandoff",
    "SeedPaper",
    "SourceDefinition",
    "TrendContext",
    "build_sample_weekly_report",
    "build_evidence_manifest",
    "build_opportunity_brief",
    "collect_discovery_evidence",
    "default_issue_dir",
    "default_evidence_problem_specs",
    "discover_report_from_dict",
    "list_source_definitions",
    "list_discover_issues",
    "load_sample_briefs",
    "load_evidence_manifest",
    "infer_opportunity_readiness",
    "load_discover_issue",
    "load_discover_report_from_file",
    "load_latest_discover_report",
    "opportunity_brief_schema",
    "opportunity_slug",
    "find_opportunity",
    "list_opportunity_cards",
    "load_opportunity_report",
    "render_discover_report_html",
    "render_discover_report_markdown",
    "render_opportunity_brief_markdown",
    "slugify_topic_name",
    "validate_evidence_manifest",
    "write_evidence_manifest",
]
