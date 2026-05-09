-- Audit substrate for topic drilldown UI.
--
-- Adds first-class columns to provenance_records and decision_log so the UI
-- can answer: who ran this? why? was it skipped/retried/cached? was it
-- triggered by the user, the orchestrator, or a loopback?

ALTER TABLE provenance_records ADD COLUMN actor TEXT;
ALTER TABLE provenance_records ADD COLUMN origin TEXT;
ALTER TABLE provenance_records ADD COLUMN retry_ordinal INTEGER DEFAULT 0;
ALTER TABLE provenance_records ADD COLUMN cache_hit INTEGER DEFAULT 0;
ALTER TABLE provenance_records ADD COLUMN parallel_group TEXT;
ALTER TABLE provenance_records ADD COLUMN skipped INTEGER DEFAULT 0;
ALTER TABLE provenance_records ADD COLUMN skip_reason TEXT;

ALTER TABLE decision_log ADD COLUMN actor TEXT;
ALTER TABLE decision_log ADD COLUMN origin TEXT;

CREATE INDEX IF NOT EXISTS idx_prov_topic_stage
    ON provenance_records(topic_id, stage, started_at);
