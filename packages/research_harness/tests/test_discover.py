"""RH Discover contract tests.

These tests lock the first implementation slice for RH Discover:
an OpportunityBrief contract, a non-paper source registry, and a local CLI
surface that can emit a machine-readable brief without touching RH Core state.
"""

from __future__ import annotations

import json

import pytest

from research_harness.cli import main


def test_opportunity_brief_contract_and_markdown_roundtrip():
    from research_harness.discover import (
        DiscoverSignal,
        SeedPaper,
        build_opportunity_brief,
        render_opportunity_brief_markdown,
    )

    brief = build_opportunity_brief(
        title="Evaluate agentic literature-review copilots",
        summary="A concrete direction for comparing agentic paper workflows.",
        why_now="Agentic coding tools are becoming research workflow surfaces.",
        signals=[
            DiscoverSignal(
                type="blog",
                title="New research-agent product release",
                url="https://example.com/research-agent",
                published_at="2026-05-10",
                importance="act_now",
                reason="Shows product pull outside pure paper search.",
            )
        ],
        seed_papers=[
            SeedPaper(
                title="Agents for literature review",
                year=2026,
                url="https://example.com/paper",
            )
        ],
        initial_queries=["agentic literature review evaluation"],
        recommended_next_steps=["Run a scoped literature search."],
    )

    payload = brief.to_dict()

    assert payload["title"] == "Evaluate agentic literature-review copilots"
    assert payload["signals"][0]["importance"] == "act_now"
    assert payload["fit_score"] == {
        "trend": 0.0,
        "novelty": 0.0,
        "feasibility": 0.0,
        "user_fit": 0.0,
        "risk": 0.0,
    }
    assert payload["rh_handoff"]["topic_name"] == (
        "evaluate-agentic-literature-review-copilots"
    )
    assert payload["rh_handoff"]["initial_queries"] == [
        "agentic literature review evaluation"
    ]
    assert payload["rh_handoff"]["suggested_primitives"] == [
        "paper_search",
        "paper_ingest",
        "gap_detect",
    ]

    markdown = render_opportunity_brief_markdown(brief)
    assert "# Evaluate agentic literature-review copilots" in markdown
    assert "## RH Handoff" in markdown
    assert "agentic literature review evaluation" in markdown


def test_opportunity_brief_rejects_news_only_items():
    from research_harness.discover import DiscoverSignal, build_opportunity_brief

    with pytest.raises(ValueError, match="research opportunity"):
        build_opportunity_brief(
            title="A generic launch",
            summary="Only reports a launch.",
            why_now="It happened today.",
            signals=[
                DiscoverSignal(
                    type="news",
                    title="Launch item",
                    url="https://example.com/news",
                    published_at="2026-05-10",
                    importance="watch",
                    reason="Interesting but no research angle.",
                )
            ],
            initial_queries=[],
            recommended_next_steps=[],
        )


def test_opportunity_brief_rejects_invalid_scoring_and_windows():
    from research_harness.discover import FitScore, TrendContext

    with pytest.raises(ValueError, match="trend window"):
        TrendContext(window="30d")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="fit_score.trend"):
        FitScore(trend=1.2)


def test_opportunity_brief_normalizes_handoff_inputs():
    from research_harness.discover import DiscoverSignal, build_opportunity_brief

    brief = build_opportunity_brief(
        title="  Evaluate agentic workflows  ",
        summary="A concrete direction.",
        why_now="The workflow is becoming measurable.",
        signals=[
            DiscoverSignal(
                type="paper",
                title="Seed signal",
                url="https://example.com/paper",
            )
        ],
        initial_queries=["  agentic workflow evaluation  ", ""],
        recommended_next_steps=["  Compare against search baselines.  ", ""],
        topic_name="  custom-topic  ",
        suggested_primitives=[" paper_search ", "gap_detect"],
    )

    payload = brief.to_dict()
    assert payload["title"] == "Evaluate agentic workflows"
    assert payload["recommended_next_steps"] == ["Compare against search baselines."]
    assert payload["rh_handoff"] == {
        "topic_name": "custom-topic",
        "initial_queries": ["agentic workflow evaluation"],
        "suggested_primitives": ["paper_search", "gap_detect"],
    }


