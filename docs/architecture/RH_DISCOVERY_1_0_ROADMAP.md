# RH Discovery 1.0.0 Roadmap

**Status:** active delivery plan
**Updated:** 2026-05-13
**Product:** RH Discovery
**Boundary:** independent product line inside the Research Harness monorepo until extraction criteria are met

## 1. 1.0.0 capability statement

RH Discovery 1.0.0 helps a researcher who does not yet have a precise topic move from frontier signals to a concrete, measurable research direction, then hand the selected opportunity to RH Core as a seeded topic.

The 1.0 loop is:

```text
signal → opportunity → goal preview → readiness judgment → RH handoff
```

## 2. Non-goals for 1.0.0

- Generic AI news aggregation.
- Generic paper recommendation.
- Autonomous experiment execution.
- Billing, accounts, team workspaces, or enterprise deployment.
- Directly coupling Discovery state to RH Core orchestration internals.

## 3. Product surfaces

| Surface | 1.0 requirement | Current status |
| --- | --- | --- |
| Discovery Home | Show high-level frontier problem map and evidence count | Implemented as static product surface |
| Opportunity Explorer | Browse opportunities with fit/readiness signals | Implemented with live API-backed opportunities |
| Opportunity Detail | Explain why now, evidence, risks, first goals, and RH handoff | Implemented with Goal Preview and handoff UI |
| Digest / Issue Archive | Publish curated daily/weekly/special issues from JSON | Implemented |
| Watchlists | Let users track long-running opportunity lanes | Implemented with local persistence |
| RH Handoff | Create RH Core topic from selected opportunity and goal seed | Backend endpoint and frontend action implemented |

## 4. Backend contract

### Stable 1.0 payload

Every 1.0 opportunity must emit:

- `OpportunityBrief`
- `goal_previews`
- `readiness`
- `rh_handoff`

### GoalPreview

`GoalPreview` is Discovery's first-goal contract. It is intentionally lighter than RH Core `goal_pool`.

Required meaning:

- `dataset`: what evidence/task pool will be measured
- `baseline`: what the first comparison is
- `metric_name`: what will be measured
- `target_metric_delta`: expected measurable movement, if known
- `compute_need`: low, medium, high
- `first_steps`: first concrete research actions

### Readiness

`OpportunityReadiness` tracks:

- evidence
- novelty
- feasibility
- goalability
- handoff readiness

These are editorial readiness signals, not objective scientific rankings.

## 5. API contract

Implemented 1.0 endpoints:

```http
GET  /api/discover/opportunities
GET  /api/discover/opportunities/{slug}
POST /api/discover/opportunities/{slug}/handoff
```

Existing endpoints:

```http
GET /api/discover/sources
GET /api/discover/weekly
GET /api/discover/issues
GET /api/discover/issues/{issue_id}
```

## 6. Release gates

Discovery cannot be called strict 1.0.0 until all gates pass.

### Contract gates

- [x] OpportunityBrief has schema coverage.
- [x] GoalPreview exists and validates compute/scores.
- [x] OpportunityReadiness exists and validates scores.
- [x] Samples include goal previews.
- [x] Opportunity list/detail APIs expose readiness and goal previews.
- [x] Handoff API creates an RH Core topic.
- [x] Published issue JSON files are migrated to include goal previews explicitly, not only inferred defaults.

### Product gates

- [x] Opportunity detail has a Goal Preview panel.
- [x] Opportunity explorer consumes live `/api/discover/opportunities` data.
- [x] Handoff UI calls `POST /api/discover/opportunities/{slug}/handoff`.
- [x] Watchlist UI can persist user-selected lanes.
- [x] Empty/error/loading states are complete for all Discovery routes.
- [x] Mobile pass completed for all Discovery routes.

### Content gates

- [x] At least 3 real published Discovery issues exist.
- [x] Every published opportunity has at least 2 evidence signals.
- [x] Every published opportunity has at least 1 goal preview.
- [x] Source registry distinguishes connector, sidecar, and manual sources.
- [x] Editorial checklist is documented and enforced by validation.

### Verification gates

- [x] Backend Discover contract/API tests pass.
- [x] Web tests pass.
- [x] Web lint passes.
- [x] Ruff check and format check pass for touched backend files.
- [x] Full backend test suite pass.
- [x] Full web production build pass.
- [x] Accessibility smoke pass for Discovery routes.

Mobile/accessibility smoke audit covered `/discovery`, `/discovery/explore`,
`/discovery/track`, `/discovery/watchlists`, `/discovery/digest`,
`/discovery/opportunities/real-world-agent-evaluation-under-dynamic-workflows`,
and `/discover/issues/2026-05-12-weekly` at 390×844. Each route had a main
landmark, at least one `h1`, no unnamed links/buttons, and no horizontal
overflow.

## 7. Extraction criteria

Keep Discovery in the RH monorepo until all are true:

- Discovery can run its main browsing/detail value without RH Core DB state.
- Handoff contract is stable for at least one beta cycle.
- Source/content pipeline has a separate operational lifecycle.
- Deployment needs differ from RH Core.
- Product analytics or growth surfaces need independent iteration.

If these conditions hold before or during 1.0 beta, split into `rh-discovery` or a monorepo package group.

## 8. Immediate next implementation steps

1. Complete mobile and accessibility review.
2. Harden remaining Discovery loading/error/empty states.
3. Decide whether current issue count is enough for 1.0 or produce two more real issues.
4. Prepare version bump only after every gate above is green.
