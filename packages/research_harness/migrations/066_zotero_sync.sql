CREATE TABLE IF NOT EXISTS zotero_item_links (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    zotero_library_id TEXT DEFAULT '',
    zotero_library_type TEXT DEFAULT 'user',
    zotero_collection_key TEXT DEFAULT '',
    zotero_item_key TEXT NOT NULL,
    zotero_note_key TEXT DEFAULT '',
    content_hash TEXT NOT NULL,
    last_synced_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (paper_id, topic_id, zotero_library_id, zotero_library_type)
);

CREATE INDEX IF NOT EXISTS idx_zotero_item_links_topic
    ON zotero_item_links(topic_id);
