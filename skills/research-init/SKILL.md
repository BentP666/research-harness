---
name: research-init
description: Initialize a new research topic or new project integration for Research Harness. Trigger on phrases like "research-init", "/research-init", "初始化研究主题", "初始化 Research Harness", "给项目接入 Research Harness", or equivalent requests to create topic scaffolding, update AGENTS or CLAUDE guidance, and ingest seed papers.
---

# Research Init

Use this skill when the user wants to bootstrap a project or topic into Research Harness.

## Workflow

1. Read `docs/agent-guide.md`.
2. Identify:
   - topic slug or project name
   - target venue or timeline if provided
   - seed papers, DOI, arXiv IDs, or PDFs if provided
3. Ensure the target project has Research Harness guidance:
   - add or update `AGENTS.md` for Codex
   - if the user explicitly wants Claude compatibility, update `CLAUDE.md` too
4. If `rhub` or MCP is available, perform the minimum viable setup:
   - initialize the topic
   - ingest any provided seed papers
   - record assumptions when metadata is incomplete
5. If the user did not provide a topic slug, derive one from the title using lowercase hyphen-case.
6. Return a compact setup report with:
   - topic slug
   - touched files
   - ingested seeds
   - missing inputs
   - next 3 actions

## Execution Heuristic

Prefer doing the setup directly instead of only describing it when the repo context is clear enough.

If inputs are partial, continue with safe defaults:

- missing venue: omit it
- missing seeds: create integration files first
- missing project-level guidance: add a minimal `AGENTS.md` that points to `docs/agent-guide.md`

Do not block on optional metadata.

## Rules

- Prefer the public Research Harness conventions in `AGENTS.md` and `docs/agent-guide.md`.
- Do not invent seed papers.
- If topic metadata is missing, make the minimum safe assumptions and state them clearly.
- For any topic intended for a paper, survey, or serious research direction,
  create or request a `frontier_attention_evidence` artifact: latest top
  academic signals plus official industry signals proving the direction is
  actively important. If either side is weak, report it as a scope risk rather
  than overstating the topic.
