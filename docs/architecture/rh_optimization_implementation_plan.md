# RH Optimization Master Plan (Backend + Frontend)

> Status: **Approved v2** (Claude × Codex second re-audit, 2026-04-24)
> Supersedes: v1 (2026-04-24 morning) which had critical architectural flaws
> Source report: `docs/architecture/rh-optimization-insights-v2.md`

## Why v1 Was Rejected

The v1 plan had three fatal assumptions that did not match the actual codebase:

1. **Wrong integration point for section-loop changes.** v1 said "wire `draft_with_review_loop()` into the main path via `loops.py:run_section_loop()`". In reality **neither function has any callsite in the repo**. The real write path is `auto_runner/stage_executor.py` → `auto_runner/runner.py`. v1 would have wired changes into dead code.
2. **Overlapping gate logic.** v1's `should_execute()` duplicated `TransitionValidator.can_advance()` and `GateEvaluator.evaluate()` and was inserted in the wrong layer (transition, not execution).
3. **Greenfield illusion.** Phase 0.2 (`check_stage_budget`) and Phase 0.3 (`Claim` schema + modality) already exist in code — the work is integration/backfill, not new design.

Additional bounded-cost, migration, and validation gaps are fixed below.

---

## Codebase Anchor Points (verified 2026-04-24)

| Component | File:Line | Status |
|---|---|---|
| `Claim` dataclass with `claim_id`, `modality`, `evidence_spans` | `packages/research_harness/research_harness/primitives/types.py:130` | Exists |
| Migration 050 (modality columns on `claims`) | `packages/research_harness/migrations/050_claim_modality.sql` | Exists, not backfilled |
| `claim_extract()` — assigns all input papers to every claim | `execution/llm_primitives.py:911` | Needs per-claim attribution |
| `write_claim()` — inserts only old columns | `orchestrator/claims.py:14` | Needs modality/spans write |
| `check_stage_budget()` + default budgets | `token_accounting.py:248` | Exists, not wired to runner |
| `run_section_loop()` — 3-round LLM review loop | `execution/loops.py:48` | No callsite |
| `draft_with_review_loop()` — deterministic revise loop | `execution/llm_primitives.py:1640` | No callsite |
| Real write path | `auto_runner/stage_executor.py`, `auto_runner/runner.py:192` | Uses primitive directly |
| `TransitionValidator.can_advance()` | `orchestrator/transitions.py:45` | Checks from_stage artifacts |
| `GateEvaluator.evaluate()` | `orchestrator/transitions.py:134` | Checks stage gate |
| `OrchestratorService.advance()` | `orchestrator/service.py:488` | Transition function, not planner |
| Action-toolbar bug `/gate-check` | `web/src/components/topic/action-toolbar.tsx:56` | Should be `/gate` |
| `fetchTopicPapers` `page_size` param mismatch | `web/src/lib/api.ts:116–120` | Should remap to `per_page` |
| No SSE/WebSocket backend routes | — | Polling required |
| `cmdk` installed but unused | `web/src/components/ui/command.tsx` | No page imports |

---

## Final Ship Order (10 steps, interleaved backend + frontend)

### Step 1 — Frontend Immediate Fixes
**Duration**: half day | **Owner**: frontend | **Unblocks**: everything else

- Fix `action-toolbar.tsx:56` `/gate-check` → `GET /api/topics/{id}/gate`
- Fix `api.ts:116-120` `fetchTopicPapers` to remap `page_size` → `per_page` (same as `fetchPapers`)
- Add `/budgets` to sidebar nav (`components/layout/sidebar.tsx`)
- Dedupe inline API helpers in `action-toolbar.tsx`, `paper-search-panel.tsx`, `analysis-panel.tsx` into `lib/api.ts`
- Confirm short-polling approach: use TanStack Query `refetchInterval: 2000` where progress visibility is needed (do NOT add SSE)

**Acceptance**: all four items in one PR, no visible behavior regression, `/budgets` reachable via sidebar.

---

### Step 2 — Backend Architecture Resolution (Design PR)
**Duration**: 1 day design + review | **Owner**: backend | **Blocks**: Steps 3, 5

Three architectural decisions, no code changes:

1. **Section-loop consolidation**
   - Keep `run_section_loop()` as the **only** outer controller (draft → review → revise)
   - Fold `run_all_checks()` into that loop as a pre-review deterministic sub-check (short-circuit: if deterministic checks fail hard, revise before the LLM review call)
   - Deprecate `draft_with_review_loop()` — rename to `_deterministic_revision_helper()` or delete if unused after consolidation
   - **Wire `run_section_loop()` into the real path**: `auto_runner/stage_executor.py` for the `write` stage, replacing any direct `section_draft()` calls

