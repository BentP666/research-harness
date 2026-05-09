-- 040: Async jobs table for long-running operations (S5)

CREATE TABLE IF NOT EXISTS async_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,            -- 'topic_candidates' | 'domain_suggest' | etc.
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | running | completed | failed
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    domain_id INTEGER REFERENCES domains(id) ON DELETE SET NULL,
    idempotency_key TEXT UNIQUE,
    input_params TEXT NOT NULL DEFAULT '{}',
    result TEXT,                        -- JSON result on completion
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_async_jobs_status ON async_jobs(status);
CREATE INDEX IF NOT EXISTS idx_async_jobs_idemp ON async_jobs(idempotency_key);
