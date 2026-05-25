# Zotero Plugin Demo

Research Harness 1.0 uses the Zotero side-panel plugin as the primary public front end. The demo story is paper-first: select a Zotero item or collection, ask a research question, and let RH connect that context to topics, papers, claims, gaps, and guarded actions.

## Demo story

Default narrative:

1. **Select a paper or collection in Zotero** — RH reads bibliographic context without moving the user into a separate web app.
2. **Ask a paper-first question** — e.g. “这篇论文对自动科研主题有什么启发？”
3. **Resolve RH context** — the local bridge matches Zotero items to RH papers/topics and uses the same primitive/provenance layer as MCP.
4. **Preview guarded writes** — supported RH↔Zotero actions show a preview and require explicit confirmation before changing Zotero or RH state.
5. **Continue in an agent** — heavier loops still run through MCP/CLI skills, while Zotero remains the reading surface.

## Install from release

Download the latest plugin asset:

```text
https://github.com/Biajin-PKU/research-harness/releases/latest/download/research-harness-zotero-panel.xpi
```

Then in Zotero:

1. Tools → Add-ons
2. Gear icon → Install Add-on From File…
3. Select `research-harness-zotero-panel.xpi`
4. Restart Zotero if prompted

## Local bridge

```bash
pip install -e "packages/research_harness_mcp[api]"
python -m research_harness_mcp.http_api
```

The plugin defaults to `http://127.0.0.1:8000`. Auto-start is opt-in and requires setting the local `repoRoot` preference; see [`zotero-rh-panel.md`](zotero-rh-panel.md).

## Deprecated web demo

The old Next.js web dashboard/demo is deprecated and is no longer the public or remote front-end story. Keep it for local/internal experiments only; do not use it as the main release demo.
