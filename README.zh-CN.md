<p align="center">
  <img src="docs/assets/hero.png" alt="Research Harness" width="720"/>
</p>

# Research Harness

**面向长周期 AI 科研 agent 的 harness。**

Research Harness 把 AI 辅助科研变成一条可持续、可审查的工作流：
从文献检索、论文精读、gap 分析，到实验设计和论文撰写。

它为 Codex、Claude Code、Cursor、OpenClaw 等工具提供科研所需的状态管理、
工具调用、阶段门控和溯源记录，让严肃科研工作可以跨 session 持续推进，
而不是散落在一次次聊天记录里。

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md"><b>简体中文</b></a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-PolyForm_Noncommercial_1.0.0-red.svg" alt="License"/></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/version-1.0.0-green.svg" alt="Version"/>
  <img src="https://img.shields.io/badge/MCP-compatible-orange.svg" alt="MCP"/>
</p>

## RH 能帮你把科研流程管起来

- 建立持续增长的 paper pool，而不是一次性的论文清单。
- 把论文精读成可复用的笔记、claims、局限和证据。
- 比较方法、baseline、矛盾和开放的 research gap。
- 把有潜力的 gap 推进成实验 brief：包括假设、指标、baseline、评估方案。
- 基于已记录证据起草 related work、proposal、报告和论文章节。
- 在不同 agent、模型、机器和 session 之间继续同一个研究状态。
- 用脱敏或合成证据维护公共安全的 Discovery issue 与 opportunity brief。

## Zotero 侧边栏插件

Research Harness 同时提供实验性的 Zotero 侧边栏插件，用于围绕当前论文或
当前目录发起 RH/Codex 对话。插件会读取 Zotero item / collection 上下文，
匹配 RH topic 与 paper，流式返回 Codex 回复；涉及写入 Zotero 或 RH 的动作
必须先经过 RH 生成的 preview，再由用户显式确认。

本地使用时，如果 `http://127.0.0.1:8000` 没有服务，插件现在可以自动启动
loopback-only 的 RH Python bridge，并在首问前预热 Codex app-server pool。构建、
安装、偏好项和安全模型见 [`docs/zotero-rh-panel.md`](docs/zotero-rh-panel.md)。

## 最简单的开始方式

你不需要一开始就读完所有配置。先把项目 clone 下来，进入目录，
然后让你正在使用的 Codex、Claude Code、Cursor 或 OpenClaw 帮你完成本地安装。

```bash
git clone https://github.com/Biajin-PKU/research-harness.git
cd research-harness
```

可以直接把下面这段话交给它：

```text
请帮我在当前 repo 安装和配置 Research Harness。

请你：
1. 先阅读 README.md、docs/quickstart.md、AGENTS.md 和 docs/agent-guide.md。
2. 检测我的环境：操作系统、shell、Python、包管理器、当前使用的 coding 工具。
3. 用最安全的本地模式安装 Research Harness。
4. 如果可以，请帮我配置当前工具使用的 Research Harness MCP server。
5. 不要硬编码任何密钥。如果需要 API key，请明确告诉我要设置哪个环境变量。
6. 运行可用的 doctor / smoke check。
7. 最后告诉我：
   - 安装了什么；
   - 当前使用哪个 Python 环境；
   - 如何启动或验证 MCP server；
   - 如何启动可选的 web workbench；
   - 下一步我可以直接使用的一条科研 prompt。
```

如果当前工具不能自动修改 MCP 配置，请让它输出准确的配置片段，并告诉你应该粘贴到哪里。

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

## 公共仓库隐私边界

这个 GitHub 仓库只应该包含公开代码、公开文档，以及经过脱敏或合成的示例数据。
不要提交未发表论文草稿、研究创新点笔记、真实项目 artifact、私有 topic 名称或 ID、
本地数据库 / 报告、凭据，或由非公开研究内容生成的 Discovery issue。

私有科研状态请保留在本地或私有数据库 / 仓库中。push 前先检查 `git diff`；
需要示例时，优先使用类似
[`docs/discover/issues/demo-weekly.json`](docs/discover/issues/demo-weekly.json)
这样的合成 fixture。

