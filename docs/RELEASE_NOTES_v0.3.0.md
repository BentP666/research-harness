# Research Harness v0.3.0 — Release Notes

**Release date:** 2026-05-09
**Status:** Stable

Research Harness v0.3.0 ships the full agent-first literature-review pipeline
end-to-end. Papers search → ingest → deep-read → topic reports all run
on a single SQLite pool, orchestrated through a FastAPI backend and a
Next.js / shadcn frontend. LLM dispatch uses a pluggable multi-provider
router with parallel fan-out for bulk paper reading.

## Highlights

### Multi-agent parallel deep-read

Expansion jobs run deep-read across every available LLM provider in
parallel, not serially. On a typical 6-paper batch this gives a **~4×
speedup** over the previous single-provider loop.

- Pool resolution via `llm_router.available_providers()` — combines
  built-in providers (`anthropic`, `cursor_agent`, `openai`, `kimi`) with
  plugin-registered ones under `~/.config/llm_router/plugins/`.
- Round-robin provider assignment per worker. Each paper runs against a
  distinct backend model, so one hung upstream doesn't stall the batch.
- Self-quarantine: a provider that hard-fails twice is removed from the
  pool for the rest of the job and the paper is retried on the next
  pool member.
- Wall-clock cap per paper (`RESEARCH_HARNESS_DEEP_READ_TIMEOUT`,
  default 300s). Hung LLM calls no longer block the batch.
- Pool and concurrency tunable via `RESEARCH_HARNESS_DEEP_READ_PROVIDERS`
  and `RESEARCH_HARNESS_DEEP_READ_CONCURRENCY`.

### Expansion panel UI

The topic page now shows:
- Round counter + 两段进度条 (新增 / 精读) during an active job.
- Topic-level totals ("主题已有 N 篇", "主题已精读 N 篇") so users can
  distinguish **this-batch additions** from **pre-existing work**.
- Four presets (快速 20/5/1 · 标准 100/20/3 · 深度 300/50/5 · 自定义) with
  configurable retrieval/deep-read/round counts.
- Live polling every 2 s while a job is running; idle otherwise.

### Observability

- Every deep-read logs provider + model + elapsed time at INFO:
  `expansion job N paper 3900 provider=openai model=openai:gpt-4o elapsed=46.2s`.
- `/api/topics/{id}/expansion` returns `topic_paper_count` and
  `topic_deep_read_count` alongside the in-flight job counters.
- Deep-read records include `model_used` = `provider:model` so
  downstream reports know which backend produced each analysis.

### Bug fixes since 2026-04-23

See `docs/TROUBLESHOOTING.md` for the complete list. High-impact fixes:

- `_get_paper_text()` abstract fallback — meta-only papers no longer
  silent-skip deep-read.
- `/api/agents/ledger` route-ordering bug (was being parsed as
  `agent_id` → 422).
- `execute_tool("deep_read", ...)` dispatch (was `api.execute_primitive`
  which isn't registered).
- `LLM_ROUTE_ALLOW_ANYTHING` escape hatch for users running Anthropic
  via a local proxy.
- `S2_API_KEY` alias for `SEMANTIC_SCHOLAR_API_KEY`.
- Expansion SQL: stop re-processing already-deep-read papers
  (`status='meta_only' OR deep_read=0` → `deep_read=0`).
- Anthropic `max_tokens` 2048 → 4096 (fixes mid-string JSON truncation
  on deep_read pass1).
- Best-effort recovery for truncated fenced-JSON in `_parse_json()`.
- `model_used='+'` → `provider:model` via `_describe_client()`.

## Known limitations

- `uvicorn --reload` kills running expansion jobs. Run without reload in
  production; see `docs/TROUBLESHOOTING.md`.
- Expansion jobs run as in-process daemon threads. `pkill` mid-run
  leaves the DB row at `status=running`; no watchdog yet (follow-up).
- Some provider backends may intermittently fail. Self-quarantine
  handles this gracefully.

## Getting started

```bash
# 1. Clone & install
cd packages/research_harness && pip install -e .
cd packages/research_harness_mcp && pip install -e .
cd web && pnpm install

# 2. Configure (copy .env.example → .env and fill in at least one LLM key)
cp .env.example .env

# 3. Run backend
python3 -m research_harness_mcp.http_api

# 4. Run frontend
cd web && pnpm dev
# open http://localhost:3000

# 5. Walk the demo pipeline
./scripts/demo_rag_topic.sh
```

## Upgrade notes from pre-release

- Set `RESEARCH_HARNESS_DEEP_READ_PROVIDERS` explicitly if you want to
  pin the pool (e.g. skip providers you don't have credentials for).
