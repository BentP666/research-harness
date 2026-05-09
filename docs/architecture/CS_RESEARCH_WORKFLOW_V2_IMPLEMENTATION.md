# CS Research Workflow — Implementation Manual

> **Companion to**: `docs/architecture/CS_RESEARCH_WORKFLOW_V2.md` (r3 — design)
> **Audience**: A less-capable model (Haiku-tier) or junior engineer executing the plan.
> **Do not second-guess the design**. This doc tells you WHAT to build; the design doc tells WHY. If any instruction here conflicts with the design doc, STOP and ask.

---

## 0. How to use this manual

**Rules for the executor**:

1. **Work through tasks in order within a phase**. Cross-phase ordering is strict.
2. **Each task has**: Goal · Prerequisites · Files to edit · Test · Exit criteria. Verify the Exit criterion before moving on.
3. **One task = one commit**. Commit message format: `feat(cs-workflow): Task N.M — <short summary>`.
4. **If a test fails, stop**. Don't "fix" by loosening the test. Report back with: the failing command, the error message, which task.
5. **DO NOT skip Phase 0**. It gates whether we use CSO or LLM for classification.
6. **Do not touch files/tables not listed in a task's "Files to edit"**. If a task needs an unlisted file, stop and ask.
7. **Never create a new migration with a number already in use**. Check `ls packages/research_harness/migrations/` first. Current claimed: 001–042 exist; 043–048 reserved by this plan.
8. **Every new primitive MUST be registered** in `packages/research_harness/research_harness/primitives/registry.py` AND dispatched in `packages/research_harness/research_harness/execution/harness.py`. Skipping this means the primitive is dead code.
9. **Every new MCP tool MUST be exposed** in `packages/research_harness_mcp/research_harness_mcp/tools.py` via `@mcp.tool()` decorator.
10. **All tests run via**: `python -m pytest packages/ -q --tb=short -x` (the `-x` stops on first failure). Run from repo root.

**File path convention**: all paths are absolute from repo root. When editing, use the Edit tool, not Write (except for brand-new files).

**When stuck**: read the relevant section of `docs/architecture/CS_RESEARCH_WORKFLOW_V2.md` for context. That doc is the source of truth for design decisions.

---

## Phase 0 — CSO Validation Spike

**Goal**: Decide whether CSO is good enough to replace LLM classification. Gates Phase 2.

### Task 0.1 — Bump Python to 3.11

- **Files to edit**: `packages/research_harness/pyproject.toml`
- **Change**: `requires-python = ">=3.10"` → `requires-python = ">=3.11"`
- **Also check** (edit if present with same string): `packages/paperindex/pyproject.toml`, `packages/research_harness_mcp/pyproject.toml`, `packages/llm_router/pyproject.toml`
- **Test**:
  ```bash
  python --version  # must be 3.11 or 3.12
  pip install -e packages/research_harness/
  ```
- **Exit criterion**: `pip install` succeeds.
- **If fail**: user's Python is 3.10. They must create a 3.11+ venv before proceeding.

### Task 0.2 — Add CSO optional dependency

- **Files to edit**: `packages/research_harness/pyproject.toml`
- **Change**: Under `[project.optional-dependencies]`, add:
  ```toml
  cs = [
    "cso-classifier>=4.0.1",
  ]
  ```
  If `[project.optional-dependencies]` doesn't exist, create it.
- **Test**:
  ```bash
  pip install -e "packages/research_harness/[cs]"
  python -c "from cso_classifier.classifier import CSOClassifier; print('OK')"
  ```
- **Exit criterion**: import succeeds.

### Task 0.3 — Download CSO model

- **Create file**: `scripts/cso_setup.py`
  ```python
  """One-time CSO ontology + word2vec download (~2GB). Run once per env."""
  from cso_classifier.classifier import CSOClassifier
  cc = CSOClassifier()
  cc.setup()  # downloads ontology RDF + word2vec model
  print("CSO setup complete.")
  ```
- **Test**:
  ```bash
  python scripts/cso_setup.py
  ```
  Expected: takes 5-15 min; no errors; prints "CSO setup complete."
- **Exit criterion**: `~/.cso-classifier/` directory exists and contains `.rdf` and `.p` files.

### Task 0.4 — Pick 30 validation papers

- **Create file**: `scripts/phase0/validation_papers.json`
- **Structure**: list of 30 objects:
  ```json
  [
    {"id": "llm_1", "category": "llm_alignment", "title": "...", "abstract": "...", "keywords": ["...", "..."], "expected_concepts": ["instruction tuning", "RLHF"]},
    ...
  ]
  ```
- **Sourcing**: USER supplies the 30 papers. Write this in the commit note: "Task 0.4 requires user to populate validation_papers.json with 30 hand-picked recent (2024–2026) papers: 10 LLM alignment, 10 diffusion/multimodal, 5 agents, 5 classical CS."
- **Exit criterion**: file exists with 30 entries each having non-empty `title`, `abstract`, and `expected_concepts` (1-3 terms).

### Task 0.5 — Run CSO coverage test

- **Create file**: `scripts/phase0/validate_cso.py`
  ```python
  """Run CSO over 30 validation papers; compute hit rate."""
  import json
  from pathlib import Path
  from cso_classifier.classifier import CSOClassifier

  papers = json.loads(Path("scripts/phase0/validation_papers.json").read_text())
  batch_input = {
      p["id"]: {"title": p["title"], "abstract": p["abstract"],
                "keywords": " ".join(p["keywords"])}
      for p in papers
  }
  cc = CSOClassifier(modules="both", enhancement="first",
                     explanation=False, get_weights=False)
  results = cc.batch_run(batch_input)

  hits, misses, generic = 0, 0, 0
  GENERIC_TERMS = {"computer science", "artificial intelligence",
                   "machine learning", "deep learning"}
  report = []
  for p in papers:
      got = set(results[p["id"]].get("enhanced", []))
      expected = {c.lower() for c in p["expected_concepts"]}
      overlap = {g.lower() for g in got} & expected
      if overlap:
          hits += 1
          status = "hit"
      elif got <= {t.lower() for t in GENERIC_TERMS}:
          generic += 1
          status = "too_generic"
      else:
          misses += 1
          status = "miss"
      report.append({"id": p["id"], "category": p["category"],
                     "expected": list(expected),
                     "got": list(got)[:10],
                     "status": status})

  total = len(papers)
  Path("scripts/phase0/cso_validation_report.json").write_text(
      json.dumps({"hits": hits, "misses": misses, "generic": generic,
                  "total": total, "hit_rate": hits / total, "details": report},
                 indent=2)
  )
  print(f"hits={hits}/{total} ({hits/total:.1%}) misses={misses} generic={generic}")
  ```
