CREATE TABLE IF NOT EXISTS zotero_import_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    zotero_library_id TEXT DEFAULT '',
    zotero_library_type TEXT DEFAULT 'user',
    zotero_item_key TEXT NOT NULL,
    zotero_child_key TEXT NOT NULL,
    zotero_child_type TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    last_imported_at TEXT DEFAULT (datetime('now')),
    UNIQUE (topic_id, paper_id, zotero_library_id, zotero_library_type, zotero_child_key, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_zotero_import_links_topic
    ON zotero_import_links(topic_id);
CREATE INDEX IF NOT EXISTS idx_zotero_import_links_paper
    ON zotero_import_links(paper_id);
