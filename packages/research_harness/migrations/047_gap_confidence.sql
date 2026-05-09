-- Phase 4: gap confidence + cross-verification.
--
-- gap_detect's LLM emits a subjective confidence 0-1 per gap. We also
-- sample a subset of recent gaps and re-run them with a different model
-- tier (Opus) to measure cross-model stability — a Jaccard similarity
-- ≥ 0.6 against the original descriptions sets cross_verified=1.
--
-- Columns are additive + default-safe: all existing gap rows keep
-- confidence=0, cross_verified=0, cross_check_runs=0 until re-detected
-- or explicitly cross-checked.

ALTER TABLE gaps ADD COLUMN confidence REAL NOT NULL DEFAULT 0.0;
ALTER TABLE gaps ADD COLUMN cross_verified INTEGER NOT NULL DEFAULT 0;
ALTER TABLE gaps ADD COLUMN cross_check_runs INTEGER NOT NULL DEFAULT 0;

-- Frequently filter on (topic_id, cross_verified, confidence) — e.g.,
-- surface high-confidence verified gaps first.
CREATE INDEX IF NOT EXISTS idx_gaps_topic_verified
    ON gaps(topic_id, cross_verified, confidence);
