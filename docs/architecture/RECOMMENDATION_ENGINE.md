# Research Recommendation Engine (v0.4 design)

> **⚠ SUPERSEDED by `CS_RESEARCH_WORKFLOW_V2.md` (r3, 2026-04-23)**
> The CS workflow plan revises this doc's scoring model (LLM-based, not deterministic)
> and renumbers the migration from `043_research_candidates.sql` → `048_research_candidates.sql`
> (numbers 043 and 044 are reserved by upstream work; 045–047 are used by CS classification,
> task canonicalization, and gap confidence respectively).
> Schema atoms (typed evidence, `lineage_key`, `evidence_signature`, `sweep_stale`) are retained.
> **Before implementing from this doc, read `CS_RESEARCH_WORKFLOW_V2.md` §4.**

**Status:** Post-review draft (codex round 1 applied) · **Target release:** v0.4.0 MVP → v0.4.2 LLM narration → v0.5 orchestrator hand-off
**Author:** Research Harness team · **Last updated:** 2026-04-23

> **TL;DR** — Replace the "hot-topic dashboard" framing with an **evidence-based
> candidate engine** that proposes `Top-N research directions` for a given scope
> (topic / domain / discipline), each backed by concrete `gap_id`s,
> `contradiction_id`s, and `claim_id`s that already exist in our DB. Scoring is
> **deterministic** (computed from counts + severities + venue / citation
> signals); LLMs are used only for narration (title, pitch, risks) — **never**
> for producing numbers. Users triage into a shortlist, and shortlisted
> candidates can be promoted into an `orchestrator_init` topic brief.

---

## 1. Motivation

The current `/research/trends` page shows "hot landscape overviews" — a commodity signal.
Our differentiator is that we already extract **structured claims**, **gaps**, and
**contradictions** per topic (migrations `022_phase2_analysis.sql`,
`031_gaps.sql`, `039_v2_product_features.sql`). A recommendation engine built on
that graph can answer the question researchers actually ask:

> *Given what I've already read, what's the **next paper I should write**?*

Commodity trend tools (Semantic Scholar Trending, Google Scholar Alerts, pubtrends)
cannot answer this — they don't have the user's structured literature model.

### Positioning vs existing `direction_ranking` primitive

| | `direction_ranking` (today) | Recommendation Engine (proposed) |
|---|---|---|
| Source of scores | LLM opinion on `gaps + claims` text | Deterministic function of counts, severities, venue ranks, citation gains |
| Output | Ranked list in the prompt-response | Persisted `research_candidates` rows w/ stable ids |
| Evidence | Free-text "supporting_gaps" strings | Typed `gap_ids`, `contradiction_ids`, `claim_ids`, `paper_ids` |
| User action | None — read-only | `shortlist` / `dismiss` / `promote-to-topic` |
| Refresh model | Ad-hoc | Scope-keyed, incremental, cacheable |

The existing primitive stays — it becomes the **narration step** inside the new
engine (producing titles/pitches/risks), not the scoring step.

---

## 2. Inputs (all already in schema)

No new ingestion is required. Engine consumes:

| Table | Column(s) used | Signal |
|---|---|---|
| `gaps` | `severity`, `related_paper_ids`, `created_at` | open gap density |
| `normalized_claims` | `method`, `dataset`, `metric`, `direction`, `value`, `confidence` | method/dataset coverage |
| `contradictions` | `same_task`, `same_dataset`, `same_metric`, `status='candidate'` | high-impact opportunity |
| `paper_topics` | `paper_id`, `topic_id`, `relevance`, `created_at` | scope filter + freshness signal |
| `papers` | `year`, `venue`, `citation_count`, `created_at` | momentum, baseline quality, ingest time |
| `venue_ranks` | `ccf_rank`, `cas_zone`, `impact_factor` | venue-quality signal |
| `taxonomy_assignments` | `node_id`, `confidence` | method clustering (v0.4.2+) |
| `project_artifacts` (migration 006) + `claims` (migration 039) | artifact-grounded claims | what the user has already written (avoid re-recommending) |
| `citation_snapshots` (**new in v0.4.2**) | `paper_id`, `citation_count`, `observed_at` | relative citation gain (pre-req for momentum term) |

