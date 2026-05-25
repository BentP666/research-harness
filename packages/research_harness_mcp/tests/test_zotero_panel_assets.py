"""Static checks for the RH-owned Zotero panel plugin MVP."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = ROOT / "integrations" / "zotero-rh-panel"


def test_zotero_panel_manifest_and_bootstrap_are_present():
    manifest = json.loads((PLUGIN_DIR / "manifest.json").read_text())

    assert manifest["applications"]["zotero"]["id"] == (
        "research-harness-zotero@github.com.Biajin-PKU"
    )
    assert manifest["applications"]["zotero"]["strict_min_version"] == "6.999"
    assert manifest["applications"]["zotero"]["strict_max_version"] == "9999.*"
    assert manifest["version"] == "1.0.0"
    assert manifest["applications"]["zotero"]["update_url"].endswith(
        "research-harness-zotero-update.json"
    )
    assert manifest["icons"]["16"] == "content/icons/rh-icon-16.png"
    assert manifest["icons"]["32"] == "content/icons/rh-icon-32.png"
    assert manifest["icons"]["48"] == "content/icons/rh-icon-48.png"
    assert manifest["icons"]["96"] == "content/icons/rh-icon-96.png"
    assert (PLUGIN_DIR / manifest["icons"]["16"]).exists()
    assert (PLUGIN_DIR / manifest["icons"]["32"]).exists()
    assert (PLUGIN_DIR / manifest["icons"]["48"]).exists()
    assert (PLUGIN_DIR / manifest["icons"]["96"]).exists()
    assert (PLUGIN_DIR / "content/icons/rh-icon-20.png").exists()
    assert (PLUGIN_DIR / "assets" / "rh-icon-source.png").exists()

    build_script = (PLUGIN_DIR / "build-xpi.sh").read_text()
    assert "write_icon(" not in build_script
    assert "Missing required icon asset" in build_script

    bootstrap = (PLUGIN_DIR / "bootstrap.js").read_text()
    assert "registerChrome" in bootstrap
    assert "rh-zotero-panel.js" in bootstrap


def test_zotero_panel_registers_item_pane_and_calls_rh_api():
    panel_js = (PLUGIN_DIR / "content" / "rh-zotero-panel.js").read_text()

    assert "Zotero.ItemPaneManager.registerSection" in panel_js
    assert "paneID: PANE_ID" in panel_js
    assert 'CHROME_CONTENT_BASE = "chrome://researchharnesszotero/content/"' in panel_js
    assert 'PANE_ICON = CHROME_CONTENT_BASE + "icons/rh-icon-20.png"' in panel_js
    assert "/api/zotero/chat/stream" in panel_js
    assert "response.body.getReader" in panel_js
    assert "parseSSEBuffer" in panel_js
    assert "/api/zotero/warmup" in panel_js
    assert "scheduleZoteroCodexWarmup" in panel_js
    assert "appendAssistantStoreMessage" in panel_js
    assert "rh-zotero-brand-logo" in panel_js
    assert "rh-zotero-brand-mark" not in panel_js
    assert "renderContextCard" in panel_js
    assert "rh-zotero-context-card" in panel_js
    assert "rh-zotero-context-title" in panel_js
    assert "rh-zotero-context-meta" in panel_js
    assert "renderStartPage" in panel_js
    assert "rh-zotero-start-page" in panel_js
    assert "rh-zotero-suggestion-btn" in panel_js
    assert "概括这篇论文的研究问题" in panel_js
    assert "提炼方法与关键发现" in panel_js
    assert "说明它和当前主题的关系" in panel_js
    assert "推荐 5 篇起步文献" in panel_js
    assert "开始文献探索" in panel_js
    assert "installRightPaneStarter" in panel_js
    assert "installLibrarySidenavButton" in panel_js
    assert "zotero-view-item-sidenav" in panel_js
    assert "research-harness-zotero-library-sidenav-button" in panel_js
    assert "openLibraryRightPaneWorkspace" in panel_js
    assert "research-harness-zotero-library-workspace" in panel_js
    assert "rh-zotero-library-workspace-body" in panel_js
    assert "zotero-collections-toolbar" not in panel_js
    assert "research-harness-zotero-collection-toolbar-button" not in panel_js
    assert "rh-zotero-collection-chat-window" not in panel_js
    assert "toggleCollectionPopover" not in panel_js
    assert "rh-zotero-collection-launcher" not in panel_js
    assert "rh-zotero-collection-popover" not in panel_js
    assert "renderPanel(body, null" in panel_js
    assert "collectionIsEmpty" in panel_js
    assert "rh-zotero-new-chat" in panel_js
    assert "renderHistoryMenu" not in panel_js
    assert "rh-zotero-history-toggle" not in panel_js
    assert "toggleHistoryMenu" not in panel_js
    assert "rh-zotero-history-menu" not in panel_js
    assert "historyToggleBtn" not in panel_js
    assert "historyMenuEl" not in panel_js
    assert "rh-zotero-prompt-rail" not in panel_js
    assert "renderPromptRail" not in panel_js
    assert "贡献" not in panel_js
    assert "局限" not in panel_js
    assert "下一步" not in panel_js
    assert "rh-zotero-composer-topline" in panel_js
    assert "rh-zotero-model-select" in panel_js
    assert "rh-zotero-send-button" in panel_js
    assert "Shift+Enter 换行" in panel_js
    assert "复制诊断" not in panel_js
    assert "复制诊断" not in panel_js
    assert "rh-zotero-message-copy" in panel_js
    assert "renderAssistantMarkdown" in panel_js
    assert "appendInlineMarkdown" in panel_js
    assert "textNode.textContent = message.text" not in panel_js
    assert "正在生成回复" in panel_js
    assert "keepTextEditingInsidePanel(input)" in panel_js
    assert "keepTextSelectionInsidePanel" in panel_js
    assert "action_preview" in panel_js
    assert "confirmImportPreview" not in panel_js
    assert "confirmActionPreview" in panel_js
    assert "executeActionPreview" in panel_js
    assert "ZOTERO_LOCAL_ACTION_HANDLERS" in panel_js
    assert "zotero_import_file_attachment" in panel_js
    assert "Zotero.Attachments.importFromFile" in panel_js
    assert "http_json" in panel_js
    assert "applySpec.path" in panel_js
    assert "applySpec.payload" in panel_js
    assert "refreshDirectoryContext(state)" in panel_js
    assert "function libraryTypeFor" in panel_js
    assert "library_type: libraryTypeFor(" in panel_js
    assert "current_directory_key: directory.key" in panel_js
    assert "current_directory_name: directory.name" in panel_js
    assert "current_directory_path: directory.path" in panel_js
    assert "MODEL_PREF" in panel_js
    assert "gpt-5.3-codex-spark" in panel_js
    assert "gpt-5.5" in panel_js
    assert "model: selectedModel()" in panel_js
    assert "captureScreenshotForNextTurn" in panel_js
    assert "addSelectedTextForNextTurn" in panel_js
    assert "cacheSelectionForNextTextTurn" in panel_js
    assert "pendingSelectedTextSnapshot" in panel_js
    assert "collectReaderSelectionDocuments" in panel_js
    assert "getActiveReaderForSelectedTab" in panel_js
    assert "prepareCaptureOverlayForSnapshot" in panel_js
    assert "selected_text: selectedTextForPayload(state)" in panel_js
    assert "screenshots: screenshotsForPayload(state)" in panel_js
    assert "clearConsumedComposerContext(state)" in panel_js
    assert "rh-zotero-context-preview" in panel_js
    assert "rh-zotero-add-text" in panel_js
    assert "rh-zotero-add-screenshot" in panel_js
    assert "renderIconButton" in panel_js
    assert "Services.wm.getMostRecentWindow" not in panel_js
    assert "syncMatchedTopicToZotero" not in panel_js
    assert 'selected_text: ""' not in panel_js
    assert "检查 API" not in panel_js
    assert "tags: tagsFor(base)" in panel_js
    assert "conversationStore" in panel_js
    assert "ensureConversationEntry" in panel_js
    assert "function formatTopicLabel" in panel_js
    assert "formatTopicLabel(matched.topic?.name)" in panel_js
    assert "orderable: false" in panel_js
    assert "placeLibrarySidenavWrapper(buttonContainer, wrapper)" in panel_js
    assert "buttonContainer.appendChild(wrapper);" in panel_js
    assert "buttonContainer.prepend" not in panel_js
    assert "Paper-first Zotero chat" not in panel_js
    assert "Collection-first Zotero chat" not in panel_js
    assert "Paper chat" not in panel_js
    assert "Library chat" not in panel_js
    assert "目录模式" not in panel_js
    assert "目录级入口" not in panel_js
    assert "最开始" not in panel_js
    assert "连接 RH/Codex" not in panel_js
    assert "RH API" not in panel_js

    panel_css = (PLUGIN_DIR / "content" / "rh-zotero-panel.css").read_text()
    assert "user-select: text" in panel_css
    assert ".rh-zotero-message.pending" in panel_css
    assert ".rh-zotero-loader" in panel_css
    assert ".rh-zotero-composer" in panel_css
    assert ".rh-zotero-composer-topline" in panel_css
    assert ".rh-zotero-brand-logo" in panel_css
    assert ".rh-zotero-context-card" in panel_css
    assert ".rh-zotero-context-pill {\n  display: inline-flex;" in panel_css
    context_pill_block = panel_css.split(".rh-zotero-context-pill {", 1)[1].split(
        "}", 1
    )[0]
    assert "text-transform: uppercase" not in context_pill_block
    assert ".rh-zotero-start-page" in panel_css
    assert ".rh-zotero-suggestion-btn" in panel_css
    assert ".rh-zotero-library-sidenav-wrapper" in panel_css
    assert ".rh-zotero-library-sidenav-button" in panel_css
    assert ".rh-zotero-library-workspace-body" in panel_css
    assert ".rh-zotero-collection-toolbar-button" not in panel_css
    assert ".rh-zotero-collection-panel-body" not in panel_css
    assert ".rh-zotero-collection-chat-window" not in panel_css
    assert ".rh-zotero-collection-launcher" not in panel_css
    assert ".rh-zotero-collection-popover" not in panel_css
    assert ".rh-zotero-history-menu" not in panel_css
    assert ".rh-zotero-history-wrap" not in panel_css
    assert ".rh-zotero-new-chat" in panel_css
    assert ".rh-zotero-action-card" in panel_css
    assert ".rh-zotero-prompt-rail" not in panel_css
    assert ".rh-zotero-send-button" in panel_css
    assert ".rh-zotero-context-preview" in panel_css
    assert ".rh-zotero-context-preview-chip" in panel_css
    assert ".rh-zotero-context-toolbar" in panel_css
    assert ".rh-zotero-context-tool" in panel_css
    assert ".rh-zotero-capture-overlay" in panel_css
    assert ".rh-zotero-capture-selection" in panel_css
    assert ".rh-zotero-capture-instructions" in panel_css
    assert ".rh-zotero-icon-button" in panel_css
    assert ".rh-zotero-message-copy" in panel_css
    assert ".rh-zotero-message-text.rich" in panel_css
    assert ".rh-zotero-message-text strong" in panel_css
    assert "-moz-user-modify: read-write" not in panel_css
    assert "100vw" not in panel_css


def test_zotero_panel_can_auto_start_local_service_safely():
    prefs_js = (PLUGIN_DIR / "prefs.js").read_text()
    panel_js = (PLUGIN_DIR / "content" / "rh-zotero-panel.js").read_text()

    assert 'pref("extensions.researchharness.zotero.autoStart", false);' in prefs_js
    assert 'pref("extensions.researchharness.zotero.repoRoot", "");' in prefs_js
    assert 'pref("extensions.researchharness.zotero.pythonBin", "");' in prefs_js

    assert "AUTO_START_PREF" in panel_js
    assert "REPO_ROOT_PREF" in panel_js
    assert "PYTHON_BIN_PREF" in panel_js
    assert "ensureResearchHarnessService" in panel_js
    assert "healthCheckResearchHarnessApi" in panel_js
    assert "canAutoStartApi" in panel_js
    assert "isLoopbackApiUrl" in panel_js
    assert "startResearchHarnessApi" in panel_js
    assert "请先设置 Zotero 偏好 extensions.researchharness.zotero.repoRoot" in panel_js
    assert "waitForResearchHarnessApi" in panel_js
    assert "loadSubprocessModule" in panel_js
    assert "Subprocess.sys.mjs" in panel_js
    assert "resource://gre/modules/Subprocess.jsm" in panel_js
    assert 'arguments: ["-m", "research_harness_mcp.http_api"]' in panel_js
    assert "environmentAppend: true" in panel_js
    assert "RESEARCH_HARNESS_DB_PATH" in panel_js
    assert "RESEARCH_HARNESS_HTTP_HOST" in panel_js
    assert "RESEARCH_HARNESS_HTTP_PORT" in panel_js
    assert "PYTHONPATH" in panel_js
    assert "RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN" in panel_js
    assert 'url.protocol !== "http:"' in panel_js
    assert 'host === "localhost"' in panel_js
    assert 'host === "::1"' in panel_js
    assert 'host === "[::1]"' in panel_js
    assert 'host.startsWith("127.")' in panel_js
    assert "await ensureResearchHarnessService()" in panel_js
    assert "healthCheckResearchHarnessApi(apiUrl)" in panel_js
    assert "Services.wm.getMostRecentWindow" not in panel_js
    assert "shellFlag" not in panel_js
    assert "wrappedCommand" not in panel_js


def test_zotero_panel_layout_regressions_stay_compact_and_native():
    panel_js = (PLUGIN_DIR / "content" / "rh-zotero-panel.js").read_text()
    panel_css = (PLUGIN_DIR / "content" / "rh-zotero-panel.css").read_text()

    assert 'state.chatShellEl.classList.toggle("empty", !hasMessages)' in panel_js
    assert 'state.chatShellEl.classList.toggle("has-messages", hasMessages)' in panel_js
    assert "historyWrap.append(historyBtn);" not in panel_js
    assert "tools.append(status, newChatBtn);" in panel_js

    assert ".rh-zotero-thread-controls {\n  position: relative;" in panel_css
    assert "width: 260px;" not in panel_css
    assert ".rh-zotero-chat-shell.empty" in panel_css
    assert ".rh-zotero-chat-shell.has-messages" in panel_css
    assert "min-height: 148px;" in panel_css
    assert "width: 20px;" in panel_css
    assert "--rh-bg: var(--material-sidepane" in panel_css
    assert "background: var(--rh-accent);" in panel_css
    assert "min-height: 52px;" in panel_css
    assert "max-height: 132px;" in panel_css

    assert "width: min(260px" not in panel_css
    assert "min-height: 240px;" not in panel_css
    assert "min-height: 88px;" not in panel_css
    assert "backdrop-filter" not in panel_css


def test_zotero_panel_builds_xpi(tmp_path: Path):
    completed = subprocess.run(
        ["bash", str(PLUGIN_DIR / "build-xpi.sh")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    output_paths = [
        Path(line) for line in completed.stdout.splitlines() if line.strip()
    ]
    xpi_path = next(path for path in output_paths if path.suffix == ".xpi")
    update_path = next(
        path
        for path in output_paths
        if path.name == "research-harness-zotero-update.json"
    )
    assert xpi_path.exists()
    assert update_path.exists()
    update_manifest = json.loads(update_path.read_text(encoding="utf-8"))
    addon_updates = update_manifest["addons"][
        "research-harness-zotero@github.com.Biajin-PKU"
    ]["updates"]
    assert addon_updates[0]["version"] == "1.0.0"
    assert addon_updates[0]["update_link"].endswith(
        "/v1.0.0/research-harness-zotero-panel.xpi"
    )
    with ZipFile(xpi_path) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "bootstrap.js" in names
    assert "content/rh-zotero-panel.js" in names
    assert "content/icon.svg" not in names
    assert "content/icons/rh-icon-16.png" in names
    assert "content/icons/rh-icon-20.png" in names
    assert "content/icons/rh-icon-32.png" in names
    assert "content/icons/rh-icon-48.png" in names
    assert "content/icons/rh-icon-96.png" in names
    assert "content/icons/icon-48.png" not in names
    assert "content/icons/icon-96.png" not in names
    assert "content/icons/icon-source.png" not in names
