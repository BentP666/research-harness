# Research Harness Zotero Panel

This is the RH-owned Zotero side-panel bridge for live Zotero ↔ RH/Codex conversations.

## What it does

- Adds a `Research Harness` section to the Zotero item pane.
- Reads the selected Zotero item metadata, RH tags, and the current Zotero collection context.
- Sends the user question to `POST /api/zotero/chat/stream` on the local RH API.
- RH resolves the Zotero item to RH paper/topic context, then connects to `codex app-server`.
- Streams Codex deltas back into Zotero and preserves multi-turn context with a durable `conversation_id -> Codex thread_id` mapping.
- Makes replies selectable/copyable in-place.
- For supported write intents, RH intercepts the request, returns a backend-owned `action_preview`, shows a lightweight confirmation card in chat, and applies the write only after explicit confirmation.
- Uses context-aware modes: concrete Zotero item/paper mode keeps the paper-first chat surface; collection/library mode exposes topic-init and RH→Zotero补库 prompts instead of forcing a paper UI.
- Adds a compact `RH` entry to Zotero's right-side item/library pane navigation. It opens the same conversation-style RH workspace used by paper mode, so an empty folder can start RH without first selecting a paper. In this bootstrap mode, RH can search for seed papers, preview the candidates, and only ingest/sync after explicit confirmation.
- Supports adding selected Zotero/PDF text and a small number of screenshot snippets to the next question.
- Supports two first-class action transports:
  - `http_json`: server-side RH operations such as syncing selected RH papers into the current Zotero collection.
  - `zotero_local`: guarded Zotero Desktop operations such as importing a local RH PDF as an attachment under the current item.
- Reuses a long-lived Codex app-server client pool keyed by model/cwd/effort so follow-up turns avoid process initialization overhead.

The Zotero plugin remains intentionally thin. RH owns paper/topic matching, sync semantics, provenance, guarded writes, and the Codex app-server bridge.

## Local service startup

Normal Zotero use can either connect to an already-running local RH API or opt in to auto-start. Public builds do **not** ship a machine-specific repo path. To enable auto-start, set `repoRoot` to your local checkout and set `autoStart=true`.

When auto-start is enabled, the plugin:

1. checks `http://127.0.0.1:8000/api/health`;
2. if nothing is listening and the URL is loopback-only (`127.*`, `localhost`, or `::1`), starts the local Python service from Zotero via Mozilla/Zotero `Subprocess`;
3. waits for health to pass, then calls `POST /api/zotero/warmup` so the Codex app-server pool starts before the first real question.

Default Zotero preferences:

```text
extensions.researchharness.zotero.apiURL    = http://127.0.0.1:8000
extensions.researchharness.zotero.autoStart = false
extensions.researchharness.zotero.repoRoot  = <empty>
extensions.researchharness.zotero.pythonBin = <empty>
extensions.researchharness.zotero.model     = gpt-5.3-codex-spark
```

Security boundary: auto-start is opt-in, requires an explicit local `repoRoot`, is disabled automatically for non-loopback URLs and for non-HTTP URLs, passes arguments as an argv array rather than through a shell, and sends the optional local token via environment variable rather than command-line text.

Manual fallback from the repository root is still:

```bash
PYTHONPATH=packages/research_harness:packages/research_harness_mcp:packages/llm_router:packages/paperindex \
.venv/bin/python -m research_harness_mcp.http_api
```

If your shell already activated the project virtualenv, `python -m research_harness_mcp.http_api` is equivalent.

The default local API URL is:

```text
http://127.0.0.1:8000
```

Codex requirements:

- `codex` must be installed and logged in.
- The bridge defaults to `/opt/homebrew/bin/codex` on Apple Silicon Homebrew when present, otherwise `codex` from `PATH`.
- The Zotero panel opportunistically calls `POST /api/zotero/warmup` when Zotero/the panel loads. This starts and initializes the local `codex app-server` process in the RH pool before the first user question. It does not start a Codex thread or consume model tokens; the first real question still pays thread creation and first-token latency.
- Override if needed:

```bash
export RESEARCH_HARNESS_CODEX_BIN="/path/to/codex"
# Optional backend default if Zotero does not send a model.
export RESEARCH_HARNESS_ZOTERO_CODEX_MODEL="gpt-5.3-codex-spark"
export RESEARCH_HARNESS_ZOTERO_CODEX_EFFORT="low"
export RESEARCH_HARNESS_ZOTERO_CODEX_TIMEOUT_SECONDS=240
```

