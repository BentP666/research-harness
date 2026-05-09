-- Experiment iteration loop: experiments (spec) + experiment_loop_runs (per-iteration history)
-- Supports karpathy/autoresearch-style autonomous loop for CPU agent experiments.

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    task_description TEXT NOT NULL DEFAULT '',
    fixture_files_json TEXT NOT NULL DEFAULT '{}',
    mutable_entry TEXT NOT NULL DEFAULT 'main.py',
    primary_metric TEXT NOT NULL DEFAULT '',
    direction TEXT NOT NULL DEFAULT 'max' CHECK(direction IN ('max','min')),
    mode TEXT NOT NULL DEFAULT 'agent' CHECK(mode IN ('strict','agent')),
    budget_json TEXT NOT NULL DEFAULT '{}',
    best_run_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed','stopped')),
    stopped_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_experiments_topic ON experiments(topic_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);

CREATE TABLE IF NOT EXISTS experiment_loop_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    iteration INTEGER NOT NULL,
    code_hash TEXT NOT NULL DEFAULT '',
    files_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    primary_metric_value REAL,
    elapsed_sec REAL NOT NULL DEFAULT 0.0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('completed','failed','timeout','invalid')),
    returncode INTEGER NOT NULL DEFAULT 0,
    stdout_tail TEXT NOT NULL DEFAULT '',
    stderr_tail TEXT NOT NULL DEFAULT '',
    feedback_to_next TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_loop_runs_exp_iter
    ON experiment_loop_runs(experiment_id, iteration);
CREATE INDEX IF NOT EXISTS idx_experiment_loop_runs_status
    ON experiment_loop_runs(experiment_id, status);
