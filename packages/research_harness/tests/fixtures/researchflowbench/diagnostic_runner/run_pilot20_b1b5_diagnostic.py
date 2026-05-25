from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

EXTERNAL_TOOLS = {"external_search", "web_search", "paper_search", "browser_network_search"}


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _provider_from_stderr(stderr: str) -> str:
    for line in stderr.splitlines():
        if line.startswith("provider:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def run_cell(
    *,
    task_dir: str | Path,
    output_dir: str | Path,
    baseline_key: str,
    baseline_id: str,
    baseline_instruction: str,
    model: str,
    reasoning_effort: str,
    provider_profile: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run one synthetic diagnostic cell; tests monkeypatch subprocess.run."""

    task_path = Path(task_dir).resolve()
    cell_dir = Path(output_dir).resolve() / task_path.name / baseline_key
    cell_dir.mkdir(parents=True, exist_ok=True)
    raw_response_path = cell_dir / "raw_response.json"
    prompt = (
        "ResearchFlowBench diagnostic cell\n"
        f"Task: {task_path.name}\n"
        f"Baseline: {baseline_id}\n"
        f"Instruction: {baseline_instruction}\n"
    )
    (cell_dir / "prompt_used.md").write_text(prompt, encoding="utf-8")
    (cell_dir / "prompt_input.md").write_text(prompt, encoding="utf-8")
    cmd = [
        "codex",
        "exec",
        "-C",
        str(task_path),
        "-o",
        str(raw_response_path),
        "-m",
        model,
    ]
    try:
        completed = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = _decode(completed.stdout)
        stderr = _decode(completed.stderr)
        timed_out = False
        returncode: int | str = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = _decode(exc.output)
        stderr = _decode(exc.stderr)
        timed_out = True
        returncode = "timeout"

    (cell_dir / "raw_stdout.txt").write_text(stdout, encoding="utf-8")
    (cell_dir / "raw_stderr.txt").write_text(stderr, encoding="utf-8")
    partial = raw_response_path.read_text(encoding="utf-8") if raw_response_path.exists() else stdout
    (cell_dir / "partial_response.txt").write_text(partial, encoding="utf-8")
    provider_observed = _provider_from_stderr(stderr)
    failures = []
    if timed_out:
        failures.append("codex_cli_timeout")
    try:
        parsed = json.loads(partial) if partial.strip() else {}
    except json.JSONDecodeError:
        parsed = {}
        failures.append("agent_output_json_parse_failed")
    failures.extend(_external_tool_output_failures(parsed))
    failures = sorted(set(failures))
    hard_failure = bool(failures)

    _write_json(cell_dir / "timeout_metadata.json", {
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "input_mode": "stdin_dash_prompt",
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stderr_bytes": len(stderr.encode("utf-8")),
    })
    _write_json(cell_dir / "quarantine_reason.json", {
        "valid_experiment_result": not hard_failure,
        "hard_failures": failures,
    })
    _write_json(cell_dir / "agent_output.json", parsed if parsed else {"parse_failed": True})
    _write_json(cell_dir / "cost_latency_trace.json", {
        "task_id": task_path.name,
        "baseline_id": baseline_id,
        "token_usage": None,
        "token_usage_unknown_reason": "synthetic diagnostic timeout fixture",
    })
    _write_json(cell_dir / "eval_report.json", {"hard_failure": hard_failure, "failures": failures})
    _write_json(cell_dir / "run_trace.json", {
        "provider_observed": provider_observed,
        "reasoning_effort": reasoning_effort,
        "returncode": returncode,
        "tools_used": ["local_static_corpus"],
    })
    _write_json(cell_dir / "object_graph.json", {"objects": [], "edges": [], "synthetic": True})
    _write_json(cell_dir / "gate_log.json", {"advance_or_block": "block" if hard_failure else "advance"})
    _write_json(cell_dir / "verification_report.json", {"checks": [], "risks": failures})
    _write_json(cell_dir / "executor_config.json", {
        "baseline_key": baseline_key,
        "baseline_id": baseline_id,
        "model": model,
        "provider_profile": provider_profile,
    })
    result = {
        "cell_dir": str(cell_dir),
        "hard_failure": hard_failure,
        "quarantined": hard_failure,
        "provider_observed": provider_observed,
        "failures": failures,
    }
    return result


def _execution_order(task_keys: list[str], baseline_keys: list[str] | None) -> list[tuple[str, str]]:
    baselines = baseline_keys or ["B5", "B1"]
    return [(task, baseline) for task in task_keys for baseline in ["B5", "B1"] if baseline in baselines]


def _tool_call_count(stdout: str, stderr: str) -> int:
    text = f"{stdout}\n{stderr}"
    return text.count("function_call:")


def _external_tool_output_failures(output: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    run_trace = output.get("run_trace") if isinstance(output, dict) else {}
    tools_used = run_trace.get("tools_used", []) if isinstance(run_trace, dict) else []
    if any(str(tool) in EXTERNAL_TOOLS for tool in tools_used):
        failures.append("external_search_reference_in_output")
    if str(output.get("external_search", "")).lower() in {"used", "true", "enabled"}:
        failures.append("external_search_reference_in_output")
    return sorted(set(failures))
