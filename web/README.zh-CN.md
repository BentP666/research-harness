# Research Harness

> **公共前端已弃用：** Next.js dashboard 仅保留给本地/内部实验。Research Harness 1.0 主推 Zotero 侧边栏插件作为公共前端，不再把这个网页端作为远程 release demo。

**面向长周期 AI 科研 agent 的 harness。**

Research Harness 把 AI 辅助科研变成一条可持续、可审查的工作流：
从文献检索、论文精读、gap 分析，到实验设计和论文撰写。

它为 Codex、Claude Code、Cursor、OpenClaw 等 coding agent 提供科研所需的
状态管理、工具调用、阶段门控和溯源记录，让严肃科研工作可以跨 session 持续推进，
而不是散落在一次次聊天记录里。

## 它能帮你的 agent 做什么

- 建立持续增长的 paper pool，而不是一次性的论文清单。
- 把论文精读成可复用的笔记、claims、局限和证据。
- 比较方法、baseline、矛盾和开放的 research gap。
- 把有潜力的 gap 推进成实验 brief：包括假设、指标、baseline、评估方案。
- 基于已记录证据起草 related work、proposal、报告和论文章节。
- 在不同 agent、模型、机器和 session 之间继续同一个研究状态。

## 最简单的开始方式

Research Harness 是 agent-native 的。推荐路径不是让用户手动理解所有配置，
而是让你的 VIB Coding 工具在当前环境里帮你安装和接入。

```bash
git clone https://github.com/Biajin-PKU/research-harness.git
cd research-harness
```

然后把下面这段 prompt 给 Codex、Claude Code、Cursor、OpenClaw 或其他 coding agent：

```text
请帮我在当前 repo 安装和配置 Research Harness。

请你：
1. 先阅读 README.md、docs/quickstart.md、AGENTS.md 和 docs/agent-guide.md。
2. 检测我的环境：操作系统、shell、Python、包管理器、当前使用的 coding agent。
3. 用最安全的本地模式安装 Research Harness。
4. 如果可以，请帮我配置当前 coding 工具使用的 Research Harness MCP server。
5. 不要硬编码任何密钥。如果需要 API key，请明确告诉我要设置哪个环境变量。
6. 运行可用的 doctor / smoke check。
7. 最后告诉我：
   - 安装了什么；
   - 当前使用哪个 Python 环境；
   - 如何启动或验证 MCP server；
   - 旧 web workbench 已弃用、仅限本地使用；
   - 下一步我可以直接使用的一条科研 prompt。
```

如果你的 coding 工具不能自动修改自己的 MCP 配置，请让它生成准确的配置片段，并告诉你应该粘贴到哪里。

## 安装后怎么开始科研

安装完成后，直接用科研语言描述任务，而不是记工具命令：

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

```text
基于已记录 claims 和 evidence 起草 related work。
请保证引用和观点都能追溯到源论文。
```

## 手动安装

如果你想手动安装：

```bash
./setup.sh
cp .env.example .env
rh --json doctor
```

如果要运行 LLM 支持的 research primitives，设置至少一个模型 provider：

```bash
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>
KIMI_API_KEY=<your-kimi-key>
```

只需要一个就能开始，其他 provider 可以之后再加。

## 遗留本地 workbench

这个应用作为公共/远程前端已经弃用，只保留给本地或内部实验。Research Harness 1.0 的 release demo 应使用 Zotero 侧边栏插件。

如果仍需本地运行：

```bash
pip install -e "packages/research_harness_mcp[api]"
python -m research_harness_mcp.http_api
cd web
npm install
npm run dev
```

## Harness 思想

Research Harness 不只是 prompt 集合。它是给科研 agent 使用的控制层：

- **Persistent state**：topic、论文、笔记、claims、gap、草稿和报告都保存在同一个研究池里。
- **Typed research primitives**：`paper_search`、`deep_read`、`claim_extract`、`gap_detect`、`experiment_handoff`、`section_draft` 等科研动作是结构化的，不是随手问答。
- **Stage gates**：研究可以沿着 `init → build → analyze → propose → experiment → write` 推进，并在关键阶段接受审查。
- **Provenance**：重要产出可以追溯到论文、artifact、工具调用和模型运行。
- **Agent interoperability**：同一个研究状态可以被 Codex、Claude Code、Cursor、OpenClaw 或其他 MCP agent 继续使用。

## 给 agent 的目录

如果你使用 coding agent，请让它优先阅读：

| 路径 | 用途 |
| --- | --- |
| `AGENTS.md` | 项目规则和 RH 使用约束。 |
| `docs/agent-guide.md` | agent 如何使用 RH 做科研。 |
| `docs/quickstart.md` | 安装、配置和首次运行细节。 |
| `skills/` | 文献检索、gap 分析、claim 提取、论文写作等工作流。 |
| `docs/DEMO.md` | 无 key demo 和真实模型 demo 路径。 |
| `docs/TROUBLESHOOTING.md` | 常见运行和 provider 问题。 |

## License

PolyForm Noncommercial 1.0.0. See [LICENSE](LICENSE).
