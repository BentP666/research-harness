"""Experiment Matrix primitive — builds cells from goals × atoms, runs proxy pass
via sandbox, and prunes/promotes based on delta to SOTA baseline.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MatrixCell(BaseModel):
    id: int | None = None
    topic_id: int
    goal_id: int
    atom_combo: list[int]
    status: str = "pending"
    proxy_metric_name: str | None = None
    proxy_metric_value: float | None = None
    baseline_metric: float | None = None
    delta_to_sota: float | None = None
    proxy_run_id: str | None = None


def build_matrix(topic_id: int, db: Any) -> list[MatrixCell]:
    """Build pending cells: each active goal × each atom (single-atom combos)."""
    conn = db.connect()
    try:
        goals = conn.execute(
            "SELECT id, baseline_metric, metric_name FROM goal_pool WHERE topic_id = ? AND status = 'active'",
            (topic_id,),
        ).fetchall()
        atoms = conn.execute(
            "SELECT id FROM method_atoms WHERE topic_id = ?",
            (topic_id,),
        ).fetchall()
    finally:
        conn.close()

    if not goals:
        raise RuntimeError("No active goals found. Build goal pool first.")
    if not atoms:
        raise RuntimeError("No method atoms found. Harvest atoms first.")

    cells: list[MatrixCell] = []
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM experiment_matrix_cell WHERE topic_id = ? AND status = 'pending'",
            (topic_id,),
        )
        for goal in goals:
            for atom in atoms:
                combo = [atom["id"]]
                cur = conn.execute(
                    """INSERT INTO experiment_matrix_cell
                       (topic_id, goal_id, atom_combo, status, baseline_metric, proxy_metric_name)
                       VALUES (?, ?, ?, 'pending', ?, ?)""",
                    (
                        topic_id,
                        goal["id"],
                        json.dumps(combo),
                        goal["baseline_metric"],
                        goal["metric_name"],
                    ),
                )
                cells.append(
                    MatrixCell(
                        id=cur.lastrowid,
                        topic_id=topic_id,
                        goal_id=goal["id"],
                        atom_combo=combo,
                        status="pending",
                        baseline_metric=goal["baseline_metric"],
                        proxy_metric_name=goal["metric_name"],
                    )
                )
        conn.commit()
    finally:
        conn.close()

    return cells


def run_proxy_pass(topic_id: int, db: Any, max_cells: int = 20) -> list[MatrixCell]:
    """Run proxy experiments on pending cells using the sandbox.

    For each pending cell:
    1. Generate experiment code via LLM (code_generate)
    2. Run in sandbox
    3. Extract primary metric
    4. Compute delta_to_sota = baseline_metric - proxy_metric_value
    5. Status: promoted if delta > 0, pruned if delta <= 0
    """
    conn = db.connect()
    try:
        rows = conn.execute(
            """SELECT * FROM experiment_matrix_cell
               WHERE topic_id = ? AND status = 'pending'
               ORDER BY id LIMIT ?""",
            (topic_id, max_cells),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    results: list[MatrixCell] = []

    for row in rows:
        cell_id = row["id"]
        baseline = row["baseline_metric"] or 0.0

        conn = db.connect()
        try:
            conn.execute(
                "UPDATE experiment_matrix_cell SET status = 'proxy_running', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (cell_id,),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            atom_ids = json.loads(row["atom_combo"])
            conn = db.connect()
            try:
                atom_rows = conn.execute(
                    f"SELECT name, description FROM method_atoms WHERE id IN ({','.join('?' * len(atom_ids))})",
                    atom_ids,
                ).fetchall()
            finally:
                conn.close()

            atom_desc = "\n".join(
                f"- {a['name']}: {a['description']}" for a in atom_rows
            )

            from research_harness.execution.llm_primitives import (
                _get_client,
                _client_chat,
            )

            client = _get_client(None, tier="medium", task_name="proxy_code_gen")
            prompt = (
                f"Generate a minimal Python experiment script that implements these method atoms:\n"
                f"{atom_desc}\n\n"
                f'The script should output a JSON line to stdout: {{"metric": <float>}}\n'
                f"Metric: {row['proxy_metric_name']}\n"
                f"Keep it under 50 lines. Use synthetic data if needed."
            )
            code = _client_chat(client, prompt)

            from research_harness.execution.llm_primitives import _parse_json

            code_parsed = _parse_json(code, primitive="proxy_code")
            if isinstance(code_parsed, dict) and "code" in code_parsed:
                code = code_parsed["code"]

            from research_harness.experiment.sandbox import run_experiment

            result = run_experiment(code=code, timeout_sec=60.0)

            metric_value = None
            for line in result.stdout.strip().split("\n"):
                try:
                    parsed = json.loads(line)
                    if "metric" in parsed:
                        metric_value = float(parsed["metric"])
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

            if metric_value is None:
                metric_value = baseline

            delta = baseline - metric_value
            new_status = "promoted" if delta > 0 else "pruned"

        except Exception as exc:
            logger.warning("Proxy pass failed for cell %d: %s", cell_id, exc)
            metric_value = None
            delta = None
            new_status = "proxy_done"

        conn = db.connect()
        try:
            conn.execute(
                """UPDATE experiment_matrix_cell SET
                     status = ?, proxy_metric_value = ?, delta_to_sota = ?,
                     updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (new_status, metric_value, delta, cell_id),
            )
            conn.commit()
        finally:
            conn.close()

        results.append(
            MatrixCell(
                id=cell_id,
                topic_id=topic_id,
                goal_id=row["goal_id"],
                atom_combo=json.loads(row["atom_combo"]),
                status=new_status,
                proxy_metric_name=row["proxy_metric_name"],
                proxy_metric_value=metric_value,
                baseline_metric=baseline,
                delta_to_sota=delta,
            )
        )

    return results