2. **`should_execute()` ownership**
   - Lives in `auto_runner/stage_policy.py` (not `OrchestratorService.advance()`)
   - Returns `(should_run, reason)` — `reason` is one of `{fresh_artifact_present, gate_already_passed, resumed_past_stage, deliberation_said_skip, run}`
   - Called by `auto_runner/runner.py` **before** invoking the primitive, **not** by `advance()`
   - Existing `TransitionValidator` and `GateEvaluator` remain unchanged — they are post-execution gates, not pre-execution planners

3. **Claim persistence path alignment**
   - `claim_extract()` must assign **per-claim** `paper_ids` (currently assigns all input papers to every claim)
   - `claim_extract()` must populate `modality` and `evidence_spans` from LLM output
   - `write_claim()` must insert the new columns added by migration 050
   - Backfill script: for existing rows, default `modality='text'`, `evidence_spans=[]`, `claim_uuid=hash(content)`

**Acceptance**: Written as an ADR in `docs/architecture/adr/` with diagrams. Codex or second reviewer signs off before Step 3.

---

### Step 3 — Backend Low-Risk Enablers
**Duration**: 3-4 days | **Owner**: backend | **Depends**: Step 2

Three parallel tasks:

#### 3.1 Wire existing stage budget into runner
- `auto_runner/runner.py` — call `check_stage_budget(topic_id, stage)` from `token_accounting.py:248` before each stage invocation
- Emit soft warning via decision_log when >80% of cap
- Block with clear error when hard cap exceeded (configurable via env `RESEARCH_HARNESS_STAGE_BUDGET_ENFORCE=soft|hard`)
- No new tables; reuse existing `budgets` + `stage_budgets` if present, else JSON config

#### 3.2 Claim persistence + backfill
- Apply Step 2.3 decisions: update `claim_extract()` and `write_claim()`
- New script `packages/research_harness/scripts/backfill_claim_modality.py`
- Add test verifying existing claims still load and new claims carry modality/spans

#### 3.3 Citation-sentence evidence coverage (replaces "70% boilerplate" metric)
- `SectionDraftOutput.evidence_map: list[EvidenceMapping]` (sidecar, not inline)
- Acceptance rule: **every sentence containing a citation marker (`\cite{}`, `[N]`, `(Author, Year)`) must have a matching `EvidenceMapping` entry**
- No "boilerplate detection" — testable by regex on citation markers
- `orchestrator/invariants.py` — add `check_citation_sentence_evidence_coverage()`

**Acceptance**: tests pass; `gap_detect` on one existing topic shows budget-warning logged when near cap; an old claim from migration 050 loads without error; a new section_draft output has evidence_map covering all citation-marked sentences.

---

### Step 4 — Frontend Tier 1 (existing endpoints only)
**Duration**: 1 week | **Owner**: frontend | **Depends**: Step 1 merged; can run parallel to Step 3

#### 4.1 Write Stage Panel
- New tab "Write" on topic detail page alongside existing Analysis tab
- Uses existing backend endpoints `POST /api/topics/{id}/outline`, `POST /api/topics/{id}/section-draft` (already defined, never called)
- Outline: trigger → editable textarea → approve-and-lock
- Sections: click section from outline → draft → show draft text + evidence sidecar (will be empty until Step 3.3 ships; still render the container)
- Self-refine round indicator (round 1/2/3) populated from primitive output once Step 5 lands

#### 4.2 Per-topic cost card
- On topic detail page, new card showing:
  - Total tokens spent (from `token_ledger` aggregated via existing `/api/topics/{id}/events` or new `/api/topics/{id}/cost` lightweight endpoint)
  - Per-stage breakdown (bar chart, recharts)
  - Last run elapsed time
- Reuses `fetchProvenanceSummary` (already in `api.ts`, never called)

**Acceptance**: user can generate an outline, draft a section, and see total spent, all without entering terminal. Works against current backend even before Step 5.

---

### Step 5 — Backend Reliability (Bounded Verification + Adversarial Review)
**Duration**: 1 week | **Owner**: backend | **Depends**: Step 3

#### 5.1 Bounded claim verification
- New `execution/claim_verification.py`
- **Candidate pair selection** (deterministic prefilter, required):
  - Group claims by shared `normalized_claims` fields (method / task / dataset / entity overlap)
  - Only compare claims within same group
  - Hard cap: ≤200 LLM pair-check calls per topic (split across groups proportionally)
- **Per-pair check**: single LLM call asking "do these two claims contradict?" → `(contradicts: bool, reason: str)`
- **Modality detection**: regex + LLM confirmation; set `needs_human_review=true` when evidence depends on figure/table/equation
- **Mode**: advisory by default (scores logged, shown in UI); strict mode opt-in via env flag
- Stored as `ClaimVerificationResult` records linked to claim_id

