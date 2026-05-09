# Troubleshooting

Common issues new users hit when running Research Harness end-to-end,
along with the fastest workaround. Entries marked ✅ are already fixed in
the current codebase — you should not see them, but if you do, update to
the latest main.

## LLM routing & deep-read

### ❗ Deep-read silently returns `model_used="none"` and empty notes

**Symptom:** `PATCH /api/papers/{id}/deep-read` returns `status: success`
but the `output.note` fields (`algorithm_walkthrough`, `critical_assessment`,
…) are empty strings, and `model_used` is `"none"`.

**Cause:** The paper has `status=meta_only` (metadata only, no downloaded
PDF, no compiled summary, no annotations). Previously `_get_paper_text()`
returned empty text, and `deep_read()` short-circuited without calling
any LLM.

**Fix:** ✅ `_get_paper_text()` now falls back to the paper's abstract
when no richer text is available (commit adding abstract fallback in
`packages/research_harness/research_harness/execution/llm_primitives.py`).
Abstract-only deep-reads are still useful for triage; run `paper_acquire`
to get the full PDF for higher-quality extraction.

### ❗ `'str' object has no attribute 'choices'`

**Symptom:** Deep-read / claim_extract / any medium-tier primitive fails
with this error even though you have `ANTHROPIC_API_KEY` or
`ANTHROPIC_AUTH_TOKEN` set.

**Cause:** The tier router has a hard-coded blocklist that forbids
Anthropic for `light` and `medium` tiers (to prevent expensive Anthropic
calls on bulk paper-reading). When blocked, it silently falls back to
`openai:gpt-4o`. If `OPENAI_API_KEY` is empty, the OpenAI SDK returns a
string error payload, and the dispatch code crashes on `response.choices[0]`.

**Fix:** ✅ Added `LLM_ROUTE_ALLOW_ANYTHING=1` escape hatch in
`packages/llm_router/llm_router/client.py`. For users running through a
local Anthropic proxy, set this plus explicit `LLM_ROUTE_*` routes —
see `.env.example`.

### ❗ `TypeError: 'NoneType' object is not iterable` in `_chat_anthropic`

**Symptom:** Anthropic call returns but `response.content` is `None`,
crashing at `"\n".join(b.text for b in response.content …)`.

**Cause:** The proxy accepted the request but rejected the model name
(e.g. `claude-sonnet-4-5` → proxy returns `{"error": {"code": "6002",
"message": "模型不存在！"}}`).

**Workaround:** Before setting `LLM_ROUTE_*`, probe your proxy for
accepted model names:
```bash
curl -s -X POST $ANTHROPIC_BASE_URL/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_AUTH_TOKEN" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-6","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```
Use whatever the proxy returns without error.

### ⚠ `S2_API_KEY` ignored by paper search providers

**Symptom:** Semantic Scholar returns HTTP 429 even though you set
`S2_API_KEY`.

**Cause:** `paper_source_clients.py:build_provider_suite()` and
`available_provider_specs()` previously only read
`SEMANTIC_SCHOLAR_API_KEY`, not `S2_API_KEY` (despite the docs and
`paper_pool.py` supporting both).

**Fix:** ✅ Both code paths now read `S2_API_KEY` first with
`SEMANTIC_SCHOLAR_API_KEY` as a legacy alias.

## API routing

### ❗ `/api/agents/ledger` returns HTTP 422

**Symptom:** Dashboard shows stale token-budget data; browser console
logs `422 Unprocessable Content` on `/api/agents/ledger?since=…&group_by=…`.

**Cause:** Route ordering bug — the dynamic route `/api/agents/{agent_id}`
was declared before `/api/agents/ledger`, so FastAPI tried to parse
`"ledger"` as an integer `agent_id` and failed with a 422.

**Fix:** ✅ `/api/agents/ledger` is now defined before
`/api/agents/{agent_id}` in `http_api.py`. The previous implementation
also had a `with get_db()` scope bug (the SQL ran outside the `with`
block and used a closed connection); that's been fixed at the same time.

### ⚠ `Unknown primitive: deep_read` from expansion worker

**Symptom:** Multi-round expansion jobs complete with
`papers_deep_read=0` even though the UI shows the job reached the
deep-read phase. Backend logs show `ValueError: Unknown primitive: deep_read`.

