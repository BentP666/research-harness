CREATE TABLE IF NOT EXISTS venue_decision (
  topic_id INTEGER PRIMARY KEY,
  decided_venue TEXT NOT NULL,
  decision_basis TEXT NOT NULL,
  fit_risk TEXT,
  source_venues TEXT NOT NULL DEFAULT '[]',
  decided_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS venue_style_kit (
  topic_id INTEGER PRIMARY KEY,
  venue TEXT NOT NULL,
  avg_section_lengths TEXT NOT NULL,
  citation_density REAL NOT NULL,
  hedging_terms TEXT NOT NULL,
  source_paper_ids TEXT NOT NULL,
  source_venues TEXT NOT NULL DEFAULT '[]',
  built_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
