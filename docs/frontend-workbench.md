# Frontend Workbench

Research Harness ships a web workbench for the public GitHub release. The
workbench is intentionally not a full research IDE. It is the product surface
that helps a user understand state, launch common actions, and hand heavier
work to an AI coding agent.

## Product promise

> From a research question to evidence you can write with.

The UI should make three things obvious:

1. What research topic is active.
2. What evidence has already been collected.
3. What the next useful action is.

## Core 1.0 surface

The default navigation is limited to the core research loop:

- **Workbench** — the daily starting point.
- **Workflow** — topic stage and next-step state.
- **Library** — papers, PDFs, and deep-reading state.
- **Reports** — reusable outputs and writing material.

The home screen exposes four product actions:

1. Create a topic.
2. Deep-read papers.
3. Find research gaps.
4. Write from evidence.

## Labs / Advanced

Some capabilities are promising but should not be the first-run experience:

- research trend analysis;
- discovery exploration;
- model/provider configuration;
- budgets, calibration, rollback, and advanced agent settings.

These remain available under Labs / Advanced. The code is preserved, but the
main product story stays focused on the research workflow.

## Copy rules

Use product language, not implementation language.

Prefer:

- research topic;
- paper pool;
- evidence;
- research gap;
- next step;
- report;
- write from evidence.

Avoid in primary UI copy:

- primitive;
- artifact;
- orchestrator;
- registry;
- provider;
- pipeline, unless it is clearly visual and user-facing.

## Agent handoff

The frontend does not hide the agent-first model. It makes the handoff clear:

```text
Read AGENTS.md, docs/agent-guide.md, and skills/.
Create a topic for <my research question>, then start literature search and
record outputs in RH.
```

This belongs in empty states and onboarding surfaces, not in every page header.

## Visual direction

The desired style is mature product UI: confident, calm, and clean. Avoid a
research prototype feeling. Avoid explaining the whole system on screen.

Good defaults:

- strong hero with one primary CTA;
- clear metrics and workspace preview;
- compact cards with outcome-oriented labels;
- advanced functionality demoted to secondary surfaces;
- no dense tables on the first screen.