All inputs are **local-first** — no external API calls required. An in-scope
refresh touches at most ~10k rows per topic.

> **Note**: `citation_snapshots` does not exist yet. Momentum's
> `relative_citation_gain` term is **not implementable in v0.4.0**; it is
> deferred to v0.4.2 alongside the snapshot table (see §8).

---

## 3. Output schema

```sql
-- migration 048_research_candidates.sql  (renumbered per CS_RESEARCH_WORKFLOW_V2.md §2/D5)
CREATE TABLE IF NOT EXISTS research_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,                     -- discipline:cs | domain:<id> | topic:<id>
    title TEXT NOT NULL,                     -- ≤ 80 chars, LLM-generated or templated
    pitch TEXT NOT NULL DEFAULT '',          -- 2 sentences
    score_total NUMERIC NOT NULL,            -- 0..10, ε-floor weighted product
    score_novelty NUMERIC NOT NULL,          -- 0..1
    score_feasibility NUMERIC NOT NULL,      -- 0..1
    score_impact NUMERIC NOT NULL,           -- 0..1
    score_momentum NUMERIC NOT NULL,         -- 0..1
    confidence_level TEXT NOT NULL DEFAULT 'normal', -- low | normal | high
    evidence_gap_ids TEXT NOT NULL DEFAULT '[]',           -- JSON int[]
    evidence_contradiction_ids TEXT NOT NULL DEFAULT '[]', -- JSON int[]
    evidence_claim_ids TEXT NOT NULL DEFAULT '[]',         -- JSON int[]
    seed_paper_ids TEXT NOT NULL DEFAULT '[]',             -- JSON int[]
    why TEXT NOT NULL DEFAULT '[]',          -- JSON list of {kind, detail, weight}
    risks TEXT NOT NULL DEFAULT '[]',        -- JSON list of {kind, detail}
    source TEXT NOT NULL DEFAULT 'computed', -- computed | seed | hybrid
    status TEXT NOT NULL DEFAULT 'candidate',-- candidate | shortlisted | dismissed | promoted
    stale_reason TEXT,                       -- null when fresh; e.g. 'resolved_by_paper', 'orphaned_evidence'
    resolved_by_paper_ids TEXT NOT NULL DEFAULT '[]', -- populated when stale_reason='resolved_by_paper'
    lineage_key TEXT NOT NULL,               -- stable identity: sha1(primary_signal_family + normalized_title_or_method_or_task)
    evidence_signature TEXT NOT NULL,        -- sha1(sorted evidence ids) — changes when evidence grows/shrinks
    narration_model TEXT,                    -- null if rule-templated title
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(scope, lineage_key)
);

CREATE INDEX idx_rc_scope_confidence_score
    ON research_candidates(scope, status, confidence_level, score_total DESC);
CREATE INDEX idx_rc_evidence_sig ON research_candidates(evidence_signature);
```

**Why `lineage_key` separate from `evidence_signature`** (codex round 1):
User dismisses candidate `{gap:42}`. Next refresh finds the same direction plus
a new supporting gap `77`, producing evidence `{gap:42, gap:77}`. A single
`signature` column would generate a new row and the dismiss would silently
revert. Instead:
- `lineage_key` is derived from the **primary signal family** plus normalized
  title/method/task text (`sha1("gap-driven" + normalize(gap.description))` for
  Pass 1; `sha1("contradiction" + c.task + c.metric)` for Pass 2). It's stable
  across evidence growth.
- `evidence_signature` is the content hash. When it differs from the stored
  row, we UPDATE scores + evidence + narration but **preserve `status`**.
- `UNIQUE(scope, lineage_key)` enforces one row per direction per scope.

**Why separate `why` and `risks` as JSON of typed atoms**:
So the UI can render them as clickable chips (each `gap` atom links to the
gap detail), not prose. Prevents "LLM writes fake-sounding paragraph" drift.

**`why` atom shapes** (closed taxonomy — keep it boring):

