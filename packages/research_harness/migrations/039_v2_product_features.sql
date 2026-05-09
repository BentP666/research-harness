-- Migration 039: v2 product features — all new tables + topic columns.
-- Creates: agent_registry, agent_pairings, token_ledger, budgets, claims,
--          claim_citations, domain_trends, venue_ranks, stage_snapshots,
--          rollback_log, rubric_scores, rubric_calibrations, topic_autonomy,
--          user_preferences.
-- Alters: topics (adds target_venue_tier, quality_tier, autonomy_level).

-- =========================================================================
-- 1. Agent registry
-- =========================================================================

CREATE TABLE IF NOT EXISTS agent_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    provider_family TEXT NOT NULL,
    model TEXT NOT NULL,
    api_key_env TEXT NOT NULL,
    role_prefs TEXT NOT NULL DEFAULT '{}',
    monthly_budget_usd NUMERIC,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, model)
);

-- =========================================================================
-- 2. Agent pairings
-- =========================================================================

CREATE TABLE IF NOT EXISTS agent_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    generator_agent_id INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    judge_agent_id     INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    challenger_agent_id INTEGER REFERENCES agent_registry(id) ON DELETE SET NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    is_global_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (generator_agent_id != judge_agent_id)
);

-- =========================================================================
-- 3. Token ledger
-- =========================================================================

CREATE TABLE IF NOT EXISTS token_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    stage TEXT,
    primitive TEXT,
    role TEXT,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd NUMERIC NOT NULL,
    idempotency_key TEXT UNIQUE,
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_token_ledger_topic_ts ON token_ledger(topic_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_token_ledger_agent_month ON token_ledger(agent_id, substr(ts,1,7));

-- =========================================================================
-- 4. Budgets
-- =========================================================================

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    scope_id INTEGER,
    monthly_cap_usd NUMERIC NOT NULL,
    hard_stop INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_budgets_scope ON budgets(scope, scope_id);

-- =========================================================================
-- 5. Claims + citations
-- =========================================================================

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES project_artifacts(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    claim_type TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_claims_artifact ON claims(artifact_id);

CREATE TABLE IF NOT EXISTS claim_citations (
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    evidence_quote TEXT,
    PRIMARY KEY (claim_id, paper_id)
);
CREATE INDEX IF NOT EXISTS idx_claim_citations_paper ON claim_citations(paper_id);

-- =========================================================================
-- 6. Domain trends
-- =========================================================================

CREATE TABLE IF NOT EXISTS domain_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    velocity_yoy NUMERIC,
    citation_median NUMERIC,
    top_venues TEXT,
    publishability_score NUMERIC,
    why TEXT,
    seed_papers TEXT,
    tier TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_domain_trends_score ON domain_trends(publishability_score DESC);

-- =========================================================================
-- 7. Venue ranks
-- =========================================================================

CREATE TABLE IF NOT EXISTS venue_ranks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    aliases TEXT NOT NULL DEFAULT '[]',
    ccf_rank TEXT,
    cas_zone INTEGER,
    impact_factor NUMERIC,
    discipline TEXT NOT NULL DEFAULT 'cs',
    source_snapshot TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_venue_ranks_rank ON venue_ranks(ccf_rank, cas_zone);

-- =========================================================================
-- 8. Stage snapshots + rollback log
-- =========================================================================

CREATE TABLE IF NOT EXISTS stage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    orchestrator_run_id INTEGER REFERENCES orchestrator_runs(id),
    artifact_snapshot TEXT NOT NULL,
    rubric_snapshot TEXT,
    token_cost_usd NUMERIC NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_stage_snapshots_topic_stage ON stage_snapshots(topic_id, stage, created_at DESC);

CREATE TABLE IF NOT EXISTS rollback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    to_snapshot_id INTEGER NOT NULL REFERENCES stage_snapshots(id),
    trigger TEXT NOT NULL,
    reason TEXT NOT NULL,
    rubric_snapshot TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =========================================================================
-- 9. Rubric scores + calibrations
-- =========================================================================

CREATE TABLE IF NOT EXISTS rubric_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL REFERENCES project_artifacts(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    tier TEXT NOT NULL,
    judge_agent_id INTEGER REFERENCES agent_registry(id) ON DELETE SET NULL,
    dimension_scores TEXT NOT NULL DEFAULT '{}',
    weighted_total NUMERIC NOT NULL,
    verdict TEXT NOT NULL,
    shadow_verdict TEXT,
    critique TEXT,
    evidence_refs TEXT,
    rubric_version TEXT,
    scored_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rubric_scores_topic ON rubric_scores(topic_id, stage);

CREATE TABLE IF NOT EXISTS rubric_calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    tier TEXT NOT NULL,
    threshold NUMERIC NOT NULL,
    false_rollback_rate NUMERIC,
    reject_rate NUMERIC,
    anchor_count INTEGER,
    calibrated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(stage, tier)
);

-- =========================================================================
-- 10. Topic autonomy
-- =========================================================================

CREATE TABLE IF NOT EXISTS topic_autonomy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL UNIQUE REFERENCES topics(id) ON DELETE CASCADE,
    level TEXT NOT NULL DEFAULT 'L2',
    sticky_pauses TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =========================================================================
-- 11. User preferences
-- =========================================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL DEFAULT 'en',
    discipline TEXT NOT NULL DEFAULT 'cs',
    default_venue_tier TEXT NOT NULL DEFAULT 'B',
    default_quality_tier TEXT NOT NULL DEFAULT 'standard',
    default_autonomy TEXT NOT NULL DEFAULT 'L2',
    monthly_budget_cap_usd NUMERIC DEFAULT 100,
    onboarding_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =========================================================================
-- 12. Alter topics table — add v2 columns
-- =========================================================================

ALTER TABLE topics ADD COLUMN target_venue_tier TEXT DEFAULT 'B';
ALTER TABLE topics ADD COLUMN quality_tier TEXT DEFAULT 'standard';
ALTER TABLE topics ADD COLUMN autonomy_level TEXT DEFAULT 'L2';
