-- Add modality and evidence_spans support to claim tables
-- These fields are optional for backward compat

ALTER TABLE claims ADD COLUMN modality TEXT DEFAULT 'text';
ALTER TABLE claims ADD COLUMN claim_uuid TEXT;
ALTER TABLE claims ADD COLUMN paper_ids_json TEXT;
ALTER TABLE claims ADD COLUMN evidence_spans_json TEXT;
ALTER TABLE claims ADD COLUMN confidence REAL DEFAULT 0.0;

ALTER TABLE normalized_claims ADD COLUMN modality TEXT DEFAULT 'text';
ALTER TABLE normalized_claims ADD COLUMN evidence_spans_json TEXT;

CREATE INDEX IF NOT EXISTS idx_claims_uuid ON claims(claim_uuid);
CREATE INDEX IF NOT EXISTS idx_claims_topic_modality ON claims(topic_id, modality);