```json
{ "kind": "unresolved_gap", "gap_id": 42, "severity": "high", "weight": 0.8 }
{ "kind": "contradiction", "contradiction_id": 17, "same_metric": true, "weight": 0.9 }
{ "kind": "method_transfer", "from_domain": "NLP", "to_domain": "CV", "claim_ids": [12,34], "weight": 0.6 }
{ "kind": "citation_momentum", "paper_id": 99, "relative_gain": 0.42, "weight": 0.5 }
{ "kind": "venue_gap", "venue": "NeurIPS", "coverage": 0.15, "weight": 0.4 }
```

**`risks` atom shapes**:

```json
{ "kind": "thin_literature", "detail": "Only 4 papers in scope" }
{ "kind": "low_confidence_claims", "detail": "Average claim confidence 0.32" }
{ "kind": "stale_gaps", "detail": "Supporting gaps haven't been refreshed in 94 days" }
{ "kind": "llm_risk", "detail": "<LLM-generated free text — optional>" }
```

---

## 4. Pipeline

```
scope (topic:42)
    │
    ▼
┌─────────────────────────┐
│ 4a. Candidate seeding   │  — deterministic, no LLM
│   • gap-driven          │
│   • contradiction-driven│
│   • method-transfer     │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4b. Merge + dedup       │  — signature collision → merge evidence
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4c. Score each candidate│  — deterministic formula (§5)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4d. Narrate (optional)  │  — LLM for title + pitch + llm_risks
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4e. Persist / UPSERT    │  — keeps user status when unchanged
└─────────────────────────┘
```

### 4a — Candidate seeding rules

A candidate is a `(set of gap_ids, set of contradiction_ids, set of claim_ids,
set of paper_ids)` tuple. The three seeding passes each produce candidates
from one primary signal; step 4b merges them.

**Pass 1 — gap-driven**
For each `gap` in scope with `severity IN ('high', 'medium')`, compute
**unresolved status** as:

1. Pool candidate-resolvers = papers where
   `paper_topics.created_at > gap.created_at` OR `papers.created_at > gap.created_at`
   (use whichever timestamp is later; covers both "ingested after the gap" and
   "linked to the topic after the gap").
2. For each resolver, compute `tfidf_cosine(paper.abstract, gap.description)`
   in Python (SQLite filters scope + timestamp first, vectorization in memory).
3. If any resolver has cosine ≥ 0.4, the gap is **probably resolved**: emit a
   candidate anyway but with `stale_reason='resolved_by_paper'` and
   `resolved_by_paper_ids=[...]`. UI shows it in a "Resolved elsewhere" lane,
   doesn't count toward score. Preserves user history if they had shortlisted
   the resolved direction.
4. Otherwise, emit a fresh candidate:
   - `gap_ids = [gap.id]`
   - `paper_ids = gap.related_paper_ids`
   - `title_hint = gap.description`
   - `lineage_key = sha1("gap-driven" + normalize(gap.description))`

**Pass 2 — contradiction-driven**
For each `contradiction` in scope with `status='candidate'` and
`same_task=1 AND (same_dataset=1 OR same_metric=1)`, produce one candidate:
- `contradiction_ids = [c.id]`
- `claim_ids = [c.claim_a_id, c.claim_b_id]`
- `paper_ids = <papers of both claims>`
- `lineage_key = sha1("contradiction" + normalize(c.task) + normalize(c.metric))`

**Pass 3 — method-transfer**
Group `normalized_claims` by `method`. For any method used ≥ 5 times in
scope A but ≤ 1 time in scope B (where B is a sibling topic in the same
domain), produce a candidate for scope B:
- `claim_ids = <the 5+ in-method claims from A>`
- `paper_ids = <their paper_ids>`

Cap total candidates at **50 per scope** before merge.

### 4b — Merge + dedup

Two candidates `x`, `y` merge if **either**:
1. They share any `gap_id` or `contradiction_id` — typed identity link, always
   merge.
2. `jaccard(x.paper_ids, y.paper_ids) ≥ 0.5`
   **AND** `cosine(title_hint_x, title_hint_y) ≥ 0.6`
   — containment alone over-merges (a 20-paper survey would swallow a 3-paper
   subset with a different contradiction); real Jaccard + title similarity is
   stricter.

