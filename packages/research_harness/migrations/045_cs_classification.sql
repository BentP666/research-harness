-- Migration 045: CS Research Workflow v2 — paper classification scaffolding.
--
-- Adds research_areas (fine-grained area within a domain, typically derived
-- from CSO or LLM) and the many-to-many tables linking papers to both
-- research_areas and top-level domains.
--
-- Notes:
-- - research_areas.source: 'cso' (syntactic/enhanced CSO label),
--   'llm_drift_patch' (LLM-proposed when CSO produces <2 usable terms),
--   'manual' (user override).
-- - red_ocean_score is populated by primitives/red_ocean.py (Phase 2 Task 2.7);
--   NULL until computed. red_ocean_breakdown carries the per-dimension JSON
--   (volume_pressure / method_convergence / lab_concentration / gap_density_cap)
--   so the UI can explain why an area was flagged.
-- - paper_research_areas.is_primary picks the paper's dominant area
--   (for drill-down UI and red-ocean attribution).
-- - paper_domains mirrors the coarser top-level bucket (one paper can belong
--   to multiple domains if it spans, e.g., cs.LG × cs.CV).

CREATE TABLE IF NOT EXISTS research_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT DEFAULT '',
    source TEXT NOT NULL DEFAULT 'llm',
    red_ocean_score REAL DEFAULT NULL,
    red_ocean_breakdown TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(domain_id, slug)
);

CREATE TABLE IF NOT EXISTS paper_research_areas (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    research_area_id INTEGER NOT NULL REFERENCES research_areas(id) ON DELETE CASCADE,
    is_primary INTEGER DEFAULT 0,
    match_type TEXT NOT NULL DEFAULT 'enhanced',
    PRIMARY KEY (paper_id, research_area_id)
);

CREATE TABLE IF NOT EXISTS paper_domains (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    is_primary INTEGER DEFAULT 0,
    PRIMARY KEY (paper_id, domain_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_research_areas_paper
    ON paper_research_areas(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_research_areas_area
    ON paper_research_areas(research_area_id);
CREATE INDEX IF NOT EXISTS idx_research_areas_domain
    ON research_areas(domain_id);
CREATE INDEX IF NOT EXISTS idx_paper_domains_paper
    ON paper_domains(paper_id);
