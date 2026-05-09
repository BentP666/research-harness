CREATE TABLE IF NOT EXISTS topic_intake_profile (
  topic_id INTEGER PRIMARY KEY,
  persona TEXT NOT NULL CHECK(persona IN ('p1_no_domain','p2_domain_no_topic','p3_topic_weak','p4_topic_strong')),
  domain_confidence INTEGER NOT NULL CHECK(domain_confidence BETWEEN 0 AND 100),
  topic_confidence INTEGER NOT NULL CHECK(topic_confidence BETWEEN 0 AND 100),
  venue_constraint TEXT NOT NULL CHECK(venue_constraint IN ('locked','preferred','open')),
  target_venue TEXT,
  compute_budget TEXT NOT NULL CHECK(compute_budget IN ('cpu_only','single_gpu','multi_gpu','cluster')),
  time_to_deadline_days INTEGER,
  seed_present INTEGER NOT NULL DEFAULT 0,
  raw_notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_intake_persona ON topic_intake_profile(persona);
