"""Data models for the Codex LongTask Supervisor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

TaskStatus = Literal[
    "queued",
    "running",
    "complete",
    "blocked",
    "quarantined",
    "waiting_gate",
    "skipped",
]

RunStatus = Literal["active", "waiting_gate", "complete", "blocked", "paused"]

GateStatus = Literal["pending", "approved", "rejected", "paused", "replan_requested"]

Decision = Literal["approved", "rejected", "paused", "replan_requested"]


@dataclass(frozen=True)
class LongTaskRun:
    id: str
    title: str
    objective: str
    status: RunStatus = "active"
    max_workers: int = 2


@dataclass(frozen=True)
class LongTaskTask:
    id: str
    run_id: str
    title: str
    prompt: str
    status: TaskStatus = "queued"
    dependencies: list[str] = field(default_factory=list)
    write_scope: list[str] = field(default_factory=list)
    risk_level: str = "low"
    summary: str = ""


@dataclass(frozen=True)
class LongTaskGate:
    id: str
    run_id: str
    task_id: str | None
    gate_type: str
    title: str
    status: GateStatus = "pending"
    token_required: bool = False


@dataclass(frozen=True)
class ExecutionResult:
    status: Literal["complete", "blocked", "quarantined"]
    summary: str
    final_text: str
    result: dict[str, Any]
    error: str | None = None
    exit_code: int | None = None
    quarantine_reason: dict[str, Any] | None = None
    files_changed: list[str] = field(default_factory=list)
    next_tasks: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GateDecisionResult:
    accepted: bool
    gate_id: str
    status: GateStatus
    message: str


class LongTaskError(RuntimeError):
    """Base error for longtask supervisor failures."""


class GateAuthError(LongTaskError):
    """Raised when a gate decision uses a missing or invalid token."""


class TaskExecutionError(LongTaskError):
    """Raised when a worker cannot be executed."""


def path_to_text(path: Path | None) -> str | None:
    return str(path) if path is not None else None
