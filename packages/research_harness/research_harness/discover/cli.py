"""Click commands for the RH Discover incubation surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from .models import (
    DiscoverSignal,
    SeedPaper,
    build_opportunity_brief,
    render_opportunity_brief_markdown,
)
from .report import (
    build_sample_weekly_report,
    render_discover_report_html,
    render_discover_report_markdown,
)
from .issues import (
    list_discover_issues,
    load_discover_report_from_file,
    load_latest_discover_report,
    summary_from_report,
)
from .schema import opportunity_brief_schema
from .sources import SourceFamily, list_source_definitions
from .evidence import (
    collect_discovery_evidence,
    default_evidence_problem_specs,
    load_evidence_manifest,
    provider_plan,
    validate_evidence_manifest,
    write_evidence_manifest,
)
from ..storage.db import Database


def _emit(ctx: click.Context, payload: object, text: str | None = None) -> None:
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        return
    if text is not None:
        click.echo(text)
        return
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _parse_signal(raw: str) -> DiscoverSignal:
    """Parse ``type|title|url|importance|reason``."""

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) != 5:
        raise click.ClickException(
            "--signal must be `type|title|url|importance|reason`"
        )
    signal_type, title, url, importance, reason = parts
    return DiscoverSignal(
        type=signal_type,  # type: ignore[arg-type]
        title=title,
        url=url,
        importance=importance,  # type: ignore[arg-type]
        reason=reason,
    )


def _parse_seed_paper(raw: str) -> SeedPaper:
    """Parse ``title|year|url`` with optional ``|arxiv_id|doi`` suffix."""

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) not in (3, 4, 5):
        raise click.ClickException(
            "--seed-paper must be `title|year|url` or `title|year|url|arxiv_id|doi`"
        )
    title, raw_year, url = parts[:3]
    try:
        year = int(raw_year) if raw_year else None
    except ValueError as exc:
        raise click.ClickException(f"invalid seed-paper year: {raw_year!r}") from exc
    arxiv_id = parts[3] if len(parts) >= 4 and parts[3] else None
    doi = parts[4] if len(parts) >= 5 and parts[4] else None
    return SeedPaper(title=title, year=year, url=url, arxiv_id=arxiv_id, doi=doi)


@click.group("discover")
def discover_group() -> None:
    """RH Discover signal-to-direction incubation tools."""


@discover_group.command("schema")
@click.pass_context
def discover_schema(ctx: click.Context) -> None:
    """Print the OpportunityBrief JSON schema."""

    _emit(ctx, opportunity_brief_schema())


@discover_group.command("sources")
@click.option(
    "--family",
    "family",
    type=click.Choice(["papers", "blogs", "product", "repos_models", "social"]),
    default=None,
    help="Filter by source family.",
)
@click.pass_context
def discover_sources(ctx: click.Context, family: SourceFamily | None) -> None:
    """List seed source definitions for RH Discover."""

    sources = list_source_definitions(family=family)
    payload = [source.to_dict() for source in sources]
    if ctx.obj.get("json"):
        _emit(ctx, payload)
        return
    lines = [
        f"{source.family:12} {source.region:6} {source.usage:9} "
        f"{source.id}: {source.name}"
        for source in sources
    ]
    _emit(ctx, payload, "\n".join(lines))


@discover_group.command("brief")
@click.option("--title", required=True, help="Candidate research direction title.")
@click.option("--summary", required=True, help="Short explanation of the opportunity.")
@click.option("--why-now", required=True, help="Why this direction matters now.")
@click.option(
    "--signal",
    "signals",
    multiple=True,
    required=True,
    help="Signal as `type|title|url|importance|reason`.",
)
@click.option(
    "--seed-paper",
    "seed_papers",
    multiple=True,
    help="Seed paper as `title|year|url` or `title|year|url|arxiv_id|doi`.",
)
@click.option(
    "--query",
    "queries",
    multiple=True,
    required=True,
    help="Initial RH Core search query.",
)
@click.option(
    "--next-step",
    "next_steps",
    multiple=True,
    required=True,
    help="Recommended next research action.",
)
@click.option("--risk", "risks", multiple=True, help="Known risk or caveat.")
@click.option("--topic-name", default=None, help="Override RH topic slug.")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write Markdown or JSON to a file.",
)
@click.pass_context
def discover_brief(
    ctx: click.Context,
    title: str,
    summary: str,
    why_now: str,
    signals: tuple[str, ...],
    seed_papers: tuple[str, ...],
    queries: tuple[str, ...],
    next_steps: tuple[str, ...],
    risks: tuple[str, ...],
    topic_name: str | None,
    output: Path | None,
) -> None:
    """Build an OpportunityBrief from curated/manual signals."""

    brief = build_opportunity_brief(
        title=title,
        summary=summary,
        why_now=why_now,
        signals=[_parse_signal(signal) for signal in signals],
        seed_papers=[_parse_seed_paper(paper) for paper in seed_papers],
        initial_queries=list(queries),
        recommended_next_steps=list(next_steps),
        risks=list(risks),
        topic_name=topic_name,
    )
    payload: dict[str, Any] = brief.to_dict()
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if ctx.obj.get("json")
        else render_opportunity_brief_markdown(brief)
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        if not ctx.obj.get("json"):
            click.echo(f"Wrote OpportunityBrief to {output}")
        return
    if ctx.obj.get("json"):
        click.echo(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        click.echo(content)


@discover_group.command("weekly")
@click.option(
    "--sample/--no-sample",
    default=True,
    show_default=True,
    help="Use bundled sample OpportunityBriefs. Live connectors are not enabled yet.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "html", "json"]),
    default="markdown",
    show_default=True,
)
@click.option("--title", default="RH Discover Weekly", show_default=True)
@click.option(
    "--subtitle",
    default=(
        "Research and technology signals converted into actionable research opportunities."
    ),
    show_default=True,
)
@click.option(
    "--generated-at",
    default=None,
    help="Override generated date, e.g. 2026-05-10.",
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write report to a file.",
)
@click.option(
    "--input",
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load a curated Discover issue JSON file instead of the sample report.",
)
@click.option(
    "--issue-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory of curated Discover issue JSON files for --no-sample latest mode.",
)
@click.option(
    "--include-drafts",
    is_flag=True,
    help="Allow draft issues when loading the latest file-backed report.",
)
@click.pass_context
def discover_weekly(
    ctx: click.Context,
    sample: bool,
    output_format: str,
    title: str,
    subtitle: str,
    generated_at: str | None,
    output: Path | None,
    input_path: Path | None,
    issue_dir: Path | None,
    include_drafts: bool,
) -> None:
    """Generate a complete RH Discover Weekly report."""

    if input_path is not None:
        report = load_discover_report_from_file(input_path)
    elif sample:
        report = build_sample_weekly_report(
            title=title,
            subtitle=subtitle,
            generated_at=generated_at,
        )
    else:
        try:
            report = load_latest_discover_report(
                issue_dir,
                cadence="weekly",
                include_drafts=include_drafts,
            )
        except FileNotFoundError as exc:
            raise click.ClickException(
                "no curated weekly issue found; use --sample or --input PATH"
            ) from exc
        if generated_at is not None:
            raise click.ClickException(
                "--generated-at is only supported for --sample reports"
            )
        if title != "RH Discover Weekly" or subtitle != (
            "Research and technology signals converted into actionable research opportunities."
        ):
            raise click.ClickException(
                "--title/--subtitle are only supported for --sample reports"
            )

    payload = report.to_dict()
    if ctx.obj.get("json") or output_format == "json":
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    elif output_format == "html":
        content = render_discover_report_html(report)
    else:
        content = render_discover_report_markdown(report)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        if not ctx.obj.get("json"):
            click.echo(f"Wrote RH Discover Weekly to {output}")
        return
    click.echo(content)


@discover_group.command("issues")
@click.option(
    "--issue-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory of curated Discover issue JSON files.",
)
@click.option(
    "--cadence",
    type=click.Choice(["daily", "weekly", "special"]),
    default=None,
    help="Filter by issue cadence.",
)
@click.option("--include-drafts", is_flag=True, help="Show draft issues too.")
@click.pass_context
def discover_issues(
    ctx: click.Context,
    issue_dir: Path | None,
    cadence: str | None,
    include_drafts: bool,
) -> None:
    """List file-backed RH Discover issues."""

    issues = list_discover_issues(
        issue_dir,
        cadence=cadence,
        include_drafts=include_drafts,
    )
    payload = [issue.to_dict(include_path=ctx.obj.get("json")) for issue in issues]
    if ctx.obj.get("json"):
        _emit(ctx, payload)
        return
    if not issues:
        click.echo("No RH Discover issues found.")
        return
    lines = [
        f"{issue.generated_at} {issue.cadence:7} {issue.status:9} "
        f"{issue.issue_id}: {issue.title} ({issue.brief_count} briefs)"
        for issue in issues
    ]
    click.echo("\n".join(lines))


@discover_group.command("validate")
@click.argument(
    "issue_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.pass_context
def discover_validate(ctx: click.Context, issue_file: Path) -> None:
    """Validate one curated RH Discover issue JSON file."""

    report = load_discover_report_from_file(issue_file)
    summary = summary_from_report(report, path=issue_file)
    payload = summary.to_dict(include_path=True)
    _emit(
        ctx,
        payload,
        (
            f"Valid RH Discover issue {summary.issue_id}: "
            f"{summary.brief_count} briefs, {summary.cadence}, {summary.status}"
        ),
    )


@discover_group.group("evidence")
def discover_evidence() -> None:
    """Collect and validate hundred-scale evidence for Discovery problems."""


@discover_evidence.command("plan")
@click.option("--include-pasa", is_flag=True, help="Include PASA in provider plan.")
@click.pass_context
def discover_evidence_plan(ctx: click.Context, include_pasa: bool) -> None:
    """Print the 10-problem evidence collection plan."""

    specs = default_evidence_problem_specs()
    payload = {
        "schema_version": "discovery-evidence-plan/v1",
        "problem_count": len(specs),
        "min_per_problem": 100,
        "freshness": "year_from defaults to current_year - 1",
        "provider_plan": provider_plan(include_pasa=include_pasa),
        "problems": [spec.to_dict() for spec in specs],
    }
    if ctx.obj.get("json"):
        _emit(ctx, payload)
        return
    lines = [
        "Discovery evidence plan: "
        f"{payload['problem_count']} problems × {payload['min_per_problem']} recent records",
        "Routes: rh_paper_search + provider_fanout",
    ]
    lines.extend(
        f"- {spec.problem_id}: {len(spec.queries)} queries, "
        f"categories={','.join(spec.subject_categories)}"
        for spec in specs
    )
    _emit(ctx, payload, "\n".join(lines))


@discover_evidence.command("collect")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("docs/discover/evidence/latest.json"),
    show_default=True,
    help="Write the evidence manifest JSON here.",
)
@click.option("--min-per-problem", type=int, default=100, show_default=True)
@click.option(
    "--freshness-year-from",
    type=int,
    default=None,
    help="Only collect/validate evidence from this year onward. Defaults to current year - 1.",
)
@click.option(
    "--min-recent-per-problem",
    type=int,
    default=None,
    help="Recent evidence floor. Defaults to --min-per-problem.",
)
@click.option("--per-query-limit", type=int, default=50, show_default=True)
@click.option(
    "--max-queries-per-problem",
    type=int,
    default=None,
    help="Debug throttle. Omit for the full query plan.",
)
@click.option(
    "--route",
    "routes",
    multiple=True,
    type=click.Choice(["rh_paper_search", "provider_fanout"]),
    default=("rh_paper_search", "provider_fanout"),
    show_default=True,
)
@click.option(
    "--include-pasa",
    is_flag=True,
    help="Include PASA fallback. Off by default because it is slower/polling-based.",
)
@click.option(
    "--allow-underfilled",
    is_flag=True,
    help="Write partial manifest even if coverage gates fail.",
)
@click.pass_context
def discover_evidence_collect(
    ctx: click.Context,
    output: Path,
    min_per_problem: int,
    freshness_year_from: int | None,
    min_recent_per_problem: int | None,
    per_query_limit: int,
    max_queries_per_problem: int | None,
    routes: tuple[str, ...],
    include_pasa: bool,
    allow_underfilled: bool,
) -> None:
    """Run multi-route evidence collection and write a manifest."""

    runtime_config = ctx.obj.get("runtime_config")
    db = Database(runtime_config.db_path) if runtime_config else Database()
    db.migrate()
    manifest = collect_discovery_evidence(
        db=db,
        routes=tuple(routes),  # type: ignore[arg-type]
        min_per_problem=min_per_problem,
        freshness_year_from=freshness_year_from,
        min_recent_per_problem=min_recent_per_problem,
        per_query_limit=per_query_limit,
        max_queries_per_problem=max_queries_per_problem,
        include_pasa=include_pasa,
    )
    write_evidence_manifest(manifest, output)
    validation = validate_evidence_manifest(manifest)
    if not validation["ok"] and not allow_underfilled:
        failures = _evidence_validation_failures(validation)
        raise click.ClickException(
            f"Wrote partial manifest to {output}, but coverage failed: "
            + " | ".join(failures)
        )
    payload = {**validation, "output": str(output)}
    _emit(
        ctx,
        payload,
        (
            f"Wrote Discovery evidence manifest to {output}; "
            f"{validation['passed_problem_count']}/{validation['problem_count']} problems passed"
        ),
    )


@discover_evidence.command("validate")
@click.argument(
    "manifest_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.pass_context
def discover_evidence_validate(ctx: click.Context, manifest_file: Path) -> None:
    """Validate a Discovery evidence manifest against coverage gates."""

    manifest = load_evidence_manifest(manifest_file)
    validation = validate_evidence_manifest(manifest)
    if not validation["ok"]:
        failures = _evidence_validation_failures(validation)
        raise click.ClickException(
            "Discovery evidence manifest failed: " + " | ".join(failures)
        )
    _emit(
        ctx,
        validation,
        (
            f"Valid Discovery evidence manifest: "
            f"{validation['passed_problem_count']}/{validation['problem_count']} problems passed"
        ),
    )


def _evidence_validation_failures(validation: dict[str, Any]) -> list[str]:
    failures = [
        f"{item['problem_id']}: {'; '.join(item['errors'])}"
        for item in validation["problems"]
        if item["errors"]
    ]
    failures.extend(
        f"{item.get('problem_id')} {item.get('route')} `{item.get('query')}`: "
        + "; ".join(item.get("provider_errors", []))
        for item in validation.get("route_errors", [])
    )
    return failures or ["unknown coverage failure"]


def register(root: click.Group) -> None:
    """Register RH Discover commands on the main CLI."""

    root.add_command(discover_group)
