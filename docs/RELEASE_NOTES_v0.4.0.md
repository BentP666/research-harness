# Research Harness v0.4.0 — Release Notes

**Release date:** 2026-05-10  
**Status:** Stable

Research Harness v0.4.0 turns the public release surface into a cleaner
agent-first workbench and adds an optional high-fidelity PDF parsing path for
Paperindex.

## Highlights

### Optional Docling parser backend

Paperindex now supports a pluggable document-parser layer:

- default parser: PyMuPDF, preserving the lightweight install path;
- optional parser: Docling, installed with `research-harness[docling]`;
- shared parser resolution through `resolve_document_parser()`;
- structured parser output with markdown, page text, and parser metadata.

This lets users choose between fast local parsing and richer Docling extraction
without changing downstream indexing, search, or card-generation workflows.

## Cursor Agent workflow surface

The repository now includes Cursor-specific Research Harness setup files:

- `.cursor/mcp.json` — project MCP server wiring;
- `.cursor/rules/research-harness-core.mdc` — core RH usage rules;
- `.cursor/agents/rh-paper-deep-reader.md` — paper deep-reading specialist;
- `.cursor/skills/rh-paper-deep-reading/SKILL.md` — direct skill workflow;
- `docs/cursor-agent.md` — verification and usage notes.

These files make the same RH storage/provenance rules available to Cursor-based
paper reading workflows.

## Frontend workbench release polish

The workbench copy and navigation now focus on the product loop:

1. understand the active research topic;
2. inspect the paper/evidence pool;
3. choose the next useful research action;
4. hand heavier loops to an agent.

The no-key demo and README material were refreshed to explain this flow without
requiring provider credentials.

## Upgrade notes

- Package and web metadata are now aligned to `0.4.0`.
- If you want the Docling parser, reinstall with:

  ```bash
  pip install -e "packages/research_harness[docling]"
  ```

- Existing PyMuPDF-based Paperindex workflows remain the default and do not
  require new dependencies.

## Verification

Local release checks used for this cut:

```bash
python -m ruff format --check packages/
python -m ruff check packages/research_harness/research_harness/paperindex/parsing/docling.py \
  packages/research_harness/research_harness/paperindex/parsing/resolver.py \
  packages/research_harness/tests/paperindex_tests/test_document_parsers.py
python -m pytest packages/research_harness/tests/paperindex_tests/test_document_parsers.py
cd web && npm run lint && npm run test && npm run build
```

