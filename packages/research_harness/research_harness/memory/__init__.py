"""v2 Step 8 — Workflow memory.

Metadata-first retrieval over the existing provenance_records and
decision_log tables, with an optional embedding-based rerank when a query
is provided.

No new table is required; workflow memory is a derived read layer over
state we already persist.
"""

from __future__ import annotations

from .workflow_memory import (
    MemoryHit,
    recall_similar_runs,
    summarize_past_topic,
)

__all__ = [
    "MemoryHit",
    "recall_similar_runs",
    "summarize_past_topic",
]
