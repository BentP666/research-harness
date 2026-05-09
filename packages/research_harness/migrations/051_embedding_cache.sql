-- v2 Step 7 — Embedding cache
-- Content-hash keyed cache for embedding vectors so repeated calls with the
-- same text don't re-hit the provider API. Keyed by (provider, model, hash).

CREATE TABLE IF NOT EXISTS embedding_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    -- sha256 of the normalized text; hex-encoded
    content_hash TEXT NOT NULL,
    -- embedding serialized as JSON array of floats
    vector_json TEXT NOT NULL,
    dim INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (provider, model, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_key
    ON embedding_cache(provider, model, content_hash);
