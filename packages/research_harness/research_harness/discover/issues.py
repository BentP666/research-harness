"""File-backed RH Discover issue publishing.

A Discover issue is a curated daily/weekly JSON file that renders to the same
``DiscoverReport`` contract consumed by CLI, FastAPI, and the web app. Keeping
issues as files makes the early product easy to publish and review without
introducing database coupling before the editorial workflow stabilizes.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .models import (
    DiscoverSignal,
    FitScore,
    GoalPreview,
    OpportunityReadiness,
    SeedPaper,
    TrendContext,
    build_opportunity_brief,
)
from .report import DiscoverReport

IssueCadence = Literal["daily", "weekly", "special"]
IssueStatus = Literal["draft", "published", "archived"]

_VALID_CADENCES = {"daily", "weekly", "special"}
_VALID_STATUSES = {"draft", "published", "archived"}


@dataclass(frozen=True)
class DiscoverIssueSummary:
    """Small archive/listing record for an RH Discover issue."""

    issue_id: str
    title: str
    subtitle: str
    generated_at: str
    cadence: str
    status: str
    brief_count: int
    path: str = ""

    def to_dict(self, *, include_path: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_path:
            payload.pop("path", None)
        return payload


def default_issue_dir(start: Path | None = None) -> Path:
    """Resolve the default issue directory.

    Priority:
    1. ``RH_DISCOVER_ISSUES_DIR`` env var.
    2. ``docs/discover/issues`` under the current workspace/repo root.
    3. ``docs/discover/issues`` near this package checkout.
    """

    env_value = os.environ.get("RH_DISCOVER_ISSUES_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()

    roots: list[Path] = []
    cwd = (start or Path.cwd()).resolve()
    roots.extend([cwd, *cwd.parents])
    module_path = Path(__file__).resolve()
    roots.extend([module_path, *module_path.parents])

    for root in roots:
        candidate = root / "docs" / "discover" / "issues"
        if candidate.exists():
            return candidate

    return cwd / "docs" / "discover" / "issues"


def load_discover_report_from_file(path: str | Path) -> DiscoverReport:
    """Load and validate a DiscoverReport issue from JSON."""

    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid RH Discover issue JSON: {file_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("RH Discover issue must be a JSON object")
    return discover_report_from_dict(payload, issue_id_fallback=file_path.stem)


def discover_report_from_dict(
    payload: dict[str, Any], *, issue_id_fallback: str = ""
) -> DiscoverReport:
    """Convert an issue/report dict into the typed DiscoverReport contract."""

    report_payload = (
        payload.get("report") if isinstance(payload.get("report"), dict) else payload
    )
    issue_id = str(
        payload.get("issue_id") or report_payload.get("issue_id") or issue_id_fallback
    )
    cadence = str(payload.get("cadence") or report_payload.get("cadence") or "weekly")
    status = str(payload.get("status") or report_payload.get("status") or "published")

    _validate_issue_metadata(issue_id=issue_id, cadence=cadence, status=status)

    raw_briefs = report_payload.get("briefs")
    if not isinstance(raw_briefs, list) or not raw_briefs:
        raise ValueError("RH Discover issue requires at least one brief")

    report = DiscoverReport(
        issue_id=issue_id,
        cadence=cadence,
        status=status,
        title=str(report_payload.get("title") or "RH Discover"),
        subtitle=str(
            report_payload.get("subtitle") or "Research signals worth studying."
        ),
        generated_at=str(report_payload.get("generated_at") or ""),
        product=str(report_payload.get("product") or "RH Discover"),
        briefs=[_brief_from_dict(raw) for raw in raw_briefs],
    )
    report.validate()
    return report


def list_discover_issues(
    issue_dir: str | Path | None = None,
    *,
    cadence: str | None = None,
    include_drafts: bool = False,
) -> list[DiscoverIssueSummary]:
    """List curated Discover issues from a directory."""

    directory = Path(issue_dir) if issue_dir is not None else default_issue_dir()
    if not directory.exists():
        return []

    summaries: list[DiscoverIssueSummary] = []
    for path in sorted(directory.glob("*.json")):
        try:
            report = load_discover_report_from_file(path)
        except ValueError:
            continue
        if cadence is not None and report.cadence != cadence:
            continue
        if not include_drafts and report.status != "published":
            continue
        summaries.append(summary_from_report(report, path=path))

    return sorted(
        summaries,
        key=lambda item: (item.generated_at, item.issue_id),
        reverse=True,
    )


def load_discover_issue(
    issue_id: str,
    issue_dir: str | Path | None = None,
    *,
    include_drafts: bool = False,
) -> DiscoverReport:
    """Load one issue by id."""

    directory = Path(issue_dir) if issue_dir is not None else default_issue_dir()
    direct_path = directory / f"{issue_id}.json"
    candidate_paths = (
        [direct_path] if direct_path.exists() else sorted(directory.glob("*.json"))
    )

    for path in candidate_paths:
        report = load_discover_report_from_file(path)
        if report.issue_id != issue_id:
            continue
        if not include_drafts and report.status != "published":
            raise FileNotFoundError(f"RH Discover issue is not published: {issue_id}")
        return report

    raise FileNotFoundError(f"RH Discover issue not found: {issue_id}")


def load_latest_discover_report(
    issue_dir: str | Path | None = None,
    *,
    cadence: str | None = "weekly",
    include_drafts: bool = False,
) -> DiscoverReport:
    """Load the newest published issue, optionally scoped by cadence."""

    issues = list_discover_issues(
        issue_dir,
        cadence=cadence,
        include_drafts=include_drafts,
    )
    if not issues:
        raise FileNotFoundError("no RH Discover issues found")
    return load_discover_issue(
        issues[0].issue_id,
        issue_dir,
        include_drafts=include_drafts,
    )


def summary_from_report(
    report: DiscoverReport, *, path: str | Path | None = None
) -> DiscoverIssueSummary:
    payload = report.to_dict()
    return DiscoverIssueSummary(
        issue_id=payload["issue_id"],
        title=payload["title"],
        subtitle=payload["subtitle"],
        generated_at=payload["generated_at"],
        cadence=payload["cadence"],
        status=payload["status"],
        brief_count=payload["brief_count"],
        path=str(path or ""),
    )


def _brief_from_dict(payload: dict[str, Any]):
    signals = [_signal_from_dict(raw) for raw in payload.get("signals", [])]
    seed_papers = [_seed_paper_from_dict(raw) for raw in payload.get("seed_papers", [])]
    handoff = payload.get("rh_handoff") or {}
    trend = payload.get("trend_context") or {}
    fit = payload.get("fit_score") or {}
    readiness = payload.get("readiness") or None

    return build_opportunity_brief(
        title=str(payload.get("title") or ""),
        summary=str(payload.get("summary") or ""),
        why_now=str(payload.get("why_now") or ""),
        signals=signals,
        seed_papers=seed_papers,
        trend_context=TrendContext(
            window=trend.get("window", "7d"),
            growth_summary=str(trend.get("growth_summary") or ""),
            saturation=trend.get("saturation", "medium"),
        ),
        fit_score=FitScore(
            trend=float(fit.get("trend", 0.0)),
            novelty=float(fit.get("novelty", 0.0)),
            feasibility=float(fit.get("feasibility", 0.0)),
            user_fit=float(fit.get("user_fit", 0.0)),
            risk=float(fit.get("risk", 0.0)),
        ),
        goal_previews=[
            _goal_preview_from_dict(raw)
            for raw in payload.get("goal_previews", [])
            if isinstance(raw, dict)
        ],
        readiness=(
            OpportunityReadiness(
                evidence=float(readiness.get("evidence", 0.0)),
                novelty=float(readiness.get("novelty", 0.0)),
                feasibility=float(readiness.get("feasibility", 0.0)),
                goalability=float(readiness.get("goalability", 0.0)),
                handoff_readiness=float(readiness.get("handoff_readiness", 0.0)),
            )
            if isinstance(readiness, dict)
            else None
        ),
        risks=[str(item) for item in payload.get("risks", [])],
        recommended_next_steps=[
            str(item) for item in payload.get("recommended_next_steps", [])
        ],
        initial_queries=[str(item) for item in handoff.get("initial_queries", [])],
        topic_name=handoff.get("topic_name"),
        suggested_primitives=handoff.get("suggested_primitives"),
    )


def _goal_preview_from_dict(payload: dict[str, Any]) -> GoalPreview:
    return GoalPreview(
        id=str(payload.get("id") or ""),
        title=str(payload.get("title") or ""),
        dataset=payload.get("dataset"),
        baseline=payload.get("baseline"),
        metric_name=payload.get("metric_name"),
        target_metric_delta=payload.get("target_metric_delta"),
        time_window_days=payload.get("time_window_days"),
        compute_need=payload.get("compute_need", "medium"),  # type: ignore[arg-type]
        feasibility=float(payload.get("feasibility", 0.0)),
        evidence_strength=float(payload.get("evidence_strength", 0.0)),
        risk=float(payload.get("risk", 0.0)),
        first_steps=[str(item) for item in payload.get("first_steps", [])],
    )


def _signal_from_dict(payload: dict[str, Any]) -> DiscoverSignal:
    return DiscoverSignal(
        type=payload.get("type", "news"),  # type: ignore[arg-type]
        title=str(payload.get("title") or ""),
        url=str(payload.get("url") or ""),
        published_at=str(payload.get("published_at") or ""),
        importance=payload.get("importance", "watch"),  # type: ignore[arg-type]
        reason=str(payload.get("reason") or ""),
    )


def _seed_paper_from_dict(payload: dict[str, Any]) -> SeedPaper:
    year = payload.get("year")
    return SeedPaper(
        title=str(payload.get("title") or ""),
        doi=payload.get("doi"),
        arxiv_id=payload.get("arxiv_id"),
        url=str(payload.get("url") or ""),
        year=int(year) if year is not None else None,
    )


def _validate_issue_metadata(*, issue_id: str, cadence: str, status: str) -> None:
    if not issue_id.strip():
        raise ValueError("RH Discover issue_id is required")
    if cadence not in _VALID_CADENCES:
        raise ValueError(f"unsupported RH Discover cadence: {cadence!r}")
    if status not in _VALID_STATUSES:
        raise ValueError(f"unsupported RH Discover status: {status!r}")
