CREATE TABLE IF NOT EXISTS field_brief_meta (
  topic_id INTEGER PRIMARY KEY,
  artifact_id INTEGER NOT NULL,
  paper_count_at_build INTEGER NOT NULL,
  built_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  stale INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (artifact_id) REFERENCES project_artifacts(id) ON DELETE CASCADE
);
