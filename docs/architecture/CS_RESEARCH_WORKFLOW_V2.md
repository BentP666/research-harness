# CS Research Workflow — v2 Joint Plan (Neal + Codex aligned)

> **Scope**: Computer Science only. Other disciplines deferred.
> **Status**: r3 (2026-04-23) — Neal + Codex aligned after 3 codex review rounds; revised for CSO Classifier + multi-dimensional red-ocean. Pending codex round-4 sign-off.
> **Data model invariant**: `topic` in RH = one paper-being-written by the user. Research directions live in a new `research_candidates` table; clustering uses new `research_areas` table. **No synthetic topic creation for harvesting.**

## Revision history

- **r1**: Initial joint plan, 13 codex round-1 issues resolved.
- **r2 (2026-04-23)**: Round-2/3 codex issues patched (S2 filter, venue_quality normalization, migration numbering, Python import for orchestrator_init, current-year paper scoring).
- **r3 (2026-04-23)**: **External research incorporated.**
  - D6/D7 replaced with CSO Classifier (14K hierarchical CS topics, Apache 2.0, no LLM). LLM drift-patch kept as fallback for new terms not in CSO.
  - **Multi-dimensional red-ocean**: score per-`area`, per-`task`, per-`method` separately. Recommendation cards surface which dimension is saturated → enables "blue-ocean task × mature method" novelty patterns.
  - **Task dimension**: reuse existing `normalized_claims.task` (populated by `evidence_matrix`); new `task_canonical` column for aggregation. No `claim_extract` changes.
  - **Phase 0 validation spike**: verify CSO covers recent AI terms (LLM, RLHF, diffusion, multimodal) before committing Phase 1 budget.
  - **Python bump**: `>=3.10` → `>=3.11` (CSO requirement).

---

## Review resolution log (codex round 1)

| # | Codex objection | Resolution |
|---|---|---|
| 1 | `SearchQuery` has no category field; providers ignore categories | Extend `SearchQuery` + patch each provider (D1) |
| 2 | `limit=50` hardcoded in providers AND cache key | Fix all 4 sites; cache key includes categories (D1) |
| 3 | `iterative_retrieval_loop` is topic-bound — using it for global harvest would force synthetic topics, violating `topic=paper` | New standalone `cs_harvest` primitive that does NOT require topic_id; papers ingested with `topic_id=NULL` until promoted (D3) |
| 4 | Red-ocean "LLM sees it, decides how to weigh" → LLM can ignore | Add deterministic two-lane sort: `red_ocean ≥ 0.7` candidates bucketed into a dedicated "red-ocean" lane, can't enter default top-5 unless user explicitly opts in (D10) |
| 5 | V2 reversed scoring (LLM) but design doc says deterministic | Rewrite `RECOMMENDATION_ENGINE.md` to reflect LLM scoring decision; keep typed evidence structure (D11) |
| 6 | Red-ocean formula: gap density as negative weight could reward noisy gap extraction | Cap `unresolved_gap_density` contribution at 0.2 absolute; require `cross_verified=1 OR confidence≥0.5` to count (D9) |
| 7 | `project_artifacts` uses `artifact_type`/`payload_json` + requires `project_id`/`stage`, not `kind`/`content` | Fix field names; use default project-per-topic semantics (D15) |
| 8 | `orchestrator_resume` already exists but requires `topic_id`; stages are `init/build/analyze/propose/experiment/write` | Rename new tool to `workflow_entry` (no collision); use correct stage names (D17) |
| 9 | `orchestrator_init` is CLI-only, not MCP | Add MCP wrapper `orchestrator_init_tool`, or have promote endpoint call CLI internally (D14) |
| 10 | `gaps` has no `confidence` column; `gap_detect` doesn't emit confidence; `adversarial_review` wants artifact_id not raw gaps; `codex_bridge` is internal | Add `confidence` + `cross_verified` columns; extend `gap_detect` to emit confidence; new dedicated cross-check primitive instead of repurposing `adversarial_review` (D18) |
| 11 | Head-paper current-year fallback `× 0.5` is arbitrary | Use venue quality × early citation percentile within same month cohort (D2) |
| 12 | `venue_ranks` uses `ccf_rank/cas_zone/impact_factor`, not clean A*/A/B/C | Derive `venue_quality` from existing columns: prefer `ccf_rank` when non-null, fall back to `impact_factor` percentile (D2) |
| 13 | Research_area layer justified but needs deterministic baseline + LLM labels | Use OpenAlex concepts + arxiv keywords as deterministic clusters first; LLM only names/merges them (D7 revised) |

All 13 points accepted into v2 joint plan below.

---

## 0. Naming & data-model invariant

