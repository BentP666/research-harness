# V3 E2E Demo Journey Script

**Topic**: #21 `v3-demo-tfrbench-replay`
**Date**: 2026-04-25
**Persona**: p3_topic_weak (I Have a Topic)
**Papers**: 30 deep-read papers linked from topic 18 (TFRBench)

## Cost Log

| Step | Primitive | Tier | Pre-cost | Post-cost | Delta |
|------|-----------|------|----------|-----------|-------|
| Baseline | — | — | $0.125 | — | — |
| 4 | field_brief | medium | $0.125 | $0.125* | ~$0.15 est |
| 5 | goal_pool | light | $0.125* | $0.125* | ~$0.05 est |
| 7 | atoms_harvest ×5 | light | $0.125* | $0.125* | ~$0.25 est |
| Final | — | — | — | $0.125* | **~$0.50 est total** |

\* Anthropic provider usage not reflected in local provenance table (proxy-routed calls don't write back to RH token accounting). Calls confirmed successful by data returned.

## Journey Steps

### Step 1-2: Onboarding + Intake Profile

**URL**: `/onboarding` → API: `PUT /api/topics/21/intake-profile`
**User Action**: Select persona p3 (I Have a Topic) → Fill constraints
**API Call**:
```
PUT /api/topics/21/intake-profile
{
  "persona": "p3_topic_weak",
  "domain_confidence": 80,
  "topic_confidence": 60,
  "venue_constraint": "preferred",
  "target_venue": "EMNLP",
  "compute_budget": "single_gpu",
  "time_to_deadline_days": 120,
  "seed_present": 0
}
```
**Result**: 200 OK, intake_profile saved + artifact recorded (stage=init)
**Note**: Topic 21 pre-created and 30 papers linked from topic 18 via SQL.

### Step 3: Stage Advancement (init → build → analyze)

**API**: `POST /api/topics/21/force-advance`
**Result**: Successfully advanced through init → build → analyze

### Step 4: Field Brief (LLM)

**URL**: `/topics/21` (stage=analyze, FieldBriefCard visible)
**User Action**: Click "Generate Field Brief"
**API**: `POST /api/topics/21/field-brief`
**Result**: 200 OK
- saturation_score: **0.62** (Yellow zone)
- datasets: **30** entries
- baselines: **10** entries
- open_challenges, venue_options, narrative_patterns populated

### Step 5: Goal Pool (LLM)

**URL**: `/topics/21` (GoalPoolCard visible)
**User Action**: Click "Build Goal Pool"
**API**: `POST /api/topics/21/goal-pool`
**Result**: 200 OK, **5 goals** returned:

| # | Dataset | Baseline | Score |
|---|---------|----------|-------|
| 1 | TimeSeriesExam | GPT-4o zero-shot | 0.5409 |
| 2 | Exchange Rate | N-BEATS | 0.5339 |
| 3 | Intermittent TS | Croston method | 0.5322 |
| 4 | ILI | DLinear | 0.5290 |
| 5 | ETTm2 | iTransformer | 0.5282 |

### Step 6: Stage Advancement (analyze → propose → experiment)

**API**: `POST /api/topics/21/force-advance` ×2
**Result**: propose → experiment

### Step 7: Method Atoms Harvest (LLM ×5)

**URL**: `/topics/21` (stage=experiment, MethodAtomsLibrary visible)
**User Action**: Select 5 papers → Click harvest
**API**: `POST /api/topics/21/method-atoms/harvest`
**Body**: `{"paper_ids": [3894, 1443, 3895, 3896, 3897]}`
**Result**: 200 OK
- papers_processed: **5**
- total_atoms: **30**
- errors: **[]**

### Step 8: Experiment Matrix Build

**URL**: `/topics/21` (ExperimentMatrixCard visible)
**User Action**: Click "Build Matrix"
**API**: `POST /api/topics/21/experiment-matrix/build`
**Result**: 200 OK
- **150 cells** (5 goals × 30 atoms)
- All status: pending
- Proxy pass skipped (would require 150 LLM calls)

### Step 9: Write Stage — Venue Decision + Style Kit (Q4 Red Line)

**URL**: `/topics/21` (stage=write, VenueDecisionBanner + VenueStyleKitCard visible)

**9a. Venue Decision**:
**API**: `POST /api/topics/21/venue-decision`
**Result**: 200 OK
```json
{
  "decided_venue": "EMNLP",
  "decision_basis": {"constraint": "preferred", "target": "EMNLP", "matched": true},
  "source_venues": ["EMNLP"]
}
```

**9b. Style Kit (Q4 Red Line — Expected 409)**:
**API**: `POST /api/topics/21/venue-style-kit`
**Result**: **409 Conflict**
```json
{
  "detail": "Need at least 3 reference papers for venue style analysis. Found 0 for 'EMNLP' and family ['emnlp', 'acl', 'naacl', 'eacl', 'coling', 'findings']. Please ingest more papers from this venue."
}
```

**Demo stops here** — system correctly refuses to fabricate style data from insufficient samples. This is the Q4 red line's intended behavior.

User options from here:
- (a) Use retrieval_trigger to ingest EMNLP papers, then retry
- (b) Change target_venue to a venue with sufficient hits (e.g., NeurIPS)

### Step 10: Cross-Stage Retrieval Trigger

**URL**: Any stage panel → retrieval trigger button
**API**: `POST /api/papers/search`
**Body**: `{"query":"time series forecasting reasoning","topic_id":21,"stage":"analyze","trigger_reason":"missing_evidence"}`
**Result**: 200 OK, 5 papers found
**DB Check**: `retrieval_log` table has entry with stage=analyze, trigger_reason=missing_evidence

## Screenshots

Screenshots to be taken by review session using MCP Playwright, following this script. Archive to `docs/assets/v3-demo/journey-screenshots/`.

Expected screenshots (≥30):
- step-01-onboarding-persona.png
- step-02-constraints-filled.png
- step-04-field-brief-success.png (6 tiles + saturation bar)
- step-05-goal-pool-table.png (5 goals + scores)
- step-07-atoms-library.png (30 atoms grouped by type)
- step-08-matrix-pending.png (150 cells grid)
- step-09a-venue-decision.png (EMNLP decided)
- step-09b-style-kit-409.png (red error + guidance text)
- step-10-retrieval-trigger.png
- mobile-* variants for key steps