- **Test**:
  ```bash
  python scripts/phase0/validate_cso.py
  ```
- **Exit criterion**: `cso_validation_report.json` created; prints hit rate.

### Task 0.6 — Document and branch

- **Create file**: `docs/architecture/CS_RESEARCH_WORKFLOW_V2_PHASE0_RESULTS.md`
- **Content template**:
  ```markdown
  # Phase 0 — CSO Validation Results

  **Date**: YYYY-MM-DD
  **Hit rate**: X/30 = Y%
  **Generic-only**: Z
  **Decision**:
  - [ ] ≥80% → CSO as primary (proceed with D6/D7 as designed)
  - [ ] 50–80% → CSO as primary + aggressive LLM drift-patch
  - [ ] <50% → revert to LLM primary classification (skip CSO)

  ## Per-category breakdown
  | Category | Hits | Total |
  |---|---|---|
  | llm_alignment | N | 10 |
  | diffusion_multimodal | N | 10 |
  | agents | N | 5 |
  | classical | N | 5 |

  ## Notable misses
  (list papers where CSO failed and what it should have returned)
  ```
- **Action based on hit rate** — set in `packages/research_harness/research_harness/config.py`:
  ```python
  CSO_MODE = "primary"  # or "primary_with_aggressive_patch" or "llm_fallback"
  ```
  If variable doesn't exist, create it with a top-level assignment. Default to `"primary"`.
- **Exit criterion**: Phase0 results doc filled; CSO_MODE set.

**Phase 0 gate**: if `CSO_MODE == "llm_fallback"`, D6 in Phase 2 uses LLM (see Phase 2 Task 2.6 fallback branch). Otherwise proceed normally.

---

## Phase 1 — Bulk CS Paper Retrieval

**Goal**: Harvest ~1000 high-quality CS papers/year with arxiv category filtering.

### Task 1.1 — Extend `SearchQuery` dataclass

- **File**: `packages/research_harness/research_harness/paper_sources.py`
- **Locate**: `class SearchQuery` (around line 47)
- **Add fields** (after existing fields, preserve ordering):
  ```python
  subject_categories: list[str] | None = None
  per_provider_limit: int = 50
  ```
- **Important**: use `None` default for `subject_categories` (not empty list) so existing callers don't change behavior.
- **Test**:
  ```bash
  python -c "from research_harness.paper_sources import SearchQuery; q = SearchQuery(query='x'); print(q.subject_categories, q.per_provider_limit)"
  ```
  Expected: `None 50`
- **Exit criterion**: command prints `None 50` without error.

### Task 1.2 — Update cache key to include new fields

- **File**: `packages/research_harness/research_harness/core/search_cache.py`
- **Locate**: `_cache_key(query, source, params)` function (around line 33)
- **Change**: current code hashes `query + source + params`. You need to ensure that `params` includes the new fields whenever callers pass them. DO NOT change `_cache_key`'s signature.
- **Action**: Find all callsites of `cache_get` and `cache_put`:
  ```bash
  grep -rn "cache_get\|cache_put" packages/research_harness/research_harness/ | grep -v search_cache.py
  ```
  For each callsite, ensure the `params` dict passed includes `subject_categories` and `per_provider_limit` (convert list to sorted tuple for stable hashing):
  ```python
  params = {
      "year_from": q.year_from,
      "year_to": q.year_to,
      "limit": q.per_provider_limit,            # was q.limit
      "categories": tuple(sorted(q.subject_categories or [])),  # NEW
  }
  ```
- **Test**: add a unit test at `packages/research_harness/tests/test_search_cache.py`:
  ```python
  def test_cache_key_differs_by_categories():
      from research_harness.core.search_cache import _cache_key
      k1 = _cache_key("x", "arxiv", {"categories": ("cs.LG",)})
      k2 = _cache_key("x", "arxiv", {"categories": ("cs.CV",)})
      assert k1 != k2
  ```
- **Exit criterion**: `pytest packages/research_harness/tests/test_search_cache.py -q` passes.

### Task 1.3 — ArxivProvider category support

- **File**: `packages/research_harness/research_harness/paper_source_clients.py`
- **Locate**: `class ArxivProvider` line 671, `def search` line 677
- **Change**: When building the arxiv API URL query string, if `query.subject_categories` is non-empty, prepend category filter:
  ```python
  if query.subject_categories:
      cat_clause = " OR ".join(f"cat:{c}" for c in query.subject_categories)
      q_str = f"({cat_clause}) AND (all:{query.query})"
  else:
      q_str = f"all:{query.query}"
  ```
- **Replace `max_results`**: change `max_results=query.limit` (or wherever `limit` is used) to `max_results=query.per_provider_limit`.
- **Test**: integration test (hits arxiv API, costs nothing):
  ```python
  # packages/research_harness/tests/test_arxiv_categories.py
  from research_harness.paper_sources import SearchQuery
  from research_harness.paper_source_clients import ArxivProvider
  def test_arxiv_category_filter():
      p = ArxivProvider()
      q = SearchQuery(query="attention",
                      subject_categories=["cs.LG"],
                      year_from=2024, year_to=2024,
                      per_provider_limit=5)
      results = p.search(q)
      assert len(results) > 0
      # All results should have cs.LG in categories if PaperRecord.metadata carries it
  ```
- **Exit criterion**: test passes.

### Task 1.4 — OpenAlexProvider category support

- **File**: `packages/research_harness/research_harness/paper_source_clients.py`
- **Locate**: `class OpenAlexProvider` line 209, `def search` line 222
- **Mapping**: arxiv CS categories → OpenAlex concept IDs. Create a constant at module top:
  ```python
  # Wikidata IDs for OpenAlex concepts corresponding to arxiv CS categories.
  # Lookup: https://api.openalex.org/concepts?search=machine+learning
  ARXIV_TO_OPENALEX_CONCEPT = {
      "cs.AI": "C154945302",  # Artificial Intelligence
      "cs.LG": "C119857082",  # Machine Learning
      "cs.CV": "C31972630",   # Computer Vision
      "cs.CL": "C204321447",  # Natural Language Processing
      "cs.IR": "C23123220",   # Information Retrieval
      "cs.RO": "C90509273",   # Robotics
      "cs.CR": "C38652104",   # Computer Security
      "cs.DB": "C77088390",   # Database
      "cs.DC": "C79974875",   # Distributed Computing
      "cs.DS": "C11413529",   # Data Structures / Algorithms
      "cs.HC": "C107457646",  # Human-Computer Interaction
      "cs.PL": "C2524010",    # Programming Languages
      "cs.SE": "C115903868",  # Software Engineering
      "cs.SY": "C127413603",  # Control Systems
  }
  ```