| Concept | RH table | Scope |
|---|---|---|
| Field | `domains` | arxiv CS primary categories (15) — seeded once |
| Area / theme | `research_areas` (**NEW**) | CSO Classifier `enhanced` label list → stable `slug`. LLM drift-patch for terms CSO misses. |
| Task | `normalized_claims.task` (existing, migration 022) + `task_canonical` (NEW column, migration 046) | Per-claim task already extracted by `evidence_matrix`; canonical label for aggregation added in r3. |
| Method / dataset / metric | `normalized_claims` (existing) | Already captured per-claim. Aggregate to paper-level when scoring red-ocean. |
| Paper project | `topics` | **One topic = one paper the user writes** |
| Recommendation | `research_candidates` (**NEW**) | Directions; promotable to `topic` |

**Multi-dimensional research space**: every paper is located in (area, task, method, dataset, metric). Red-ocean is computed per-dimension; recommendations surface blue-ocean cross-cuts (e.g., "blue-ocean task × mature method = low-hanging fruit").

---

## 1. Bulk CS paper retrieval (Phase 1)

### D1. Extend `SearchQuery` + each provider

**Code changes** (concrete, per codex verification):
- `paper_sources.py` `SearchQuery` dataclass: add `subject_categories: list[str] | None = None`, `per_provider_limit: int = 50`
- Cache key (`search_cache.py`): include `subject_categories` and `per_provider_limit` in hash
- Provider patches:
  - `ArxivProvider` (`paper_source_clients.py:671`): wrap query as `(cat:cs.LG OR cat:cs.CV ...) AND (all:"{query}")` when `subject_categories` present
  - `OpenAlexProvider`: add `concept.id:C<wikidata_id>` filter; mapping table from arxiv categories → OpenAlex concept Wikidata IDs (one-time lookup, cached)
  - `SemanticScholarProvider`: use `fieldsOfStudy=Computer Science` only (coarse). Do **not** post-filter by arxiv category — `PaperRecord` has no per-paper category field; arxiv + OpenAlex already give precise CS-category filtering, S2 serves as noise-tolerant third source for recall. Duplicates are deduped by DOI/arxiv-id in `SearchAggregator`.
- `primitives/impls.py:91`: accept `per_provider_limit` parameter, thread through to `AggSearchQuery`

### D2. Head-paper ranking (deterministic)
New primitive `head_paper_rank(papers, year) -> ranked_papers`:
```python
def score(paper):
    venue_q = venue_quality(paper.venue)  # from venue_ranks, see below
    if paper.year == current_year:
        # Codex round 2 fix: no publication_date granularity available in current providers
        # Use venue_quality alone + existing citation_count (may be 0); trust venue as proxy
        citation_term = venue_q
    else:
        citation_term = log1p(paper.citation_count) / log1p(median_citation_in_year)
    recency_decay = exp(-(current_year - paper.year) / 3)
    return citation_term * venue_q * recency_decay

def venue_quality(venue_name):
    row = lookup venue_ranks(venue_name)  # TEXT column, may hold any string
    rank = (row.ccf_rank or '').upper().strip()
    # Normalize common variants (existing data may include 'A*', 'A+', 'ccf_a' etc.)
    if rank in ('A*', 'A+', 'A-STAR'): return 1.0
    if rank in ('A', 'CCF_A'):         return 0.8
    if rank in ('B', 'CCF_B'):         return 0.5
    if rank in ('C', 'CCF_C'):         return 0.3
    # Percentile fallback when ccf_rank missing — compute IF percentile across all venue_ranks rows
    if row.impact_factor is not None:
        return impact_factor_percentile(row.impact_factor)  # 0..1 rank within venue_ranks
    return 0.4  # unranked prior
```

### D3. Standalone `cs_harvest` primitive (not iterative_retrieval_loop)

**Codex critical fix**: `iterative_retrieval_loop` requires `topic_id`. Using it for global harvest would force synthetic topics = violation.

New primitive:
```python
def cs_harvest(year: int, target: int = 1000) -> HarvestResult:
    categories = ['cs.AI','cs.LG','cs.CV','cs.CL','cs.IR',...]
    seed_queries = ['machine learning', 'deep learning', 'language models', ...]  # 3-5 broad
    all_papers = []
    for cat in categories:
        for q in seed_queries:
            result = SearchAggregator.search(
                SearchQuery(query=q, subject_categories=[cat],
                            year_from=year, year_to=year,
                            per_provider_limit=200)
            )
            all_papers.extend(result.papers)
    deduped = dedupe_by_fingerprint(all_papers)  # existing logic
    ranked = head_paper_rank(deduped, year)
    top_n = ranked[:target]
    for p in top_n:
        paper_ingest(source=p, topic_id=None)  # papers are topic-less initially
    return HarvestResult(ingested=len(top_n))
```

Papers sit in `papers` table with no `paper_topics` link until domain classification + recommendation + promotion.

---

## 2. Domain + research_area + task tagging (Phase 2) — **r3 revised**

### D4. Seed 15 CS domains (one-time)
CLI script `rh domain seed cs`: creates `domains` rows for the 15 arxiv CS categories. Idempotent.