---

## 项目定位

Research Harness 是科研 Agent 在做文献综述、研究提案、实验协调和论文撰写时所依赖的**执行与状态层**。它负责运行「搜集证据 → 采取行动 → 核验结果」的循环，并把每一步都持久化下来，让下一次 session（无论是人还是 Agent）能从上一次停下的位置继续。

具体包含三层：

- **状态层** —— 单一的 SQLite `pool.db`，集中存放论文、Paper Card、精读笔记、Claim、artifact、provenance 记录；
- **原语层** —— 81 个类型化的科研操作（`paper_search`、`claim_extract`、`gap_detect`、`adversarial_review`、`section_draft`、`paper_verify_numbers` 等），一处注册，通过 134 个 MCP 工具、Python API、`rh` CLI 和 HTTP / Web 入口对外暴露；
- **控制层** —— 六个阶段（`init → build → analyze → propose → experiment → write`），每一次推进都要求上一阶段产出了能通过阶段边界门禁的类型化 artifact。

"Harness" 一词沿用 Anthropic Engineering 的定义[^1]：它是把模型变成 Agent 的那套系统 —— 编排工具调用、跨回合保留状态、记录发生的事情。Research Harness 把这套框架落到科研工作上。

[^1]: 参见 Anthropic Engineering 的 *Demystifying evals for AI agents*（2026 年 1 月）与 *Effective harnesses for long-running agents*（2025 年 11 月），二者给出了 Agent Harness 的基础定义。

## 项目动机

系统设计围绕文献密集型科研工作中的三个长期需求展开：

1. **连续性。** 一个论文项目往往跨越数周甚至数月，Agent 积累下来的状态 —— 已入库的论文、抽出的 claim、标记的 gap —— 必须能跨越 session 边界、跨越模型切换、跨越人工交接存活下来。
2. **可审计性。** 最终出现在论文草稿里的每一条论断，都应该能回溯到某个具体的源头：一篇论文、一段抽取的引文、一次实验运行、或一条经过核验的数字。
3. **阶段边界的可复核性。** 从文献综述到研究提案、从提案到实验、从实验到撰稿，这几个关键交接点上，人需要一个清晰的 checkpoint：直接可读的类型化 artifact。

Research Harness 把这三点当成一等公民：状态持久化在数据库里，经过记录通道的原语调用都带 provenance，阶段推进只在所需证据以类型化形式齐备时才开门。

## 面向谁

- **科研人员** —— 在文献密集项目中（PhD、应用实验室、产业研究）希望引入 Agent，同时保留对流程的复核能力。
- **Agent 工程师** —— 基于 MCP 客户端（Claude Code、Codex、自定义 runner）构建领域 Harness，需要一个把状态 / 门禁 / provenance 做完整的参考实现。
- **重视可复现性的团队** —— 需要在 Agent 产出的 artifact 上保证引用完整性和数字到实验的可追溯。

最适合的使用方式是：人工在阶段边界审核 artifact —— 系统的设计精力也都集中在这里。

## 快速上手

需要 Python 3.11+。一把 LLM API key（OpenAI、Anthropic 或 Kimi）即可起步。

```bash
git clone https://github.com/Biajin-PKU/research-harness.git
cd research-harness
./setup.sh                    # 创建虚拟环境，安装四个 package
cp .env.example .env          # 填入一把 API key
rh topic init "my-topic"      # 注册一个研究主题
```

验证安装：

```bash
python -m pytest packages/ -q --ignore=packages/research_harness_eval
# package tests should pass
```

完整安装说明（含 Conda、GPU、离线环境）见 [`docs/quickstart.md`](docs/quickstart.md)。


## PDF 解析质量模式

Research Harness 默认保留轻量 PDF 路径：`pymupdf` 快速抽取文本和 PDF
内置目录，不需要下载模型。对于需要更高质量精读的论文，可以按需安装
Docling 后端，用于生成更好的 Markdown、表格和 layout-aware headings：

