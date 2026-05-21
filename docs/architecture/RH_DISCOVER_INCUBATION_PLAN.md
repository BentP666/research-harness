# RH Discover Incubation Plan

**Status:** planning note
**Date:** 2026-05-10
**Owner:** Gewu AI / Research Harness

## 1. Brand and product logic

Company brand:

```text
格物智能 Gewu AI
```

Flagship AI-research product:

```text
Research Harness / RH
```

Early incubation surface:

```text
RH Discover
```

Core principle:

> RH Discover belongs to the Research Harness product architecture, but should be
> developed and validated as a technically decoupled early module.

RH should remain the main product brand. RH Discover is not a separate competing
brand; it is the direction-discovery entrance for RH.

## 2. Why RH Discover should be developed first

Full RH is valuable after a user already has a research direction. Many early
users, especially students and early-stage researchers, first need help with:

- what is happening in their field;
- what has changed in the last 24 hours / 7 days;
- what has been trending over the last 1 / 3 / 5 years;
- which signals can become feasible research topics;
- whether a direction fits their background, resources, and timeline.

Therefore RH Discover is the best early acquisition and validation product:

```text
No research direction
    ↓
RH Discover
    ↓
Candidate directions / opportunity briefs
    ↓
Research Harness core workflow
```

## 3. Product scope

RH Discover should convert research and technology signals into actionable
research opportunities.

It should not be positioned as:

- a generic AI news aggregator;
- a generic paper recommender;
- a replacement for RH Core;
- an automatic topic oracle.

It should be positioned as:

> A signal-to-direction system that helps researchers discover what is worth
> studying next, then hand off the selected direction to RH.

## 4. Initial modules

```text
RH Discover
├── Signal Feed
│   ├── 24h / 7d research and technology signals
│   ├── papers, technical blogs, product releases, repos, models
│   └── signal cards with why-now and research-opportunity notes
│
├── Trend Atlas
│   ├── 1 / 3 / 5 year trend maps
│   ├── paper-volume and venue signals
│   ├── citation / benchmark / repo activity where available
│   └── saturation and red-ocean indicators
│
├── Topic Scout
│   ├── candidate research directions
│   ├── representative papers
│   ├── feasible angles
│   └── next-step reading/search plans
│
├── Fit Score
│   ├── user-background fit
│   ├── difficulty and resource estimate
│   ├── novelty / feasibility / impact / risk
│   └── “suitable for whom / not suitable for whom” judgment
│
└── RH Handoff
    ├── opportunity brief export
    ├── seed papers
    ├── initial search queries
    └── import/create-topic bridge into RH Core
```

## 5. Output contract

RH Discover should produce a stable `OpportunityBrief` that RH Core can consume.

Draft shape:

```json
{
  "title": "Candidate research direction",
  "summary": "Short explanation of the opportunity",
  "why_now": "Why this direction matters now",
  "signals": [
    {
      "type": "paper|blog|product|repo|model|benchmark|news",
      "title": "...",
      "url": "...",
      "published_at": "...",
      "importance": "act_now|watch|horizon",
      "reason": "..."
    }
  ],
  "trend_context": {
    "window": "1y|3y|5y",
    "growth_summary": "...",
    "saturation": "low|medium|high"
  },
  "seed_papers": [
    {
      "title": "...",
      "doi": null,
      "arxiv_id": null,
      "url": "...",
      "year": 2026
    }
  ],
  "fit_score": {
    "trend": 0.0,
    "novelty": 0.0,
    "feasibility": 0.0,
    "user_fit": 0.0,
    "risk": 0.0
  },
  "risks": ["..."],
  "recommended_next_steps": ["..."],
  "rh_handoff": {
    "topic_name": "...",
    "initial_queries": ["..."],
    "suggested_primitives": ["paper_search", "paper_ingest", "gap_detect"]
  }
}
```

## 6. Engineering boundary

Recommended early architecture:

```text
research-harness
  └── RH Core: workflow, evidence, provenance, writing, review

rh-discover or research-harness-discover
  └── Signal ingestion, trend analysis, topic scouting, lightweight web/CLI
```

The two systems should communicate through `OpportunityBrief`, not through
shared UI state or hidden database coupling.

This keeps RH Core focused while allowing RH Discover to move quickly.

## 7. Incubation roadmap

### Phase 0 — Content validation

- Publish RH Discover Weekly / CS Research Radar manually or semi-automatically.
- Channels: Xiaohongshu, WeChat public account, newsletter, private community.
- Validate whether users save, share, comment, or request topic diagnosis.

### Phase 1 — Lightweight tool

- Build a simple CLI / web report generator.
- Inputs: field, time window, user background, target outcome.
- Outputs: Markdown / HTML / JSON opportunity briefs.

### Phase 2 — Personalization

- Add user profiles and watchlists.
- Add Fit Score and saved directions.
- Add daily/weekly personalized signal briefs.

### Phase 3 — RH integration

- Import `OpportunityBrief` into RH Core.
- Create RH topic from selected direction.
- Attach seed papers and initial search queries.

