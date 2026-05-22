# MCP 工具与工作流

Research Harness 的核心能力通过 MCP Server 暴露给 Codex、Claude Code、Cursor 等 Agent。Agent 不需要记住复杂脚本；它可以直接调用类型化科研工具。

## 常用 Research Primitives

| 工具 | 类型 | 用途 |
| --- | --- | --- |
| `paper_search` | 检索 | 多源论文搜索 |
| `paper_ingest` | 入库 | 按 arXiv、DOI、Semantic Scholar ID 或本地 PDF 入库 |
| `paper_summarize` | 理解 | 生成论文摘要或指定 focus 的摘要 |
| `claim_extract` | 提取 | 从论文中提取研究声明 |
| `evidence_link` | 提取 | 将声明关联到证据 |
| `gap_detect` | 分析 | 识别研究空白 |
| `baseline_identify` | 分析 | 识别 baseline 方法 |
| `section_draft` | 写作 | 基于证据起草章节 |
| `consistency_check` | 验证 | 检查章节、claim、引用和数字一致性 |

## Orchestrator 工具

| 工具 | 用途 |
| --- | --- |
| `orchestrator_status` | 查看当前阶段和状态 |
| `orchestrator_resume` | 接管已有 topic / project，自动从 artifact 推断进度 |
| `orchestrator_gate_check` | 检查阶段门禁是否满足 |
| `orchestrator_advance` | 推进到下一阶段 |
| `orchestrator_record_artifact` | 记录关键产出 |
| `adversarial_review` | 运行独立对抗审查 |

## Agent 优先入口

接管已有研究时，优先让 Agent 调用：

```text
orchestrator_resume(topic_id=..., stop_before="experiment")
```

这样不会从头开始，而是从现有 artifact 和 topic 状态推断下一步。

## 自然语言驱动示例

```text
请接管 topic「automated scientific discovery agents」。
先用 orchestrator_resume 判断当前阶段，然后告诉我缺哪些证据才能推进。
```

```text
请对 topic 中最重要的 10 篇论文做 claim_extract，
并把 claims 组织成 methods、evidence、limitations 三类。
```

```text
基于当前 claims 和 evidence，运行 gap_detect，
输出可以推进成实验 brief 的前三个方向。
```

## CLI 只做数据管理

科研 primitive 应优先走 MCP，以保留 provenance 和 artifact 记录。CLI 适合：

- `rh topic list`
- `rh topic overview`
- `rh paper list`
- `rh paper ingest`
- `rh orchestrator status`

不要用 CLI 绕过 MCP 执行 claim extraction、gap detection、section drafting 等核心研究原语。

## 更多说明

- Agent 操作规范：[`docs/agent-guide.md`](agent-guide.md)
- 核心原语设计：[`docs/architecture/01_research_primitives.md`](architecture/01_research_primitives.md)
- Orchestrator 设计：[`docs/architecture/06_orchestrator.md`](architecture/06_orchestrator.md)