**Cause:** `_deep_read_paper_impl()` called
`api.execute_primitive("deep_read", …)`, but the primitive registry
doesn't register an implementation for `DEEP_READ_SPEC` — it's served
via the MCP tool dispatcher instead.

**Fix:** ✅ `_deep_read_paper_impl()` now dispatches through
`execute_tool("deep_read", …)`, matching how the MCP server and
`toggle_deep_read` endpoint already worked.

## Frontend warnings (non-functional)

### ⚠ `<circle> attribute r: Expected length, "undefined"`

**Symptom:** Console logs this error once per page load from
`motion-dom/dist/es/…`.

**Cause:** Upstream motion animation lib bug, occurs during the initial
transition of certain icon SVGs. No user-facing impact.

**Workaround:** None needed. Safe to ignore until motion-dom patches it.

### ⚠ Hydration mismatch on theme toggle button

**Symptom:** `/settings` and a few other pages log
"Hydration failed because the server rendered HTML didn't match the
client" on first load, pointing at the `Dark mode`/`Light mode` toggle.

**Cause:** `next-themes` renders the server HTML assuming default theme,
then the client swaps in the user's actual preference on mount —
inherent to `next-themes` with SSR. No data corruption.

**Workaround:** None required. The Next.js dev overlay shows "2 issues"
because of this; it does not appear in production builds.

## Paper expansion jobs

### ✅ Parallel deep-read across the agent pool

**Added in v1.0:** expansion jobs now deep-read papers in parallel across
every available LLM provider (e.g. `anthropic`, `openai`, `kimi`,
`cursor_agent`). Each
worker round-robins through the pool, so fan-out hits diverse model
backends rather than hammering one.

- Tune with `RESEARCH_HARNESS_DEEP_READ_PROVIDERS` (comma-separated) and
  `RESEARCH_HARNESS_DEEP_READ_CONCURRENCY` (default `min(8, pool*2)`).
- Broken providers self-quarantine after 2 failures — the worker retries
  the paper with the next pool member, so a single flaky backend doesn't
  derail the batch.
- Logs (at `INFO`): `paper N provider=P model=P:M elapsed=Xs` per completion
  plus one `deep-read phase: N papers, pool=[...], max_workers=X` line per
  job start.

Observed wall-clock (TFRBench topic, 6 parallel workers): 6 papers in ~170s
vs. ~700s serial. ~4× speedup bound by the longest tail.

### ❗ Expansion re-ran deep-reads on already-processed papers

**Symptom:** `papers_deep_read` counter increments but `topic_deep_read_count`
lags behind; same papers appear to get re-deep-read each round.

**Cause:** The paper-selection SQL used
`WHERE status='meta_only' OR deep_read=0`. For topics whose papers all have
`status='meta_only'` (i.e. no full-text ingest, abstract-only), the `OR`
matches every paper — including those already `deep_read=1`. LIMIT would
then happily re-pick completed papers.

**Fix:** ✅ Changed to `WHERE deep_read=0`. Abstract-only papers can still
be deep-read (the `_get_paper_text` abstract fallback handles that); they
just shouldn't be deep-read *again* inside a single expansion run.

### ❗ `model_used='+'` / empty provider identifier on deep-read output

**Symptom:** Deep-read records `model_used: "+"` instead of a real model
identifier. The underlying LLM call succeeded and produced proper text,
but consumers (report generator, provenance display) can't tell which
provider ran.

**Cause:** Some plugin providers register with ``model=''`` in
`resolve_llm_config()` and substitute their default model inside the
chat function. `deep_read()` reads `client.model` at the end and
concatenates `f"{pass1_model}+{pass2_model}"` → `"+"`.

**Fix:** ✅ Replaced with `_describe_client(client)` which returns
``provider:model`` (falling back to ``provider:*`` when model is blank)
so the recorded identifier always names a real backend.

### ❗ `uvicorn --reload` kills running expansion jobs

**Symptom:** Editing backend code mid-expansion silently drops the job.
Row stays at `status=running` forever; progress counters stop moving.

**Cause:** Expansion jobs run as **daemon** threads in the uvicorn worker
process. `--reload` restarts the worker on file changes, and daemon
threads die with their parent.

