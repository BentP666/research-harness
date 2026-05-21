---
name: rh-codex-checkpoint
description: Create a compact Codex checkpoint before context pressure, compaction, handoff, or a new large Research Harness phase. Trigger on phrases like "rh-codex-checkpoint", "/compact", "checkpoint", "上下文压缩", "handoff", or when visible context is low.
---

# RH Codex Checkpoint

Use this skill to avoid losing Research Harness context during long Codex sessions.

## When to Run

- A major phase just completed.
- The next step would require large searches, many file reads, or multi-file edits.
- Visible context remaining is below 40%, or likely below 40% based on session length.
- Visible context remaining is below 30%: only checkpoint, summarize, or ask for compaction.

## Checkpoint Format

```markdown
## Goal
[Current objective]

## Completed
- [Durable facts/actions completed]

## Key Findings
- [Decisions, artifacts, paper ids, gotchas]

## Current State
- Topic/stage:
- Relevant files/artifacts:
- Verification status:

## Next Steps
1. ...
2. ...
3. ...

## Constraints
- [User preferences, tool limits, safety constraints]
```

## Persistence Rules

- Prefer recording durable research outputs with `orchestrator_record_artifact`.
- Use memory/session summary for agent handoff context.
- Do not create new top-level docs solely for a checkpoint unless the user asks or an existing doc location is clearly appropriate.
- If Codex cannot execute `/compact`, ask the user to run it and include the checkpoint text.
