# Research Harness Product Demo

Use this demo to show the GitHub release without requiring a live LLM key.
The goal is to communicate the product experience: a research question becomes
papers, evidence, gaps, and writing material inside one reusable workspace.

## Demo story

Default topic:

> Auto-Bidding / Budget Pacing in Online Advertising

Five-step narrative:

1. **Frame the workspace** — create a tracked research topic with scope and
   success criteria.
2. **Build a paper pool** — ingest candidate papers instead of leaving search
   results in chat logs.
3. **Deep-read into evidence** — convert papers into notes, claims,
   limitations, and reproducibility signals.
4. **Choose a direction** — compare gaps and objections before promoting a
   direction into an experiment brief.
5. **Write from recorded work** — draft reports and sections from traceable
   artifacts.

## No-key demo

Start the backend and frontend:

```bash
python -m research_harness_mcp.http_api
cd web && npm run dev
```

Open:

```text
http://localhost:3000/demo
```

The page includes a static product walkthrough. If the backend is running, the
"Replay canned run" button also replays pre-recorded responses from
`research_harness.demo.canned_auto_bidding` with zero API cost.

## Live demo with real models

For a real run, configure at least one provider in `.env` and use the normal
workflow:

```bash
cp .env.example .env
# add OPENAI_API_KEY, ANTHROPIC_API_KEY, KIMI_API_KEY, or another configured route

python -m research_harness_mcp.http_api
cd web && npm run dev
```

Then open the workbench and create a topic. A good live prompt for an agent is:

```text
Read AGENTS.md, docs/agent-guide.md, and skills/.
Create a topic on "robust budget pacing for online advertising".
Search for recent papers, ingest the useful ones, deep-read the top papers,
and record claims and gaps in RH.
```

## What to emphasize

- RH is not a chatbot. It is a workbench that persists the research state.
- The frontend shows progress and reviewable outputs; the agent runs the heavy
  research loop.
- Outputs are reusable: papers, claims, gaps, reports, and provenance survive
  across sessions.
- Advanced surfaces such as trend analysis are available, but they are not the
  core first-run story.