**Workaround (until a durable queue is added):**
- Don't run `python -m research_harness_mcp.http_api` in reload mode when
  you have an active expansion. The `__main__` block turns reload on for
  developer ergonomics; for stable operation start without it:
  ```bash
  python3 -c "
  import uvicorn
  uvicorn.run('research_harness_mcp.http_api:app',
              host='0.0.0.0', port=8000, reload=False)
  " &
  ```
- After an unclean restart, cancel orphaned rows (same SQL below as the
  watchdog follow-up).

### ❗ `no such table: expansion_jobs`

**Symptom:** `POST /api/topics/{id}/expansion` or `GET` on the same
endpoint returns HTTP 500 with "no such table: expansion_jobs".

**Cause:** Migration `056_expansion_jobs.sql` wasn't applied.

**Fix:** The DB auto-runs all `migrations/*.sql` on first connect, so
this should never happen for a fresh clone. If you already had the DB
open when pulling this migration, restart the backend — it re-runs
`_apply_migrations()` on startup and will pick up 056.

If for some reason it's still missing, apply manually:
```bash
/opt/miniconda3/bin/python3 -c "
import sqlite3, os
db = os.path.expanduser('~/.research-harness/pool.db')
sql = open('packages/research_harness/migrations/056_expansion_jobs.sql').read()
conn = sqlite3.connect(db)
conn.executescript(sql)
conn.execute('INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (56, \"056_expansion_jobs\")')
conn.commit()
"
```

### ⚠ Expansion job runs as in-process daemon thread

**Caveat:** The current worker spawns a background thread inside the
FastAPI process. If you `pkill` the backend mid-run, the job row stays
at `status=running` forever — there's no watchdog.

**Workaround:** After an unclean restart, manually mark stuck jobs:
```sql
UPDATE expansion_jobs SET status='cancelled', last_error='backend restart'
WHERE status IN ('running','pending');
```
A future migration should add a TTL-based sweep; tracked as a follow-up.

## Known LLM output quirks

### ⚠ Deep-read pass1 sometimes returns empty structured fields

**Symptom:** `deep_read` output has `critical_assessment` filled with a
rich multi-thousand-character analysis (pass2), but
`algorithm_walkthrough`, `limitation_analysis`, and
`reproducibility_assessment` (pass1) are empty.

**Cause:** Pass1 prompts the model for a strict JSON object; the model
occasionally wraps the JSON in `` ```json … ``` `` fences with trailing
commentary. The `_parse_json()` fence stripper looks for a matching
closing ```` ``` ```` — if the model terminated before writing the
closer (max_tokens=2048 cap), parsing fails and pass1 returns `{}`.
Pass2 still runs with pass1 treated as "no info", so you get a good
critical analysis but miss the algorithmic walkthrough.

**Partial fix (landed):** ✅ `_parse_json()` now does a best-effort
recovery when fence parsing fails — it scans backward for the last `}`
and tries to parse the truncated object. This recovers the common case
where the model finished most fields but got cut before the closing
fence.

**Still open:** Mid-string truncation (e.g. `"algorithm_walkthrough": "…lots of text…` without a closing quote) still yields `{}`. Options:
- Raise `max_tokens` from 2048 → 4096 in `_chat_anthropic()` /
  `_chat_openai()` — the cheapest fix.
- Add a proper partial-JSON parser (`partial-json-parser` pypi pkg).

## Speed expectations

Rough per-unit timings on a decent connection:

| Operation | Wall time | Notes |
|---|---:|---|
| `paper_search` (1 query) | ~15 s | Multi-provider (arxiv + S2 + pasa) |
| `paper_ingest` (1 paper) | ~1.7 s | Incl. S2 enrichment |
| `deep_read` (1 paper) | 60–120 s | 2 LLM passes; rate-limited to 5 RPS |
| Full 100/20/3 expansion job | 15–30 min | Dominated by 20× deep-read pass2 |

If deep-read consistently exceeds 180 s per paper, check:
- Your proxy's latency (curl test above)
- Rate-limit warnings in `/tmp/rh_backend.log` (look for "HTTP 429")
- Whether `stream=True` is supported end-to-end (some proxies need it;
  non-streaming requests may hit nginx 60 s idle timeouts).