- **In `search`**: when `query.subject_categories` is set, add filter:
  ```python
  if query.subject_categories:
      concept_ids = [ARXIV_TO_OPENALEX_CONCEPT.get(c) for c in query.subject_categories]
      concept_ids = [c for c in concept_ids if c]
      if concept_ids:
          params["filter"] = params.get("filter", "")
          prefix = "," if params["filter"] else ""
          params["filter"] += f"{prefix}concepts.id:{'|'.join(concept_ids)}"
  ```
- **Replace limit**: use `query.per_provider_limit` everywhere this provider used `query.limit`.
- **Test**: skip unit test if `OPENALEX_API_KEY` not set. If set, add similar integration test as 1.3.
- **Exit criterion**: code compiles (`python -c "import research_harness.paper_source_clients"`); existing tests still pass.

### Task 1.5 — SemanticScholarProvider fieldsOfStudy

- **File**: `packages/research_harness/research_harness/paper_source_clients.py`
- **Locate**: `class SemanticScholarProvider` line 431, `def search` line 479
- **Change**: if `query.subject_categories` has ANY CS category, add to request params:
  ```python
  if query.subject_categories:
      cs_cats = [c for c in query.subject_categories if c.startswith("cs.")]
      if cs_cats:
          params["fieldsOfStudy"] = "Computer Science"
          # DO NOT post-filter by specific subcategory — S2 doesn't store them reliably.
  ```
- **Replace limit**: use `query.per_provider_limit`.
- **Test**: code compiles, existing tests pass.
- **Exit criterion**: `pytest packages/research_harness/ -q -k "semantic_scholar or s2"` passes.

### Task 1.6 — Remove `limit=50` hardcoding in primitives/impls.py

- **File**: `packages/research_harness/research_harness/primitives/impls.py`
- **Locate**: line 106 `limit=50,  # per-provider cap`
- **Change**: replace with `limit=params.get("per_provider_limit", 50),`. In the same function, accept `per_provider_limit` as a new optional parameter forwarded to `AggSearchQuery`.
- **Test**: existing tests.
- **Exit criterion**: `pytest packages/research_harness/tests/ -q -k "paper_search"` passes.

### Task 1.7 — Add `head_paper_rank` primitive