### Phase 4 — Commercial RH Cloud path

- Bundle RH Discover + RH Core into RH Cloud.
- Offer personal, lab, and enterprise editions.

## 8. Commercialization and growth

Early public-facing content should emphasize concrete pain points:

- “不知道研究方向怎么选？”
- “过去 24 小时 AI/CS 有哪些真正值得关注的信号？”
- “这个方向火，但适合硕士做吗？”
- “从某个大厂技术发布里能拆出哪些研究题？”
- “本周值得关注的 5 个 CS/AI 研究方向。”

Commercial layers:

```text
Free content
    └── RH Discover Daily / Weekly

Individual Pro
    └── personalized signals, Topic Scout reports, exports

Service packages
    └── topic diagnosis, field trend reports, opening-topic consultation

Lab / team edition
    └── shared watchlists, weekly lab brief, group topic pool

Enterprise / research institute edition
    └── technology radar, competitor research intelligence, private deployment
```

## 9. Guardrails

RH Discover must always answer:

1. What happened?
2. Why does it matter now?
3. What research direction could it become?
4. Who is this direction suitable for?
5. What evidence supports it?
6. How can it be handed off to RH?

If an item cannot answer these questions, it is only news, not an RH Discover
opportunity.

## 10. Near-term next steps

1. Finalize the `OpportunityBrief` schema.
2. Define first-source list for CS/AI signals.
3. Produce 3 sample RH Discover Weekly issues manually.
4. Use the samples as Xiaohongshu / newsletter content.
5. Build the simplest report generator only after content demand is validated.

## 11. Implemented scaffold

The first code slice is intentionally small and decoupled from RH Core storage:

```text
packages/research_harness/research_harness/discover/
├── models.py    — OpportunityBrief dataclasses, validation, Markdown rendering
├── schema.py    — JSON Schema for the Discover/Core handoff contract
├── sources.py   — seed source registry for papers, blogs, product, repos/models, social
└── cli.py       — `rh discover` commands
```

CLI surface:

```bash
rh discover schema
rh discover sources
rh discover brief \
  --title "Candidate direction" \
  --summary "Why this could be a research opportunity" \
  --why-now "Why the timing matters" \
  --signal "blog|Signal title|https://example.com|act_now|Research-opportunity reason" \
  --query "initial literature search query" \
  --next-step "Run a scoped literature search"
rh discover weekly --sample --format markdown
rh discover weekly --sample --format html --output reports/rh-discover-weekly.html
```

Guardrail: `rh discover brief` refuses news-only items. A valid
`OpportunityBrief` must include a why-now rationale, at least one signal,
recommended next steps, and RH handoff queries.

Product-ready MVP state:

- `rh discover sources` exposes the seed source registry.
- `rh discover brief` lets an editor or agent build one validated
  `OpportunityBrief`.
- `rh discover weekly --sample` renders a complete RH Discover Weekly issue in
  Markdown, HTML, or JSON.
- `rh discover weekly --input <issue.json>` and
  `rh discover weekly --no-sample` load curated file-backed issues from
  `docs/discover/issues/`.
- The weekly report explicitly answers the six RH Discover guardrail questions:
  what happened, why now, direction, fit, evidence, and RH handoff.
- HTML reports embed the full `OpportunityBrief` JSON payload for reuse by
  agents or future RH Core importers.
- A checked-in Markdown sample lives at
  `docs/architecture/RH_DISCOVER_WEEKLY_SAMPLE.md`.
- The publishable issue archive lives under `docs/discover/`, with one
  published launch issue at `docs/discover/issues/2026-05-10-weekly.json` and a
  reusable template at `docs/discover/templates/issue-template.json`.
- The MCP/FastAPI layer exposes the same product artifact for the web frontend:
  - `GET /api/discover/sources`
  - `GET /api/discover/weekly?sample=true`
  - `GET /api/discover/weekly?sample=false`
  - `GET /api/discover/issues?cadence=weekly`
  - `GET /api/discover/issues/latest?cadence=weekly`
- The Next.js `/discover` page now renders a real RH Discover Weekly showcase
  from that API, including OpportunityBrief cards, source evidence, fit score,
  initial search queries, suggested RH primitives, and a “Turn into RH topic”
  action.
- “Turn into RH topic” now opens `/topics/new` with the `OpportunityBrief`
  handoff prefilled as an editable RH Core topic draft: topic slug, summary,
  why-now rationale, handoff queries, risks, recommended next steps, and seed
  paper identifiers when available.
- The Python contract layer now enforces schema-critical constraints in code:
  supported trend windows, 0..1 fit-score values, non-empty source titles/URLs,
  and normalized RH handoff strings.

Next implementation slices:

1. Use the launch issue format to publish/manual-test 2 more RH Discover Weekly
   issues before adding live connectors.
2. Add optional YAML input loading only if editors prefer YAML over JSON.
3. Replace the URL-prefill handoff with a first-class create-topic/import API
   once handoff policy is finalized.
4. Add optional connector adapters only after the manual samples show demand.