Evidence sets are unioned on merge. Merged candidate's `lineage_key` comes from
the candidate with the **largest** primary-signal evidence set (ties broken by
lowest gap/contradiction id for determinism).
`evidence_signature = sha1(sorted(gap_ids) + sorted(contradiction_ids) + sorted(claim_ids))`.

Cap post-merge at **20 candidates per scope**.

### 4c — Scoring formula

Every dimension is normalized to `[0, 1]` before combination.

Let:
- `evidence_paper_count` = `|paper_ids|` on the candidate (post-merge), **not** the full scope count.
- `scope_paper_count` = papers in the whole scope (still useful for feasibility).
- `severity_w(gap)` = `{high: 1.0, medium: 0.5, low: 0.2}`.

```
novelty     = min(1, Σ severity_w(gap) for gap in evidence)
              / max(1, log2(2 + evidence_paper_count))

feasibility = min(1, scope_paper_count / 20)
              × venue_quality(top-3 venues in scope)        -- 0..1, see below
              × (1 − 0.3 × stale_fraction)                   -- gaps older than 180d

impact      = 0.4 × min(1, citation_median_in_scope / 50)
            + 0.4 × min(1, contradiction_count × 0.33)
            + 0.2 × min(1, top_venue_freq)

-- v0.4.0 momentum (no citation history yet):
momentum    = clip(0, 1, 0.5 + 0.5 × tanh(velocity_yoy))   -- papers YoY velocity, on evidence paper subset

-- v0.4.2 momentum (after citation_snapshots table exists):
momentum    = clip(0, 1, 0.5 + 0.5 × tanh(velocity_yoy))
              × (1 + mean(relative_citation_gain)) / 2

score_total = round(10 × max(ε, novelty) × max(ε, feasibility)
                       × max(ε, impact) × max(ε, momentum), 2)
```

`ε = 0.1` (same as publishability). Product not sum — any near-zero dimension
drags the score down; that's the gate.

**Why `novelty` uses evidence_paper_count** (codex round 1): using scope paper
count hurt mature topics — 200 scope papers + 3 high gaps would cap novelty at
`1/log2(202) ≈ 0.13`. The useful signal is "how many papers *already address
this specific direction*", which is `evidence_paper_count`.

`venue_quality` uses `venue_ranks`:
`A* → 1.0, A → 0.8, B → 0.5, C → 0.3, unranked → 0.4` (assume middle).

**Confidence level assignment** (influences sort order, not score value):
- `confidence_level = 'low'` if `scope_paper_count < 10` OR `evidence_paper_count < 3` OR `avg(claim.confidence) < 0.4` on supporting claims.
- `confidence_level = 'high'` if `evidence_paper_count ≥ 10` AND `avg(claim.confidence) ≥ 0.7`.
- else `normal`.

Low-confidence candidates are shown but hide the numeric score and sort into a
separate lane (see §6).

**Why these weights**: starting anchor values. Need empirical calibration once
we have a 30+ researcher-labeled anchor set — same playbook as the rubric
calibration (§`rubric_calibrations`).

### 4d — Narration (LLM, optional)

**Inputs to prompt**: for each evidence atom, include
(a) its immutable id (opaque reference), and
(b) bounded, **quoted** source text — `gap.description` (first 400 chars),
`claim.claim_text` (first 200 chars per claim, capped at 10 claims),
`paper.title + venue + year` (up to 10 papers). Plus scope label.

**Output accepted**: `{title ≤ 80 chars, pitch ≤ 240 chars, llm_risks[0..3]}`.

**Output rejected**: any numeric field, any generated id (even if the LLM
repeats one of the input ids — we only trust ids that came from the
deterministic stage). If the response is malformed or exceeds budget, fall
back to a rule-templated title:
`"{primary_gap_description} (+{count-1} related gaps)"` for Pass 1,
`"Resolving {task} contradiction on {metric}"` for Pass 2.

Tier: `light` by default (Haiku), per-call cost < $0.002. Cap per refresh: $0.20 /
scope — if exceeded, remaining candidates use templated titles.

### 4e — Persistence

