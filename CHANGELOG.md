# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_No unreleased changes._

## [0.3.0] — 2026-05-09

### Added — CS Research Workflow v2 (Phases 3–4)

End-to-end recommendation + experiment-handoff pipeline for the
CS-paper-first workflow. Complements Phases 0–2 (CSO validation, bulk
harvest, classification + red-ocean) already shipped under
`feat(cs-workflow)` commits.

- **Migration 048 — `research_candidates`** table with multi-dimensional
  red-ocean columns, `opportunity_angle`, `lineage_key` (sha1 of signal
  family + normalized pitch, stable across re-seeding), and
  `evidence_signature` (sha1 of sorted evidence IDs, triggers re-score).
  Two-lane sort index keeps non-red-ocean candidates above red-ocean
  ones even when the latter has a higher LLM score.
- **`candidate_seed` primitive** — seeds drafts from `gaps`
  (≥ `min_gap_severity`) and `contradictions` within a `topic:N` scope.
- **`candidate_upsert` primitive** — preserves user status
  (dismissed/promoted) across evidence-triggered updates.
- **`opportunity_angle()`** classifies (area_red, task_red, method_red)
  into `{new_task_mature_method, novel_method_known_task, frontier,
  red_ocean}` using `RED_THRESHOLD=0.7`.
- **`recommendations_generate`** pipeline — seeds → compute triplet →
  optional LLM score (degrades to 0.0 on failure) → upsert. Optional
  `skip_llm_scoring=True` for deterministic unit tests.
- **Migration 047 — `gaps.confidence`, `gaps.cross_verified`,
  `gaps.cross_check_runs`**. `gap_detect` prompt + parser emit per-gap
  confidence 0-1.
- **`gap_cross_verify` primitive** — re-runs gap_detect pinned to a
  different LLM tier (default `heavy`) and marks originals verified
  when Jaccard over content words ≥ `min_jaccard` (default 0.6).
  Cross-verified flag is sticky.
- **`direction_ranking` saturation-aware** — new optional kwargs
  (`area/task/method_red_ocean`, `opportunity_angle`) grow the prompt
  with red-ocean scoring guidance; baseline prompt unchanged when
  kwargs omitted.
- **MCP `experiment_handoff_prepare`** — packages a research_candidate
  into an `experiment_brief` artifact on the experiment stage;
  dereferences evidence IDs into full rows and validates
  `candidate.scope` matches the caller's `topic_id`.
- **MCP `experiment_handoff_submit`** — records an `experiment_handoff`
  artifact linked via `consumed_by` dependency, flips the originating
  candidate's status to `promoted`.
- **MCP `workflow_entry`** — single-call status + ranked
  `next_actions` list (gap_detect → cross_verify →
  recommendations_generate → experiment_handoff_prepare →
  orchestrator_advance) so agents can resume any topic without
  threading multiple tool calls.

### Fixed — Calibration, rollback mode, and web polish

Release stabilization: tightens three spec deviations found during the v0.3.0 audit and moves three CLI-only actions into the web UI.

### Fixed

- **Publishability formula restored to weighted product with ε-floor** (spec
  §15 Q7). `compute_publishability` in `trends/pipeline.py` was shipping as
  a weighted sum, which let one strong factor mask a dead one. Now:
  `max(ε, v) · max(ε, c) · max(ε, q) · 10`, ε = 0.1.
- **Auto-rollback default flipped back to shadow mode** (spec §7.3). v0.3.0
  shipped with `RUBRIC_AUTO_ROLLBACK=true` as the default against uncalibrated
  thresholds. The new default is `false` (shadow mode) until calibration runs.
- **Calibration anchor corpus now ships**. 60-entry seed corpus at
  `research_harness/calibration/anchors.jsonl` covers all 6 stages with
  labeled accept/reject rows. `rh calibrate run` and `rh calibrate all` now
  actually execute Youden's J on the anchors instead of writing the default.

### Added

- **`research_harness.calibration` package.** Anchor loader, Youden's J
  threshold selection, and a runner that writes to `rubric_calibrations`.
- **Web UI: `/admin/calibration`.** Threshold table per (stage × tier),
  per-row "Recalibrate" button, "Recalibrate all" button, and a
  shadow/live toggle. No CLI needed.
- **Web UI: trends "Refresh" button.** On both the dashboard carousel and
  the trends explorer. Empty states offer a "Generate trends" call to
  action instead of a CLI hint.
- **`POST /api/domains/trends/refresh`** — run the trends pipeline.
- **`GET /api/calibrations` + `POST /api/calibrations/run`** — list + trigger
  rubric calibrations.
- **`user_preferences.auto_rollback_live`** (migration 041) — shadow/live
  mode toggled from the UI at runtime, no env-var edit required.
