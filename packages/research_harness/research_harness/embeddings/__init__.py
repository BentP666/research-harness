"""v2 Step 7 — Embedding service.

Reusable ``embed_texts()`` with a SQLite content-hash cache. Prefers
API-based embeddings (OpenAI text-embedding-3-small by default) over
sentence-transformers — the plan calls for cheap, stateless, well-cached
vectors rather than self-hosted models.

Provider routing::

    RESEARCH_HARNESS_EMBEDDING_PROVIDER = "openai" (default) | "fake"
    RESEARCH_HARNESS_EMBEDDING_MODEL    = "text-embedding-3-small" (default)

The ``fake`` provider returns deterministic hashes-to-vectors and is the
default in tests (and whenever no API key is available) so embed_texts()
never blocks on network when credentials are missing.
"""

from __future__ import annotations

from .cache import clear_cache, read_cached, write_cached
from .service import EmbeddingResult, embed_texts

__all__ = [
    "EmbeddingResult",
    "clear_cache",
    "embed_texts",
    "read_cached",
    "write_cached",
]
