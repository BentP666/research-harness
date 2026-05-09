# Research Harness — Product & Technical Design v2

> **Status: HISTORICAL — superseded by `09_v2_delivery_spec.md` (2026-04-22 review).**
> This is the first-pass design, preserved for provenance. The authoritative spec for v2 implementation
> incorporates red-team feedback (Joy GPT-5 review) and adds a Quality-Tier system orthogonal to
> autonomy levels. Read `09_v2_delivery_spec.md` before executing.

> **Status (original):** proposal (drafted 2026-04-22, before implementation)
> **Scope v1:** CS-only (AI/ML, systems, HCI, etc.). Other disciplines deferred.
> **North star:** the user goes from *no idea* / *rough idea* / *full idea* to an accepted **top-venue** paper, with the system taking over as much of the grunt work as they're willing to delegate, while staying fully inspectable and rollback-able.

---

## 1. Design Principles

1. **Delegation dial, not binary.** Every topic runs under one of 4 autonomy levels; the user can bump the dial up or down at any point, per-topic.
2. **Every stage re-runnable.** Borrowed from Elicit's "living reviews": any stage can be re-executed in isolation without rewinding the full pipeline — unless the user asks for a rewind.
3. **Two models, always.** Generator and Judge/Challenger must be different providers or at least different models; this is baked into the agent model, not left to user discipline.
4. **Citations are load-bearing, not decorative.** Every claim in a downstream artifact must trace to a `papers.id` or a `provenance_records.id`. No free-floating facts. Lesson learned from Sakana AI Scientist ([arxiv/2504.08066](https://arxiv.org/abs/2504.08066)) and Elicit's sentence-level grounding ([elicit.com](https://elicit.com/)).
5. **Venue-aware thresholds.** Same rubric, different cut-offs for CCF-A vs CCF-B. Target venue drives scoring bar.
6. **Budget is a first-class artifact.** Token / cost is tracked as rigorously as papers and claims, with hard caps that pause execution rather than silently overrun.

---

## 2. User Journeys

### Blank state (first use)

```
┌─ Onboarding wizard ─────────────────────────────────────────────┐
│ 1. Pick language & domain area   → "Computer Science"           │
│ 2. Pick target venue tier         → "CCF-A / 中科院 1–2 区"      │
│ 3. Register 2 agents              → Generator + Challenger      │
│    Presets: [Opus + Gemini 2.5] [GPT-5 + Claude Sonnet] [...]   │
│ 4. Pick autonomy default          → L2 (core-gate stop)         │
│ 5. Pick monthly budget cap        → $50 / $200 / custom         │
└─────────────────────────────────────────────────────────────────┘
        ↓
┌─ Home: "How would you like to start?" ─────────────────────────┐
│ ○ I have no idea        → trending domains (Top 10, grounded)   │
│ ○ I have a rough idea   → paste paragraph → LLM extracts domain │
│ ○ I have the domain     → system proposes topics (調研)          │
│ ○ I have everything     → manual Domain + Topic + seed papers   │
└────────────────────────────────────────────────────────────────┘
```

After onboarding the 4 entry paths funnel into the same trunk: **Domain → Topic (with seed papers) → Orchestrator-driven research**.

### Returning state

The home page becomes a **command center**:
- One card per active topic, showing stage badge, rubric score, token spend, next gate, and autonomy level.
- "+ New topic" always visible.

---

## 3. Research Workflow (reuses existing 5-stage model)

We already have a 5-stage trunk (see `07_orchestrator_implementation.md`):

```
init  →  build  →  analyze  →  propose  →  experiment  →  write
```

Each stage has:
- `required_artifacts` — must exist before gate passes
- `gate_type` — approval / coverage / adversarial / review / experiment / integrity
- `fallback_stage` — used for auto-rollback

**Additions in v2:**

| Addition | Purpose |
|---|---|
| `rubric_scores` per artifact | Per-stage quality dimensions, 0–10 each, weighted total |
| Stage snapshots | Immutable `{artifacts + provenance + rubric}` snapshot on every gate pass, the rollback anchor |
| Parallel branches | A single topic can fork into N parallel `experiment_runs` (Sakana's tree-search idea at stage granularity) |
| Stage-skip flag | L3 users can ask "just get to write ASAP" — the orchestrator will mark earlier stages as "accepted by proxy" only if rubric thresholds survive |

---

## 4. Autonomy Levels

Four levels. Switchable per-topic at any point. Stored in `topic_autonomy` table.

| Level | Name | Stop at | Advance trigger |
|---|---|---|---|
| **L0** | Manual | Every primitive call | User clicks "Run" |
| **L1** | Step-by-Step | Every gate (approval / coverage / adversarial / review / experiment / integrity) | User clicks "Accept & continue" |
| **L2** | Core-Gate | Only approval + adversarial + review gates (user-judgment gates); coverage/experiment gates auto-pass if rubric > threshold | System auto-continues past non-judgment gates |
| **L3** | Full Auto | Only on auto-rollback exhaustion, or budget cap, or integrity violation | System runs stages end-to-end, reports final draft |

Level can be **overridden per-stage**. E.g., someone running L3 can still ask "stop me at `propose` no matter what" via a sticky pause flag.

---

## 5. Quality Scoring & Auto-Rollback

Each stage has a **rubric** — a small fixed set of dimensions, 0–10 each, plus a weighted total.

Example — `analyze` rubric:
| Dimension | Weight |
|---|---|
| Evidence coverage (claims → paper_ids) | 0.2 |
| Counter-evidence represented | 0.15 |
| Gap crispness | 0.15 |
| Citation grounding (every claim cited) | 0.2 |
| Novelty relative to existing literature | 0.1 |
| Feasibility signal | 0.1 |
| Clarity / structure | 0.1 |

Scoring is done by the **Judge agent** (must be different model from the Generator that produced the artifact), using a Prometheus-style rubric-conditioned prompt with chain-of-thought ([G-Eval / EMNLP 2023](https://aman.ai/primers/ai/LLM-as-a-judge/)). Output is structured YAML so per-dimension scores are preserved, not just a single scalar (lesson from [Amazon Nova rubric judge](https://aws.amazon.com/blogs/machine-learning/evaluate-generative-ai-models-with-an-amazon-nova-rubric-based-llm-judge-on-amazon-sagemaker-ai-part-2/)).

**Thresholds are venue-calibrated.** Same rubric, but cutoff for CCF-A ≈ 7.5, CCF-B ≈ 6.5, workshop ≈ 5.5.

**Auto-rollback rules** (only in L2 / L3):
- If `weighted_total < threshold` → rollback to `fallback_stage`, record rollback_log with:
  - which dimension failed
  - the judge's verbatim critique
  - diff between current artifact and what would satisfy the rubric
- If rollback triggered 3× on the same stage → escalate to user (pause + banner) regardless of autonomy level.
- If `weighted_total` improves across retries but stays below threshold → nudge to next-lower venue tier and ask user.

---

## 6. Human Rollback

Separate from auto-rollback. Any user can rollback any stage snapshot. UI: on each stage card, "Rollback to here" button → required text input "Reason" → snapshot restored, `rollback_log` row created.

**Rollback reasons feed the lessons system.** `rollback_log` has a FK to `lessons`; the harness can surface "users rolled back `propose` 5× in 1 month citing 'weak novelty' — consider tightening novelty rubric" in retrospective view.

---

## 7. Agent Model

### Data model

```sql
CREATE TABLE agent_registry (
  id INTEGER PRIMARY KEY,
  name TEXT,                       -- user-visible nickname
  provider TEXT,                   -- "anthropic" | "openai" | "google" | ...
  model TEXT,                      -- "claude-opus-4-7" | "gpt-5" | ...
  api_key_ref TEXT,                -- reference, not raw key (env var name)
  role_defaults TEXT,              -- JSON: {"writer": 0.8, "judge": 0.2, ...}
  monthly_budget_usd NUMERIC,
  status TEXT,                     -- "active" | "paused" | "archived"
  created_at TEXT
);

CREATE TABLE agent_pairings (
  id INTEGER PRIMARY KEY,
  name TEXT,                       -- "Opus + Gemini (default adversarial)"
  generator_agent_id INTEGER REFERENCES agent_registry(id),
  challenger_agent_id INTEGER REFERENCES agent_registry(id),
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  is_default INTEGER DEFAULT 0
);

CREATE TABLE token_ledger (
  id INTEGER PRIMARY KEY,
  agent_id INTEGER REFERENCES agent_registry(id),
  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
  stage TEXT,
  primitive TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  cost_usd NUMERIC,
  ts TEXT
);
```

### Roles

Derived from Google Co-Scientist's multi-agent split ([research.google](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/)):

| Role | Responsibility | Stage usage |
|---|---|---|
| `generator` | Produces initial artifacts | all stages |
| `challenger` | Counter-arguments, adversarial probes | propose, write |
| `reflector` | Rubric scoring, quality judge | every gate |
| `ranker` | Tournament-style comparison when N candidates generated | analyze (directions), propose (algos) |
| `evolver` | Refines top-ranked candidate | propose, write |
| `writer` | Final LaTeX/Markdown output | write |
| `reviewer` | Simulated venue reviewer | write (review_gate) |

**Minimum agents for the system to function:** 2 (one each for Generator and Challenger). Strongly recommended: 3 (add a third model for Reflector to reduce Generator↔Judge bias). The onboarding wizard states this explicitly.

### Preset pairings (first-run suggestions)

```
[Opus 4.7 + Gemini 2.5 Pro]  — best quality, most expensive
[GPT-5 + Claude Sonnet 4.6]  — balanced, well-tested
[Claude Sonnet 4.6 + Kimi K2] — cost-optimised
[Codex + Claude Opus]         — for topics with heavy experiment-code stage
```

Delivered as a dropdown with "Apply to my default pairing", plus a custom option.

---

## 8. Proactive Discovery

### Domain trends (the "I have no idea" path)

Offline pipeline (CLI `rh trends refresh`, monthly cron later):

1. Pull 5 years of papers from the configured providers (Semantic Scholar + OpenAlex), filtered to CCF-B+ **OR** 中科院 ≤2 区 venues (per `venue_ranks` table).
2. Embed titles + abstracts → cluster (HDBSCAN on sentence-transformer embeddings).
3. For each cluster:
   - Compute: publication velocity (YoY growth), citation median, top 3 venues.
   - Ask LLM to label + write the "why it's hot" paragraph, citing the numerical evidence.
   - Pick 3–5 seed papers (top-cited within the cluster).
4. Rank by a **publishability score** = `velocity × gap_density × (1 − saturation_ratio) × venue_prestige`.
5. Persist top 50 to `domain_trends` table. Home page surfaces top 10.

User picks one → system auto-creates the Domain row with the pre-written description + seed papers attached.

### Topic recommendation (the "I have the domain" path)

Runs on demand per Domain:

1. `paper_search` scoped to that Domain, last 3 years, CCF-B+.
2. Cluster → candidate topics (similar to domain clustering but one layer finer).
3. For each candidate: run the existing `gap_detect` primitive + venue publication velocity.
4. Score: same publishability formula, applied per-topic.
5. Return Top N + rationale + seed papers. User ticks the ones to keep.

This reuses primitives we already have (`gap_detect`, `claim_extract`, `paper_search`, `venue_tiers.py`).

---

## 9. Observability

### Token & cost panel (right-rail, always visible)

- Live counter per active agent (prompt / completion / total / $).
- Per-topic subtotal.
- Per-stage subtotal when drilled in.
- Budget bar: "used $12.40 of $50 monthly cap" — turns red at 80%.
- Artifact-level: clicking any artifact shows the provenance of which agent+tokens produced it.

Data comes from `token_ledger` + existing `provenance_records`.

### Timeline view (per topic)

- Gantt-style strip showing stage durations, gate approvals, rollbacks, and artifact insertions.
- Compare against a venue-calibrated baseline: "papers targeting CCF-A spend median 3 days in `build`, you're at 5 days — consider wrapping up."

### Failure heatmap (per domain)

- Which rubric dimensions get rolled back most often in this domain?
- Feeds into prompt tuning for the Generator role.

---

## 10. Backend API Deltas

Net-new endpoints (existing ones kept):

```
# Domain discovery
POST   /api/domains/suggest           { idea: string } → single domain proposal
GET    /api/domains/trends            → top-10 precomputed list
POST   /api/domains/{id}/bootstrap    → create domain row + attach seed papers

# Topic discovery
POST   /api/domains/{id}/topic-candidates → N-candidate list (may be slow, async job)

# Agents
GET    /api/agents
POST   /api/agents                    → register
PATCH  /api/agents/{id}
DELETE /api/agents/{id}
POST   /api/agents/pairings           → register pairing
GET    /api/agents/presets            → built-in presets (no credentials, just suggestions)

# Autonomy
GET    /api/topics/{id}/autonomy
PATCH  /api/topics/{id}/autonomy      → level + per-stage overrides

# Rubric
GET    /api/topics/{id}/rubric        → latest rubric scores per stage
POST   /api/topics/{id}/rubric/rerun  → force re-score (changes nothing else)

# Rollback
POST   /api/topics/{id}/rollback      { to_stage, reason } → manual rollback
GET    /api/topics/{id}/rollback/log

# Token ledger
GET    /api/agents/ledger             ?topic_id=&stage=&since=
GET    /api/budgets                   → monthly caps + usage
PATCH  /api/budgets

# Venue ranks
GET    /api/venues                    → venue_ranks table
```

Long-running jobs (domain bootstrap, topic candidates, full-auto L3 runs) should be async — return a `job_id` and poll `/api/jobs/{id}`. Use the existing orchestrator worker pattern.

---

## 11. Frontend Architecture Deltas

### Routes

```
/                           home / command center (already exists)
/onboarding                 first-run wizard (new)
/domains                    list (exists) — add trend carousel at top
/domains/new                (exists)
/domains/new/from-idea      LLM-extracted domain preview (new)
/domains/trends             full trend explorer with filters (new)
/domains/[id]               (exists) — add "recommend topics" button
/topics                     (exists) — already groups by domain
/topics/new                 (exists) — rework as L0 manual creation
/topics/[id]                command center (exists, needs heavy rework)
/topics/[id]/rubric         per-stage rubric scores
/topics/[id]/rollback       rollback history
/agents                     registry (new)
/agents/new                 wizard (new)
/budgets                    monthly caps + usage (new)
```

### Cross-cutting UI additions

- **Right rail** (collapsible): live token counter, next gate, autonomy slider.
- **Command palette** (cmd-K): "go to topic X", "rollback propose", "change level to L3".
- **Provenance graph** drawer on every artifact card (DAG from `artifact_dependencies`).

### Design inspiration

- Elicit's column-table for paper review (we reuse for claim_extract output).
- Google Co-Scientist's multi-agent "tournament" visual (we use for ranking view in `analyze` and `propose`).
- STORM's perspective carousel (we expose in `propose` as "what does a skeptical reviewer / a practitioner / a theorist ask?").

---

## 12. Data Model Deltas (single migration)

New tables: `agent_registry`, `agent_pairings`, `token_ledger`, `topic_autonomy`, `rubric_scores`, `rollback_log`, `domain_trends`, `venue_ranks`, `budgets`.

Already-existing tables that get new columns:
- `topics` — `target_venue_tier` (A/B/C), `autonomy_level` (L0/L1/L2/L3).
- `project_artifacts` (soon to be `topic_artifacts`?) — `snapshot_id` (FK to stage snapshot).

Migration number: **039_product_v2**.

---

## 13. Phased Delivery

Each phase is independently shippable and has a "demo moment".

| Phase | Scope | Demo moment |
|---|---|---|
| **S1** (done) | Step 1 — domain/topic CRUD + orphan sweep | 3 domains, 10 topics, clean grouping |
| **S2** | Agent registry + pairings + onboarding wizard + token ledger + budgets | User registers 2 models, sees live token counter on an `analyze` run |
| **S3** | Venue ranks table + autonomy levels (L0/L1/L2/L3) + per-topic slider | User sets L2, runs an end-to-end topic, manually approves at 3 core gates |
| **S4** | Rubric scoring + auto-rollback (+ rollback_log) + human rollback UI | User triggers rollback, system also auto-rolls back a bad `analyze` output |
| **S5** | LLM-from-idea → Domain suggestion; topic_candidates endpoint (grounded) | User pastes paragraph, gets Domain + 5 candidate Topics, picks 2 |
| **S6** | Domain trends pipeline + CLI + UI carousel | User opens home, sees Top-10 trending domains with "why", picks one, lands in pre-bootstrapped Domain with 5 seed papers |
| **S7** | Tree-search parallel branches + reproducibility gate + LaTeX/Overleaf export | Optional (can slip to v2.1) |

Phases 2–6 must land in order (each depends on the previous); 7 is parallelizable.

---

## 14. Non-Goals for v1

Called out so we don't scope-creep:

- Multi-user collaboration, share links — future v3.
- Live experiment execution (running PyTorch jobs on user infra from the UI) — we trigger via Codex/Claude Code, not inline.
- Mobile / tablet UI.
- Non-CS disciplines (will require per-discipline venue ranks + rubric tuning).
- Real peer-review submission — we stop at "press-ready" LaTeX + reviewer simulation.

---

## 15. Open Questions (for Codex review)

1. **Rubric calibration** — do we hand-write the first rubric per stage, or have an LLM propose it from top-venue accepted papers? Human-written is safer; LLM-proposed scales better.
2. **Judge model diversity** — is "different model" enough, or do we need "different provider family" (Anthropic vs OpenAI vs Google) to really de-bias? Research so far: [Langfuse LLM-as-Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge) suggests diverse ensembles help.
3. **Budget granularity** — per-agent, per-topic, per-user (global)? I've proposed all three layered; may be overkill for v1.
4. **Auto-rollback vs auto-retry** — if rubric fails, do we retry the same stage with a different prompt before rolling back to `fallback_stage`? I've proposed retry=0, rollback immediately. Codex to weigh in.
5. **Tree-search scope** — Sakana v2 branches at the *experiment* level. We could branch at *propose* level too. How many branches is sane? (Cost ↑ linearly.)
6. **Venue rank source of truth** — bundle a snapshot JSON, or fetch from public sources at runtime? Snapshot is reproducible; fetch is fresh.
7. **"Publishability score" formula** — is the 4-factor product `velocity × gap_density × (1−saturation) × venue_prestige` reasonable, or should we learn the weights from past-user-accepts?
8. **Cost of the trends pipeline** — 5 years × CCF-B+/中科院≤2 × CS ≈ how many papers? 200k? Estimating the LLM-labeling cost before committing. If > $50 to refresh monthly, we need to prune.
9. **Onboarding without API keys** — can we offer a "demo mode" that runs a canned topic end-to-end so users can evaluate before paying? Currently they're blocked at the agent-registration step.
10. **Cross-stage artifact reuse** — rolling back `analyze` invalidates `propose`'s inputs. Do we rollback both? Or keep `propose` and re-apply to the new `analyze`? Auto-mark stale.

---

## 16. Source Material

Product features & interaction patterns borrowed:
- [Elicit Systematic Review](https://elicit.com/blog/systematic-review/) — column-table data extraction, sentence-level citation grounding, living reviews.
- [Sakana AI Scientist v2](https://arxiv.org/abs/2504.08066) — agentic tree search, VLM reviewer, template-free pipeline.
- [Google AI Co-Scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) — multi-agent roles, Elo tournament, persistent context memory.
- [Stanford STORM](https://arxiv.org/pdf/2402.14207) — perspective-guided question asking, simulated writer/expert conversation, two-stage pre-writing vs writing.

Evaluation mechanics:
- [Agent-as-a-Judge (2025)](https://arxiv.org/html/2508.02994v1) — intermediate-step evaluation, not just final output.
- [Autorubric](https://arxiv.org/html/2603.00077v2) — checkpoint-resumable rubric scoring, psychometric reliability metrics.
- [Amazon Nova rubric judge](https://aws.amazon.com/blogs/machine-learning/evaluate-generative-ai-models-with-an-amazon-nova-rubric-based-llm-judge-on-amazon-sagemaker-ai-part-2/) — per-criterion YAML output, interpretability.
- [G-Eval (EMNLP 2023)](https://aman.ai/primers/ai/LLM-as-a-judge/) — CoT + rubric prompting standard.
