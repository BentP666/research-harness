"""CLI registration for Codex LongTask Supervisor."""

from __future__ import annotations

import json
from pathlib import Path

import click

from .notify import deliver_chat_notification
from .runner import CodexExecutor, DryRunExecutor, LongTaskSupervisor
from .store import LongTaskStore


def _store(home: str | None) -> LongTaskStore:
    return LongTaskStore(Path(home or ".longrun"))


def register(main: click.Group) -> None:
    @main.group("longtask")
    def longtask_group() -> None:
        """Codex long-task supervisor runs."""

    @longtask_group.command("start")
    @click.argument("objective_file", type=click.Path(exists=True, dir_okay=False))
    @click.option("--title", default=None, help="Run title; defaults to file stem.")
    @click.option("--home", default=".longrun", help="LongTask state directory.")
    @click.option("--max-workers", default=2, type=int)
    @click.pass_context
    def start(
        ctx: click.Context,
        objective_file: str,
        title: str | None,
        home: str,
        max_workers: int,
    ) -> None:
        """Create a run from an objective Markdown file."""
        path = Path(objective_file)
        supervisor = LongTaskSupervisor(_store(home))
        run = supervisor.start_run(
            title=title or path.stem.replace("_", " "),
            objective_text=path.read_text(encoding="utf-8"),
            max_workers=max_workers,
        )
        detail = supervisor.store.get_run_detail(run.id)
        if ctx.obj.get("json"):
            click.echo(json.dumps(detail, ensure_ascii=False, default=str))
        else:
            click.echo(f"Created longtask run {run.id}: {run.title}")
            for task in detail["tasks"]:
                click.echo(f"  {task['id']} [{task['status']}] {task['title']}")

    @longtask_group.command("status")
    @click.option("--home", default=".longrun")
    @click.option("--run-id", default=None)
    @click.pass_context
    def status(ctx: click.Context, home: str, run_id: str | None) -> None:
        """Show run status or list recent runs."""
        store = _store(home)
        if run_id:
            detail = store.get_run_detail(run_id)
            if ctx.obj.get("json"):
                click.echo(json.dumps(detail, ensure_ascii=False, default=str))
                return
            run = detail["run"]
            click.echo(f"{run['id']} [{run['status']}] {run['title']}")
            for task in detail["tasks"]:
                click.echo(f"  {task['id']} [{task['status']}] {task['title']}")
            for gate in detail["gates"]:
                click.echo(f"  {gate['id']} gate [{gate['status']}] {gate['title']}")
            return
        runs = store.list_runs()
        if ctx.obj.get("json"):
            click.echo(json.dumps(runs, ensure_ascii=False, default=str))
            return
        for run in runs:
            click.echo(
                f"{run['id']} [{run['status']}] {run['title']} "
                f"{run['complete_count'] or 0}/{run['task_count'] or 0}"
            )

    @longtask_group.command("dispatch")
    @click.option("--home", default=".longrun")
    @click.option("--run-id", required=True)
    @click.option("--limit", default=None, type=int)
    @click.option("--timeout-seconds", default=300, type=int)
    @click.option("--execute", is_flag=True, help="Actually call codex exec.")
    @click.option("--cwd", default=".", help="Workspace cwd for codex exec.")
    @click.option("--worktree-isolation", is_flag=True)
    @click.option("--worktree-root", default=".longrun/worktrees")
    @click.pass_context
    def dispatch(
        ctx: click.Context,
        home: str,
        run_id: str,
        limit: int | None,
        timeout_seconds: int,
        execute: bool,
        cwd: str,
        worktree_isolation: bool,
        worktree_root: str,
    ) -> None:
        """Run queued tasks. Defaults to deterministic dry-run for safety."""
        supervisor = LongTaskSupervisor(_store(home))
        executor = (
            CodexExecutor(
                Path(cwd).resolve(),
                worktree_root=Path(worktree_root) if worktree_isolation else None,
            )
            if execute
            else DryRunExecutor()
        )
        results = supervisor.dispatch_ready(
            run_id,
            executor=executor,
            limit=limit,
            timeout_seconds=timeout_seconds,
        )
        payload = [r.result for r in results]
        if ctx.obj.get("json"):
            click.echo(json.dumps(payload, ensure_ascii=False, default=str))
        else:
            click.echo(f"Dispatched {len(results)} task(s)")
            for result in results:
                click.echo(f"  [{result.status}] {result.summary}")

    @longtask_group.command("supervise")
    @click.option("--home", default=".longrun")
    @click.option("--run-id", required=True)
    @click.option("--max-cycles", default=10, type=int)
    @click.option("--limit-per-cycle", default=None, type=int)
    @click.option("--timeout-seconds", default=300, type=int)
    @click.option("--execute", is_flag=True, help="Actually call codex exec.")
    @click.option("--cwd", default=".", help="Workspace cwd for codex exec.")
    @click.option("--worktree-isolation", is_flag=True)
    @click.option("--worktree-root", default=".longrun/worktrees")
    @click.pass_context
    def supervise(
        ctx: click.Context,
        home: str,
        run_id: str,
        max_cycles: int,
        limit_per_cycle: int | None,
        timeout_seconds: int,
        execute: bool,
        cwd: str,
        worktree_isolation: bool,
        worktree_root: str,
    ) -> None:
        """Keep dispatching ready work until complete, gated, or blocked."""
        supervisor = LongTaskSupervisor(_store(home))
        executor = (
            CodexExecutor(
                Path(cwd).resolve(),
                worktree_root=Path(worktree_root) if worktree_isolation else None,
            )
            if execute
            else DryRunExecutor()
        )
        result = supervisor.supervise(
            run_id,
            executor=executor,
            max_cycles=max_cycles,
            limit_per_cycle=limit_per_cycle,
            timeout_seconds=timeout_seconds,
        )
        if ctx.obj.get("json"):
            click.echo(json.dumps(result, ensure_ascii=False, default=str))
        else:
            click.echo(
                f"Supervise stopped: {result['stop_reason']} "
                f"({result['dispatched']} dispatched)"
            )

    @longtask_group.group("gate")
    def gate_group() -> None:
        """Manage mobile approval gates."""

    @gate_group.command("create")
    @click.option("--home", default=".longrun")
    @click.option("--run-id", required=True)
    @click.option("--task-id", default=None)
    @click.option("--type", "gate_type", default="continue_next_wave")
    @click.option("--title", required=True)
    @click.option("--token", default=None, help="Optional mobile approval token.")
    @click.pass_context
    def gate_create(
        ctx: click.Context,
        home: str,
        run_id: str,
        task_id: str | None,
        gate_type: str,
        title: str,
        token: str | None,
    ) -> None:
        supervisor = LongTaskSupervisor(_store(home))
        gate = supervisor.create_gate(
            run_id=run_id,
            task_id=task_id,
            gate_type=gate_type,
            title=title,
            token=token,
        )
        if ctx.obj.get("json"):
            click.echo(json.dumps(gate.__dict__, ensure_ascii=False))
        else:
            click.echo(f"Created gate {gate.id}: {gate.title}")

    @gate_group.command("approve")
    @click.argument("gate_id")
    @click.option("--home", default=".longrun")
    @click.option("--token", default=None)
    @click.option("--actor", default="cli")
    @click.option("--note", default="")
    @click.pass_context
    def gate_approve(
        ctx: click.Context,
        gate_id: str,
        home: str,
        token: str | None,
        actor: str,
        note: str,
    ) -> None:
        supervisor = LongTaskSupervisor(_store(home))
        decision = supervisor.decide_gate(
            gate_id,
            decision="approved",
            actor=actor,
            token=token,
            note=note,
        )
        if ctx.obj.get("json"):
            click.echo(json.dumps(decision.__dict__, ensure_ascii=False))
        else:
            click.echo(decision.message)

    @gate_group.command("notification")
    @click.argument("gate_id")
    @click.option("--home", default=".longrun")
    @click.option("--base-url", default="http://localhost:8000")
    @click.option("--expires-seconds", default=24 * 60 * 60, type=int)
    @click.option(
        "--provider",
        type=click.Choice(["generic", "feishu", "slack"]),
        default="generic",
    )
    @click.option("--webhook-url", default=None)
    @click.option("--send", is_flag=True, help="Actually POST to the webhook URL.")
    @click.pass_context
    def gate_notification(
        ctx: click.Context,
        gate_id: str,
        home: str,
        base_url: str,
        expires_seconds: int,
        provider: str,
        webhook_url: str | None,
        send: bool,
    ) -> None:
        """Print a signed phone/chat notification payload for a gate."""
        supervisor = LongTaskSupervisor(_store(home))
        notification = supervisor.gate_notification_payload(
            gate_id,
            base_url=base_url,
            expires_in_seconds=expires_seconds,
        )
        delivery = deliver_chat_notification(
            notification,
            provider=provider,  # type: ignore[arg-type]
            webhook_url=webhook_url,
            send=send,
        )
        if ctx.obj.get("json"):
            click.echo(json.dumps(delivery.__dict__, ensure_ascii=False))
        else:
            click.echo(f"{notification['title']} [{notification['status']}]")
            click.echo(delivery.message)
            click.echo(f"approve: {notification['action_url']}")
