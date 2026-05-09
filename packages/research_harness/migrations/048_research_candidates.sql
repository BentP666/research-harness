-- Migration 048: research_candidates — CS Workflow v2 recommendation engine.
--
-- Consolidated schema per CS_RESEARCH_WORKFLOW_V2.md §D11 (LLM-driven scoring
-- plus deterministic multi-dimensional red-ocean).
--
-- scope format: 'domain:N' | 'research_area:N' | 'topic:N' — drives the
-- deterministic two-lane sort at the index level (non-red_ocean candidates
-- always surface ahead of red_ocean ones, even if LLM scores the red_ocean
-- candidate higher).
--
-- lineage_key = sha1(primary_signal_family + normalize(gap.description))
-- evidence_signature = sha1(sort(evidence_gap_ids + contradictions + claims))
-- (evidence_signature change ⇒ candidate needs re-scoring; lineage_key is
-- stable across re-score so user's status (dismissed/promoted) is preserved.)

CREATE TABLE IF NOT EXISTS research_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    primary_domain_id INTEGER REFERENCES domains(id),
    research_area_ids TEXT NOT NULL DEFAULT '[]',
    title TEXT NOT NULL,
    pitch TEXT NOT NULL DEFAULT '',
    llm_score NUMERIC NOT NULL DEFAULT 0,
    llm_score_breakdown TEXT NOT NULL DEFAULT '{}',
    area_red_ocean NUMERIC NOT NULL DEFAULT 0,
    task_red_ocean NUMERIC NOT NULL DEFAULT 0,
    method_red_ocean NUMERIC NOT NULL DEFAULT 0,
    opportunity_angle TEXT,
    confidence_level TEXT NOT NULL DEFAULT 'normal',
    evidence_gap_ids TEXT NOT NULL DEFAULT '[]',
    evidence_contradiction_ids TEXT NOT NULL DEFAULT '[]',
    evidence_claim_ids TEXT NOT NULL DEFAULT '[]',
    seed_paper_ids TEXT NOT NULL DEFAULT '[]',
    why TEXT NOT NULL DEFAULT '[]',
    risks TEXT NOT NULL DEFAULT '[]',
    lineage_key TEXT NOT NULL,
    evidence_signature TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    narration_model TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(scope, lineage_key)
);

-- Two-lane sort: non-red-ocean lane first, then red-ocean lane;
-- within each lane sort by confidence_level (high > normal > low) then llm_score DESC.
CREATE INDEX IF NOT EXISTS idx_rc_scope_sort
    ON research_candidates(scope, status,
        (area_red_ocean >= 0.7 AND task_red_ocean >= 0.7),
        confidence_level, llm_score DESC);

CREATE INDEX IF NOT EXISTS idx_rc_status
    ON research_candidates(status);
