# Research Harness v1.0 Demo

A ~10 minute walk-through of the v1.0 pipeline, from fresh clone to a
completed expansion job with 20+ deep-read papers analysed in parallel.

## Prerequisites

- Python ≥ 3.11 (the codebase is tested against 3.13)
- `pnpm` for the web frontend
- **At least one** LLM credential on the host — any of:
  - `OPENAI_API_KEY` / `CHATGPT_API_KEY`
  - `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` (with `ANTHROPIC_BASE_URL`
    if using a proxy)
  - `KIMI_API_KEY`
  - Cursor Agent CLI (`which agent` must succeed) — auto-detected

## 1. Install

```bash
git clone <this repo> research-harness
cd research-harness

# Python packages (editable installs)
pip install -e packages/llm_router
pip install -e packages/research_harness
pip install -e packages/research_harness_mcp

# Web frontend
cd web && pnpm install && cd ..
```

## 2. Configure

```bash
cp .env.example .env
# Edit .env — uncomment and fill whichever LLM credentials you have.
# Minimum viable config is ONE of:
#   OPENAI_API_KEY=sk-…
#   ANTHROPIC_API_KEY=sk-ant-…
#   (or just have `agent` on your PATH for cursor_agent)
```

Optional: pin the deep-read agent pool to match your credentials —

```bash
# .env
RESEARCH_HARNESS_DEEP_READ_PROVIDERS=anthropic,cursor_agent
RESEARCH_HARNESS_DEEP_READ_CONCURRENCY=4
```

## 3. Start the services

Open two terminals.

```bash
# Terminal 1 — backend (do NOT use --reload for stable jobs)
python3 -c "
import uvicorn, logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logging.getLogger('research_harness').setLevel(logging.INFO)
logging.getLogger('research_harness_mcp').setLevel(logging.INFO)
uvicorn.run('research_harness_mcp.http_api:app',
            host='0.0.0.0', port=8000, reload=False)
"

# Terminal 2 — web dashboard
cd web && pnpm dev
```

Verify:
```bash
curl -sf http://localhost:8000/api/topics        # → []
curl -sfI http://localhost:3000                  # → HTTP 200
```

## 4. Run the demo script

```bash
./scripts/demo_v1.sh --quick
```

This runs a 10-paper / 5-deep-read / 1-round smoke test and finishes in
~3 minutes. For the full demo drop `--quick`:

```bash
./scripts/demo_v1.sh             # 100 retrieval / 20 deep-read / 3 rounds
```

What it does, in order:

1. **Probe the agent pool.** Prints the list of available LLM providers
   (`anthropic`, `openai`, `kimi`, `cursor_agent`, …) so you can see
   which backends the parallel deep-read will dispatch across.
2. **Create a topic** (`LLM Agents for Time-Series Reasoning` by default).
3. **Seed 15 arXiv papers** via `paper_search` + `paper_ingest`.
4. **Start an expansion job** through `POST /api/topics/{id}/expansion`.
5. **Poll progress** every 15 s, showing `round/retrieval/deep` counters and
   topic-level totals.
6. **Print a topic overview + final job summary**.

While the script runs, open `http://localhost:3000/topics/<id>` in your
browser to see:

- The expansion panel with Round counter and two progress bars
  (本轮新增 / 精读).
- Topic-level footnotes ("主题已有 N 篇" / "主题已精读 N 篇").
- Live polling every 2 s while the job is active.

## 5. Inspect what happened

Backend log (`/tmp/rh_backend.log` or wherever you redirected stdout):

```
expansion job 11 deep-read phase: 4 papers,
    pool=['anthropic', 'openai', 'kimi', 'cursor_agent'],
    max_workers=4, timeout=180s
expansion job 11 paper 3899 provider=anthropic    model=anthropic:claude-sonnet-4-6   elapsed=103.5s
expansion job 11 paper 3906 provider=openai       model=openai:gpt-4o               elapsed=148.7s
expansion job 11 paper 3917 provider=kimi         model=kimi:kimi-for-coding        elapsed=194.0s
expansion job 11 paper 3912 provider=cursor_agent model=cursor_agent:composer-2-fast elapsed=196.1s
```

Each paper lands on a **different provider**, bounded by
`max_workers`. Serial wall-clock ≈ 650 s, parallel ≈ 200 s. The slowest
single paper sets the lower bound, not the sum.

Deep-read output (full analysis per paper):

```bash
curl -sf http://localhost:8000/api/papers/3899 | python3 -m json.tool | less
```

Look for the `deep_read_note` fields: `algorithm_walkthrough`,
`critical_assessment`, `limitation_analysis`, `reproducibility_assessment`,
`industrial_feasibility`.

## 6. Common issues

See [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md). Most reported bugs
during the v1.0 freeze are already fixed and marked ✅; a handful of
environment gotchas still need attention (e.g. `uvicorn --reload` kills
running expansion jobs, listed prominently).

## What to show off

- **Agent pool** — highlight that deep-read runs 6+ distinct models
  simultaneously. Point at the `pool=[...]` line in the backend log.
- **Progress UX** — open the expansion panel in the browser and let it
  tick through a job. The topic-level footnotes answer the "fetched=0,
  why is anything happening?" question that tripped up early testers.
- **Self-healing pool** — kill a provider mid-demo
  (`curl localhost:8111/healthz` then `kill -9` the proxy). The job keeps
  going on the other providers; the failed provider self-quarantines
  after 2 failures.
- **Stage-gated reports** — once deep-read finishes, the `/topics/<id>`
  page surfaces a "Next Stage" CTA that generates a topic overview
  report from the actual deep-read analysis (not a template).