```python
def upsert(candidate: Candidate) -> int:
    # lineage_key is the identity; evidence_signature triggers score refresh
    existing = conn.execute(
        "SELECT id, status, evidence_signature FROM research_candidates "
        "WHERE scope=? AND lineage_key=?",
        (candidate.scope, candidate.lineage_key),
    ).fetchone()
    if existing:
        if existing["evidence_signature"] == candidate.evidence_signature:
            # nothing changed; keep timestamps stable
            return existing["id"]
        # evidence changed — update content but preserve user's status
        conn.execute(
            "UPDATE research_candidates "
            "SET title=?, pitch=?, score_total=?, score_novelty=?, "
            "    score_feasibility=?, score_impact=?, score_momentum=?, "
            "    confidence_level=?, evidence_gap_ids=?, "
            "    evidence_contradiction_ids=?, evidence_claim_ids=?, "
            "    seed_paper_ids=?, why=?, risks=?, "
            "    evidence_signature=?, updated_at=datetime('now') "
            "WHERE id=?",
            (..., existing["id"]),
        )
        return existing["id"]
    return conn.execute("INSERT ...").lastrowid


def sweep_stale(scope: str) -> None:
    """Post-refresh pass — validate evidence ids against source tables."""
    rows = conn.execute(
        "SELECT id, status, evidence_gap_ids, evidence_contradiction_ids, "
        "       evidence_claim_ids FROM research_candidates WHERE scope=?",
        (scope,),
    ).fetchall()
    for r in rows:
        missing = _find_deleted_ids(r)  # queries gaps/contradictions/claims tables
        if not missing:
            continue
        if r["status"] == "candidate":
            # unacted → safe to delete
            conn.execute("DELETE FROM research_candidates WHERE id=?", (r["id"],))
        else:
            # shortlisted / promoted / dismissed → keep history, mark stale
            conn.execute(
                "UPDATE research_candidates "
                "SET stale_reason='orphaned_evidence', updated_at=datetime('now') "
                "WHERE id=?",
                (r["id"],),
            )
```

**Why active validation instead of timestamp comparison** (codex round 1): the
draft had `updated_at < generated_at` as the orphan detector, but `updated_at`
is bumped on every refresh, making the predicate always false. Active scan
over the JSON id arrays is cheap (O(candidates × ids_per_candidate)) and
definitive.

---

## 5. API surface

All under `/api/recommendations` in `research_harness_mcp/http_api.py`.

```
GET  /api/recommendations?scope=topic:42&status=candidate&limit=20
     → RecommendationList
     — Sort order: ORDER BY
         (confidence_level = 'low') ASC,     -- high/normal first
         (stale_reason IS NOT NULL) ASC,     -- fresh first
         score_total DESC
     — This guarantees a low-confidence 4-paper niche does NOT get buried
       under a 9-paper candidate just because the score is hidden in the UI.

POST /api/recommendations/refresh
     body: { "scope": "topic:42", "tier": "standard", "with_narration": false }
     — Sync when with_narration=false (expected runtime < 2s for typical scope):
         → 200 { "refreshed_at", "candidate_count", "candidates": [...] }
     — Async (202 + async_jobs) only when with_narration=true, OR when invoked
       by nightly cron (no user in loop):
         → 202 { "job_id": "rec-refresh-abc" }
     — Mirrors the existing `POST /api/domains/trends/refresh` sync model
       (http_api.py:2314) rather than inventing a new polling surface.

PATCH /api/recommendations/{id}
     body: { "status": "shortlisted" | "dismissed" }
     → 200

POST /api/recommendations/{id}/promote
     → creates a new topic brief draft (orchestrator_init payload),
       status → "promoted"
     → 201 { "topic_brief_artifact_id": N }
```

No breaking changes to existing endpoints. `domain_trends` stays as-is (still
used by the landscape view); recommendations are a new surface.

---

## 6. UI — `/research/recommendations`

