"""Curated sample bank for RH Discover Weekly validation.

These examples are deliberately framed as product/content samples, not live
claims about a specific day. They show the expected quality bar for an
OpportunityBrief before connector automation exists.
"""

from __future__ import annotations

from .models import (
    DiscoverSignal,
    FitScore,
    GoalPreview,
    OpportunityBrief,
    TrendContext,
    build_opportunity_brief,
)


def load_sample_briefs() -> list[OpportunityBrief]:
    """Return three guardrail-complete sample briefs."""

    return [
        build_opportunity_brief(
            title="Evaluate agentic literature-review workflows",
            summary=(
                "Agentic coding and research tools are becoming practical "
                "interfaces for literature search, screening, note synthesis, "
                "and handoff. A publishable direction is to benchmark whether "
                "these workflows improve recall, traceability, and reviewer "
                "trust compared with ordinary search-and-summary baselines."
            ),
            why_now=(
                "Research workflows are moving from one-shot chat prompts to "
                "stateful agents with tools, memory, and provenance; this creates "
                "a new evaluation problem that traditional IR metrics only partly cover."
            ),
            signals=[
                DiscoverSignal(
                    type="product",
                    title="Official AI lab and product-release streams",
                    url="https://openai.com/news/",
                    published_at="",
                    importance="watch",
                    reason=(
                        "Release velocity suggests agentic tooling is becoming a "
                        "research workflow surface, not only a coding surface."
                    ),
                ),
                DiscoverSignal(
                    type="paper",
                    title="OpenReview activity for agent and evaluation papers",
                    url="https://openreview.net/",
                    published_at="",
                    importance="watch",
                    reason=(
                        "Conference-review systems expose emerging evaluation themes "
                        "before they are consolidated into surveys."
                    ),
                ),
            ],
            trend_context=TrendContext(
                window="7d",
                growth_summary="Qualitative momentum across tools, papers, and benchmarks.",
                saturation="medium",
            ),
            fit_score=FitScore(
                trend=0.75,
                novelty=0.68,
                feasibility=0.82,
                user_fit=0.8,
                risk=0.35,
            ),
            risks=[
                "The direction can become a tool demo unless it defines task suites and blinded judging.",
                "Claims need provenance/error analysis, not only end-user preference scores.",
            ],
            goal_previews=[
                GoalPreview(
                    title="Benchmark traceable agentic literature review against keyword search",
                    dataset="Known relevant-paper pools",
                    baseline="Keyword search plus LLM summary",
                    metric_name="recall@50",
                    target_metric_delta=0.08,
                    time_window_days=30,
                    compute_need="low",
                    feasibility=0.82,
                    evidence_strength=0.78,
                    risk=0.35,
                    first_steps=[
                        "Assemble a small pool of known relevant papers for 10 queries.",
                        "Score traceability and recall against a keyword-search baseline.",
                    ],
                )
            ],
            recommended_next_steps=[
                "Search for agentic literature-review, evidence synthesis, and systematic-review automation benchmarks.",
                "Build a small task suite with known relevant-paper pools and traceability rubrics.",
            ],
            initial_queries=[
                "agentic literature review evaluation benchmark",
                "LLM agents systematic review automation provenance",
            ],
        ),
        build_opportunity_brief(
            title="Use open-model adoption signals to forecast research opportunity windows",
            summary=(
                "Model hubs, code releases, and benchmark pages expose weak but fast "
                "signals about which methods are becoming usable. RH Discover can turn "
                "these into research questions about adoption, reproducibility, and "
                "which benchmark gaps appear when models become easy to deploy."
            ),
            why_now=(
                "Open model releases often move faster than peer-reviewed surveys. "
                "Researchers who can translate adoption bursts into rigorous questions "
                "may find feasible directions before a field becomes saturated."
            ),
            signals=[
                DiscoverSignal(
                    type="model",
                    title="Hugging Face model and paper trends",
                    url="https://huggingface.co/papers/trending",
                    published_at="",
                    importance="watch",
                    reason=(
                        "Trending models and papers provide early adoption signals "
                        "that can be cross-checked against formal literature."
                    ),
                ),
                DiscoverSignal(
                    type="repo",
                    title="GitHub Trending",
                    url="https://github.com/trending",
                    published_at="",
                    importance="horizon",
                    reason=(
                        "Repository momentum can reveal implementation bottlenecks "
                        "and benchmark demand before citation counts catch up."
                    ),
                ),
            ],
            trend_context=TrendContext(
                window="7d",
                growth_summary="Fast-moving repository/model signals; slower paper validation.",
                saturation="medium",
            ),
            fit_score=FitScore(
                trend=0.72,
                novelty=0.62,
                feasibility=0.86,
                user_fit=0.7,
                risk=0.42,
            ),
            risks=[
                "Repository stars and model downloads are popularity signals, not research evidence.",
                "A valid paper must connect adoption signals to measurable scientific gaps.",
            ],
            goal_previews=[
                GoalPreview(
                    title="Forecast benchmark gaps from open-model adoption bursts",
                    dataset="Model hub trends and benchmark coverage snapshots",
                    baseline="Paper-volume trend heuristic",
                    metric_name="gap prediction precision@10",
                    target_metric_delta=0.1,
                    time_window_days=45,
                    compute_need="low",
                    feasibility=0.76,
                    evidence_strength=0.7,
                    risk=0.42,
                    first_steps=[
                        "Collect 20 open-model releases with hub and repository signals.",
                        "Label whether a benchmark or reproducibility gap appeared within 3 months.",
                    ],
                )
            ],
            recommended_next_steps=[
                "Compare hub/repo momentum against paper volume, benchmark availability, and reported limitations.",
                "Define a small forecasting task: which adoption bursts become paper-worthy gaps within 3-6 months?",
            ],
            initial_queries=[
                "open source model adoption benchmark reproducibility",
                "software repository signals research trend forecasting",
            ],
        ),
        build_opportunity_brief(
            title="Mine Chinese big-tech releases for thesis-scale AI systems questions",
            summary=(
                "Chinese cloud and AI product channels often publish systems, platform, "
                "and application signals that are underrepresented in English-first "
                "research feeds. A useful RH Discover lane is to convert these releases "
                "into thesis-scale questions with public-paper triangulation."
            ),
            why_now=(
                "Students and early-stage researchers need directions that are concrete "
                "enough to execute. Product-release signals can reveal real deployment "
                "constraints, but they need translation into falsifiable research tasks."
            ),
            signals=[
                DiscoverSignal(
                    type="blog",
                    title="Alibaba Cloud Blog",
                    url="https://www.alibabacloud.com/blog",
                    published_at="",
                    importance="watch",
                    reason=(
                        "Cloud/product writing can reveal deployment pain points and "
                        "systems requirements that papers may not emphasize."
                    ),
                ),
                DiscoverSignal(
                    type="blog",
                    title="Baidu Research",
                    url="https://research.baidu.com/",
                    published_at="",
                    importance="horizon",
                    reason=(
                        "Chinese AI lab channels are useful weak signals when verified "
                        "against papers and official technical pages."
                    ),
                ),
            ],
            trend_context=TrendContext(
                window="7d",
                growth_summary="Manual watchlist signal; requires primary-source verification.",
                saturation="low",
            ),
            fit_score=FitScore(
                trend=0.64,
                novelty=0.74,
                feasibility=0.7,
                user_fit=0.76,
                risk=0.5,
            ),
            risks=[
                "Chinese-language product posts may be marketing-oriented; require paper and benchmark triangulation.",
                "Some promising product constraints may lack open data, limiting thesis feasibility.",
            ],
            goal_previews=[
                GoalPreview(
                    title="Extract thesis-scale systems questions from Chinese AI product releases",
                    dataset="Curated Chinese cloud and AI release corpus",
                    baseline="Manual paper-only topic scouting",
                    metric_name="validated topic yield",
                    target_metric_delta=0.15,
                    time_window_days=30,
                    compute_need="low",
                    feasibility=0.72,
                    evidence_strength=0.66,
                    risk=0.5,
                    first_steps=[
                        "Select 30 primary-source release notes and extract technical constraints.",
                        "Triangulate each constraint with papers, datasets, and benchmark availability.",
                    ],
                )
            ],
            recommended_next_steps=[
                "Extract one technical constraint from each product signal and map it to papers, datasets, and baselines.",
                "Classify the direction as thesis, workshop, or industry-track before starting a full RH topic.",
            ],
            initial_queries=[
                "Chinese AI cloud systems research deployment benchmark",
                "AI product release technical constraints research opportunities",
            ],
        ),
    ]