```bash
pip install -e "packages/research_harness[docling]"
PAPERINDEX_PARSER=docling rh paper annotate <paper_id>
```

Docling 在本地运行，不调用 LLM API。首次运行会从 HuggingFace 下载
Docling 的 layout/table 模型资产，之后复用本地缓存。OCR 默认关闭，适合
born-digital 学术 PDF；扫描件 OCR 后续可以作为单独 parser profile 增加。

## 一次完整的端到端全自动运行

同一条自主流水线，三种入口 —— 按手头的 session 挑一种即可。三种方式都会驱动项目走完六个阶段，都在同一套人工 checkpoint（方向选择、实验设计审批、finalize）停下来，并且都写入同一个 `pool.db`：在一种方式里起步，可以换另一种方式接着往下跑。

示例场景：一个 *diffusion-bidding* 主题、两篇种子论文的项目，自动推进 `init → build → analyze → propose`，在 `experiment` 之前停下供人工审阅方向。

### 1. Vibe coding —— 通过 MCP 由 Claude Code / Codex 驱动

配好 `research-harness` MCP server（见下文 [MCP —— Claude Code](#mcp--claude-code)）后，用自然语言驱动。Agent 会调用 `orchestrator_resume`，参数 `stop_before="experiment"`：

```
你：    在主题 "diffusion-bidding" 下新开一个 "paper-01" 项目。
        种子论文：arXiv 2407.15686 与 2404.10702。
        把流水线跑到 experiment 阶段之前停下，让我审方向。

Agent：[调用 paper_ingest × 2、orchestrator_init、orchestrator_resume
        mode="standard", stop_before="experiment"]
       已完成 init → build → analyze → propose，在 `experiment` 前暂停。
       direction_ranking 里有 3 个候选方向（得分 4.6 / 4.1 / 3.8）；
       gap_detect 标出了 7 个 open gap；adversarial_review 对
       候选 #1 提出了 2 条反驳。要打开看看吗？

你：    给我看候选 #2 的 artifact，然后继续跑到下一个 checkpoint。

Agent：[调用 orchestrator_artifacts 读候选 #2，再
        orchestrator_resume stop_before="finalize"]
       ...
```

这是 Agent 驱动时的标准流程。Agent 每一次工具调用都会跟 artifact 一起写进 `pool.db`，队友之后打开同一个数据库能看到全程轨迹。

### 2. CLI —— `rh auto-runner` 脚本

同一条流程的脚本化版本。不依赖 MCP 客户端，适合 CI、cron、远程 shell。

```bash
# 注册主题并入库种子论文
rh topic init "diffusion-bidding"
rh paper ingest --arxiv-id 2407.15686 --topic diffusion-bidding
rh paper ingest --arxiv-id 2404.10702 --topic diffusion-bidding

# 启动自主 Runner（topic_id=1 可从 `rh topic list` 查看）
rh auto-runner start --topic-id 1 --mode standard \
  --direction "Hierarchical diffusion planner for cross-channel budget allocation"

# Runner 自动推进 init → build → analyze → propose，然后在人工 checkpoint 停下。
# 查看 Runner 产出的 artifact：
rh auto-runner status     --topic-id 1
rh orchestrator artifacts --topic diffusion-bidding --stage propose

# 继续 —— Runner 会一路推进到下一个人工 checkpoint。
rh auto-runner resume --topic-id 1
```

### 3. Python —— 直接调 `run_topic`

同一条流程作为函数调用。适合写在 Notebook、更大的训练流水线、或任何已经 import 了 `research_harness` 的脚本里。

```python
from research_harness.auto_runner.runner import run_topic, resume_topic, get_status
from research_harness.api import ResearchAPI

api = ResearchAPI()                                    # 自动从环境解析 pool.db 路径
topic_id   = api.topic_init("diffusion-bidding")
api.paper_ingest(arxiv_id="2407.15686", topic_id=topic_id)
api.paper_ingest(arxiv_id="2404.10702", topic_id=topic_id)
result = run_topic(
    topic_id,
    direction="Hierarchical diffusion planner for cross-channel budget allocation",
    mode="standard",
)
# result = {"status": "paused", "current_stage": "propose", ...}

# 这里是人工审阅点 —— 检查 artifact、编辑、拍板
print(get_status(topic_id))

# 继续跑到下一个 checkpoint（或跑到完成）
run_again = resume_topic(topic_id)
```

---

无论走哪种入口，Runner 都不止是一个加壳的 `for` 循环：

- 每个阶段都会把**类型化 artifact**（gap 表、claim 表、研究提案、草稿章节）写进 `pool.db`，Runner 只有在阶段边界的门禁接受这些 artifact 后才会跨过下一阶段。
- Runner 路由的每一次 LLM 调用都走 `TrackedBackend`，所以 `rh provenance list` 能清楚看到哪条 artifact 由哪个模型、在何种输入下、花了多少成本生成。
- Runner 是可恢复的：中途 kill 掉、换个模型、甚至把数据库拷到另一台机器，`resume` 会从最近一个 checkpoint 继续 —— 不论当初是由哪种入口启动的。

若需要完全手动逐个原语运行的走查版本（不启用 Runner），见 [`docs/quickstart.md`](docs/quickstart.md)。

## 四种接口

四种入口访问的是同一套原语注册表，读写的是同一份 `pool.db`。按任务选一个顺手的即可。

| 接口 | 适合 | 入口 |
|------|------|------|
| **MCP server** | Claude Code / Codex / 任意 MCP 客户端 | `python -m research_harness_mcp` |
| **Python API** | Notebook、流水线、已有代码库 | `from research_harness import ResearchAPI` |
| **`rh` CLI** | 终端、脚本、CI | `rh --help` |
| **HTTP API + Web dashboard** | 用浏览器浏览 pool.db、触发入库 / 分析 | `python -m research_harness_mcp.http_api` + `cd web && npm run dev` |

Provenance 说明：MCP server 和 `rh primitive exec` 走的是 `TrackedBackend`，每次执行都会被记录；Python API 直接调用原语实现，如果需要审计，请自行用 `TrackedBackend` 包一层。详见 [`docs/python-api.md`](docs/python-api.md)。

### MCP —— Claude Code

写入 `.claude/settings.json`（项目级）或 `~/.claude/settings.json`（全局）：

```json
{
  "mcpServers": {
    "research-harness": {
      "command": "/absolute/path/to/research-harness/.venv/bin/python",
      "args": ["-m", "research_harness_mcp"],
      "env": { "RESEARCH_HARNESS_DB_PATH": "/absolute/path/to/pool.db" }
    }
  }
}
```

### MCP —— Codex

写入 `~/.codex/config.toml`：

```toml
[mcp_servers.research-harness]
command = "/absolute/path/to/research-harness/.venv/bin/python"
args = ["-m", "research_harness_mcp"]
env = { "RESEARCH_HARNESS_DB_PATH" = "/absolute/path/to/pool.db" }
startup_timeout_sec = 30.0
```

或用命令行：`codex mcp add research-harness -- /abs/path/python -m research_harness_mcp`。

### HTTP API + Web dashboard

如果操作者更习惯浏览器而不是聊天 prompt，仓库提供了 FastAPI 后端
（130+ 条 REST route，包含分页读取和 action endpoint）以及 [`web/`](web/)
下的 Next.js 16 / React 19 dashboard。启动方式：

```bash
# Backend —— 安装 FastAPI + uvicorn extras
pip install -e "packages/research_harness_mcp[api]"
python -m research_harness_mcp.http_api   # http://localhost:8000

# Frontend
cd web && npm install && npm run dev      # http://localhost:3000
```

Dashboard 展示 topics、papers、projects、artifacts 和 provenance stats，并提供
paper search / ingest、gap detection、claim extraction、outline generation、
section drafting 等按钮；它们都通过与 MCP server 相同的 primitive registry 执行。

## Vibe Coding 可用的 Skill

在 Claude Code 或 Codex 里，常态是用自然语言驱动 —— 你描述任务，Agent 自动路由到合适的 Skill，再由 Skill 调度对应的 MCP 工具。仓库里 [`skills/`](skills/) 下随发行版提供了 19 个 Skill，采用 Claude Code 通用的 YAML frontmatter 格式；把目录挂进 skills 路径后，下表里的触发语就能直接生效。

### 对照表

| Skill | 作用 | 自然语言触发示例 |
|-------|------|------------------|
| [`research-harness`](skills/research-harness/SKILL.md) | 路由 Skill —— 意图宽泛时自动转到更具体的子 Skill | "进入科研工作流"、"用 Research Harness 开工" |
| [`research-init`](skills/research-init/SKILL.md) | 初始化主题、搭项目骨架 | "给这个项目接入 Research Harness，主题是 X" |
| [`literature-search`](skills/literature-search/SKILL.md) | 按查询做大范围论文检索 | "帮我搜一下 diffusion bidding 最近的论文" |
| [`literature-mapping`](skills/literature-mapping/SKILL.md) | 聚类论文、识别 baseline、建主题地图 | "给这个主题做一份文献地图" |
| [`citation-trace`](skills/citation-trace/SKILL.md) | 从种子论文沿引用链前/后扩展 | "从这三篇种子论文扩展" |
| [`paper-sync`](skills/paper-sync/SKILL.md) | 体检论文池：元数据、PDF、dismiss | "同步一下我的论文池" |
| [`paper-verify`](skills/paper-verify/SKILL.md) | 校验论文是否真实存在、元数据是否匹配 | "这个 DOI 是真的吗" |
| [`claim-extraction`](skills/claim-extraction/SKILL.md) | 从论文抽取结构化 claim | "把论文 42 的核心 claim 抽出来" |
| [`gap-analysis`](skills/gap-analysis/SKILL.md) | 找研究 gap、缺失的 baseline | "现在的研究 gap 在哪里" |
| [`evidence-gating`](skills/evidence-gating/SKILL.md) | 判断阶段是否可以推进 | "现在能推进到 propose 阶段了吗" |
| [`section-drafting`](skills/section-drafting/SKILL.md) | 基于已挂接的证据起草章节 | "根据抽出的 claim 写 related work" |
| [`paper-writing`](skills/paper-writing/SKILL.md) | 基于 RH 证据组织论文 / 报告草稿 | "把这些证据整理成 workshop paper outline" |
| [`provenance-review`](skills/provenance-review/SKILL.md) | 回顾执行历史、已录 artifact、挂接关系 | "审一下这个项目最近的 provenance" |
| [`rh-session-resume`](skills/rh-session-resume/SKILL.md) | 接手已有 RH topic/session，避免从头开始 | "继续当前 RH topic" |
| [`rh-codex-checkpoint`](skills/rh-codex-checkpoint/SKILL.md) | 在上下文压缩或交接前保存 compact checkpoint | "压缩前创建 RH checkpoint" |
| [`rh-codex-verify`](skills/rh-codex-verify/SKILL.md) | 校验 Codex workflow、配置和 skill 变更 | "跑一下 RH Codex 验证" |
| [`rh-artifact-record`](skills/rh-artifact-record/SKILL.md) | 把耐久产出记录成 orchestrator artifact | "把这份报告记录成 RH artifact" |
| [`research-primitives`](skills/research-primitives/SKILL.md) | 参考 —— 所有 MCP 原语一览 | "给我看原语参考表" |
| [`task-taxonomy`](skills/task-taxonomy/SKILL.md) | 参考 —— 模型路由与任务分类指引 | "claim extraction 该用哪一档模型" |

### 示例 —— 自然语言到 Skill 路由

- "开一个关于 hierarchical diffusion bidding 的新项目，先拉 20–30 篇最近的论文" → `research-init` → `literature-search`
- "从这两个 arXiv ID 出发扩展论文池" → `citation-trace`
- "已经入库 80 篇了，研究 gap 在哪儿" → `claim-extraction` → `gap-analysis`
- "基于抽出的 claim 起草 related work 章节" → `section-drafting`
- "现在能不能推进到 experiment 阶段" → `evidence-gating`
- "审一下这个项目上周做过什么" → `provenance-review`

### 安装 Skill

`setup.sh` 会自动生成 skill manifest，`rh skill` CLI 把 skill 装到 agent
期望的位置。**RH 不需要预知你的 agent**——由 agent 通过 `.rh-agent.toml`
自声明装在哪里、用什么策略。完整设计见
[`docs/skills/`](docs/skills/README.md)。

```bash
# A. 自动：在仓库根放一份 .rh-agent.toml，跑一次 install
cp skills/agent-profiles/claude-code.toml .rh-agent.toml
rh skill install

# B. 用仓库内置的 agent profile（无需手写 .rh-agent.toml）
rh skill install --agent claude-code
rh skill install --agent codex

# C. 临时直接指定目标目录
rh skill install --target ~/.claude/skills

# D. 不落盘：通过 MCP 运行时拉取（agent 端调 skill_list / skill_get）
```

Claude Code 和 Codex 共用同一份 `SKILL.md` 格式 —— 上表的触发语在两边都适用。
新增任何 agent，只需写一行 `.rh-agent.toml`，RH 这边零改动。

## 可信机制

以下三个机制在 [`docs/architecture.md`](docs/architecture.md) 中有更详细的规范说明。

**Provenance（溯源记录）。** 经 `TrackedBackend` 调用的原语（MCP server、`rh primitive exec`）会被记录：模型、档位（tier）、成本、输入 / 输出哈希、以及依赖边（`derived_from`、`consumed_by`）。可以用 `rh provenance list` 或直接写 SQL 查询。Python API 直接调用不会自动记录，有审计需要时请自行包裹 `TrackedBackend`。

**阶段门禁（Stage Gates）。** 一个「阶段」是 `init → build → analyze → propose → experiment → write` 中的一个命名步骤；一个「门禁」是在阶段边界运行的类型化检查。门禁读取当前阶段产出的 artifact，当必要证据缺失时，它不会让流水线推进。门禁是对 artifact 类型的代码化检查。

**Verified Number Registry（已核验数字注册表）。** 进入 `write` 阶段后，草稿中出现的数字可以与一份由**已记录实验指标**构建出的注册表对照。`paper_verify_numbers` 原语负责比对，支持可配置的容差和分节严格度（严格节中的未匹配数字标记为 error，宽松节中标记为 warning）。Always-allowed 值（常用常数、年份、已注册的数据集规模等）会被排除在检查之外。这套机制用来在评审环节捕捉伪造的数字，不替代评审人本身。

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│   MCP server（134 个工具，stdio 传输）                       │
├──────────────────────────────────────────────────────────────┤
│   Orchestrator（编排器）                                     │
│     init → build → analyze → propose → experiment → write    │
│     gates: approval · coverage · adversarial · review ·      │
│            experiment                                        │
├──────────────────────────────────────────────────────────────┤
│   Primitives (69)      Provenance         Observation        │
│   类型化操作           审计轨迹           策略演化            │
├──────────────────────────────────────────────────────────────┤
│   执行后端（LLM 路由、本地、插件）                           │
├──────────────────────────────────────────────────────────────┤
│   SQLite pool.db（论文 · artifact · provenance · tasks）     │
└──────────────────────────────────────────────────────────────┘
```

**双轴执行。** 两个独立的旋钮：

- `workflow_mode` ∈ {`explore`, `standard`, `strict`, `demo`} —— 控制深度、覆盖度和质量阈值。
- `autonomy_mode` ∈ {`supervised`, `autonomous`} —— 控制由谁来解门。方向选择、finalize 这类高风险阶段，即便在 autonomous 模式下也强制要求人工审批。

**跨模型对抗评审（Cross-model adversarial review）。** 在 `propose → experiment` 这类仅靠自洽无法担保结论的 checkpoint 上，提案和草稿会交给一个独立的 challenger 模型评审。challenge / response / resolution 三段都会作为一等公民 artifact 落盘。

## 扩展

新能力通过 `plugin.yaml` 清单发布，不必 fork 主仓。

```yaml
# plugin.yaml
name: my-paper-source
version: 0.1.0
description: Custom paper source integration
author: Your Name
license: PolyForm-Noncommercial-1.0.0
schema_version: 1
min_harness_version: 0.1.0
extension_points:
  primitives:
    - name: my_search
      category: RETRIEVAL
      module: my_plugin.search
      function: search_impl
      requires_llm: false
```

原语通过 `@register_primitive(spec)` 注册；门禁继承 `GateEvaluator`；后端实现 `ExecutionBackend`。完整的清单 Schema、扩展点列表和发现流程见 [`docs/plugin-guide.md`](docs/plugin-guide.md)。

## 文档

| 文档 | 内容 |
|------|------|
| [`docs/quickstart.md`](docs/quickstart.md) | 安装、API key 配置、第一个主题 |
| [`docs/architecture.md`](docs/architecture.md) | 阶段、门禁、artifact 类型、存储模型 |
| [`docs/agent-guide.md`](docs/agent-guide.md) | Claude Code / Codex 如何驾驭 Harness |
| [`docs/python-api.md`](docs/python-api.md) | 不依赖 MCP 客户端的 Python 用法 |
| [`docs/plugin-guide.md`](docs/plugin-guide.md) | 自定义原语 / 门禁 / 后端开发 |
| [`docs/PAPER_MANAGEMENT.md`](docs/PAPER_MANAGEMENT.md) | 论文存储的规范协议 |
| [`docs/codex-workflow.md`](docs/codex-workflow.md) | Codex 配置、checkpoint 与验证流程 |
| [`docs/discover/README.md`](docs/discover/README.md) | RH Discover issue 发布与编辑流程 |
| [`docs/DEMO.md`](docs/DEMO.md) | 无 key demo 和真实模型 demo 路径 |
| [`CHANGELOG.md`](CHANGELOG.md) | 1.0.0 及更早版本发布说明 |

## 迭代记录

公共仓库每轮迭代的核心工作，最新在上。

### 2026-05-21 — v1.0.0 公共安全的 Discovery 与治理版本

- **RH Discover 1.0**：增加 file-backed issue publishing、opportunity brief、
  product API routes 和独立的 Discovery workbench；公共示例只使用脱敏或合成 fixture。
- **ResearchFlowBench diagnostics**：增加确定性的 preflight、task-pack 校验、
  leakage 检查、retrieval trace 完整性检查和 cost cap helper。
- **Semantic governance utilities**：增加对象图校验、normalization、trace checking、
  rollback payload 和 contract hardening。
- **Codex workflow surface**：加入项目级 Codex 配置、RH 专用 skills、checkpoint 指南、
  verification scripts 和 review workflow 文档。
- **发布卫生**：核心 package 与 web 元数据统一到 `1.0.0`；Ruff、targeted pytest、
  Codex checks、web build 和 GitHub PR checks 均通过。

### 2026-05-10 — v0.4.0 Workbench 与解析器发布

- **可选 Docling 解析器**：Paperindex 增加 parser 抽象，默认继续使用轻量 PyMuPDF，也可以通过 `research-harness[docling]` 启用更高保真解析。
- **Workbench 发布面整理**：首页、demo、README、quickstart 和 release docs 聚焦核心科研循环与 agent handoff。
- **Cursor Agent 接入**：新增项目级 Cursor MCP 配置、规则、论文精读 subagent 和 skill，让 Cursor 精读也遵守 RH 的入库与溯源规则。
- **发布卫生**：package/web 元数据统一到 `0.4.0`；Ruff format、targeted Ruff check、parser tests、web lint/tests/build 均通过。

### 2026-05-09 — v0.3.0 一体化科研工作流发布

- **科研工作流扩展**：CS Research Workflow v2 增加 candidate seed/upsert、red-ocean 评分、gap 交叉验证、推荐排序、experiment handoff，以及单入口 workflow resume 能力。
- **Web 产品化**：Next.js 控制台覆盖 agent 配置、预算、发现、onboarding、论文阅读、报告、topic 阶段面板、venue decision、method atoms、goal pool、retrieval log 等核心路径。
- **LLM 路由增强**：支持 LiteLLM 生态 provider、tier routing、token accounting、并行 deep-read provider pool、provider 自隔离和单篇超时。
- **Paperindex 内嵌**：PDF/card/retrieval 能力迁入 `research_harness.paperindex`，`paperindex` package 保留为兼容 shim。
- **发布整理**：系统版本统一到 `0.3.0`；本地 Python ruff、Python tests、web lint、web tests、web build 均通过。

### 2026-04-22 — 公共仓库 CI 修复

- CI matrix 移除 Python 3.10：`research_harness_mcp` 已声明 `>=3.11`，不再假装兼容。
- 修复 212 个 ruff 报错（`F401` / `F541` / `E402` / `F821` / `F841` / `E741`），覆盖 `llm_primitives.py`、`orchestrator/service.py`、`auto_runner/*`、`paper_source_clients.py` 以及多处测试文件；全量 `ruff format` 通过。
- 补齐缺失的 re-export：`writing_checks.REVIEW_DIMENSIONS`、`orchestrator.review.REVIEW_DIMENSIONS` 现都指向统一的 dimension 源。
- 让测试在无 LLM key 时也能跑：给 paperindex LLM 测试、`TestE2ELiteratureReview` 打上模块级 `skipif`；在 conftest 加了一个自动生效的 fixture，在无 provider 时 stub 掉 `PaperIndexer.build_card`。CI 从原先 22 个用例报 `401` / `No LLM provider`，恢复到 987+ 全绿。

## 项目状态

**1.0.0** —— 公共安全的 Discovery 与治理版本。RH Discover 1.0 提供 issue publishing 与 Discovery workbench；ResearchFlowBench 增加确定性诊断；semantic governance utilities 强化对象图校验 / 回滚流程；Codex workflow 已文档化并纳入检查。版本说明见 [`CHANGELOG.md`](CHANGELOG.md)。

已支持的 LLM Provider：OpenAI、Anthropic、Kimi / Moonshot，并通过 LiteLLM / tier routing 接入 DeepSeek、Qwen / 通义、Zhipu / GLM、Doubao、MiniMax、Yi / Baichuan、SiliconFlow 等 provider。

已知边界：

- Experiment 阶段的算力由用户自备，Research Harness 不负责 provision 训练作业。
- `figure_generate` 调用 fal.ai，需要相应的 API key。
- 数字核验覆盖的是**已记录的实验指标**；来自系统外的数字（例如引用的 baseline）需要登记为 always-allowed 或人工复核。

## 引用

若在学术工作中使用 Research Harness，请引用：

```bibtex
@software{research_harness_2026,
  title        = {Research Harness: an agent harness for scientific literature},
  author       = {Research Harness Contributors},
  year         = {2026},
  version      = {1.0.0},
  url          = {https://github.com/Biajin-PKU/research-harness},
  license      = {PolyForm-Noncommercial-1.0.0}
}
```

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)。所有贡献默认使用同一许可证。

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。欢迎 Issue 和 PR；小修复可直接提交，新增原语、门禁、阶段建议先开 Issue 讨论。

## 致谢

基于 [MCP](https://modelcontextprotocol.io) 构建。文献数据来自 [Semantic Scholar](https://www.semanticscholar.org)、[OpenAlex](https://openalex.org)、[arXiv](https://arxiv.org) 和 [Unpaywall](https://unpaywall.org)。

## 相关项目

Agent Harness 空间中的相关工作 —— 各自针对不同的工作流：

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code) —— 终端里的 Agentic 编程 Harness。
- [`SWE-agent/SWE-agent`](https://github.com/SWE-agent/SWE-agent) —— 面向软件基准测试的 Issue 解决 Harness。
- [`All-Hands-AI/OpenHands`](https://github.com/All-Hands-AI/OpenHands) —— 通用开发者 Agent 平台。
- [`langchain-ai/langgraph`](https://github.com/langchain-ai/langgraph) —— 面向 Stateful Agent 的低层编排框架。