def test_goal_preview_and_readiness_are_part_of_1_0_contract():
    from research_harness.discover import (
        DiscoverSignal,
        GoalPreview,
        OpportunityReadiness,
        build_opportunity_brief,
    )

    brief = build_opportunity_brief(
        title="Evaluate agentic workflows",
        summary="Compare agentic workflows against ordinary search baselines.",
        why_now="The tooling is now mature enough to benchmark.",
        signals=[
            DiscoverSignal(
                type="paper",
                title="Seed signal",
                url="https://example.com/paper",
            )
        ],
        goal_previews=[
            GoalPreview(
                title="Improve recall over keyword search on known-paper pools",
                dataset="Known relevant-paper pools",
                baseline="Keyword search plus LLM summary",
                metric_name="recall@50",
                target_metric_delta=0.08,
                time_window_days=30,
                compute_need="low",
                feasibility=0.82,
                evidence_strength=0.75,
                risk=0.34,
                first_steps=[
                    "Assemble 10 seed queries with known relevant papers.",
                    "Compare traceable agent search against keyword retrieval.",
                ],
            )
        ],
        initial_queries=["agentic workflow evaluation"],
        recommended_next_steps=["Compare against search baselines."],
    )

    payload = brief.to_dict()

    assert payload["goal_previews"][0]["compute_need"] == "low"
    assert payload["goal_previews"][0]["metric_name"] == "recall@50"
    assert payload["readiness"]["goalability"] >= 0.8
    assert payload["readiness"]["handoff_readiness"] >= 0.8

    explicit = OpportunityReadiness(
        evidence=0.5,
        novelty=0.6,
        feasibility=0.7,
        goalability=0.8,
        handoff_readiness=0.9,
    )
    assert explicit.to_dict()["handoff_readiness"] == 0.9


def test_goal_preview_rejects_invalid_compute_need_and_scores():
    from research_harness.discover import GoalPreview, OpportunityReadiness

    with pytest.raises(ValueError, match="compute_need"):
        GoalPreview(
            title="Invalid compute",
            compute_need="cluster",  # type: ignore[arg-type]
            feasibility=0.5,
            evidence_strength=0.5,
            risk=0.5,
            first_steps=["Scope the task."],
        )

    with pytest.raises(ValueError, match="readiness.goalability"):
        OpportunityReadiness(goalability=1.2)


def test_source_registry_covers_required_rh_discover_signal_families():
    from research_harness.discover import list_source_definitions

    sources = list_source_definitions()
    families = {source.family for source in sources}
    usages = {source.usage for source in sources}

    assert {"papers", "blogs", "product", "repos_models", "social"} <= families
    assert any(source.region == "cn" for source in sources)
    assert all(source.usage in {"connector", "sidecar", "manual"} for source in sources)
    assert {"connector", "sidecar", "manual"} <= usages


def test_discover_schema_contains_handoff_contract():
    from research_harness.discover import opportunity_brief_schema

    schema = opportunity_brief_schema()
    required = set(schema["required"])

    assert {"title", "summary", "why_now", "signals", "rh_handoff"} <= required
    assert {"goal_previews", "readiness"} <= required
    assert schema["properties"]["goal_previews"]["items"]["required"] == [
        "title",
        "dataset",
        "baseline",
        "metric_name",
        "target_metric_delta",
        "time_window_days",
        "compute_need",
        "feasibility",
        "evidence_strength",
        "risk",
        "first_steps",
    ]
    assert set(schema["properties"]["readiness"]["required"]) == {
        "evidence",
        "novelty",
        "feasibility",
        "goalability",
        "handoff_readiness",
    }
    assert schema["properties"]["rh_handoff"]["required"] == [
        "topic_name",
        "initial_queries",
        "suggested_primitives",
    ]


