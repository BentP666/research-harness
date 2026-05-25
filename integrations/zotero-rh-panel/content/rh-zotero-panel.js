/* global Zotero, TextDecoder, ChromeUtils, Components */

var RHZoteroPanel = (() => {
  const ADDON_ID = "research-harness-zotero@github.com.Biajin-PKU";
  const PANE_ID = "research-harness-zotero-panel";
  const API_URL_PREF = "extensions.researchharness.zotero.apiURL";
  const TOKEN_PREF = "extensions.researchharness.zotero.token";
  const MODEL_PREF = "extensions.researchharness.zotero.model";
  const AUTO_START_PREF = "extensions.researchharness.zotero.autoStart";
  const REPO_ROOT_PREF = "extensions.researchharness.zotero.repoRoot";
  const PYTHON_BIN_PREF = "extensions.researchharness.zotero.pythonBin";
  const DEFAULT_API_URL = "http://127.0.0.1:8000";
  const DEFAULT_MODEL = "gpt-5.3-codex-spark";
  const DEFAULT_REPO_ROOT = "";
  const CHROME_CONTENT_BASE = "chrome://researchharnesszotero/content/";
  const LIBRARY_SIDENAV_WRAPPER_ID = "research-harness-zotero-library-sidenav-wrapper";
  const LIBRARY_SIDENAV_BUTTON_ID = "research-harness-zotero-library-sidenav-button";
  const LIBRARY_WORKSPACE_ID = "research-harness-zotero-library-workspace";
  const LIBRARY_WORKSPACE_BODY_ID = "research-harness-zotero-library-workspace-body";
  const RIGHT_PANE_STARTER_CLEANUP_KEY = "__rhZoteroRightPaneStarterCleanup";
  const MODEL_OPTIONS = [
    "gpt-5.3-codex-spark",
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.5",
  ];
  const MAX_SELECTED_TEXT_CHARS = 20000;
  const MAX_SCREENSHOTS = 2;
  const MAX_SCREENSHOT_DATA_URL_LENGTH = 3800000;
  const ZOTERO_LOCAL_ACTION_HANDLERS = {
    zotero_import_file_attachment: zoteroImportFileAttachment,
  };
  const HTML_NS = "http://www.w3.org/1999/xhtml";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const conversationStore = new Map();
  const codexWarmupUntil = new Map();
  const CODEX_WARMUP_SUCCESS_TTL_MS = 10 * 60 * 1000;
  const CODEX_WARMUP_RETRY_MS = 30 * 1000;
  const SERVICE_START_WAIT_MS = 18000;
  const SERVICE_START_POLL_MS = 450;
  let rootURI = "";
  let registeredSectionID = null;
  let subprocessModule = null;
  let serviceProcess = null;
  let serviceStartPromise = null;

  async function startup(pluginRootURI) {
    rootURI = pluginRootURI;
    Zotero.RHZoteroPanel = api;
    await Promise.all([
      Zotero.initializationPromise,
      Zotero.unlockPromise,
      Zotero.uiReadyPromise,
    ]);
    for (const win of Zotero.getMainWindows()) {
      await onMainWindowLoad(win);
    }
    registerSection();
  }

  async function shutdown() {
    if (registeredSectionID && Zotero.ItemPaneManager?.unregisterSection) {
      try {
        Zotero.ItemPaneManager.unregisterSection(registeredSectionID);
      } catch (err) {
        Zotero.debug(`RH Zotero Panel: unregister failed: ${err}`);
      }
    }
    registeredSectionID = null;
    stopResearchHarnessService();
    for (const win of Zotero.getMainWindows()) {
      await onMainWindowUnload(win);
    }
    delete Zotero.RHZoteroPanel;
  }

  async function onMainWindowLoad(win) {
    try {
      win.MozXULElement.insertFTLIfNeeded("mainWindow.ftl");
    } catch (err) {
      Zotero.debug(`RH Zotero Panel: FTL insert failed: ${err}`);
    }
    registerStyles(win);
    installRightPaneStarter(win);
    scheduleZoteroCodexWarmupForWindow(win);
  }

  async function onMainWindowUnload(win) {
    removeRightPaneStarter(win);
    win.document.getElementById("research-harness-zotero-styles")?.remove();
  }

  function registerSection() {
    if (registeredSectionID || !Zotero.ItemPaneManager?.registerSection) {
      return;
    }
    const PANE_ICON = CHROME_CONTENT_BASE + "icons/rh-icon-20.png";
    registeredSectionID = Zotero.ItemPaneManager.registerSection({
      paneID: PANE_ID,
      pluginID: ADDON_ID,
      header: {
        l10nID: "rh-zotero-panel-head",
        icon: PANE_ICON,
      },
      sidenav: {
        l10nID: "rh-zotero-panel-sidenav-tooltip",
        icon: PANE_ICON,
        orderable: false,
      },
      onInit: ({ setEnabled }) => {
        setEnabled(true);
      },
      onItemChange: ({ setEnabled }) => {
        setEnabled(true);
        return true;
      },
      onRender: ({ body, item }) => {
        renderPanel(body, item || null);
      },
    });
  }

  function registerStyles(win) {
    const doc = win.document;
    if (doc.getElementById("research-harness-zotero-styles")) {
      return;
    }
    const link = doc.createElement("link");
    link.id = "research-harness-zotero-styles";
    link.rel = "stylesheet";
    link.type = "text/css";
    link.href = CHROME_CONTENT_BASE + "rh-zotero-panel.css";
    doc.documentElement.appendChild(link);
  }

  function installRightPaneStarter(win) {
    const doc = win.document;
    installLibrarySidenavButton(win);
    if (typeof win[RIGHT_PANE_STARTER_CLEANUP_KEY] === "function") {
      return;
    }

    const scheduleRefresh = () => {
      win.setTimeout(() => refreshRightPaneStarter(win), 0);
    };
    const events = ["click", "keyup", "command", "select"];
    events.forEach((eventName) => {
      doc.addEventListener(eventName, scheduleRefresh, true);
    });
    const interval = win.setInterval(() => refreshRightPaneStarter(win), 1200);
    win[RIGHT_PANE_STARTER_CLEANUP_KEY] = () => {
      events.forEach((eventName) => {
        doc.removeEventListener(eventName, scheduleRefresh, true);
      });
      win.clearInterval(interval);
      doc.getElementById(LIBRARY_SIDENAV_WRAPPER_ID)?.remove();
      closeLibraryRightPaneWorkspace(win);
      delete win[RIGHT_PANE_STARTER_CLEANUP_KEY];
    };

    refreshRightPaneStarter(win);
  }

  function installLibrarySidenavButton(win) {
    const doc = win.document;
    const existingButton = doc.getElementById(LIBRARY_SIDENAV_BUTTON_ID);
    const existingWrapper = doc.getElementById(LIBRARY_SIDENAV_WRAPPER_ID);
    const sideNav = doc.getElementById("zotero-view-item-sidenav");
    const buttonContainer = sideNav?.querySelector?.(".inherit-flex");
    if (existingButton && existingWrapper && buttonContainer) {
      placeLibrarySidenavWrapper(buttonContainer, existingWrapper);
      return true;
    }
    if (!buttonContainer) {
      return false;
    }

    const wrapper = doc.createElementNS(HTML_NS, "div");
    wrapper.id = LIBRARY_SIDENAV_WRAPPER_ID;
    wrapper.className = "pin-wrapper rh-zotero-library-sidenav-wrapper";

    const buttonNode = createXulElement(doc, "div");
    buttonNode.id = LIBRARY_SIDENAV_BUTTON_ID;
    buttonNode.className = "btn rh-zotero-library-sidenav-button";
    buttonNode.dataset.action = "research-harness-library-chat";
    buttonNode.setAttribute("custom", "true");
    buttonNode.setAttribute("tabindex", "0");
    buttonNode.setAttribute("role", "tab");
    buttonNode.style = `--custom-sidenav-icon-light: url('${CHROME_CONTENT_BASE}icons/rh-icon-20.png'); --custom-sidenav-icon-dark: url('${CHROME_CONTENT_BASE}icons/rh-icon-20.png');`;
    buttonNode.addEventListener("click", (event) => {
      event.stopPropagation();
      event.preventDefault();
      openLibraryRightPaneWorkspace(win, { focusInput: true });
    });
    buttonNode.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      event.stopPropagation();
      event.preventDefault();
      openLibraryRightPaneWorkspace(win, { focusInput: true });
    });

    wrapper.appendChild(buttonNode);
    placeLibrarySidenavWrapper(buttonContainer, wrapper);
    refreshRightPaneStarter(win);
    return true;
  }

  function placeLibrarySidenavWrapper(buttonContainer, wrapper) {
    if (!buttonContainer || !wrapper) {
      return;
    }
    if (wrapper.parentElement !== buttonContainer || wrapper.nextElementSibling) {
      buttonContainer.appendChild(wrapper);
    }
  }

  function openLibraryRightPaneWorkspace(win, options = {}) {
    const doc = win.document;
    const directory = getCurrentDirectoryContext(win);
    if (!directory.name && !directory.path) {
      refreshRightPaneStarter(win);
      return false;
    }
    const itemPane = getLibraryItemPane(win);
    if (!itemPane) {
      return false;
    }
    ensureItemPaneVisible(itemPane);
    const workspace = ensureLibraryWorkspace(win);
    const body = workspace?.querySelector?.(`#${LIBRARY_WORKSPACE_BODY_ID}`);
    if (!workspace || !body) {
      return false;
    }
    try {
      renderPanel(body, null, { focusInput: Boolean(options.focusInput) });
      workspace.dataset.directoryKey = conversationKeyFor(null, directory);
      itemPane.classList.add("rh-zotero-library-workspace-open");
      itemPane.setAttribute("data-rh-zotero-library-workspace", "open");
      markLibrarySidenavActive(win, true);
      if (options.focusInput) {
        win.setTimeout(() => {
          body.querySelector?.(".rh-zotero-input")?.focus?.();
        }, 0);
      }
      return true;
    } catch (err) {
      Zotero.debug(`RH Zotero Panel: right pane workspace open failed: ${err}`);
      return false;
    }
  }

  function ensureLibraryWorkspace(win) {
    const doc = win.document;
    const existing = doc.getElementById(LIBRARY_WORKSPACE_ID);
    if (existing) {
      return existing;
    }
    const workspace = doc.createElementNS(HTML_NS, "div");
    workspace.id = LIBRARY_WORKSPACE_ID;
    workspace.className = "rh-zotero-library-workspace";

    const body = doc.createElementNS(HTML_NS, "div");
    body.id = LIBRARY_WORKSPACE_BODY_ID;
    body.className = "rh-zotero-library-workspace-body";
    workspace.appendChild(body);

    const itemPane = getLibraryItemPane(win);
    if (typeof itemPane?.setItemPaneMessage === "function") {
      itemPane.setItemPaneMessage(workspace);
    } else {
      try {
        itemPane.mode = "message";
      } catch (_) {
        // ignore
      }
      const messagePane = doc.getElementById("zotero-item-message");
      if (typeof messagePane?.render === "function") {
        messagePane.render(workspace);
      } else {
        const messageBox = doc.getElementById("zotero-item-pane-message-box");
        messageBox?.replaceChildren?.(workspace);
      }
    }
    return workspace;
  }

  function refreshRightPaneStarter(win) {
    installLibrarySidenavButton(win);
    const doc = win.document;
    const buttonNode = doc.getElementById(LIBRARY_SIDENAV_BUTTON_ID);
    const wrapper = doc.getElementById(LIBRARY_SIDENAV_WRAPPER_ID);
    if (!buttonNode || !wrapper) return;

    const selectedItems = getSelectedItems(win);
    const hasItemSelection = selectedItems.length > 0;
    wrapper.hidden = hasItemSelection;
    if (hasItemSelection) {
      markLibrarySidenavActive(win, false);
      getLibraryItemPane(win)?.classList?.remove?.("rh-zotero-library-workspace-open");
      getLibraryItemPane(win)?.removeAttribute?.("data-rh-zotero-library-workspace");
      return;
    }

    const directory = getCurrentDirectoryContext(win);
    const hasDirectory = Boolean(directory.name || directory.path);
    if (!hasDirectory) {
      buttonNode.setAttribute("disabled", "true");
      buttonNode.setAttribute("tooltiptext", "Research Harness：选择文库或文件夹后开始");
      buttonNode.setAttribute("aria-label", "Research Harness：选择文库或文件夹后开始");
      return;
    }
    buttonNode.removeAttribute("disabled");

    const empty = collectionIsEmpty(win);
    buttonNode.classList.toggle("empty-collection", empty);
    const label = empty
      ? `Research Harness：为「${directoryLabel(directory)}」推荐起步文献`
      : `Research Harness：整理「${directoryLabel(directory)}」`;
    buttonNode.setAttribute("tooltiptext", label);
    buttonNode.setAttribute("title", label);
    buttonNode.setAttribute("aria-label", label);

    refreshOpenLibraryWorkspace(win, directory);
  }

  function refreshOpenLibraryWorkspace(win, directory) {
    const doc = win.document;
    const workspace = doc.getElementById(LIBRARY_WORKSPACE_ID);
    const body = doc.getElementById(LIBRARY_WORKSPACE_BODY_ID);
    if (!workspace || !body) {
      markLibrarySidenavActive(win, false);
      return false;
    }
    const nextKey = conversationKeyFor(null, directory);
    markLibrarySidenavActive(win, true);
    if (workspace.dataset.directoryKey === nextKey) {
      return true;
    }
    try {
      renderPanel(body, null, { focusInput: false });
      workspace.dataset.directoryKey = nextKey;
      return true;
    } catch (err) {
      Zotero.debug(`RH Zotero Panel: right pane workspace refresh failed: ${err}`);
      return false;
    }
  }

  function closeLibraryRightPaneWorkspace(win) {
    const doc = win?.document;
    doc?.getElementById(LIBRARY_SIDENAV_WRAPPER_ID)?.remove();
    doc?.getElementById(LIBRARY_WORKSPACE_ID)?.remove();
    const itemPane = getLibraryItemPane(win);
    itemPane?.classList?.remove?.("rh-zotero-library-workspace-open");
    itemPane?.removeAttribute?.("data-rh-zotero-library-workspace");
    markLibrarySidenavActive(win, false);
  }

  function removeRightPaneStarter(win) {
    if (typeof win?.[RIGHT_PANE_STARTER_CLEANUP_KEY] === "function") {
      win[RIGHT_PANE_STARTER_CLEANUP_KEY]();
      return;
    }
    closeLibraryRightPaneWorkspace(win);
  }

  function getLibraryItemPane(win) {
    return win?.document?.getElementById?.("zotero-item-pane") || win?.ZoteroPane?.itemPane || null;
  }

  function ensureItemPaneVisible(itemPane) {
    try {
      itemPane.collapsed = false;
    } catch (_) {
      itemPane?.removeAttribute?.("collapsed");
    }
  }

  function getSelectedItems(win) {
    try {
      const selected = win?.ZoteroPane?.getSelectedItems?.();
      if (Array.isArray(selected)) {
        return selected;
      }
    } catch (_) {
      // ignore
    }
    try {
      const selected = win?.ZoteroPane?.itemsView?.getSelectedItems?.();
      return Array.isArray(selected) ? selected : [];
    } catch (_) {
      return [];
    }
  }

  function markLibrarySidenavActive(win, active) {
    const buttonNode = win?.document?.getElementById?.(LIBRARY_SIDENAV_BUTTON_ID);
    buttonNode?.classList?.toggle?.("active", Boolean(active));
    buttonNode?.setAttribute?.("aria-selected", active ? "true" : "false");
  }

  function collectionIsEmpty(win) {
    try {
      const collection = win?.ZoteroPane?.getSelectedCollection?.();
      if (!collection?.getChildItems) {
        return false;
      }
      const childIDs = collection.getChildItems(true) || [];
      return childIDs.length === 0;
    } catch (_) {
      return false;
    }
  }

  function renderPanel(body, item, options = {}) {
    const doc = body.ownerDocument;
    body.replaceChildren();

    const base = resolveBaseItem(item);
    const directory = getCurrentDirectoryContext(doc.defaultView);
    const conversationKey = conversationKeyFor(base, directory);
    const bucket = ensureConversationEntry(conversationKey);

    const state = {
      body,
      item,
      base,
      directory,
      conversationKey,
      bucket,
      rootEl: null,
      statusEl: null,
      statusTextEl: null,
      contextModeEl: null,
      contextTitleEl: null,
      contextMetaEl: null,
      contextRhEl: null,
      chatShellEl: null,
      messagesEl: null,
      startPageEl: null,
      inputEl: null,
      sendBtn: null,
      modelSelectEl: null,
      composerHintEl: null,
      composerContextEl: null,
      addTextBtn: null,
      screenshotBtn: null,
    };

    bucket.lastKnownItem = base?.key || item?.key || "";
    if (!bucket.uiStatus) {
      bucket.uiStatus = canChat(state) ? "就绪" : "请先选择论文";
    }

    const root = el(doc, "div", "rh-zotero-panel");
    root.classList.add(base ? "rh-zotero-mode-paper" : "rh-zotero-mode-library");
    keepTextSelectionInsidePanel(root);

    root.append(
      renderHeader(doc, state),
      renderContextCard(doc, state),
      renderChatShell(doc, state),
      renderComposer(doc, state),
    );

    body.appendChild(root);
    state.rootEl = root;

    if (typeof body.style !== "undefined") {
      body.style.overflowAnchor = "none";
      body.style.minWidth = "0";
      body.style.width = "100%";
      body.style.maxWidth = "100%";
      body.style.overflowX = "hidden";
      body.style.boxSizing = "border-box";
    }

    refreshPanel(state, { focusInput: Boolean(options.focusInput) });
    scheduleZoteroCodexWarmup(state);
  }

  function renderHeader(doc, state) {
    const header = el(doc, "div", "rh-zotero-header");
    const brand = el(doc, "div", "rh-zotero-brand");
    const mark = el(doc, "img", "rh-zotero-brand-logo");
    mark.src = CHROME_CONTENT_BASE + "icons/rh-icon-48.png";
    mark.alt = "Research Harness";
    const copy = el(doc, "div", "rh-zotero-brand-copy");
    copy.append(
      el(doc, "div", "rh-zotero-title", "Research Harness"),
      el(
        doc,
        "div",
        "rh-zotero-subtitle",
        state.base ? "基于当前论文" : "基于当前文件夹",
      ),
    );
    brand.append(mark, copy);

    const tools = el(doc, "div", "rh-zotero-thread-controls");
    const status = el(doc, "div", "rh-zotero-status-pill");
    status.setAttribute("aria-live", "polite");
    status.title = getApiUrl();
    status.append(
      el(doc, "span", "rh-zotero-status-dot"),
      el(doc, "span", "rh-zotero-status-text", bucketStatusText(state.bucket)),
    );
    state.statusEl = status;
    state.statusTextEl = status.querySelector(".rh-zotero-status-text");

    const newChatBtn = renderIconButton(
      doc,
      "plus",
      "新建会话",
      "rh-zotero-new-chat",
    );
    newChatBtn.type = "button";
    newChatBtn.addEventListener("click", () => {
      startNewChat(state);
    });
    newChatBtn.append(el(doc, "span", "rh-zotero-new-chat-label", "新建"));

    tools.append(status, newChatBtn);
    header.append(brand, tools);
    return header;
  }

  function renderContextCard(doc, state) {
    const card = el(doc, "section", "rh-zotero-context-card");
    const top = el(doc, "div", "rh-zotero-context-topline");
    const mode = el(doc, "span", "rh-zotero-context-pill");
    const rh = el(doc, "span", "rh-zotero-context-pill subtle");
    state.contextModeEl = mode;
    state.contextRhEl = rh;
    top.append(mode, rh);

    const title = el(doc, "div", "rh-zotero-context-title");
    const meta = el(doc, "div", "rh-zotero-context-meta");
    state.contextTitleEl = title;
    state.contextMetaEl = meta;

    card.append(top, title, meta);
    return card;
  }

  function renderChatShell(doc, state) {
    const shell = el(doc, "div", "rh-zotero-chat-shell");
    state.chatShellEl = shell;
    return shell;
  }

  function renderStartPage(doc, state) {
    const wrap = el(doc, "div", "rh-zotero-start-page");
    const title = el(doc, "div", "rh-zotero-start-title");
    const subtitle = el(doc, "div", "rh-zotero-start-subtitle");
    const suggestions = el(doc, "div", "rh-zotero-suggestion-row");
    const hasMessages = Array.isArray(state.bucket.messages) && state.bucket.messages.length > 0;

    if (!canChat(state)) {
      title.textContent = "选择论文或文件夹开始";
      subtitle.textContent = "Research Harness 会基于当前 Zotero 上下文，帮助你整理文献、主题和后续动作。";
    } else if (state.base) {
      title.textContent = "研究这篇论文";
      subtitle.textContent = hasMessages
        ? "你可以继续追问，或新建一轮更聚焦的讨论。"
        : "围绕论文内容、方法、证据和主题关系继续提问。";
      buildSuggestionButtons(doc, state, suggestions, [
        "概括这篇论文的研究问题",
        "提炼方法与关键发现",
        "说明它和当前主题的关系",
        "为当前条目附加 PDF",
      ]);
    } else {
      title.textContent = collectionIsEmpty(doc.defaultView)
        ? "开始文献探索"
        : "整理当前文件夹";
      subtitle.textContent = collectionIsEmpty(doc.defaultView)
        ? "Research Harness 可以为当前文件夹推荐起步文献、创建研究主题，并把结果保存回 Zotero。"
        : "基于这个文件夹的论文，识别主题、补齐相关文献，并同步可执行结果。";
      buildSuggestionButtons(doc, state, suggestions, [
        "推荐 5 篇起步文献",
        "识别这个文件夹的研究主题",
        "从当前文件夹创建研究主题",
        "补充相关文献",
        "导入缺失文献",
      ]);
    }

    wrap.append(title, subtitle, suggestions);
    state.startPageEl = wrap;
    return wrap;
  }

  function buildSuggestionButtons(doc, state, target, prompts) {
    target.replaceChildren();
    for (const prompt of prompts) {
      const btn = el(doc, "button", "rh-zotero-suggestion-btn", prompt);
      btn.type = "button";
      btn.addEventListener("click", () => {
        if (!state.inputEl) return;
        state.inputEl.value = prompt;
        state.bucket.draftText = prompt;
        syncTextareaHeight(state.inputEl);
        setStatus(state, "已填入建议问题");
        state.inputEl.focus();
      });
      target.appendChild(btn);
    }
  }

  function renderComposer(doc, state) {
    const composer = el(doc, "div", "rh-zotero-composer");
    const topline = el(doc, "div", "rh-zotero-composer-topline");
    const modelSelect = doc.createElement("select");
    modelSelect.className = "rh-zotero-model-select";
    modelSelect.setAttribute("aria-label", "选择模型");
    for (const model of MODEL_OPTIONS) {
      const option = doc.createElement("option");
      option.value = model;
      option.textContent = model;
      if (model === selectedModel()) {
        option.selected = true;
      }
      modelSelect.appendChild(option);
    }
    modelSelect.addEventListener("change", () => {
      Zotero.Prefs.set(MODEL_PREF, modelSelect.value, true);
      setStatus(state, `模型已切换到 ${modelSelect.value}`);
    });
    state.modelSelectEl = modelSelect;

    const hint = el(doc, "span", "rh-zotero-composer-hint", "Enter 发送，Shift+Enter 换行");
    state.composerHintEl = hint;
    topline.append(modelSelect, hint);

    const contextPreview = el(doc, "div", "rh-zotero-context-preview");
    contextPreview.setAttribute("aria-live", "polite");
    contextPreview.hidden = true;
    state.composerContextEl = contextPreview;

    const input = el(doc, "textarea", "rh-zotero-input");
    input.placeholder = "围绕当前论文提问，或请 Research Harness 说明它和当前主题的关系…";
    input.setAttribute("aria-label", "Research Harness 提问输入框");
    input.setAttribute("spellcheck", "true");
    keepTextEditingInsidePanel(input);
    input.addEventListener("input", () => {
      state.bucket.draftText = input.value;
      syncTextareaHeight(input);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) return;
      event.preventDefault();
      void sendToRH({ doc, state });
    });
    state.inputEl = input;

    const footer = el(doc, "div", "rh-zotero-composer-footer");
    const tools = el(doc, "div", "rh-zotero-context-toolbar");
    const addTextBtn = renderIconButton(
      doc,
      "text",
      "加入选中文本",
      "rh-zotero-context-tool rh-zotero-add-text",
    );
    addTextBtn.append(el(doc, "span", "", "选中文本"));
    const cacheSelection = () => {
      cacheSelectionForNextTextTurn(state);
    };
    addTextBtn.addEventListener("pointerdown", cacheSelection, true);
    addTextBtn.addEventListener("mousedown", cacheSelection, true);
    addTextBtn.addEventListener("click", () => {
      void addSelectedTextForNextTurn(state);
    });
    state.addTextBtn = addTextBtn;

    const screenshotBtn = renderIconButton(
      doc,
      "camera",
      "添加截图",
      "rh-zotero-context-tool rh-zotero-add-screenshot",
    );
    screenshotBtn.append(el(doc, "span", "", "截图"));
    screenshotBtn.addEventListener("click", () => {
      void captureScreenshotForNextTurn(state);
    });
    state.screenshotBtn = screenshotBtn;
    tools.append(addTextBtn, screenshotBtn);

    const sendBtn = renderIconButton(
      doc,
      "send",
      "发送",
      "rh-zotero-send-button",
    );
    sendBtn.type = "button";
    sendBtn.addEventListener("click", () => {
      void sendToRH({ doc, state });
    });
    state.sendBtn = sendBtn;

    footer.append(tools, sendBtn);
    composer.append(topline, contextPreview, input, footer);
    return composer;
  }

  function refreshPanel(state, options = {}) {
    refreshHeader(state);
    refreshContextCard(state);
    refreshChatSurface(state);
    refreshComposer(state, options);
  }

  function refreshHeader(state) {
    setGenerating(state, state.bucket.isGenerating);
    setStatus(state, bucketStatusText(state.bucket));
  }

  function refreshContextCard(state) {
    if (!state.contextTitleEl || !state.contextMetaEl) return;
    const matched = state.bucket.matched || null;
    state.contextModeEl.textContent = state.base ? "论文助手" : "文件夹助手";
    state.contextRhEl.textContent = rhStatusLabel(state, matched);
    state.contextTitleEl.textContent = contextHeadline(state);
    state.contextMetaEl.textContent = contextMetaLine(state, matched);
  }

  function refreshChatSurface(state) {
    const hasMessages = Boolean(state.bucket.messages?.length);
    state.chatShellEl.classList.toggle("empty", !hasMessages);
    state.chatShellEl.classList.toggle("has-messages", hasMessages);
    state.chatShellEl.replaceChildren();
    state.messagesEl = null;
    state.startPageEl = null;
    if (!hasMessages) {
      state.chatShellEl.appendChild(renderStartPage(state.chatShellEl.ownerDocument, state));
      return;
    }
    const messages = el(state.chatShellEl.ownerDocument, "div", "rh-zotero-messages");
    keepTextSelectionInsidePanel(messages);
    state.messagesEl = messages;
    for (const message of state.bucket.messages) {
      if (message.type === "action") {
        messages.appendChild(renderActionCard(state, message));
      } else {
        messages.appendChild(renderTextMessage(state, message));
      }
    }
    state.chatShellEl.appendChild(messages);
    queueScrollToBottom(messages);
  }

  function refreshComposer(state, options = {}) {
    const canUseChat = canChat(state);
    const isBusy = Boolean(state.bucket.isGenerating);
    refreshComposerContext(state);
    if (state.inputEl) {
      state.inputEl.disabled = !canUseChat || isBusy;
      if (typeof state.bucket.draftText === "string" && state.inputEl.value !== state.bucket.draftText) {
        state.inputEl.value = state.bucket.draftText;
      }
      state.inputEl.placeholder = state.base
        ? "围绕当前论文提问，或请 Research Harness 说明它和当前主题的关系…"
        : "询问当前文件夹、研究主题，或请 Research Harness 推荐起步文献…";
      syncTextareaHeight(state.inputEl);
      if (options.focusInput) {
        state.inputEl.focus();
      }
    }
    if (state.sendBtn) {
      state.sendBtn.disabled = !canUseChat || isBusy;
      state.sendBtn.setAttribute(
        "aria-label",
        isBusy ? "正在生成回复" : "发送",
      );
      state.sendBtn.title = isBusy ? "正在生成回复" : "发送";
      state.sendBtn.classList.toggle("loading", isBusy);
    }
    if (state.modelSelectEl) {
      const currentModel = selectedModel();
      state.modelSelectEl.disabled = isBusy;
      if (state.modelSelectEl.value !== currentModel) {
        state.modelSelectEl.value = currentModel;
      }
    }
    if (state.composerHintEl) {
      state.composerHintEl.textContent = isBusy
        ? "正在生成回复…"
        : "Enter 发送，Shift+Enter 换行";
    }
    if (state.addTextBtn) {
      state.addTextBtn.disabled = !canUseChat || isBusy;
    }
    if (state.screenshotBtn) {
      state.screenshotBtn.disabled = !canUseChat || isBusy;
    }
  }

  function refreshComposerContext(state) {
    const target = state.composerContextEl;
    if (!target) return;
    const doc = target.ownerDocument;
    const selectedText = selectedTextForPayload(state);
    const screenshots = screenshotsForPayload(state);
    target.replaceChildren();
    if (!selectedText && !screenshots.length) {
      target.hidden = true;
      return;
    }
    target.hidden = false;
    if (selectedText) {
      const chip = contextPreviewChip(
        doc,
        "选中文本",
        `${selectedText.length} 字`,
        selectedText.slice(0, 280),
        () => {
          state.bucket.selectedText = "";
          setStatus(state, "已移除选中文本");
          refreshComposerContext(state);
        },
      );
      target.appendChild(chip);
    }
    if (screenshots.length) {
      const chip = contextPreviewChip(
        doc,
        "截图",
        `${screenshots.length} 张`,
        "已加入到本次提问",
        () => {
          state.bucket.screenshots = [];
          setStatus(state, "已移除截图");
          refreshComposerContext(state);
        },
      );
      const thumb = el(doc, "img", "rh-zotero-context-thumb");
      thumb.src = screenshots[screenshots.length - 1];
      thumb.alt = "";
      chip.insertBefore(thumb, chip.firstChild);
      target.appendChild(chip);
    }
  }

  function contextPreviewChip(doc, label, value, title, onClear) {
    const chip = el(doc, "div", "rh-zotero-context-preview-chip");
    chip.title = safeString(title);
    const text = el(doc, "span", "rh-zotero-context-preview-text");
    text.append(
      el(doc, "strong", "", label),
      el(doc, "span", "", value),
    );
    const clear = el(doc, "button", "rh-zotero-context-preview-clear", "×");
    clear.type = "button";
    clear.title = `移除${label}`;
    clear.setAttribute("aria-label", `移除${label}`);
    clear.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      onClear?.();
    });
    chip.append(text, clear);
    return chip;
  }

  async function sendToRH({ doc, state }) {
    if (state.bucket.isGenerating) {
      setStatus(state, "上一轮仍在处理中");
      return;
    }
    refreshDirectoryContext(state);
    if (!canChat(state)) {
      setStatus(state, "请先选择论文或目录");
      return;
    }
    const contextMessage = defaultMessageForComposerContext(state);
    const message = (state.inputEl?.value || "").trim() || contextMessage;
    if (!message) {
      setStatus(state, "请输入内容");
      return;
    }

    const userMessage = createTextMessage("user", message, { model: null });
    const assistantMessage = createTextMessage("assistant", "", {
      model: selectedModel(),
      pending: true,
    });
    if (!state.bucket.sessionTitle) {
      state.bucket.sessionTitle = buildSessionTitle(message);
    }
    state.bucket.updatedAt = Date.now();
    state.bucket.messages.push(userMessage, assistantMessage);
    state.bucket.draftText = "";
    state.bucket.uiStatus = "正在生成回复…";
    state.bucket.isGenerating = true;
    if (state.inputEl) {
      state.inputEl.value = "";
      syncTextareaHeight(state.inputEl);
    }
    refreshPanel(state, { focusInput: false });

    try {
      state.bucket.uiStatus = "正在连接本地 Research Harness 服务…";
      refreshHeader(state);
      await ensureResearchHarnessService();
      const payload = {
        message,
        conversation_id: state.bucket.conversationId || undefined,
        model: selectedModel(),
        locale: Zotero.locale || "zh-CN",
        item: await buildItemContext(state),
      };
      const response = await fetch(`${getApiUrl()}/api/zotero/chat/stream`, {
        method: "POST",
        headers: requestHeaders(),
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        throw new Error(detail || `${response.status} ${response.statusText}`);
      }
      clearConsumedComposerContext(state);
      refreshComposer(state);
      if (!response.body?.getReader) {
        throw new Error("当前 Zotero 环境不支持 fetch ReadableStream");
      }
      await readSSEStream(response, (event) => {
        handleStreamEvent({ event, state, assistantMessage });
      });
      if (!assistantMessage.text.trim()) {
        assistantMessage.text = "暂时没有可显示的返回内容，请稍后重试。";
        assistantMessage.pending = false;
        state.bucket.updatedAt = Date.now();
        refreshPanel(state, { focusInput: true });
      }
    } catch (err) {
      assistantMessage.text = `连接 Research Harness 服务失败：${err.message || err}`;
      assistantMessage.pending = false;
      assistantMessage.error = true;
      state.bucket.updatedAt = Date.now();
      state.bucket.uiStatus = "连接失败：请确认 Research Harness 服务已启动";
      refreshPanel(state, { focusInput: true });
    } finally {
      state.bucket.isGenerating = false;
      if (state.bucket.uiStatus === "正在生成回复…") {
        state.bucket.uiStatus = "已完成；上下文已保留";
      }
      refreshPanel(state, { focusInput: true });
    }
  }

  async function ensureResearchHarnessService() {
    const apiUrl = getApiUrl();
    if (!canAutoStartApi(apiUrl)) {
      return { ready: false, reason: "auto-start-disabled" };
    }
    if (await healthCheckResearchHarnessApi(apiUrl)) {
      return { ready: true, started: false };
    }
    if (!serviceStartPromise) {
      serviceStartPromise = (async () => {
        await startResearchHarnessApi(apiUrl);
        const ready = await waitForResearchHarnessApi(apiUrl);
        if (!ready) {
          throw new Error("本地 Research Harness 服务启动后仍未就绪，请检查插件首选项里的仓库路径和 Python 路径。");
        }
        return { ready: true, started: true };
      })();
    }
    try {
      return await serviceStartPromise;
    } finally {
      serviceStartPromise = null;
    }
  }

  async function healthCheckResearchHarnessApi(apiUrl = getApiUrl()) {
    try {
      const response = await fetch(`${apiUrl}/api/health`, {
        method: "GET",
        headers: requestHeaders(false),
      });
      return Boolean(response?.ok);
    } catch (_) {
      return false;
    }
  }

  function canAutoStartApi(apiUrl = getApiUrl()) {
    return autoStartEnabled() && isLoopbackApiUrl(apiUrl) && Boolean(getRepoRoot() && getPythonBin());
  }

  function autoStartEnabled() {
    const value = pref(AUTO_START_PREF);
    if (value === "") {
      return true;
    }
    if (typeof value === "boolean") {
      return value;
    }
    const normalized = String(value).trim().toLowerCase();
    return !["0", "false", "no", "off"].includes(normalized);
  }

  function isLoopbackApiUrl(apiUrl = getApiUrl()) {
    const url = parseApiUrl(apiUrl);
    if (!url || url.protocol !== "http:") {
      return false;
    }
    const host = url.hostname;
    return host === "localhost" || host === "::1" || host === "[::1]" || host.startsWith("127.");
  }

  async function startResearchHarnessApi(apiUrl = getApiUrl()) {
    const Subprocess = loadSubprocessModule();
    if (!Subprocess?.call) {
      throw new Error("当前 Zotero 环境不支持自动启动本地 Research Harness 服务，请手动在仓库根目录运行 python -m research_harness_mcp.http_api。");
    }
    const repoRoot = getRepoRoot();
    if (!repoRoot) {
      throw new Error("请先设置 Zotero 偏好 extensions.researchharness.zotero.repoRoot 为本机 Research Harness 仓库绝对路径，或手动启动本地 Research Harness 服务。");
    }
    const pythonBin = getPythonBin();
    const proc = await Subprocess.call({
      command: pythonBin,
      arguments: ["-m", "research_harness_mcp.http_api"],
      workdir: repoRoot,
      stdout: "pipe",
      stderr: "pipe",
      environment: buildResearchHarnessApiEnv(repoRoot, apiUrl),
      environmentAppend: true,
    });
    serviceProcess = proc;
    drainSubprocessPipe(proc.stdout, "stdout");
    drainSubprocessPipe(proc.stderr, "stderr");
    return proc;
  }

  async function waitForResearchHarnessApi(apiUrl = getApiUrl()) {
    const deadline = Date.now() + SERVICE_START_WAIT_MS;
    while (Date.now() < deadline) {
      if (await healthCheckResearchHarnessApi(apiUrl)) {
        return true;
      }
      await sleep(SERVICE_START_POLL_MS);
    }
    return false;
  }

  function buildResearchHarnessApiEnv(repoRoot, apiUrl = getApiUrl()) {
    const url = parseApiUrl(apiUrl);
    const env = {
      PYTHONUNBUFFERED: "1",
      PYTHONPATH: buildPythonPath(repoRoot),
      RESEARCH_HARNESS_DB_PATH: joinPath(repoRoot, ".research-harness/pool.db"),
      RESEARCH_HARNESS_HTTP_HOST: serverHostFor(url),
      RESEARCH_HARNESS_HTTP_PORT: url?.port || "8000",
    };
    const token = pref(TOKEN_PREF);
    if (token) {
      env.RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN = String(token);
    }
    return env;
  }

  function buildPythonPath(repoRoot) {
    const separator = /^[a-z]:[\\/]/i.test(repoRoot) ? ";" : ":";
    return [
      "packages/research_harness",
      "packages/research_harness_mcp",
      "packages/llm_router",
      "packages/paperindex",
    ].map((path) => joinPath(repoRoot, path)).join(separator);
  }

  function serverHostFor(url) {
    const host = url?.hostname || "127.0.0.1";
    return host === "[::1]" ? "::1" : host;
  }

  function loadSubprocessModule() {
    if (subprocessModule?.call) {
      return subprocessModule;
    }
    const CU = typeof ChromeUtils !== "undefined" ? ChromeUtils : globalThis.ChromeUtils;
    if (CU?.importESModule) {
      try {
        const mod = CU.importESModule("resource://gre/modules/Subprocess.sys.mjs");
        subprocessModule = mod.Subprocess || mod.default || mod;
        if (subprocessModule?.call) {
          return subprocessModule;
        }
      } catch (err) {
        Zotero.debug?.(`RH Zotero Panel: Subprocess.sys.mjs unavailable: ${err}`);
      }
    }
    if (CU?.import) {
      try {
        const mod = CU.import("resource://gre/modules/Subprocess.jsm");
        subprocessModule = mod.Subprocess || mod;
        if (subprocessModule?.call) {
          return subprocessModule;
        }
      } catch (err) {
        Zotero.debug?.(`RH Zotero Panel: Subprocess.jsm unavailable: ${err}`);
      }
    }
    const C = typeof Components !== "undefined" ? Components : globalThis.Components;
    if (C?.utils?.import) {
      try {
        const mod = C.utils.import("resource://gre/modules/Subprocess.jsm", {});
        subprocessModule = mod.Subprocess || mod;
      } catch (err) {
        Zotero.debug?.(`RH Zotero Panel: legacy Subprocess import unavailable: ${err}`);
      }
    }
    return subprocessModule;
  }

  function drainSubprocessPipe(pipe, label) {
    if (!pipe?.readString) {
      return;
    }
    void (async () => {
      try {
        while (true) {
          const chunk = await pipe.readString();
          if (!chunk) {
            break;
          }
          if (label === "stderr") {
            Zotero.debug?.(`RH Zotero Panel service stderr: ${String(chunk).slice(0, 1200)}`);
          }
        }
      } catch (err) {
        Zotero.debug?.(`RH Zotero Panel service ${label} drain stopped: ${err}`);
      }
    })();
  }

  function stopResearchHarnessService() {
    serviceStartPromise = null;
    if (!serviceProcess) {
      return;
    }
    try {
      serviceProcess.kill?.();
    } catch (err) {
      Zotero.debug?.(`RH Zotero Panel: local service stop failed: ${err}`);
    }
    serviceProcess = null;
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function scheduleZoteroCodexWarmup(state) {
    if (!canChat(state)) {
      return;
    }
    scheduleZoteroCodexWarmupForWindow(state.body?.ownerDocument?.defaultView);
  }

  function scheduleZoteroCodexWarmupForWindow(win) {
    if (!win?.setTimeout) {
      return;
    }
    const key = `${getApiUrl()}::${selectedModel()}`;
    const now = Date.now();
    const cooldownUntil = codexWarmupUntil.get(key) || 0;
    if (cooldownUntil > now) {
      return;
    }
    codexWarmupUntil.set(key, now + CODEX_WARMUP_SUCCESS_TTL_MS);
    win.setTimeout(() => {
      void warmUpZoteroCodex(key);
    }, 250);
  }

  async function warmUpZoteroCodex(cacheKey) {
    try {
      await ensureResearchHarnessService();
      const response = await fetch(`${getApiUrl()}/api/zotero/warmup`, {
        method: "POST",
        headers: requestHeaders(),
        body: JSON.stringify({ model: selectedModel() }),
      });
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
    } catch (err) {
      Zotero.debug?.(`RH Zotero Panel: warmup skipped: ${err.message || err}`);
      codexWarmupUntil.set(cacheKey, Date.now() + CODEX_WARMUP_RETRY_MS);
    }
  }

  function handleStreamEvent({ event, state, assistantMessage }) {
    const data = event.data || {};
    if (event.event === "ready") {
      rememberConversation(state.bucket, data.conversation_id);
      if (data.matched) {
        state.bucket.matched = data.matched;
      }
      if (data.context) {
        state.bucket.context = data.context;
      }
      if (Array.isArray(data.available_actions)) {
        state.bucket.availableActions = data.available_actions;
      }
      state.bucket.uiStatus = describeMatch(data.matched);
      state.bucket.updatedAt = Date.now();
      refreshHeader(state);
      refreshContextCard(state);
      return;
    }
    if (event.event === "started") {
      rememberConversation(state.bucket, data.conversation_id || state.bucket.conversationId);
      state.bucket.uiStatus = data.thread_id ? "正在生成回复…" : "正在整理上下文…";
      refreshHeader(state);
      return;
    }
    if (event.event === "status") {
      if (data.status?.message) {
        state.bucket.uiStatus = safeString(data.status.message);
        refreshHeader(state);
      } else if (data.status?.type === "active") {
        state.bucket.uiStatus = "正在接收回复…";
        refreshHeader(state);
      }
      return;
    }
    if (event.event === "action_preview") {
      const previewText = safeString(data.message) || "我为你准备了一份执行预览。";
      assistantMessage.text = previewText;
      assistantMessage.pending = false;
      assistantMessage.model = selectedModel();
      state.bucket.messages.push(createActionPreviewMessage(data));
      state.bucket.updatedAt = Date.now();
      state.bucket.uiStatus = "等待确认…";
      refreshPanel(state, { focusInput: false });
      return;
    }
    if (event.event === "delta") {
      const text = safeString(data.text);
      if (!text) return;
      assistantMessage.text += text;
      assistantMessage.pending = false;
      assistantMessage.model = safeString(data.model || assistantMessage.model || selectedModel());
      state.bucket.updatedAt = Date.now();
      state.bucket.uiStatus = "正在接收回复…";
      updateTextMessageDom(state, assistantMessage);
      refreshHeader(state);
      return;
    }
    if (event.event === "done") {
      rememberConversation(state.bucket, data.conversation_id || state.bucket.conversationId);
      if (data.matched) {
        state.bucket.matched = data.matched;
      }
      if (!assistantMessage.text && data.assistant_message) {
        assistantMessage.text = safeString(data.assistant_message);
      }
      assistantMessage.pending = false;
      assistantMessage.model = safeString(data.model || assistantMessage.model || selectedModel());
      state.bucket.updatedAt = Date.now();
      state.bucket.uiStatus = data.action_preview ? "等待确认…" : "已完成；上下文已保留";
      refreshPanel(state, { focusInput: false });
      return;
    }
    if (event.event === "error") {
      const text = `处理失败：${data.message || "unknown"}`;
      assistantMessage.text = assistantMessage.text
        ? `${assistantMessage.text}\n${text}`
        : text;
      assistantMessage.pending = false;
      assistantMessage.error = true;
      state.bucket.updatedAt = Date.now();
      state.bucket.uiStatus = "处理失败";
      refreshPanel(state, { focusInput: false });
    }
  }

  function renderTextMessage(state, message) {
    const doc = state.chatShellEl.ownerDocument;
    const node = el(doc, "div", `rh-zotero-message ${message.role}`);
    node.dataset.messageId = message.id;
    if (message.pending) {
      node.classList.add("pending");
    }
    if (message.error) {
      node.classList.add("error");
    }

    const meta = el(doc, "div", "rh-zotero-message-meta");
    const author = el(
      doc,
      "span",
      "rh-zotero-message-author",
      message.role === "assistant" ? "RH" : "你",
    );
    const time = el(doc, "span", "rh-zotero-message-time", formatMessageTime(message.timestamp));
    meta.append(author, time);
    if (message.role === "assistant" && message.model) {
      meta.append(el(doc, "span", "rh-zotero-message-model", message.model));
    }
    if (message.role === "assistant" && message.text) {
      const copyBtn = renderIconButton(
        doc,
        "copy",
        "复制回复",
        "rh-zotero-message-copy",
      );
      copyBtn.type = "button";
      copyBtn.addEventListener("click", async (event) => {
        event.stopPropagation();
        const copied = await copyMessageText(state, message.text || "");
        setStatus(state, copied ? "已复制回复" : "复制失败");
      });
      meta.append(copyBtn);
    }

    const bubble = el(doc, "div", "rh-zotero-message-bubble");
    if (message.pending) {
      const loader = el(doc, "span", "rh-zotero-loader");
      loader.setAttribute("aria-hidden", "true");
      loader.append(el(doc, "i"), el(doc, "i"), el(doc, "i"));
      bubble.appendChild(loader);
    }
    const textNode = el(doc, "div", "rh-zotero-message-text");
    textNode.setAttribute("data-rh-selectable", "true");
    renderMessageText(textNode, message);
    if (message.pending && !message.text) {
      textNode.dataset.placeholder = "true";
    }
    keepTextSelectionInsidePanel(node);
    keepTextSelectionInsidePanel(textNode);
    bubble.appendChild(textNode);
    node.append(meta, bubble);
    return node;
  }

  function renderMessageText(textNode, message) {
    const text = safeString(message.text);
    textNode.replaceChildren();
    textNode.classList.toggle("rich", message.role === "assistant" && Boolean(text));
    if (!text) {
      textNode.textContent = message.pending ? "正在生成回复…" : "";
      return;
    }
    if (message.role !== "assistant") {
      textNode.textContent = text;
      return;
    }
    renderAssistantMarkdown(textNode, text);
  }

  function renderAssistantMarkdown(container, text) {
    const doc = container.ownerDocument;
    const lines = safeString(text).replace(/\r\n?/g, "\n").split("\n");
    let paragraphLines = [];
    let listNode = null;
    let listType = "";

    const flushParagraph = () => {
      if (!paragraphLines.length) {
        return;
      }
      const paragraph = doc.createElement("p");
      paragraphLines.forEach((line, index) => {
        if (index > 0) {
          paragraph.appendChild(doc.createElement("br"));
        }
        appendInlineMarkdown(paragraph, line);
      });
      container.appendChild(paragraph);
      paragraphLines = [];
    };

    const closeList = () => {
      listNode = null;
      listType = "";
    };

    for (const line of lines) {
      if (!line.trim()) {
        flushParagraph();
        closeList();
        continue;
      }
      const ordered = line.match(/^\s*\d+[\.)]\s+(.+)$/);
      const unordered = line.match(/^\s*[-•]\s+(.+)$/);
      if (ordered || unordered) {
        flushParagraph();
        const nextType = ordered ? "ol" : "ul";
        if (!listNode || listType !== nextType) {
          listNode = doc.createElement(nextType);
          listType = nextType;
          container.appendChild(listNode);
        }
        const item = doc.createElement("li");
        appendInlineMarkdown(item, ordered ? ordered[1] : unordered[1]);
        listNode.appendChild(item);
        continue;
      }
      closeList();
      paragraphLines.push(line);
    }
    flushParagraph();
    if (!container.childNodes.length) {
      container.textContent = safeString(text);
    }
  }

  function appendInlineMarkdown(target, text) {
    const doc = target.ownerDocument;
    const raw = safeString(text);
    const parts = raw.split("**");
    if (parts.length < 3 || parts.length % 2 === 0) {
      target.appendChild(doc.createTextNode(raw));
      return;
    }
    parts.forEach((part, index) => {
      if (!part) {
        return;
      }
      if (index % 2 === 1) {
        const strong = doc.createElement("strong");
        strong.textContent = part;
        target.appendChild(strong);
        return;
      }
      target.appendChild(doc.createTextNode(part));
    });
  }

  function updateTextMessageDom(state, message) {
    const messageNode = state.rootEl?.querySelector?.(`[data-message-id="${message.id}"]`);
    if (!messageNode) {
      refreshPanel(state, { focusInput: false });
      return;
    }
    const textNode = messageNode.querySelector(".rh-zotero-message-text");
    const loader = messageNode.querySelector(".rh-zotero-loader");
    if (textNode) {
      renderMessageText(textNode, message);
      if (message.text) {
        delete textNode.dataset.placeholder;
      }
    }
    messageNode.classList.toggle("pending", Boolean(message.pending));
    messageNode.classList.toggle("error", Boolean(message.error));
    if (!message.pending) {
      loader?.remove();
    }
    const meta = messageNode.querySelector(".rh-zotero-message-meta");
    if (meta && message.role === "assistant") {
      const existingCopy = meta.querySelector(".rh-zotero-message-copy");
      if (message.text && !existingCopy) {
        const copyBtn = renderIconButton(
          state.rootEl.ownerDocument,
          "copy",
          "复制回复",
          "rh-zotero-message-copy",
        );
        copyBtn.type = "button";
        copyBtn.addEventListener("click", async (event) => {
          event.stopPropagation();
          const copied = await copyMessageText(state, message.text || "");
          setStatus(state, copied ? "已复制回复" : "复制失败");
        });
        meta.appendChild(copyBtn);
      }
      const modelNode = meta.querySelector(".rh-zotero-message-model");
      if (message.model && !modelNode) {
        meta.insertBefore(
          el(state.rootEl.ownerDocument, "span", "rh-zotero-message-model", message.model),
          meta.querySelector(".rh-zotero-message-copy") || null,
        );
      } else if (modelNode) {
        modelNode.textContent = message.model || "";
      }
    }
    queueScrollToBottom(state.messagesEl);
  }

  function renderActionCard(state, message) {
    const doc = state.chatShellEl.ownerDocument;
    const preview = message.preview || {};
    const applySpec = preview.apply || {};
    const records = Array.isArray(preview.records) ? preview.records : [];
    const card = el(doc, "div", "rh-zotero-action-card");
    card.dataset.messageId = message.id;
    if (message.phase) {
      card.classList.add(message.phase);
    }

    const title = el(doc, "div", "rh-zotero-action-title", preview.title || "准备执行");
    const rows = el(doc, "div", "rh-zotero-action-rows");
    rows.append(
      actionRow(doc, "动作", actionTypeLabel(preview)),
      actionRow(doc, "来源", preview.source_label || "Research Harness"),
      actionRow(doc, "目标", actionTargetLabel(preview)),
      actionRow(doc, "计划", formatActionCount(preview)),
    );
    if (preview.filter_label) {
      rows.append(actionRow(doc, "筛选", preview.filter_label));
    }
    if (preview.known_existing_count) {
      rows.append(actionRow(doc, "已存在", formatCount(preview.known_existing_count)));
    }
    if (preview.notice) {
      rows.append(actionNotice(doc, preview.notice));
    }
    if (message.resultSummary) {
      rows.append(actionNotice(doc, message.resultSummary));
    }
    if (message.errorText) {
      rows.append(actionNotice(doc, message.errorText));
    }

    const footer = el(doc, "div", "rh-zotero-action-footer");
    if (message.phase === "idle" || message.phase === "failed") {
      const confirmBtn = button(
        doc,
        safeString(applySpec.label || preview.confirm_label) || "确认执行",
        "primary compact",
      );
      const listBtn = button(
        doc,
        safeString(preview.list_label) || "查看清单",
        "ghost compact",
      );
      const cancelBtn = button(
        doc,
        safeString(preview.cancel_label) || "取消",
        "ghost compact",
      );
      confirmBtn.addEventListener("click", () => {
        void confirmActionPreview({ state, message });
      });
      listBtn.addEventListener("click", () => {
        appendPreviewList(state, message.preview);
      });
      cancelBtn.addEventListener("click", () => {
        message.phase = "cancelled";
        state.bucket.uiStatus = "已取消";
        appendAssistantStoreMessage(state, "已取消这次操作。你可以继续描述新的需求。", { error: false });
        refreshPanel(state, { focusInput: true });
      });
      footer.append(confirmBtn);
      if (records.length) {
        footer.append(listBtn);
      }
      footer.append(cancelBtn);
    } else {
      footer.append(
        el(
          doc,
          "div",
          "rh-zotero-action-state",
          message.phase === "running"
            ? "正在执行…"
            : message.phase === "completed"
              ? "已完成"
              : message.phase === "cancelled"
                ? "已取消"
                : "需要确认",
        ),
      );
    }

    card.append(title, rows, footer);
    return card;
  }

  async function confirmActionPreview({ state, message }) {
    const preview = message.preview || {};
    const applySpec = preview.apply || {};
    refreshDirectoryContext(state);
    message.phase = "running";
    message.errorText = "";
    message.resultSummary = "";
    state.bucket.uiStatus = runningStatusForAction(preview);
    refreshPanel(state, { focusInput: false });
    try {
      const result = await executeActionPreview({ state, preview, applySpec });
      message.phase = "completed";
      message.resultSummary = summarizeActionResult(preview, result);
      state.bucket.uiStatus = completedStatusForAction(preview);
      appendAssistantStoreMessage(
        state,
        message.resultSummary,
      );
    } catch (err) {
      message.phase = "failed";
      message.errorText = `${actionTypeLabel(preview)}失败：${err.message || err}`;
      state.bucket.uiStatus = "执行失败";
    }
    refreshPanel(state, { focusInput: true });
  }

  async function executeActionPreview({ state, preview, applySpec }) {
    const actionType = safeString(applySpec.type);
    if (actionType === "http_json") {
      const method = safeString(applySpec.method || "POST").toUpperCase();
      if (method !== "POST") {
        throw new Error(`不支持的 HTTP action method: ${method}`);
      }
      if (!applySpec.path) {
        throw new Error("后端 action 缺少 apply.path");
      }
      return await postJson(applySpec.path, applySpec.payload || {});
    }
    if (actionType === "zotero_local") {
      return await runZoteroLocalAction(applySpec.handler, applySpec.payload || {}, state);
    }
    throw new Error(`未知 action 类型：${actionType || "empty"}`);
  }

  async function runZoteroLocalAction(handlerName, payload, state) {
    const handler = ZOTERO_LOCAL_ACTION_HANDLERS[safeString(handlerName)];
    if (!handler) {
      throw new Error(`当前插件不支持本地 Zotero handler：${handlerName || "empty"}`);
    }
    return await handler(payload || {}, state);
  }

  async function zoteroImportFileAttachment(payload, state) {
    const pdfPath = safeString(payload.pdf_path);
    const parentItemKey = safeString(payload.parent_item_key);
    const parentLibraryID = safeString(payload.parent_library_id || payload.library_id);
    if (!pdfPath) {
      throw new Error("PDF 附件 action 缺少 pdf_path");
    }
    if (!parentItemKey) {
      throw new Error("PDF 附件 action 缺少 parent_item_key");
    }
    if (payload.replace_existing) {
      throw new Error("replace_existing 尚未开放；请先取消并改用新增附件流程");
    }
    if (!Zotero.Attachments?.importFromFile) {
      throw new Error("当前 Zotero API 不支持 Attachments.importFromFile，无法本地附加 PDF");
    }

    const parentItem = findZoteroItemByKey(parentItemKey, parentLibraryID, state.base);
    if (!parentItem) {
      throw new Error(`未找到 Zotero 父条目 ${parentItemKey}`);
    }
    const parentItemID = parentItem.id || parentItem.itemID;
    if (!parentItemID) {
      throw new Error(`Zotero 父条目 ${parentItemKey} 缺少 itemID`);
    }

    const attachment = await Zotero.Attachments.importFromFile({
      file: pdfPath,
      parentItemID,
      title: safeString(payload.title) || "RH PDF",
      contentType: "application/pdf",
    });
    return {
      status: "success",
      action_type: "zotero_attach_pdf",
      attachment_id: attachment?.id || attachment?.itemID || "",
      attachment_key: attachment?.key || "",
      parent_item_key: parentItemKey,
      title: safeString(attachment?.getField?.("title")) || safeString(payload.title) || "RH PDF",
    };
  }

  function findZoteroItemByKey(itemKey, libraryID, fallbackItem) {
    const key = safeString(itemKey);
    if (!key) return null;
    if (fallbackItem?.key === key) {
      return fallbackItem;
    }
    const candidateLibraryIDs = uniqueStrings([
      libraryID,
      fallbackItem?.libraryID,
      Zotero.Libraries?.userLibraryID,
    ]);
    for (const candidateID of candidateLibraryIDs) {
      try {
        const lookupID = Number(candidateID) || candidateID;
        const item = Zotero.Items?.getByLibraryAndKey?.(lookupID, key);
        if (item) {
          return item;
        }
      } catch (_) {
        // Try the next candidate.
      }
    }
    return null;
  }

  function summarizeActionResult(preview, result) {
    const actionType = safeString(preview.action_type);
    if (actionType === "sync_rh_papers_to_collection") {
      const push = result?.output?.push || {};
      return [
        `已导入到当前文件夹：${actionTargetLabel(preview)}`,
        `新增 ${push.synced_count || 0} 篇，跳过 ${push.skipped_count || 0} 篇。`,
      ].join("\n");
    }
    if (actionType === "zotero_seed_paper_search") {
      const output = result?.output || {};
      return [
        `已为当前文件夹导入起步文献：${actionTargetLabel(preview)}`,
        `主题 #${output.topic_id || preview.topic_id || "?"}，入库 ${output.ingested_count || 0} 篇。`,
      ].join("\n");
    }
    if (actionType === "zotero_attach_pdf") {
      const key = result?.attachment_key ? `（附件 ${result.attachment_key}）` : "";
      return `已附加 PDF 到 ${preview.target_label || "当前 Zotero 条目"}${key}。`;
    }
    return "动作已完成。";
  }

  function actionTargetLabel(preview) {
    return (
      preview.target_label
      || preview.target_collection_path
      || preview.target_collection_name
      || preview.parent_item_key
      || "当前 Zotero 上下文"
    );
  }

  function actionTypeLabel(preview) {
    const actionType = safeString(preview.action_type);
    if (actionType === "sync_rh_papers_to_collection") return "导入当前文件夹";
    if (actionType === "zotero_seed_paper_search") return "推荐起步文献";
    if (actionType === "zotero_attach_pdf") return "PDF 附件";
    return preview.title || "执行动作";
  }

  function formatActionCount(preview) {
    const count = Number(preview.planned_count || 0);
    if (preview.count_label) {
      return `${count} 个 ${preview.count_label}`;
    }
    return formatCount(count);
  }

  function runningStatusForAction(preview) {
    const actionType = safeString(preview.action_type);
    if (actionType === "sync_rh_papers_to_collection") return "正在导入到当前文件夹…";
    if (actionType === "zotero_seed_paper_search") return "正在准备起步文献…";
    if (actionType === "zotero_attach_pdf") return "正在附加 PDF…";
    return "正在执行…";
  }

  function completedStatusForAction(preview) {
    const actionType = safeString(preview.action_type);
    if (actionType === "sync_rh_papers_to_collection") return "导入完成";
    if (actionType === "zotero_seed_paper_search") return "起步文献已导入";
    if (actionType === "zotero_attach_pdf") return "PDF 已附加";
    return "执行完成";
  }

  function appendPreviewList(state, preview) {
    const records = Array.isArray(preview?.records) ? preview.records : [];
    if (!records.length) {
      appendAssistantStoreMessage(state, "这次预览里暂时没有可展示的论文清单。", { error: false });
      refreshPanel(state, { focusInput: false });
      return;
    }
    const lines = records
      .slice(0, 12)
      .map((record, index) => `${index + 1}. ${safeString(record.title || "Untitled")}`);
    if (records.length > 12) {
      lines.push(`……其余 ${records.length - 12} 篇将在确认后一起导入。`);
    }
    appendAssistantStoreMessage(state, lines.join("\n"), { error: false });
    state.bucket.uiStatus = "已展开预览清单";
    refreshPanel(state, { focusInput: false });
  }

  function appendAssistantStoreMessage(state, text, options = {}) {
    state.bucket.messages.push(
      createTextMessage("assistant", text, {
        model: selectedModel(),
        pending: false,
        error: Boolean(options.error),
      }),
    );
    state.bucket.updatedAt = Date.now();
    if (!state.bucket.sessionTitle && text) {
      state.bucket.sessionTitle = buildSessionTitle(text);
    }
  }

  function startNewChat(state) {
    state.bucket.conversationId = "";
    state.bucket.messages = [];
    state.bucket.matched = null;
    state.bucket.sessionTitle = "";
    state.bucket.draftText = "";
    state.bucket.isGenerating = false;
    state.bucket.uiStatus = canChat(state) ? "新对话已就绪" : "请先选择论文";
    refreshPanel(state, { focusInput: true });
  }

  async function readSSEStream(response, onEvent) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const parsed = parseSSEBuffer(buffer);
      buffer = parsed.rest;
      for (const event of parsed.events) {
        onEvent(event);
      }
      if (done) {
        if (buffer.trim()) {
          for (const event of parseSSEBuffer(`${buffer}\n\n`).events) {
            onEvent(event);
          }
        }
        break;
      }
    }
  }

  function parseSSEBuffer(buffer) {
    const normalized = buffer.replace(/\r\n/g, "\n");
    const parts = normalized.split("\n\n");
    const rest = parts.pop() || "";
    const events = parts.map(parseSSEEvent).filter(Boolean);
    return { events, rest };
  }

  function parseSSEEvent(block) {
    let event = "message";
    const dataLines = [];
    for (const rawLine of block.split("\n")) {
      const line = rawLine.trimEnd();
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }
    if (!dataLines.length) return null;
    const rawData = dataLines.join("\n");
    try {
      return { event, data: JSON.parse(rawData) };
    } catch (_) {
      return { event, data: { text: rawData } };
    }
  }

  async function readErrorDetail(response) {
    try {
      const text = await response.text();
      try {
        const json = JSON.parse(text);
        return json?.detail || json?.message || text;
      } catch (_) {
        return text || "";
      }
    } catch (_) {
      return "";
    }
  }

  async function postJson(path, payload) {
    await ensureResearchHarnessService();
    const response = await fetch(`${getApiUrl()}${path}`, {
      method: "POST",
      headers: requestHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new Error(detail || `${response.status} ${response.statusText}`);
    }
    return await response.json();
  }

  function rememberConversation(bucket, conversationId) {
    if (!conversationId || !bucket) return;
    bucket.conversationId = String(conversationId);
  }

  function selectedTextForPayload(state) {
    return normalizeSelectedText(state.bucket?.selectedText || "");
  }

  function screenshotsForPayload(state) {
    const values = Array.isArray(state.bucket?.screenshots) ? state.bucket.screenshots : [];
    return values
      .map((value) => safeString(value).trim())
      .filter((value) => /^data:image\/(?:png|jpe?g|webp);base64,/i.test(value))
      .slice(0, MAX_SCREENSHOTS);
  }

  function composerContextHasPayload(state) {
    return Boolean(selectedTextForPayload(state) || screenshotsForPayload(state).length);
  }

  function defaultMessageForComposerContext(state) {
    if (!composerContextHasPayload(state)) return "";
    const hasText = Boolean(selectedTextForPayload(state));
    const hasScreenshots = screenshotsForPayload(state).length > 0;
    if (hasText && hasScreenshots) return "请结合已加入的选中文本和截图进行分析。";
    if (hasText) return "请解释已加入的选中文本。";
    return "请分析已加入的截图。";
  }

  function clearConsumedComposerContext(state) {
    if (!state?.bucket) return;
    state.bucket.selectedText = "";
    state.bucket.pendingSelectedTextSnapshot = null;
    state.bucket.screenshots = [];
  }

  async function addSelectedTextForNextTurn(state) {
    if (state.bucket.isGenerating) {
      setStatus(state, "正在生成回复…");
      return;
    }
    const text = getActiveSelectionText(state) || consumeSelectionTextSnapshot(state);
    state.bucket.pendingSelectedTextSnapshot = null;
    if (!text) {
      setStatus(state, "请先在 PDF 或 Zotero 笔记中选中文本");
      return;
    }
    state.bucket.selectedText = text;
    setStatus(state, `已加入选中文本（${text.length} 字）`);
    refreshComposerContext(state);
    state.inputEl?.focus?.({ preventScroll: true });
  }

  function cacheSelectionForNextTextTurn(state) {
    if (!state?.bucket || state.bucket.isGenerating) return;
    const text = getActiveSelectionText(state);
    state.bucket.pendingSelectedTextSnapshot = text
      ? { text, capturedAt: Date.now() }
      : null;
  }

  function consumeSelectionTextSnapshot(state) {
    const snapshot = state.bucket?.pendingSelectedTextSnapshot;
    const text = normalizeSelectedText(snapshot?.text || "");
    const capturedAt = Number(snapshot?.capturedAt || 0);
    if (!text || !Number.isFinite(capturedAt)) return "";
    if (Date.now() - capturedAt > 5000) return "";
    return text;
  }

  function getActiveSelectionText(state) {
    const doc = state.body?.ownerDocument;
    const win = doc?.defaultView;
    const reader = getActiveReaderForSelectedTab(win);
    const fromReader = getFirstSelectionFromReader(reader);
    if (fromReader) return fromReader;

    const docs = [];
    const seen = new Set();
    pushUniqueDocument(docs, seen, doc);
    pushUniqueDocument(docs, seen, win?.top?.document);
    pushUniqueDocument(docs, seen, Zotero.getMainWindow?.()?.document);
    for (const candidateDoc of docs) {
      const text = getSelectionFromDocument(candidateDoc);
      if (text) return text;
      const iframes = safeArray(() => Array.from(candidateDoc.querySelectorAll("iframe")));
      for (const frame of iframes) {
        const frameText = getSelectionFromDocument(frame.contentDocument);
        if (frameText) return frameText;
      }
    }
    return "";
  }

  function getActiveReaderForSelectedTab(win) {
    const tabs = getZoteroTabsState(win);
    const selectedTabId = tabs?.selectedID;
    if (selectedTabId === undefined || selectedTabId === null) {
      return null;
    }
    try {
      return Zotero.Reader?.getByTabID?.(selectedTabId) || null;
    } catch (_) {
      return null;
    }
  }

  function getZoteroTabsState(win) {
    const candidates = [
      Zotero.Tabs,
      win?.Zotero?.Tabs,
      win?.Zotero_Tabs,
      win?.top?.Zotero?.Tabs,
      win?.top?.Zotero_Tabs,
      Zotero.getMainWindow?.()?.Zotero?.Tabs,
      Zotero.getMainWindow?.()?.Zotero_Tabs,
    ];
    for (const candidate of candidates) {
      if (candidate && typeof candidate === "object" && ("selectedID" in candidate || "selectedType" in candidate || Array.isArray(candidate._tabs))) {
        return candidate;
      }
    }
    return null;
  }

  function collectReaderSelectionDocuments(reader) {
    const docs = [];
    const seen = new Set();
    pushUniqueDocument(docs, seen, reader?._iframeWindow?.document);
    pushUniqueDocument(docs, seen, reader?._iframe?.contentDocument);
    pushUniqueDocument(docs, seen, reader?._window?.document);
    const internalReader = reader?._internalReader;
    const views = [internalReader?._primaryView, internalReader?._secondaryView, internalReader?._lastView];
    for (const view of views) {
      pushUniqueDocument(docs, seen, view?._iframeWindow?.document);
      pushUniqueDocument(docs, seen, view?._iframe?.contentDocument);
    }
    return docs;
  }

  function getFirstSelectionFromReader(reader) {
    for (const doc of collectReaderSelectionDocuments(reader)) {
      const text = getSelectionFromDocument(doc);
      if (text) return text;
    }
    return "";
  }

  function getSelectionFromDocument(doc) {
    try {
      return normalizeSelectedText(doc?.defaultView?.getSelection?.()?.toString?.() || "");
    } catch (_) {
      return "";
    }
  }

  function pushUniqueDocument(target, seen, doc) {
    if (!doc || seen.has(doc)) return;
    seen.add(doc);
    target.push(doc);
  }

  function normalizeSelectedText(value) {
    return safeString(value)
      .replace(/\u00ad/g, "")
      .replace(/[ \t\r\f\v]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim()
      .slice(0, MAX_SELECTED_TEXT_CHARS);
  }

  async function captureScreenshotForNextTurn(state) {
    if (state.bucket.isGenerating) {
      setStatus(state, "正在生成回复…");
      return;
    }
    const current = screenshotsForPayload(state);
    if (current.length >= MAX_SCREENSHOTS) {
      setStatus(state, `最多加入 ${MAX_SCREENSHOTS} 张截图`);
      return;
    }
    const win = Zotero.getMainWindow?.() || state.body?.ownerDocument?.defaultView?.top || state.body?.ownerDocument?.defaultView;
    if (!win?.document) {
      setStatus(state, "无法访问 Zotero 窗口");
      return;
    }
    setStatus(state, "拖拽选择截图区域");
    const dataUrl = await captureScreenshotSelection(win);
    if (!dataUrl) {
      setStatus(state, "已取消截图");
      return;
    }
    const optimized = await optimizeScreenshotDataUrl(win, dataUrl);
    if (!optimized || optimized.length > MAX_SCREENSHOT_DATA_URL_LENGTH) {
      setStatus(state, "截图过大，请选择更小区域");
      return;
    }
    state.bucket.screenshots = [...current, optimized].slice(0, MAX_SCREENSHOTS);
    setStatus(state, `已加入截图（${state.bucket.screenshots.length}/${MAX_SCREENSHOTS}）`);
    refreshComposerContext(state);
    state.inputEl?.focus?.({ preventScroll: true });
  }

  function captureScreenshotSelection(win) {
    return new Promise((resolve) => {
      const doc = win.document;
      const container = doc.body || doc.documentElement;
      if (!container) {
        resolve(null);
        return;
      }
      const overlay = doc.createElementNS(HTML_NS, "div");
      overlay.className = "rh-zotero-capture-overlay";
      const instructions = doc.createElementNS(HTML_NS, "div");
      instructions.className = "rh-zotero-capture-instructions";
      instructions.textContent = "拖拽选择需要加入提问的区域";
      const cancel = doc.createElementNS(HTML_NS, "button");
      cancel.className = "rh-zotero-capture-cancel";
      cancel.type = "button";
      cancel.textContent = "取消 Esc";
      const selection = doc.createElementNS(HTML_NS, "div");
      selection.className = "rh-zotero-capture-selection";
      overlay.append(instructions, cancel, selection);
      container.appendChild(overlay);

      let startX = 0;
      let startY = 0;
      let selecting = false;
      let finished = false;
      const cleanup = () => {
        overlay.remove();
        doc.removeEventListener("keydown", onKeyDown, true);
      };
      const finish = (value) => {
        if (finished) return;
        finished = true;
        cleanup();
        resolve(value);
      };
      const onKeyDown = (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          finish(null);
        }
      };
      doc.addEventListener("keydown", onKeyDown, true);
      cancel.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        finish(null);
      });
      overlay.addEventListener("mousedown", (event) => {
        if (event.target === cancel) return;
        event.preventDefault();
        event.stopPropagation();
        selecting = true;
        startX = event.clientX;
        startY = event.clientY;
        updateCaptureSelection(selection, startX, startY, startX, startY);
      });
      overlay.addEventListener("mousemove", (event) => {
        if (!selecting) return;
        event.preventDefault();
        updateCaptureSelection(selection, startX, startY, event.clientX, event.clientY);
      });
      overlay.addEventListener("mouseup", async (event) => {
        if (!selecting) return;
        event.preventDefault();
        event.stopPropagation();
        selecting = false;
        const left = Math.min(startX, event.clientX);
        const top = Math.min(startY, event.clientY);
        const width = Math.abs(event.clientX - startX);
        const height = Math.abs(event.clientY - startY);
        if (width < 20 || height < 20) {
          finish(null);
          return;
        }
        prepareCaptureOverlayForSnapshot(win, overlay, instructions, cancel, selection);
        await waitForNextFrame(win);
        const dataUrl = await captureRegion(win, left, top, width, height);
        finish(dataUrl);
      });
    });
  }

  function prepareCaptureOverlayForSnapshot(win, overlay, instructions, cancel, selection) {
    overlay.classList.add("capturing");
    overlay.style.background = "transparent";
    overlay.style.pointerEvents = "none";
    instructions.hidden = true;
    cancel.hidden = true;
    selection.style.display = "none";
  }

  function waitForNextFrame(win) {
    return new Promise((resolve) => {
      const done = () => resolve();
      const scheduleMacrotask = () => {
        if (typeof win?.setTimeout === "function") {
          win.setTimeout(done, 0);
          return;
        }
        setTimeout(done, 0);
      };
      if (typeof win?.requestAnimationFrame === "function") {
        win.requestAnimationFrame(scheduleMacrotask);
        return;
      }
      scheduleMacrotask();
    });
  }

  function updateCaptureSelection(selection, startX, startY, currentX, currentY) {
    const left = Math.min(startX, currentX);
    const top = Math.min(startY, currentY);
    const width = Math.abs(currentX - startX);
    const height = Math.abs(currentY - startY);
    Object.assign(selection.style, {
      display: "block",
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      height: `${height}px`,
    });
  }

  async function captureRegion(win, x, y, width, height) {
    const canvasHit = findBestCanvasForRegion(win, x, y, width, height);
    if (canvasHit) {
      const { canvas, rect, intersection } = canvasHit;
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      const srcX = Math.max(0, (intersection.left - rect.left) * scaleX);
      const srcY = Math.max(0, (intersection.top - rect.top) * scaleY);
      const srcWidth = Math.min(intersection.width * scaleX, canvas.width - srcX);
      const srcHeight = Math.min(intersection.height * scaleY, canvas.height - srcY);
      const out = win.document.createElementNS(HTML_NS, "canvas");
      out.width = Math.max(1, Math.floor(srcWidth));
      out.height = Math.max(1, Math.floor(srcHeight));
      const ctx = out.getContext("2d");
      if (ctx) {
        ctx.drawImage(canvas, srcX, srcY, srcWidth, srcHeight, 0, 0, out.width, out.height);
        return out.toDataURL("image/png");
      }
    }
    return fallbackWindowCapture(win, x, y, width, height);
  }

  function findBestCanvasForRegion(win, x, y, width, height) {
    const region = { left: x, top: y, right: x + width, bottom: y + height, width, height };
    let best = null;
    for (const entry of canvasDocumentEntries(win)) {
      const canvases = safeArray(() => Array.from(entry.doc.querySelectorAll(".pdfViewer canvas, .canvasWrapper canvas, canvas")));
      for (const canvas of canvases) {
        const local = canvas.getBoundingClientRect();
        const rect = {
          left: entry.offsetX + local.left,
          top: entry.offsetY + local.top,
          right: entry.offsetX + local.right,
          bottom: entry.offsetY + local.bottom,
          width: local.width,
          height: local.height,
        };
        const intersection = intersectRects(region, rect);
        const area = intersection ? intersection.width * intersection.height : 0;
        if (area > (best?.area || 0)) {
          best = { canvas, rect, intersection, area };
        }
      }
    }
    return best?.area ? best : null;
  }

  function canvasDocumentEntries(win) {
    const entries = [{ doc: win.document, offsetX: 0, offsetY: 0 }];
    const iframes = safeArray(() => Array.from(win.document.querySelectorAll("iframe")));
    for (const frame of iframes) {
      try {
        if (!frame.contentDocument) continue;
        const rect = frame.getBoundingClientRect();
        entries.push({ doc: frame.contentDocument, offsetX: rect.left, offsetY: rect.top });
      } catch (_) {
        // Ignore inaccessible frames.
      }
    }
    return entries;
  }

  function intersectRects(a, b) {
    const left = Math.max(a.left, b.left);
    const top = Math.max(a.top, b.top);
    const right = Math.min(a.right, b.right);
    const bottom = Math.min(a.bottom, b.bottom);
    if (right <= left || bottom <= top) return null;
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  }

  function fallbackWindowCapture(win, x, y, width, height) {
    try {
      const canvas = win.document.createElementNS(HTML_NS, "canvas");
      canvas.width = Math.max(1, Math.floor(width));
      canvas.height = Math.max(1, Math.floor(height));
      const ctx = canvas.getContext("2d");
      if (ctx && typeof ctx.drawWindow === "function") {
        ctx.drawWindow(win, x, y, width, height, "white");
        return canvas.toDataURL("image/png");
      }
    } catch (err) {
      Zotero.debug(`RH Zotero Panel: screenshot fallback failed: ${err}`);
    }
    return null;
  }

  async function optimizeScreenshotDataUrl(win, dataUrl) {
    if (!dataUrl || dataUrl.length <= MAX_SCREENSHOT_DATA_URL_LENGTH) {
      return dataUrl;
    }
    try {
      const img = await loadImageFromDataUrl(win, dataUrl);
      const scale = Math.min(1, 1400 / Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height));
      const canvas = win.document.createElementNS(HTML_NS, "canvas");
      canvas.width = Math.max(1, Math.floor((img.naturalWidth || img.width) * scale));
      canvas.height = Math.max(1, Math.floor((img.naturalHeight || img.height) * scale));
      const ctx = canvas.getContext("2d");
      if (!ctx) return dataUrl;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", 0.86);
    } catch (err) {
      Zotero.debug(`RH Zotero Panel: screenshot optimize failed: ${err}`);
      return dataUrl;
    }
  }

  function loadImageFromDataUrl(win, dataUrl) {
    return new Promise((resolve, reject) => {
      const img = new win.Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image decode failed"));
      img.src = dataUrl;
    });
  }

  function safeArray(factory) {
    try {
      return factory() || [];
    } catch (_) {
      return [];
    }
  }

  async function buildItemContext(state) {
    const item = state.item;
    const base = state.base;
    const directory = state.directory;
    const libraryID = safeString(base?.libraryID || item?.libraryID || directory.libraryID);
    return {
      zotero_item_key: safeString(base?.key || item?.key),
      library_id: libraryID,
      library_type: libraryTypeFor(libraryID, directory.libraryType || "user"),
      title: getField(base, "title"),
      creators: creatorsFor(base),
      year: yearFromItem(base),
      doi: getField(base, "DOI"),
      arxiv_id: arxivFromItem(base),
      url: getField(base, "url"),
      abstract: getField(base, "abstractNote"),
      extra: getField(base, "extra"),
      tags: tagsFor(base),
      selected_text: selectedTextForPayload(state),
      note_text: "",
      screenshots: screenshotsForPayload(state),
      current_directory_key: directory.key,
      current_directory_name: directory.name,
      current_directory_path: directory.path,
    };
  }

  function ensureConversationEntry(key) {
    let entry = conversationStore.get(key);
    if (!entry) {
      entry = {
        key,
        conversationId: "",
        messages: [],
        matched: null,
        sessionTitle: "",
        draftText: "",
        context: null,
        availableActions: [],
        uiStatus: "",
        isGenerating: false,
        selectedText: "",
        pendingSelectedTextSnapshot: null,
        screenshots: [],
        lastKnownItem: "",
        updatedAt: Date.now(),
      };
      conversationStore.set(key, entry);
    }
    return entry;
  }

  function createTextMessage(role, text, options = {}) {
    return {
      id: `message-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type: "text",
      role,
      text: safeString(text),
      timestamp: Date.now(),
      model: options.model || null,
      pending: Boolean(options.pending),
      error: Boolean(options.error),
    };
  }

  function createActionPreviewMessage(preview) {
    return {
      id: `action-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type: "action",
      preview,
      phase: "idle",
      errorText: "",
      resultSummary: "",
      timestamp: Date.now(),
    };
  }

  function bucketStatusText(bucket) {
    return safeString(bucket?.uiStatus) || "就绪";
  }

  function contextHeadline(state) {
    if (state.base) {
      return getField(state.base, "title") || "当前论文";
    }
    return directoryLabel(state.directory);
  }

  function contextMetaLine(state, matched) {
    const bits = [];
    if (state.base) {
      const creators = compactCreators(creatorsFor(state.base));
      const year = yearFromItem(state.base);
      if (creators) bits.push(creators);
      if (year) bits.push(String(year));
      if (state.directory?.name) bits.push(`目录：${directoryLabel(state.directory)}`);
    } else if (state.directory?.name) {
      bits.push(`目录：${directoryLabel(state.directory)}`);
    }
    const matchedTopic = formatTopicLabel(matched?.topic?.name);
    if (matchedTopic) {
      bits.push(`研究主题：${matchedTopic}`);
    }
    if (state.bucket?.sessionTitle) {
      bits.push(`会话：${state.bucket.sessionTitle}`);
    }
    if (state.bucket?.messages?.length) {
      bits.push(`${state.bucket.messages.length} 条消息`);
    }
    return bits.join(" · ") || "暂无更多上下文信息";
  }

  function resolveBaseItem(item) {
    if (!item) return null;
    try {
      if (item.isAttachment?.() && item.parentItemID) {
        return Zotero.Items.get(item.parentItemID) || item;
      }
      if (item.isAttachment?.() && item.parentID) {
        return Zotero.Items.get(item.parentID) || item;
      }
    } catch (_) {
      return item;
    }
    return item;
  }

  function getCurrentDirectoryContext(win) {
    const mainWin = Zotero.getMainWindow?.() || win;
    const pane = mainWin?.ZoteroPane;
    const context = {
      key: "",
      name: "",
      path: "",
      libraryID: "",
      libraryType: "user",
    };
    try {
      const collection = pane?.getSelectedCollection?.();
      if (collection) {
        context.key = safeString(collection.key);
        context.name = safeString(collection.name);
        context.path = collectionPath(collection);
        context.libraryID = safeString(collection.libraryID);
        context.libraryType = libraryTypeFor(collection.libraryID, context.libraryType);
        return context;
      }
    } catch (_) {
      // ignore
    }
    try {
      const libraryID = pane?.getSelectedLibraryID?.();
      if (libraryID !== undefined && libraryID !== null) {
        context.libraryID = safeString(libraryID);
        context.libraryType = libraryTypeFor(libraryID, context.libraryType);
        const libraryName = libraryNameFor(libraryID);
        context.name = libraryName || "我的文库";
        context.path = libraryName || "我的文库";
      }
    } catch (_) {
      // ignore
    }
    return context;
  }

  function collectionPath(collection) {
    const names = [safeString(collection?.name)];
    try {
      let parentID = collection?.parentID || collection?.parentCollectionID || 0;
      while (parentID) {
        const parent = Zotero.Collections?.get?.(parentID);
        if (!parent) break;
        names.unshift(safeString(parent.name));
        parentID = parent.parentID || parent.parentCollectionID || 0;
      }
    } catch (_) {
      // ignore
    }
    return names.filter(Boolean).join(" / ");
  }

  function conversationKeyFor(item, directory) {
    if (item) {
      return [safeString(item.libraryID), safeString(item.key), getField(item, "title")]
        .filter(Boolean)
        .join(":");
    }
    return [safeString(directory.libraryID), safeString(directory.key), directory.path || directory.name]
      .filter(Boolean)
      .join(":");
  }

  function canChat(state) {
    return Boolean(state.base || state.directory.name);
  }

  function refreshDirectoryContext(state) {
    const win = state.body?.ownerDocument?.defaultView || state.rootEl?.ownerDocument?.defaultView;
    state.directory = getCurrentDirectoryContext(win);
    refreshContextCard(state);
    refreshComposer(state);
    return state.directory;
  }

  function libraryTypeFor(libraryID, fallback = "user") {
    const fallbackType = fallback === "group" ? "group" : "user";
    const normalizedID = safeString(libraryID);
    try {
      const lookupID = Number(normalizedID) || normalizedID;
      const library = Zotero.Libraries?.get?.(lookupID);
      const rawType = safeString(library?.libraryType || library?.type).toLowerCase();
      if (rawType === "group" || rawType === "user") {
        return rawType;
      }
      if (library?.isGroup) {
        return "group";
      }
      const userLibraryID = safeString(Zotero.Libraries?.userLibraryID);
      if (normalizedID && userLibraryID && normalizedID !== userLibraryID) {
        return "group";
      }
    } catch (_) {
      // Fall through to fallback type.
    }
    return fallbackType;
  }

  function libraryNameFor(libraryID) {
    try {
      const lookupID = Number(libraryID) || libraryID;
      return safeString(Zotero.Libraries?.get?.(lookupID)?.name);
    } catch (_) {
      return "";
    }
  }

  function directoryLabel(directory) {
    return directory.path || directory.name || "未选择文件夹";
  }

  function rhStatusLabel(state, matched) {
    if (matched?.paper) {
      const topic = formatTopicLabel(matched.topic?.name);
      const topicName = topic ? ` · ${topic}` : "";
      return `${matched.paper.deep_read ? "已精读" : "已接入 Research Harness"}${topicName}`;
    }
    const tags = tagsFor(state.base);
    const topic = formatTopicLabel(tagValue(tags, "rh-topic:"));
    const hasPaper = Boolean(tagValue(tags, "rh-paper-id:"));
    const hasDeepRead = tags.includes("rh-deep-read");
    if (hasDeepRead) {
      return topic ? `已精读 · ${topic}` : "已精读";
    }
    if (hasPaper) {
      return topic ? `已接入 Research Harness · ${topic}` : "已接入 Research Harness";
    }
    return state.base ? "未接入 Research Harness" : "等待匹配";
  }

  function compactCreators(creators) {
    if (!creators.length) return "";
    if (creators.length === 1) return creators[0];
    return `${creators[0]} et al.`;
  }

  function tagValue(tags, prefix) {
    const tag = tags.find((value) => String(value).startsWith(prefix));
    return tag ? String(tag).slice(prefix.length) : "";
  }

  function describeMatch(match) {
    if (!match?.paper) {
      return "正在仅使用当前上下文回答";
    }
    const topicLabel = formatTopicLabel(match.topic?.name);
    const topic = topicLabel ? ` · ${topicLabel}` : "";
    return `已连接文献 #${match.paper.id}${topic}`;
  }

  function formatTopicLabel(value) {
    const raw = safeString(value).trim();
    if (!raw) {
      return "";
    }
    if (/[\u4e00-\u9fff]/.test(raw)) {
      return raw;
    }
    const normalized = raw.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
    if (!normalized) {
      return "";
    }
    const shouldTitleCase = raw === raw.toUpperCase() || /[_-]/.test(raw);
    if (!shouldTitleCase) {
      return normalized;
    }
    return normalized
      .toLowerCase()
      .split(" ")
      .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : ""))
      .join(" ");
  }

  function formatCount(value) {
    const number = Number(value || 0);
    return `${number} 篇`;
  }

  function actionRow(doc, label, value) {
    const row = el(doc, "div", "rh-zotero-action-row");
    row.append(
      el(doc, "span", "rh-zotero-action-label", label),
      el(doc, "span", "rh-zotero-action-value", safeString(value)),
    );
    return row;
  }

  function actionNotice(doc, text) {
    return el(doc, "div", "rh-zotero-action-notice", text);
  }

  function getApiUrl() {
    const raw = pref(API_URL_PREF) || DEFAULT_API_URL;
    return String(raw).replace(/\/+$/, "");
  }

  function parseApiUrl(apiUrl) {
    try {
      return new URL(apiUrl);
    } catch (_) {
      return null;
    }
  }

  function getRepoRoot() {
    return normalizePath(safeString(pref(REPO_ROOT_PREF)).trim() || DEFAULT_REPO_ROOT);
  }

  function getPythonBin() {
    const configured = normalizePath(safeString(pref(PYTHON_BIN_PREF)).trim());
    if (configured) {
      return configured;
    }
    const repoRoot = getRepoRoot();
    if (repoRoot) {
      return joinPath(repoRoot, ".venv/bin/python");
    }
    return "python3";
  }

  function normalizePath(path) {
    const value = safeString(path).trim();
    if (!value) {
      return "";
    }
    if (/^[a-z]:[\\/]?$/i.test(value) || value === "/") {
      return value;
    }
    return value.replace(/[\\/]+$/, "");
  }

  function joinPath(base, child) {
    const root = normalizePath(base);
    const suffix = safeString(child).replace(/^[\\/]+/, "");
    if (!root) {
      return suffix;
    }
    const separator = /^[a-z]:/i.test(root) || root.includes("\\") ? "\\" : "/";
    return `${root}${root.endsWith("/") || root.endsWith("\\") ? "" : separator}${suffix}`;
  }

  function selectedModel() {
    const value = safeString(pref(MODEL_PREF));
    return MODEL_OPTIONS.includes(value) ? value : DEFAULT_MODEL;
  }

  function requestHeaders(includeJson = true) {
    const headers = includeJson ? { "Content-Type": "application/json" } : {};
    const token = pref(TOKEN_PREF);
    if (token) {
      headers["X-RH-Zotero-Token"] = String(token);
    }
    return headers;
  }

  function pref(key) {
    try {
      const value = Zotero.Prefs.get(key, true);
      return value === undefined || value === null ? "" : value;
    } catch (_) {
      return "";
    }
  }

  function getField(item, field) {
    try {
      return safeString(item?.getField?.(field));
    } catch (_) {
      return "";
    }
  }

  function creatorsFor(item) {
    try {
      return (item?.getCreators?.() || [])
        .map((creator) => {
          const firstName = creator.firstName || "";
          const lastName = creator.lastName || "";
          const name = creator.name || `${firstName} ${lastName}`;
          return name.trim();
        })
        .filter(Boolean);
    } catch (_) {
      return [];
    }
  }

  function tagsFor(item) {
    try {
      return (item?.getTags?.() || [])
        .map((tag) => tag.tag || tag.name || tag)
        .filter(Boolean);
    } catch (_) {
      return [];
    }
  }

  function yearFromItem(item) {
    const date = getField(item, "date");
    const match = String(date).match(/\b(19|20)\d{2}\b/);
    return match ? Number(match[0]) : null;
  }

  function arxivFromItem(item) {
    const extra = `${getField(item, "extra")}\n${getField(item, "url")}`;
    const match = extra.match(/(?:arxiv[:\s/]+|abs\/)(\d{4}\.\d{4,5}(?:v\d+)?)/i);
    return match ? match[1] : "";
  }

  function formatMessageTime(timestamp) {
    try {
      return new Date(timestamp).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return "";
    }
  }

  function buildSessionTitle(text) {
    const normalized = safeString(text).replace(/\s+/g, " ").trim();
    if (!normalized) return "未命名会话";
    return normalized.length > 28 ? `${normalized.slice(0, 28)}…` : normalized;
  }

  async function copyMessageText(state, text) {
    const doc = state.rootEl?.ownerDocument;
    const win = doc?.defaultView;
    try {
      if (win?.navigator?.clipboard?.writeText) {
        await win.navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {
      // fallback
    }
    try {
      const textarea = doc.createElementNS(HTML_NS, "textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      textarea.style.pointerEvents = "none";
      doc.documentElement.appendChild(textarea);
      textarea.select();
      const success = doc.execCommand?.("copy");
      textarea.remove();
      return Boolean(success);
    } catch (_) {
      return false;
    }
  }

  function syncTextareaHeight(textarea) {
    if (!textarea) return;
    textarea.style.height = "auto";
    const next = Math.max(52, Math.min(textarea.scrollHeight, 132));
    textarea.style.height = `${next}px`;
  }

  function queueScrollToBottom(node) {
    if (!node) return;
    node.scrollTop = node.scrollHeight;
    node.ownerDocument?.defaultView?.requestAnimationFrame?.(() => {
      node.scrollTop = node.scrollHeight;
    });
  }

  function keepTextEditingInsidePanel(node) {
    const stopOnly = (event) => event.stopPropagation();
    [
      "mousedown",
      "mouseup",
      "click",
      "dblclick",
      "select",
      "selectstart",
      "copy",
      "cut",
      "paste",
      "keydown",
      "keyup",
    ].forEach((eventName) => {
      node.addEventListener(eventName, stopOnly);
    });
  }

  function keepTextSelectionInsidePanel(node) {
    const stopOnly = (event) => event.stopPropagation();
    [
      "mousedown",
      "mouseup",
      "click",
      "dblclick",
      "select",
      "selectstart",
      "copy",
      "contextmenu",
    ].forEach((eventName) => {
      node.addEventListener(eventName, stopOnly);
    });
  }

  function setStatus(state, text) {
    state.bucket.uiStatus = safeString(text) || "就绪";
    if (state.statusTextEl) {
      state.statusTextEl.textContent = state.bucket.uiStatus;
    }
  }

  function setGenerating(state, generating) {
    if (state.statusEl) {
      state.statusEl.classList.toggle("generating", Boolean(generating));
    }
  }

  function button(doc, text, variant) {
    const node = el(doc, "button", `rh-zotero-button ${variant || ""}`.trim(), text);
    node.type = "button";
    return node;
  }

  function renderIconButton(doc, name, label, className = "") {
    const node = doc.createElement("button");
    node.className = className;
    node.type = "button";
    node.title = label;
    node.setAttribute("aria-label", label);
    node.append(svgIcon(doc, name));
    return node;
  }

  function svgIcon(doc, name) {
    const svg = doc.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "rh-zotero-icon");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.8");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");

    const defs = {
      plus: [
        ["path", { d: "M12 5v14" }],
        ["path", { d: "M5 12h14" }],
      ],
      send: [["path", { d: "M4 11.5L20 4l-4.5 16-3.5-6L4 11.5Z" }]],
      copy: [
        ["rect", { x: "9", y: "9", width: "10", height: "10", rx: "2" }],
        ["path", { d: "M7 15H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v1" }],
      ],
      text: [
        ["path", { d: "M5 6h14" }],
        ["path", { d: "M7 10h10" }],
        ["path", { d: "M7 14h8" }],
        ["path", { d: "M5 18h6" }],
      ],
      camera: [
        ["path", { d: "M8 7l1.3-2h5.4L16 7h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3Z" }],
        ["circle", { cx: "12", cy: "13", r: "3" }],
      ],
    };

    for (const [tag, attrs] of defs[name] || defs.plus) {
      const child = doc.createElementNS(SVG_NS, tag);
      Object.entries(attrs).forEach(([key, value]) => child.setAttribute(key, value));
      svg.appendChild(child);
    }
    return svg;
  }

  function el(doc, tag, className = "", text = "") {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function createXulElement(doc, tag) {
    if (typeof doc.createXULElement === "function") {
      return doc.createXULElement(tag);
    }
    return doc.createElement(tag);
  }

  function safeString(value) {
    return value === undefined || value === null ? "" : String(value);
  }

  function uniqueStrings(values) {
    const seen = new Set();
    const result = [];
    for (const value of values || []) {
      const text = safeString(value).trim();
      if (!text || seen.has(text)) continue;
      seen.add(text);
      result.push(text);
    }
    return result;
  }

  const api = {
    startup,
    shutdown,
    onMainWindowLoad,
    onMainWindowUnload,
  };
  return api;
})();
