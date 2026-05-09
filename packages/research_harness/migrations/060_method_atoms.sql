CREATE TABLE IF NOT EXISTS method_atoms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  topic_id INTEGER NOT NULL,
  source_paper_id INTEGER NOT NULL,
  atom_type TEXT NOT NULL CHECK(atom_type IN ('loss','data_trick','augmentation','training_schedule','inference_heuristic','micro_block')),
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  deps TEXT NOT NULL DEFAULT '[]',
  reported_gain TEXT,
  reuse_risk TEXT NOT NULL CHECK(reuse_risk IN ('low','medium','high')),
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (source_paper_id) REFERENCES papers(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_atom_topic_type ON method_atoms(topic_id, atom_type);