Domain assignment per paper: primary = arxiv primary category (already in `PaperRecord.metadata.categories` from ArxivProvider). No LLM needed.

### D5. New tables (r3, codex round-4 fixes)

**Migration split by phase + dependency** (codex round-4 #5): each phase owns its own migration. Numbers begin at 045 because 043 is already claimed by `RECOMMENDATION_ENGINE.md` (which will ship as 045 under its own PR) and 044 is reserved for CS candidates.

| Migration | Phase | Contents |
|---|---|---|
| `045_cs_classification.sql` | Phase 2 start | `research_areas`, `paper_research_areas`, `paper_domains` |
| `046_task_canonicalization.sql` | Phase 2 mid | `ALTER TABLE normalized_claims ADD task_canonical` (reuse existing `task` col) |
| `047_gap_confidence.sql` | Phase 4 | `gaps.confidence`, `gaps.cross_verified`, `gaps.cross_check_runs` |
| `048_research_candidates.sql` | Phase 3 | `research_candidates` (consolidated schema, see D11) |

**Codex round-4 #4 correction**: RH already has `normalized_claims.task` (migration 022, `evidence_matrix` primitive populates it). **Do not extend `claim_extract` with a new `task` field and do not introduce `paper_tasks`**. Reuse `normalized_claims.task` aggregated to paper-level.

```sql
-- 045_cs_classification.sql
CREATE TABLE research_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                      -- CSO topic label (e.g. "machine learning")
    slug TEXT NOT NULL,                      -- normalize(name) — stable identity surrogate for the "URI-style" id
    description TEXT DEFAULT '',
    source TEXT NOT NULL DEFAULT 'cso',      -- 'cso' | 'llm_drift_patch'
    red_ocean_score REAL DEFAULT NULL,       -- composite area_red_ocean (see D9)
    red_ocean_breakdown TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(domain_id, slug)
);

CREATE TABLE paper_research_areas (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    research_area_id INTEGER NOT NULL REFERENCES research_areas(id) ON DELETE CASCADE,
    is_primary INTEGER DEFAULT 0,
    match_type TEXT NOT NULL DEFAULT 'enhanced',  -- 'syntactic' | 'semantic' | 'enhanced' | 'llm_patch'
    PRIMARY KEY (paper_id, research_area_id)
);

CREATE TABLE paper_domains (
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    is_primary INTEGER DEFAULT 0,
    PRIMARY KEY (paper_id, domain_id)
);
```

```sql
-- 046_task_canonicalization.sql
-- normalized_claims.task already exists (022_phase2_analysis.sql:31).
-- Add canonical column for cross-paper aggregation:
ALTER TABLE normalized_claims ADD COLUMN task_canonical TEXT;
CREATE INDEX idx_normalized_claims_task_canonical ON normalized_claims(task_canonical);
```

Paper-level task inference: `SELECT task_canonical, COUNT(*) FROM normalized_claims JOIN claims ON ... WHERE claim.paper_id = ? GROUP BY task_canonical ORDER BY COUNT(*) DESC LIMIT 1;` — no new table needed.

### D6. `cso_classify` primitive (replaces LLM `domain_classify`)

Deterministic wrapper around CSO Classifier — no LLM in hot path.

```python
def cso_classify(papers: list[Paper]) -> list[CSOResult]:
    """Bulk classification via CSO Classifier v4.x.
    Returns per-paper {syntactic, semantic, union, enhanced}.
    """
    from cso_classifier.classifier import CSOClassifier
    cc = CSOClassifier(modules="both", enhancement="first",
                       explanation=False, get_weights=False)
    # batch_run takes: {paper_id: {'title': str, 'abstract': str, 'keywords': str}}
    results = cc.batch_run({
        p.id: {'title': p.title or '',
               'abstract': p.abstract or '',
               'keywords': ' '.join(p.keywords or [])}
        for p in papers
    })
    # Each result dict has keys: 'syntactic', 'semantic', 'union', 'enhanced'
    # Values are LISTS OF TOPIC LABEL STRINGS (e.g. ["machine learning", "graph theory"])
    # They are NOT URIs — codex round-4 #2 correction.
    return [CSOResult(paper_id=pid,
                      syntactic=r.get('syntactic', []),
                      semantic=r.get('semantic', []),
                      union=r.get('union', []),
                      enhanced=r.get('enhanced', []))
            for pid, r in results.items()]
```

- Input: paper title + abstract + keywords (all already in `papers`)
- Output: per-paper 4 lists of **topic label strings** (not URIs)
- **Cost**: $0 (CPU-only, pre-downloaded 2GB word2vec model)
- **Setup**: one-time `python -m cso_classifier.setup` (downloads ontology + model)
- **Dependency**: `cso-classifier>=4.0.1` as optional extra `research-harness[cs]`

**CSO output → `research_areas` mapping** (codex round-4 #2 fix):
- `enhanced` list contains labels after hypernym expansion — use this as canonical set
- **Identity is the label string**, not a URI. Persist as `research_areas.name` (label) + `research_areas.slug` (lowercase, dash-separated) for stable lookup.
- Filter: drop labels that are in a configured blocklist of too-generic terms (e.g. "computer science", "artificial intelligence" alone). The blocklist is ~20 terms, defined in code constant. This was the purpose of the original "hierarchy level 2-3 cutoff" which isn't directly exposable via batch_run output.
- For finer hierarchical filtering (if blocklist isn't enough), the CSO ontology itself is an RDF file available locally after setup; load it once to build a label→depth lookup. Defer this to Phase 2 sub-task if blocklist proves too crude.
- Each distinct post-filter enhanced label creates/reuses a `research_areas` row via `(domain_id, slug)` UNIQUE.
- `match_type` on `paper_research_areas` records which CSO list produced the edge: `syntactic` (exact match), `semantic` (word2vec near-match), `enhanced` (post-expansion), or `llm_patch` (from D7).

### D7. LLM drift-patch (fallback for CSO misses)

When CSO returns `enhanced` with fewer than 2 labels OR all labels hit the too-generic blocklist (e.g. only "artificial intelligence") → trigger LLM fallback:

```python
def area_drift_patch(paper, cso_result, existing_areas):
    """Haiku call to name a research_area when CSO is too generic.
    Input: paper title+abstract + list of existing area names in same domain
    Output: {area_name (existing or new), confidence}
    """
```
- Tier: `light` (Haiku)
- Output creates/links to a `research_areas` row with `source='llm_drift_patch'`; its `slug` is computed from the LLM-proposed name
- Periodic job (weekly) reviews `llm_drift_patch` rows: if 5+ papers share one, it's a genuine new term; otherwise collapse into nearest CSO area via LLM judgment.

### D8. Task dimension via existing `normalized_claims.task` (codex round-4 #4 fix)

**Rejected earlier plan**: extending `claim_extract` to emit a `task` field.

**Reason**: RH already has `normalized_claims.task` (migration `022_phase2_analysis.sql:31`), populated by the `evidence_matrix` primitive (`prompts.py:890`). Extending `claim_extract` would:
1. Break the existing `Claim` dataclass shape (no `task` field) and downstream parsers
2. Duplicate data with `normalized_claims.task`
3. Require `claim_extract` to write to `paper_tasks` — but `claim_extract` currently does not perform DB writes other than its primary claim-writing path

**Adopted plan**:
- Ensure `evidence_matrix` is triggered for every head paper after ingest (it's gated by having `claim_extract` output to normalize; verify trigger condition in `harness.py`)
- Read `normalized_claims.task` as the authoritative task signal
- Migration 046 adds `normalized_claims.task_canonical` (populated by new `task_canonicalize` primitive)
- Paper-level primary task = mode of `task_canonical` across that paper's normalized claims (computed on-demand, no extra table)

**`task_canonicalize` primitive** (runs periodically or when new distinct tasks > 50):
  - Input: distinct `normalized_claims.task` values within a domain where `task_canonical IS NULL`
  - Sonnet-tier LLM call: "Here are N task names; group near-duplicates and output one canonical label per group. Preserve distinctions across sub-tasks (e.g., 'sentiment classification' vs 'stance detection')."
  - Writes `task_canonical` back via bulk UPDATE
  - Idempotent — safe to re-run as the vocabulary grows

---

## 3. Multi-dimensional red-ocean quantification (Phase 2 continued) — **r3 revised**

### D9. Per-dimension red-ocean formulas

Red-ocean is computed independently for **three dimensions** (area, task, method). Each dimension has its own normalized score ∈ [0,1]:

```
area_red_ocean = clip(0, 1,
    0.30 × volume_pressure        # tanh(log2(papers_in_area_last_2y / median_across_areas_in_domain))
  + 0.30 × method_convergence     # top-3 method share among verified claims in area
  + 0.25 × lab_concentration      # HHI of top-10 affiliations, normalized to [0,1]
  − 0.15 × gap_density_cap        # min(0.2, verified_open_gaps / papers_in_area)
)

task_red_ocean = clip(0, 1,
    0.50 × volume_pressure(task)          # papers_with_task_last_2y / median_across_tasks_in_domain
  + 0.30 × method_convergence(task)       # same formula, restricted to papers with this task
  + 0.20 × lab_concentration(task)
)
-- Simpler than area: no gap_density term (gaps aren't task-scoped in schema)

method_red_ocean = clip(0, 1,
    0.60 × share_of_papers_using_method_in_scope  # scope = primary area or domain
  + 0.40 × growth_rate(method_2y)                 # tanh(YoY papers-using-method)
)
```

**Storage**:
- `research_areas.red_ocean_score` + `red_ocean_breakdown` (materialized per area)
- `task_red_ocean` computed on-demand via SQL aggregate on `normalized_claims.task_canonical` — no separate table. If this becomes a hot query, add a materialized view `task_red_ocean_v` in a follow-up migration.
- `method_red_ocean` computed per query (method space is small per area), not materialized

**Data source gating**:
- `method_convergence` uses `normalized_claims.method` with `confidence ≥ 0.5`
- `gap_density_cap` uses `gaps.cross_verified = 1 OR gaps.confidence ≥ 0.5` (D19)
- `lab_concentration` uses `papers.authors` (JSON) — parse affiliations; fall back to author-name HHI if affiliations absent

**Default weights are anchors**; calibrate once 30-anchor labeled set exists (same playbook as publishability rubric).

### D10. Multi-dimensional sort + UI surfacing

**API sort** (recommendation list default):
```sql
ORDER BY (area_red_ocean >= 0.7 AND task_red_ocean >= 0.7) ASC,  -- bucket 1: not double-red
         confidence_level = 'low' ASC,                             -- high/normal first
         llm_score DESC
```

Rationale (codex fix #4 extended): a candidate is bucketed into "red ocean" only when **both area AND task** are saturated. This surfaces the key insight: **a blue-ocean task inside a red-ocean area is still a valid opportunity**. A candidate that's red on method but blue on task can still rank top.

**UI surfacing** on recommendation cards:
```
Title: Retrieval-augmented RLHF for small LMs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[🌊 Red area: RLHF]  [💙 Blue task: small-LM alignment]  [🌊 Red method: DPO]
→ Opportunity angle: new task on mature methods
```

The "opportunity angle" text is a deterministic template based on which dimensions are blue:
- `(task blue, method red)` → "new task on mature methods" (safe, incremental)
- `(task red, method blue)` → "novel method on known task" (ambitious, competitive benchmarks)
- `(task blue, method blue)` → "frontier direction" (high risk/reward)
- `(all red)` → bucketed to red-ocean lane; "differentiation needed"

---

## 4. Recommendation engine (Phase 3)

### D11. Rewrite `RECOMMENDATION_ENGINE.md` for LLM scoring — **consolidated schema**

**Action item (in-scope for Phase 3 start)**: Before migration `048_research_candidates.sql` ships, `docs/architecture/RECOMMENDATION_ENGINE.md` MUST be updated. Two options:
- Option A: rewrite §3 (schema) and §4c–§4d (scoring) to match the consolidated schema below and the LLM-scoring decision
- Option B: prepend a `> DEPRECATED by CS_RESEARCH_WORKFLOW_V2.md §4` banner and archive the doc under `docs/architecture/archive/`

**Migration collision note** (codex round-4 #4): the existing `RECOMMENDATION_ENGINE.md:73` claims migration 043 for `research_candidates`. That migration has NOT been created in `migrations/`. The CS workflow claims 045–048. So the RECOMMENDATION_ENGINE doc's 043 claim is obsolete; if Option A is taken, re-point the doc to 048.

**Consolidated schema** (codex round-4 #1/#2 contradictions fixed — single truth, no D13 override needed):

```sql
-- 048_research_candidates.sql
CREATE TABLE research_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,                            -- 'domain:N' | 'research_area:N' | 'topic:N'
    primary_domain_id INTEGER REFERENCES domains(id),
    research_area_ids TEXT NOT NULL DEFAULT '[]',    -- JSON int[]
    title TEXT NOT NULL,
    pitch TEXT NOT NULL DEFAULT '',
    llm_score NUMERIC NOT NULL,                     -- from direction_ranking (LLM, 0..10)
    llm_score_breakdown TEXT NOT NULL DEFAULT '{}',  -- {novelty, feasibility, impact, momentum}
    area_red_ocean NUMERIC NOT NULL DEFAULT 0,       -- r3 multi-dimensional
    task_red_ocean NUMERIC NOT NULL DEFAULT 0,
    method_red_ocean NUMERIC NOT NULL DEFAULT 0,
    opportunity_angle TEXT,                          -- 'new_task_mature_method' | 'novel_method_known_task' | 'frontier' | 'red_ocean'
    confidence_level TEXT NOT NULL DEFAULT 'normal', -- low|normal|high (deterministic)
    evidence_gap_ids TEXT NOT NULL DEFAULT '[]',
    evidence_contradiction_ids TEXT NOT NULL DEFAULT '[]',
    evidence_claim_ids TEXT NOT NULL DEFAULT '[]',
    seed_paper_ids TEXT NOT NULL DEFAULT '[]',
    why TEXT NOT NULL DEFAULT '[]',
    risks TEXT NOT NULL DEFAULT '[]',
    lineage_key TEXT NOT NULL,
    evidence_signature TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    narration_model TEXT,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(scope, lineage_key)
);

CREATE INDEX idx_rc_scope_sort
    ON research_candidates(scope, status,
        (area_red_ocean >= 0.7 AND task_red_ocean >= 0.7),
        confidence_level, llm_score DESC);
```

### D12. Pipeline
```
scope (domain:N | research_area:N | topic:N)
    ↓
candidate_seeding (deterministic: group gaps + contradictions + claims)
    ↓
direction_ranking (LLM — existing, extended)
    ↓
persist research_candidates (upsert by lineage_key)
```

### D13. Extend `direction_ranking` input schema (r3)

Add to existing prompt (no new primitive): `area_red_ocean`, `task_red_ocean`, `method_red_ocean` (+ breakdowns), `research_area_name`, `primary_task`, `primary_method`, and the deterministic `opportunity_angle` tag from D10.

Prompt instructs LLM to produce breakdown scores for novelty/feasibility/impact/momentum. Final sort is deterministic multi-dimensional (D10); LLM's free-text reasoning references the `opportunity_angle` so the pitch stays aligned with the actual blue/red mix.

(Schema already includes these columns — see D11's consolidated schema. No further schema changes here.)

### D14. Promote to topic (codex fix #9)
Promote endpoint:
1. Create `topic` row (existing table): name=candidate.title, description=candidate.pitch, domain_id=primary_domain
2. Link `paper_topics` entries for each seed_paper_id
3. Copy evidence → initial `project_artifacts` with `artifact_type='topic_brief'`, `stage='init'`
4. Call `orchestrator_init` handler via **Python import** (not subprocess). The CLI handler in `cli.py` delegates to a service function — import that directly to share DB connection + avoid env var plumbing (per codex round 2 Q3).
5. v2 follow-up: expose `orchestrator_init_tool` MCP wrapper for symmetry

---

## 5. CC experiment handoff (Phase 4)

### D15. `experiment_handoff_prepare(topic_id)` — corrected fields

```python
# insert into project_artifacts with CORRECT schema (codex fix #7)
conn.execute("""
    INSERT INTO project_artifacts
    (project_id, topic_id, stage, artifact_type, title, payload_json)
    VALUES (?, ?, 'experiment', 'experiment_brief', ?, ?)
""", (project_id_for_topic(topic_id), topic_id, title, json.dumps(brief)))
```
Returns `artifact_id` + paste-ready prompt.

### D16. `experiment_handoff_submit(topic_id, result)` — same fix
Writes `artifact_type='experiment_result'`, `stage='experiment'`, links via `parent_artifact_id` to the brief.

---

## 6. Narrative imitation (Phase 4, bonus)

### D18 (renumbered from original §6)
Defer sentence-level style transfer. Existing `competitive_learning` + `writing_pattern_extract` + `writing_skill_aggregate` cover structural patterns. Revisit after MVP ships.

---

## 7. Mid-stream entry (Phase 4)

### D17. New MCP tool `workflow_entry` (codex fix #8 — rename to avoid collision)

Avoids collision with existing `orchestrator_resume(topic_id)`. Uses correct stage names.

```python
@mcp.tool()
def workflow_entry(user_context: str,
                   topic_id: int | None = None,
                   artifact_paths: list[str] | None = None,
                   keywords: list[str] | None = None) -> WorkflowEntryResult:
    """Classify user's current research state and route to appropriate primitive.
    Does NOT create topics — caller decides whether to promote/init.
    Stages: init | build | analyze | propose | experiment | write
    """
```

Routing table (corrected stages):
| User input | Stage | Suggested primitives |
|---|---|---|
| Keywords only | `init` | cs_harvest → domain_classify → research_area_extract |
| topic_id + papers | `build`/`analyze` | claim_extract, gap_detect |
| topic_id + gaps | `propose` | direction_ranking, algorithm_design_loop |
| topic_id + results | `experiment`→`write` | section_draft, competitive_learning |
| topic_id + draft | `write` | adversarial_review (via existing tool) |

---

## 8. Gap/claim quality gate (Phase 4, codex-rewritten)

### D19. Add columns + new cross-check primitive
Migration:
```sql
ALTER TABLE gaps ADD COLUMN confidence REAL DEFAULT NULL;
ALTER TABLE gaps ADD COLUMN cross_verified INTEGER DEFAULT 0;
ALTER TABLE gaps ADD COLUMN cross_check_runs INTEGER DEFAULT 0;
```

New primitive `gap_cross_verify(topic_id, sample_ratio=0.2)`:
- Samples 20% of recent gaps for topic
- Re-runs `gap_detect` on source papers with different LLM (Opus via llm_router)
- Computes Jaccard per paper; if ≥ 0.6 → `cross_verified=1`
- Writes back `confidence` = Jaccard

Extend `gap_detect` prompt to emit self-reported confidence per gap (0-1). Store on insert.

Recommendation engine filters: only count gaps where `cross_verified=1 OR confidence >= 0.5`.

---

## 9. Phased delivery (r3)

### Phase 0 — CSO validation spike (2-3 days, **must pass before Phase 2 start**)

Before committing to CSO as primary classifier, validate its coverage on recent AI terms.

**Prerequisite** (codex round-4 #1): bump `packages/research_harness/pyproject.toml` `requires-python` from `>=3.10` to `>=3.11`. Without this, `cso-classifier` cannot install. Do this as the first commit of Phase 0, before trying to install CSO.

**Steps**:
1. Bump Python to `>=3.11` in pyproject.toml
2. Install `cso-classifier>=4.0.1`, run `cc.setup()` (download ~2GB model)
3. Hand-pick 30 recent papers (2024-2026): 10 LLM alignment, 10 diffusion/multimodal, 5 agents, 5 classical (e.g., graph algorithms, PL)
3. Run `cso_classify` on each; record the `enhanced` label list returned
4. Manual labeling: for each paper, does CSO surface the expected concept? (hit / miss / too generic)
5. Score:
   - **≥80% hit rate** → CSO as primary, LLM drift-patch rarely triggered (go ahead with D6/D7 as written)
   - **50-80%** → CSO as primary + aggressive LLM drift-patch (flagged for weekly review)
   - **<50%** → fallback: LLM-primary classification (revert to original D6/D7 LLM approach). Still drop D7 auto-clustering in favor of directly labeling research_area per paper via LLM.

Document result in `docs/architecture/CS_RESEARCH_WORKFLOW_V2_PHASE0_RESULTS.md`. Blocks Phase 2 if <50%.

### Phase 1 (1 week): Retrieval
- D1 (extend SearchQuery + provider category support)
- D2 (head_paper_rank)
- D3 (cs_harvest primitive)
- (Python bump already done in Phase 0 prerequisite)

### Phase 2 (1 week): Classification + red-ocean
- Phase 0 result gates this phase
- D4 (seed domains)
- D5 migrations: `045_cs_classification.sql` (research_areas, paper_research_areas, paper_domains) + `046_task_canonicalization.sql` (ALTER normalized_claims ADD task_canonical)
- D6 (cso_classify) — **or fallback LLM domain_classify if Phase 0 score <50%**
- D7 (LLM drift-patch)
- D8 (reuse `normalized_claims.task` via `evidence_matrix`; add `task_canonicalize` primitive)
- D9 (per-dimension red-ocean: area, task, method)

### Phase 3 (1 week): Recommendation
- D10 (multi-dimensional sort + opportunity_angle)
- D11 (research_candidates migration — **precondition: RECOMMENDATION_ENGINE.md updated or deprecated banner added**)
- D12 (pipeline)
- D13 (direction_ranking schema extension)
- D14 (promote to topic via Python import)

### Phase 4 (1 week): Integration + QA
- D15/D16 (experiment handoff)
- D17 (workflow_entry)
- D19 (gap cross-verify) — includes migration `047_gap_confidence.sql`

**Exit criteria**: `cs_harvest(2025, 1000)` → 1000 classified papers → ~150-300 research_areas (CSO-derived) → tasks extracted + canonicalized → per-dimension red-ocean computed → pick 3 random areas → recommendation engine produces ≥3 candidates each with typed evidence + opportunity_angle + ≥2 dimension red-ocean scores → promote-to-topic creates valid topic via Python import to `orchestrator_init`.

---

## 10. Reuse audit (r3)

| Feature | Verified existing | Delta |
|---|---|---|
| arxiv/S2/OpenAlex providers | ✓ (paper_source_clients.py) | add category params |
| SearchQuery / SearchAggregator | ✓ (paper_sources.py) | extend schema |
| `gap_detect` / `claim_extract` / `direction_ranking` / `competitive_learning` / `evidence_matrix` | ✓ (registry.py, llm_primitives.py) | extend input for `direction_ranking`; reuse existing `evidence_matrix` task output — no `claim_extract` change |
| `domains` / `topics` / `paper_topics` / `gaps` / `normalized_claims` / `venue_ranks` | ✓ (migrations) | add columns to `gaps`; new tables |
| `project_artifacts` | ✓ (migration 006) | use correct fields |
| `orchestrator_resume` (topic-bound) | ✓ (MCP) | keep — NEW tool is `workflow_entry` |
| `orchestrator_init` | ⚠ CLI only, no MCP | call via Python import from promote |
| `llm_router` tier routing | ✓ | — |
| `codex_bridge` | ⚠ internal helper, not primitive | new `gap_cross_verify` primitive uses llm_router directly |
| **External: CSO Classifier v4.0.1** (Apache 2.0) | — | new optional dep `research-harness[cs]` + ~2GB model via `cc.setup()` |
| **New tables**: research_areas, paper_research_areas, paper_domains, research_candidates | — | migrations 045 & 048 |
| **Column additions**: `normalized_claims.task_canonical` (046), `gaps.confidence`/`cross_verified`/`cross_check_runs` (047) | — | 4 ALTER TABLE (in 046, 047) |
| **New primitives**: cs_harvest, head_paper_rank, cso_classify, area_drift_patch, task_canonicalize, gap_cross_verify | — | 6 new |
| **New MCP tools**: experiment_handoff_prepare/submit, workflow_entry | — | 3 new |

**Bottom line**: 4 new tables (`paper_tasks` removed in r3-fix; reuse `normalized_claims.task` per codex #4), 6 primitives, 3 MCP tools, 4 column additions, 4 migrations (045–048), 1 external dependency (optional extra), 1 Python version bump. All other work is extension/param-threading.

**R3 net change vs r2**:
- Kills 2 LLM primitives (`domain_classify`, `research_area_extract`) → replaced by deterministic CSO (no LLM cost on hot path)
- Adds 3 primitives (`cso_classify`, `area_drift_patch`, `task_canonicalize`) — task extraction reuses existing `evidence_matrix` / `normalized_claims.task`, no `claim_extract` modification
- Removes planned `paper_tasks` table (codex round-4 #4: `normalized_claims.task` already exists in migration 022)
- **Net cost reduction**: ~$5-10 per 1000-paper harvest (LLM → CSO)
- **Net capability gain**: multi-dimensional red-ocean enables "blue-task × red-method" discovery

---

## 11. Round-2 open questions — resolved

1. ~~early_citation_percentile~~ → **resolved**: providers don't expose `publication_date` granularity. Use `venue_quality` alone for current-year papers (D2 updated).
2. ~~concept intersection threshold~~ → **resolved**: ">2 shared concepts" is prototype anchor, calibrate on a 50-paper sample before locking. Calibration is Phase 2 sub-task.
3. ~~subprocess vs import~~ → **resolved**: use Python import for `orchestrator_init` (D14 updated).

## 12. Codex round-2 new issues — resolved

- ~~Migration 042 collision~~ → renumbered to 045/046/047/048 (split by phase, codex round-4 fix).
- ~~`paper_ingest(topic_id=None)`~~ → verified: `impls.py` `paper_ingest` signature accepts `topic_id: int | None = None`. Topicless ingest supported.

---

## R. R3 rationale (CSO + TaxoAdapt-inspired)

### Why CSO over LLM classification
| Axis | LLM `domain_classify` (r2) | CSO Classifier (r3) |
|---|---|---|
| Cost per 1000 papers | ~$1 Haiku calls | $0 (CPU only) |
| Reproducibility | Stochastic (sampling temp) | Deterministic |
| Ontology coverage | Whatever LLM knows | 14K curated CS topics, updated 2025 |
| Setup | Zero | `pip install` + 2GB model download |
| Python version | 3.10+ | 3.11+ (RH bump required) |
| New terminology (LLM, RLHF etc.) | ✓ inherent | ⚠ requires Phase 0 validation |

Mitigated via Phase 0 spike + LLM drift-patch fallback (D7).

### Why TaxoAdapt ideas but not TaxoAdapt library
TaxoAdapt is a **taxonomy generator** (builds trees from corpus). RH needs a **classifier into stable taxonomy** (reproducible assignments). Different tools.

What we adopted from TaxoAdapt:
- **Multi-dimensional research space** — papers exist in (area, task, method, dataset, metric) simultaneously
- **Red-ocean is dimension-specific** — a task can be blue in a red area
- **Opportunity-angle framing** — recommendation cards surface cross-dimension novelty

What we rejected:
- Dynamic taxonomy generation (not reproducible, hard to accumulate)
- 5-dimension independent classification (3 dimensions already in `normalized_claims`; only `task` is a genuine new extraction)

### Non-goals for r3
- **Application-domain dimension** (healthcare / finance) — defer to Phase 5
- **Per-dimension calibration anchors** — same 30-anchor set will cover all dimensions once collected; don't over-engineer pre-calibration
- **Integrating CSO into existing `concepts` field** on PaperRecord — keep CSO output in new `paper_research_areas` table, don't modify `PaperRecord.concepts`

### v0.5 candidate: TaxoAdapt density-triggered drift-patch adaptation
(Deferred by Neal on 2026-04-23, captured for future reference — **NOT in MVP**)

Inspired by TaxoAdapt's (pkargupta/taxoadapt, ACL 2025) **density-triggered** expansion rules. Apply ONLY to `source='llm_drift_patch'` areas (CSO-derived areas stay read-only):

- **Width trigger**: drift-patch area with > N_WIDTH (~10) papers, not covered by any single CSO area at >50% → formalize as stable area (polished name, `status='promoted'`)
- **Depth trigger**: drift-patch area with > N_DEPTH (~30) papers → LLM proposes 2-5 sub-areas from paper titles/claims; redistribute papers; parent becomes umbrella
- **Merge trigger**: two drift-patch areas in same domain with paper overlap > 60% OR slug similarity > 0.7 → LLM judges; merge if genuine duplicate

Implementation: one new primitive `area_adapt(domain_id)` run weekly. Small LLM cost (a few Sonnet calls per domain per week).

Why deferred: current D7 "< 5 papers collapse" rule handles basic fragmentation. Density-triggered adaptation is a robustness enhancement worth building only if drift-patch areas prove unwieldy in practice.
