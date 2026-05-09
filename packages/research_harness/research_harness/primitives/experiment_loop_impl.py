"""Experiment iteration loop: code_generate → validate → run → record → feedback.

Inspired by karpathy/autoresearch's minimalist autonomous research pattern,
adapted for CPU agent experiments (LLM API calls, RAG tuning, prompt engineering)
rather than GPU training runs. Each iteration produces an ``experiment_loop_runs`` row;
the loop stops when the budget is exhausted or ``patience`` iterations pass without
improvement on the primary metric.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from ..experiment.sandbox import is_improvement, run_experiment
from ..experiment.validator import auto_fix_unbound_locals, validate_code
from ..storage.db import Database
from .registry import EXPERIMENT_LOOP_SPEC, register_primitive
from .types import (
    ExperimentBudget,
    ExperimentLoopOutput,
    ExperimentRunSummary,
    ExperimentSpec,
)

logger = logging.getLogger(__name__)


def _coerce_spec(**kwargs: Any) -> ExperimentSpec:
    """Accept either an ExperimentSpec or flat kwargs (MCP-friendly)."""
    if "spec" in kwargs and isinstance(kwargs["spec"], ExperimentSpec):
        return kwargs["spec"]

    budget_data = kwargs.get("budget", {}) or {}
    if isinstance(budget_data, ExperimentBudget):
        budget = budget_data
    else:
        budget = ExperimentBudget(
            max_iterations=int(budget_data.get("max_iterations", 10)),
            max_cost_usd=float(budget_data.get("max_cost_usd", 0.0)),
            max_tokens=int(budget_data.get("max_tokens", 0)),
            patience=int(budget_data.get("patience", 3)),
        )

    return ExperimentSpec(
        name=str(kwargs.get("name", "")),
        task_description=str(kwargs.get("task_description", "")),
        fixture_files=dict(kwargs.get("fixture_files") or {}),
        mutable_entry=str(kwargs.get("mutable_entry", "main.py")),
        primary_metric=str(kwargs.get("primary_metric", "")),
        direction=str(kwargs.get("direction", "max")),
        mode=str(kwargs.get("mode", "agent")),
        timeout_sec=float(kwargs.get("timeout_sec", 300.0)),
        env_vars=dict(kwargs.get("env_vars") or {}),
        budget=budget,
    )


def _record_experiment(db: Database, topic_id: int, spec: ExperimentSpec) -> int:
    conn = db.connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO experiments
                (topic_id, name, task_description, fixture_files_json,
                 mutable_entry, primary_metric, direction, mode, budget_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')
            """,
            (
                topic_id,
                spec.name or spec.primary_metric or "experiment",
                spec.task_description,
                json.dumps(spec.fixture_files),
                spec.mutable_entry,
                spec.primary_metric,
                spec.direction,
                spec.mode,
                json.dumps(
                    {
                        "max_iterations": spec.budget.max_iterations,
                        "max_cost_usd": spec.budget.max_cost_usd,
                        "max_tokens": spec.budget.max_tokens,
                        "patience": spec.budget.patience,
                    }
                ),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _record_run(
    db: Database,
    experiment_id: int,
    iteration: int,
    files: dict[str, str],
    code_hash: str,
    metrics: dict[str, float],
    primary_value: float | None,
    elapsed_sec: float,
    cost_usd: float,
    tokens_used: int,
    status: str,
    returncode: int,
    stdout_tail: str,
    stderr_tail: str,
    feedback: str,
) -> int:
    conn = db.connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO experiment_loop_runs
                (experiment_id, iteration, code_hash, files_json, metrics_json,
                 primary_metric_value, elapsed_sec, cost_usd, tokens_used, status,
                 returncode, stdout_tail, stderr_tail, feedback_to_next)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                iteration,
                code_hash,
                json.dumps(files),
                json.dumps(metrics),
                primary_value,
                elapsed_sec,
                cost_usd,
                tokens_used,
                status,
                returncode,
                stdout_tail,
                stderr_tail,
                feedback,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def _finalize_experiment(
    db: Database,
    experiment_id: int,
    best_run_id: int | None,
    status: str,
    stopped_reason: str,
) -> None:
    conn = db.connect()
    try:
        conn.execute(
            """
            UPDATE experiments
            SET best_run_id = ?, status = ?, stopped_reason = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (best_run_id, status, stopped_reason, experiment_id),
        )
        conn.commit()
    finally:
        conn.close()


def _build_feedback(
    spec: ExperimentSpec,
    iteration: int,
    primary_value: float | None,
    best_value: float | None,
    stdout_tail: str,
    stderr_tail: str,
    returncode: int,
) -> str:
    """Compact feedback string passed to the next code_generate call."""
    parts: list[str] = []
    if returncode != 0:
        tail = (stderr_tail or "").strip().splitlines()[-5:]
        parts.append(
            f"Iteration {iteration} failed (returncode={returncode}). "
            f"Last stderr: {' | '.join(tail)}"
        )
    elif primary_value is None:
        parts.append(
            f"Iteration {iteration} produced no `{spec.primary_metric}` metric. "
            "Ensure the code prints it in a line like "
            f"'{spec.primary_metric}: <value>'."
        )
    else:
        comparison = ""
        if best_value is not None:
            delta = primary_value - best_value
            trend = (
                "improved"
                if (
                    (spec.direction == "max" and delta > 0)
                    or (spec.direction == "min" and delta < 0)
                )
                else "regressed"
            )
            comparison = f" ({trend} by {delta:+.4f} vs best={best_value:.4f})"
        parts.append(
            f"Iteration {iteration}: {spec.primary_metric}={primary_value:.4f}"
            f"{comparison}."
        )
    return " ".join(parts)


def _resolve_code_generate() -> Callable[..., Any]:
    """Lazy import to avoid circular deps with llm_primitives."""
    from ..execution.llm_primitives import code_generate

    return code_generate


@register_primitive(EXPERIMENT_LOOP_SPEC)
def experiment_loop(
    *,
    db: Database,
    topic_id: int,
    code_generate_fn: Callable[..., Any] | None = None,
    **kwargs: Any,
) -> ExperimentLoopOutput:
    """Run the code_generate → experiment_run loop until budget/patience."""
    spec = _coerce_spec(**kwargs)
    if not spec.primary_metric:
        raise ValueError("experiment_loop requires spec.primary_metric")

    experiment_id = _record_experiment(db, topic_id, spec)
    gen = code_generate_fn or _resolve_code_generate()

    best_value: float | None = None
    best_iteration: int | None = None
    best_run_id: int | None = None
    total_cost = 0.0
    total_tokens = 0
    stagnation = 0
    stopped_reason = "completed"
    summaries: list[ExperimentRunSummary] = []

    previous_code = ""
    previous_metrics: dict[str, float] = {}
    feedback = ""

    for iteration in range(spec.budget.max_iterations):
        # Budget pre-check (skip first iter where totals are zero).
        if iteration > 0:
            if spec.budget.max_cost_usd > 0 and total_cost >= spec.budget.max_cost_usd:
                stopped_reason = "budget_cost"
                break
            if spec.budget.max_tokens > 0 and total_tokens >= spec.budget.max_tokens:
                stopped_reason = "budget_tokens"
                break

        # 1. Generate code.
        try:
            cg_out = gen(
                db=db,
                topic_id=topic_id,
                study_spec=spec.task_description,
                iteration=iteration,
                previous_code=previous_code,
                previous_metrics=previous_metrics,
                feedback=feedback,
            )
        except Exception as exc:
            logger.warning("code_generate failed at iteration %d: %s", iteration, exc)
            _record_run(
                db,
                experiment_id,
                iteration,
                {},
                "",
                {},
                None,
                0.0,
                0.0,
                0,
                "failed",
                -1,
                "",
                str(exc)[:500],
                f"generator error: {exc}",
            )
            stopped_reason = "error_generator"
            break

        generated_files = dict(getattr(cg_out, "files", {}) or {})
        entry = getattr(cg_out, "entry_point", spec.mutable_entry) or spec.mutable_entry
        gen_cost = float(getattr(cg_out, "cost_usd", 0.0) or 0.0)
        gen_tokens = int(getattr(cg_out, "tokens_used", 0) or 0)
        total_cost += gen_cost
        total_tokens += gen_tokens

        # 2. Merge fixtures + generated. Fixtures win on path collision so the
        # harness stays in control of eval set / scorer.
        files: dict[str, str] = {}
        files.update(generated_files)
        files.update(spec.fixture_files)
        if entry not in files:
            # Generator failed to emit an entry file; bail for this iteration.
            _record_run(
                db,
                experiment_id,
                iteration,
                files,
                "",
                {},
                None,
                0.0,
                gen_cost,
                gen_tokens,
                "invalid",
                -1,
                "",
                f"missing entry file: {entry}",
                f"Output lacked entry_point {entry!r}; got files={sorted(files)}",
            )
            feedback = f"Must emit a file named {entry!r} as the entry point."
            previous_code = ""
            previous_metrics = {}
            stagnation += 1
            continue

        entry_code = files[entry]

        # 3. Validate (agent-mode permits HTTP clients).
        if spec.mode != "skip":
            patched_code, _fixes = auto_fix_unbound_locals(entry_code)
            validation = validate_code(patched_code, mode=spec.mode)
            if not validation.ok:
                msg = "; ".join(
                    f"{i.category}:{i.message}"
                    for i in validation.issues
                    if i.severity == "error"
                )[:400]
                _record_run(
                    db,
                    experiment_id,
                    iteration,
                    files,
                    "",
                    {},
                    None,
                    0.0,
                    gen_cost,
                    gen_tokens,
                    "invalid",
                    -2,
                    "",
                    msg,
                    f"Validator rejected code: {msg}",
                )
                feedback = f"Previous code failed validation: {msg}"
                previous_code = entry_code
                previous_metrics = {}
                stagnation += 1
                continue
            files[entry] = patched_code
            entry_code = patched_code

        # 4. Run in sandbox.
        result = run_experiment(
            files=files,
            entry_point=entry,
            timeout_sec=spec.timeout_sec,
            extra_env=spec.env_vars,
        )

        primary_value: float | None = None
        if result.metrics and spec.primary_metric:
            for key, val in result.metrics.items():
                if key == spec.primary_metric or key.endswith(
                    f"/{spec.primary_metric}"
                ):
                    primary_value = val
                    break

        status = "completed"
        if result.timed_out:
            status = "timeout"
        elif result.returncode != 0:
            status = "failed"

        run_feedback = _build_feedback(
            spec,
            iteration,
            primary_value,
            best_value,
            result.stdout,
            result.stderr,
            result.returncode,
        )

        run_id = _record_run(
            db,
            experiment_id,
            iteration,
            files,
            result.code_hash,
            result.metrics,
            primary_value,
            result.elapsed_sec,
            gen_cost,
            gen_tokens,
            status,
            result.returncode,
            result.stdout[-2000:] if result.stdout else "",
            result.stderr[-1000:] if result.stderr else "",
            run_feedback,
        )

        summaries.append(
            ExperimentRunSummary(
                iteration=iteration,
                primary_metric_value=primary_value,
                status=status,
                elapsed_sec=result.elapsed_sec,
                cost_usd=gen_cost,
                tokens_used=gen_tokens,
                code_hash=result.code_hash,
            )
        )

        # 5. Improvement bookkeeping.
        improved = False
        if primary_value is not None:
            if best_value is None:
                improved = True
            else:
                improved = is_improvement(
                    primary_value,
                    best_value,
                    direction=("maximize" if spec.direction == "max" else "minimize"),
                )

        if improved:
            best_value = primary_value
            best_iteration = iteration
            best_run_id = run_id
            stagnation = 0
        else:
            stagnation += 1

        # Feed next iteration.
        previous_code = entry_code
        previous_metrics = dict(result.metrics)
        feedback = run_feedback

        if stagnation >= spec.budget.patience and best_value is not None:
            stopped_reason = "patience"
            break
    else:
        stopped_reason = "budget_iterations"

    final_status = "completed" if best_value is not None else "failed"
    _finalize_experiment(db, experiment_id, best_run_id, final_status, stopped_reason)

    return ExperimentLoopOutput(
        experiment_id=experiment_id,
        total_iterations=len(summaries),
        best_iteration=best_iteration,
        best_value=best_value,
        best_run_id=best_run_id,
        stopped_reason=stopped_reason,
        runs=summaries,
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
    )
