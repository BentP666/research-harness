# Research Harness — Agent Guide

Research Harness is an agent-first research workflow platform for literature review, evidence management, experiment planning, and paper writing.

## Repository Layout

```text
packages/                  Python packages
  llm_router/              LLM provider routing
  paperindex/              PDF parsing and paper-card compatibility package
  research_harness/        Core workflow, primitives, provenance, CLI
  research_harness_mcp/    MCP and HTTP API surfaces
skills/                    Research Harness workflow skills
integrations/zotero-rh-panel/  Optional Zotero side-panel plugin
web/                       Optional Next.js workbench
docs/                      Public setup, usage, architecture, and troubleshooting docs
```

## Paper Management

See `docs/PAPER_MANAGEMENT.md` for the full protocol.

In short:

1. Use one RH database (`.research-harness/pool.db` by default, or `RESEARCH_HARNESS_DB_PATH`).
2. Store PDFs through RH ingestion/acquisition, not ad-hoc folders.
3. Always attach paper ingestion and analysis to an explicit topic.
4. Use MCP tools for research primitives when provenance matters; use the `rh` CLI mainly for setup, listing, and data-management tasks.

## Common Commands

```bash
# Install / verify
./setup.sh
rh --json doctor
python -m pytest packages/ -q

# Data management
rh topic list
rh topic init "my-research-topic"
rh paper ingest --arxiv-id 2401.12345 --topic my-research-topic
rh paper queue --topic my-research-topic
rh orchestrator status --topic my-research-topic

# MCP server
python -m research_harness_mcp
```

## Public Repository Hygiene

Keep this repository focused on reusable code, sanitized examples, and concise public documentation. Do not commit local databases, private research artifacts, unpublished drafts, credentials, one-off debug logs, or personal machine paths.

For bugs or process improvements, prefer GitHub Issues or the project backlog instead of new top-level report files.
