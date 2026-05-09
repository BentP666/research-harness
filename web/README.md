# Research Harness

**A harness for long-running AI research agents.**

Research Harness turns AI-assisted research into a persistent, reviewable
workflow — from literature search and deep reading to gap analysis, experiment
design, and paper writing.

It gives Codex, Claude Code, Cursor, OpenClaw, and other coding agents the
state, tools, gates, and provenance they need to move serious research forward
across sessions instead of losing progress in chat history.

## What it helps your agent do

- Build a living paper pool instead of a one-off reading list.
- Deep-read papers into reusable notes, claims, limitations, and evidence.
- Compare methods, baselines, contradictions, and open research gaps.
- Turn promising gaps into experiment briefs with assumptions, metrics,
  baselines, and evaluation plans.
- Draft related work, proposals, reports, and paper sections from recorded
  evidence.
- Resume the same research state across agents, models, machines, and sessions.

## The easiest way to start

Research Harness is agent-native. The recommended setup path is to let your
VIB-coding tool install and configure it for the environment you are already
using.

```bash
git clone https://github.com/Biajin-PKU/research-harness.git
cd research-harness
```

Then give this prompt to Codex, Claude Code, Cursor, OpenClaw, or another
coding agent:

```text
You are helping me install and configure Research Harness in this repo.

Please:
1. Read README.md, docs/quickstart.md, AGENTS.md, and docs/agent-guide.md.
2. Detect my environment: OS, shell, Python, package manager, and current coding agent.
3. Install Research Harness in the safest local mode for this machine.
4. Configure the Research Harness MCP server for the coding tool I am using if possible.
5. Do not hardcode secrets. If an API key is needed, tell me exactly which environment variable to set.
6. Run the available doctor / smoke checks.
7. Report back with:
   - what was installed;
   - which Python environment is being used;
   - how to start or verify the MCP server;
   - how to launch the optional web workbench;
   - one research prompt I can use next.
```

If your coding tool cannot edit its own MCP configuration automatically, ask it
to produce the exact config snippet and where to paste it.

## Start researching after setup

Once RH is installed, use research-language prompts instead of tool-language
commands:

```text
Create a topic on robust budget pacing for online advertising.
Search for recent papers, ingest the useful ones, and build a first literature map.
```

```text
Deep-read the most relevant papers in this topic.
Extract their claims, assumptions, limitations, datasets, metrics, and reproducibility risks.
```

```text
Based on the recorded evidence, identify research gaps that could become experiments.
For the top direction, prepare an experiment brief with baselines, metrics, ablations, and expected failure modes.
```

```text
Draft a related-work section from the recorded claims and evidence.
Keep the citations and claims traceable to the source papers.
```

## Manual install

If you prefer to install by hand:

```bash
./setup.sh
cp .env.example .env
rh --json doctor
```

Add at least one model provider when you want RH to run LLM-backed primitives:

```bash
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>
KIMI_API_KEY=<your-kimi-key>
```

Only one is required to start. Extra providers can be added later.

## Optional web workbench

The web workbench is available for browsing topics, papers, reports, and state.
It is optional; the recommended first path is still agent-driven.

```bash
# Backend
pip install -e "packages/research_harness_mcp[api]"
python -m research_harness_mcp.http_api

# Frontend
cd web
npm install
npm run dev
```

Open <http://localhost:3000>. A no-key product walkthrough is available at
<http://localhost:3000/demo>.

## How the harness works

Research Harness is not just a prompt collection. It is a control layer for
research agents:

- **Persistent state** — topics, papers, notes, claims, gaps, drafts, and
  reports stay in one research pool.
- **Typed research primitives** — actions like `paper_search`, `deep_read`,
  `claim_extract`, `gap_detect`, `experiment_handoff`, and `section_draft` are
  structured instead of ad hoc.
- **Stage gates** — research can move through `init → build → analyze → propose
  → experiment → write` with reviewable checkpoints.
- **Provenance** — important outputs can be traced back to papers, artifacts,
  tool calls, and model runs.
- **Agent interoperability** — the same research state can be used by Codex,
  Claude Code, Cursor, OpenClaw, and other MCP-capable agents.

## Agent-readable directory

If you are using a coding agent, ask it to start here:

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Project-level rules and RH operating constraints. |
| `docs/agent-guide.md` | How agents should use RH for research work. |
| `docs/quickstart.md` | Installation, configuration, and first-run details. |
| `skills/` | Portable workflows for literature search, gap analysis, claim extraction, paper writing, and more. |
| `docs/DEMO.md` | No-key and live demo paths. |
| `docs/TROUBLESHOOTING.md` | Common runtime and provider issues. |

## License

PolyForm Noncommercial 1.0.0. See [LICENSE](LICENSE).
