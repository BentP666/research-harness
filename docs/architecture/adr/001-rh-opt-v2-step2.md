# ADR 001: RH Optimization v2 Step 2 — Three Architectural Decisions

> **Status**: Accepted
> **Date**: 2026-04-24
> **Owner**: Claude (v2 execution) × Codex consensus
> **Supersedes**: v1 plan assumptions in `rh_optimization_implementation_plan.md`

## Context

v1 plan (morning 2026-04-24) was rejected in second audit because:
1. It wired `draft_with_review_loop()` and `run_section_loop()` changes into files
   neither of which has a callsite — the real write path is
   `auto_runner/stage_executor.py` → `tool_dispatch.py`.
2. Its proposed `should_execute()` gate was inserted inside
   `OrchestratorService.advance()` and duplicated logic already in
   `TransitionValidator.can_advance()` and `GateEvaluator.evaluate()`.
3. It treated claim schema (`modality`, `evidence_spans`) as greenfield, but
   migration `050_claim_modality.sql` and the dataclass fields already exist.
   The missing work is persistence-path alignment + backfill.

This ADR resolves all three before Step 3 code ships.

---

## Decision 1: Section-Loop Consolidation

### Current state (verified 2026-04-24)

| Function | File | Line | Callsites |
|----------|------|------|-----------|
| `run_section_loop()` | `execution/loops.py` | 48 | **none** |
| `draft_with_review_loop()` | `execution/llm_primitives.py` | 1640 | **none** |
| `section_draft()` | `execution/llm_primitives.py` | 1541 | used in `run_section_loop` + tool_dispatch |
| `section_review()` | `execution/llm_primitives.py` | 1888 | used in `run_section_loop` |
| `section_revise()` | `execution/llm_primitives.py` | 1965 | used in `run_section_loop` |
| `run_all_checks()` | `execution/writing_checks.py` | 507 | used in `draft_with_review_loop` only |

Both loop functions are **dead code** relative to the production path. The real
write-stage tool registered in `tool_dispatch.py` calls `section_draft()`
directly, one-shot, no review loop.

### Decision

1. **Canonical controller**: `run_section_loop()` in `execution/loops.py`
   - Three-phase: draft → review → revise
   - Configurable `max_rounds` and `min_score`
   - Uses existing LLM-based `section_review()` for semantic review
2. **Fold deterministic checks in**: at the start of each round's review
   phase, first call `run_all_checks()` from `writing_checks.py`. If any
   hard check (citation, word count, structure) fails, synthesize its
   failures into the review feedback stream before the LLM review is
   called. Short-circuit revision if purely deterministic.
3. **Deprecate `draft_with_review_loop()`**:
   - Rename to `_deprecated_draft_with_review_loop()` with a
     `DeprecationWarning` on first call
   - Not deleted until Step 4 ships (in case any out-of-tree caller)
4. **Wire into production path**:
   - `auto_runner/tool_dispatch.py` write-stage dispatcher routes
     `section_draft` tool calls through `run_section_loop()`
   - Behind feature flag `RESEARCH_HARNESS_SECTION_LOOP=1` initially, on
     by default for new topics
5. **Hard cap**: `max_rounds=2` in production (not 3) to respect Step 5 cost
   budget. Configurable via stage policy.

### Rejected alternatives

- **Replace `run_section_loop` with `draft_with_review_loop`**: the
  deterministic-only strategy misses semantic issues (hallucinated claims,
  weak transitions). LLM review is needed for quality.
- **Run both and pick best**: doubles cost; no clear quality arbiter.
- **Leave dead code alone**: leaves production path one-shot with no quality
  loop, which is the v1 motivation.

---

## Decision 2: `should_execute()` Ownership

### Current state

Three functions already gate the orchestrator lifecycle:

| Function | File | Purpose | Called from |
|----------|------|---------|-------------|
| `TransitionValidator.can_advance()` | `orchestrator/transitions.py:45` | "Can I move from X to Y?" (artifacts + graph edge) | `svc.advance()` |
| `GateEvaluator.evaluate()` | `orchestrator/transitions.py:134` | "Is the gate for stage Y passed?" | `svc.advance()` |
| `should_pause_human()` | `auto_runner/stage_policy.py:247` | "Does this stage need human approval before next?" | `stage_executor.py` |

These are all **post-execution** gates. There is no pre-execution planner
that asks "should we bother running this stage at all?".

### Decision

1. **New function**: `should_execute(db, topic_id, stage) -> ExecutionDecision`
   in `auto_runner/stage_policy.py`
2. **ExecutionDecision**:
   ```python
   @dataclass(frozen=True)
   class ExecutionDecision:
       should_run: bool
       reason: Literal[
           "run",                      # go ahead
           "fresh_artifact_present",   # artifacts exist, not stale, skip
           "gate_already_passed",      # gate evaluated as pass, skip
           "resumed_past_stage",       # checkpoint says we're past this
           "deliberation_said_skip",   # optional LLM advisor said skip
       ]
       advisory_notes: list[str] = field(default_factory=list)
   ```
3. **Insertion point**: `auto_runner/runner.py` main loop, **before**
   calling `execute_stage()`. If `should_run=False`, log the reason via
   `decision_log`, advance checkpoint, and call `svc.advance()` directly
   to transition state without running the stage.
