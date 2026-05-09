CREATE TABLE IF NOT EXISTS retrieval_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  stage TEXT NOT NULL,
  trigger_reason TEXT NOT NULL CHECK(trigger_reason IN ('missing_evidence','weak_baseline','new_atom_idea','venue_pattern','user_request')),
  query TEXT NOT NULL,
  results_count INTEGER NOT NULL DEFAULT 0,
  ingested_paper_ids TEXT NOT NULL DEFAULT '[]',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_retrieval_topic_stage ON retrieval_log(topic_id, stage);