```
┌───────────────────────────────────────────────────────────────────┐
│ Research > Recommendations                [ Scope: Topic ▾ ] [⟳] │
├───────────────────────────────────────────────────────────────────┤
│  Filter:  [min score ━━━●─── 6.0]  [ show dismissed ]             │
├─────────────────────────────────────────────┬─────────────────────┤
│ CANDIDATES                                  │ SHORTLIST (max 5)   │
│                                             │                     │
│ ┌─────────────────────────────────────────┐ │ 1. RLHF robustness  │
│ │ 7.8  Retrieval-augmented RLHF robustness│ │    [ Open brief → ] │
│ │      for small LMs                      │ │                     │
│ │ ───────────────────────────────────────│ │ 2. Method-transfer  │
│ │ Nov ▇▇▇▇▇░  Feas ▇▇▇▇░  Imp ▇▇▇▇▇  Mom│ │    Diffusion→Graph  │
│ │                                         │ │    [ Open brief → ] │
│ │ Based on:                               │ │                     │
│ │  • 3 unresolved gaps  [gap #42 #51 #77]│ │                     │
│ │  • 2 contradictions   [claim #12 ↔ #19]│ │                     │
│ │  • 14 supporting papers                │ │                     │
│ │                                         │ │                     │
│ │ Why?                                    │ │                     │
│ │  ▪ Unresolved gap (high severity)       │ │                     │
│ │  ▪ Contradiction on ROUGE-L same task  │ │                     │
│ │  ▪ Citation momentum: +0.42 relative   │ │                     │
│ │                                         │ │                     │
│ │ Risks:                                  │ │                     │
│ │  ▪ Thin literature (4 papers in scope) │ │                     │
│ │  ▪ LLM: dataset availability uncertain │ │                     │
│ │                                         │ │                     │
│ │  [+ Add to shortlist]  [✕ Dismiss]      │ │                     │
│ └─────────────────────────────────────────┘ │                     │
│ ┌─────────────────────────────────────────┐ │                     │
│ │ 7.1  ...                                │ │                     │
│ └─────────────────────────────────────────┘ │                     │
└─────────────────────────────────────────────┴─────────────────────┘
```

**Interaction specifics**:

- **Every evidence chip is clickable** → `gap #42` opens the GapDetail popover;
  `claim #12` opens the claim's paper in `PaperDrawer`; `14 papers` expands
  inline into a list of paper titles.
- **Score dimension bars use the same 0–1 scale** — consistent with the
  landscape view's publishability bars. Tooltip shows the raw number.
- **Dismiss is persistent** (`status='dismissed'`) and is remembered across
  refreshes (UPSERT preserves status). "Show dismissed" toggles visibility.
- **Promote action** opens a side panel with the auto-generated topic brief
  (markdown preview) before committing — user can edit the brief before the
  new topic is created.
- **Empty state**: *"No candidates yet. Run `gap_detect` and
  `claim_extract` on at least one topic in this scope, then refresh."* — with
  a direct button to trigger those primitives on the currently-selected topic.

---

## 7. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **GIGO** — candidate quality is hard-bounded by claim/gap extraction quality. | High | (1) Show evidence counts + average claim confidence on every card. (2) Gate candidate visibility on `min_evidence_count=3` by default. (3) Feed `dismissed` candidates into a nightly job that de-weights the corresponding extraction rules. |
| **Score gaming** — a user who extracts more claims gets higher scores, incentivizing volume over quality. | Medium | Use `log` / `tanh` rather than raw counts in formula. Cap per-dimension contribution. Require confidence ≥ 0.5 claims to count at full weight. |
| **Cold start** — topic with < 10 papers produces noisy scores. | Medium | Deterministic rule: `confidence_level='low'` when `scope_paper_count < 10` OR `evidence_paper_count < 3` OR `avg(claim.confidence) < 0.4`. API orders low-confidence after normal/high so they don't compete head-to-head; UI hides the numeric rank-score and shows only evidence counts + a "Add more literature for reliable scoring" banner. Threshold `10` is a sensible default anchor; tune once calibration data exists (same playbook as `rubric_calibrations`). |
| **Seed contamination** — recommending candidates whose only evidence comes from editorial seed data. | Low | Tag `source='seed'` when any seed paper contributes, filter out of top-5 by default. |
| **LLM hallucinates fake gap ids** in narration. | Low | Narration prompt only sees evidence id list as an opaque reference, not described content. Ids in narration output are ignored — only `title`, `pitch`, `llm_risks` are persisted. |
| **Stale candidates** — old candidates lingering after evidence invalidated. | Medium | `sweep_stale(scope)` (§4e) actively re-validates evidence ids against source tables: deletes unacted candidates with orphan evidence, marks shortlisted/promoted ones with `stale_reason='orphaned_evidence'` (history preserved, UI shows stale badge). Separately, Pass 1 tags candidates with `stale_reason='resolved_by_paper'` when a newer paper already matches the gap description (cosine ≥ 0.4). |
| **Privacy / scope leakage** — candidate generated in `topic:1` references claims from a sibling `topic:2` the user doesn't own (future multi-user). | Low today (single-user local DB) | Defer until v0.5 when user auth lands. |