#### 5.2 Adversarial weakness review (replaces v1 Phase 2.2)
- Prompt structure alone is insufficient (LLM optimism bias). Implementation:
  - **Second independent pass**: after `section_review()`, run `adversarial_review()` with a different system prompt persona (skeptical reviewer), different model if available (via `llm_router` tier override)
  - Output: structured weaknesses JSON (categories: experimental_design, baseline_fairness, statistical_significance, limitation_discussion, novelty_claim, reproducibility)
  - Each weakness must cite concrete text or concrete absence
  - Critical severity auto-opens `review_issues` row
- Not a gate — advisory in UI until human-verified on 5 topics

**Acceptance**: verification cost stays under 200 LLM calls per topic regardless of claim count; adversarial review finds ≥1 weakness that `section_review()` missed on 3/5 test topics.

---

### Step 6 — Frontend Tier 2 (follows backend)
**Duration**: 1 week | **Owner**: frontend | **Depends**: Steps 3.3, 5.1

#### 6.1 Evidence / Provenance Viewer
- On Write Stage Panel, render `evidence_map` sidecar: sentence → source paper card with relation_type badge
- Click a citation-marked sentence → highlights corresponding evidence entry
- Coverage indicator: "X of Y citation sentences have evidence mapping" (based on Step 3.3 invariant)

#### 6.2 Claim Verification Dashboard
- New tab "Claims" on topic detail page
- Claim cards with badges: consistency_score, grounding_score, modality_flags
- `needs_human_review=true` → prominent warning badge
- Contradicting-pair viewer: list of detected contradictions with both claim texts and reason
- Advisory, not blocking

**Acceptance**: user can verify section-level evidence coverage; user can see which claims need human attention and why.

---

### Step 7 — Embedding Service Prerequisite
**Duration**: 2-3 days | **Owner**: backend | **Blocks**: Step 8

v1 assumed embeddings existed. They do not. Options:

- **A (preferred)**: thin wrapper over an API-based embedding (OpenAI `text-embedding-3-small`) with SQLite-backed cache keyed by content hash
- **B (fallback)**: bring `sentence-transformers` from stub to real in `trends/pipeline.py` and expose as `research_harness.embeddings.embed(texts)`

Either way, a reusable `embed_texts(texts: list[str], tier: str = 'light') -> list[list[float]]` function must exist with cost accounting integrated into `token_accounting.py`.

**Acceptance**: unit test embeds 3 strings, returns vectors of expected dim, cached on second call.

---

### Step 8 — Workflow Memory (Metadata-First)
**Duration**: 4-5 days | **Owner**: backend | **Depends**: Step 7

- `packages/research_harness/research_harness/memory/workflow_memory.py`
- **Metadata retrieval first** (no embeddings needed for v1):
  - Filter: successful runs, last 90 days, same domain
  - Rank by: recency × quality_score
  - Top-k returned
- **Semantic reranking** (uses Step 7):
  - Embed task description; cosine similarity rerank top-k from metadata filter
  - Never used as primary retrieval — only to break ties
- **Storage**: reuse `provenance_records`, `decision_log`, `session_observations` — no new tables for v1
- **Usage**: `suggest_config(task_description, topic_id)` returns advisory recommendation (stage sequence + estimated cost); never auto-applied

**Acceptance**: after 2 completed runs, `suggest_config()` returns a sensible recommendation on a 3rd similar topic; tests verify no auto-application.

---

### Step 9 — Frontend Workflow Memory UI
**Duration**: 3 days | **Owner**: frontend | **Depends**: Step 8

- New card on Topic Creation Wizard Step 4: "Similar past runs" with recommended stage config + cost estimate
- On Topic Detail Page: run history panel (list past orchestrator runs with cost / duration / quality)
- "Use this config" button → applies as topic overrides (advisory, user confirms)

**Acceptance**: creating a new topic in a domain with 2+ past runs shows at least one suggestion.

---

### Step 10 — DAG Pilot (Last, with Ground Truth)
**Duration**: 1-2 weeks | **Owner**: backend + human rater | **Depends**: Step 5 validated

- `execution/dag_reasoning.py`
- `gap_detect_dag()` as **opt-in** mode (env flag `RESEARCH_HARNESS_GAP_DAG=1` or explicit arg)
- **Scope**: topics with ≥20 papers
- **New artifact**: `gap_decomposition` in `ARTIFACT_SCHEMAS`

**Ground-truth protocol (required before any rollout)**:
1. Pick 3 topics with **known** gaps (use existing topics where the human researcher already identified gaps not found by current `gap_detect`)
2. Run DAG mode and single-pass mode on all 3
3. Human rater (not Claude, not Codex) evaluates each produced gap: `{real, hallucinated, already_known}`
4. Pass criteria: DAG mode must find ≥1 `real` gap that single-pass missed across the 3 topics, AND ≤10% `hallucinated` rate

