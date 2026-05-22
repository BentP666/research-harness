# Zotero 集成

Research Harness 的 Zotero 集成目标是让 Zotero 成为本地文献入口，同时由 RH 管理 topic、paper、note、tag、provenance 和 Codex handoff。

## 当前定位

RH 采用 **RH-owned thin Zotero plugin** 思路：

- Zotero 插件只负责读取当前选中文献、展示 RH 面板、把问题发给本地 RH API。
- RH 后端负责 paper/topic 匹配、Zotero sync、精读卡片、标签、provenance 和后续 Codex handoff。
- 不直接把完整研究语义塞进 Zotero 插件，避免 Zotero 端过重。

## 启动 RH 本地 API

```bash
PYTHONPATH=packages/research_harness:packages/research_harness_mcp:packages/llm_router \
python -m research_harness_mcp.http_api
```

默认地址：

```text
http://127.0.0.1:8000
```

可选 token：

```bash
export RESEARCH_HARNESS_ZOTERO_CHAT_TOKEN="choose-a-local-token"
```

如果设置了 token，Zotero 侧也需要将 `extensions.researchharness.zotero.token` 设为同值。

## 当前可用形态

首版中文文档先记录 RH 对 Zotero 的集成方向和操作边界。具体能力会分两层逐步发布：

1. **资源同步层**：把 RH paper、topic、精读卡片、标签同步到 Zotero，并从 Zotero 拉回人工笔记和高亮。
2. **侧边面板层**：在 Zotero 中显示 `Research Harness` 面板，把当前选中文献上下文发送给本地 RH API，并生成可交给 Codex 的 handoff prompt。

如果你的 checkout 已经包含 Zotero panel 集成代码，可以按对应分支或 release note 的安装说明构建 XPI；在相关代码合并到公开主线后，本页会补充稳定安装步骤。

## 预期交互

选中 RH 已同步到 Zotero 的论文后，Zotero 面板可以询问：

```text
这篇论文对自动科研主题有什么启发？
```

RH 应返回：

- 是否匹配到对应 paper/topic；
- 简洁中文回答；
- 可复制给 Codex 的 handoff prompt；
- 后续可追溯到 RH artifact / provenance 的处理结果。

## 与 llm-for-zotero 的关系

[`llm-for-zotero`](https://github.com/yilewang/llm-for-zotero) 是成熟的 Zotero AI 插件，可作为 UI、侧边栏、Codex App Server、Agent Mode 的参考。但 RH 当前不直接 fork 它，而是保留 RH 后端作为科研状态和 provenance 的唯一事实来源。

## 后续计划

- 将 Zotero 选中文本、笔记和高亮导入 RH artifact。
- 将 Zotero 中的人工反馈同步回 RH topic 状态。
- 为批量同步、精读卡片、标签规范补充更细的中文操作页。
