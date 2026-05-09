-- Migration 064: normalise papers.(doi, arxiv_id, s2_id) to plain UNIQUE so
-- NULL rows coexist.
--
-- Background: 001_initial_schema declared these as ``TEXT DEFAULT '' UNIQUE``.
-- SQLite treats the empty string as a regular value in UNIQUE comparisons, so
-- two papers lacking, say, s2_id collide on '' and the second INSERT is
-- rejected (or silently skipped under INSERT OR IGNORE). That was a real data
-- loss path when ingesting papers that had only arxiv_id (no s2_id yet).
--
-- Fix: recreate the table with the three columns nullable + UNIQUE, then
-- back-fill any existing '' value to NULL so the constraint holds going
-- forward. SQLite does not support ALTER COLUMN; the standard rebuild dance
-- is the idiomatic workaround.

CREATE TABLE IF NOT EXISTS papers_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT '',
    authors TEXT DEFAULT '[]',
    year INTEGER,
    venue TEXT DEFAULT '',
    doi TEXT UNIQUE,
    arxiv_id TEXT UNIQUE,
    s2_id TEXT UNIQUE,
    pdf_path TEXT DEFAULT '',
    pdf_hash TEXT DEFAULT '',
    status TEXT DEFAULT 'meta_only',
    created_at TEXT DEFAULT (datetime('now')),
    url TEXT DEFAULT '',
    abstract TEXT DEFAULT '',
    bibtex_auto TEXT DEFAULT '',
    concepts_json TEXT DEFAULT '',
    citation_count INTEGER,
    affiliations TEXT DEFAULT '[]',
    compiled_summary TEXT DEFAULT '',
    compiled_from_hash TEXT DEFAULT '',
    deep_read INTEGER DEFAULT 0
);

-- Collapse '' → NULL so the new UNIQUE constraint is satisfied.
INSERT INTO papers_new (
    id, title, authors, year, venue, doi, arxiv_id, s2_id,
    pdf_path, pdf_hash, status, created_at, url, abstract,
    bibtex_auto, concepts_json, citation_count, affiliations,
    compiled_summary, compiled_from_hash, deep_read
)
SELECT
    id, title, authors, year, venue,
    NULLIF(TRIM(doi), ''),
    NULLIF(TRIM(arxiv_id), ''),
    NULLIF(TRIM(s2_id), ''),
    pdf_path, pdf_hash, status, created_at, url, abstract,
    bibtex_auto, concepts_json, citation_count, affiliations,
    compiled_summary, compiled_from_hash, deep_read
FROM papers;

DROP TABLE papers;
ALTER TABLE papers_new RENAME TO papers;

CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