**Acceptance**: human-rater protocol complete; decision logged; promoted to default only if pass criteria met.

---

### Deferred — `cmdk` Command Center
Not in this plan. Current product is topic-centric; global palette has low value. Revisit after Step 9 ships.

---

## Updated Rollout Success Criteria

| Metric | Definition | Baseline | Target |
|--------|-----------|----------|--------|
| Citation-sentence evidence coverage | sentences w/ citation marker that have `EvidenceMapping` entry / total | 0% (metric doesn't exist) | 100% on new drafts |
| Stage skip rate on simple tasks | stages auto-skipped on 5 known-simple tasks | 0 | ≥1 per task |
| Per-stage hard cap breaches | stages that hit hard cap per week | unknown (not tracked) | 0 after Step 3.1 |
| Claim cross-consistency issues found | contradictions detected per topic (bounded ≤200 pair checks) | 0 | ≥1 on topics with ≥20 claims |
| Adversarial review unique findings | weaknesses found by adversarial pass not found by `section_review` | 0 | ≥1 on 3/5 test topics |
| DAG real-gap recall | real gaps found by DAG missed by single-pass (human rated) | — | ≥1 across 3 topics |
| DAG hallucination rate | hallucinated gaps / total DAG gaps (human rated) | — | ≤10% |
| Workflow memory suggestion quality | sensible recommendations on 3rd similar topic | — | subjective pass on 3/3 |

Baselines captured by new `packages/research_harness/research_harness/eval/baseline.py` during Step 3, running against 3 existing completed topics.

---

## Dependencies & Risks (Updated)

| Risk | Mitigation |
|------|-----------|
| v1 architectural confusion repeats | Step 2 is an ADR signed off before any code |
| Section-loop wire-up misses real path | Step 2.1 explicitly targets `stage_executor.py` + `runner.py`, not `loops.py` alone |
| Claim backfill breaks old data | Step 3.2 ships a script with a dry-run mode; tests cover old-schema reads |
| Pairwise claim verification cost blowup | Step 5.1 hard-caps at 200 LLM calls per topic with deterministic prefilter |
| Adversarial review is just "negative prompt" | Step 5.2 requires second pass with different persona AND structured output AND cross-validation on 5 topics |
| Embedding service missing | Step 7 is a prerequisite for Step 8 |
| DAG mode looks good but hallucinates | Step 10 requires human-rater protocol before any default-on rollout |
| SSE drift | Not in plan; polling only |
| Frontend ahead of backend | Tier 2 frontend work waits for backend Step 3.3 / 5.1 to ship |

---

## Consolidated Timeline

```
Week 1:  Step 1 (FE fixes, 0.5d) + Step 2 (backend ADR, 1d) + Step 3 start (2d)
Week 2:  Step 3 finish (2d) + Step 4 Write Stage + Cost Card (5d parallel)
Week 3:  Step 5 Bounded verification + Adversarial review (5d)
Week 4:  Step 6 FE evidence + claim dashboards (5d)
Week 5:  Step 7 embedding service (3d) + Step 8 workflow memory start (2d)
Week 6:  Step 8 finish (3d) + Step 9 FE memory UI (3d)
Week 7:  Step 10 DAG pilot + human-rater protocol (5-10d)
```

Each step ships independently. A step's acceptance tests must pass before the next step depending on it starts.

---

## Change Log from v1

| v1 item | v2 resolution |
|---------|---------------|
| Phase 1.1 "wire `draft_with_review_loop` into `loops.py`" | Step 2.1: one outer controller (`run_section_loop`), wired into `stage_executor.py`, `draft_with_review_loop` becomes helper |
| Phase 0.2 "new `check_stage_budget`" | Step 3.1: already exists at `token_accounting.py:248`, work is runner integration |
| Phase 0.3 "new claim schema" | Step 3.2: schema exists (migration 050), work is persistence path + backfill |
| Phase 1.2 `should_execute()` in `advance()` | Step 2.2: lives in `stage_policy.py`, called by `runner.py` before primitive |
| Phase 1.3 "70% boilerplate coverage" | Step 3.3: testable "every citation-marked sentence has evidence entry" |
| Phase 2.1 unbounded pairwise | Step 5.1: deterministic prefilter + 200-call cap |
| Phase 2.2 forced weakness JSON only | Step 5.2: separate adversarial pass + different persona + 5-topic validation |
| Phase 3.1 assumes embeddings | Step 7 added as prerequisite |
| Phase 4.1 no ground truth | Step 10: explicit 3-topic human-rater protocol |
| Frontend plan separate, with SSE | Interleaved as Steps 1/4/6/9; polling only |
| cmdk Command Center | Deferred |
