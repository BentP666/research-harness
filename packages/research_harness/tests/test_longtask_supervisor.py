from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from research_harness.longtask import (
    DryRunExecutor,
    ExecutionResult,
    LongTaskStore,
    LongTaskSupervisor,
    build_chat_notification,
    deliver_chat_notification,
)
from research_harness.longtask.runner import prepare_task_worktree


class FailingExecutor:
    def execute(
        self, *, prompt: str, run_dir: Path, timeout_seconds: int
    ) -> ExecutionResult:
        return ExecutionResult(
            status="quarantined",
            summary="worker timed out before structured output",
            final_text="",
            result={"status": "quarantined", "blockers": ["timeout"]},
            error="codex_cli_timeout",
            exit_code=124,
            quarantine_reason={"reason": "codex_cli_timeout"},
        )


class NextTaskExecutor:
    def execute(
        self, *, prompt: str, run_dir: Path, timeout_seconds: int
    ) -> ExecutionResult:
        next_tasks = [
            {
                "title": "Verify generated mobile approval payload",
                "prompt": "Check that the approval notification can be copied to a phone chat.",
                "risk_level": "medium",
                "write_scope": ["web/src/app/longrun/page.tsx"],
            },
            {
                "title": "Verify generated mobile approval payload",
                "prompt": "Duplicate suggestion should not create another node.",
            },
        ]
        return ExecutionResult(
            status="complete",
            summary="Worker produced next-wave task suggestions",
            final_text=json.dumps(
                {
                    "status": "complete",
                    "summary": "Worker produced next-wave task suggestions",
                    "next_tasks": next_tasks,
                },
                ensure_ascii=False,
            ),
            result={"status": "complete", "summary": "done", "next_tasks": next_tasks},
            next_tasks=next_tasks,
        )


def test_start_run_extracts_checklist_tasks(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)

    run = supervisor.start_run(
        title="Mobile gate MVP",
        objective_text="""
# Goal
Build the MVP.

## Tasks
- [ ] Implement durable state
- [ ] Add mobile approval gate
- [ ] Render execution path UI
""".strip(),
        max_workers=3,
    )

    detail = store.get_run_detail(run.id)
    assert detail["run"]["title"] == "Mobile gate MVP"
    assert detail["run"]["status"] == "active"
    assert [task["title"] for task in detail["tasks"]] == [
        "Implement durable state",
        "Add mobile approval gate",
        "Render execution path UI",
    ]
    assert all(task["status"] == "queued" for task in detail["tasks"])


def test_dry_run_dispatch_completes_ready_tasks_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="One task",
        objective_text="- [ ] Produce a status summary",
        max_workers=1,
    )

    results = supervisor.dispatch_ready(run.id, executor=DryRunExecutor(), limit=1)

    assert len(results) == 1
    detail = store.get_run_detail(run.id)
    task = detail["tasks"][0]
    assert task["status"] == "complete"
    assert task["summary"] == "Dry run completed: Produce a status summary"

    attempt = detail["attempts"][0]
    assert attempt["status"] == "complete"
    assert Path(attempt["final_path"]).exists()
    result_payload = json.loads(Path(attempt["result_path"]).read_text())
    assert result_payload["status"] == "complete"


def test_dispatch_quarantines_failed_worker_without_backfilling(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Timeout task",
        objective_text="- [ ] Run risky diagnostic",
    )

    supervisor.dispatch_ready(run.id, executor=FailingExecutor(), limit=1)

    detail = store.get_run_detail(run.id)
    task = detail["tasks"][0]
    assert task["status"] == "quarantined"
    assert task["summary"] == "worker timed out before structured output"
    attempt = detail["attempts"][0]
    assert attempt["error"] == "codex_cli_timeout"
    assert Path(attempt["quarantine_reason_path"]).exists()


