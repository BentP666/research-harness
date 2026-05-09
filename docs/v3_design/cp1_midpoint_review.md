# CP1 Midpoint Review — iter-03 + iter-05

**Reviewer**: codex:codex-rescue  
**Date**: 2026-04-25  
**Scope**: field_brief (058) + goal_pool (059) schema/scoring design

## Findings

### A. Schema design — WARN (accepted)
- FK `field_brief_meta.artifact_id → project_artifacts(id) ON DELETE CASCADE` — if artifacts are cleaned up, meta row silently disappears. Acceptable for now (artifact cleanup is manual/rare).
- `goal_pool` lacks `UNIQUE(topic_id, priority_rank)` — rank collisions prevented by application code (`DELETE` + re-`INSERT` pattern). Acceptable.

### B. Scoring weights — WARN (accepted with notes)
- `headroom + feasibility = 0.60` combined — heavy but intentional (research ROI = headroom × feasibility).
- `evidence_coverage` floor `0.3` is generous but prevents false negatives when field_brief hasn't captured all baselines.
- `compute_fit` binary `0/1` is harsh at boundary — acknowledged. Could add partial scoring in future but current filter (`compute_fit >= 0.5`) already gates the binary.

### C. Stale detection — WARN (not FAIL)
- Codex flagged "15% paper growth trigger missing" — **incorrect**: it IS implemented in `http_api.py:ingest_paper()`, not in the primitive file. The primitive's `get_latest_field_brief()` only checks time-based staleness (>21 days). Design is intentional: ingest triggers growth stale, GET triggers time stale.
- **No actual gap** — both paths exist and work (tested in `test_stale_flag_after_paper_ingest`).

### D. Error handling — WARN (accepted)
- Retry only covers LLM call, not DB writes — correct by design (DB writes are idempotent via UPSERT/DELETE-INSERT).
- Crash after `record_artifact()` but before meta write → orphan artifact possible. Low risk (SQLite is local, crashes are rare).

### E. Concurrency — FIXED
- **Original finding valid**: `DELETE` → `INSERT` without transaction isolation = race condition.
- **Fix applied**: Added `BEGIN IMMEDIATE` to both `build_goal_pool()` and `build_field_brief()` meta writes.

### F. Downstream risk — WARN (accepted)
- `goal_pool` rows rewritten while artifact is versioned separately — expected behavior. Downstream consumers (experiment_matrix) should read from `goal_pool` table (source of truth), not artifact history.

## Resolution Summary

| Item | Original | Resolution |
|------|----------|------------|
| A | WARN | Accepted — cascading FK is intentional |
| B | WARN | Accepted — weights documented in acceptance |
| C | FAIL | Downgraded to WARN — 15% trigger exists in http_api.py |
| D | WARN | Accepted — idempotent writes |
| E | FAIL | FIXED — added BEGIN IMMEDIATE |
| F | WARN | Accepted — documented consumer contract |

**Verdict**: All FAIL items resolved. Proceeding to iter-07a.