- **`rh calibrate all` + `rh calibrate list`** — batch-calibrate every
  (stage × tier) pair, inspect current state.

### Changed

- Judge engine resolves shadow/live mode at call time, checking (1) DB
  preference, (2) env var, (3) default. Module-level `SHADOW_MODE` kept
  as a back-compat alias but no longer the source of truth.
- Judge engine reads per-stage thresholds from `rubric_calibrations` when
  present, falling back to venue-tier defaults only when no calibration
  row exists.

### Added — Agent platform, budgets, judge, and trends

- **Agent registry + onboarding wizard (S2a).** Multi-agent management with
  provider configuration, agent pairings (generator/judge/challenger), preset
  gallery, and demo mode for offline exploration.
- **Token ledger + budgets (S2b).** Per-agent token usage tracking with monthly
  budget caps, hard-stop enforcement, and live cost counters in the web UI.
- **Venue ranks + quality tiers (S3).** CCF/CAS venue ranking database with seed
  data for 80+ venues. Three-tier quality system (economy/standard/premium) with
  per-topic autonomy levels (supervised/semi/autonomous).
- **Stage snapshots + rollback (S4pre).** Artifact snapshots on stage transitions
  with staleness propagation. One-click rollback from the web UI with reason
  logging and rollback history.
- **Rubric scoring + judge engine (S4).** Per-stage rubric definitions across 3
  tiers (economy 3 dims, standard 7, premium 10+). Weighted scoring with venue-
  tier thresholds, dual-judge routing for premium, and calibration CLI.
- **Domain suggest + topic candidates (S5).** AI-assisted domain creation from a
  research idea. Async job infrastructure for topic candidate generation with
  polling and batch creation.
- **Trends pipeline (S6).** Research trend clustering with publishability scoring
  (velocity × citations × venue quality). 12-entry seed dataset for AI/ML
  research directions. Dashboard carousel and full explorer page.

### Changed

- **Auto-rollback enabled by default.** `RUBRIC_AUTO_ROLLBACK` now defaults to
  `true`. Shadow mode (observation without enforcement) can be restored by
  setting `RUBRIC_AUTO_ROLLBACK=false`. (Folded into 0.3.0 — see stabilization notes above.)

### Infrastructure

- 7 new SQLite migrations (039–045).
- ~150 new tests across rubric scoring, judge engine, snapshots, claims,
  domains, and trends modules.
- Web dashboard expanded: agent management, budget controls, rubric scorecards,
  rollback UI, trend explorer, domain from-idea wizard.

## [0.2.0] — 2026-04-22

### Added

- **HTTP API + Web dashboard.** FastAPI-backed service exposing orchestrator
  state, topics/domains, papers, and artifacts with a React dashboard for
  navigation. Concurrent paper-search across configured providers.
- **Orchestrator stage gating.** Hardened gate mechanism — stages cannot
  advance until their typed evidence artifacts are recorded and verified.
- **`llm_router` standalone package.** Multi-provider LLM routing lifted out
  of `paperindex` into its own package. Task-tier routing (`light`/`medium`/
  `heavy`) is now usable anywhere without a paperindex dependency.
- **Plugin discovery for custom providers.** Drop a `.py` file in
  `~/.config/llm_router/plugins/` (or point `$LLM_ROUTER_PLUGINS` at one) and
  it is auto-loaded on import. Broken plugins are logged, not propagated.
- **Config file for `llm_router`.** Optional TOML at `$LLM_ROUTER_CONFIG` or
  `~/.config/llm_router/config.toml` supporting `[routing] provider_order`
  and tier route entries. Env vars still win when set.
- **Codex bridge stability hardening.** Pre-flight check, per-backend graded
  timeouts (codex 180s / anthropic 90s), `stdin=DEVNULL`, and a per-backend
  circuit breaker so repeat failures stop wasting 300s timeouts.

### Changed (breaking)

- **Data model: Domain → Topic → Papers.** The standalone `projects` table has been
  merged into `topics`. Orchestrator state, artifacts, reviews, and experiment runs
  now key off `topic_id`. The `projects` table and `project_id` columns remain in the
  SQLite schema for backward compat (SQLite cannot DROP COLUMN) but are no longer
  written by code. Migrations `037_domains_and_project_merge.sql` and
  `038_reviews_drop_project_not_null.sql` apply automatically on first DB open.
- **CLI:** `rh project add/list/show/update` removed. Use `rh topic init` (with optional
  `--domain`). Orchestrator commands that took `--project-id` now take `--topic` (by
  name) or `--topic-id`. New `rh domain init/list/show` commands added.
- **Python API:** `run_project`/`resume_project` renamed to `run_topic`/`resume_topic`.
  `ResearchAPI` methods (`record_artifact`, `orchestrator_status`, `gate_check`,
  `list_stage_artifacts`, `list_stale_artifacts`) take `topic_id` instead of `project_id`.