def test_gate_approval_requires_token_when_configured(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(title="Gate run", objective_text="- [ ] Prepare release")
    task_id = store.get_run_detail(run.id)["tasks"][0]["id"]
    approval_code = "fixture-passcode"
    wrong_code = "wrong-passcode"
    gate = supervisor.create_gate(
        run_id=run.id,
        task_id=task_id,
        gate_type="continue_next_wave",
        title="Approve next wave",
        token=approval_code,
    )

    assert not supervisor.decide_gate(
        gate.id,
        decision="approved",
        actor="mobile",
        token=wrong_code,
        note="bad attempt",
    ).accepted

    decision = supervisor.decide_gate(
        gate.id,
        decision="approved",
        actor="mobile",
        token=approval_code,
        note="continue",
    )
    assert decision.accepted
    detail = store.get_run_detail(run.id)
    assert detail["gates"][0]["status"] == "approved"
    assert detail["gates"][0]["decision"] == "approved"
    assert detail["run"]["status"] == "active"


def test_run_summary_counts_are_not_inflated_by_task_gate_join(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Counts",
        objective_text="- [ ] First task\n- [ ] Second task",
    )
    task_id = store.get_run_detail(run.id)["tasks"][0]["id"]
    supervisor.create_gate(
        run_id=run.id,
        task_id=task_id,
        gate_type="continue_next_wave",
        title="One gate",
    )

    summary = store.list_runs()[0]

    assert summary["task_count"] == 2
    assert summary["pending_gate_count"] == 1


def test_completed_worker_next_tasks_create_dependent_next_wave_without_duplicates(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Next wave",
        objective_text="- [ ] Build first node",
    )

    supervisor.dispatch_ready(run.id, executor=NextTaskExecutor(), limit=1)
    detail = store.get_run_detail(run.id)

    assert [task["title"] for task in detail["tasks"]] == [
        "Build first node",
        "Verify generated mobile approval payload",
    ]
    next_task = detail["tasks"][1]
    assert next_task["status"] == "queued"
    assert next_task["dependencies"] == ["T001"]
    assert next_task["risk_level"] == "medium"
    assert next_task["write_scope"] == ["web/src/app/longrun/page.tsx"]

    # Re-ingesting the same worker suggestion should remain idempotent.
    supervisor.ingest_next_tasks(
        run_id=run.id,
        source_task_id="T001",
        next_tasks=[
            {
                "title": "Verify generated mobile approval payload",
                "prompt": "same next task",
            }
        ],
    )
    assert len(store.get_run_detail(run.id)["tasks"]) == 2


def test_gate_notification_payload_uses_signed_action_url_without_token_leakage(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Gate links", objective_text="- [ ] Prepare approval"
    )
    task_id = store.get_run_detail(run.id)["tasks"][0]["id"]
    approval_code = "fixture-redacted-passcode"
    gate = supervisor.create_gate(
        run_id=run.id,
        task_id=task_id,
        gate_type="continue_next_wave",
        title="Approve next wave",
        token=approval_code,
    )

    detail_json = json.dumps(store.get_run_detail(run.id), ensure_ascii=False)
    assert approval_code not in detail_json
    assert "token_hash" not in detail_json

    payload = supervisor.gate_notification_payload(
        gate.id,
        base_url="https://rh.example.test",
        expires_in_seconds=600,
    )
    payload_json = json.dumps(payload, ensure_ascii=False)
    assert payload["title"] == "Approve next wave"
    assert payload["status"] == "pending"
    assert payload["action_url"].startswith(
        "https://rh.example.test/api/longtasks/gates/"
    )
    assert "fixture-redacted-passcode" not in payload_json

    parsed = urlparse(payload["actions"]["approve"]["url"])
    params = parse_qs(parsed.query)
    decision = supervisor.decide_gate_with_signature(
        gate.id,
        decision=params["decision"][0],
        expires_at=int(params["expires_at"][0]),
        signature=params["signature"][0],
        actor="mobile-link",
    )
    assert decision.accepted
    assert store.get_run_detail(run.id)["gates"][0]["status"] == "approved"

    replay = supervisor.decide_gate_with_signature(
        gate.id,
        decision=params["decision"][0],
        expires_at=int(params["expires_at"][0]),
        signature=params["signature"][0],
        actor="mobile-link",
    )
    assert not replay.accepted
    assert replay.message == "gate is not pending"


def test_signed_gate_action_rejects_expired_signature(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Expired link", objective_text="- [ ] Prepare approval"
    )
    gate = supervisor.create_gate(
        run_id=run.id,
        task_id=None,
        gate_type="continue_next_wave",
        title="Approve expired link",
    )
    signature = supervisor.sign_gate_action(
        gate.id,
        decision="approved",
        expires_at=1,
    )

    decision = supervisor.decide_gate_with_signature(
        gate.id,
        decision="approved",
        expires_at=1,
        signature=signature,
        actor="mobile-link",
    )

    assert not decision.accepted
    assert decision.message == "signed gate action expired"


def test_supervise_loop_runs_until_complete_and_records_stop_event(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Supervise complete",
        objective_text="- [ ] First dry node\n- [ ] Second dry node",
        max_workers=2,
    )

    result = supervisor.supervise(
        run.id,
        executor=DryRunExecutor(),
        max_cycles=3,
    )

    assert result["stop_reason"] == "complete"
    assert result["dispatched"] == 2
    detail = store.get_run_detail(run.id)
    assert detail["run"]["status"] == "complete"
    assert all(task["status"] == "complete" for task in detail["tasks"])
    assert detail["events"][-1]["event_type"] == "supervise_stopped"


def test_longtask_state_and_artifacts_are_private_on_posix(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(
        title="Private files", objective_text="- [ ] Write artifacts"
    )
    supervisor.dispatch_ready(run.id, executor=DryRunExecutor(), limit=1)
    detail = store.get_run_detail(run.id)
    attempt = detail["attempts"][0]

    if os.name == "posix":
        assert oct(store.home.stat().st_mode & 0o777) == "0o700"
        assert oct(store.runs_dir.stat().st_mode & 0o777) == "0o700"
        assert oct(store.db_path.stat().st_mode & 0o777) == "0o600"
        for key in ("events_path", "final_path", "result_path"):
            assert oct(Path(attempt[key]).stat().st_mode & 0o777) == "0o600"


def test_supervise_loop_stops_at_pending_gate_without_dispatch(tmp_path: Path) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(title="Gate stop", objective_text="- [ ] Waiting task")
    supervisor.create_gate(
        run_id=run.id,
        task_id=None,
        gate_type="continue_next_wave",
        title="Human check",
    )

    result = supervisor.supervise(
        run.id,
        executor=DryRunExecutor(),
        max_cycles=3,
    )

    assert result["stop_reason"] == "waiting_gate"
    assert result["dispatched"] == 0
    assert store.get_run_detail(run.id)["tasks"][0]["status"] == "queued"


def test_run_moves_to_waiting_gate_if_other_gate_remains_after_approval(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(title="Two gates", objective_text="- [ ] First")
    detail = store.get_run_detail(run.id)
    task_id = detail["tasks"][0]["id"]
    first_gate = supervisor.create_gate(
        run_id=run.id,
        task_id=task_id,
        gate_type="continue_next_wave",
        title="gate one",
    )
    supervisor.create_gate(
        run_id=run.id,
        task_id=task_id,
        gate_type="continue_next_wave",
        title="gate two",
    )

    first = supervisor.decide_gate(
        first_gate.id,
        decision="approved",
        actor="mobile",
        note="approve",
    )

    assert first.accepted
    assert store.get_run_detail(run.id)["run"]["status"] == "waiting_gate"
    assert {gate["status"] for gate in store.get_run_detail(run.id)["gates"]} == {
        "approved",
        "pending",
    }


def test_chat_notification_builds_feishu_and_slack_cards_without_token_leakage(
    tmp_path: Path,
) -> None:
    store = LongTaskStore(tmp_path / ".longrun")
    supervisor = LongTaskSupervisor(store)
    run = supervisor.start_run(title="Notify", objective_text="- [ ] Prepare approval")
    approval_code = "fixture-passcode"
    gate = supervisor.create_gate(
        run_id=run.id,
        task_id=None,
        gate_type="continue_next_wave",
        title="Approve notification",
        token=approval_code,
    )
    notification = supervisor.gate_notification_payload(
        gate.id,
        base_url="https://rh.example.test",
    )

    feishu = build_chat_notification(notification, provider="feishu")
    slack = build_chat_notification(notification, provider="slack")

    feishu_json = json.dumps(feishu, ensure_ascii=False)
    slack_json = json.dumps(slack, ensure_ascii=False)
    assert feishu["msg_type"] == "interactive"
    assert "Approve notification" in feishu_json
    assert "https://rh.example.test/api/longtasks/gates/" in feishu_json
    assert slack["blocks"][0]["type"] == "header"
    assert "fixture-passcode" not in feishu_json
    assert "fixture-passcode" not in slack_json

    rejected = deliver_chat_notification(
        notification,
        provider="feishu",
        webhook_url="http://example.test/webhook",
        send=True,
    )
    assert not rejected.sent
    assert rejected.message == "webhook_url must use https when send=true"


def test_prepare_task_worktree_creates_detached_task_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=LongTask Test",
            "-c",
            "user.email=longtask@example.test",
            "commit",
            "-m",
            "init",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    worktree = prepare_task_worktree(repo, tmp_path / "worktrees", "T001")

    assert worktree.exists()
    assert (worktree / "README.md").read_text(encoding="utf-8") == "hello\n"
    assert prepare_task_worktree(repo, tmp_path / "worktrees", "T001") == worktree
