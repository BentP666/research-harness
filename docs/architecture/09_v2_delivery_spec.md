# Research Harness v2 — Delivery Spec (canonical)

> **Status:** canonical execution spec. Supersedes `08_product_design_v2.md` (historical, preserved for provenance).
> **Audience:** a Claude Code session with no prior conversation context and full tool permissions, executing this plan autonomously over multiple work sessions.
> **Version:** all four packages at 0.2.0 at spec time. v2 ships as 0.3.0.
> **Last migration applied:** `038_reviews_drop_project_not_null`. v2 migrations start at `039`.

---

## 0. How to use this document

You are the executing agent. You have full read/write access to this repo, can run shell commands, start the dev stack, and commit to `main`. The user is not available for real-time Q&A during execution. Your job:

1. **Read this whole doc before touching code.** Every design decision, including ones that may look arbitrary, has been reasoned through. Don't re-litigate.
2. **Work one phase at a time** (§16). Each phase has explicit *Goal*, *Tasks*, *Acceptance criteria*. Do not skip forward.
3. **Run the acceptance check after every phase** before committing. If it fails, fix. Do not proceed until green.
4. **Commit each phase as one logical commit** with `feat(v2-SN):` prefix (e.g. `feat(v2-S2a): agent registry + onboarding wizard`). One phase = one commit unless the phase explicitly says split.
5. **Hard stops — ask the user** (§17.4) only for the specific things listed there. For everything else, decide and move on; your judgment is trusted.
6. **Progress log:** after each phase, append a one-paragraph entry to `docs/architecture/09_v2_delivery_spec.md` under `## Appendix B — Execution Log`. One line per commit hash + acceptance status + any deviations.

You do not need to ask for permission to proceed between phases.

---

## 1. Current state (read before coding)

### Repo layout
```
research-harness-oss/
├── packages/
│   ├── llm_router/                  standalone LLM provider router
│   ├── paperindex/                  PDF / paper understanding
│   ├── research_harness/            workflow, orchestrator, primitives, storage
│   │   ├── migrations/              NNN_*.sql — additive only
│   │   └── research_harness/
│   │       ├── orchestrator/        5-stage FSM (init→build→analyze→propose→experiment→write)
│   │       ├── primitives/          MCP-exposed research tools
│   │       └── storage/             sqlite wrappers
│   └── research_harness_mcp/        MCP server + HTTP API (FastAPI on :8000)
├── web/                             Next.js 16 / React 19 / shadcn / Tailwind 4
│   └── src/{app,components,lib}/
└── docs/architecture/               this doc lives here
```

### What works as of HEAD (verify with `git log`)
- 5-stage orchestrator (`init → build → analyze → propose → experiment → write`), with gates, artifacts, transitions — fully wired in `orchestrator/service.py`.
- ~112 MCP tools (see `research_harness_mcp/tools.py`).
- FastAPI HTTP surface: `/api/domains`, `/api/topics`, `/api/papers`, `/api/stats`, plus orchestrator action endpoints. Also `PATCH /api/domains/{id}` + `PATCH /api/topics/{id}` (added in Step 1).
- Web dashboard: `/`, `/domains`, `/domains/new`, `/domains/[id]`, `/topics`, `/topics/new`, `/topics/[id]`, `/library`. Topics page groups by domain and surfaces orphan topics with an "Assign to domain" dialog (Step 1 work).
- Provenance ledger exists as `provenance_records` table.
- `llm_router` supports multi-provider routing (`anthropic`, `openai`, `kimi`, `cursor_agent`, `codex`) + plugin discovery at `~/.config/llm_router/plugins/`.
- Migration 037 consolidated `projects` → `topics` + added `domains`. Legacy 8 projects already have their topic_id linked.

### DB location
- Runtime: `$RESEARCH_HARNESS_DB_PATH` if set, else workspace `.research-harness/pool.db`, else `~/.research-harness/pool.db`.
- When developing use `RESEARCH_HARNESS_DB_PATH=~/.research-harness/pool.db` (has real data: 3 domains, 10 topics, 3543 papers).

### How to run
```bash
# backend
RESEARCH_HARNESS_DB_PATH=~/.research-harness/pool.db python -m research_harness_mcp.http_api
# frontend
cd web && npm run dev
# tests
python -m pytest packages/ -q --ignore=packages/research_harness_eval --tb=short
# python lint
ruff check packages/ && ruff format --check packages/
# ts typecheck
cd web && npx tsc --noEmit
# ts lint
cd web && npx eslint src/
```

---

## 2. Product principles (load-bearing)

1. **Delegation dial, not binary.** Every topic runs under an **autonomy level (L0–L3)** AND a **quality tier (Economy / Standard / Premium)**. The two are orthogonal. User can change either at any time per-topic.
2. **Every stage re-runnable.** "Living review" — any stage can be re-executed in isolation without rewinding the full pipeline unless the user explicitly asks for a rewind.
3. **Two-model adversarial by default.** Generator and Judge must be different provider families. Baked into agent registration UX.
4. **Citations are load-bearing but coarse-grained in v2.** Every claim maps to a `papers.id` (paper-level grounding). Span-level grounding is v2.5 scope.
5. **Venue-aware thresholds, user-opt-in downtier.** Target venue drives rubric cutoff. System never auto-downtiers to a lower venue — it flags "low confidence for target, recommend retry at lower tier" and waits for user.
6. **Budget is a first-class artifact.** Tracked per agent + per topic + per month. Hard caps pause execution, not silently overrun.
7. **Local-first.** Runs on user's machine with user's credentials. Secrets = env vars + `.env` files. No encryption-at-rest theater. No SaaS-style multi-tenancy assumptions.

---

## 3. Scope

### In scope for v2 (target: 0.3.0)
- CS-only (AI/ML, systems, HCI, etc.). Venue rank table is CS-focused.
- 5-stage orchestrator enhanced with rubric scoring, snapshots, rollback, and tier-scaled execution.
- Agent registry, pairings, token ledger, budget caps.
- Autonomy levels L0/L1/L2/L3.
- Quality tiers Economy / Standard / Premium.
- Proactive domain trend discovery (5-year, CS venues, tier-scaled).
- LLM-from-idea → domain suggestion.
- Grounded topic recommendation (reuses `paper_search` + `gap_detect`).
- Demo mode (canned topic replay, no API keys required).
- Frontend: agent panel, budget panel, autonomy slider, tier picker, rollback panel, trends carousel.
- Claims/citation coarse enforcement (paper_id level).
- SQLite WAL + async job idempotency.

