-- Stage-level token budgets for per-primitive soft warnings and hard caps.
CREATE TABLE IF NOT EXISTS stage_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    topic_id INTEGER,
    soft_warn_tokens INTEGER NOT NULL DEFAULT 8000,
    hard_cap_tokens INTEGER NOT NULL DEFAULT 12000,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(stage, topic_id)
);
