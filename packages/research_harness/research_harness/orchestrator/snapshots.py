"""Stage snapshot + rollback logic.

Snapshots capture the state of a topic at a given stage (artifacts, claims,
rubric scores) as a JSON blob. On rollback, later-stage artifacts are marked
stale and the orchestrator is rewound.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def create_snapshot(
    conn: sqlite3.Connection,
    topic_id: int,
    stage: str,
    run_id: int | None = None,
) -> int:
    artifacts = conn.execute(
        "SELECT id, stage, artifact_type, title, version, status FROM project_artifacts WHERE topic_id = ? AND (stale = 0 OR stale IS NULL)",
        (topic_id,),
    ).fetchall()

    claims = conn.execute(
        "SELECT c.id, c.text, c.claim_type FROM claims c WHERE c.topic_id = ?",
        (topic_id,),
    ).fetchall()

    rubric = conn.execute(
        "SELECT * FROM rubric_scores WHERE topic_id = ?",
        (topic_id,),
    ).fetchall()

    snapshot_data = {
        "artifacts": [dict(r) for r in artifacts],
        "claims": [dict(r) for r in claims],
        "rubric_scores": [dict(r) for r in rubric],
    }

    total_cost = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM token_ledger WHERE topic_id = ?",
        (topic_id,),
    ).fetchone()[0]

    cur = conn.execute(
        """
        INSERT INTO stage_snapshots (topic_id, stage, orchestrator_run_id, artifact_snapshot, token_cost_usd)
        VALUES (?, ?, ?, ?, ?)
        """,
        (topic_id, stage, run_id, json.dumps(snapshot_data), total_cost),
    )
    return cur.lastrowid  # type: ignore[return-value]


def rollback_to_stage(
    conn: sqlite3.Connection,
    topic_id: int,
    to_stage: str,
    reason: str,
    trigger: str = "user",
) -> dict[str, Any]:
    from .stages import STAGE_ORDER, stage_index

    to_idx = stage_index(to_stage)

    run = conn.execute(
        "SELECT id, current_stage FROM orchestrator_runs WHERE topic_id = ? ORDER BY id DESC LIMIT 1",
        (topic_id,),
    ).fetchone()
    if not run:
        return {"success": False, "error": "No orchestrator run found"}

    from_stage = run["current_stage"]

    snapshot = conn.execute(
        "SELECT id FROM stage_snapshots WHERE topic_id = ? AND stage = ? ORDER BY created_at DESC LIMIT 1",
        (topic_id, to_stage),
    ).fetchone()
    if not snapshot:
        return {"success": False, "error": f"No snapshot found for stage '{to_stage}'"}

    for stage in STAGE_ORDER:
        if stage_index(stage) > to_idx:
            conn.execute(
                "UPDATE project_artifacts SET stale = 1 WHERE topic_id = ? AND stage = ?",
                (topic_id, stage),
            )

    conn.execute(
        "UPDATE orchestrator_runs SET current_stage = ?, stage_status = 'in_progress', updated_at = datetime('now') WHERE topic_id = ?",
        (to_stage, topic_id),
    )

    rubric_snapshot = conn.execute(
        "SELECT artifact_snapshot FROM stage_snapshots WHERE id = ?",
        (snapshot["id"],),
    ).fetchone()

    conn.execute(
        """
        INSERT INTO rollback_log (topic_id, from_stage, to_stage, to_snapshot_id, trigger, reason, rubric_snapshot)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            topic_id,
            from_stage,
            to_stage,
            snapshot["id"],
            trigger,
            reason,
            rubric_snapshot["artifact_snapshot"] if rubric_snapshot else None,
        ),
    )

    conn.commit()

    return {
        "success": True,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "snapshot_id": snapshot["id"],
    }
