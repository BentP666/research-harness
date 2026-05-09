-- Migration 046: Add task_canonical column to normalized_claims.
--
-- Populated by the `task_canonicalize` primitive (Phase 2 Task 2.6), which
-- groups near-duplicate `task` strings (e.g. "sentiment classification",
-- "sentiment analysis", "sentiment detection") under one canonical label
-- per cluster. Enables cross-paper queries to treat them as one task when
-- computing task-level red-ocean pressure.
--
-- NULL until canonicalized. Index enables GROUP BY in aggregation queries.

ALTER TABLE normalized_claims ADD COLUMN task_canonical TEXT;
CREATE INDEX IF NOT EXISTS idx_normalized_claims_task_canonical
    ON normalized_claims(task_canonical);