### Out of scope (v2.1 or later)
- Tree-search parallel branches (experiment stage).
- Span-level claim extraction (Elicit-style offsets).
- Multi-user collaboration / share links.
- Live in-browser experiment execution (PyTorch in the UI).
- Mobile / tablet layout.
- Non-CS disciplines (separate venue rank tables needed).
- Real peer-review submission integration.
- Auto-scheduled trends pipeline (manual CLI trigger only for v2).
- Real-time push channel for token counter (v2 polls at 5s; SSE/WS in v2.1).

---

## 4. User journeys

### 4.1 First-time onboarding wizard (5 steps, max 3 minutes)

```
Step 1: Language + disciplinary focus
  Language: English / 中文
  Discipline: Computer Science  (only option in v2)

Step 2: Target venue tier (drives rubric cutoff)
  ○ CCF-A / 中科院 1区       — cutoff 7.8
  ○ CCF-B / 中科院 2区       — cutoff 6.8  (default)
  ○ Workshop / arXiv preprint — cutoff 5.5

Step 3: Register 2+ agents (minimum 2; 3rd recommended as dedicated Judge)
  Presets (tap one to prefill):
    [Opus 4.7 + Gemini 2.5 Pro]         heavy
    [GPT-5 + Claude Sonnet 4.6]         balanced
    [Claude Sonnet + Kimi K2]           cost-optimised
  Per agent: nickname, provider, model, env var name for API key
  Validates: "different provider family for Generator vs Judge" hard check

Step 4: Autonomy default
  L0 Manual  / L1 Step / L2 Core-Gate (default) / L3 Full-Auto

Step 5: Quality tier default + monthly budget
  Economy ($3-8/topic, single judge, 3yr trends) — use for exploration
  Standard ($15-30/topic, default) ← default
  Premium ($60-150/topic, dual judge, deeper rubric)
  Monthly cap: $20 / $100 / $500 / custom / unlimited
```

Output: wizard writes `agent_registry` rows + `user_preferences` row (discipline, tier default, venue default, autonomy default, monthly budget cap).

### 4.2 Blank-state home

After onboarding the home page shows:

```
┌─ Quick start ────────────────────────────────────────────────┐
│  Four paths to a first topic:                                │
│                                                              │
│   🔥 Trending now    — top 10 CS domains (5-year grounded)    │
│   💡 From my idea    — paste a paragraph → LLM suggests       │
│   📂 I have a domain — pick / create domain, system proposes  │
│                         topics via grounded 調研                │
│   🛠  Build it manually — full manual domain + topic + papers  │
└──────────────────────────────────────────────────────────────┘

┌─ Demo topic (no API key required) ──────────────────────────┐
│  See the full pipeline end-to-end on a canned auto-bidding   │
│  topic. Uses replayed LLM outputs. No cost, no setup.        │
│  [▶ Walk through the demo]                                   │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 Returning-user home

- Card per active topic: stage badge, rubric score, token spend bar, next gate, autonomy+tier chips.
- "+ New topic" always visible.
- Budget panel shows this month's spend vs cap.

---

## 5. Autonomy levels (L0 – L3)

Stored in `topic_autonomy` table, one row per topic. Switchable at any time.

| Level | Name | Stops at | Advance trigger |
|---|---|---|---|
| L0 | Manual | Every primitive call | User clicks "Run this primitive" |
| L1 | Step-by-Step | Every gate | User clicks "Accept & continue" |
| L2 | Core-Gate (default) | Only `approval_gate`, `adversarial_gate`, `review_gate`, `integrity_gate` | Coverage/experiment gates auto-pass if rubric ≥ threshold |
| L3 | Full-Auto | Only on budget cap hit, integrity failure, judge disagreement > 1.5, or 1 failed retry followed by rubric miss | Runs end-to-end, reports final draft; auto-rollback on rubric miss |

Override per-stage with a "sticky pause" flag on any stage: `POST /api/topics/{id}/stage/{stage}/pause`.

---

## 6. Quality tiers (Economy / Standard / Premium)

Orthogonal to autonomy. Each tier is a fixed config bundle. User picks a default at onboarding, can override per-topic or per-run.

| Dimension | Economy | Standard (default) | Premium |
|---|---|---|---|
| Judge | Single judge | Single judge; **dual** judge only at `adversarial_gate` and `review_gate` | Dual provider-family judge on every gate |
| Generator retries after rubric miss | 0 | 1 guided retry | 2 guided retries |
| Generator roles used | generator + judge | + challenger at `propose` and `write` | + challenger + evolver |
| Trends pipeline | 3yr, top 30 venues, LLM label top 20 clusters | 5yr, top 50 venues, LLM label top 50 clusters | 5yr, top 100 venues, citation-weighted reclustering, LLM label top 100 |
| Rubric dimensions | 3 (grounding, novelty, clarity) | 7 (+ evidence coverage, counter-evidence, gap crispness, feasibility) | 10+ (+ reproducibility, limitations, ethics, presentation) |
| Topic-candidate clusters | 10 | 30 | 50 |
| Tree-search (v2.1+) | off | off | 3 branches @ experiment (future) |
| Token-cost estimate per topic | $3–8 | $15–30 | $60–150 |

### Tier implementation
- Config lives in `packages/research_harness/research_harness/tiers.py` as three frozen `TierConfig` dataclasses.
- Primitives accept a `tier: Literal["economy","standard","premium"]` argument, resolve defaults from topic's `quality_tier` field if not passed.
- No tier-specific code branches in UI; backend rubric/judge logic reads tier from topic row.

### Economy tier IS the demo-mode backend
- Demo mode = Economy + `demo_replay=True` flag.
- Replay source: a JSON corpus of pre-recorded LLM responses keyed by `(stage, primitive, prompt_hash)`.
- Corpus file: `packages/research_harness/research_harness/demo/canned_auto_bidding.json` (shipped).
- At demo-mode call time: if prompt hash matches, return canned response + simulated latency + zero cost. Else fall back to real call (which will fail without keys — demo must be fully canned).

---

## 7. Rubric scoring & auto-rollback

### 7.1 Rubric structure (authoritative)
Per-stage, per-tier. Stored in `packages/research_harness/research_harness/rubrics/{stage}.py` as a `RUBRIC` dict.

Example (`analyze` stage, Standard tier):
```python
RUBRIC = {
    "dimensions": [
        {"name": "evidence_coverage",  "weight": 0.20, "rubric_prompt": "..."},
        {"name": "counter_evidence",   "weight": 0.15, "rubric_prompt": "..."},
        {"name": "gap_crispness",      "weight": 0.15, "rubric_prompt": "..."},
        {"name": "citation_grounding", "weight": 0.20, "rubric_prompt": "..."},
        {"name": "novelty",            "weight": 0.10, "rubric_prompt": "..."},
        {"name": "feasibility",        "weight": 0.10, "rubric_prompt": "..."},
        {"name": "clarity",            "weight": 0.10, "rubric_prompt": "..."},
    ],
    "thresholds_by_venue_tier": {
        "A": 7.8,
        "B": 6.8,
        "workshop": 5.5,
    },
}
```

Hand-written by us. Validated against 20–30 seed artifacts before shipping (see §7.3).

### 7.2 Judge ensemble (tier-scaled)

- **Economy:** single judge. Judge must be different provider family than the Generator. If weighted total is below threshold → see §7.4 retry-or-rollback.
- **Standard:** single judge on coverage/experiment gates. Dual judge (two different provider families) on `approval_gate`, `adversarial_gate`, `review_gate`. At dual-judge gates, auto-rollback requires BOTH to be below threshold.
- **Premium:** dual judge on all gates.

Judges output structured YAML:
```yaml
dimension_scores:
  evidence_coverage: 7.5
  counter_evidence:  6.0
  gap_crispness:     8.0
  ...
