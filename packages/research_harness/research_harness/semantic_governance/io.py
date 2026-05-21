"""Read-only B5 governance artifact discovery and JSON loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_B5_FILES = (
    "object_graph.json",
    "gate_log.json",
    "verification_report.json",
    "run_trace.json",
    "agent_output.json",
)


@dataclass(frozen=True)
class B5TaskBundlePaths:
    task_id: str
    baseline_id: str
    task_dir: Path
    baseline_dir: Path
    object_graph: Path
    gate_log: Path
    verification_report: Path
    run_trace: Path
    agent_output: Path

    def source_files(self, run_root: Path) -> dict[str, str]:
        return {
            "object_graph.json": str(self.object_graph.relative_to(run_root)),
            "gate_log.json": str(self.gate_log.relative_to(run_root)),
            "verification_report.json": str(
                self.verification_report.relative_to(run_root)
            ),
            "run_trace.json": str(self.run_trace.relative_to(run_root)),
            "agent_output.json": str(self.agent_output.relative_to(run_root)),
        }


def load_json(path: Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_b5_task_bundles(
    run_root: Path | str, baseline_id: str = "B5.full_rh"
) -> list[B5TaskBundlePaths]:
    """Discover complete B5 task bundles without writing to the Pilot-5 run root."""

    root = Path(run_root)
    bundles: list[B5TaskBundlePaths] = []
    for task_dir in sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith("rfb.")
    ):
        baseline_dir = task_dir / baseline_id
        if not baseline_dir.is_dir():
            continue
        paths = {name: baseline_dir / name for name in REQUIRED_B5_FILES}
        if all(path.exists() for path in paths.values()):
            bundles.append(
                B5TaskBundlePaths(
                    task_id=task_dir.name,
                    baseline_id=baseline_id,
                    task_dir=task_dir,
                    baseline_dir=baseline_dir,
                    object_graph=paths["object_graph.json"],
                    gate_log=paths["gate_log.json"],
                    verification_report=paths["verification_report.json"],
                    run_trace=paths["run_trace.json"],
                    agent_output=paths["agent_output.json"],
                )
            )
    return bundles


def load_combined_eval_summary(run_root: Path | str) -> dict[str, Any]:
    path = Path(run_root) / "combined_eval_summary.json"
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def combined_row_for_task(
    combined_eval_summary: dict[str, Any], task_id: str, baseline_id: str
) -> dict[str, Any]:
    for row in combined_eval_summary.get("rows", []):
        if row.get("task_id") == task_id and row.get("baseline_id") == baseline_id:
            return dict(row)
    return {}
