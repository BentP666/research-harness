"""Lightweight eval baseline — snapshot quality/cost/latency for topics.

Reads existing provenance_records, token_ledger, decision_log, and
session_observations to produce a JSON snapshot of per-topic metrics.
This snapshot serves as the "before" state for optimization comparisons.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime

from ..storage.db import Database

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    stage: str
    primitive_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    avg_quality_score: float | None = None
    total_duration_sec: float = 0.0


@dataclass
class TopicBaseline:
    topic_id: int
    topic_name: str
    total_cost_usd: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_primitive_calls: int = 0
    success_rate: float = 0.0
    avg_quality_score: float | None = None
    human_intervention_count: int = 0
    stage_metrics: list[StageMetrics] = field(default_factory=list)
    observation_count: int = 0
    total_latency_ms: int = 0
    decision_count: int = 0


@dataclass
class BaselineSnapshot:
    snapshot_id: str = ""
    created_at: str = ""
    topics: list[TopicBaseline] = field(default_factory=list)


def collect_baseline(
    db: Database,
    topic_ids: list[int] | None = None,
    top_k: int = 3,
) -> BaselineSnapshot:
    """Collect baseline metrics for the given topics (or auto-select top_k)."""
    conn = db.connect()
    try:
        if topic_ids is None:
            rows = conn.execute(
                """
                SELECT topic_id, COUNT(*) as cnt
                FROM provenance_records
                GROUP BY topic_id
                ORDER BY cnt DESC
                LIMIT ?
                """,
                (top_k,),
            ).fetchall()
            topic_ids = [r["topic_id"] for r in rows]

        if not topic_ids:
            logger.warning("No topics with provenance records found")
            return BaselineSnapshot(
                snapshot_id=f"baseline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                created_at=datetime.utcnow().isoformat(),
            )

        topics: list[TopicBaseline] = []
        for tid in topic_ids:
            topics.append(_collect_topic(conn, tid))

        return BaselineSnapshot(
            snapshot_id=f"baseline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.utcnow().isoformat(),
            topics=topics,
        )
    finally:
        conn.close()


def _collect_topic(conn, topic_id: int) -> TopicBaseline:
    """Collect metrics for a single topic."""
    name_row = conn.execute(
        "SELECT name FROM topics WHERE id = ?", (topic_id,)
    ).fetchone()
    topic_name = name_row["name"] if name_row else f"topic_{topic_id}"

    # Provenance aggregates
    prov_rows = conn.execute(
        """
        SELECT stage,
               COUNT(*) as calls,
               SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
               SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
               COALESCE(SUM(cost_usd), 0) as cost,
               COALESCE(SUM(prompt_tokens), 0) as ptoks,
               COALESCE(SUM(completion_tokens), 0) as ctoks,
               AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score END) as avg_quality,
               SUM(
                   CASE WHEN started_at IS NOT NULL AND finished_at IS NOT NULL
                   THEN (julianday(finished_at) - julianday(started_at)) * 86400
                   ELSE 0 END
               ) as duration_sec
        FROM provenance_records
        WHERE topic_id = ?
        GROUP BY stage
        """,
        (topic_id,),
    ).fetchall()

    stage_metrics: list[StageMetrics] = []
    total_cost = 0.0
    total_ptoks = 0
    total_ctoks = 0
    total_calls = 0
    total_success = 0
    total_failure = 0
    all_quality: list[float] = []
    total_duration = 0.0

    for r in prov_rows:
        sm = StageMetrics(
            stage=r["stage"] or "unknown",
            primitive_calls=r["calls"],
            success_count=r["successes"],
            failure_count=r["failures"],
            total_cost_usd=r["cost"],
            total_prompt_tokens=r["ptoks"],
            total_completion_tokens=r["ctoks"],
            avg_quality_score=r["avg_quality"],
            total_duration_sec=r["duration_sec"] or 0.0,
        )
        stage_metrics.append(sm)
        total_cost += r["cost"]
        total_ptoks += r["ptoks"]
        total_ctoks += r["ctoks"]
        total_calls += r["calls"]
        total_success += r["successes"]
        total_failure += r["failures"]
        if r["avg_quality"] is not None:
            all_quality.append(r["avg_quality"])
        total_duration += r["duration_sec"] or 0.0

    # Token ledger (separate source for cost if available)
    ledger_row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) as cost FROM token_ledger WHERE topic_id = ?",
        (topic_id,),
    ).fetchone()
    ledger_cost = ledger_row["cost"] if ledger_row else 0.0
    if ledger_cost > total_cost:
        total_cost = ledger_cost

    # Decision log count
    dec_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM decision_log WHERE topic_id = ?",
        (topic_id,),
    ).fetchone()
    decision_count = dec_row["cnt"] if dec_row else 0

    # Human interventions from decision_log
    human_row = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM decision_log
        WHERE topic_id = ? AND choice LIKE '%human%'
        """,
        (topic_id,),
    ).fetchone()
    human_count = human_row["cnt"] if human_row else 0

    # Session observations
    obs_row = conn.execute(
        """
        SELECT COUNT(*) as cnt, COALESCE(SUM(latency_ms), 0) as lat
        FROM session_observations
        WHERE session_id IN (
            SELECT DISTINCT session_id FROM session_observations
        )
        """,
    ).fetchone()
    obs_count = obs_row["cnt"] if obs_row else 0
    obs_latency = obs_row["lat"] if obs_row else 0

    return TopicBaseline(
        topic_id=topic_id,
        topic_name=topic_name,
        total_cost_usd=total_cost,
        total_prompt_tokens=total_ptoks,
        total_completion_tokens=total_ctoks,
        total_primitive_calls=total_calls,
        success_rate=total_success / max(total_calls, 1),
        avg_quality_score=sum(all_quality) / len(all_quality) if all_quality else None,
        human_intervention_count=human_count,
        stage_metrics=stage_metrics,
        observation_count=obs_count,
        total_latency_ms=obs_latency,
        decision_count=decision_count,
    )


def save_baseline(snapshot: BaselineSnapshot, path: str | None = None) -> str:
    """Save baseline snapshot to JSON file. Returns the file path."""
    if path is None:
        path = f"baseline_{snapshot.snapshot_id}.json"
    with open(path, "w") as f:
        json.dump(asdict(snapshot), f, indent=2, default=str)
    logger.info("Baseline saved to %s", path)
    return path