---

## 8. Phased delivery plan

### v0.4.0 — MVP (target: 2 weeks)
- Migration 043 + `research_candidates` table (incl. `lineage_key` / `evidence_signature` split + `confidence_level` + `stale_reason`)
- Seeding passes 1 & 2 (gap-driven, contradiction-driven) — **not** method-transfer
- Deterministic scoring, **momentum without citation gain** (velocity_yoy on evidence paper subset only)
- **Rule-templated titles only** (no LLM narration)
- API: `GET /api/recommendations` (sorted by confidence × score × freshness), `POST /api/recommendations/refresh` (sync 200), `PATCH`
- UI: candidate list (two lanes: normal/high vs low-confidence) + shortlist column, no Cytoscape, no promote-to-brief
- `sweep_stale()` runs at the end of every refresh
- Tests: 20+ Pytest cases covering seeding determinism, dedup (Jaccard + title-cosine), scoring edge cases (mature-topic novelty no longer underflows), scope isolation, UPSERT preserves status when only evidence changes, sweep deletes vs marks correctly
- No backend LLM call on the hot path — page loads from DB

**Exit criteria**: on a topic with ≥ 20 papers and ≥ 5 gaps, generates ≥ 3
non-trivial candidates, each with ≥ 2 evidence atoms. User can dismiss /
shortlist / refresh without errors. tsc + ruff + pytest clean.

### v0.4.1 — LLM narration (target: +1 week)
- Narration step (4d) with Haiku default, cost cap
- Templated titles become fallback only
- Shortlisted card gets a **richer pitch** (LLM expands 2 sentences → 5)

### v0.4.2 — Transfer candidates + citation momentum + relation graph (target: +2 weeks)
- **New table `citation_snapshots(paper_id, citation_count, observed_at)`** +
  nightly job to populate it (Semantic Scholar batch lookup, cached)
- Enable `relative_citation_gain` term in momentum (prerequisite: 2+ snapshots
  per paper)
- Seeding pass 3 (method-transfer) — try lexical `normalized_claims.method`
  match first; only fall back to `taxonomy_assignments` if false-positive
  rate > 20% on dogfood data
- Optional Cytoscape.js overlay showing candidate ↔ candidate overlap (shared
  evidence) so users don't shortlist 3 candidates that are really the same
  direction

### v0.5 — Promotion to orchestrator (target: post-v0.4.2)
- `POST /api/recommendations/{id}/promote` generates a topic brief. Evidence
  maps into brief fields deterministically:

  | Evidence type | Brief field |
  |---|---|
  | `gaps` (description + severity) | `motivation` (problem statement) + `open_questions` |
  | `contradictions` (claims + task + metric) | `hypothesis` + `falsification_target` |
  | `claim_citations` → papers | `baseline_papers` (with venue, year, citation_count) |
  | `normalized_claims` (metric + dataset) | `success_criteria` (metric names, dataset names to match/beat) |
  | `risks` atoms | `assumptions` (things the research must hold true) |
  | scope label (`domain:N` / `topic:N`) | `parent_domain` / `parent_topic` |

  LLM is used only to **paraphrase per-field** (preserve numbers / ids); the
  brief is shown as editable markdown before committing to `orchestrator_init`.
  A contradiction-only candidate therefore gets a hypothesis + falsification
  target without fabricating a fake motivation paragraph.

- Closes the loop: recommendation → topic → run → new claims/gaps → next
  recommendation.

