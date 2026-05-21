"""Model-free ResearchFlowBench Pilot-20 schema dry-run helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cost import make_cost_latency_stub, validate_cost_latency_trace
from .leakage import validate_leakage_audit
from .preflight import validate_allowed_tools_preflight
from .retrieval import (
    make_retrieval_provenance_rehearsal,
    validate_retrieval_provenance,
)
from .validators import validate_pilot20_task_pack


def run_schema_dry_run(
    task_pack_root: str | Path, output_dir: str | Path
) -> dict[str, Any]:
    """Run a static, no-model rehearsal for Pilot-20 T01–T05."""

    root = Path(task_pack_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    deterministic = validate_pilot20_task_pack(root).to_dict()
    task_dirs = sorted((root / "tasks").glob("T*_*/"))
    preflight_reports = [
        validate_allowed_tools_preflight(task_dir) for task_dir in task_dirs
    ]
    leakage_reports = [validate_leakage_audit(task_dir) for task_dir in task_dirs]
    retrieval_reports = [
        validate_retrieval_provenance(
            task_dir,
            trace=make_retrieval_provenance_rehearsal(task_dir),
        )
        for task_dir in task_dirs
    ]
    cost_reports = [
        validate_cost_latency_trace(
            make_cost_latency_stub(
                task_id=preflight_report["task_id"],
                baseline_id="schema_dry_run",
                executor="not_applicable_schema_dry_run",
                provider="not_applicable_schema_dry_run",
                model="not_applicable_schema_dry_run",
            )
        )
        for preflight_report in preflight_reports
    ]

    payloads = {
        "deterministic_validation_report.json": deterministic,
        "allowed_tools_preflight.json": _pack_report(
            "allowed_tools_preflight", preflight_reports
        ),
        "leakage_audit_report.json": _pack_report("leakage_audit", leakage_reports),
        "retrieval_provenance_rehearsal.json": _pack_report(
            "retrieval_provenance", retrieval_reports
        ),
        "cost_latency_trace_stub.json": _pack_report(
            "cost_latency_trace", cost_reports
        ),
    }
    for filename, payload in payloads.items():
        (out / filename).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    failures = _collect_failures(
        deterministic,
        preflight_reports,
        leakage_reports,
        retrieval_reports,
        cost_reports,
    )
    summary = {
        "schema_version": "researchflowbench.schema_dry_run.v0.1",
        "task_pack_root": str(root),
        "output_dir": str(out),
        "task_count": len(task_dirs),
        "dry_run_pass": not failures,
        "failures": failures,
        "reports": sorted(payloads),
    }
    (out / "schema_dry_run_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "schema_dry_run_report.md").write_text(
        _markdown_summary(summary), encoding="utf-8"
    )
    return summary


def _pack_report(kind: str, reports: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": f"researchflowbench.{kind}.pack.v0.1",
        "report_count": len(reports),
        "pass": all(
            report.get("preflight_pass", True)
            and report.get("independent_audit_pass", True)
            and report.get("retrieval_trace_complete", True)
            and report.get("cost_trace_pass", True)
            for report in reports
        ),
        "reports": reports,
    }


def _collect_failures(
    deterministic: dict[str, Any],
    preflight: list[dict[str, Any]],
    leakage: list[dict[str, Any]],
    retrieval: list[dict[str, Any]],
    cost: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if not deterministic.get("is_valid"):
        failures.extend(
            {"scope": "deterministic", "failure": issue.get("code")}
            for issue in deterministic.get("issues", [])
        )
    for scope, reports in (
        ("preflight", preflight),
        ("leakage", leakage),
        ("retrieval", retrieval),
        ("cost", cost),
    ):
        for report in reports:
            for failure in report.get("failures", []) or []:
                failures.append(
                    {
                        "scope": scope,
                        "task_id": report.get("task_id"),
                        "failure": failure,
                    }
                )
    return failures


def _markdown_summary(summary: dict[str, Any]) -> str:
    status = "PASS" if summary["dry_run_pass"] else "FAIL"
    lines = [
        "# ResearchFlowBench Pilot-20 Schema Dry Run",
        "",
        "Date: 2026-05-20",
        "Mode: static no-model rehearsal; not release-grade evidence.",
        "",
        f"Status: **{status}**",
        f"Task count: {summary['task_count']}",
        "",
        "## Reports written",
        "",
    ]
    lines.extend(f"- `{report}`" for report in summary["reports"])
    lines.extend(["", "## Failures", ""])
    if summary["failures"]:
        lines.extend(f"- `{failure}`" for failure in summary["failures"])
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)