Optional token gate:

```bash
export RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN="choose-a-local-token"
```

If you set this token, also set Zotero preference
`extensions.researchharness.zotero.token` to the same value.

## Build and install the Zotero plugin

```bash
./integrations/zotero-rh-panel/build-xpi.sh
```

Then in Zotero:

1. Tools → Add-ons
2. Gear icon → Install Add-on From File…
3. Select `integrations/zotero-rh-panel/dist/research-harness-zotero-panel.xpi`
4. Restart Zotero if Zotero asks.

## Expected first visible effect

Select one of the papers that RH already pushed into `Research Harness/自动科研`.

In the item pane you should see a `Research Harness` section. Ask:

```text
这篇论文对自动科研主题有什么启发？
```

The panel should show:

- a llm-for-zotero-inspired paper-first chat shell: compact header, status pill, new-chat control, and a single context summary card instead of multiple status blocks;
- a start page with suggested prompts and the model picker embedded in the composer;
- live streamed Codex text, not the old fixed “我已匹配到…” response;
- copyable/selectable assistant text;
- a retained multi-turn conversation for follow-up questions on the same Zotero item; previous turns stay in the chat transcript above the input instead of a separate history popover.

Try a write intent while a Zotero collection is selected:

```text
把这个主题里精读过的 3 篇论文导入当前目录
```

RH should show a confirmation card in chat first, then execute the import only after you click confirm.

Try the empty-folder bootstrap flow while a newly created Zotero collection is selected:

```text
帮我找到最开始的 5 篇种子论文
```

Click the small `RH` button in Zotero's right-side navigation. RH should open a full conversation-style workspace with the same compact header, context card, suggestions, chat transcript, model picker, and composer used by the paper pane. It should search from the collection/topic name, return a candidate preview card, and wait for confirmation before creating/reusing the RH topic, ingesting the candidate papers, and syncing them into the current Zotero collection.

Try a PDF attachment write intent while a concrete Zotero item is selected and RH already has a safe local `pdf_path` for the matched paper:

```text
下载并附加 PDF 到当前条目，先 dry-run，确认后 apply
```

RH should show a PDF attachment preview first. Confirming it runs the plugin-local Zotero handler, which calls `Zotero.Attachments.importFromFile` under the matched parent item. The preview/apply payload is generated by the RH API; the frontend does not infer write targets from model text.

## Safety model

The panel-side Codex bridge starts/resumes Codex threads with read-only sandbox and `approvalPolicy=never`. Free-form chat answers stay read-only by default. RH-owned write actions in the sidebar must go through an explicit confirmation flow (for example dry-run/import preview -> user confirm -> apply).

Local service auto-start has additional guards:

- only loopback URLs are eligible;
- process launch uses a fixed Python binary and repository root from Zotero preferences;
- no shell command string is constructed from chat/model text;
- optional local auth token is passed through process environment, not command-line arguments;
- if Zotero cannot load `Subprocess`, the panel falls back to a clear manual-start error.

The frontend only executes backend-provided `apply` specs:

- `http_json` specs post to the supplied local RH API path/payload.
- `zotero_local` specs dispatch to a small allow-list of plugin handlers. The initial allow-listed handler is `zotero_import_file_attachment`.
- PDF attachment previews require the stored `pdf_path` to resolve under RH's configured `PDF_ROOTS`; arbitrary filesystem paths from chat/model text are not executed.

## Current limitations

- This release intentionally focuses on the llm-for-zotero interaction subset we need most: paper-first chat, model selection, start-page suggestions, selected-text/screenshot context, streaming, and the current chat transcript.
- Human note/highlight import remains handled by the existing RH Zotero sync pull path and is not wired to a dedicated chat action yet.
- The PDF attachment action currently imports an already-local RH PDF into Zotero. If RH does not yet have `pdf_path`, first run RH paper ingestion/sync to download the PDF, then retry from the side panel.
- If the local Python service is not already running, the first panel load/question may spend a few seconds on auto-start. The first answer for a given model can still take several seconds because RH must initialize an app-server client and wait for the first model token. Follow-up turns on the same model/cwd reuse the pooled client and should avoid that startup cost.