---

## 9. Open questions for review

1. **Is the deterministic/LLM split correct?** — Concrete proposal: LLM only
   produces `title`, `pitch`, `llm_risks`. All numbers deterministic. Keeps the
   v0.3.0 publishability-formula lesson: any float that came from an LLM is an
   attack surface for trust.
2. **Is the ε-floor weighted product the right composite?** — Same shape as
   `compute_publishability`. Alternative: weighted sum with per-dimension floor.
   Product is stricter (good, but can be too punishing if `feasibility` is
   capped by thin literature).
3. **Should we cap candidates per scope at 20 post-merge, or let the UI
   filter?** — Argue for cap at source: SQLite writes and signature computation
   are cheap, but the UI risk is "50 candidates, no one reads past 10". Cap
   keeps the user focused.
4. **Auto-refresh cadence?** — Proposal: nightly (cron, async_jobs), plus
   on-demand button. No auto-refresh on every page load (expensive if
   narration is on).
5. **Method-transfer false-positive rate** — method name matching (`method`
   column) is lexical. May need `taxonomy_assignments` as the join key instead
   to reduce "Transformer vs. transformer-XL" conflations. Defer to v0.4.2
   once MVP is real.
6. **Multi-scope candidates** — A contradiction that spans two topics: does it
   produce one `scope=domain:N` candidate, or two `scope=topic:*` candidates?
   Proposal: prefer domain-scope when evidence spans ≥ 2 topics in the same
   domain; otherwise topic-scope.

---

## 10. Non-goals

- **Not** a paper-recommender (we're not Semantic Scholar).
- **Not** an LLM-powered "write me a research proposal" chatbot.
- **Not** replacing `direction_ranking` — the primitive stays as the narration
  step inside 4d.
- **Not** a global "best research topics in CS" leaderboard — recommendations
  are always scoped, always grounded in *this user's* extracted knowledge.

---

## 11. Review resolution log

### Round 1 — codex-rescue (2026-04-23)

| # | Issue | Resolution | Section |
|---|---|---|---|
| 1 | `novelty` divisor used whole-scope paper count → mature topics collapsed | Switched divisor to `evidence_paper_count` with `max(1, …)` guard | §4c |
| 2 | Cold-start sort order silently buried low-confidence candidates | Added `confidence_level` column; explicit multi-key sort (confidence, stale, score); UI two-lane layout | §3 §5 §6 §7 |
| 3 | Pass 1 unresolved-gap semantics ambiguous on ingest-later papers | Use `max(paper_topics.created_at, papers.created_at)`; cosine ≥ 0.4 tags `stale_reason='resolved_by_paper'` rather than hides | §4a |
| 4 | "Jaccard" rule was actually containment, over-merged surveys | Real Jaccard ≥ 0.5 **AND** title cosine ≥ 0.6, OR shared typed id | §4b |
| 5 | `UNIQUE(scope, signature)` lost user status when evidence grew | Split into stable `lineage_key` + content `evidence_signature`; UPSERT on lineage, refresh scores on signature change | §3 §4a §4e |
| 6 | `202 + async_jobs` overkill for sub-2s MVP refresh | Sync 200 for `with_narration=false`; async only for narration / nightly | §5 |
| 7 | Stale predicate `updated_at < generated_at` was backwards | Added active `sweep_stale(scope)` that walks evidence ids against source tables | §4e §7 |
| 8 | Promote-to-brief mapping was hand-wavy | Added deterministic `evidence type → brief field` table | §8 |
| 9 | §4d / §7 conflicted on what the LLM sees | LLM sees bounded quoted text + immutable ids; only free-text fields accepted, generated ids/numbers rejected | §4d |
| 10 | `relative_citation_gain` assumed a citation_snapshots table that doesn't exist | Deferred to v0.4.2 behind new `citation_snapshots` table; v0.4.0 momentum uses velocity only | §2 §4c §8 |

**Divergent (codex agreed)**: taxonomy deferred to v0.4.2, product form OK, four dimensions are the right MVP cut.

**Repo-drift fix**: `project_artifacts` is created in migration 006, not 039; only `claims` / `claim_citations` were added in 039.
