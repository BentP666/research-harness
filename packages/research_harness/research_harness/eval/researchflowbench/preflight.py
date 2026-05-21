"""Allowed-tools preflight validator for ResearchFlowBench runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._runtime_common import (
    EXTERNAL_SEARCH_TOOLS,
    load_json,
    local_corpus_path,
    sha256_file,
    sorted_unique,
    task_no_from_task,
)


def validate_allowed_tools_preflight(
    task_dir: str | Path,
    *,
    baseline_id: str = "schema_dry_run",
    runner_exposed_tools: list[str] | None = None,
    prompt_visible_tools: list[str] | None = None,
    external_search_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a task's allowed-tool contract before model execution.

    The validator is static and deterministic. It accepts optional runner and
    prompt tool inventories so callers can check a concrete run, while defaulting
    to the task-pack contract for schema dry runs.
    """

    task_path = Path(task_dir)
    task = load_json(task_path / "task.json")
    input_bundle = load_json(task_path / "input_bundle.json")
    contract = load_json(task_path / "tool_fixtures/allowed_tools_contract.json")
    visible_manifest = load_json(
        task_path / "tool_fixtures/visible_input_manifest.json"
    )

    declared_tools = _contract_tool_names(contract)
    disabled_tools = _disabled_tool_names(contract)
    task_tools = sorted_unique(task.get("allowed_tools"))
    input_tools = sorted_unique(input_bundle.get("allowed_tools"))
    runner_tools = sorted_unique(
        runner_exposed_tools if runner_exposed_tools is not None else declared_tools
    )
    prompt_tools = sorted_unique(
        prompt_visible_tools if prompt_visible_tools is not None else input_tools
    )
    fixture_paths = _fixture_paths(contract)
    fixture_hashes = _fixture_hashes(task_path, fixture_paths)
    external_tools_enabled = sorted(
        (
            set(task_tools)
            | set(input_tools)
            | set(declared_tools)
            | set(runner_tools)
            | set(prompt_tools)
        )
        & set(EXTERNAL_SEARCH_TOOLS)
    )

    failures: list[str] = []
    if not declared_tools:
        failures.append("declared_allowed_tools_missing")
    if set(runner_tools) - set(declared_tools):
        failures.append("runner_exposes_undeclared_tool")
    if set(prompt_tools) - set(declared_tools):
        failures.append("prompt_exposes_undeclared_tool")
    if set(task_tools) != set(declared_tools) or set(input_tools) != set(
        declared_tools
    ):
        failures.append("declared_allowed_tools_mismatch")

    forbidden_tools = set(sorted_unique(contract.get("forbidden_tools")))
    if not set(EXTERNAL_SEARCH_TOOLS).issubset(forbidden_tools):
        failures.append("external_tools_not_explicitly_forbidden")

    for tool_name in declared_tools:
        if tool_name in disabled_tools:
            continue
        fixture_path = fixture_paths.get(tool_name)
        if not fixture_path:
            failures.append(f"{tool_name}_fixture_missing")
            continue
        if not (task_path / "tool_fixtures" / fixture_path).exists():
            failures.append(f"{tool_name}_fixture_missing")
        elif not fixture_hashes.get(tool_name):
            failures.append(f"{tool_name}_fixture_hash_missing")

    if "local_static_corpus" in declared_tools:
        corpus_path = local_corpus_path(task_path)
        if (
            fixture_paths.get("local_static_corpus") != "local_static_corpus.jsonl"
            or not corpus_path.exists()
        ):
            failures.append("local_static_corpus_fixture_missing")
        if not fixture_hashes.get("local_static_corpus"):
            failures.append("local_static_corpus_hash_missing")

    policies = {
        str(task.get("external_search_policy") or ""),
        str(input_bundle.get("external_search_policy") or ""),
        str(visible_manifest.get("external_search_policy") or ""),
    }
    external_policy_enabled = policies != {"forbidden_in_v0"}
    external_enabled = bool(external_tools_enabled) or external_policy_enabled
    if task_no_from_task(task) == "T05" and external_enabled:
        failures.append("t05_external_search_enabled")
    if external_enabled and not _external_trace_complete(external_search_trace):
        failures.append("external_search_trace_missing")

    report = {
        "schema_version": "researchflowbench.allowed_tools_preflight.v0.1",
        "task_id": str(task.get("task_id") or ""),
        "baseline_id": baseline_id,
        "declared_allowed_tools": declared_tools,
        "runner_exposed_tools": runner_tools,
        "prompt_visible_tools": prompt_tools,
        "fixture_paths": fixture_paths,
        "fixture_hashes": fixture_hashes,
        "explicitly_disabled_tools": disabled_tools,
        "optional_tools_enabled": external_tools_enabled,
        "optional_tools_trace_required": bool(external_enabled),
        "forbidden_tools_absent": not bool(
            (set(runner_tools) | set(prompt_tools)) & set(EXTERNAL_SEARCH_TOOLS)
        ),
        "external_search_trace_complete": (not external_enabled)
        or _external_trace_complete(external_search_trace),
        "preflight_pass": not failures,
        "failures": sorted(set(failures)),
    }
    return report


def _contract_tool_names(contract: dict[str, Any]) -> list[str]:
    return sorted(
        str(item.get("tool_name"))
        for item in contract.get("allowed_tools", [])
        if isinstance(item, dict) and item.get("tool_name")
    )


def _disabled_tool_names(contract: dict[str, Any]) -> list[str]:
    disabled = set(str(item) for item in contract.get("disabled_tools", []) or [])
    for item in contract.get("allowed_tools", []) or []:
        if not isinstance(item, dict):
            continue
        if (
            item.get("enabled") is False
            or item.get("disabled") is True
            or item.get("mode") == "disabled"
        ):
            disabled.add(str(item.get("tool_name") or ""))
    return sorted(item for item in disabled if item)


def _fixture_paths(contract: dict[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for item in contract.get("allowed_tools", []) or []:
        if (
            isinstance(item, dict)
            and item.get("tool_name")
            and item.get("fixture_path")
        ):
            paths[str(item["tool_name"])] = str(item["fixture_path"])
    return paths


def _fixture_hashes(
    task_dir: Path, fixture_paths: dict[str, str]
) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for tool_name, fixture_path in fixture_paths.items():
        path = task_dir / "tool_fixtures" / fixture_path
        hashes[tool_name] = sha256_file(path) if path.exists() else None
    return hashes


def _external_trace_complete(trace: dict[str, Any] | None) -> bool:
    if not isinstance(trace, dict):
        return False
    return bool(
        trace.get("queries") and trace.get("results") and trace.get("cost_trace")
    )
