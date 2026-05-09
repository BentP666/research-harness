CREATE TABLE IF NOT EXISTS goal_pool (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  dataset TEXT NOT NULL,
  baseline TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  baseline_metric REAL NOT NULL,
  target_metric_delta REAL NOT NULL,
  target_venue TEXT,
  time_window_days INTEGER,
  score REAL NOT NULL,
  scoring_breakdown TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','done','skipped')),
  priority_rank INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_goal_topic_rank ON goal_pool(topic_id, priority_rank);
