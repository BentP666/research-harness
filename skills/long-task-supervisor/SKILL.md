---
name: long-task-supervisor
description: Use when a user wants Codex to run a long-horizon task with minimal manual intervention, split work into durable worker tasks, monitor execution, quarantine failures, and stop for mobile/human gate approvals.
---

# LongTask Supervisor

Use this skill to turn a long-running Codex objective into a supervised local run.

## When to Use

- The user asks to "全程推进", "long task", "后台跑", "少人工介入", or "mobile approval".
- The task has multiple checkpoints or parallelizable sub-tasks.
- The user needs a phone-friendly way to approve critical gates.

## Core Contract

1. Define one objective and explicit stop conditions.
2. Create a run with `rh longtask start <objective.md>`.
3. Dispatch only safe queued work by default; use dry-run unless the user explicitly wants real worker execution.
4. Treat timeout, parse failure, missing output, or unsafe worker behavior as `quarantined`; never backfill missing results.
5. Stop at human gates for upload, publish, push, paid API/model runs, claim-boundary changes, destructive operations, or unresolved conflicts.
6. Use `/longrun` in the web UI for mobile-friendly status and gate decisions.

## Commands

```bash
# Create a run from a Markdown objective/checklist
rh longtask start objective.md --title "RFB release readiness" --max-workers 4

# Inspect runs or one run
rh longtask status
rh longtask status --run-id <run_id>

# Dispatch ready tasks. Defaults to deterministic dry-run for safety.
rh longtask dispatch --run-id <run_id> --limit 2

# Keep going until complete, gated, blocked, quarantined, or max cycles.
rh longtask supervise --run-id <run_id> --max-cycles 10

# Actually call codex exec only when explicitly approved.
rh longtask dispatch --run-id <run_id> --execute --timeout-seconds 300
rh longtask supervise --run-id <run_id> --execute --timeout-seconds 300
rh longtask supervise --run-id <run_id> --execute --worktree-isolation

# Approve a gate from CLI if not using the mobile UI.
rh longtask gate approve <gate_id> --token "$LONGTASK_APPROVAL_TOKEN"

# Print a signed phone/chat payload for a pending gate.
rh longtask gate notification <gate_id> --base-url http://localhost:8000
rh longtask gate notification <gate_id> --provider feishu --base-url https://host
rh longtask gate notification <gate_id> --provider slack --base-url https://host
```

## Objective Template

```markdown
# Goal
[One durable outcome]

## Stop rules
- Do not upload, publish, push, run paid jobs, or change external resources.
- Stop for human approval before claim-boundary changes.

## Tasks
- [ ] Task A with clear output
- [ ] Task B with clear output
- [ ] Task C with clear output

## Acceptance criteria
- [ ] Each node has a structured summary
- [ ] Quarantined failures have reason files
- [ ] Human gates are recorded before risky actions
```

## UI

Start the FastAPI/Next.js app as usual, then open:

```text
/longrun
```

The page shows:

- current runs;
- execution-path timeline;
- one-line summary per node;
- pending gate cards with approve/replan/pause/reject actions;
- signed confirmation links and a copyable notification payload;
- a safe dry-run supervision button for mobile-side pushing.

Completed workers can suggest follow-up work through `next_tasks`; accepted
suggestions become queued dependent tasks in the same run. Duplicate suggested
task titles are ignored.

## Safety Notes

- Mobile approval tokens are hashed in the SQLite state store.
- The MVP supports both manual token input and time-limited signed action links.
- Signed action GET links are confirmation-only; POST or UI/CLI approval records
  the actual decision. Signed actions are pending-only/single-use.
- Feishu/Slack webhook delivery is dry-run unless `--send` is passed explicitly.
- Webhook `--send` requires HTTPS.
- HTTP dispatch/supervise is dry-run by default; real Codex execution through
  HTTP requires `RESEARCH_HARNESS_LONGTASK_API_EXECUTE=1`.
- Set `RESEARCH_HARNESS_LONGTASK_ADMIN_TOKEN` to require a local admin token on
  LongTask HTTP endpoints; the web client can pass it via
  `NEXT_PUBLIC_LONGTASK_ADMIN_TOKEN`.
- Worktree isolation creates detached per-task git checkouts; human review/merge
  remains separate from worker execution.
- Do not expose the FastAPI endpoint publicly without auth, TLS, and an allowlist.