- **HTTP API:** `/api/projects` endpoints replaced by richer `/api/topics` endpoints
  (with orchestrator state inline) plus new `/api/domains`. Web dashboard updated to
  navigate Domain → Topic.
- **MCP tools:** all orchestrator/review/adversarial tools now take `topic_id`
  (no longer accept `project_id`).
- **Import paths:** LLM client code moved from `paperindex.llm.client` to
  `llm_router.client`. Update imports (`from llm_router import LLMClient,
  resolve_llm_config`).

### Fixed

- HTTP API uvicorn reload watcher scoped to the package directory to avoid
  reloading on unrelated file changes.

## [0.1.0] — 2026-04-21

### Added

**Core platform**

- 69 research primitives spanning retrieval, comprehension, extraction, analysis, synthesis, generation, and verification categories
- 112 MCP tools (stdio transport) wrapping all primitives plus orchestrator, provenance, advisory, and paperindex tools
- Primitive registry with `@register_primitive` decorator for registration and auto-MCP-exposure
- Provenance recorder that tracks every primitive execution with cost, model, output hash, and artifact lineage
- Plugin architecture: custom primitives, gates, stages, advisory rules, and backends via `plugin.yaml` manifest

**Orchestrator**

- 6-stage pipeline: `init → build → analyze → propose → experiment → write`
- Evidence-gated stage advancement — stages produce typed artifacts; gates verify them before permitting progression
- Dual-axis execution model: `workflow_mode` (explore/standard/strict/demo) × `autonomy_mode` (supervised/autonomous)
- Autonomous mode with auto-resolved gates; high-risk stages (direction selection, finalize) always require human approval
- `orchestrator_resume` tool for re-attaching to an in-progress project without restarting from scratch
- Stale artifact tracking and dependency graph for artifact lineage

**Adversarial review**

- `adversarial_review` primitive: independent cross-model challenge/response for high-stakes decisions
- Configurable challenger model separate from the orchestrating model
- Challenge/response/resolution recorded as first-class artifacts

**Literature tools**

- `paper_search` across multiple configured providers (Semantic Scholar, OpenAlex, arXiv)
- `paper_ingest` with arXiv ID, DOI, or local PDF path
- `paper_acquire` for batch PDF download
- `paper_summarize`, `claim_extract`, `evidence_link`, `gap_detect`, `baseline_identify`
- `iterative_retrieval_loop` for coverage-driven search expansion
- `paper_coverage_check` for gap-aware coverage scoring
- `deep_read` two-pass deep reading with `DeepReadingNote` output
- `enrich_affiliations` for author affiliation resolution

**Analysis tools**

- `method_taxonomy`, `evidence_matrix`, `contradiction_detect`
- `table_extract`, `figure_interpret`, `metrics_aggregate`
- `competitive_learning`, `reading_prioritize`

**Writing tools**

- `outline_generate`, `section_draft`, `section_review`, `section_revise`
- `writing_architecture`, `paper_finalize`
- `figure_plan`, `figure_generate` (via fal.ai integration)
- `rebuttal_format`, `topic_export`
- `consistency_check` for cross-section verification
- `latex_compile` with tectonic backend
- Writing skill aggregate and writing pattern extraction

**Algorithm design tools**

- `direction_ranking`, `design_brief_expand`, `design_gap_probe`
- `algorithm_candidate_generate`, `originality_boundary_check`
- `algorithm_design_refine`, `algorithm_design_loop`

**Self-improvement**

- Observation middleware for recording execution traces
- `experience_ingest`, `lesson_extract`, `lesson_overlay`
- `strategy_distill`, `strategy_inject`, `meta_reflect`
- `cold_start_run` for bootstrapping from a gold-standard trace

**Paperindex package**

- PDF structure extraction (sections, headings, figures, tables)
- Section-level full-text search
- Paper card generation (`paperindex_card` MCP tool)
- Multi-LLM provider routing for extraction tasks

**Web dashboard**

- Local Flask monitoring dashboard at `http://127.0.0.1:18080`
- Pipeline stage progress, provenance log, advisory notices, artifact browser

**Infrastructure**

- SQLite storage with incremental migrations (`pool.db`)
- `rh` / `rhub` / `research-harness` CLI entry points
- `claude-admin` CLI for administrative tasks
- `rhub --json doctor` health check
- Advisory engine with heuristic warnings and acknowledgement tracking
- Auto-runner for bounded autonomous task execution
- 987+ tests across `research_harness` and `paperindex` packages
- `environment.yml` for conda setup
- `setup.sh` one-command bootstrap

[Unreleased]: https://github.com/your-org/research-harness/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/your-org/research-harness/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/your-org/research-harness/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-org/research-harness/releases/tag/v0.1.0
