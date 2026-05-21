"""RH Discover report rendering.

Reports are the public-facing incubation artifact: they can be published as a
weekly note, saved as HTML, or handed to another agent as JSON.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .models import OpportunityBrief
from .samples import load_sample_briefs


@dataclass(frozen=True)
class DiscoverReport:
    """A collection of OpportunityBriefs ready for publication."""

    issue_id: str = ""
    cadence: str = "weekly"
    status: str = "published"
    title: str = "RH Discover Weekly"
    subtitle: str = "Research and technology signals converted into actionable research opportunities."
    generated_at: str = field(default_factory=lambda: date.today().isoformat())
    briefs: list[OpportunityBrief] = field(default_factory=list)
    product: str = "RH Discover"

    def validate(self) -> None:
        if not self.issue_id.strip():
            raise ValueError("DiscoverReport requires an issue_id")
        if not self.briefs:
            raise ValueError("DiscoverReport requires at least one OpportunityBrief")
        for brief in self.briefs:
            brief.validate()
            if self.status == "published":
                if len(brief.signals) < 2:
                    raise ValueError(
                        "published RH Discover issue requires at least 2 evidence "
                        "signals per opportunity"
                    )
                if not any(signal.type != "news" for signal in brief.signals):
                    raise ValueError(
                        "published RH Discover issue requires at least one "
                        "non-news evidence signal per opportunity"
                    )
                if not brief.goal_previews:
                    raise ValueError(
                        "published RH Discover issue requires explicit goal_previews"
                    )
                if not brief.risks:
                    raise ValueError(
                        "published RH Discover issue requires explicit risks"
                    )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "issue_id": self.issue_id,
            "cadence": self.cadence,
            "status": self.status,
            "product": self.product,
            "title": self.title,
            "subtitle": self.subtitle,
            "generated_at": self.generated_at,
            "brief_count": len(self.briefs),
            "briefs": [brief.to_dict() for brief in self.briefs],
        }


def build_sample_weekly_report(
    *,
    title: str = "RH Discover Weekly",
    subtitle: str = (
        "Research and technology signals converted into actionable research opportunities."
    ),
    generated_at: str | None = None,
) -> DiscoverReport:
    """Build a complete sample weekly report for content validation."""

    resolved_generated_at = generated_at or date.today().isoformat()
    return DiscoverReport(
        issue_id=f"sample-weekly-{resolved_generated_at}",
        cadence="weekly",
        status="published",
        title=title,
        subtitle=subtitle,
        generated_at=resolved_generated_at,
        briefs=load_sample_briefs(),
    )


def render_discover_report_markdown(report: DiscoverReport) -> str:
    """Render a publication-ready Markdown report."""

    payload = report.to_dict()
    lines = [
        f"# {payload['title']}",
        "",
        f"_{payload['subtitle']}_",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Editorial contract",
        "",
        "Every RH Discover opportunity must answer:",
        "",
        "1. What happened?",
        "2. Why does it matter now?",
        "3. What research direction could it become?",
        "4. Who is this direction suitable for?",
        "5. What evidence supports it?",
        "6. What is the first measurable goal?",
        "7. How can it be handed off to RH?",
        "",
        "## Opportunities",
        "",
    ]
    for index, brief in enumerate(payload["briefs"], start=1):
        lines.extend(_brief_markdown_section(index, brief))
    return "\n".join(lines).rstrip() + "\n"


def _brief_markdown_section(index: int, brief: dict[str, Any]) -> list[str]:
    signals = brief["signals"]
    handoff = brief["rh_handoff"]
    fit = brief["fit_score"]
    source_lines = [
        f"- **{signal['type']}**: [{signal['title']}]({signal['url']})"
        f" — {signal['importance']}; {signal['reason']}"
        for signal in signals
    ]
    query_lines = [f"  - `{query}`" for query in handoff["initial_queries"]]
    next_step_lines = [f"- {step}" for step in brief["recommended_next_steps"]]
    risk_lines = [f"- {risk}" for risk in brief["risks"]] or ["- Not assessed yet."]
    goal_lines = [
        f"- **{goal['title']}**: {goal.get('metric_name') or 'metric'}"
        f" on {goal.get('dataset') or 'a scoped dataset'}"
        f" vs {goal.get('baseline') or 'a baseline'}"
        f" ({goal['compute_need']} compute, {goal.get('time_window_days') or 'n/a'} days)"
        for goal in brief["goal_previews"]
    ] or ["- Not goal-ready yet."]
    score_line = (
        f"trend={fit['trend']:.2f}, novelty={fit['novelty']:.2f}, "
        f"feasibility={fit['feasibility']:.2f}, user_fit={fit['user_fit']:.2f}, "
        f"risk={fit['risk']:.2f}"
    )
    readiness = brief["readiness"]
    readiness_line = (
        f"evidence={readiness['evidence']:.2f}, "
        f"goalability={readiness['goalability']:.2f}, "
        f"handoff={readiness['handoff_readiness']:.2f}"
    )

    return [
        f"### {index}. {brief['title']}",
        "",
        f"**What happened?** {brief['summary']}",
        "",
        f"**Why does it matter now?** {brief['why_now']}",
        "",
        f"**What research direction could it become?** `{handoff['topic_name']}`",
        "",
        f"**Who is this direction suitable for?** Researchers with fit score signals: {score_line}.",
        "",
        f"**Readiness.** {readiness_line}.",
        "",
        "**What evidence supports it?**",
        *source_lines,
        "",
        "**First measurable goal**",
        *goal_lines,
        "",
        "**Risks / watch-outs**",
        *risk_lines,
        "",
        "**Recommended next steps**",
        *next_step_lines,
        "",
        "**How can it be handed off to RH?**",
        f"- Topic: `{handoff['topic_name']}`",
        "- Initial queries:",
        *query_lines,
        f"- Suggested primitives: {', '.join(handoff['suggested_primitives'])}",
        "",
    ]


def render_discover_report_html(report: DiscoverReport) -> str:
    """Render a standalone HTML report with embedded JSON payload."""

    payload = report.to_dict()
    body = "\n".join(
        _brief_html_section(index, brief)
        for index, brief in enumerate(payload["briefs"], start=1)
    )
    json_payload = html.escape(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )
    title = html.escape(payload["title"])
    subtitle = html.escape(payload["subtitle"])
    generated_at = html.escape(payload["generated_at"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }}
    main {{ max-width: 960px; margin: 0 auto; padding: 48px 24px; }}
    header {{
      border: 1px solid #e2e8f0;
      background: linear-gradient(135deg, #eef2ff, #fff7ed);
      border-radius: 24px;
      padding: 32px;
      margin-bottom: 28px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 40px; letter-spacing: -0.03em; }}
    h2 {{ margin-top: 32px; font-size: 24px; }}
    article {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      padding: 24px;
      margin: 18px 0;
      box-shadow: 0 12px 40px rgba(15, 23, 42, 0.06);
    }}
    .meta, .muted {{ color: #64748b; }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      background: #eef2ff;
      color: #3730a3;
      padding: 4px 10px;
      font-size: 12px;
      margin: 4px 4px 4px 0;
    }}
    pre {{
      white-space: pre-wrap;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 16px;
      padding: 18px;
      overflow: auto;
    }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #020617; color: #e2e8f0; }}
      header, article {{ background: #0f172a; border-color: #1e293b; }}
      header {{ background: linear-gradient(135deg, #1e1b4b, #431407); }}
      .meta, .muted {{ color: #94a3b8; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <p class="meta">{html.escape(payload["product"])} · {generated_at}</p>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </header>
    <section>
      <h2>Editorial contract</h2>
      <p>Every opportunity answers: what happened, why now, direction, fit, evidence, and RH handoff.</p>
    </section>
    <section>
      <h2>Opportunities</h2>
      {body}
    </section>
    <details>
      <summary>OpportunityBrief JSON</summary>
      <pre>{json_payload}</pre>
    </details>
  </main>
</body>
</html>
"""


