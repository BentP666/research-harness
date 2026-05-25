"""Supervisor and worker executors for long-running Codex tasks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from .models import (
    ExecutionResult,
    GateDecisionResult,
    LongTaskGate,
    LongTaskRun,
    LongTaskTask,
    TaskExecutionError,
)
from .store import LongTaskStore, now_iso


class TaskExecutor(Protocol):
    def execute(
        self,
        *,
        prompt: str,
        run_dir: Path,
        timeout_seconds: int,
    ) -> ExecutionResult: ...


@dataclass(frozen=True)
class DryRunExecutor:
    """Deterministic executor used for tests, demos, and mobile UI dry runs."""

    def execute(
        self,
        *,
        prompt: str,
        run_dir: Path,
        timeout_seconds: int,
    ) -> ExecutionResult:
        title = _extract_prompt_title(prompt)
        result = {
            "status": "complete",
            "summary": f"Dry run completed: {title}",
            "files_changed": [],
            "next_tasks": [],
            "blockers": [],
        }
        return ExecutionResult(
            status="complete",
            summary=result["summary"],
            final_text=json.dumps(result, ensure_ascii=False, indent=2),
            result=result,
        )


@dataclass(frozen=True)
class CodexExecutor:
    """Run a task through `codex exec` and capture structured artifacts."""

    cwd: Path
    model: str | None = None
    sandbox: str = "workspace-write"
    worktree_root: Path | None = None

    def execute(
        self,
        *,
        prompt: str,
        run_dir: Path,
        timeout_seconds: int,
    ) -> ExecutionResult:
        final_path = run_dir / "final.md"
        events_path = run_dir / "events.jsonl"
        execution_cwd = (
            prepare_task_worktree(self.cwd, self.worktree_root, run_dir.name)
            if self.worktree_root
            else self.cwd
        )
        _write_private_text(run_dir / "execution_cwd.txt", str(execution_cwd))
        cmd = [
            "codex",
            "exec",
            "-C",
            str(execution_cwd),
            "-s",
            self.sandbox,
            "--json",
            "-o",
            str(final_path),
            "-",
        ]
        if self.model:
            cmd[2:2] = ["-m", self.model]

        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            _write_private_text(run_dir / "raw_stdout.txt", exc.stdout or "")
            _write_private_text(run_dir / "raw_stderr.txt", exc.stderr or "")
            return ExecutionResult(
                status="quarantined",
                summary="Codex worker timed out before structured output",
                final_text="",
                result={"status": "quarantined", "blockers": ["codex_cli_timeout"]},
                error="codex_cli_timeout",
                exit_code=124,
                quarantine_reason={"reason": "codex_cli_timeout"},
            )

        _write_private_text(events_path, completed.stdout)
        if completed.stderr:
            _write_private_text(run_dir / "stderr.txt", completed.stderr)
        final_text = (
            final_path.read_text(encoding="utf-8") if final_path.exists() else ""
        )
        parsed = _parse_worker_result(final_text)
        status = parsed.get("status", "complete")
        if completed.returncode != 0 and status == "complete":
            status = "quarantined"
            parsed["status"] = status
            parsed.setdefault("blockers", []).append("codex_exec_nonzero")

        if status not in {"complete", "blocked", "quarantined"}:
            status = "quarantined"
            parsed["status"] = status
            parsed.setdefault("blockers", []).append("invalid_worker_status")

        return ExecutionResult(
            status=status,  # type: ignore[arg-type]
            summary=str(parsed.get("summary") or parsed.get("status") or status),
            final_text=final_text,
            result=parsed,
            error=";".join(parsed.get("blockers", []))
            if status == "quarantined"
            else None,
            exit_code=completed.returncode,
            quarantine_reason=parsed if status == "quarantined" else None,
            files_changed=list(parsed.get("files_changed") or []),
            next_tasks=list(parsed.get("next_tasks") or []),
        )


class LongTaskSupervisor:
    """High-level orchestration over the local longtask state store."""

    def __init__(self, store: LongTaskStore):
        self.store = store

    def start_run(
        self,
        title: str,
        objective_text: str,
        *,
        max_workers: int = 2,
    ) -> LongTaskRun:
        run = LongTaskRun(
            id=self.store.next_run_id(),
            title=title,
            objective=objective_text,
            max_workers=max(1, max_workers),
        )
        self.store.create_run(run)
        for task_title in extract_task_titles(objective_text):
            task_id = self.store.next_task_id(run.id)
            prompt = render_worker_prompt(
                objective=objective_text,
                task_id=task_id,
                task_title=task_title,
            )
            self.store.create_task(
                LongTaskTask(
                    id=task_id,
                    run_id=run.id,
                    title=task_title,
                    prompt=prompt,
                )
            )
        return run

    def create_gate(
        self,
        *,
        run_id: str,
        task_id: str | None,
        gate_type: str,
        title: str,
        token: str | None = None,
    ) -> LongTaskGate:
        gate = LongTaskGate(
            id=f"G{hashlib.sha1(f'{run_id}:{title}:{now_iso()}'.encode()).hexdigest()[:10]}",
            run_id=run_id,
            task_id=task_id,
            gate_type=gate_type,
            title=title,
            token_required=bool(token),
        )
        self.store.create_gate(gate, token_hash=_hash_token(token) if token else None)
        self.store.set_run_status(run_id, "waiting_gate")
        return gate

    def decide_gate(
        self,
        gate_id: str,
        *,
        decision: str,
        actor: str,
        token: str | None = None,
        note: str = "",
    ) -> GateDecisionResult:
        if decision not in {"approved", "rejected", "paused", "replan_requested"}:
            return GateDecisionResult(False, gate_id, "pending", "invalid decision")
        expected = self.store.gate_token_hash(gate_id)
        if expected and not hmac.compare_digest(_hash_token(token or ""), expected):
            return GateDecisionResult(
                False, gate_id, "pending", "invalid approval token"
            )
        return self._record_gate_decision(
            gate_id,
            decision=decision,
            actor=actor,
            note=note,
        )

    def _record_gate_decision(
        self,
        gate_id: str,
        *,
        decision: str,
        actor: str,
        note: str,
    ) -> GateDecisionResult:
        updated = self.store.update_gate(
            gate_id,
            status=decision,
            decision=decision,
            actor=actor,
            note=note,
        )
        if not updated:
            return GateDecisionResult(False, gate_id, "pending", "gate is not pending")
        gate = self.store.get_gate(gate_id)
        run_id = str(gate["run_id"])
        if decision == "approved":
            stop_reason = _run_stop_reason(self.store.get_run_detail(run_id))
            self.store.set_run_status(
                run_id,
                "complete"
                if stop_reason == "complete"
                else "waiting_gate"
                if stop_reason == "waiting_gate"
                else "active",
            )
        elif decision == "paused":
            self.store.set_run_status(run_id, "paused")
        else:
            self.store.set_run_status(run_id, "blocked")
        return GateDecisionResult(True, gate_id, decision, "decision recorded")  # type: ignore[arg-type]

    def describe_run(
        self,
        run_id: str,
        *,
        base_url: str = "",
        gate_link_expires_seconds: int = 24 * 60 * 60,
    ) -> dict[str, object]:
        """Return run detail enriched with notification-ready gate payloads."""
        detail = self.store.get_run_detail(run_id)
        detail["gates"] = [
            {
                **gate,
                "notification": self.gate_notification_payload(
                    str(gate["id"]),
                    base_url=base_url,
                    expires_in_seconds=gate_link_expires_seconds,
                ),
            }
            if gate.get("status") == "pending"
            else gate
            for gate in detail["gates"]
        ]
        return detail

    def gate_notification_payload(
        self,
        gate_id: str,
        *,
        base_url: str = "",
        expires_in_seconds: int = 24 * 60 * 60,
    ) -> dict[str, object]:
        """Build a phone/chat-friendly signed gate notification payload."""
        gate = self.store.get_gate(gate_id)
        expires_at = int(time.time()) + max(1, expires_in_seconds)
        actions = {
            "approve": self._signed_action(
                gate_id,
                decision="approved",
                label="Approve",
                base_url=base_url,
                expires_at=expires_at,
            ),
            "replan": self._signed_action(
                gate_id,
                decision="replan_requested",
                label="Replan",
                base_url=base_url,
                expires_at=expires_at,
            ),
            "pause": self._signed_action(
                gate_id,
                decision="paused",
                label="Pause",
                base_url=base_url,
                expires_at=expires_at,
            ),
            "reject": self._signed_action(
                gate_id,
                decision="rejected",
                label="Reject",
                base_url=base_url,
                expires_at=expires_at,
            ),
        }
        return {
            "gate_id": gate_id,
            "run_id": gate["run_id"],
            "task_id": gate.get("task_id"),
            "gate_type": gate["gate_type"],
            "title": gate["title"],
            "status": gate["status"],
            "expires_at": expires_at,
            "action_url": actions["approve"]["url"],
            "actions": actions,
        }

    def _signed_action(
        self,
        gate_id: str,
        *,
        decision: str,
        label: str,
        base_url: str,
        expires_at: int,
    ) -> dict[str, object]:
        query = urlencode(
            {
                "decision": decision,
                "expires_at": str(expires_at),
                "signature": self.sign_gate_action(
                    gate_id,
                    decision=decision,
                    expires_at=expires_at,
                ),
            }
        )
        prefix = base_url.rstrip("/")
        return {
            "label": label,
            "decision": decision,
            "method": "GET",
            "url": f"{prefix}/api/longtasks/gates/{gate_id}/action?{query}",
        }

    def sign_gate_action(self, gate_id: str, *, decision: str, expires_at: int) -> str:
        message = f"{gate_id}:{decision}:{expires_at}".encode("utf-8")
        secret = self.store.signing_secret().encode("utf-8")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    def decide_gate_with_signature(
        self,
        gate_id: str,
        *,
        decision: str,
        expires_at: int,
        signature: str,
        actor: str,
        note: str = "Signed LongTask mobile action link",
    ) -> GateDecisionResult:
        validated = self.validate_gate_signature(
            gate_id,
            decision=decision,
            expires_at=expires_at,
            signature=signature,
        )
        if not validated.accepted:
            return validated
        return self._record_gate_decision(
            gate_id,
            decision=decision,
            actor=actor,
            note=note,
        )

    def validate_gate_signature(
        self,
        gate_id: str,
        *,
        decision: str,
        expires_at: int,
        signature: str,
    ) -> GateDecisionResult:
        if expires_at < int(time.time()):
            return GateDecisionResult(
                False,
                gate_id,
                "pending",
                "signed gate action expired",
            )
        expected = self.sign_gate_action(
            gate_id,
            decision=decision,
            expires_at=expires_at,
        )
        if not hmac.compare_digest(expected, signature):
            return GateDecisionResult(
                False,
                gate_id,
                "pending",
                "invalid signed gate action",
            )
        if decision not in {"approved", "rejected", "paused", "replan_requested"}:
            return GateDecisionResult(False, gate_id, "pending", "invalid decision")
        try:
            gate = self.store.get_gate(gate_id)
        except KeyError:
            return GateDecisionResult(False, gate_id, "pending", "gate not found")
        if gate.get("status") != "pending":
            return GateDecisionResult(False, gate_id, "pending", "gate is not pending")
        return GateDecisionResult(True, gate_id, "pending", "signed gate action valid")

    def dispatch_ready(
        self,
        run_id: str,
        *,
        executor: TaskExecutor,
        limit: int | None = None,
        timeout_seconds: int = 300,
    ) -> list[ExecutionResult]:
        ready = self.store.ready_tasks(run_id)
        if limit is not None:
            ready = ready[: max(0, limit)]
        results: list[ExecutionResult] = []
        for task in ready:
            result = self._execute_task(task, executor, timeout_seconds=timeout_seconds)
            results.append(result)
        return results

    def supervise(
        self,
        run_id: str,
        *,
        executor: TaskExecutor,
        max_cycles: int = 10,
        limit_per_cycle: int | None = None,
        timeout_seconds: int = 300,
    ) -> dict[str, object]:
        """Run safe dispatch cycles until complete, gated, blocked, or exhausted.

        This is the local "keep going" primitive: it advances ready work without
        requiring the human to paste a new prompt after every node, but it still
        stops at pending human gates and quarantined/blocked tasks.
        """
        cycles = 0
        dispatched = 0
        stop_reason = "max_cycles"
        self.store.record_event(
            run_id=run_id,
            task_id=None,
            event_type="supervise_started",
            message=f"Supervise loop started for {run_id}",
            payload={"max_cycles": max_cycles, "limit_per_cycle": limit_per_cycle},
        )
        for cycle in range(max(0, max_cycles)):
            cycles = cycle + 1
            detail = self.store.get_run_detail(run_id)
            stop_reason = _run_stop_reason(detail)
            if stop_reason != "ready":
                break
            limit = limit_per_cycle or int(detail["run"].get("max_workers") or 1)
            results = self.dispatch_ready(
                run_id,
                executor=executor,
                limit=limit,
                timeout_seconds=timeout_seconds,
            )
            dispatched += len(results)
            if not results:
                stop_reason = "no_ready_tasks"
                break

        detail = self.store.get_run_detail(run_id)
        stop_reason = (
            _run_stop_reason(detail) if stop_reason == "ready" else stop_reason
        )
        if stop_reason == "complete":
            self.store.set_run_status(run_id, "complete")
        elif stop_reason == "waiting_gate":
            self.store.set_run_status(run_id, "waiting_gate")
        elif stop_reason in {"blocked", "quarantined"}:
            self.store.set_run_status(run_id, "blocked")

        summary = {
            "run_id": run_id,
            "cycles": cycles,
            "dispatched": dispatched,
            "stop_reason": stop_reason,
            "status": self.store.get_run_detail(run_id)["run"]["status"],
        }
        self.store.record_event(
            run_id=run_id,
            task_id=None,
            event_type="supervise_stopped",
            message=f"Supervise stopped: {stop_reason}",
            payload=summary,
        )
        return summary

    def ingest_next_tasks(
        self,
        *,
        run_id: str,
        source_task_id: str,
        next_tasks: list[dict[str, object]],
    ) -> list[LongTaskTask]:
        """Create queued next-wave tasks suggested by a completed worker.

        Duplicate titles are ignored, and every accepted task depends on the
        source task that proposed it so the execution path remains explicit.
        """
        if not next_tasks:
            return []
        detail = self.store.get_run_detail(run_id)
        objective = str(detail["run"]["objective"])
        existing_titles = {
            _normalize_title(str(task["title"]))
            for task in detail["tasks"]
            if str(task.get("title") or "").strip()
        }
        created: list[LongTaskTask] = []
        for candidate in next_tasks:
            if not isinstance(candidate, dict):
                continue
            title = str(candidate.get("title") or "").strip()
            normalized = _normalize_title(title)
            if not title or normalized in existing_titles:
                continue
            task_id = self.store.next_task_id(run_id)
            task = LongTaskTask(
                id=task_id,
                run_id=run_id,
                title=title,
                prompt=render_worker_prompt(
                    objective=objective,
                    task_id=task_id,
                    task_title=title,
                    suggested_prompt=str(candidate.get("prompt") or "").strip(),
                ),
                dependencies=_merge_dependencies(
                    source_task_id,
                    candidate.get("dependencies"),
                ),
                write_scope=_string_list(candidate.get("write_scope")),
                risk_level=str(candidate.get("risk_level") or "low"),
            )
            self.store.create_task(task)
            created.append(task)
            existing_titles.add(normalized)
        return created

    def _execute_task(
        self,
        task: dict[str, object],
        executor: TaskExecutor,
        *,
        timeout_seconds: int,
    ) -> ExecutionResult:
        task_id = str(task["id"])
        run_id = str(task["run_id"])
        prompt = str(task["prompt"])
        run_dir = self.store.runs_dir / run_id / task_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.store.harden_dir(run_dir)
        prompt_path = run_dir / "prompt.md"
        final_path = run_dir / "final.md"
        events_path = run_dir / "events.jsonl"
        result_path = run_dir / "result.json"
        quarantine_path = run_dir / "quarantine_reason.json"
        self.store.write_private_text(prompt_path, prompt)

        started_at = now_iso()
        self.store.update_task_status(task_id, "running")
        result = executor.execute(
            prompt=prompt,
            run_dir=run_dir,
            timeout_seconds=timeout_seconds,
        )
        if not final_path.exists():
            self.store.write_private_text(final_path, result.final_text)
        else:
            self.store.harden_file(final_path)
        if not events_path.exists():
            self.store.write_private_text(events_path, "")
        else:
            self.store.harden_file(events_path)
        self.store.write_private_text(
            result_path,
            json.dumps(result.result, ensure_ascii=False, indent=2),
        )
        quarantine_reason_path: str | None = None
        if result.status == "quarantined":
            self.store.write_private_text(
                quarantine_path,
                json.dumps(
                    result.quarantine_reason
                    or {"reason": result.error or "quarantined"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            quarantine_reason_path = str(quarantine_path)

        self.store.update_task_status(
            task_id,
            result.status,
            summary=result.summary,
            result=result.result,
        )
        self.store.record_attempt(
            run_id=run_id,
            task_id=task_id,
            status=result.status,
            started_at=started_at,
            finished_at=now_iso(),
            exit_code=result.exit_code,
            error=result.error,
            events_path=str(events_path),
            final_path=str(final_path),
            result_path=str(result_path),
            quarantine_reason_path=quarantine_reason_path,
        )
        if result.status == "complete":
            self.ingest_next_tasks(
                run_id=run_id,
                source_task_id=task_id,
                next_tasks=result.next_tasks,
            )
        return result


def extract_task_titles(objective_text: str) -> list[str]:
    """Extract checklist/bullet tasks from an objective document."""
    titles: list[str] = []
    for raw_line in objective_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        checklist = re.match(r"^[-*]\s+\[[ xX]\]\s+(.+)$", line)
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)
        match = checklist or numbered or bullet
        if not match:
            continue
        title = match.group(1).strip()
        if title and not title.lower().startswith(("do not ", "stop if ")):
            titles.append(title)
    if not titles:
        fallback = (
            objective_text.strip().splitlines()[0]
            if objective_text.strip()
            else "Long task"
        )
        titles.append(fallback.lstrip("# ").strip() or "Long task")
    return titles


def render_worker_prompt(
    *,
    objective: str,
    task_id: str,
    task_title: str,
    suggested_prompt: str = "",
) -> str:
    suggested_section = (
        f"\n## Suggested details from parent worker\n{suggested_prompt}\n"
        if suggested_prompt
        else ""
    )
    return f"""# Codex LongTask Worker

