CREATE TABLE IF NOT EXISTS experiment_matrix_cell (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  goal_id INTEGER NOT NULL,
  atom_combo TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','proxy_running','proxy_done','pruned','promoted')),
  proxy_metric_name TEXT,
  proxy_metric_value REAL,
  baseline_metric REAL,
  delta_to_sota REAL,
  proxy_run_id TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (goal_id) REFERENCES goal_pool(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_matrix_topic ON experiment_matrix_cell(topic_id, status);