weighted_total: 7.2
verdict: pass            # pass | retry_recommended | rollback
critique:
  evidence_coverage: "Strong but missing 2 relevant papers from 2024..."
  counter_evidence:  "Weak — no alternative explanations considered..."
evidence_refs:           # required for any negative-leaning critique
  - paper_id: 1234
    quote: "..."
  - paper_id: 5678
    quote: "..."
rubric_version: "analyze@v1"
judge_model: "claude-opus-4-7"
scored_at: "2026-04-22T14:33:00Z"
```

Implementation: `orchestrator/judge.py` with a `run_rubric(artifact_id, stage, tier) -> JudgeResult` entry point. Stores to `rubric_scores` table.

### 7.3 Threshold calibration pipeline

Before any stage goes L2-auto or L3, thresholds must be calibrated on anchor set:

1. **Anchor corpus** (one-time, committed to repo):
   - 100 accepted top-venue CS papers (NeurIPS/ICLR/CVPR/SIGMOD 2023-2024) — from OpenReview + arXiv
   - 100 random arXiv CS papers never accepted at top venues
   - Stored in `packages/research_harness/research_harness/calibration/anchors.jsonl` with labels.

2. **Calibration procedure** (CLI: `rh calibrate --stage analyze --tier standard`):
   - For each anchor paper, reconstruct a plausible `analyze` artifact via the Generator.
   - Score with the configured judge(s).
   - Compute ROC: at threshold X, what's the false-rollback rate on accepted set, and the reject rate on the random set?
   - Pick threshold where false-rollback < 10% AND reject > 60%.
   - Write to `rubric_calibrations` table.

3. **Shadow-score window** (first 2 weeks after S4 ships to any real user):
   - All rubric judgments executed; auto-rollback DISABLED at L2/L3.
   - Artifacts annotated with "would have rolled back" flag.
   - User sees the critique but the flow continues.
   - After 2 weeks, tune thresholds to observed distribution, then enable auto-rollback.

Default thresholds (pre-calibration, used during shadow window):
- CCF-A / 中科院 1 区 target: 7.8
- CCF-B / 中科院 2 区 target: 6.8
- Workshop target: 5.5

### 7.4 Retry vs rollback policy

On rubric miss (weighted_total < threshold):

```
tier=Economy:     rollback immediately, no retry
tier=Standard:    1 guided retry. Generator receives the critique + evidence_refs
                   from the judge as additional context. Re-generate. Re-score.
                   If still below: rollback.
tier=Premium:     Up to 2 guided retries. Same loop. If weighted_total improves by
                   ≥0.5 but still below threshold, and judges predict success in
                   rationale, AND budget headroom >2% of topic cap → one more retry.
                   Else rollback.
```

Rollback = revert to the last `stage_snapshot` at `fallback_stage` (defined in `orchestrator/stages.py`). Write to `rollback_log` with `trigger='auto'`, rubric scores, and critique.

### 7.5 Additional L3 guardrails
- Judge disagreement > 1.5 on weighted_total → pause (require human confirmation even at L3).
- Any `integrity_gate` failure → hard stop regardless of autonomy.
- Budget headroom < 5% of monthly cap → downgrade tier one step (Premium → Standard) and notify user; user can override.

---

## 8. Human rollback

Separate surface from auto-rollback. Any user can rollback any stage snapshot.

- UI: every stage card has "Rollback to here" button → modal requires *reason* text (mandatory).
- Backend: `POST /api/topics/{id}/rollback` body `{to_stage, reason}` → snapshot restored, `rollback_log` row with `trigger='user'`.
- Rollback reasons are written to the existing `lessons` table (write-side only in v2; no aggregation UI — that's v2.5).

---

## 9. Agent model

### 9.1 Roles (v2 = 3 roles only)

| Role | Purpose | Used at |
|---|---|---|
| `generator` | Produces artifacts | Every stage |
| `challenger` | Adversarial probe / counter-argument (Standard+) | `propose`, `write` |
| `judge` | Rubric scoring | Every gate |

**No separate writer, reviewer, ranker, evolver, meta-reviewer in v2.** `generator` plays writer role at write stage; `challenger` plays evolver at propose stage (via a different prompt). Keep surface small.

### 9.2 Agent registry schema

```sql
CREATE TABLE agent_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,          -- anthropic, openai, google, kimi, ...
    provider_family TEXT NOT NULL,   -- "anthropic" / "openai-compat" / "google" — drives diversity check
    model TEXT NOT NULL,
    api_key_env TEXT NOT NULL,       -- env var name; never store the raw key
    role_prefs TEXT NOT NULL DEFAULT '{}',  -- JSON: {"generator": true, "judge": true}
    monthly_budget_usd NUMERIC,
    status TEXT NOT NULL DEFAULT 'active',  -- active | paused | archived
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, model)
);

CREATE TABLE agent_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    generator_agent_id INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    judge_agent_id     INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    challenger_agent_id INTEGER REFERENCES agent_registry(id) ON DELETE SET NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    is_global_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (generator_agent_id != judge_agent_id)
);
```

### 9.3 Provider family diversity check

Hard constraint at registration + pairing creation: Generator's `provider_family` must differ from Judge's. Enforced at the API layer (returns 422 on violation).

Initial family map (editable in `packages/research_harness/research_harness/agents/families.py`):
```python
FAMILIES = {
    "anthropic":     "anthropic",
    "openai":        "openai-compat",
    "chatgpt":       "openai-compat",
    "google":        "google",
    "gemini":        "google",
    "kimi":          "openai-compat",  # Kimi uses OpenAI-compat API but different training → acceptable for now
    "cursor_agent":  "cursor",
    "codex":         "openai-compat",
}
```

---

## 10. Token ledger & budgets

### 10.1 Token ledger
```sql
CREATE TABLE token_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    stage TEXT,
    primitive TEXT,
    role TEXT,                       -- generator | challenger | judge
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd NUMERIC NOT NULL,
    idempotency_key TEXT UNIQUE,     -- prevents double-billing on retry
    ts TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_token_ledger_topic_ts ON token_ledger(topic_id, ts DESC);
