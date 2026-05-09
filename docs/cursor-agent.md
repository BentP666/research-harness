# Cursor Agent setup for Research Harness

This machine uses Cursor as the primary local client for Research Harness paper deep reading.

## What is configured

- Project MCP: `.cursor/mcp.json`
  - Starts `research_harness_mcp` with `/Users/biajin/miniconda3/envs/research-harness/bin/python`
  - Loads provider keys from `.env`
  - Uses `.research-harness/pool.db`
- Project rule: `.cursor/rules/research-harness-core.mdc`
- Project subagent: `.cursor/agents/rh-paper-deep-reader.md`
- Project skill: `.cursor/skills/rh-paper-deep-reading/SKILL.md`

The shipped Research Harness skills can also be installed for Cursor with:

```bash
/Users/biajin/miniconda3/envs/research-harness/bin/rh skill install --target ~/.cursor/skills
```

## Verify

```bash
cursor-agent mcp list
cursor-agent mcp list-tools research-harness
```

If the CLI reports that it is not logged in, run:

```bash
cursor-agent login
```

The Cursor IDE can still use the project `.cursor/mcp.json` after restarting or reloading the window.

Note: the RH `deep_read` MCP primitive uses RH's configured LLM providers. If
`.env` does not contain `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `KIMI_API_KEY`,
or an equivalent route, the Cursor subagent should use Cursor's own model for
the reading and record the note as an `orchestrator_record_artifact` with
`artifact_type="cursor_deep_read_note"`.

## Typical prompt

```text
Use the rh-paper-deep-reader subagent to 精读 paper_id=12 for topic_id=3,
focus on reproducibility and what claims can support our related work.
```