def _brief_html_section(index: int, brief: dict[str, Any]) -> str:
    handoff = brief["rh_handoff"]
    signals = "".join(
        "<li>"
        f"<strong>{html.escape(signal['type'])}</strong>: "
        f'<a href="{html.escape(signal["url"])}">{html.escape(signal["title"])}</a>'
        f" — {html.escape(signal['importance'])}; {html.escape(signal['reason'])}"
        "</li>"
        for signal in brief["signals"]
    )
    goals = "".join(
        "<li>"
        f"<strong>{html.escape(goal['title'])}</strong>: "
        f"{html.escape(goal.get('metric_name') or 'metric')} on "
        f"{html.escape(goal.get('dataset') or 'a scoped dataset')}"
        "</li>"
        for goal in brief["goal_previews"]
    )
    next_steps = "".join(
        f"<li>{html.escape(step)}</li>" for step in brief["recommended_next_steps"]
    )
    risks = "".join(f"<li>{html.escape(risk)}</li>" for risk in brief["risks"])
    queries = "".join(
        f'<span class="pill">{html.escape(query)}</span>'
        for query in handoff["initial_queries"]
    )
    return f"""<article>
  <p class="meta">Opportunity {index}</p>
  <h3>{html.escape(brief["title"])}</h3>
  <p><strong>What happened?</strong> {html.escape(brief["summary"])}</p>
  <p><strong>Why does it matter now?</strong> {html.escape(brief["why_now"])}</p>
  <p><strong>What research direction could it become?</strong> <code>{html.escape(handoff["topic_name"])}</code></p>
  <p class="muted">Goalability: {brief["readiness"]["goalability"]:.2f} · Handoff: {brief["readiness"]["handoff_readiness"]:.2f}</p>
  <p><strong>What evidence supports it?</strong></p>
  <ul>{signals}</ul>
  <p><strong>First measurable goals</strong></p>
  <ul>{goals or "<li>Not goal-ready yet.</li>"}</ul>
  <p><strong>Risks / watch-outs</strong></p>
  <ul>{risks or "<li>Not assessed yet.</li>"}</ul>
  <p><strong>Recommended next steps</strong></p>
  <ul>{next_steps}</ul>
  <p><strong>How can it be handed off to RH?</strong></p>
  <p>{queries}</p>
</article>"""
