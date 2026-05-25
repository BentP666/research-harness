# Backend Stability Test Suite

Backend-only stability tests for the research-harness pipeline.
Lives at `packages/research_harness/tests/backend_stability/`.

## What this is

A self-contained test subtree that verifies the **state machine**, **fault
tolerance**, and **regression coverage** of the orchestrator without
requiring a live LLM, real network, or any frontend.

Three tiers, selected via `--tier`:

| Tier        | Wall-time   | Use                       | LLM         | Network |
|-------------|-------------|---------------------------|-------------|---------|
| `smoke`     | < 5 s       | pre-commit hook           | replay only | none    |
| `pre_merge` | < 15 s      | CI gate before merge      | replay only | none    |
| `nightly`   | minutes     | full E2E + open-bug guard | replay+real | none    |

Default tier is `smoke`. Override with `--tier=pre_merge` or `--tier=nightly`,
or set `RH_TEST_TIER` env var.

## Layout

```
backend_stability/
├── conftest.py             # tier filtering + LLM replay session fixture
├── README.md               # this file
├── assertions/
│   └── boolean_suite.py    # 10 go/no-go orchestrator-state checks
├── fixtures/
│   ├── topics/*.json       # 3 topic specs (smoke/pre_merge/nightly)
│   ├── papers/*.json       # 15 paper fixtures (5 per topic)
│   └── loader.py           # offline DB-direct ingest
├── injectors/
│   ├── llm.py              # 7 pathological LLM injectors (rate_limit, refusal, ...)
│   ├── storage.py          # corrupt_paper_row, sqlite_writer_lock, drop_index
│   ├── filesystem.py       # readonly_path, disk_full_on_write, missing_pdf
│   ├── network.py          # network_outage, http_5xx, http_timeout,
│   │                       # FailingProvider, RateLimitedProvider, fake_provider_suite
│   └── fake_proxy.py       # in-process Anthropic-compatible mock server
├── replay/
│   └── recorder.py         # llm_router replay hook (record/replay/auto)
├── regressions/
│   └── test_p0_p1_history.py    # 20 historical P0/P1 bugs guarded
└── scenarios/
    ├── test_smoke_*.py     # injector + fixture self-tests
    ├── test_e2e_chains.py  # 2 main chains + 1 negative guard
    └── test_resilience.py  # checkpoint, multi-session, full nightly chain
```

## How to run

```bash
# pre-commit: fastest tier
pytest packages/research_harness/tests/backend_stability --tier smoke

# CI gate
pytest packages/research_harness/tests/backend_stability --tier pre_merge

# nightly full pass
pytest packages/research_harness/tests/backend_stability --tier nightly

# replay mode override (for explicit cache control)
pytest ... --replay-mode=record    # hits real LLMs, appends to cache
pytest ... --replay-mode=replay    # cache-only, miss = fail (default)
pytest ... --replay-mode=auto      # cache-only, miss = stub response
```

## The 10 boolean assertions

`assertions/boolean_suite.py` exposes 10 deterministic checks. Each takes
`(Database, topic_id)` and returns `AssertionResult(passed, detail, evidence)`.

1. `assert_terminal_state` — run.stage_status reached a terminal value
2. `assert_transition_legal` — every recorded stage event is in `STAGE_GRAPH`
3. `assert_artifacts_present_and_valid` — required_artifacts exist with payloads
4. `assert_provenance_complete` — critical artifacts link to provenance rows
5. `assert_paper_count_conserved` — `searched == ingested + skipped + failed`
6. `assert_gate_has_reason` — every gate event carries a rationale
7. `assert_budget_tracked` — `provenance_records.cost_usd` is finite + reported
8. `assert_citations_no_dangling` — every `\cite{key}` resolves in BibTeX
9. `assert_llm_route_audited` — every LLM call records a real `model_used`
10. `assert_no_unexplained_traceback` — failed calls all carry a non-empty error

`assert_full_pipeline_ok(db, topic_id, tier="smoke"|"full")` runs the
appropriate subset and returns `(overall_passed, [results...])`.

## Design principles

- **Offline first.** Default mode never touches the network. The `nightly`
  tier may flip on real LLM calls when explicitly enabled.
- **Tests own their fault.** Each scenario explicitly opts into one fault
  via a context-manager injector — no global mutable state.
- **Negative guards.** For each non-trivial assertion, scenarios exist that
  *deliberately* break the precondition and verify the assertion fires.
  This proves the suite catches what it claims to catch.
- **Regression on every P0/P1.** Every documented historical bug in
  historical P0/P1 bugs have named test slots in `regressions/`. New bugs
  get a new test before the fix lands.

## Known schema-level findings surfaced by the suite

Both were found by this suite and **fixed in this branch**:

- **2026-05-07** `papers.s2_id DEFAULT '' UNIQUE` silently dropped rows when
  multiple papers lacked an s2_id (empty strings collided on UNIQUE).
  Migration `064_paper_identifiers_nullable.sql` recreates the table with
  doi/arxiv_id/s2_id as nullable UNIQUE so NULLs coexist per standard SQL
  semantics. Guard: `test_papers_identifier_columns_allow_multiple_nulls`.
- **#27 deep_read short-circuit** returned `model_used="none"` for
  abstract-only papers, making LLM-route auditing ambiguous. Fix in
  `execution/llm_primitives.py`: short-circuit now records
  `model_used="local:abstract_only"`. Guard:
  `test_deep_read_records_real_model_used`.

## Live-LLM full-chain (nightly)

`test_nightly_full_chain_live_llm` drives `auto_runner.run_topic()`
against the replay-cache hook + FakeProxyMock under dry_run, proving
the runner's config/DB/checkpoint plumbing holds together under the
replay harness without escaping to real network calls.
