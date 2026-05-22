# 快速开始

本页是 Research Harness 中文快速上手指南。完整细节可继续参考仓库根目录的 `README.zh-CN.md` 与英文版 [`docs/quickstart.md`](quickstart.md)。

## 前置要求

- Python 3.11+
- SQLite 3.35+（macOS 与大多数 Linux 发行版已内置）
- 至少一个 LLM Provider API key：OpenAI、Anthropic、Kimi / Moonshot 等
- 如果要让 Codex / Claude Code 调用 RH，需要配置 MCP server

## 安装

```bash
git clone https://github.com/Biajin-PKU/research-harness.git
cd research-harness
./setup.sh
```

`setup.sh` 会创建虚拟环境、安装核心 package、复制 `.env.example`，并执行基础 smoke check。

### 手动安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/paperindex[dev]
pip install -e "packages/research_harness[dev,paperindex]"
pip install -e "packages/research_harness_mcp[dev]"
cp .env.example .env
```

## 配置 API key

编辑 `.env`，至少配置一个模型供应商：

```bash
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>
KIMI_API_KEY=<your-kimi-key>
```

推荐但非必需：

```bash
S2_API_KEY=...                   # Semantic Scholar，提高检索限额
UNPAYWALL_EMAIL=you@example.com  # Unpaywall，用 DOI 查 OA PDF
```

## 验证安装

```bash
rh --json doctor
# 或
rhub --json doctor
```

运行测试：

```bash
python -m pytest packages/ -q --ignore=packages/research_harness_eval
```

## 创建第一个研究 topic

```bash
rh topic init "my-research-topic"
rh paper search "my research query" --topic-id 1 --auto-ingest
rh orchestrator init --topic my-research-topic --mode standard
rh orchestrator status --topic my-research-topic
```

## 配置 Agent Skills

```bash
# 安装给 Claude Code
rh skill install --agent claude-code

# 安装给 Codex
rh skill install --agent codex

# 查看 RH 自带 skills
rh skill list
```

## 配置 MCP Server

MCP 配置的关键是使用**绝对路径**，避免不同 shell / venv 下找不到 Python。

示例：

```json
{
  "mcpServers": {
    "research-harness": {
      "command": "/absolute/path/to/research-harness/.venv/bin/python",
      "args": ["-m", "research_harness_mcp"],
      "env": {
        "RESEARCH_HARNESS_DB_PATH": "/absolute/path/to/research-harness/.research-harness/pool.db"
      }
    }
  }
}
```

配置完成后，Agent 就可以调用 RH 的 paper、claim、gap、orchestrator、artifact 等工具。

## 启动 Web Workbench（可选）

```bash
pip install -e "packages/research_harness_mcp[api]"
python -m research_harness_mcp.http_api

cd web
npm install
npm run dev
```

打开：<http://localhost:3000>

## 下一步

把下面这段交给你的 Agent：

```text
请阅读 docs/agent-guide.md 和 docs/PAPER_MANAGEMENT.md，
然后围绕我的研究方向创建 topic、检索论文、筛选入库，
并给我一份可审查的 literature map 初稿。
```