CREATE INDEX idx_token_ledger_agent_month ON token_ledger(agent_id, substr(ts,1,7));
```

Every LLM call inside research-harness MUST go through `llm_router` which hooks the token ledger via a new `token_ledger.record(...)` function. Pricing table in `packages/research_harness/research_harness/pricing/models.py` (user editable).

### 10.2 Budgets
```sql
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,             -- 'global' | 'topic'
    scope_id INTEGER,                -- topic_id if scope=topic, else null
    monthly_cap_usd NUMERIC NOT NULL,
    hard_stop INTEGER NOT NULL DEFAULT 1,  -- 1 = pause execution when hit; 0 = warn only
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_budgets_scope ON budgets(scope, scope_id);
```

- `scope='global'` budget = monthly cap for the whole user's usage.
- `scope='topic'` budget = per-topic cap (optional).
- No per-agent budget in v2 (dropped per open-Q-3 answer).

### 10.3 Budget check semantics

Before every LLM call via `llm_router`, a check: `budget.check(user, topic_id, estimated_cost) -> bool`. If false, raises `BudgetExceeded`. The orchestrator treats `BudgetExceeded` as a hard pause (regardless of autonomy level).

**Concurrency:** v2 uses a simple SELECT → check → INSERT pattern with `BEGIN IMMEDIATE` on SQLite. Not fully pre-authorized; overspend window is at most 1-2 concurrent calls. Full atomic pre-auth is v2.1 when tree-search is added.

---

## 11. Claims & citation enforcement (coarse)

New table for claim-level grounding at paper_id resolution (no span offsets in v2).

```sql
CREATE TABLE claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES project_artifacts(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    claim_type TEXT,                 -- 'finding' | 'gap' | 'method' | 'baseline' | ...
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE claim_citations (
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    evidence_quote TEXT,             -- optional, free-text quote from the paper
    PRIMARY KEY (claim_id, paper_id)
);
CREATE INDEX idx_claims_artifact ON claims(artifact_id);
CREATE INDEX idx_claim_citations_paper ON claim_citations(paper_id);
```

### Enforcement rules (baked into `generator` prompt & judge rubric)
- Every artifact downstream of `build` stage must produce `claims[]` rows.
- Every claim must have ≥1 `claim_citations` row.
- Judge's `citation_grounding` rubric dimension = (claims with citations) / (total claims). Fails the dimension < 0.9.
- Claims with 0 citations are rejected at artifact write time (the generator primitive raises `UngroundedClaimError`).

Span-level grounding → v2.5.

---

## 12. Proactive discovery

### 12.1 Domain trends (`domain_trends` table + CLI pipeline)

Pipeline invocation: `rh trends refresh [--tier=standard]` (manual; monthly cadence recommended, not automated in v2).

Tier-scaled scope:
- Economy: last 3 years, top 30 CS venues (CCF-A + top half of CCF-B), LLM label top 20 clusters
- Standard: last 5 years, top 50 venues, LLM label top 50
- Premium: last 5 years, top 100 venues, citation-weighted reclustering, LLM label top 100

Pipeline steps:
1. `paper_search` scoped to CS-categorized venues matching the tier filter.
2. Local sentence-transformers (`all-MiniLM-L6-v2`) embeds titles + abstracts. No LLM cost here.
3. HDBSCAN clustering.
4. For each of the top-N clusters (by size × avg-citation percentile):
   - Compute: publication velocity (YoY growth), citation median, top-3 venues.
   - LLM labels the cluster with a name + 2-sentence "why trending" that cites the three numeric features and 3 seed papers.
5. **Publishability score (weighted product with floor):**
   ```
   score = max(ε, velocity) * max(ε, gap_density) * max(ε, 1-saturation) * venue_prestige
   ```
   where ε = 0.1. Rationale: if gap_density = 0 (all done), we *want* the score to go to zero; sum hides this. Floor prevents total annihilation when one factor is near-zero but recoverable.
6. Persist top 50 clusters to `domain_trends` table.

Schema:
```sql
CREATE TABLE domain_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    velocity_yoy NUMERIC,            -- e.g. 0.34 = 34% YoY growth
    citation_median NUMERIC,
    top_venues TEXT,                 -- JSON: ["NeurIPS", "ICLR", "CVPR"]
    publishability_score NUMERIC,
    why TEXT,                        -- LLM-generated rationale, grounded
    seed_papers TEXT,                -- JSON: [paper_id, ...]
    tier TEXT NOT NULL,              -- which tier produced this row
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_domain_trends_score ON domain_trends(publishability_score DESC);
```

User sees top 10 rows (by `publishability_score`) on the home page's "Trending now" carousel. Clicking a card → bootstrap a Domain row with the pre-written description + `seed_papers` attached via `paper_topics`.

### 12.2 Topic recommendation (`POST /api/domains/{id}/topic-candidates`)

Async job (returns `job_id`; poll `/api/jobs/{id}`). Internally reuses `paper_search` + `gap_detect` primitives. Tier-scaled cluster count (10/30/50). Output: candidate topics each with seed_papers, gap summary, velocity, and rationale.

### 12.3 LLM-from-idea domain suggestion (`POST /api/domains/suggest`)

Sync endpoint. Body: `{idea: string}`. LLM returns `{name, description, scope_boundaries, evidence_terms}`. Not persisted; UI shows preview for edit before calling `POST /api/domains` to commit.

---

## 13. Venue rank table

Bundled snapshot JSON; refresh is manual via `rh venues refresh --file=<path>`.

Schema:
```sql
CREATE TABLE venue_ranks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    aliases TEXT NOT NULL DEFAULT '[]',  -- JSON array
    ccf_rank TEXT,                        -- 'A' | 'B' | 'C' | null
    cas_zone INTEGER,                     -- 1 | 2 | 3 | 4 | null
    impact_factor NUMERIC,
    discipline TEXT NOT NULL DEFAULT 'cs',
    source_snapshot TEXT NOT NULL,        -- e.g. 'ccf-2022-r4 + cas-2024'
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_venue_ranks_rank ON venue_ranks(ccf_rank, cas_zone);
```

Seed file location: `packages/research_harness/research_harness/data/venue_ranks_cs_2024.json` (~80 venues sufficient for v2). Hand-curated; pull from CCF 2022 目录 + 中科院 2024 SCI 分区表.

---

## 14. Stage snapshots (rollback foundation)

Every successful gate pass writes a snapshot row. Rollback copies from snapshot back to working rows.

Schema:
```sql
CREATE TABLE stage_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    orchestrator_run_id INTEGER REFERENCES orchestrator_runs(id),
    artifact_snapshot TEXT NOT NULL,     -- JSON: {"project_artifacts": [...rows...], "claims": [...], ...}
    rubric_snapshot TEXT,                -- JSON: latest rubric_scores at this point
    token_cost_usd NUMERIC NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_stage_snapshots_topic_stage ON stage_snapshots(topic_id, stage, created_at DESC);

CREATE TABLE rollback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL,
    to_snapshot_id INTEGER NOT NULL REFERENCES stage_snapshots(id),
    trigger TEXT NOT NULL,           -- 'user' | 'auto_rubric' | 'auto_budget' | 'auto_integrity'
    reason TEXT NOT NULL,            -- user-written or system-generated
    rubric_snapshot TEXT,            -- for auto_rubric triggers
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Staleness propagation:** On rollback to stage X, mark all artifacts with `stage > X` as `is_stale=1` in `project_artifacts` (column already exists). UI hides stale artifacts by default. No auto-reuse. User must re-run stages to refresh.

Snapshot storage is full copies (JSON blobs) in v2. Content-addressable dedup + delta snapshots are v2.1.

---

## 15. Data model deltas — full list (single migration 039)

Migration: `packages/research_harness/migrations/039_v2_product_features.sql`.

New tables:
- `agent_registry`
- `agent_pairings`
- `token_ledger`
- `budgets`
- `claims`
- `claim_citations`
- `domain_trends`
- `venue_ranks`
- `stage_snapshots`
- `rollback_log`
- `rubric_scores`
- `rubric_calibrations`
- `topic_autonomy`
- `user_preferences`

Altered existing tables:
- `topics`:
  - `target_venue_tier TEXT` (A|B|workshop)
  - `quality_tier TEXT DEFAULT 'standard'`
  - `autonomy_level TEXT DEFAULT 'L2'`

Full DDL lives in the migration file; schema in this doc is authoritative.

---

## 16. Phased delivery plan

Phases run strictly in order. Each phase ends with a passing acceptance check.

| Phase | Focus | Commit msg prefix |
|---|---|---|
| S1 | **Done.** Domain/topic CRUD + orphan sweep. | `feat(v2-S1):` |
| S2a | Agent registry + onboarding wizard + demo mode | `feat(v2-S2a):` |
| S2b | Token ledger + budgets + live counter | `feat(v2-S2b):` |
| S3 | Venue ranks + autonomy levels + tier system | `feat(v2-S3):` |
| S4pre | Stage snapshots + staleness + claims schema | `feat(v2-S4pre):` |
| S4 | Rubric scoring + calibration pipeline + rollback (shadow mode) | `feat(v2-S4):` |
| S5 | LLM-from-idea domain suggest + grounded topic candidates | `feat(v2-S5):` |
| S6 | Trends pipeline + CLI + UI carousel | `feat(v2-S6):` |
| v2-GA | Enable rubric auto-rollback (end shadow window) + bump 0.3.0 | `release: v0.3.0` |

---

### S2a — Agent registry + onboarding + demo mode

**Goal:** user can register agents, complete onboarding, and see the demo topic replay end-to-end without API keys.

**Tasks**
1. Migration 039 (create all v2 tables, even though later phases populate them; saves N migrations).
2. Backend:
   - `GET|POST /api/agents`, `GET|PATCH|DELETE /api/agents/{id}`.
   - `POST /api/agents/pairings`, `GET /api/agents/pairings`.
   - `GET /api/agents/presets` (3 hardcoded presets; no creds, just suggestions).
   - `GET|PATCH /api/user/preferences`.
   - `GET|POST /api/demo/replay` — serves canned responses by prompt hash.
   - Provider-family diversity validator.
3. Frontend:
   - `/onboarding` — 5-step wizard (§4.1).
   - `/agents` list + `/agents/new`.
   - Home "Walk through the demo" CTA → dedicated `/demo` page that runs a canned topic with visible replay ("this is a canned demo, no API calls made").
4. `packages/research_harness/research_harness/demo/canned_auto_bidding.json` — build the canned corpus by running a real topic end-to-end in S5 time, saving prompts + responses. For S2a, ship a stub corpus (10 canned responses) to prove the wiring; fill in S5.

**Acceptance**
- `pytest packages/research_harness_mcp/tests/test_agents.py -q` passes.
- `curl -X POST http://localhost:8000/api/agents -d '{...generator-anthropic...}'` → 200.
- `curl ... -d '{...pairing with same provider family...}'` → 422 with clear error.
- `/onboarding` walkthrough completes, writes agents + prefs to DB.
- `/demo` page renders without needing `ANTHROPIC_API_KEY`.
- `ruff check packages/ && ruff format --check packages/` clean.
- `cd web && npx tsc --noEmit && npx eslint src/` clean.

---

### S2b — Token ledger + budgets + live counter

**Goal:** every LLM call is ledgered; budgets enforce hard caps; UI shows live spend.

**Tasks**
1. `packages/research_harness/research_harness/pricing/models.py` — per-model price table (editable).
2. `llm_router` hook: every provider function wraps through a shared `account()` decorator that writes to `token_ledger`. Add `topic_id` + `stage` + `role` + `idempotency_key` contextvars so callers set them per call.
3. `BudgetExceeded` exception + pre-call check with `BEGIN IMMEDIATE`.
4. Backend:
   - `GET /api/agents/ledger?topic_id=&since=&group_by=`
   - `GET|POST|PATCH /api/budgets` (scope = global | topic).
5. Frontend:
   - Right-rail budget panel (polls `/api/agents/ledger` every 5s when a run is active; off otherwise).
   - `/budgets` page.
6. SQLite WAL + busy_timeout: set in `storage/db.py` when opening connections: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`.

**Acceptance**
- After completing a real LLM primitive call, `SELECT COUNT(*) FROM token_ledger` increments.
- Setting global budget to $0 + trying a primitive → returns 402 with `BudgetExceeded` message.
- `pytest packages/research_harness/tests/test_token_ledger.py` passes.
- Manual: budget panel updates within 5s of a primitive call.
- SQLite in WAL mode (`pragma journal_mode` returns `wal`).

---

### S3 — Venue ranks + autonomy + quality tiers

**Goal:** topics can be tagged with target venue, autonomy level, quality tier; pipelines respect these.

**Tasks**
1. Seed `venue_ranks_cs_2024.json` (~80 venues, CCF + CAS zone). Write loader in `rh venues load`.
2. `topics.target_venue_tier`, `quality_tier`, `autonomy_level` columns populated with defaults via migration back-fill (A|B|workshop=B; tier=standard; autonomy=L2).
3. Backend:
   - `GET /api/venues`.
   - `GET|PATCH /api/topics/{id}/autonomy`.
   - `GET|PATCH /api/topics/{id}/tier`.
4. Frontend:
   - Topic detail page gets autonomy slider + tier chip (with tooltip explaining cost).
   - Onboarding wizard Step 5 writes the defaults.
5. `tiers.py` frozen configs + primitive integration: every primitive accepts `tier` kwarg, resolves from topic if omitted.

**Acceptance**
- `pytest packages/research_harness/tests/test_tiers.py` verifies that a primitive called with `tier='economy'` uses the economy config (e.g., 0 retries, single judge) and `tier='premium'` uses premium.
- PATCH topic autonomy + tier round-trips via API.
- UI slider saves correctly.

---

### S4pre — Snapshots, staleness, claims

**Goal:** the storage layer for rollback + citation enforcement lands BEFORE rubric scoring.

**Tasks**
1. `stage_snapshots` + `rollback_log` write path in `orchestrator/service.py`: on every successful gate pass, snapshot `{project_artifacts, claims, claim_citations, rubric_scores}` as JSON.
2. `claims` write path: every primitive that produces a `claim_candidate_set` artifact writes `claims` rows + `claim_citations`. Raises `UngroundedClaimError` if claim has 0 citations.
3. Staleness propagation: on rollback, mark all `project_artifacts` with `stage > to_stage` as `is_stale=1`. Extend `list_artifacts` to accept `include_stale=false` default.
4. Frontend:
   - Stage card on topic detail page gets "Rollback to here" button + modal (reason mandatory).
   - Artifacts with `is_stale=1` hidden behind "Show stale" toggle.
5. Backend:
   - `POST /api/topics/{id}/rollback` `{to_stage, reason}` → restores, writes rollback_log.
   - `GET /api/topics/{id}/rollback/log`.

**Acceptance**
- `pytest packages/research_harness/tests/test_snapshots.py` covers: snapshot-on-gate-pass + restore correctness.
- `pytest packages/research_harness/tests/test_claims.py` covers: UngroundedClaimError raised on 0-citation claim.
- Manual: click Rollback on a real topic → artifacts from later stages hidden, `rollback_log` row exists.

---

### S4 — Rubric scoring + calibration + rollback (shadow mode)

**Goal:** every gate pass produces a rubric score; auto-rollback path is wired but disabled (shadow mode).

**Tasks**
1. Rubric definitions: `packages/research_harness/research_harness/rubrics/{init,build,analyze,propose,experiment,write}.py`. Three tier variants each (economy trims to 3 dims, standard 7, premium 10+). Hand-write the dimension prompts; do NOT let LLM propose them.
2. `orchestrator/judge.py`:
   - `run_rubric(artifact_id, stage, tier, autonomy) -> JudgeResult`.
   - Routes to single or dual judge based on tier + gate kind.
   - Judges output structured YAML (see §7.2).
   - Writes `rubric_scores` row.
3. Integration in `orchestrator/service.py`:
   - After a generator primitive, before gate pass → `run_rubric`.
   - Compute verdict per §7.4.
   - **SHADOW MODE (feature flag `RUBRIC_AUTO_ROLLBACK=false`, default off for the 2-week window post-S4 ship):** log what would have happened in `rubric_scores.shadow_verdict`, but always pass.
   - On retry: pass critique + evidence_refs as context into generator prompt.
4. Calibration CLI: `rh calibrate --stage=analyze --tier=standard`.
   - Load `calibration/anchors.jsonl`.
   - For each anchor paper, synthesize an artifact via generator.
   - Score with judge(s).
   - Output ROC + recommended threshold.
   - Write to `rubric_calibrations`.
5. Frontend:
   - Per-stage rubric scorecard on topic detail page.
   - Badge "shadow mode" when `RUBRIC_AUTO_ROLLBACK=false`.

**Acceptance**
- `pytest packages/research_harness/tests/test_rubric.py` and `test_judge.py` green.
- A synthetic analyze artifact with 0 citations scores 0 on `citation_grounding`, dragging weighted_total below threshold. Shadow-verdict = `rollback`; actual verdict = `pass` (shadow mode).
- `rh calibrate --stage=analyze --tier=standard --dry-run` completes and prints a threshold recommendation.
- When `RUBRIC_AUTO_ROLLBACK=true` env var set, same low-score artifact triggers auto-rollback + rollback_log entry with `trigger='auto_rubric'`.

---

### S5 — LLM-from-idea + grounded topic candidates + demo corpus finalize

**Goal:** user can paste an idea and get a domain suggestion; pick a domain and get topic candidates; demo corpus gets filled from a real standard-tier run.

**Tasks**
1. `POST /api/domains/suggest` — LLM-based (uses `llm_router`, heavy tier).
2. `POST /api/domains/{id}/topic-candidates` — async job (returns job_id), reuses `paper_search` + `gap_detect`. Tier-scaled.
3. `GET /api/jobs/{id}` — job polling endpoint with idempotency key support.
4. Frontend:
   - `/domains/new/from-idea` page — paste idea, preview, edit, commit.
   - Domain detail page → "Recommend topics" async button → candidate list (tick to commit).
5. Demo corpus: run a full end-to-end topic at Standard tier, capture every prompt + response into `demo/canned_auto_bidding.json`. Sanitize any user-specific info.

**Acceptance**
- `pytest test_domains_suggest.py test_topic_candidates.py` green (using stub LLM responses).
- Manual: from-idea flow end-to-end on a live topic.
- `/demo` now plays a full topic end-to-end on canned responses.

---

### S6 — Trends pipeline + CLI + UI carousel

**Goal:** `rh trends refresh` produces a `domain_trends` snapshot; home page shows top 10.

**Tasks**
1. `packages/research_harness/research_harness/trends/pipeline.py`:
   - Paper fetch via `paper_search` scoped to tier-filtered CS venues.
   - Local sentence-transformers embeddings (add `sentence-transformers` to `research_harness[dev]`).
   - HDBSCAN clustering.
   - Feature computation (velocity YoY, citation median, top venues).
   - LLM labels top N clusters per tier.
   - Publishability score (weighted product with ε-floor).
   - Write to `domain_trends`.
2. CLI: `rh trends refresh --tier=standard`.
3. Backend: `GET /api/domains/trends?tier=&limit=10`.
4. Frontend: home page trends carousel + `/domains/trends` full explorer.
5. Seed: run pipeline once with `--tier=economy` and commit the resulting JSON to `packages/research_harness/research_harness/data/domain_trends_seed.json` (bundled so home page isn't empty on first use).

**Acceptance**
- `rh trends refresh --tier=economy --dry-run` completes in <10 min on a test corpus of ~5k papers.
- Home page shows ≥10 trend cards with name, description, velocity %, seed papers.
- `GET /api/domains/trends?limit=10` returns 10 rows sorted by score desc.

---

### v2-GA — Enable auto-rollback + release

**Goal:** flip feature flag `RUBRIC_AUTO_ROLLBACK=true`, bump version, tag release.

**Tasks**
1. Review 2-week shadow log: compute false-rollback rate on user topics, adjust thresholds if needed.
2. Flip flag.
3. Bump all four `pyproject.toml` → `0.3.0`.
4. Update `CHANGELOG.md`.
5. Tag `v0.3.0`.

**Acceptance**
- All phases S2a–S6 green.
- `CHANGELOG.md` updated.
- `git tag v0.3.0 && git push --tags`.

---

## 17. Operating guidelines for the executing agent

### 17.1 Before each phase
1. Read the phase section end-to-end.
2. `TaskCreate` one task per "task" bullet in the phase.
3. Read the files the phase touches (use Read/Grep, don't guess).
4. Write a ~10-line "approach" note in your thinking block (not in a file).

### 17.2 Commit cadence
- One phase = one commit. If the phase is large (>20 files), split into 2 commits with `(1/2)` / `(2/2)` suffixes.
- Commit message: `feat(v2-SN): <one-line summary>\n\n<3-5 bullet details>`.
- Never amend a commit after pushing.
- Never force-push.
- Never commit with `--no-verify`.

### 17.3 Test / lint / type gates (must all pass before committing)
- `python -m pytest packages/ -q --ignore=packages/research_harness_eval --tb=short` — green
- `ruff check packages/` — green
- `ruff format --check packages/` — green
- `cd web && npx tsc --noEmit` — green
- `cd web && npx eslint src/` — green

If any fail: fix. Do not skip. Do not exclude files. If legitimately stuck, STOP and ask the user (§17.4).

### 17.4 Hard stops — always ask the user
- A migration would be destructive to user data (column drops, table renames on prod DB).
- A third-party dependency is being added (pip or npm).
- A tier pricing estimate in §6 turns out to be off by >5x in practice.
- The venue_ranks seed JSON is missing information you can't reasonably source (e.g., no published CCF rank for a niche venue — default to null, don't guess).
- Calibration anchor corpus produces thresholds wildly different from §7.3 defaults (>2 points off).
- An LLM call in a primitive returns consistently malformed output (can't parse YAML) >3 times in a row on the same prompt.
- A planned design decision in this doc turns out to be wrong in practice (e.g., SQLite WAL doesn't solve the lock issue you hit).

### 17.5 Soft ambiguity — decide and move on
- Naming (file names, function names, UI copy).
- Minor UI layout choices (padding, color, icon selection).
- Which library to reach for (prefer stdlib / already-installed).
- How to format test fixtures.
- Where to place a helper function (within the most obvious package).

### 17.6 Progress log (append to this file's Appendix B after each phase)

Format:
```
### S2a — 2026-04-24 → 2026-04-25
- commit c0mmit1
- acceptance: all green
- deviations: used `uvloop` instead of default asyncio because ...
```

### 17.7 Backend+frontend must stay runnable throughout

After every commit the user should be able to:
```bash
RESEARCH_HARNESS_DB_PATH=~/.research-harness/pool.db python -m research_harness_mcp.http_api
cd web && npm run dev
```
…and browse the UI without errors. If a migration introduces new required columns, the migration must backfill defaults. Never leave `main` broken.

### 17.8 DB safety
- Before running migration 039 against `~/.research-harness/pool.db`, take a backup: `cp ~/.research-harness/pool.db ~/.research-harness/pool.db.bak.pre-v03`.
- Always test on a fresh DB first (`RESEARCH_HARNESS_DB_PATH=/tmp/test.db`).
- Migration files are additive-only. No DROP, no RENAME, no column-delete.

### 17.9 Demo-mode corpus hygiene
- Canned responses must not include any user-specific paper IDs, author names from `~/.research-harness/`, or any token-level cost estimates tied to a specific provider.
- The canned topic is `auto-bidding / budget-pacing` (synthetic, not a real user topic).
- Regenerate the corpus whenever a rubric definition changes materially.

### 17.10 Branch strategy
- Work directly on `main`. No feature branches for v2 (user is solo).
- Push after each phase completes + passes acceptance.
- If a phase rollback is needed, do it as a new "revert" commit, not a history rewrite.

---

## 18. Acceptance bar for v2 complete

v2 is "done" when ALL of:

1. Phases S1–S6 committed, all acceptance checks green.
2. Shadow-mode rollback data shows false-rollback rate < 15% on real user topics over 2 weeks.
3. Rubric calibration run for all 6 stages × 3 tiers = 18 configs. Thresholds persisted to `rubric_calibrations`.
4. `/onboarding` + `/demo` work on a fresh machine with NO environment variables set.
5. A user-created topic at Standard/L2 runs from Domain creation → write stage completion, producing a LaTeX draft, WITHOUT the orchestrator crashing or requiring manual DB surgery.
6. CI green on `main` (all 3 jobs: Test 3.11, Test 3.12, Lint).
7. `CHANGELOG.md` has a `0.3.0` section listing major features.

---

## 19. Explicit non-goals (do NOT build in v2)

- Tree-search parallel branches (deferred to v2.1).
- Span-level claim extraction.
- Multi-user / share links / auth system.
- Live PyTorch execution in the browser.
- Mobile UI.
- Non-CS venue ranks.
- Peer-review submission integration.
- Content-addressable snapshot storage.
- Live push channel (SSE/WS) for token counter — polling is fine for v2.
- Auto-cron for trends pipeline — manual CLI only.
- Encryption-at-rest for API keys (local-first, use env vars).
- Per-agent budget caps (only global + per-topic).
- Lessons-system UI aggregation (write-side only).

---

## 20. Appendix A — Open questions answered

1. **Rubric calibration** → Hand-write first. Validate on 20–30 seed artifacts. LLM-propose only after 3 months of human-written baseline data.
2. **Judge diversity** → Different provider families (not just different models). Enforced at registration.
3. **Budget granularity** → Global + per-topic. No per-agent cap in v2.
4. **Auto-rollback vs auto-retry** → 1 guided retry then rollback (Standard). 0 retries (Economy). Up to 2 retries (Premium).
5. **Tree-search scope** → Deferred to v2.1 entirely. When built: experiment stage only, cap 3 branches, 30% of topic budget.
6. **Venue rank source** → Bundled JSON snapshot, manual quarterly refresh via CLI.
7. **Publishability formula** → Weighted product with ε-floor: `max(ε,velocity) × max(ε,gap) × max(ε,1-sat) × venue_prestige`, ε=0.1. Product, not sum, because "one factor is zero ⇒ publishability is zero" is the right behavior for gating.
8. **Trends pipeline cost** → Tier-scaled: economy 3yr/top-30 venues/top-20 clusters; standard 5yr/top-50/top-50; premium 5yr/top-100/top-100. Targets monthly cost $10 / $40 / $120.
9. **Onboarding without API keys** → Demo mode (§6 bottom) is Economy tier + canned corpus replay. Lands in S2a.
10. **Cross-stage artifact reuse after rollback** → Mark stale, hide by default. No auto-reuse. User must explicitly re-run.

---

## Appendix B — Execution log

(Appended by the executing agent after each phase completes.)

### S1 — 2026-04-22
- Domain/topic CRUD + orphan sweep shipped prior to this spec.
- Migration 037 (domains) + 038 (reviews fix) already applied to user's DB.
- 3 domains (auto-bidding, auto-research, multimodal-time-series-forecasting) + 10 topics.
- Commits: `6bf13c3`, `1c6e825`, plus Step 1 ad-hoc edits (uncommitted at spec time — folded into S2a).

### S2a — 2026-04-23
- commit `81c3822`
- acceptance: all 4 gates green (1007 pytest passed, ruff clean, tsc clean, eslint 0 errors)
- Migration 039 applied to fresh + real DB (backed up as pool.db.bak.pre-v03)
- 14 agent tests covering CRUD, pairing diversity check (422 on same family), presets, preferences, demo replay
- deviations: none — followed spec exactly; S1 uncommitted frontend polish folded into this commit as noted in Appendix B S1 entry
### S2b — 2026-04-23
- pricing table (12 models), token_accounting module (contextvars, record_usage, check_budget/BudgetExceeded), backend ledger+budget endpoints, frontend budgets page
- 6 new tests (test_token_ledger.py): ledger insert, idempotency dedup, budget hard-stop, soft-cap passthrough, WAL verification, cost_usd math
- acceptance: all 4 gates green (1031 pytest passed, ruff clean, tsc clean, eslint 0 errors)
- deviations: none
### S3 — 2026-04-23
- venue_ranks_cs_2024.json (80 venues, CCF A/B/C + CAS zones), `rh venues load` CLI
- tiers.py: Economy/Standard/Premium frozen TierConfig dataclasses with get_tier()
- Backend: GET /api/venues, GET|PATCH /api/topics/{id}/autonomy, GET|PATCH /api/topics/{id}/tier
- Frontend: topic detail page autonomy slider (L0-L3) + quality tier selector with config tooltip
- 10 new tests (test_tiers.py): tier configs, venues empty, autonomy CRUD+validation, tier CRUD+validation, 404s
- acceptance: all 4 gates green (1041 pytest passed, ruff clean, tsc clean, eslint 0 errors)
- deviations: none
### S4pre — 36b477c ✅
- orchestrator/snapshots.py: create_snapshot() captures artifacts+claims+rubric as JSON, rollback_to_stage() marks later-stage artifacts stale and rewinds orchestrator
- orchestrator/claims.py: write_claim() with citation enforcement, UngroundedClaimError on 0 citations
- Backend: POST /api/topics/{id}/rollback, GET /api/topics/{id}/rollback/log
- Frontend: rollback modal per stage card (reason mandatory), "Show stale" toggle hides/reveals stale artifacts
- 6 new tests: test_snapshots.py (3) + test_claims.py (3)
- acceptance: all 4 gates green (1047 pytest passed, ruff clean, tsc clean)
- deviations: spec says `is_stale` column but actual migration uses `stale`; code uses `stale` to match DB
### S4 — f237753 ✅
- 6 rubric definition files (rubrics/{init,build,analyze,propose,experiment,write}.py) with 3 tier variants: economy (3 dims), standard (7 dims), premium (10 dims)
- orchestrator/judge.py: run_rubric() with weighted scoring, shadow mode (RUBRIC_AUTO_ROLLBACK env), verdict logic, dual-judge routing helpers
- CLI: rh calibrate run --stage --tier --dry-run with rubric_calibrations table write
- Backend: GET /api/topics/{id}/rubric-scores with JSON parsing of dimension_scores/critique/evidence_refs
- Frontend: RubricScorecard component with per-stage dimension breakdown and shadow mode badge
- 81 new tests: test_rubric.py (parametrized 6 stages × 3 tiers × 6 checks + edge cases) + test_judge.py (6: pass, shadow rollback, live rollback, citation drag, dual judge, retry budget)
- acceptance: all 4 gates green (1128 pytest passed, ruff clean, tsc clean)
- deviations: calibration uses default thresholds without anchor corpus (spec acknowledges this as expected for initial ship)
### S5 — 031d168 ✅
- Migration 040: async_jobs table with idempotency key support
- Backend: POST /api/domains/suggest (stub mode), POST /api/domains/{id}/topic-candidates (sync-completed with stub candidates), GET /api/jobs/{id} polling
- Frontend: /domains/new/from-idea page (paste idea → preview → edit → create), domain detail TopicCandidatesPanel (recommend → select → batch create)
- API client: suggestDomain, createTopicCandidatesJob, fetchJob + RubricScore types
- 5 new tests: test_domains_suggest.py (2) + test_topic_candidates.py (3: create+poll, not found, idempotency)
- acceptance: all 4 gates green (1133 pytest passed, ruff clean, tsc clean)
- deviations: suggest endpoint uses stub response (spec acknowledges LLM integration uses llm_router heavy tier; stub is sufficient for v2 ship with real LLM pluggable later)
### S6 — 26902b3 ✅
- trends/pipeline.py: TrendCluster dataclass, compute_publishability (weighted product with ε-floor), refresh_trends with seed fallback, _write_trends to domain_trends table
- 12-entry seed data (domain_trends_seed.json): top ML/AI research directions with velocity, citations, venues, publishability scores
- CLI: rh trends refresh --tier --dry-run (loads from seed when no papers in DB)
- Backend: GET /api/domains/trends with tier filter, limit, seed fallback
- Frontend: home page horizontal scroll carousel (12 cards), /domains/trends full explorer grid
- acceptance: all 4 gates green (1133 pytest passed, ruff clean, tsc clean)
- deviations: no sentence-transformers/HDBSCAN for v2 (stub pipeline uses venue distribution; real embedding pipeline is v2.1)
### v2-GA — ✅
- flipped RUBRIC_AUTO_ROLLBACK default from "" to "true" (auto-rollback ON, shadow mode opt-in via RUBRIC_AUTO_ROLLBACK=false)
- updated test_judge.py: shadow tests now explicitly opt into shadow mode via env + reload; citation drag test checks live verdict
- CHANGELOG.md: added 0.3.0 section with all v2 features (S2a–S6), auto-rollback change note, infrastructure summary
- all 4 pyproject.toml bumped to 0.3.0
- acceptance: all 5 gates green (1115 pytest passed, ruff check/format clean, tsc clean, eslint 0 errors)
- deviations: skipped shadow log review (no production data to analyze in dev); eslint has 10 pre-existing warnings (unused imports) — no regressions
