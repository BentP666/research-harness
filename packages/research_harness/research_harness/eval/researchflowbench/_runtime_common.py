"""Shared helpers for ResearchFlowBench runtime contract validators."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

EXTERNAL_SEARCH_TOOLS = frozenset(
    {"external_search", "web_search", "paper_search", "browser_network_search"}
)
RETRIEVAL_SENSITIVE_TASK_NOS = frozenset({"T01", "T02", "T05"})


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    return records


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def rel(task_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(task_dir))
    except ValueError:
        return str(path)


def task_no_from_task(task: dict[str, Any]) -> str:
    template_id = str(task.get("template_id") or "")
    if template_id.endswith(("T01", "T02", "T03", "T04", "T05")):
        return template_id.rsplit("-", 1)[-1]
    task_id = str(task.get("task_id") or "")
    if ".full_context_citation_eval." in task_id:
        return "T01"
    if ".open_world_attribution_abstain." in task_id:
        return "T02"
    if ".partial_support_claim." in task_id:
        return "T03"
    if ".evidence_stale_propagation." in task_id:
        return "T04"
    if ".false_novelty_baseline_gap." in task_id:
        return "T05"
    return ""


def sorted_unique(values: Any) -> list[str]:
    if values is None:
        return []
    return sorted({str(item) for item in values})


def local_corpus_path(task_dir: Path) -> Path:
    return task_dir / "tool_fixtures/local_static_corpus.jsonl"


def visible_manifest_path(task_dir: Path) -> Path:
    return task_dir / "tool_fixtures/visible_input_manifest.json"
