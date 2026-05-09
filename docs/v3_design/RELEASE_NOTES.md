# Research Harness v3 — Release Notes

## Overview

v3 upgrades the 6-stage pipeline (Init/Build/Analyze/Propose/Experiment/Write) with:
- **4 researcher personas** (p1-p4) with adaptive onboarding
- **7 new first-class artifacts**: intake_profile, field_brief, goal_pool, method_atoms, experiment_matrix, venue_decision, venue_style_kit
- **Retrieval logging** across all stages
- **3-tier venue degradation** with Q4 red line enforcement

## New Artifacts

| Artifact | Stage | Description |
|----------|-------|-------------|
| intake_profile | init | Researcher persona + constraints (venue/compute/deadline) |
| field_brief | analyze | 6-dimension field landscape snapshot (datasets/baselines/challenges/venues/compute/narratives + saturation score) |
| goal_pool | analyze | Scored research goals with 5-factor breakdown (headroom/feasibility/evidence/venue_fit/compute_fit) |
| method_atoms | experiment | Reusable method components extracted from papers (6 types: loss/data_trick/augmentation/training_schedule/inference_heuristic/micro_block) |
| experiment_matrix | experiment | Goals × atoms matrix with proxy pass execution and prune/promote workflow |
| venue_decision | write | Venue selection with constraint-aware logic (locked/preferred/open) |
| venue_style_kit | write | Writing style distillation from real venue papers (section lengths/citation density/hedging terms) |

## New Endpoints (17 total)

| Iter | Endpoint | Method |
|------|----------|--------|
| 01 | `/api/topics/{id}/intake-profile` | GET, PUT |
| 03 | `/api/topics/{id}/field-brief` | GET, POST |
| 05 | `/api/topics/{id}/goal-pool` | POST |
| 05 | `/api/topics/{id}/goals` | GET |
| 05 | `/api/topics/{id}/goals/{gid}` | PATCH, DELETE |
| 07a | `/api/topics/{id}/method-atoms/harvest` | POST |
| 07a | `/api/topics/{id}/method-atoms` | GET |
| 07a | `/api/method-atoms/{aid}` | DELETE |
| 07b | `/api/topics/{id}/experiment-matrix/build` | POST |
| 07b | `/api/topics/{id}/experiment-matrix/proxy` | POST |
| 07b | `/api/topics/{id}/experiment-matrix` | GET |
| 08 | `/api/topics/{id}/venue-decision` | GET, POST |
| 08 | `/api/topics/{id}/venue-style-kit` | GET, POST |
| 09 | `/api/topics/{id}/retrieval-log` | GET |
| 09 | `/api/papers/search` (extended) | POST |

## New Migrations (7)

| # | Name | Tables |
|---|------|--------|
| 057 | intake_profile | topic_intake_profile |
| 058 | field_brief_meta | field_brief_meta |
| 059 | goal_pool | goal_pool |
| 060 | method_atoms | method_atoms |
| 061 | retrieval_log | retrieval_log |
| 062 | experiment_matrix | experiment_matrix_cell |
| 063 | venue_decision | venue_decision, venue_style_kit |

## New Frontend Components (10)

| Iter | Component | Location |
|------|-----------|----------|
| 02 | PersonaStep | `components/onboarding/persona-step.tsx` |
| 02 | ConstraintsStep | `components/onboarding/constraints-step.tsx` |
| 04 | FieldBriefCard | `components/topic/field-brief-card.tsx` |
| 06 | GoalPoolCard | `components/topic/goal-pool-card.tsx` |
| 07b | MethodAtomsLibrary | `components/topic/method-atoms-library.tsx` |
| 07b | ExperimentMatrixCard | `components/topic/experiment-matrix-card.tsx` |
| 08 | VenueDecisionBanner | `components/topic/venue-kit.tsx` |
| 08 | VenueStyleKitCard | `components/topic/venue-kit.tsx` |
| 09 | RetrievalTriggerButton | `components/topic/retrieval-trigger-button.tsx` |
| 09 | RetrievalLogTimeline | `components/topic/retrieval-log-timeline.tsx` |

## New Primitives (5)

| Iter | File | Function |
|------|------|----------|
| 03 | `field_brief_impl.py` | `build_field_brief()` |
| 05 | `goal_pool_impl.py` | `build_goal_pool()`, `score_goal()` |
| 07a | `harvest_atoms_impl.py` | `harvest_atoms_from_paper()` |
| 07b | `experiment_matrix_impl.py` | `build_matrix()`, `run_proxy_pass()` |
| 08 | `venue_decision_impl.py` | `decide_venue()`, `build_style_kit()` |

## Test Coverage

| Layer | Count |
|-------|-------|
| Backend pytest | 1378 passed / 0 failed (37 new in v3) |
| Frontend vitest | 22 passed / 0 failed (all new in v3) |
| E2E scripts | 5 (iter 02/04/06/07b/08) |
| Demo screenshots | 28 (CP2 mid: 17 + iter-10: 11 + iter-09 step-12: 1) |
| Console errors during demo | 0 (after stage-graph CSS + Matrix Fragment key fixes) |

## Commits (by iteration)

| Iter | Commit | Title |
|------|--------|-------|
| 01 | a8abba8 | intake_profile schema + endpoints |
| 02 | 7333cd5 | onboarding persona branching |
| 03 | bd13a4c | field_brief primitive + freshness |
| 04 | c9717e3 | field_brief card UI |
| 05 | 4027164 | goal_pool scoring + endpoints |
| 06 | 37310e2 | goal_pool card UI |
| 07a | 38ec051 | method_atoms harvest |
| 07b | 9968164 | experiment_matrix proxy + UI |
| 08 | 65495b1 | venue_decision + style_kit |
| 09 | 4ed0faf | retrieval_log cross-stage |
| 10 | (this commit) | e2e demo + release notes |

## Breaking Changes

None. All v3 features are additive. Existing v2 endpoints and workflows continue to function unchanged.

## Known Limitations

1. FieldBriefCard / GoalPoolCard only render at stage=analyze; past-analyze topics cannot revisit
2. MethodAtomsLibrary empty state lacks "Harvest from paper" CTA button
3. venue_style_kit returns 409 when target venue has <3 matching papers in pool (by design — Q4 red line)
4. Proxy pass in experiment_matrix uses sandbox subprocess; long-running experiments may timeout

## v0.3.0 Polish (final pass before GA)

- **Bug fix** `stage-graph.tsx`: framer-motion array keyframes on SVG `<circle r>` triggered "Expected length, undefined" errors. Replaced with CSS `@keyframes rh-pulse-ring` (opacity-only, SVG-safe across browsers).
- **Bug fix** `experiment-matrix-card.tsx`: shorthand `<>...</>` Fragment in map without key triggered React key warning. Replaced with `<Fragment key={...}>`.
- **Iter-09 frontend completion**: shipped `retrieval-trigger-button.tsx` + `retrieval-log-timeline.tsx`, mounted on 4 panels (build/analyze/experiment/write); +5 vitest tests.
- **Verification**: live MCP Playwright sweep on topic 21 — **0 console errors** in all stages.
