# Research Harness 中文文档

Research Harness 是面向长周期 AI 科研 Agent 的执行与状态层。它把文献检索、论文精读、claim 提取、gap 分析、实验设计和论文写作连接成一条可持续、可审查、可恢复的科研工作流。

!!! info "当前文档站状态"
    这是 Research Harness 的中文文档站首版。优先覆盖安装、Agent 使用、论文管理、MCP 工具、Zotero 集成和核心架构。部分深层设计文档仍保留原始英文或中英混排，后续会逐步中文化。

## 你可以用 RH 做什么

- 建立持续增长的 paper pool，而不是一次性的论文清单。
- 将论文精读结果沉淀为 notes、claims、limitations、evidence 和 provenance。
- 使用 MCP 工具让 Codex、Claude Code、Cursor 等 Agent 直接调用科研原语。
- 通过 orchestrator 在 `init → build → analyze → propose → experiment → write` 阶段之间推进，并在关键节点留下可复核 artifact。
- 将 Zotero 作为本地文献入口，同时让 RH 管理 topic、paper、note、tag、provenance 和 Codex handoff。

## 推荐阅读顺序

1. [快速开始](quickstart.zh.md)：安装、配置环境变量、验证 CLI/MCP。
2. [Agent 使用手册](agent-guide.md)：给 Codex / Claude Code / Cursor 的操作规范。
3. [论文管理规范](paper-management.zh.md)：paper 入库、PDF 路径、topic 绑定的硬性约束。
4. [MCP 工具与工作流](mcp-tools.zh.md)：常用工具、编排工具和自然语言驱动方式。
5. [Zotero 集成](zotero-integration.zh.md)：本地 Zotero 与 RH 的桥接方式。
6. [架构总览](architecture/README.md)：深入了解 primitives、provenance、orchestrator。

## 核心原则

### 1. 论文必须入库

所有论文都应通过 `paper_ingest` 或 `rh paper ingest` 进入统一数据库。不要把 PDF 或元数据散落在项目目录里。

### 2. 产出必须记录

关键产出需要通过 orchestrator artifact 记录，确保后续 session 能接着工作，也能回溯产生过程。

### 3. Agent 可以自由推进，但必须可审计

RH 不强制死板阶段顺序；它提供的是工具、状态、门禁和 provenance，让 Agent 能灵活工作，同时保留人工复核能力。

## 一句话启动示例

```text
围绕「robust budget pacing for online advertising」创建一个研究 topic。
检索近期论文，筛选有用论文入库，并建立第一版 literature map。
```

```text
精读这个 topic 里最相关的论文。
提取它们的 claims、假设、局限、数据集、指标和可复现性风险。
```

```text
基于已记录证据，找出可以推进成实验的 research gaps。
针对排名第一的方向，准备实验 brief：包括 baseline、metric、ablation 和可能失败的情况。
```

## 本地隐私边界

公共仓库只应包含公开代码、公开文档和脱敏示例。未发表论文草稿、真实研究 artifact、私有 topic、真实数据库和凭据都不应提交。