## Task
{task_id}: {task_title}
{suggested_section}

## Parent objective
{objective}

## Operating contract
- Work only on this task; do not perform external upload, publish, push, paid jobs, or destructive actions.
- If blocked, say so instead of inventing results.
- If a result is unsafe or incomplete, report `quarantined` or `blocked`.

## Required final response
Return a concise Markdown summary containing a JSON object with these fields:

```json
{{
  "status": "complete | blocked | quarantined",
  "summary": "one sentence",
  "files_changed": [],
  "artifacts": [],
  "blockers": [],
  "next_tasks": []
}}
```
"""


def _hash_token(token: str | None) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _merge_dependencies(source_task_id: str, value: object) -> list[str]:
    dependencies = [source_task_id]
    for dependency in _string_list(value):
        if dependency not in dependencies:
            dependencies.append(dependency)
    return dependencies


def _run_stop_reason(detail: dict[str, object]) -> str:
    gates = list(detail.get("gates") or [])
    tasks = list(detail.get("tasks") or [])
    if any(
        isinstance(gate, dict) and gate.get("status") == "pending" for gate in gates
    ):
        return "waiting_gate"
    if any(
        isinstance(task, dict) and task.get("status") == "quarantined" for task in tasks
    ):
        return "quarantined"
    if any(
        isinstance(task, dict) and task.get("status") == "blocked" for task in tasks
    ):
        return "blocked"
    if tasks and all(
        isinstance(task, dict) and task.get("status") == "complete" for task in tasks
    ):
        return "complete"
    if any(isinstance(task, dict) and task.get("status") == "queued" for task in tasks):
        return "ready"
    return "no_ready_tasks"


def prepare_task_worktree(cwd: Path, worktree_root: Path | None, task_id: str) -> Path:
    """Create or reuse a detached git worktree for one write-capable task."""
    if worktree_root is None:
        return cwd.resolve()
    root = worktree_root.expanduser().resolve()
    target = root / task_id
    if target.exists():
        return target
    root.mkdir(parents=True, exist_ok=True)
    top_level = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if top_level.returncode != 0:
        raise TaskExecutionError("worktree isolation requires a git repository")
    subprocess.run(
        [
            "git",
            "-C",
            top_level.stdout.strip(),
            "worktree",
            "add",
            "--detach",
            str(target),
            "HEAD",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return target


def _write_private_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if os.name == "posix":
        try:
            path.chmod(0o600)
        except OSError:
            pass


def _extract_prompt_title(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("T") and ":" in line:
            return line.split(":", 1)[1].strip()
    match = re.search(r"## Task\s+(.+?)(?:\n##|\Z)", prompt, flags=re.S)
    if match:
        lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
        if lines:
            return lines[0].split(":", 1)[-1].strip()
    return "Long task"


def _parse_worker_result(final_text: str) -> dict[str, object]:
    text = final_text.strip()
    if not text:
        return {
            "status": "quarantined",
            "summary": "Worker produced no final output",
            "blockers": ["empty_worker_output"],
        }
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = [fenced.group(1)] if fenced else []
    if text.startswith("{"):
        candidates.append(text)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {
        "status": "complete",
        "summary": text.splitlines()[0][:240],
        "files_changed": [],
        "next_tasks": [],
        "blockers": [],
    }
