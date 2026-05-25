# Codex LongTask Supervisor 1.0.0

Status: Stable local-first implementation.

The LongTask Supervisor is a Codex-native supervision layer for long-running work:

```text
objective.md → task DAG → Codex workers → structured summaries → gate decisions → resume
```

It is not a replacement for Codex, tmux, or Codex Cloud. It keeps durable state, structured worker artifacts, quarantine records, and phone-friendly gate decisions around those execution backends.

## What ships in this 1.0.0 release

- SQLite state under `.longrun/state.db`.
- CLI commands under `rh longtask ...`.
- Deterministic dry-run dispatch for safe testing.
- Optional `codex exec` worker backend via `rh longtask dispatch --execute` or
  `rh longtask supervise --execute`.
- Optional detached git worktree isolation for real write-capable workers.
- Auto-ingestion of completed worker `next_tasks` as dependent next-wave tasks.
- Supervision loop that keeps dispatching ready work until complete, gated, or blocked.
- FastAPI endpoints under `/api/longtasks/*`.
- Mobile-friendly Next.js page at `/longrun`.
- Signed confirmation links with a mobile-friendly confirmation page and
  Feishu/Slack/generic notification payloads.
- Codex skill at `skills/long-task-supervisor/SKILL.md`.

## Start a run

Create an objective file:

```markdown
# Goal
Complete the release readiness packet.

## Stop rules
- Do not upload, publish, push, or run paid model experiments.
- Stop before changing public claim boundaries.

## Tasks
- [ ] Clean export and final scan
- [ ] Final claim/citation/visual review
- [ ] Prepare go/no-go receipt
```

Start the run:

```bash
rh longtask start objective.md --title "Release readiness" --max-workers 3
```

Check status:

```bash
rh longtask status
rh longtask status --run-id <run_id>
```

Create a mobile/human approval gate when the next step needs review:

```bash
rh longtask gate create --run-id <run_id> --title "Approve next wave" --token "$LONGTASK_APPROVAL_TOKEN"
```

Generate a signed notification payload that can be pasted into a phone chat or
wrapped by Feishu/Slack later:

```bash
rh longtask gate notification <gate_id> --base-url http://localhost:8000

# Provider-shaped dry-runs, safe by default:
rh longtask gate notification <gate_id> --provider feishu --base-url https://your-host
rh longtask gate notification <gate_id> --provider slack --base-url https://your-host

# Actual webhook delivery requires explicit --send and a webhook URL:
rh longtask gate notification <gate_id> --provider feishu --webhook-url "$FEISHU_WEBHOOK" --send
```

Dispatch in safe dry-run mode:

```bash
rh longtask dispatch --run-id <run_id> --limit 1
```

Keep going locally until the run completes, hits a gate, or quarantines/blocks:

```bash
rh longtask supervise --run-id <run_id> --max-cycles 10
```

Dispatch real Codex workers only after explicit approval:

```bash
rh longtask dispatch --run-id <run_id> --execute --timeout-seconds 300
rh longtask supervise --run-id <run_id> --execute --timeout-seconds 300

# Optional: run real workers in per-task detached worktrees under .longrun/worktrees.
rh longtask supervise --run-id <run_id> --execute --worktree-isolation
```

## Mobile approval/UI

Run the existing backend/frontend, then open `/longrun` from desktop or phone.

The page is intentionally simple:

1. run list;
2. progress stats;
3. pending gate cards;
4. signed confirmation link + copyable notification payload;
5. “Run safe cycle” dry-run supervision button;
6. vertical execution path;
7. one-line node summaries.

Gate decisions are written to `.longrun/state.db` and the event log.
Signed links are time-limited HMAC capability URLs generated from a local
`.longrun/signing.key`; approval tokens are not embedded in the URL. The GET
link is confirmation-only; state changes require POST or the local UI/CLI token
decision path.

## API endpoints

```http
GET  /api/longtasks/runs
POST /api/longtasks/runs
GET  /api/longtasks/runs/{run_id}
POST /api/longtasks/runs/{run_id}/dispatch
POST /api/longtasks/runs/{run_id}/supervise
POST /api/longtasks/runs/{run_id}/gates
POST /api/longtasks/gates/{gate_id}/decision
GET  /api/longtasks/gates/{gate_id}/action?decision=approved&expires_at=...&signature=...&view=1
POST /api/longtasks/gates/{gate_id}/action?decision=approved&expires_at=...&signature=...
```

`view=1` renders a mobile-friendly confirmation HTML page for the signed action.

HTTP dispatch/supervise defaults to dry-run. Real `codex exec` through HTTP is
blocked unless the server sets `RESEARCH_HARNESS_LONGTASK_API_EXECUTE=1`.
If `RESEARCH_HARNESS_LONGTASK_ADMIN_TOKEN` is set, all LongTask HTTP endpoints
require `X-LongTask-Token` or `Authorization: Bearer ...`.

Set a custom state directory with:

```bash
export RESEARCH_HARNESS_LONGTASK_HOME=/path/to/.longrun
export RESEARCH_HARNESS_HTTP_HOST=127.0.0.1
export RESEARCH_HARNESS_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Security posture

This 1.0.0 release is local-first.

- Approval tokens are stored as SHA-256 hashes, never plaintext.
- Gate API validates the token when a gate was created with one.
- Signed action links validate HMAC signature and expiry; the signing key stays
  local under `.longrun/signing.key`.
- Signed links are pending-only/single-use; GET confirms, POST consumes.
- `.longrun/`, `state.db`, signing material, and worker artifacts are chmod-hardened
  where supported.
- Webhook delivery is dry-run unless `--send` is passed explicitly.
- Webhook `--send` requires HTTPS.
- Real Codex execution via HTTP is disabled unless explicitly enabled by env var.
- The API entrypoint defaults to `127.0.0.1`; CORS defaults to localhost frontend
  origins instead of wildcard.
- Worktree isolation requires a git repository and creates detached task checkouts
  under `.longrun/worktrees/`; merging remains a human-reviewed step.
- Do not expose the API publicly without authentication, TLS, and an allowlist.
- External actions remain out of scope: upload, publish, push, paid API/model runs, and destructive actions must stop at a gate.

## Next increments

1. Codex Cloud backend using `codex cloud exec/status/list`.
2. Budget tracking and notification throttling.
3. Authentication/TLS/allowlist packaging for any non-local deployment.
4. Merge-review tooling for task worktrees.
