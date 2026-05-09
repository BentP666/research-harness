# Handoff prompt — paste into a fresh Claude Code session

Below is the complete prompt to give a new session. Copy everything between the `---BEGIN---` and `---END---` markers.

---BEGIN---

You are implementing the CS Research Workflow v2 on the Research Harness codebase. This is a multi-week, multi-phase project that has already been designed and reviewed (5 rounds of adversarial review). **Your job is execution, not redesign.**

## Working directory
`research-harness-oss` (the cloned repo root)

## Two source-of-truth documents — READ BOTH BEFORE STARTING

1. **Design (WHY)**: `docs/architecture/CS_RESEARCH_WORKFLOW_V2.md`
   — Explains the architecture decisions, data model, trade-offs. Do NOT modify this doc.
2. **Implementation manual (WHAT to build)**: `docs/architecture/CS_RESEARCH_WORKFLOW_V2_IMPLEMENTATION.md`
   — Step-by-step tasks with file paths, code templates, tests, and exit criteria. Follow this as a script.

If anything in the manual contradicts the design doc, STOP and ask — do not guess.

## Execution contract

1. **Phase order is strict**: Phase 0 → 1 → 2 → 3 → 4. Do not start a phase until the prior phase's exit criteria are all green.
2. **Within a phase, tasks are ordered**. Complete and verify each task's Exit criterion before moving to the next.
3. **One task = one commit**. Commit message format: `feat(cs-workflow): Task N.M — <short summary>`. Do NOT skip hooks, do NOT amend published commits.
4. **Tests must pass before you move on**. Run `python -m pytest packages/ -q --tb=short -x` after each task. If a test fails after 2 fix attempts, STOP and report.
5. **Do not "fix" failing tests by loosening them**. The test is the spec. If a test is actually wrong, flag it and ask.
6. **Do not touch files not listed in a task's "Files to edit"**. If you need to, stop and ask.
7. **Do not invent migration numbers**. Check `ls packages/research_harness/migrations/` first. 045–048 are reserved by this plan; 001–042 are already taken.
8. **Every new primitive MUST be registered** in `packages/research_harness/research_harness/primitives/registry.py` AND dispatched in `packages/research_harness/research_harness/execution/harness.py`. Skipping this means the primitive is dead code.
9. **Every new MCP tool MUST be exposed** via `@mcp.tool()` in `packages/research_harness_mcp/research_harness_mcp/tools.py`.
10. **Phase 0 is a hard gate**. The CSO coverage validation decides whether the rest of the project uses CSO Classifier (primary path) or falls back to LLM classification. Do NOT proceed to Phase 2 before Phase 0 results are documented and `CSO_MODE` is set.

## What to do first

1. `cd` into the working directory. Verify you are on branch `main` (or create a new branch `feat/cs-workflow-v2` if preferred).
2. Read `docs/architecture/CS_RESEARCH_WORKFLOW_V2.md` end to end. Take notes on the data model invariant (`topic = one paper`), the multi-dimensional red-ocean model, and the migration numbering (045–048).
3. Read `docs/architecture/CS_RESEARCH_WORKFLOW_V2_IMPLEMENTATION.md` end to end. Note Appendix A (common pitfalls) and Appendix C (when to ask).
4. Run `pytest packages/ -q --tb=short` to confirm the repo is in a green state before you start.
5. Start Phase 0, Task 0.1.

## When to stop and report

- A test fails after 2 fix attempts
- A file path in the manual doesn't exist (the codebase may have shifted)
- A migration number conflict (someone added 045+ since the manual was written)
- Phase 0 validation returns `CSO_MODE = "llm_fallback"` — you need explicit confirmation before taking the fallback branch
- `project_artifacts.project_id` semantics unclear when you reach Task 4.4
- Any sentence in the manual you don't understand

Report via: a message listing (a) which task, (b) the exact error, (c) what you tried. Then wait for guidance. Do NOT freelance fixes.

## Progress reporting

After each phase's exit criteria are all green, post a status:
- Phase N complete
- Commits: <range>
- Tests: all green
- Surprises / deviations: <list or "none">

## Out of scope (do NOT do these)

- Do not add features not in the manual (e.g. the TaxoAdapt v0.5 candidate mentioned in the design doc's §R).
- Do not rewrite or refactor code outside the task's "Files to edit" list.
- Do not optimize prematurely. Correct-and-slow beats fast-and-wrong.
- Do not change the CCF rank scoring table, red-ocean formula weights, or migration numbers without asking.
- Do not ship new documentation beyond what the manual specifies (except commit messages and phase-complete reports).

## Your first message back

After reading both docs, reply with:
- Confirmation that you've read both docs
- The output of `git status` and `git log -5 --oneline`
- The output of `ls packages/research_harness/migrations/`
- Your Python version (`python --version`)
- Any questions about the plan

Then await "proceed" before touching any files.

---END---
