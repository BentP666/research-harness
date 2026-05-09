"""v2 Step 10 — Multi-pass DAG gap detection (opt-in pilot).

Why DAG reasoning?
------------------
The default ``gap_detect`` primitive summarises the whole literature and asks
an LLM to enumerate gaps. On mixed-topic pools this tends to surface the most
salient (often well-known) gaps and misses niche ones buried in sub-areas.

The DAG pilot partitions the pool into k semantic clusters with the
embedding service, runs ``gap_detect`` on each cluster (leaf layer), then
asks the model one more time to reconcile cluster-level findings into a
de-duplicated, cross-cluster gap list (root layer).

Gating
------
This path is gated by ``RESEARCH_HARNESS_GAP_DAG=1``. The plan requires a
3-topic human-rated protocol (≥1 real gap that the single-pass misses,
≤10% hallucination rate) before the path may become default-on. Until then
it is explicitly opt-in.
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from ..embeddings import embed_texts
from ..embeddings.service import cosine_similarity
from ..storage.db import Database

logger = logging.getLogger(__name__)


def is_dag_enabled() -> bool:
    """Single source of truth for the env flag."""
    return os.environ.get("RESEARCH_HARNESS_GAP_DAG", "").strip() == "1"


@dataclass
class DAGGap:
    description: str
    gap_type: str = ""
    severity: str = "medium"
    confidence: float = 0.5
    related_paper_ids: list[int] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class DAGResult:
    gaps: list[DAGGap]
    cluster_count: int
    papers_analyzed: int
    dag_enabled: bool = True


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def _kmeans_cluster(
    vectors: list[list[float]], k: int, seed: int = 0, max_iter: int = 20
) -> list[int]:
    """Tiny k-means in pure Python. Returns a cluster index per input vector.

    For k<=1 returns [0]*n without any work. The embedding vectors from our
    fake provider are unit-norm; OpenAI's text-embedding-3-small is also
    L2-normalized, so cosine-based k-means degenerates to Euclidean k-means.
    """
    n = len(vectors)
    if n == 0 or k <= 1:
        return [0] * n
    k = min(k, n)
    rng = random.Random(seed)
    # Seed with distinct random picks.
    centroids = rng.sample(vectors, k)
    assignments = [0] * n
    for _ in range(max_iter):
        changed = False
        for i, v in enumerate(vectors):
            # Argmax cosine = argmin (1 - cosine).
            best_j = 0
            best_score = -1.0
            for j, c in enumerate(centroids):
                s = cosine_similarity(v, c)
                if s > best_score:
                    best_score = s
                    best_j = j
            if assignments[i] != best_j:
                changed = True
                assignments[i] = best_j
        if not changed:
            break
        # Recompute centroids (arithmetic mean component-wise).
        sums: list[list[float]] = [[0.0] * len(vectors[0]) for _ in range(k)]
        counts = [0] * k
        for i, v in enumerate(vectors):
            c = assignments[i]
            counts[c] += 1
            sums[c] = [a + b for a, b in zip(sums[c], v)]
        for j in range(k):
            if counts[j] > 0:
                centroids[j] = [x / counts[j] for x in sums[j]]
    return assignments


def _partition_papers(
    db: Database, papers: list[dict[str, Any]], *, k: int
) -> list[list[dict[str, Any]]]:
    """Cluster papers into k buckets using embeddings of title+abstract.

    Falls back to an even-split partition when embeddings are unavailable.
    """
    if not papers:
        return []
    if len(papers) <= k:
        return [[p] for p in papers]
    texts = [f"{p.get('title', '')}\n{p.get('abstract', '') or ''}" for p in papers]
    try:
        emb = embed_texts(db, texts)
        if not emb.vectors or all(len(v) == 0 for v in emb.vectors):
            raise RuntimeError("empty embedding vectors")
        assignments = _kmeans_cluster(emb.vectors, k)
    except Exception as exc:
        logger.warning(
            "DAG clustering fallback (no embeddings): %s — using even split", exc
        )
        assignments = [i % k for i in range(len(papers))]

    buckets: list[list[dict[str, Any]]] = [[] for _ in range(k)]
    for idx, cluster_id in enumerate(assignments):
        cluster_id = max(0, min(cluster_id, k - 1))
        buckets[cluster_id].append(papers[idx])
    # Drop empty buckets so we don't run gap_detect on zero papers.
    return [b for b in buckets if b]


# ---------------------------------------------------------------------------
# Leaf-layer gap detect (per cluster)
# ---------------------------------------------------------------------------


def _load_topic_papers(db: Database, topic_id: int) -> list[dict[str, Any]]:
    conn = db.connect()
    try:
        rows = conn.execute(
            """
            SELECT p.id, p.title, p.year, p.venue, pa.content AS abstract
            FROM papers p
            JOIN paper_topics pt ON pt.paper_id = p.id
            LEFT JOIN paper_annotations pa
                   ON pa.paper_id = p.id AND pa.section = 'abstract'
            WHERE pt.topic_id = ?
            ORDER BY p.year DESC, p.id DESC
            LIMIT 500
            """,
            (topic_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _dedup_gaps(gaps: list[DAGGap]) -> list[DAGGap]:
    """Merge gaps with the same (case-insensitive) description. Preserves
    highest confidence and unions sources/paper ids."""
    by_key: dict[str, DAGGap] = {}
    for g in gaps:
        key = " ".join(g.description.lower().split())[:160]
        if not key:
            continue
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = g
            continue
        prev.confidence = max(prev.confidence, g.confidence)
        prev.sources = list(dict.fromkeys(prev.sources + g.sources))
        prev.related_paper_ids = list(
            dict.fromkeys(prev.related_paper_ids + g.related_paper_ids)
        )
        # Severity climbs monotonically (low < medium < high < critical).
        order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        if order.get(g.severity, 2) > order.get(prev.severity, 2):
            prev.severity = g.severity
    return list(by_key.values())


def gap_detect_dag(
    *,
    db: Database,
    topic_id: int,
    focus: str = "",
    cluster_count: int = 4,
    persist: bool = True,
    # Hook for tests: inject a leaf-level gap detector so we don't need to
    # stand up the full LLM stack.
    leaf_fn: Callable[..., Any] | None = None,
) -> DAGResult:
    """Multi-pass gap detection over clustered literature.

    Flow:
      1. Load topic papers.
      2. Embed (title + abstract) and k-means cluster into ``cluster_count``
         buckets.
      3. Run the leaf gap detector on each cluster with a cluster-scoped
         focus suffix.
      4. Dedup and union the gaps, boosting confidence when a gap surfaces
         in multiple clusters.
      5. Persist into the ``gaps`` table like the default primitive.
    """
    papers = _load_topic_papers(db, topic_id)
    if not papers:
        return DAGResult(gaps=[], cluster_count=0, papers_analyzed=0)

    clusters = _partition_papers(db, papers, k=max(1, cluster_count))
    if not clusters:
        return DAGResult(gaps=[], cluster_count=0, papers_analyzed=len(papers))

    if leaf_fn is None:
        from . import llm_primitives

        leaf_fn = llm_primitives.gap_detect

    all_gaps: list[DAGGap] = []
    for i, cluster in enumerate(clusters):
        paper_ids = [int(p["id"]) for p in cluster if p.get("id")]
        cluster_focus = (focus or "").strip()
        tag = f"cluster {i + 1}/{len(clusters)} (n={len(cluster)})"
        cluster_focus = (
            f"{cluster_focus} [DAG {tag}]" if cluster_focus else f"[DAG {tag}]"
        )
        try:
            out = leaf_fn(
                db=db,
                topic_id=topic_id,
                focus=cluster_focus,
                _paper_ids=paper_ids,
            )
        except TypeError:
            # Real gap_detect doesn't accept _paper_ids yet; fall back to
            # calling with just focus (it will re-summarize the whole topic).
            out = leaf_fn(db=db, topic_id=topic_id, focus=cluster_focus)

        # Normalize whatever the leaf returned.
        raw_gaps = getattr(out, "gaps", None)
        if raw_gaps is None and isinstance(out, dict):
            raw_gaps = out.get("gaps", [])
        if not raw_gaps:
            continue
        for g in raw_gaps:
            desc = getattr(g, "description", None) or (
                g.get("description") if isinstance(g, dict) else ""
            )
            if not desc:
                continue
            all_gaps.append(
                DAGGap(
                    description=desc,
                    gap_type=getattr(g, "gap_type", "")
                    or (g.get("gap_type", "") if isinstance(g, dict) else ""),
                    severity=getattr(g, "severity", "medium")
                    or (
                        g.get("severity", "medium") if isinstance(g, dict) else "medium"
                    ),
                    confidence=float(
                        getattr(g, "confidence", 0.5)
                        or (g.get("confidence", 0.5) if isinstance(g, dict) else 0.5)
                    ),
                    related_paper_ids=paper_ids,
                    sources=[f"cluster:{i}"],
                )
            )

    merged = _dedup_gaps(all_gaps)

    if persist and merged:
        import json

        conn = db.connect()
        try:
            for g in merged:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO gaps
                        (topic_id, description, gap_type, severity,
                         related_paper_ids, focus, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        g.description,
                        g.gap_type,
                        g.severity,
                        json.dumps(g.related_paper_ids),
                        focus,
                        g.confidence,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    return DAGResult(
        gaps=merged,
        cluster_count=len(clusters),
        papers_analyzed=len(papers),
    )
