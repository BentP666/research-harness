-- Migration 056: background paper expansion jobs for topic-level search+ingest.

CREATE TABLE IF NOT EXISTS expansion_jobs (
    id INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),
    retrieval_target INTEGER NOT NULL,
    deep_read_target INTEGER NOT NULL,
    rounds_target INTEGER NOT NULL,
    current_round INTEGER NOT NULL DEFAULT 0,
    papers_fetched INTEGER NOT NULL DEFAULT 0,
    papers_deep_read INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_expansion_jobs_topic_status
    ON expansion_jobs(topic_id, status);

CREATE INDEX IF NOT EXISTS idx_expansion_jobs_topic_created
    ON expansion_jobs(topic_id, created_at DESC);