4. **Checks in order**:
   - `fresh_artifact_present`: query `project_artifacts` for non-stale
     artifacts of types required by this stage (derived from
     `ARTIFACT_SCHEMAS`). If all required types present and non-stale,
     skip.
   - `gate_already_passed`: call `GateEvaluator.evaluate(topic_id, stage)`.
     If outcome is `pass`, skip.
   - `resumed_past_stage`: compare `checkpoint_data["current_stage"]`
     position in `STAGE_ORDER` vs target stage.
   - `deliberation_said_skip` (optional, light-tier LLM call; off by
     default via env flag `RESEARCH_HARNESS_DELIBERATION=1`).
5. **No change to existing gates**: `TransitionValidator` and
   `GateEvaluator` remain post-execution gates inside `svc.advance()`.
   `should_execute()` is pre-execution planner in the runner layer.
6. **Audit trail**: every skip writes a `decision_log` row with
   `checkpoint="pre_execute"`, `choice="skip_{reason}"`,
   `reasoning=advisory_notes joined`.

### Rejected alternatives

- **Put `should_execute` inside `svc.advance()`**: `advance()` is a
  transition function, not a planner. It is called both by the runner and by
  the MCP `orchestrator_advance` tool. Overloading it with pre-execution
  logic breaks the single-responsibility and creates a recursion risk.
- **Let `execute_stage()` decide to skip internally**: scatters
  decision-making across two layers (runner and executor) and makes
  testing harder.
- **Use only deterministic checks, no LLM**: v1's criticism was that
  pure LLM deliberation was unsafe. The fix is deterministic first,
  optional LLM only for ambiguous cases — which matches the codex review.

---

## Decision 3: Claim Persistence Path Alignment

### Current state

| Component | File | Status |
|-----------|------|--------|
| `Claim` dataclass with `modality`, `evidence_spans` | `primitives/types.py:130` | Exists ✓ |
| Migration 050 (`claim_uuid`, `modality`, `evidence_spans_json`, `paper_ids_json`, `confidence`) | `migrations/050_claim_modality.sql` | Exists ✓ |
| `claim_extract()` — populates `paper_ids` per claim | `execution/llm_primitives.py:911` | **Broken**: assigns all input papers to every claim (line 960) |
| `claim_extract()` — populates `modality` | `execution/llm_primitives.py:911` | **Broken**: does not read from LLM output |
| `claim_extract()` — populates `evidence_spans` | `execution/llm_primitives.py:911` | **Broken**: always empty |
| `write_claim()` — persists new columns | `orchestrator/claims.py:14` | **Broken**: inserts only old columns |
| Backfill for existing claim rows | — | **Missing** |

### Decision

1. **Prompt change**: `prompts.claim_extract_prompt()` requests claims with
   `paper_id` (singular, which paper this claim comes from),
   `modality` (text|figure|table|equation|mixed), and optional
   `evidence_spans` (list of `{paper_id, section, snippet}`).
2. **Parse change in `claim_extract()`**:
   - `paper_ids` is assigned from LLM output (`item.get("paper_id")`)
     with fallback to `paper_ids[0]` if the LLM doesn't return one
     (still better than "all input papers")
   - `modality` read from `item.get("modality", "text")`
   - `evidence_spans` parsed into `list[EvidenceSpan]`
3. **Persistence change in `write_claim()`**:
   - Accept `modality` and `evidence_spans` parameters (with sensible
     defaults for backward compat)
   - INSERT populates `modality`, `claim_uuid`, `evidence_spans_json`,
     `paper_ids_json`, `confidence` columns
   - Legacy call sites without new args still work (defaults preserve
     old behavior)
4. **Backfill script**:
   `packages/research_harness/scripts/backfill_claim_modality.py`
   - Read all rows from `claims` where `claim_uuid IS NULL`
   - Compute `claim_uuid = "claim_" + sha256(content)[:12]`
   - Set `modality = "text"` (historic default)
   - Set `confidence = 0.0` where null
   - `paper_ids_json`: if the row has `claim_citations`, join them into
     JSON array; else leave null
   - `evidence_spans_json = "[]"`
   - Dry-run mode default; `--apply` to commit
5. **Test**:
   - Verify existing `claims` rows still load after the fix (read old
     columns, default new columns)
   - Verify new `claim_extract()` call produces claims with populated
     modality + per-claim paper_ids
   - Verify `write_claim()` round-trips new columns

### Rejected alternatives

- **Drop old columns**: breaks legacy data.
- **Require all new fields on every write**: breaks out-of-tree callers
  that only pass text + paper_ids.

---

## Summary

| Decision | One-line |
|----------|----------|
| Section loop | `run_section_loop` is canonical; `run_all_checks` folded in; `draft_with_review_loop` deprecated; wired via `tool_dispatch.py` |
| `should_execute()` | Lives in `stage_policy.py`, called by `runner.py` before `execute_stage()`; deterministic first, optional LLM; does not touch `advance()` |
| Claim persistence | Fix `claim_extract()` + `write_claim()` to populate migration 050 columns; ship backfill script with dry-run default |

## Consequences

- Step 3 code proceeds with clear scope
- No changes to `OrchestratorService.advance()` logic
- No duplication of gate evaluation
- Existing claim data preserved; new claims carry richer metadata
- Section loop wired into the real production tool dispatch path
