"""Cost and latency trace validator for ResearchFlowBench runs."""

from __future__ import annotations

from typing import Any


def make_cost_latency_stub(
    *,
    task_id: str,
    baseline_id: str,
    executor: str,
    provider: str,
    model: str,
    unknown_reason: str = "schema dry run; no model execution or token accounting performed",
) -> dict[str, Any]:
    """Create an explicit-unknown cost trace stub for non-model dry runs."""

    return {
        "schema_version": "researchflowbench.cost_latency_trace.v0.1",
        "task_id": task_id,
        "baseline_id": baseline_id,
        "executor": executor,
        "provider": provider,
        "model": model,
        "wall_clock_seconds": None,
        "wall_clock_unknown_reason": unknown_reason,
        "token_usage": None,
        "token_usage_unknown_reason": unknown_reason,
        "tool_call_count": 0,
        "retry_count": 0,
        "estimated_cost": None,
        "estimated_cost_unknown_reason": unknown_reason,
        "cost_trace_pass": True,
        "failures": [],
    }


def validate_cost_latency_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Validate that missing cost/latency values are explicit, not silent nulls."""

    failures: list[str] = []
    for field_name in ("executor", "provider", "model", "task_id", "baseline_id"):
        if not trace.get(field_name):
            failures.append(f"{field_name}_missing")

    if trace.get("wall_clock_seconds") is None and not trace.get(
        "wall_clock_unknown_reason"
    ):
        failures.append("wall_clock_seconds_missing_without_reason")
    elif trace.get("wall_clock_seconds") is not None and not _nonnegative_number(
        trace.get("wall_clock_seconds")
    ):
        failures.append("wall_clock_seconds_invalid")

    if trace.get("token_usage") is None and not trace.get("token_usage_unknown_reason"):
        failures.append("token_usage_missing_without_reason")
    elif trace.get("token_usage") is not None and not isinstance(
        trace.get("token_usage"), dict
    ):
        failures.append("token_usage_invalid")

    if trace.get("estimated_cost") is None and not trace.get(
        "estimated_cost_unknown_reason"
    ):
        failures.append("estimated_cost_missing_without_reason")
    elif trace.get("estimated_cost") is not None and not _nonnegative_number(
        trace.get("estimated_cost")
    ):
        failures.append("estimated_cost_invalid")

    for field_name in ("tool_call_count", "retry_count"):
        value = trace.get(field_name)
        if not isinstance(value, int) or value < 0:
            failures.append(f"{field_name}_invalid")

    report = dict(trace)
    report["schema_version"] = str(
        report.get("schema_version") or "researchflowbench.cost_latency_trace.v0.1"
    )
    report["cost_trace_pass"] = not failures
    report["failures"] = sorted(set(failures))
    return report


def _nonnegative_number(value: Any) -> bool:
    return isinstance(value, int | float) and value >= 0