def test_cli_discover_brief_json_contract(runner):
    result = runner.invoke(
        main,
        [
            "--json",
            "discover",
            "brief",
            "--title",
            "Evaluate agentic literature-review copilots",
            "--summary",
            "A direction for comparing agentic paper workflows.",
            "--why-now",
            "Agentic coding tools are becoming research workflow surfaces.",
            "--signal",
            "blog|New research-agent product release|https://example.com/research-agent|act_now|Shows product pull outside pure paper search.",
            "--seed-paper",
            "Agents for literature review|2026|https://example.com/paper",
            "--query",
            "agentic literature review evaluation",
            "--next-step",
            "Run a scoped literature search.",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["title"] == "Evaluate agentic literature-review copilots"
    assert payload["signals"][0]["type"] == "blog"
    assert payload["seed_papers"][0]["year"] == 2026
    assert payload["rh_handoff"]["topic_name"] == (
        "evaluate-agentic-literature-review-copilots"
    )


def test_cli_discover_sources_text_lists_seed_sources(runner):
    result = runner.invoke(main, ["discover", "sources"])

    assert result.exit_code == 0, result.output
    assert "papers" in result.output
    assert "repos_models" in result.output


def test_sample_bank_has_three_guardrail_complete_briefs():
    from research_harness.discover import load_sample_briefs

    briefs = load_sample_briefs()

    assert len(briefs) >= 3
    for brief in briefs:
        payload = brief.to_dict()
        assert payload["why_now"]
        assert payload["signals"]
        assert payload["recommended_next_steps"]
        assert payload["rh_handoff"]["initial_queries"]


def test_weekly_report_renders_markdown_html_and_json():
    from research_harness.discover import (
        build_sample_weekly_report,
        render_discover_report_html,
        render_discover_report_markdown,
    )

    report = build_sample_weekly_report(generated_at="2026-05-10")

    payload = report.to_dict()
    markdown = render_discover_report_markdown(report)
    html = render_discover_report_html(report)

    assert payload["product"] == "RH Discover"
    assert len(payload["briefs"]) >= 3
    assert "What happened?" in markdown
    assert "Why does it matter now?" in markdown
    assert "How can it be handed off to RH?" in markdown
    assert "<html" in html
    assert "OpportunityBrief JSON" in html


def test_published_discover_issue_requires_explicit_goal_previews():
    from research_harness.discover import (
        discover_report_from_dict,
        load_latest_discover_report,
    )

    report = load_latest_discover_report(cadence="weekly")
    payload = report.to_dict()

    assert payload["status"] == "published"
    assert all(brief["goal_previews"] for brief in payload["briefs"])
    assert all(brief["readiness"]["goalability"] > 0 for brief in payload["briefs"])

    with pytest.raises(ValueError, match="published RH Discover issue"):
        discover_report_from_dict(
            {
                "issue_id": "missing-goal-preview",
                "cadence": "weekly",
                "status": "published",
                "briefs": [
                    {
                        "title": "A plausible direction",
                        "summary": "A summary.",
                        "why_now": "Now is the moment.",
                        "signals": [
                            {
                                "type": "paper",
                                "title": "Signal",
                                "url": "https://example.com",
                                "published_at": "2026-05-01",
                                "importance": "watch",
                                "reason": "Evidence.",
                            }
                        ],
                        "recommended_next_steps": ["Search papers."],
                        "rh_handoff": {
                            "topic_name": "plausible-direction",
                            "initial_queries": ["plausible direction"],
                            "suggested_primitives": ["paper_search"],
                        },
                    }
                ],
            }
        )


def test_published_discover_issue_enforces_editorial_evidence_checklist():
    from research_harness.discover import discover_report_from_dict

    payload = _issue_payload("single-signal-weekly")
    payload["briefs"][0]["signals"] = payload["briefs"][0]["signals"][:1]

    with pytest.raises(ValueError, match="at least 2 evidence signals"):
        discover_report_from_dict(payload)


def test_repository_has_sanitized_demo_published_discover_issue():
    from research_harness.discover import list_discover_issues, load_discover_issue

    issues = list_discover_issues(cadence="weekly")

    assert len(issues) >= 1
    assert any(issue.issue_id == "demo-weekly" for issue in issues)
    for issue in issues:
        report = load_discover_issue(issue.issue_id)
        payload = report.to_dict()
        assert payload["status"] == "published"
        for brief in payload["briefs"]:
            assert len(brief["signals"]) >= 2
            assert brief["goal_previews"]
            assert brief["risks"]
            assert brief["recommended_next_steps"]
            assert brief["rh_handoff"]["initial_queries"]
            assert "Synthetic" in brief["title"]


def test_cli_discover_weekly_json_and_file_output(runner, tmp_path):
    json_result = runner.invoke(
        main,
        [
            "--json",
            "discover",
            "weekly",
            "--sample",
            "--generated-at",
            "2026-05-10",
        ],
    )

    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_result.output)
    assert payload["product"] == "RH Discover"
    assert len(payload["briefs"]) >= 3

    output = tmp_path / "weekly.html"
    html_result = runner.invoke(
        main,
        [
            "discover",
            "weekly",
            "--sample",
            "--format",
            "html",
            "--output",
            str(output),
        ],
    )

    assert html_result.exit_code == 0, html_result.output
    assert output.exists()
    assert "RH Discover Weekly" in output.read_text()


def _issue_payload(issue_id: str = "2026-05-10-weekly") -> dict:
    return {
        "issue_id": issue_id,
        "cadence": "weekly",
        "status": "published",
        "product": "RH Discover",
        "title": "RH Discover Weekly · 2026-05-10",
        "subtitle": "Signals worth turning into research directions.",
        "generated_at": "2026-05-10",
        "briefs": [
            {
                "title": "Evaluate agentic literature-review workflows",
                "summary": "Agentic research tools are becoming practical literature-review interfaces.",
                "why_now": "Stateful agents with tools and provenance create a new evaluation problem.",
                "signals": [
                    {
                        "type": "product",
                        "title": "Official AI lab release stream",
                        "url": "https://example.com/news",
                        "published_at": "2026-05-10",
                        "importance": "watch",
                        "reason": "Shows product pull outside pure paper search.",
                    },
                    {
                        "type": "paper",
                        "title": "A benchmark seed paper",
                        "url": "https://example.com/paper",
                        "published_at": "2026-05-09",
                        "importance": "watch",
                        "reason": "Provides a second evidence signal for publication.",
                    },
                ],
                "trend_context": {
                    "window": "7d",
                    "growth_summary": "Qualitative momentum across tools and benchmarks.",
                    "saturation": "medium",
                },
                "seed_papers": [
                    {
                        "title": "A seed paper",
                        "doi": "10.1145/1234567.1234568",
                        "arxiv_id": None,
                        "url": "https://example.com/paper",
                        "year": 2026,
                    }
                ],
                "fit_score": {
                    "trend": 0.75,
                    "novelty": 0.68,
                    "feasibility": 0.82,
                    "user_fit": 0.8,
                    "risk": 0.35,
                },
                "goal_previews": [
                    {
                        "id": "traceability-benchmark",
                        "title": "Build a small traceability benchmark",
                        "dataset": "Known relevant-paper pools",
                        "baseline": "Keyword search plus LLM summary",
                        "metric_name": "recall@50",
                        "target_metric_delta": 0.08,
                        "time_window_days": 30,
                        "compute_need": "low",
                        "feasibility": 0.82,
                        "evidence_strength": 0.75,
                        "risk": 0.35,
                        "first_steps": ["Build a small traceability benchmark."],
                        "goalability": 1.0,
                    }
                ],
                "readiness": {
                    "evidence": 0.5,
                    "novelty": 0.68,
                    "feasibility": 0.82,
                    "goalability": 1.0,
                    "handoff_readiness": 1.0,
                },
                "risks": ["Can become a tool demo without blinded judging."],
                "recommended_next_steps": ["Build a small traceability benchmark."],
                "rh_handoff": {
                    "topic_name": "evaluate-agentic-literature-review-workflows",
                    "initial_queries": [
                        "agentic literature review evaluation benchmark"
                    ],
                    "suggested_primitives": [
                        "paper_search",
                        "paper_ingest",
                        "gap_detect",
                    ],
                },
            }
        ],
    }


def test_discover_issue_file_load_list_and_latest(tmp_path):
    from research_harness.discover import (
        list_discover_issues,
        load_discover_issue,
        load_discover_report_from_file,
        load_latest_discover_report,
    )

    issue_dir = tmp_path / "issues"
    issue_dir.mkdir()
    first = issue_dir / "2026-05-10-weekly.json"
    second = issue_dir / "2026-05-17-weekly.json"
    first.write_text(json.dumps(_issue_payload("2026-05-10-weekly")))
    newer_payload = _issue_payload("2026-05-17-weekly")
    newer_payload["generated_at"] = "2026-05-17"
    second.write_text(json.dumps(newer_payload))

    report = load_discover_report_from_file(first)
    summaries = list_discover_issues(issue_dir)
    latest = load_latest_discover_report(issue_dir)
    selected = load_discover_issue("2026-05-10-weekly", issue_dir)

    assert report.to_dict()["issue_id"] == "2026-05-10-weekly"
    assert summaries[0].issue_id == "2026-05-17-weekly"
    assert summaries[0].brief_count == 1
    assert latest.issue_id == "2026-05-17-weekly"
    assert selected.generated_at == "2026-05-10"


def test_discover_issue_archive_hides_drafts_by_default(tmp_path):
    from research_harness.discover import list_discover_issues

    issue_dir = tmp_path / "issues"
    issue_dir.mkdir()
    published = _issue_payload("published-weekly")
    draft = _issue_payload("draft-weekly")
    draft["status"] = "draft"
    (issue_dir / "published-weekly.json").write_text(json.dumps(published))
    (issue_dir / "draft-weekly.json").write_text(json.dumps(draft))

    assert [item.issue_id for item in list_discover_issues(issue_dir)] == [
        "published-weekly"
    ]
    assert {
        item.issue_id for item in list_discover_issues(issue_dir, include_drafts=True)
    } == {
        "published-weekly",
        "draft-weekly",
    }


def test_cli_discover_issues_validate_and_latest_weekly(runner, tmp_path):
    issue_dir = tmp_path / "issues"
    issue_dir.mkdir()
    issue_file = issue_dir / "2026-05-10-weekly.json"
    issue_file.write_text(json.dumps(_issue_payload("2026-05-10-weekly")))

    list_result = runner.invoke(
        main,
        ["--json", "discover", "issues", "--issue-dir", str(issue_dir)],
    )
    assert list_result.exit_code == 0, list_result.output
    issues = json.loads(list_result.output)
    assert issues[0]["issue_id"] == "2026-05-10-weekly"
    assert issues[0]["brief_count"] == 1

    validate_result = runner.invoke(main, ["discover", "validate", str(issue_file)])
    assert validate_result.exit_code == 0, validate_result.output
    assert "Valid RH Discover issue 2026-05-10-weekly" in validate_result.output

    weekly_result = runner.invoke(
        main,
        [
            "discover",
            "weekly",
            "--no-sample",
            "--issue-dir",
            str(issue_dir),
            "--format",
            "json",
        ],
    )
    assert weekly_result.exit_code == 0, weekly_result.output
    payload = json.loads(weekly_result.output)
    assert payload["issue_id"] == "2026-05-10-weekly"
    assert payload["briefs"][0]["rh_handoff"]["topic_name"] == (
        "evaluate-agentic-literature-review-workflows"
    )