- **File**: `packages/research_harness/research_harness/execution/llm_primitives.py` (even though it's deterministic, co-locate with other primitives)

  Actually — since this is deterministic, put it in a new file: `packages/research_harness/research_harness/primitives/head_paper.py`

- **Create file**: `packages/research_harness/research_harness/primitives/head_paper.py`
  ```python
  """Deterministic head-paper ranking (no LLM).

  Score = citation_term × venue_quality × recency_decay

  - current_year papers: citation_term = venue_quality (no citation history)
  - else: citation_term = log(1+cites) / log(1+median_year_cites)
  """
  from __future__ import annotations
  import math
  from dataclasses import dataclass
  from typing import Any
  from ..storage.db import Database

  CCF_RANK_SCORE = {
      "A*": 1.0, "A+": 1.0, "A-STAR": 1.0,
      "A": 0.8, "CCF_A": 0.8,
      "B": 0.5, "CCF_B": 0.5,
      "C": 0.3, "CCF_C": 0.3,
  }
  UNRANKED_PRIOR = 0.4

  @dataclass
  class RankedPaper:
      paper_id: int
      score: float
      citation_term: float
      venue_q: float
      recency: float

  def _venue_quality(db: Database, venue_name: str) -> float:
      if not venue_name:
          return UNRANKED_PRIOR
      row = db.conn.execute(
          "SELECT ccf_rank, impact_factor FROM venue_ranks "
          "WHERE lower(canonical_name) = lower(?) OR lower(name) = lower(?) "
          "LIMIT 1",
          (venue_name, venue_name),
      ).fetchone()
      if not row:
          return UNRANKED_PRIOR
      rank = (row["ccf_rank"] or "").upper().strip()
      if rank in CCF_RANK_SCORE:
          return CCF_RANK_SCORE[rank]
      if row["impact_factor"] is not None:
          return _if_percentile(db, row["impact_factor"])
      return UNRANKED_PRIOR

  def _if_percentile(db: Database, value: float) -> float:
      row = db.conn.execute(
          "SELECT COUNT(*) as total, SUM(CASE WHEN impact_factor <= ? THEN 1 ELSE 0 END) as below "
          "FROM venue_ranks WHERE impact_factor IS NOT NULL",
          (value,),
      ).fetchone()
      if not row or not row["total"]:
          return UNRANKED_PRIOR
      return float(row["below"]) / float(row["total"])

  def head_paper_rank(
      *, db: Database, year: int, paper_ids: list[int],
      current_year: int = 2026, target: int | None = None, **_: Any,
  ) -> list[RankedPaper]:
      # Fetch papers
      placeholders = ",".join("?" * len(paper_ids))
      rows = db.conn.execute(
          f"SELECT id, year, venue, citation_count FROM papers WHERE id IN ({placeholders})",
          paper_ids,
      ).fetchall()
      # Median citations for this year (for normalization)
      med_row = db.conn.execute(
          "SELECT citation_count FROM papers WHERE year = ? AND citation_count > 0 "
          "ORDER BY citation_count LIMIT 1 OFFSET "
          "(SELECT COUNT(*)/2 FROM papers WHERE year = ? AND citation_count > 0)",
          (year, year),
      ).fetchone()
      median_cites = (med_row["citation_count"] if med_row else 1) or 1

      ranked: list[RankedPaper] = []
      for r in rows:
          venue_q = _venue_quality(db, r["venue"])
          if r["year"] == current_year:
              citation_term = venue_q
          else:
              citation_term = math.log1p(r["citation_count"] or 0) / math.log1p(median_cites)
          recency = math.exp(-(current_year - (r["year"] or current_year)) / 3.0)
          ranked.append(RankedPaper(
              paper_id=r["id"], score=citation_term * venue_q * recency,
              citation_term=citation_term, venue_q=venue_q, recency=recency,
          ))
      ranked.sort(key=lambda x: x.score, reverse=True)
      if target is not None:
          ranked = ranked[:target]
      return ranked
  ```
- **Register** in `packages/research_harness/research_harness/primitives/registry.py`:
  - Add a spec entry describing the primitive. Use an existing spec as template (e.g. `paper_search` spec around line 57).
  - Spec keys: `name="head_paper_rank"`, `inputs={"year": "int", "paper_ids": "list[int]", "target": "int"}`, `outputs={"ranked": "list[RankedPaper]"}`, `tier="n/a"` (non-LLM).
- **Dispatch**: in `packages/research_harness/research_harness/execution/harness.py`, add `head_paper_rank` to the **non-LLM** dispatch path. If only `_LLM_DISPATCH` exists, add a separate `_DETERMINISTIC_DISPATCH` dict and update the `dispatch()` method to check both.
- **Test**: `packages/research_harness/tests/test_head_paper_rank.py` with 5 synthetic papers, assert correct ordering.
- **Exit criterion**: test passes; primitive visible via `rh primitive list` (if that CLI exists) or importable.

### Task 1.8 — Add `cs_harvest` primitive

- **Create file**: `packages/research_harness/research_harness/primitives/cs_harvest.py`
  ```python
  """CS yearly paper harvest — topicless ingest."""
  from __future__ import annotations
  from dataclasses import dataclass
  from typing import Any
  from ..paper_sources import SearchQuery, SearchAggregator
  from ..storage.db import Database
  from .head_paper import head_paper_rank
  from .impls import paper_ingest

  CS_CATEGORIES = [
      "cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.IR", "cs.RO",
      "cs.CR", "cs.DB", "cs.DC", "cs.DS", "cs.HC", "cs.PL",
      "cs.SE", "cs.SY",
  ]
  SEED_QUERIES = [
      "machine learning",
      "deep learning",
      "neural network",
      "transformer",
      "large language model",
  ]

  @dataclass
  class HarvestResult:
      ingested: int
      discovered: int
      categories_covered: list[str]

  def cs_harvest(
      *, db: Database, year: int, target: int = 1000,
      per_provider_limit: int = 200, **_: Any,
  ) -> HarvestResult:
      agg = SearchAggregator()  # default providers from config
      all_records = []
      for cat in CS_CATEGORIES:
          for q in SEED_QUERIES:
              sq = SearchQuery(
                  query=q, subject_categories=[cat],
                  year_from=year, year_to=year,
                  per_provider_limit=per_provider_limit,
              )
              res = agg.search(sq)
              all_records.extend(res.papers if hasattr(res, 'papers') else res)

      # Dedupe by existing SearchAggregator logic OR by fingerprint
      seen = {}
      for p in all_records:
          fp = p.doi or p.arxiv_id or (p.title or "").lower().strip()
          if fp and fp not in seen:
              seen[fp] = p
      deduped = list(seen.values())

      # Ingest all with topic_id=None
      ingested_ids: list[int] = []
      for p in deduped:
          result = paper_ingest(db=db, source=p, topic_id=None)
          if result and result.get("paper_id"):
              ingested_ids.append(result["paper_id"])

      # Rank and trim to target
      if len(ingested_ids) > target:
          ranked = head_paper_rank(db=db, year=year, paper_ids=ingested_ids,
                                   current_year=year, target=target)
          keep_ids = {r.paper_id for r in ranked}
          # Soft-delete non-top: mark status='filtered' (do NOT hard delete)
          for pid in set(ingested_ids) - keep_ids:
              db.conn.execute(
                  "UPDATE papers SET pool_status = 'filtered_low_rank' WHERE id = ?",
                  (pid,),
              )
          db.conn.commit()
          ingested_count = target
      else:
          ingested_count = len(ingested_ids)

      return HarvestResult(
          ingested=ingested_count, discovered=len(deduped),
          categories_covered=CS_CATEGORIES,
      )
  ```
  **Note**: If `papers.pool_status` column doesn't exist, use the status column that does (check migration 001 or run `sqlite3 .research-harness/pool.db ".schema papers"`). If no status column, skip the soft-delete and just return the ranked ids; Phase 2 will only tag the top-N.

- **Register + dispatch** as in Task 1.7.
- **Test**: `packages/research_harness/tests/test_cs_harvest.py` — mock SearchAggregator, assert 15 categories × 5 queries = 75 search calls, assert topic_id=None on all ingests.
- **Exit criterion**: mocked test passes; live run (smoke): `python -c "from research_harness.primitives.cs_harvest import cs_harvest; from research_harness.storage.db import Database; r = cs_harvest(db=Database(), year=2024, target=10, per_provider_limit=5); print(r)"` succeeds.

### Task 1.9 — CLI wiring for `rh cs harvest`

- **File**: `packages/research_harness/research_harness/cli.py`
- **Action**: add subcommand group `cs` with subcommand `harvest` that accepts `--year <int>` and `--target <int>` (default 1000). Use the existing CLI pattern (look at how `topic init` is wired around `cli.py:583`).
- **Test**:
  ```bash
  rh cs harvest --year 2024 --target 20 --per-provider-limit 5
  ```
- **Exit criterion**: command exits 0 and prints `HarvestResult(ingested=..., discovered=...)`.

### Phase 1 exit criteria

- [ ] `rh cs harvest --year 2024 --target 100` completes in <30 min, ingests ≥100 papers
- [ ] Sample paper via `rh paper show <id>` shows `year=2024` and a CS venue
- [ ] `SELECT COUNT(*) FROM papers WHERE year=2024` = ~100 in pool.db
- [ ] `pytest packages/ -q --tb=short` all green

---

## Phase 2 — Classification + Red-Ocean

**Prerequisite**: Phase 0 results committed. Phase 1 complete.

### Task 2.1 — Migration 045 (cs_classification)

- **Create file**: `packages/research_harness/migrations/045_cs_classification.sql`
- **Content** (copy verbatim from `CS_RESEARCH_WORKFLOW_V2.md` §2/D5):
  ```sql
  CREATE TABLE research_areas (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
      name TEXT NOT NULL,
      slug TEXT NOT NULL,
      description TEXT DEFAULT '',
      source TEXT NOT NULL DEFAULT 'cso',
      red_ocean_score REAL DEFAULT NULL,
      red_ocean_breakdown TEXT DEFAULT '{}',
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now')),
      UNIQUE(domain_id, slug)
  );

  CREATE TABLE paper_research_areas (
      paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
      research_area_id INTEGER NOT NULL REFERENCES research_areas(id) ON DELETE CASCADE,
      is_primary INTEGER DEFAULT 0,
      match_type TEXT NOT NULL DEFAULT 'enhanced',
      PRIMARY KEY (paper_id, research_area_id)
  );

  CREATE TABLE paper_domains (
      paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
      domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
      is_primary INTEGER DEFAULT 0,
      PRIMARY KEY (paper_id, domain_id)
  );

  CREATE INDEX IF NOT EXISTS idx_paper_research_areas_paper
      ON paper_research_areas(paper_id);
  CREATE INDEX IF NOT EXISTS idx_paper_research_areas_area
      ON paper_research_areas(research_area_id);
  CREATE INDEX IF NOT EXISTS idx_research_areas_domain
      ON research_areas(domain_id);
  ```
- **Test**: `rh migrate` (or whatever the migration-runner command is; check `cli.py`). Expected: migration applies cleanly; the 3 tables exist.
- **Exit criterion**: `sqlite3 .research-harness/pool.db ".tables"` lists `research_areas`, `paper_research_areas`, `paper_domains`.

### Task 2.2 — Seed 15 CS domains

- **File**: `packages/research_harness/research_harness/cli.py`
- **Action**: add command `rh domain seed cs` that inserts/updates 15 rows into `domains`:
  ```python
  CS_DOMAIN_SEED = [
      ("cs.AI",  "Artificial Intelligence"),
      ("cs.LG",  "Machine Learning"),
      ("cs.CV",  "Computer Vision"),
      ("cs.CL",  "Computation and Language / NLP"),
      ("cs.IR",  "Information Retrieval"),
      ("cs.RO",  "Robotics"),
      ("cs.CR",  "Cryptography and Security"),
      ("cs.DB",  "Databases"),
      ("cs.DC",  "Distributed Computing"),
      ("cs.DS",  "Data Structures and Algorithms"),
      ("cs.HC",  "Human-Computer Interaction"),
      ("cs.PL",  "Programming Languages"),
      ("cs.SE",  "Software Engineering"),
      ("cs.SY",  "Systems and Control"),
      ("cs.OTHER", "Other Computer Science"),
  ]
  # INSERT OR IGNORE into domains(name, description)
  ```
- **Test**: `rh domain seed cs` then `rh domain list` shows 15 rows.
- **Exit criterion**: `SELECT COUNT(*) FROM domains WHERE name LIKE 'cs.%'` = 15.

### Task 2.3 — `cso_classify` primitive

- **Create file**: `packages/research_harness/research_harness/primitives/cso.py`
  ```python
  """CSO Classifier wrapper — deterministic research_area assignment."""
  from __future__ import annotations
  from dataclasses import dataclass, field
  from typing import Any
  from ..storage.db import Database

  GENERIC_BLOCKLIST = {
      "computer science", "artificial intelligence",
      "machine learning", "deep learning", "algorithms",
      "mathematics", "engineering",
  }

  @dataclass
  class CSOResult:
      paper_id: int
      syntactic: list[str] = field(default_factory=list)
      semantic: list[str] = field(default_factory=list)
      union: list[str] = field(default_factory=list)
      enhanced: list[str] = field(default_factory=list)

  def _slugify(s: str) -> str:
      return "-".join(s.lower().split()).strip("-") or "unknown"

  def cso_classify(
      *, db: Database, paper_ids: list[int], domain_id: int | None = None, **_: Any,
  ) -> list[CSOResult]:
      """Classify papers via CSO; write to paper_research_areas.
      If domain_id is None, infer from paper's primary arxiv category.
      """
      from cso_classifier.classifier import CSOClassifier

      rows = db.conn.execute(
          f"SELECT id, title, abstract FROM papers WHERE id IN ({','.join('?'*len(paper_ids))})",
          paper_ids,
      ).fetchall()
      batch = {
          str(r["id"]): {
              "title": r["title"] or "",
              "abstract": r["abstract"] or "",
              "keywords": "",
          }
          for r in rows
      }

      cc = CSOClassifier(modules="both", enhancement="first",
                         explanation=False, get_weights=False)
      raw = cc.batch_run(batch)

      results: list[CSOResult] = []
      for pid_str, r in raw.items():
          pid = int(pid_str)
          enhanced = [t for t in r.get("enhanced", []) if t.lower() not in GENERIC_BLOCKLIST]

          # Resolve or infer domain_id for this paper
          paper_domain_id = domain_id or _infer_domain_id(db, pid)
          if not paper_domain_id:
              continue

          # Upsert research_areas; link via paper_research_areas
          for i, topic in enumerate(enhanced[:5]):  # cap 5 areas per paper
              slug = _slugify(topic)
              db.conn.execute(
                  "INSERT OR IGNORE INTO research_areas(domain_id, name, slug, source) "
                  "VALUES (?, ?, ?, 'cso')",
                  (paper_domain_id, topic, slug),
              )
              area_row = db.conn.execute(
                  "SELECT id FROM research_areas WHERE domain_id=? AND slug=?",
                  (paper_domain_id, slug),
              ).fetchone()
              db.conn.execute(
                  "INSERT OR IGNORE INTO paper_research_areas"
                  "(paper_id, research_area_id, is_primary, match_type) "
                  "VALUES (?, ?, ?, 'enhanced')",
                  (pid, area_row["id"], 1 if i == 0 else 0),
              )
          db.conn.commit()
          results.append(CSOResult(
              paper_id=pid, syntactic=r.get("syntactic", []),
              semantic=r.get("semantic", []), union=r.get("union", []),
              enhanced=enhanced,
          ))
      return results

  def _infer_domain_id(db: Database, paper_id: int) -> int | None:
      """Infer primary CS domain from arxiv_id or metadata."""
      row = db.conn.execute(
          "SELECT arxiv_id FROM papers WHERE id = ?", (paper_id,)
      ).fetchone()
      # arxiv_id format: "2401.12345" — no category. Check if papers has
      # a `categories` column (added by ArxivProvider). If not, return cs.OTHER.
      # TODO: once ArxivProvider persists categories to DB, use them.
      fallback = db.conn.execute(
          "SELECT id FROM domains WHERE name = 'cs.OTHER' LIMIT 1"
      ).fetchone()
      return fallback["id"] if fallback else None
  ```
- **Register + dispatch** (see Task 1.7 pattern).
- **Test**: unit test mocking `CSOClassifier.batch_run` to return fixed output; verify correct DB writes.
- **Exit criterion**: test passes; smoke test on 5 real papers inserts rows into `research_areas` and `paper_research_areas`.

### Task 2.4 — `area_drift_patch` primitive

- **File**: same as 2.3 or new `packages/research_harness/research_harness/primitives/area_drift.py`
- **Trigger condition**: called when `cso_classify` result for a paper has fewer than 2 `enhanced` terms after blocklist filter.
- **Logic**:
  ```python
  def area_drift_patch(*, db, paper_id, domain_id, **_):
      """LLM call: propose a research_area name for this paper,
      preferring an existing domain area if appropriate."""
      from llm_router.client import resolve_llm_config
      from ..storage.db import Database

      row = db.conn.execute(
          "SELECT title, abstract FROM papers WHERE id = ?", (paper_id,)
      ).fetchone()
      existing = db.conn.execute(
          "SELECT name FROM research_areas WHERE domain_id = ? ORDER BY name LIMIT 50",
          (domain_id,),
      ).fetchall()
      existing_names = [r["name"] for r in existing]

      cfg = resolve_llm_config(tier="light")
      prompt = _drift_prompt(row["title"], row["abstract"], existing_names)
      # call cfg.client.complete(prompt) - follow existing pattern in llm_primitives.py
      # ... (get response, parse JSON)
      # Expected JSON: {"area_name": str, "is_existing": bool, "confidence": float}
      ...
  ```
- **Wire this into `cso_classify`**: after CSO run, for papers with <2 enhanced terms, trigger `area_drift_patch`.
- **Test**: mock LLM response, verify `research_areas.source = 'llm_drift_patch'` row inserted.
- **Exit criterion**: integration test where a paper with empty abstract goes through drift-patch path.

### Task 2.5 — Migration 046 (task_canonical)

- **Create file**: `packages/research_harness/migrations/046_task_canonicalization.sql`
  ```sql
  ALTER TABLE normalized_claims ADD COLUMN task_canonical TEXT;
  CREATE INDEX idx_normalized_claims_task_canonical
      ON normalized_claims(task_canonical);
  ```
- **Test**: `rh migrate`; check `sqlite3 .research-harness/pool.db "PRAGMA table_info(normalized_claims)"` lists `task_canonical`.
- **Exit criterion**: column exists.

### Task 2.6 — `task_canonicalize` primitive

- **Create file**: `packages/research_harness/research_harness/execution/llm_primitives.py` — add function `task_canonicalize`.
- **Prompt**: extend `packages/research_harness/research_harness/execution/prompts.py` with a new function `task_canonicalize_prompt(task_names: list[str])` that returns:
  > "Given these task names, group near-duplicates and output a canonical label per group. Preserve real distinctions (e.g. 'sentiment classification' vs 'stance detection' are different). Output JSON: [{canonical: str, members: [str]}, ...]"
- **Execution**:
  1. Query `SELECT DISTINCT task FROM normalized_claims WHERE task_canonical IS NULL AND task != ''` within scope (optional domain filter via join)
  2. Call Sonnet-tier LLM
  3. For each group: `UPDATE normalized_claims SET task_canonical = ? WHERE task IN (...)`
- **Register + dispatch**.
- **Test**: mock LLM response; assert correct DB updates.
- **Exit criterion**: `SELECT task, task_canonical FROM normalized_claims LIMIT 10` shows populated `task_canonical`.

### Task 2.7 — Per-dimension red-ocean computation

- **Create file**: `packages/research_harness/research_harness/primitives/red_ocean.py`
  ```python
  """Deterministic red-ocean scoring per dimension."""
  from __future__ import annotations
  import json
  import math
  from typing import Any
  from ..storage.db import Database

  def compute_area_red_ocean(*, db: Database, research_area_id: int, **_) -> float:
      """See CS_RESEARCH_WORKFLOW_V2.md §3/D9 — area formula."""
      # 1. volume_pressure
      # 2. method_convergence
      # 3. lab_concentration
      # 4. gap_density_cap (NEGATIVE weight)
      # Return clipped score; also write to research_areas.red_ocean_score + breakdown
      ...

  def compute_task_red_ocean(*, db: Database, task_canonical: str,
                             domain_id: int, **_) -> float: ...

  def compute_method_red_ocean(*, db: Database, method: str,
                               research_area_id: int, **_) -> float: ...
  ```
- **Implementation rules**:
  - `volume_pressure = math.tanh(math.log2(papers_last_2y / max(median_peer, 1)))` — clip to [0, 1] by `(x+1)/2`
  - `method_convergence = sum(top-3 method counts) / total_method_entries` in the scope
  - `lab_concentration = HHI = sum(share_i²)` for top-10 affiliations
  - `gap_density = min(0.2, verified_open_gaps / max(papers, 1))` — require `confidence ≥ 0.5 OR cross_verified=1`
  - Final: `clip(0, 1, 0.30 × vp + 0.30 × mc + 0.25 × lc − 0.15 × gdc)`
- **Persist**: write `red_ocean_score` + `red_ocean_breakdown` JSON to `research_areas` row.
- **Register** as deterministic primitive(s). No LLM.
- **Test**: synthetic data — 10 papers, some high-overlap methods, known HHI — assert computed value matches hand-calc within ±0.01.
- **Exit criterion**: unit tests pass.

### Task 2.8 — Wire up area classification into `cs_harvest`

- **File**: `packages/research_harness/research_harness/primitives/cs_harvest.py` (from Task 1.8)
- **Change**: after ingesting and ranking, call `cso_classify` on the kept papers:
  ```python
  from .cso import cso_classify
  cso_classify(db=db, paper_ids=list(keep_ids))
  ```
- **Then** run red-ocean computation for all affected `research_areas`.
- **Test**: end-to-end: `rh cs harvest --year 2024 --target 20` → assert each paper has ≥1 row in `paper_research_areas`.
- **Exit criterion**: all retained papers have research_area assignments.

### Phase 2 exit criteria

- [ ] 100 harvested papers → 15 domains seeded → ≥30 distinct research_areas (CSO-derived)
- [ ] `SELECT COUNT(*) FROM paper_research_areas` > 100 (multi-label)
- [ ] `research_areas.red_ocean_score` populated for all areas with ≥5 papers
- [ ] `normalized_claims.task_canonical` populated for all claims after running `rh claim canonicalize`
- [ ] All tests pass

---

## Phase 3 — Recommendation Engine

**Prerequisite**: Phase 2 complete.

### Task 3.1 — Update `RECOMMENDATION_ENGINE.md`

- **File**: `docs/architecture/RECOMMENDATION_ENGINE.md`
- **Action**: The SUPERSEDED banner is already at the top. Now align §4c (scoring) text with LLM scoring decision. Either:
  - Option A: rewrite §4c to say "scores come from `direction_ranking` LLM primitive; deterministic structural atoms (lineage_key, evidence_signature) retained"
  - Option B: move the existing doc to `docs/architecture/archive/RECOMMENDATION_ENGINE_v0.4_deterministic.md` and leave only the banner + a link in the current location
- **Pick Option A** unless directed otherwise.
- **Exit criterion**: doc renders; no conflict with CS_RESEARCH_WORKFLOW_V2.md.

### Task 3.2 — Migration 048 (research_candidates)

- **Create file**: `packages/research_harness/migrations/048_research_candidates.sql`
- **Content**: copy verbatim from `CS_RESEARCH_WORKFLOW_V2.md` §4/D11 (consolidated schema with 3 red_ocean columns + opportunity_angle).
- **Test**: `rh migrate`; `sqlite3 .research-harness/pool.db ".schema research_candidates"` matches.
- **Exit criterion**: table + index exist.

### Task 3.3 — Candidate seeding logic

- **Create file**: `packages/research_harness/research_harness/primitives/candidate_seed.py`
- **Logic** (deterministic, no LLM):
  ```python
  def seed_candidates(*, db, scope: str, **_) -> list[CandidateDraft]:
      """scope format: 'domain:N' | 'research_area:N' | 'topic:N'
      Returns list of CandidateDraft (pre-LLM scoring).
      See CS_RESEARCH_WORKFLOW_V2.md design for Pass 1/2/3 rules;
      BUT in r3 we use LLM for scoring, so seeding just groups evidence."""
      # Pass 1: gap-driven — each high/medium severity gap in scope
      # Pass 2: contradiction-driven — each candidate contradiction in scope
      # Pass 3: (deferred to v0.4.2 per design) method-transfer — skip in MVP
      # Return merged list with lineage_key + evidence_signature
  ```
- **Use**: `sha1(primary_signal_family + normalize(gap.description))` for lineage_key (follow design doc §4a).
- **Test**: synthetic gaps/contradictions → expected candidates emitted.
- **Exit criterion**: test passes.

### Task 3.4 — Extend `direction_ranking` prompt

- **File**: `packages/research_harness/research_harness/execution/prompts.py`
- **Locate**: `direction_ranking_prompt` function (~line 1246)
- **Change**: add new prompt inputs to signature:
  ```python
  def direction_ranking_prompt(
      gaps_text, claims_text, summary,
      area_red_ocean: float = 0.0,
      task_red_ocean: float = 0.0,
      method_red_ocean: float = 0.0,
      research_area_name: str = "",
      primary_task: str = "",
      primary_method: str = "",
      opportunity_angle: str = "",
  ) -> str:
  ```
- **In the prompt body**, add a "Context" section showing the 3 red_ocean values, the area/task/method names, and the opportunity_angle. Instruct the LLM to reference opportunity_angle in its reasoning but NOT to produce red_ocean scores itself.
- **File**: `packages/research_harness/research_harness/execution/llm_primitives.py`
- **Locate**: `direction_ranking` function (line 3389)
- **Change**: accept new optional params; pass through to prompt builder.
- **Test**: existing test updated to pass new params; verify prompt contains the new context block.
- **Exit criterion**: test passes.

### Task 3.5 — Compute `opportunity_angle` (deterministic)

- **File**: `packages/research_harness/research_harness/primitives/red_ocean.py`
- **Add function**:
  ```python
  def opportunity_angle(area_red: float, task_red: float,
                       method_red: float) -> str:
      task_is_red = task_red >= 0.7
      method_is_red = method_red >= 0.7
      area_is_red = area_red >= 0.7
      if not task_is_red and method_is_red:
          return "new_task_mature_method"
      if task_is_red and not method_is_red:
          return "novel_method_known_task"
      if not task_is_red and not method_is_red:
          return "frontier"
      return "red_ocean"
  ```
- **Test**: 4 cases covering the 4 outputs.
- **Exit criterion**: test passes.

### Task 3.6 — Persistence + UPSERT

- **Add to**: `packages/research_harness/research_harness/primitives/candidate_seed.py` or new `candidate_persist.py`
- **Logic**:
  ```python
  def upsert_candidate(db, scope: str, draft: CandidateDraft,
                      llm_score_result: dict, ro_scores: dict) -> int:
      # 1. Look up by (scope, lineage_key)
      # 2. If exists and evidence_signature unchanged → return id (no write)
      # 3. If exists and evidence_signature changed → UPDATE all fields
      #    BUT PRESERVE status column (user's triage state)
      # 4. If not exists → INSERT
      # Write: llm_score, llm_score_breakdown, area_red_ocean, task_red_ocean,
      #        method_red_ocean, opportunity_angle, and all evidence arrays
  ```
- **Test**: 3 scenarios — new, unchanged, evidence-updated.
- **Exit criterion**: tests pass.

### Task 3.7 — Promote to topic endpoint

- **File**: `packages/research_harness_mcp/research_harness_mcp/tools.py` — add MCP tool `candidate_promote(candidate_id)`.
- **Logic** (follow design doc §4/D14):
  1. Read `research_candidates` row
  2. `INSERT INTO topics(name, description, domain_id, contributions)` using candidate fields
  3. For each `seed_paper_id`: `INSERT OR IGNORE INTO paper_topics(paper_id, topic_id, relevance)`
  4. `INSERT INTO project_artifacts(project_id, topic_id, stage, artifact_type, title, payload_json)` with `artifact_type='topic_brief'`, `stage='init'`
  5. Import `orchestrator_init` handler from `cli.py` (Python import, not subprocess) and call it with the new topic_id
  6. `UPDATE research_candidates SET status='promoted' WHERE id=?`
- **Find orchestrator_init handler**: `grep -n "def.*orchestrator_init\|orchestrator_init_handler" packages/research_harness/research_harness/cli.py` to find exact symbol.
- **Test**: mock orchestrator_init call; assert all 5 steps executed.
- **Exit criterion**: integration test passes (creates a topic, links papers, creates artifact).

### Task 3.8 — Pipeline runner

- **Create file**: `packages/research_harness/research_harness/primitives/recommend.py`
- **Logic**:
  ```python
  def generate_recommendations(*, db, scope: str, **_) -> list[int]:
      """End-to-end: seed → score → persist. Returns candidate ids."""
      drafts = seed_candidates(db=db, scope=scope)
      results = []
      for d in drafts:
          # Compute red-ocean for candidate's primary area/task/method
          ro = compute_red_ocean_for_candidate(db, d)
          angle = opportunity_angle(**ro)
          # LLM score via direction_ranking
          llm_result = direction_ranking(
              db=db, scope=scope,
              area_red_ocean=ro["area"], task_red_ocean=ro["task"],
              method_red_ocean=ro["method"],
              opportunity_angle=angle,
              # ... + gaps, claims, summary as existing
          )
          cid = upsert_candidate(db, scope, d, llm_result, ro)
          results.append(cid)
      return results
  ```
- **MCP tool**: expose as `recommendations_generate(scope)`.
- **Test**: end-to-end on a topic with known gaps → ≥2 candidates.
- **Exit criterion**: end-to-end test passes.

### Phase 3 exit criteria

- [ ] `recommendations_generate(scope='topic:<id>')` produces ≥2 candidates with typed evidence
- [ ] Each candidate has: `llm_score`, 3 red_ocean scores, `opportunity_angle`
- [ ] `candidate_promote` creates a new topic; topic appears in `rh topic list`
- [ ] Dismiss via `PATCH status='dismissed'` persists across regeneration

---

## Phase 4 — Integration + QA

### Task 4.1 — Migration 047 (gap confidence)

- **Create file**: `packages/research_harness/migrations/047_gap_confidence.sql`
  ```sql
  ALTER TABLE gaps ADD COLUMN confidence REAL DEFAULT NULL;
  ALTER TABLE gaps ADD COLUMN cross_verified INTEGER DEFAULT 0;
  ALTER TABLE gaps ADD COLUMN cross_check_runs INTEGER DEFAULT 0;
  ```
- **Exit criterion**: columns exist.

### Task 4.2 — Extend `gap_detect` to emit confidence

- **File**: `packages/research_harness/research_harness/execution/prompts.py` — extend `gap_detect_prompt` to ask for `confidence: float (0-1)` per gap.
- **File**: `packages/research_harness/research_harness/execution/llm_primitives.py` — parse the new field; pass to insert.
- **SQL insert**: include `confidence`.
- **Test**: mock LLM → confidence persisted.
- **Exit criterion**: test passes.

### Task 4.3 — `gap_cross_verify` primitive

- **Create file**: `packages/research_harness/research_harness/primitives/gap_verify.py`
- **Logic**:
  ```python
  def gap_cross_verify(*, db, topic_id: int, sample_ratio: float = 0.2, **_):
      """Sample recent gaps; re-run gap_detect with different LLM;
      compute Jaccard; mark cross_verified when Jaccard ≥ 0.6."""
      # Use llm_router with tier="heavy" (Opus) for re-verification —
      # the original gap_detect uses "medium" by default.
  ```
- **Register + dispatch**.
- **Test**: mock two LLM calls with controlled overlap; assert cross_verified set correctly.
- **Exit criterion**: test passes.

### Task 4.4 — `experiment_handoff_prepare` MCP tool

- **File**: `packages/research_harness_mcp/research_harness_mcp/tools.py`
- **Follow** CS_RESEARCH_WORKFLOW_V2.md §5/D15 exactly. **Field names**: `artifact_type='experiment_brief'`, `stage='experiment'`, `payload_json=...`.
- **Before inserting**, look up `project_id` for the given `topic_id`:
  ```sql
  SELECT project_id FROM topics WHERE id = ?
  ```
  If `topics.project_id` doesn't exist (check schema), use `SELECT id FROM projects WHERE default_for_topic = ? ...` or similar. If no project machinery, create a default project. ASK USER if unclear.
- **Return**: `{artifact_id, paste_prompt}` where `paste_prompt` is a string the user copies into a new CC session.
- **Test**: integration test creates artifact, returns prompt.
- **Exit criterion**: test passes.

### Task 4.5 — `experiment_handoff_submit` MCP tool

- **File**: same as 4.4
- **Logic**: insert `artifact_type='experiment_result'`, `parent_artifact_id=<brief id>`, `stage='experiment'`.
- **Test**: round-trip with a brief+result pair.
- **Exit criterion**: test passes.

### Task 4.6 — `workflow_entry` MCP tool

- **File**: `packages/research_harness_mcp/research_harness_mcp/tools.py`
- **IMPORTANT**: this is a NEW tool — do NOT modify existing `orchestrator_resume`. Name it `workflow_entry`.
- **Signature**:
  ```python
  @mcp.tool()
  def workflow_entry(user_context: str, topic_id: int | None = None,
                     artifact_paths: list[str] | None = None,
                     keywords: list[str] | None = None) -> dict:
      """Classify user's current state; return suggested next primitives + stage.
      See CS_RESEARCH_WORKFLOW_V2.md §7/D17 routing table."""
  ```
- **Logic**: simple heuristic routing (no LLM):
  - `keywords only (no topic_id, no artifacts)` → stage=`init`, suggest `cs_harvest` + `domain_classify` + `research_area_extract` (or their r3 equivalents)
  - `topic_id + count(papers) > 0` → stage=`build` or `analyze`, suggest `claim_extract`, `gap_detect`
  - `topic_id + count(gaps) > 0 + no candidates` → stage=`propose`, suggest `recommendations_generate`
  - etc. per design doc routing table.
- **Return** a dict with `{stage, suggested_primitives, rationale}`.
- **Test**: table-driven with 5 input scenarios → expected stage.
- **Exit criterion**: tests pass.

### Phase 4 exit criteria

- [ ] `gap_cross_verify(topic_id=X)` marks ≥ 80% of recent gaps as `cross_check_runs ≥ 1`
- [ ] `experiment_handoff_prepare(topic_id=X)` returns paste-able prompt
- [ ] `workflow_entry(user_context="I have keywords", keywords=["X","Y"])` returns stage=`init`
- [ ] All tests pass

---

## Final end-to-end test

After all phases:

```bash
# 1. Harvest
rh cs harvest --year 2024 --target 200

# 2. Expect classification already ran
sqlite3 .research-harness/pool.db "SELECT COUNT(*) FROM research_areas"
# > 20

# 3. Pick a research_area, extract claims + gaps on its papers
# (may require wiring `rh research_area analyze <id>` or doing it via MCP)

# 4. Generate recommendations
rh recommendations generate --scope research_area:1

# 5. Inspect
sqlite3 .research-harness/pool.db "SELECT id, title, llm_score, opportunity_angle FROM research_candidates"

# 6. Promote top candidate
rh candidate promote --id <top_id>

# 7. Verify topic created
rh topic list

# 8. Trigger experiment handoff
rh topic experiment-handoff --topic-id <new_topic_id>
# prints paste_prompt
```

**All 8 steps exit 0** = project delivered.

---

## Appendix A — Common pitfalls

1. **Migration numbering**: always `ls packages/research_harness/migrations/` first. Do not guess.
2. **Primitive dispatch**: easy to forget. Symptom: `KeyError: 'your_primitive'` at runtime. Fix: add to `_LLM_DISPATCH` (if LLM) or `_DETERMINISTIC_DISPATCH`.
3. **MCP tool not exposed**: decorator missing. Symptom: tool doesn't show up in `/mcp` list.
4. **Python version**: if user on 3.10, CSO install fails. STOP — don't try to work around.
5. **LLM tier**: follow existing pattern in `llm_primitives.py`. Don't hardcode model IDs.
6. **`topic_id = None` ingest**: verified works. Do NOT pass 0 or negative — use `None`.
7. **CSO batch_run returns STRING keys**: must convert back to `int(pid)` before DB writes.

## Appendix B — Rollback

Each phase creates isolated migrations + files. To roll back:
- Revert commit(s) of the phase
- `sqlite3 .research-harness/pool.db` — manually `DROP TABLE` for the created tables (check `migrations_log` table first for cleaner rollback if present)
- No data-lossy rollbacks in Phases 1-3 (harvested papers can stay; research_area assignments are additive)

## Appendix C — When to ask the user

**Ask before proceeding if**:
- A test fails after 2 fix attempts
- A file path referenced in this manual doesn't exist
- A migration conflict arises (another number was used since this doc was written)
- CSO_MODE detected as `llm_fallback` in Phase 0 — requires user confirmation to proceed with LLM-primary path
- `project_artifacts.project_id` semantics unclear (Task 4.4)

Ask via: comment in a commit message + stop work + surface in final report.
