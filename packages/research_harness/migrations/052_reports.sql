-- v2 Sprint 1 — Advisor Reports
-- Sharable, versioned artifacts that bundle a subset of drafted sections
-- for advisor review. PDF export is client-side; server stores HTML + MD.

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    template TEXT NOT NULL,           -- abstract_only | abstract_intro | deep_pitch | full_review
    title TEXT NOT NULL DEFAULT '',
    sections_json TEXT NOT NULL DEFAULT '[]',   -- ordered list of section ids included
    content_md TEXT NOT NULL DEFAULT '',        -- rendered markdown
    content_html TEXT NOT NULL DEFAULT '',      -- rendered HTML (used for PDF print)
    metadata_json TEXT NOT NULL DEFAULT '{}',   -- confidence tags, word counts, estimates
    version_major INTEGER NOT NULL DEFAULT 0,
    version_minor INTEGER NOT NULL DEFAULT 1,
    share_token TEXT DEFAULT NULL UNIQUE,       -- nullable; set when share link created
    share_expires_at TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_topic ON reports(topic_id);
CREATE INDEX IF NOT EXISTS idx_reports_share_token ON reports(share_token);
