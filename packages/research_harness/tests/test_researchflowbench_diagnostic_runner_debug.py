from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

RUNNER_PATH = (
    Path(__file__).resolve().parent
    / "fixtures/researchflowbench/diagnostic_runner/run_pilot20_b1b5_diagnostic.py"
)
T04_TASK_DIR = (
    Path(__file__).resolve().parent
    / "fixtures/researchflowbench/pilot20_v0_synthetic_task_pack/tasks/T04_evidence_stale_propagation"
)


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rfb_debug_runner", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_timeout_writes_complete_quarantine_artifacts_and_uses_stdin(
    monkeypatch, tmp_path
):
    runner = _load_runner()
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        assert kwargs["input"].startswith("ResearchFlowBench diagnostic cell")
        assert "stdin" not in kwargs
        raw_response_path = Path(cmd[cmd.index("-o") + 1])
        assert raw_response_path.is_absolute()
        assert Path(cmd[cmd.index("-C") + 1]).is_absolute()
        raw_response_path.write_text(
            '{"answer":{"diagnosis":"partial"', encoding="utf-8"
        )
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=7,
            output=b"partial stdout from codex",
            stderr=b"provider: local-test-provider\npartial stderr",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_cell(
        task_dir=T04_TASK_DIR,
        output_dir=tmp_path,
        baseline_key="B5",
        baseline_id="B5.full_rh",
        baseline_instruction="Use RH workflow, but this test forces a timeout.",
        model="gpt-5.4-mini",
        reasoning_effort="low",
        provider_profile="codex_cli_config_default",
        timeout_seconds=7,
    )

    assert result["hard_failure"] is True
    assert result["quarantined"] is True
    assert result["provider_observed"] == "local-test-provider"
    assert set(result["failures"]) == {
        "agent_output_json_parse_failed",
        "codex_cli_timeout",
    }

    cell_dir = Path(result["cell_dir"])
    for filename in (
        "prompt_used.md",
        "prompt_input.md",
        "raw_stdout.txt",
        "raw_stderr.txt",
        "timeout_metadata.json",
        "partial_response.txt",
        "quarantine_reason.json",
        "agent_output.json",
        "cost_latency_trace.json",
        "eval_report.json",
        "run_trace.json",
        "object_graph.json",
        "gate_log.json",
        "verification_report.json",
        "executor_config.json",
    ):
        assert (cell_dir / filename).exists(), filename

    timeout_metadata = runner._load_json(cell_dir / "timeout_metadata.json")
    assert timeout_metadata["timed_out"] is True
    assert timeout_metadata["timeout_seconds"] == 7
    assert timeout_metadata["input_mode"] == "stdin_dash_prompt"
    assert timeout_metadata["stdout_bytes"] > 0
    assert timeout_metadata["stderr_bytes"] > 0

    quarantine = runner._load_json(cell_dir / "quarantine_reason.json")
    assert quarantine["valid_experiment_result"] is False
    assert quarantine["hard_failures"] == [
        "agent_output_json_parse_failed",
        "codex_cli_timeout",
    ]

    run_trace = runner._load_json(cell_dir / "run_trace.json")
    assert run_trace["provider_observed"] == "local-test-provider"
    assert run_trace["reasoning_effort"] == "low"
    assert run_trace["returncode"] == "timeout"


def test_execution_order_can_gate_single_baseline_retries():
    runner = _load_runner()

    assert runner._execution_order(["T04"], None) == [("T04", "B5"), ("T04", "B1")]
    assert runner._execution_order(["T04"], ["B5"]) == [("T04", "B5")]
    assert runner._execution_order(["T04"], ["B1"]) == [("T04", "B1")]


def test_tool_call_counter_ignores_echoed_prompt_prohibitions():
    runner = _load_runner()
    echoed_prompt = "\n".join(
        [
            "user",
            "Do not use web/external/browser search, network, shell commands, package installs.",
            "codex",
            '{"answer": {"diagnosis": "No external search used."}}',
        ]
    )

    assert runner._tool_call_count("", echoed_prompt) == 0
    assert runner._tool_call_count("", "function_call: exec_command") == 1


def test_external_tool_detection_allows_forbidden_self_report():
    runner = _load_runner()

    safe_output = {
        "run_trace": {
            "tools_used": ["local_static_corpus"],
            "external_search": "forbidden",
        }
    }
    unsafe_output = {"run_trace": {"tools_used": ["external_search"]}}
    unsafe_flag = {"external_search": "used"}

    assert runner._external_tool_output_failures(safe_output) == []
    assert runner._external_tool_output_failures(unsafe_output) == [
        "external_search_reference_in_output"
    ]
    assert runner._external_tool_output_failures(unsafe_flag) == [
        "external_search_reference_in_output"
    ]
