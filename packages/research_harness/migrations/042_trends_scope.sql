-- Migration 042: scope + time-series indexes for trends (Phase C).
--
-- Adds a single "scope" string column to domain_trends so a cluster can be
-- scoped to a discipline (`discipline:cs`), a domain (`domain:<id>`), or
-- a topic (`topic:<id>`). Codex specifically recommended ONE text column
-- over (scope_kind, scope_id) polymorphic pair — simpler queries, simpler
-- backfill, and it models the three-level hierarchy without a joinable
-- nullable id.
--
-- Also adds an index on papers(year) so the yearly-counts endpoint used by
-- trend sparklines and line charts doesn't trigger a full table scan.

ALTER TABLE domain_trends ADD COLUMN scope TEXT NOT NULL DEFAULT 'discipline:cs';

CREATE INDEX IF NOT EXISTS idx_domain_trends_scope
  ON domain_trends(scope, tier, publishability_score DESC);

CREATE INDEX IF NOT EXISTS idx_papers_year
  ON papers(year);
