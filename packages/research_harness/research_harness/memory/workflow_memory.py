"""Workflow memory — metadata-first retrieval over past research runs.

Given a query (free-text description of a new topic/problem), return the
most similar historical topics based on:

1. **Metadata filter** — only consider topics that are ``active`` (not
   archived), are at least `min_age_days` old, and have at least one
   successful provenance record.
2. **Text shortlist** — rank candidate topics by lexical overlap between
   the query and each topic's name/description so the embedding pass stays
   cheap (top_k candidates).
3. **Embedding rerank** — if available, use ``research_harness.embeddings``
   to compute cosine similarity between the query and each candidate's
   concatenated (name + description + key decisions).

Returns a small digest per hit (stage_summaries, last_decisions, provenance
counts) so the caller can show a "similar past runs" card without pulling
the full history.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ..storage.db import Database

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "why",
        "with",
        "will",
        "can",
        "could",
        "should",
        "would",
    }
)


@dataclass
class MemoryHit:
    topic_id: int
    topic_name: str
    description: str
    created_at: str
    score: float  # rerank score in [0, 1]
    lexical_score: float = 0.0
    provenance_success_count: int = 0
    decision_highlights: list[str] = field(default_factory=list)


def _tokenize(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if t.lower() not in _STOPWORDS and len(t) > 1
    }


def _lexical_score(query_tokens: set[str], doc_text: str) -> float:
    doc_tokens = _tokenize(doc_text)
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    # Jaccard-style score normalized by query size so documents aren't
    # penalized for being longer than the query.
    return len(overlap) / max(len(query_tokens), 1)


def _summarize_decisions(db: Database, topic_id: int, limit: int = 3) -> list[str]:
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT stage, checkpoint, choice, reasoning
            FROM decision_log
            WHERE topic_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (topic_id, limit),
        ).fetchall()
    except Exception as exc:
        logger.debug("decision_log read failed: %s", exc)
        return []
    finally:
        conn.close()
    out: list[str] = []
    for r in rows:
        tag = f"{r['stage']}/{r['checkpoint']}"
        summary = f"{tag}: {r['choice']}"
        reasoning = (r["reasoning"] or "").strip()
        if reasoning:
            summary += f" — {reasoning[:160]}"
        out.append(summary)
    return out


def _provenance_success_count(db: Database, topic_id: int) -> int:
    conn = db.connect()
    try:
        row = conn.execute(
            """
            SELECT COUNT(1) AS n FROM provenance_records
            WHERE topic_id = ? AND success = 1
            """,
            (topic_id,),
        ).fetchone()
        return int(row["n"]) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def _candidate_topics(
    db: Database,
    *,
    exclude_topic_id: int | None,
    min_age_days: int,
    max_age_days: int | None,
    require_success: bool,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    min_created = (now - timedelta(days=min_age_days)).isoformat()
    max_created: str | None = None
    if max_age_days is not None:
        max_created = (now - timedelta(days=max_age_days)).isoformat()

    conn = db.connect()
    try:
        clauses = ["t.status = 'active'"]
        params: list[Any] = []
        if exclude_topic_id is not None:
            clauses.append("t.id != ?")
            params.append(exclude_topic_id)
        if min_age_days > 0:
            clauses.append("t.created_at <= ?")
            params.append(min_created)
        if max_created is not None:
            clauses.append("t.created_at >= ?")
            params.append(max_created)
        where = " WHERE " + " AND ".join(clauses)
        rows = conn.execute(
            f"""
            SELECT t.id, t.name, t.description, t.created_at
            FROM topics t
            {where}
            ORDER BY t.id DESC
            """,
            params,
        ).fetchall()
        topics = [dict(r) for r in rows]
    finally:
        conn.close()

    if require_success:
        topics = [t for t in topics if _provenance_success_count(db, int(t["id"])) > 0]
    return topics


def recall_similar_runs(
    db: Database,
    query: str,
    *,
    exclude_topic_id: int | None = None,
    top_k: int = 5,
    shortlist_k: int = 25,
    min_age_days: int = 0,
    max_age_days: int | None = 90,
    require_success: bool = True,
    use_embeddings: bool = True,
    embed_weight: float = 0.6,
) -> list[MemoryHit]:
    """Rank historical topics by similarity to ``query``.

    90-day / successful filter by default per v2 plan. ``max_age_days=None``
    removes the recency cap.
    """
    query = (query or "").strip()
    if not query:
        return []

    candidates = _candidate_topics(
        db,
        exclude_topic_id=exclude_topic_id,
        min_age_days=min_age_days,
        max_age_days=max_age_days,
        require_success=require_success,
    )
    if not candidates:
        return []

    query_tokens = _tokenize(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in candidates:
        doc = f"{c.get('name', '')}. {c.get('description', '')}"
        scored.append((_lexical_score(query_tokens, doc), c))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    shortlist = scored[:shortlist_k]

    # Optional embedding rerank.
    rerank: dict[int, float] = {}
    if use_embeddings and shortlist:
        try:
            from ..embeddings import embed_texts
            from ..embeddings.service import cosine_similarity

            docs = [
                f"{c.get('name', '')}\n{c.get('description', '')}" for _, c in shortlist
            ]
            emb = embed_texts(db, [query] + docs)
            if emb.vectors and len(emb.vectors) == 1 + len(docs):
                q_vec = emb.vectors[0]
                for (_, c), v in zip(shortlist, emb.vectors[1:]):
                    rerank[int(c["id"])] = cosine_similarity(q_vec, v)
        except Exception as exc:
            logger.debug("embedding rerank skipped: %s", exc)

    # Combine lexical + embedding scores.
    hits: list[MemoryHit] = []
    for lex, c in shortlist:
        emb_score = rerank.get(int(c["id"]), 0.0)
        if rerank:
            combined = (1 - embed_weight) * lex + embed_weight * emb_score
        else:
            combined = lex
        hits.append(
            MemoryHit(
                topic_id=int(c["id"]),
                topic_name=c.get("name", ""),
                description=c.get("description", ""),
                created_at=c.get("created_at", ""),
                score=round(combined, 4),
                lexical_score=round(lex, 4),
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    top = hits[:top_k]
    # Hydrate decision highlights + success count for the top hits only.
    for h in top:
        h.provenance_success_count = _provenance_success_count(db, h.topic_id)
        h.decision_highlights = _summarize_decisions(db, h.topic_id, limit=3)
    return top


def summarize_past_topic(db: Database, topic_id: int) -> dict[str, Any]:
    """Lightweight digest for a single past topic. Used by the FE drilldown."""
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        if row is None:
            return {"error": f"topic not found: {topic_id}"}
        topic = dict(row)
    finally:
        conn.close()
    topic["provenance_success_count"] = _provenance_success_count(db, topic_id)
    topic["decision_highlights"] = _summarize_decisions(db, topic_id, limit=5)
    return topic
